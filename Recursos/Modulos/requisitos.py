"""Requisitos del sistema: detectarlos, bajarlos del FTP e instalarlos.

Este archivo es **el mismo en todas las apps**. Se edita acá, en MINIhub, y se
reparte con `python sincronizar_nucleo.py`. No agregarle nada de una app en
particular.

Lo usan dos lados, y por eso vive en el núcleo:

- **Cada app, al arrancar** (`ui_requisitos.chequear_al_inicio`), por si la copia
  llegó a mano y nunca pasó por MINIhub. Es el caso de hoy: MINIhub todavía no se
  reparte.
- **MINIhub, antes de instalar**, para resolver de una sola vez los requisitos de
  todas las apps que se van a poner en esa sesión, en vez de que cada una haga su
  propio UAC.

Hasta dónde llega esto (leer antes de confiar)
----------------------------------------------
**Un requisito que impide arrancar el intérprete no se puede chequear desde
acá.** Si falta el Universal CRT, `python313.dll` no carga y el bootloader de
PyInstaller muere con "Failed to load Python DLL" antes de ejecutar una sola
línea nuestra: este módulo nunca corre. Lo mismo si el antivirus se llevó una DLL
de `_internal`, o si alguien ejecutó el `.exe` desde adentro de un `.zip` (Windows
extrae al temp **solo** el ejecutable, sin `_internal/`, y da ese mismo error).

O sea: esto sirve para lo que se necesita *después* de arrancar y para avisar con
un cartel decente en vez de un crash. Lo que evita el fallo de arranque es cómo se
reparte el build — un autoextraíble o MINIhub, nunca un `.zip` suelto.

Se deja igualmente porque el mismo mensaje de Windows ("no se puede encontrar el
módulo especificado") tapa tres causas distintas, y porque en la máquina donde
falta el redistribuible **el diagnóstico lo tiene que dar alguien**: si la app
arrancó, este módulo lo dice con nombre y apellido y lo arregla solo.

Cómo decide si algo falta
-------------------------
Cada requisito trae varias pruebas y **alcanza con que una pase**. Es a propósito:
un falso negativo (decirle "instalá esto" a alguien que ya lo tiene) es molesto y
manda a un UAC al pedo, mientras que un falso positivo no empeora nada — si de
verdad faltaba, la app iba a fallar igual. Ante la duda, callarse.

La lista local (`REQUISITOS_BASE`) es la que se usa siempre; el `requisitos.json`
firmado del FTP puede corregirla o agregarle requisitos sin recompilar nada. La
detección es **declarativa** (`registro`, `dll`, `windows`) y la interpreta este
archivo: el JSON remoto nunca describe código a ejecutar.

Seguridad
---------
El `requisitos.json` va firmado con la misma clave Ed25519 que los manifiestos y
se rechaza si no verifica, y el instalador se verifica contra el SHA-256 que
figura en ese JSON firmado antes de ejecutarlo.

Esto no es opcional ni es paranoia de manual: bajar un `.exe` de un FTP de texto
plano cuyas credenciales viajan dentro de cada build **y ejecutarlo con permisos
de administrador** es la forma más directa que existe de convertir una fuga de
credenciales en control total de todas las PCs de la oficina. Es el mismo
razonamiento que ya obliga a firmar los manifiestos (ver `nucleo.py`), pero peor,
porque acá encima hay elevación de por medio. Si alguna vez alguien quiere
"probar rápido" salteando la verificación, no.
"""

import ctypes
import os
import subprocess
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

from . import nucleo
from .ftp_config import RUTA_LISTA_REQUISITOS, ruta_instalador

# Códigos de salida que los instaladores de Microsoft dan por buenos.
#   0     instalado
#   1638  ya hay una versión igual o más nueva (no es un error)
#   3010  instalado, pide reiniciar Windows
EXITOS_POR_DEFECTO = (0, 1638, 3010)
EXITOS_CON_REINICIO = (3010,)
# 1602 = cancelado por el usuario, 1223 = cancelado el UAC.
CANCELADOS = (1602, 1223)


# ==========================================
# LA LISTA
# ==========================================
# Copia local de la lista, para que esto funcione sin FTP y en la primera
# ejecución. El `requisitos.json` firmado del FTP la pisa entrada por entrada
# (por `nombre`) y puede agregar otras.
#
# `instalador` va vacío acá a propósito: el SHA-256 del `VC_redist.x64.exe` sale
# del JSON firmado, no de una constante compilada que quedaría vieja el día que
# Microsoft publique otro. Sin FTP se detecta igual y se cae al arreglo manual.
REQUISITOS_BASE = [
    {
        "nombre": "vcredist-x64",
        "titulo": "Microsoft Visual C++ 2015-2022 (x64)",
        "porque": (
            "Lo necesitan el intérprete de Python y las bibliotecas de Qt que "
            "usa la app."
        ),
        "arquitectura": "x64",
        "detectar": [
            {"tipo": "registro",
             "clave": r"HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
             "valor": "Installed", "igual": 1},
            {"tipo": "dll", "nombre": "vcruntime140_1.dll"},
        ],
        "manual": "https://aka.ms/vs/17/release/vc_redist.x64.exe",
    },
    {
        # Sin instalador: en Windows 10/11 viene con el sistema y en Windows 8.1
        # lo pone Windows Update (KB2999226), no un `.exe` que podamos repartir.
        # Se detecta igual porque es la causa más difícil de adivinar del
        # "no se puede encontrar el módulo especificado".
        "nombre": "ucrt",
        "titulo": "Universal C Runtime de Windows",
        "porque": "Es parte de Windows. Si falta, el sistema está sin actualizar.",
        "detectar": [
            {"tipo": "dll", "nombre": "api-ms-win-crt-runtime-l1-1-0.dll"},
            {"tipo": "dll", "nombre": "ucrtbase.dll"},
        ],
        "manual": "https://support.microsoft.com/help/2999226",
        "arreglo_manual": (
            "Pasá Windows Update hasta que no queden actualizaciones pendientes "
            "y volvé a abrir la app."
        ),
    },
]


class Requisito:
    """Un requisito del sistema, con cómo detectarlo y cómo instalarlo."""

    def __init__(self, datos):
        self.datos = dict(datos)
        self.nombre = str(datos.get("nombre") or "")
        self.titulo = str(datos.get("titulo") or self.nombre)
        self.porque = str(datos.get("porque") or "")
        self.manual = str(datos.get("manual") or "")
        self.arreglo_manual = str(datos.get("arreglo_manual") or "")
        self.arquitectura = str(datos.get("arquitectura") or "")
        self.instalador = datos.get("instalador") or {}

    def __repr__(self):
        return f"<Requisito {self.nombre}>"

    @property
    def se_puede_instalar(self):
        """True si tenemos un instalador identificado por hash para bajarlo."""
        return bool(nucleo._es_sha(self.instalador.get("sha256")))

    @property
    def tam(self):
        try:
            return int(self.instalador.get("tam") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def aplica(self):
        """False si el requisito es de otra arquitectura que la del proceso.

        Todas las apps se compilan a 64 bits, pero dejarlo declarado evita que un
        build de 32 bits del futuro instale el redistribuible equivocado.
        """
        if not self.arquitectura:
            return True
        propia = "x64" if sys.maxsize > 2 ** 32 else "x86"
        return self.arquitectura == propia

    def presente(self):
        """True si el requisito ya está en esta máquina.

        Alcanza con que **una** de las pruebas pase (ver el encabezado). Si no hay
        ninguna prueba, se da por presente: un requisito que no sabemos detectar
        no es motivo para frenar a nadie.
        """
        pruebas = self.datos.get("detectar") or []
        if not pruebas:
            return True
        return any(_probar(p) for p in pruebas)


# ==========================================
# DETECCIÓN
# ==========================================
def _probar(prueba):
    tipo = str(prueba.get("tipo") or "")
    try:
        if tipo == "dll":
            return _hay_dll(prueba.get("nombre"))
        if tipo == "registro":
            return _hay_registro(prueba)
        if tipo == "windows":
            return _windows_al_menos(prueba.get("minimo"))
    except Exception:
        # Una prueba que revienta no puede impedir que la app abra.
        return False
    return False


def _hay_dll(nombre):
    """True si Windows puede cargar esa DLL por su nombre.

    Es la prueba más honesta que hay: no mira registros ni versiones, prueba
    exactamente lo que va a hacer el sistema cuando la app la necesite. Se libera
    enseguida; cargarla de más no molesta porque si la app anda ya está cargada.

    **Solo nombres, nunca rutas.** Cargar una DLL es ejecutar su `DllMain`, así
    que esto es un `LoadLibrary` con un nombre que viene de un archivo remoto. El
    archivo va firmado, pero eso protege del que no tiene la clave, no de un
    descuido al armar el JSON: con una ruta se podría terminar cargando algo de
    una carpeta escribible por cualquiera. Con un nombre suelto manda el orden de
    búsqueda de Windows, que empieza por System32.
    """
    nombre = str(nombre or "")
    if not nombre or "/" in nombre or "\\" in nombre or ":" in nombre:
        return False
    try:
        ctypes.WinDLL(nombre)
        return True
    except (OSError, AttributeError):
        return False


def _hay_registro(prueba):
    """Lee un valor del registro y lo compara.

    Siempre en la vista de 64 bits (`KEY_WOW64_64KEY`): las claves de los
    redistribuibles x64 viven ahí, y un Python de 32 bits las vería redirigidas a
    `Wow6432Node` y no las encontraría.
    """
    import winreg

    raices = {
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU": winreg.HKEY_CURRENT_USER,
    }
    clave = str(prueba.get("clave") or "").replace("/", "\\")
    raiz_txt, _, sub = clave.partition("\\")
    raiz = raices.get(raiz_txt.upper())
    if raiz is None or not sub:
        return False

    try:
        with winreg.OpenKey(raiz, sub, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            nombre_valor = prueba.get("valor")
            if not nombre_valor:
                return True          # Alcanza con que la clave exista.
            valor, _ = winreg.QueryValueEx(k, str(nombre_valor))
    except OSError:
        return False

    if "igual" in prueba:
        return str(valor) == str(prueba["igual"])
    if "minimo" in prueba:
        return nucleo.tupla_version(valor) >= nucleo.tupla_version(prueba["minimo"])
    return True


def _windows_al_menos(minimo):
    """Compara la build real de Windows contra un mínimo.

    Usa `sys.getwindowsversion()`, que en Python viene de `RtlGetVersion` y no
    miente por compatibilidad como sí lo hace `GetVersionEx`.
    """
    if not minimo:
        return True
    v = sys.getwindowsversion()
    return (v.major, v.minor, v.build) >= nucleo.tupla_version(minimo)


# ==========================================
# QUÉ FALTA
# ==========================================
def lista(sesion=None, solo_local=False):
    """Devuelve los `Requisito` conocidos: la lista local, corregida por la del
    FTP si se puede leer.

    Nunca levanta por un problema de red: si el FTP no contesta se usa la copia
    local, que alcanza para detectar (lo que no se puede sin FTP es *instalar*).
    """
    por_nombre = {r["nombre"]: dict(r) for r in REQUISITOS_BASE}

    if not solo_local:
        try:
            for datos in _leer_lista_remota(sesion):
                nombre = str(datos.get("nombre") or "")
                if not nombre:
                    continue
                por_nombre.setdefault(nombre, {}).update(datos)
        except Exception:
            pass

    return [Requisito(d) for d in por_nombre.values()]


def _leer_lista_remota(sesion=None):
    """Lee `requisitos/requisitos.json` del FTP y verifica su firma."""
    propia = sesion is None
    s = sesion or nucleo.Sesion()
    try:
        import json
        documento = json.loads(s.leer(RUTA_LISTA_REQUISITOS).decode("utf-8"))
    finally:
        if propia:
            s.cerrar()
    if not nucleo.firma_valida(documento):
        raise nucleo.FirmaInvalida("la firma de requisitos.json no verifica")
    return documento.get("requisitos") or []


def faltantes(nombres=None, sesion=None, solo_local=False):
    """Los requisitos que esta máquina no cumple.

    `nombres` limita el chequeo a esos requisitos (los que declara una app en su
    manifiesto). Sin `nombres` se chequean todos los conocidos.
    """
    pedidos = set(nombres) if nombres is not None else None
    faltan = []
    for req in lista(sesion=sesion, solo_local=solo_local):
        if pedidos is not None and req.nombre not in pedidos:
            continue
        if not req.aplica:
            continue
        if req.presente():
            continue
        faltan.append(req)
    return faltan


# ==========================================
# DESCARGA
# ==========================================
def descargar(req, carpeta=None, progreso_cb=None, cancelar_cb=None, sesion=None):
    """Baja el instalador de un requisito y devuelve su ruta local.

    Verifica el SHA-256 contra el del `requisitos.json` firmado y borra el
    archivo si no coincide: nada que no verifique llega a ejecutarse.

    Va a `%TEMP%` y no a la carpeta de la app a propósito. El staging del updater
    tiene que estar en el mismo volumen porque termina en un `os.replace()`; acá
    no se renombra nada, solo se ejecuta y se borra.
    """
    sha = req.instalador.get("sha256")
    if not nucleo._es_sha(sha):
        raise ValueError(f"{req.nombre} no tiene un instalador identificado por hash")

    carpeta = Path(carpeta or tempfile.mkdtemp(prefix="requisitos-mini-"))
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = str(req.instalador.get("nombre") or f"{req.nombre}.exe")
    destino = carpeta / nombre

    # Puede haber quedado de un intento anterior que se cortó.
    if destino.is_file() and nucleo.sha256_archivo(destino) == sha:
        return destino

    total = req.tam
    hechos = 0
    parcial = destino.parent / (destino.name + ".parcial")

    propia = sesion is None
    s = sesion or nucleo.Sesion()
    try:
        with open(parcial, "wb") as f:
            def _escribir(bloque):
                nonlocal hechos
                if cancelar_cb and cancelar_cb():
                    raise nucleo.ActualizacionCancelada()
                f.write(bloque)
                hechos += len(bloque)
                if progreso_cb:
                    progreso_cb(hechos, total)

            s.ftp.retrbinary(
                f"RETR {ruta_instalador(sha)}", _escribir, blocksize=131072
            )
    except nucleo.ActualizacionCancelada:
        parcial.unlink(missing_ok=True)
        raise
    except Exception as e:
        parcial.unlink(missing_ok=True)
        raise RuntimeError(f"no se pudo bajar el instalador de {req.titulo}: {e}") from e
    finally:
        if propia:
            s.cerrar()

    if nucleo.sha256_archivo(parcial) != sha:
        parcial.unlink(missing_ok=True)
        raise RuntimeError(
            f"el instalador de {req.titulo} llegó corrupto "
            "(hash distinto al del requisitos.json firmado)"
        )
    os.replace(parcial, destino)
    return destino


# ==========================================
# INSTALACIÓN
# ==========================================
class ResultadoInstalacion:
    """Qué pasó al instalar un requisito."""

    def __init__(self, codigo, salida=None, detalle=""):
        self.codigo = codigo          # "ok" | "reinicio" | "cancelado" | "error"
        self.salida = salida          # Código de salida del instalador, si hubo.
        self.detalle = detalle

    @property
    def bien(self):
        return self.codigo in ("ok", "reinicio")

    def __repr__(self):
        return f"<ResultadoInstalacion {self.codigo} salida={self.salida}>"


def es_administrador():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def instalar(req, ruta_instalador_local, elevar=True):
    """Corre el instalador en silencio y devuelve un `ResultadoInstalacion`.

    "Silencioso" quiere decir sin ventanas del instalador, **no sin UAC**: el
    redistribuible escribe en `C:\\Windows\\System32` y eso pide elevación sí o
    sí. Si el técnico no es administrador de su PC, el UAC le va a pedir una
    credencial que no tiene y esto va a volver `cancelado`; ahí el único camino
    es el manual, con alguien que pueda elevar. No hay forma de esquivarlo y
    conviene no fingir que la hay.

    Después de instalar se vuelve a detectar: el código de salida dice que el
    instalador terminó bien, no que el requisito ahora esté. Son cosas distintas
    y ya hubo casos de instaladores que devuelven 0 sin haber puesto nada.
    """
    args = [str(a) for a in (req.instalador.get("args") or ["/install", "/quiet", "/norestart"])]
    exitos = tuple(req.instalador.get("exitos") or EXITOS_POR_DEFECTO)
    reinicio = tuple(req.instalador.get("reinicio") or EXITOS_CON_REINICIO)

    try:
        if elevar and not es_administrador():
            salida = _correr_elevado(ruta_instalador_local, args)
        else:
            salida = subprocess.run(
                [str(ruta_instalador_local), *args],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).returncode
    except PermissionError:
        return ResultadoInstalacion("cancelado", None, "el UAC se rechazó")
    except Exception as e:
        return ResultadoInstalacion("error", None, str(e))

    if salida in CANCELADOS:
        return ResultadoInstalacion("cancelado", salida, "el UAC se rechazó")

    if salida not in exitos:
        return ResultadoInstalacion(
            "error", salida,
            f"el instalador terminó con el código {salida}",
        )

    if not req.presente():
        return ResultadoInstalacion(
            "error", salida,
            "el instalador dijo que terminó bien pero el requisito sigue sin "
            "detectarse",
        )

    return ResultadoInstalacion(
        "reinicio" if salida in reinicio else "ok", salida
    )


def abrir_para_instalar_a_mano(req, ruta_instalador_local=None):
    """Abre el instalador con su interfaz normal, o la página de descarga.

    Es la salida cuando la instalación silenciosa no se pudo: mejor que el
    técnico apriete Siguiente tres veces a que se quede sin app.
    """
    destino = str(ruta_instalador_local or req.manual)
    if not destino:
        return False
    try:
        os.startfile(destino)     # noqa: S606  (es una acción pedida por el usuario)
        return True
    except Exception:
        return False


# --- Elevación ---
class _SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SEE_MASK_NOASYNC = 0x00000100
_SW_HIDE = 0
_INFINITO = 0xFFFFFFFF
_ERROR_CANCELLED = 1223


def _correr_elevado(exe, args):
    """Lanza el instalador con el verbo `runas` (UAC) y espera a que termine.

    Se usa `ShellExecuteExW` y no `ShellExecuteW` porque el segundo no devuelve
    un handle del proceso y no habría forma de esperarlo ni de leer su código de
    salida — y sin eso no se sabe si el requisito quedó instalado.

    `SEE_MASK_NOASYNC` es obligatorio acá: sin él la llamada puede volver antes
    de que el shell haya terminado de arrancar el proceso, y este hilo (que no
    bombea mensajes, corre en un QThread) se quedaría con un handle inválido.
    """
    info = _SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_NOASYNC
    info.lpVerb = "runas"
    info.lpFile = str(exe)
    info.lpParameters = subprocess.list2cmdline(args)
    info.nShow = _SW_HIDE

    # `use_last_error=True` no es un detalle: sin eso `ctypes.get_last_error()`
    # devuelve siempre 0, porque ctypes solo guarda el GetLastError del sistema
    # cuando se le pide. Sin él no se podría distinguir "el usuario dijo que no
    # al UAC" (1223, que es normal y no hay que reportar como falla) de un error
    # de verdad.
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == _ERROR_CANCELLED:
            raise PermissionError("el usuario rechazó el UAC")
        raise OSError(f"no se pudo lanzar el instalador (error {error})")

    if not info.hProcess:
        raise OSError("el instalador se lanzó pero no devolvió un proceso")

    try:
        ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, _INFINITO)
        salida = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(
            info.hProcess, ctypes.byref(salida)
        )
        return int(salida.value)
    finally:
        ctypes.windll.kernel32.CloseHandle(info.hProcess)
