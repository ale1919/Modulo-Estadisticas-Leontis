"""Instalación y actualización de apps desde el FTP.

Este archivo es **el mismo en todas las apps**. Se edita acá, en MINIhub, y se
reparte con `python sincronizar_nucleo.py`. No agregarle nada que dependa de una
app en particular: lo único que sabe es el nombre de la app y su carpeta.

Cómo funciona
-------------
Cada app publicada tiene en el FTP un `version.json` firmado con la lista de sus
archivos (ruta, tamaño, SHA-256), y los archivos viven en un almacén **compartido
entre todas las apps** guardados por contenido: `objetos/<xx>/<sha256>`.

Guardar por contenido y no por nombre da cuatro cosas:

- Publicar una versión sube solo lo que cambió.
- El cliente baja solo los hashes que no tiene. En un build onedir de PyInstaller
  el 98% del peso (los ~130 MB de `_internal`) casi nunca cambia, así que un
  cambio de código son ~3 MB.
- Renombrar un archivo entre versiones no cuesta descarga: el contenido ya está.
- El nombre del objeto **es** su verificación de integridad.

Y como el almacén es compartido, instalar la segunda app PySide6 tampoco cuesta
descarga: los objetos se copian de la primera, que ya está en disco
(`carpetas_donantes`).

**Instalar es exactamente lo mismo que actualizar, con la carpeta vacía.**
`armar_plan()` contra un directorio vacío pide todos los archivos y `aplicar()`
los pone. No hay un camino de código separado para instalar, y conviene no
romper esa propiedad.

Reemplazo en caliente
---------------------
Windows no deja *sobrescribir* un `.exe` o una DLL en uso, pero sí
*renombrarlos* dentro del mismo volumen. Por eso el archivo viejo se mueve a
`<nombre>.viejo-<pid>` y el nuevo ocupa su lugar; los `.viejo-*` se borran en el
arranque siguiente, cuando ya nadie los tiene abiertos. Por eso también el
staging va en `<carpeta app>/.actualizacion` y no en `%TEMP%`: `os.replace()` no
puede mover entre volúmenes distintos, y la app puede estar en otro disco.

La carpeta de configuración de cada app (`RECURSOS/CONFIG` por defecto) queda
fuera del manifiesto y el núcleo nunca la toca, así que actualizar no borra la
config de nadie.

Seguridad
---------
Los manifiestos y el catálogo van firmados con Ed25519 y se rechaza cualquiera
cuya firma no verifique. La clave privada existe solo en la máquina desde la que
se publica.

Esto **no es opcional**: las credenciales del FTP están hardcodeadas y viajan
dentro de cada `.exe`, y el FTP es texto plano. Sin firma, cualquiera que extraiga
esas credenciales podría reemplazar un objeto y su código se ejecutaría solo en la
PC de todos los técnicos: el auto-update convierte una fuga de credenciales en
ejecución remota de código en toda la oficina. Con firma, lo peor que puede hacer
es borrar o corromper (el cliente avisa y entra con la versión que tenía).

Una sola clave para todas las apps: la clave es la identidad del que publica, no
de la app.
"""

import datetime
import ftplib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .ftp_config import (FTP_CONFIG, RUTA_CATALOGO, RUTA_OBJETOS, ruta_manifiesto,
                         ruta_objeto)

# Clave pública Ed25519 (hex) del que publica. La privada NO va en el repo:
# vive en %USERPROFILE%\.claves\utilidadesmini_release_ed25519.pem.
# Se genera una única vez, desde MINIhub:
#     python publicar_release.py --generar-clave
#
# Es la misma en todas las apps. Si se cambia, todos los .exe ya repartidos dejan
# de aceptar actualizaciones y hay que recompilarlos y repartirlos a mano.
CLAVE_PUBLICA_HEX = "8ff92f7b34fe7d0a6d93e590edfaa57ab8f6e855376d221aa59284b8fad55e37"

# Carpeta de configuración que el updater nunca toca. Por app se puede cambiar
# desde el catálogo: no todas la tienen en el mismo lugar.
INTOCABLES_POR_DEFECTO = ("RECURSOS/CONFIG",)

SUFIJO_VIEJO = ".viejo-"
NOMBRE_STAGING = ".actualizacion"
NOMBRE_INSTALADO = "instalado.json"

# Corto a propósito: si el FTP no está, nadie tiene que esperar para entrar.
TIMEOUT_FTP = 12
TIMEOUT_FTP_SUBIDA = 120


# ==========================================
# FIRMA
# ==========================================
def canonizar(documento):
    """Devuelve los bytes exactos que se firman: el documento sin el campo
    `firma`, en JSON canónico (claves ordenadas, sin espacios).

    El publicador y el cliente tienen que calcular esto igual, byte por byte, o
    la firma no verifica. Por eso la función vive acá y los publicadores la
    importan en vez de tener su propia copia.
    """
    datos = {k: v for k, v in documento.items() if k != "firma"}
    return json.dumps(
        datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def firma_valida(documento):
    """True si la firma del documento corresponde a CLAVE_PUBLICA_HEX."""
    firma = documento.get("firma")
    if not firma:
        return False
    try:
        publica = Ed25519PublicKey.from_public_bytes(bytes.fromhex(CLAVE_PUBLICA_HEX))
        publica.verify(bytes.fromhex(firma), canonizar(documento))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ==========================================
# VERSIONES
# ==========================================
def tupla_version(v):
    """'1.10.2' -> (1, 10, 2). Compara por número y no alfabéticamente, para que
    1.10 quede después de 1.9 y no antes."""
    numeros = tuple(int(p) for p in re.findall(r"\d+", str(v))[:4])
    return numeros or (0,)


def es_mas_nueva(remota, local):
    return tupla_version(remota) > tupla_version(local)


# ==========================================
# HASH
# ==========================================
def sha256_archivo(ruta, bloque=1 << 20):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(bloque), b""):
            h.update(chunk)
    return h.hexdigest()


def _es_sha(s):
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(s or "")))


# ==========================================
# SESIÓN FTP
# ==========================================
class Sesion:
    """Una conexión FTP reusable.

    MINIhub necesita leer el catálogo y el manifiesto de cada app; hacerlo con
    una conexión por archivo multiplica la latencia por la cantidad de apps.

    Se usa como context manager:

        with Sesion() as s:
            cat = s.catalogo()
            for app in cat["apps"]:
                man = s.manifiesto(app["nombre"])
    """

    def __init__(self, timeout=TIMEOUT_FTP):
        self.ftp = ftplib.FTP(FTP_CONFIG["host"], timeout=timeout)
        self.ftp.login(FTP_CONFIG["user"], FTP_CONFIG["pass"])
        self.ftp.set_pasv(True)
        self.ftp.voidcmd("TYPE I")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cerrar()
        return False

    def cerrar(self):
        try:
            self.ftp.quit()
        except Exception:
            try:
                self.ftp.close()
            except Exception:
                pass

    # --- Lectura ---
    def leer(self, remoto, max_bytes=8_000_000):
        """Baja un archivo remoto chico a memoria (un manifiesto, el catálogo)."""
        buf = bytearray()

        def _cb(bloque):
            buf.extend(bloque)
            if len(buf) > max_bytes:
                raise ValueError(f"{remoto} es más grande de lo esperado")

        self.ftp.retrbinary(f"RETR {remoto}", _cb, blocksize=65536)
        return bytes(buf)

    def _json_firmado(self, remoto):
        documento = json.loads(self.leer(remoto).decode("utf-8"))
        if not firma_valida(documento):
            raise FirmaInvalida(f"la firma de {remoto} no verifica")
        return documento

    def manifiesto(self, app):
        """Manifiesto firmado de una app. Lanza excepción si no existe (la app
        todavía no se publicó), si el JSON está roto, si es de otra app o si la
        firma no verifica."""
        documento = self._json_firmado(ruta_manifiesto(app))
        if documento.get("app") != app:
            raise ValueError(
                f"el manifiesto de {app} dice ser de {documento.get('app')!r}"
            )
        return documento

    def catalogo(self):
        """Catálogo firmado: qué apps existen. No trae versiones a propósito
        (ver `catalogo.py`)."""
        return self._json_firmado(RUTA_CATALOGO)


class FirmaInvalida(Exception):
    """El documento remoto no está firmado por quien dice. Se ignora entero."""


class ActualizacionCancelada(Exception):
    """El usuario canceló mientras se bajaba la actualización."""


def obtener_manifiesto(app):
    """Conveniencia para la autoactualización de una app: abre su propia
    conexión, lee su manifiesto y cierra."""
    with Sesion() as s:
        return s.manifiesto(app)


# ==========================================
# RUTAS
# ==========================================
def ruta_segura(rel, intocables=INTOCABLES_POR_DEFECTO):
    """True si `rel` es una ruta relativa que cae dentro de la carpeta de la app
    y no está protegida.

    El manifiesto va firmado, así que esto es defensa en profundidad: evita que
    un manifiesto mal armado escriba en C:\\Windows vía "..\\..\\" o pise la
    carpeta de configuración.

    La comparación con `intocables` es **sin distinguir mayúsculas**, a propósito.
    Estas apps son solo de Windows y ahí `Recursos/Config` y `RECURSOS/CONFIG` son
    la misma carpeta, pero las rutas del manifiesto salen con la capitalización
    real del disco. Comparando como texto exacto, declarar `RECURSOS/CONFIG` en una
    app cuya carpeta se llama `Recursos/Config` no protegería nada: la config se
    publicaría y el updater se la pisaría al usuario, en silencio. No es hipotético
    (`ModuloEstadisticasLeontis` usa esa capitalización).
    """
    if not rel or str(rel).startswith(("/", "\\")) or ":" in str(rel):
        return False
    partes = [p for p in str(rel).replace("\\", "/").split("/") if p]
    if not partes or ".." in partes or "." in partes:
        return False
    norm = "/".join(partes)
    norm_cmp = norm.lower()
    for protegida in intocables:
        protegida = protegida.replace("\\", "/").strip("/").lower()
        if protegida and (
            norm_cmp == protegida or norm_cmp.startswith(protegida + "/")
        ):
            return False
    if SUFIJO_VIEJO in norm or partes[0].lower() == NOMBRE_STAGING.lower():
        return False
    return True


# ==========================================
# PLAN
# ==========================================
class Plan:
    """Qué hay que bajar, qué hay que escribir y qué hay que borrar."""

    def __init__(self, manifiesto):
        self.manifiesto = manifiesto
        self.app = manifiesto.get("app", "?")
        self.version = manifiesto.get("version", "?")
        self.notas = manifiesto.get("notas", "")
        self.entradas = []      # [{ruta, sha256, tam}] las que hay que escribir
        self.a_bajar = {}       # sha256 -> tam de los objetos que faltan
        self.locales = {}       # sha256 -> Path de contenido que ya está en disco
        self.borrar = []        # rutas relativas que dejaron de existir
        self.verificados = set()  # sha256 ya presentes y verificados en el staging

    @property
    def bytes_a_bajar(self):
        return sum(self.a_bajar.values())

    @property
    def bytes_totales(self):
        return sum(e["tam"] for e in self.entradas)

    @property
    def hay_algo_que_hacer(self):
        return bool(self.entradas or self.borrar)


# ==========================================
# INSTALACIÓN
# ==========================================
class Instalacion:
    """Una app instalada (o por instalar) en una carpeta.

    Toda la lógica es agnóstica de la ruta: una app se autoactualiza con
    `Instalacion(APP_NAME, BASE_DIR)` y MINIhub actualiza a las demás con
    `Instalacion("OtraApp", ruta)`.
    """

    def __init__(self, app, carpeta, intocables=INTOCABLES_POR_DEFECTO):
        self.app = app
        self.carpeta = Path(carpeta)
        self.intocables = tuple(intocables)
        self.staging = self.carpeta / NOMBRE_STAGING
        # El manifiesto de lo último que se aplicó va DENTRO de la carpeta
        # intocable: así el updater no puede pisárselo a sí mismo.
        self.instalado = self.carpeta / self.intocables[0] / NOMBRE_INSTALADO

    def __repr__(self):
        return f"Instalacion({self.app!r}, {str(self.carpeta)!r})"

    def ruta_segura(self, rel):
        return ruta_segura(rel, self.intocables)

    # --- Estado ---
    def manifiesto_instalado(self):
        try:
            with open(self.instalado, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def version_instalada(self):
        """Versión que hay en disco, sin ejecutar la app.

        `APP_VERSION` está compilada dentro del `.exe`, así que desde afuera no se
        lee. `instalado.json` la guarda, y lo escribe `registrar_instalado()`
        tanto cuando la app se autoactualiza como cuando MINIhub la instala.

        Devuelve None si no se sabe: carpeta vacía, o una copia instalada a mano
        que nunca pasó por el updater. "No se sabe" se trata como "replanificar":
        cuesta hashear la carpeta y **0 bytes de descarga** si ya estaba al día.
        """
        man = self.manifiesto_instalado()
        return (man or {}).get("version") or None

    def esta_instalada(self):
        """True si la carpeta tiene algo que parezca un build."""
        if not self.carpeta.is_dir():
            return False
        for hijo in self.carpeta.iterdir():
            if hijo.name in (NOMBRE_STAGING,) or SUFIJO_VIEJO in hijo.name:
                continue
            return True
        return False

    def escribible(self):
        """True si podemos escribir en la carpeta (falla en Program Files sin
        permisos de administrador)."""
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            prueba = self.carpeta / f".permiso-{os.getpid()}.tmp"
            prueba.write_bytes(b"")
            prueba.unlink()
            return True
        except OSError:
            return False

    def en_onedrive(self):
        """La sincronización de OneDrive pelea con el renombrado de archivos y
        puede dejar el build hecho de mitades de dos versiones."""
        return "onedrive" in str(self.carpeta).lower()

    # --- Plan ---
    def armar_plan(self, manifiesto, donantes=()):
        """Compara el manifiesto contra lo que hay en disco.

        Hashea solo los archivos cuyo tamaño coincide con el del manifiesto: si
        el tamaño ya difiere, el contenido difiere y no hace falta leerlo.

        `donantes` son otras carpetas de instalación (las apps hermanas) de donde
        se puede sacar un objeto en vez de bajarlo. Es lo que hace que instalar
        la segunda app PySide6 no cueste 130 MB. Nada de lo que se saca de un
        donante se cree por su nombre: se hashea antes de usarlo.
        """
        plan = Plan(manifiesto)

        for e in manifiesto.get("archivos", []):
            rel = str(e.get("ruta", "")).replace("\\", "/")
            sha = str(e.get("sha256", "")).lower()
            if not self.ruta_segura(rel) or not _es_sha(sha):
                continue
            try:
                tam = int(e.get("tam", 0) or 0)
            except (TypeError, ValueError):
                tam = 0

            destino = self.carpeta / rel
            if destino.is_file():
                try:
                    if destino.stat().st_size == tam:
                        sha_local = sha256_archivo(destino)
                        plan.locales.setdefault(sha_local, destino)
                        if sha_local == sha:
                            continue  # Ya está bien.
                except OSError:
                    pass

            plan.entradas.append({"ruta": rel, "sha256": sha, "tam": tam})

        # Lo que falta después de comparar ruta por ruta.
        faltan = {
            e["sha256"]: e["tam"]
            for e in plan.entradas
            if e["sha256"] not in plan.locales
        }

        # Antes de bajar, buscar el contenido por hash en disco. El primer lugar
        # donde mirar es la propia carpeta: comparar ruta por ruta no encuentra un
        # archivo que se **renombró** entre versiones (la ruta nueva no existe
        # todavía y la vieja no está en el manifiesto nuevo, así que nadie la
        # mira), pero el índice sí, porque va por contenido. Después, las apps
        # hermanas: casi todas son PySide6 y comparten los ~130 MB de _internal.
        if faltan:
            self._buscar_por_hash(plan, faltan, [self.carpeta, *donantes])

        plan.a_bajar = {
            sha: tam for sha, tam in faltan.items() if sha not in plan.locales
        }

        # Borrados: solo archivos que estaban en el manifiesto anterior y ya no
        # figuran. Nunca se borra algo que no pusimos nosotros; si no hay
        # manifiesto previo (instalación hecha a mano), no se borra nada.
        anterior = self.manifiesto_instalado()
        if anterior:
            vigentes = {
                str(e.get("ruta", "")).replace("\\", "/")
                for e in manifiesto.get("archivos", [])
            }
            for e in anterior.get("archivos", []):
                rel = str(e.get("ruta", "")).replace("\\", "/")
                if rel in vigentes or not self.ruta_segura(rel):
                    continue
                if (self.carpeta / rel).exists():
                    plan.borrar.append(rel)

        return plan

    def _buscar_por_hash(self, plan, faltan, carpetas):
        """Busca en disco, por contenido, los hashes que faltan.

        Usa el `instalado.json` de cada carpeta como índice (sha -> rutas) para no
        tener que hashear 130 MB por carpeta. Ese índice es solo una pista: el
        archivo se hashea igual antes de darlo por bueno, así que un
        `instalado.json` desactualizado o mentiroso no puede colar contenido
        equivocado, solo desperdiciar una lectura.
        """
        vistas = set()
        for carpeta in carpetas:
            if not faltan:
                return
            carpeta = Path(carpeta)
            try:
                clave = carpeta.resolve()
            except OSError:
                continue
            if clave in vistas:
                continue
            vistas.add(clave)

            indice = _indice_de(carpeta)
            for sha in list(faltan):
                if sha in plan.locales:
                    continue
                for rel in indice.get(sha, ()):
                    candidato = carpeta / rel
                    try:
                        if not candidato.is_file():
                            continue
                        if candidato.stat().st_size != faltan[sha]:
                            continue
                        if sha256_archivo(candidato) != sha:
                            continue
                    except OSError:
                        continue
                    plan.locales[sha] = candidato
                    break

    # --- Descarga ---
    def descargar_objetos(self, plan, progreso_cb=None, cancelar_cb=None,
                          sesion=None):
        """Baja al staging los objetos que faltan.

        `progreso_cb(bytes_hechos, bytes_totales)` se llama tras cada bloque.
        `cancelar_cb()` se consulta seguido: si devuelve True se aborta.
        Cada objeto se verifica contra su SHA-256 y si no coincide se descarta.
        """
        if not plan.a_bajar:
            return
        self.staging.mkdir(parents=True, exist_ok=True)
        total = plan.bytes_a_bajar
        hechos = 0

        propia = sesion is None
        s = sesion or Sesion()
        try:
            for sha, tam in plan.a_bajar.items():
                if cancelar_cb and cancelar_cb():
                    raise ActualizacionCancelada()

                destino = self.staging / sha
                # Puede haber quedado de un intento anterior que se cortó.
                if destino.is_file() and sha256_archivo(destino) == sha:
                    plan.verificados.add(sha)
                    hechos += tam
                    if progreso_cb:
                        progreso_cb(hechos, total)
                    continue

                parcial = destino.with_suffix(".parcial")
                with open(parcial, "wb") as f:
                    def _escribir(bloque):
                        nonlocal hechos
                        if cancelar_cb and cancelar_cb():
                            raise ActualizacionCancelada()
                        f.write(bloque)
                        hechos += len(bloque)
                        if progreso_cb:
                            progreso_cb(hechos, total)

                    try:
                        s.ftp.retrbinary(
                            f"RETR {ruta_objeto(sha)}", _escribir, blocksize=131072
                        )
                    except ActualizacionCancelada:
                        raise
                    except Exception as e:
                        raise RuntimeError(f"no se pudo bajar {sha[:12]}…: {e}") from e

                if sha256_archivo(parcial) != sha:
                    parcial.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"el objeto {sha[:12]}… llegó corrupto "
                        "(hash distinto al del manifiesto)"
                    )
                os.replace(parcial, destino)
                plan.verificados.add(sha)
        finally:
            if propia:
                s.cerrar()

    # --- Aplicación ---
    def _materializar(self, plan):
        """Deja en el staging, verificado por hash, TODO objeto que haga falta y
        no se haya bajado: los que venían de otra ruta de la propia carpeta y los
        que venían de un donante.

        Esto pasa **antes** de tocar un solo archivo del destino, y no es solo
        prolijidad. Si un archivo local es a la vez fuente de un objeto y destino
        de otro, aplicar en un solo pase lo lee después de haberlo sobrescrito y
        escribe contenido equivocado sin que nada lo detecte. El caso concreto es
        dos archivos que intercambian contenido entre versiones (A pasa a tener lo
        de B y B lo de A): ambos hashes están en disco, no se baja nada, y el
        segundo sale corrupto. Copiando todo al staging primero, eso no puede
        pasar; y si algo falta, se corta acá con el build todavía intacto en vez
        de a medio actualizar.
        """
        self.staging.mkdir(parents=True, exist_ok=True)
        for entrada in plan.entradas:
            sha = entrada["sha256"]
            destino = self.staging / sha
            if sha in plan.verificados and destino.is_file():
                continue
            if destino.is_file():
                # No lo bajamos nosotros en esta corrida: verificarlo.
                if sha256_archivo(destino) == sha:
                    plan.verificados.add(sha)
                    continue
                destino.unlink(missing_ok=True)

            fuente = plan.locales.get(sha)
            if not fuente or not Path(fuente).is_file():
                raise RuntimeError(
                    f"falta el contenido de {entrada['ruta']} ({sha[:12]}…), "
                    "no se aplica nada"
                )

            parcial = destino.with_suffix(".parcial")
            shutil.copy2(fuente, parcial)
            if sha256_archivo(parcial) != sha:
                parcial.unlink(missing_ok=True)
                raise RuntimeError(
                    f"{fuente} cambió mientras se preparaba la actualización, "
                    "no se aplica nada"
                )
            os.replace(parcial, destino)
            plan.verificados.add(sha)

    def aplicar(self, plan):
        """Pone cada archivo en su lugar definitivo.

        Devuelve la lista [(origen, destino)] de lo que no se pudo mover en
        caliente, para que el `.cmd` de respaldo lo termine cuando el proceso
        cierre. En la práctica debería salir vacía.
        """
        self._materializar(plan)

        pendientes = []

        # Un mismo objeto puede ir a más de una ruta: a las primeras se las copia
        # y a la última se la mueve, así el staging queda vacío sin copiar de más.
        restantes = {}
        for entrada in plan.entradas:
            restantes[entrada["sha256"]] = restantes.get(entrada["sha256"], 0) + 1

        for entrada in plan.entradas:
            sha = entrada["sha256"]
            destino = self.carpeta / entrada["ruta"]
            origen = self.staging / sha

            restantes[sha] -= 1
            ultima_vez = restantes[sha] <= 0

            try:
                destino.parent.mkdir(parents=True, exist_ok=True)
                _colocar(origen, destino, mover=ultima_vez)
            except OSError:
                pendientes.append((str(origen), str(destino)))

        # Los borrados también se apartan en vez de eliminarse: si el archivo
        # está en uso, el unlink falla pero el rename funciona.
        for rel in plan.borrar:
            objetivo = self.carpeta / rel
            try:
                if objetivo.is_file():
                    viejo = _mover_a_viejo(objetivo)
                    try:
                        viejo.unlink()
                    except OSError:
                        pass  # Se limpia en el próximo arranque.
            except OSError:
                pass

        # Si el staging quedó vacío, sacarlo. `rmdir` falla si todavía tiene algo
        # (quedaron pendientes para el .cmd de respaldo), que es justo lo que
        # queremos. Importa porque no todas las apps corren `limpiar_rastros()` al
        # arrancar: las que todavía no tienen el núcleo integrado se quedarían con
        # una carpeta .actualizacion vacía para siempre.
        try:
            self.staging.rmdir()
        except OSError:
            pass

        return pendientes

    def registrar_instalado(self, manifiesto):
        """Guarda el manifiesto aplicado.

        Sirve para tres cosas: el diff de borrados, saber la versión instalada sin
        ejecutar la app, y hacer de índice para que otra app pueda sacar objetos
        de esta carpeta sin hashearla entera.

        **No es la fuente de verdad de la versión** (esa es la `APP_VERSION`
        compilada en el `.exe`): si este archivo se pierde, no se rompe nada, solo
        se replanifica desde cero la próxima vez.
        """
        liviano = {
            "app": manifiesto.get("app"),
            "version": manifiesto.get("version"),
            "fecha": manifiesto.get("fecha"),
            "archivos": [
                {"ruta": e.get("ruta"), "sha256": e.get("sha256"), "tam": e.get("tam")}
                for e in manifiesto.get("archivos", [])
            ],
        }
        try:
            self.instalado.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.instalado.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(liviano, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.instalado)
        except OSError:
            pass

    # --- Limpieza ---
    def limpiar_rastros(self):
        """Borra los `.viejo-*` y el staging de una actualización anterior.

        Se llama al arrancar, cuando el proceso que tenía esos archivos abiertos
        ya murió. Todo error se ignora: son archivos de descarte.
        """
        try:
            for ruta in self.carpeta.rglob("*" + SUFIJO_VIEJO + "*"):
                try:
                    if ruta.is_file():
                        ruta.unlink()
                except OSError:
                    pass
        except OSError:
            pass
        shutil.rmtree(self.staging, ignore_errors=True)

    def lanzar_ayudante(self, pendientes, relanzar=None):
        """Deja un `.cmd` que termina el reemplazo cuando este proceso cierre.

        Respaldo para lo que no se pudo renombrar en caliente (un antivirus, un
        Explorer con el archivo abierto). Espera a que muera el PID, mueve lo que
        quedó, relanza `relanzar` si se le pasa y se borra solo.
        """
        pendientes = [(o, d) for o, d in pendientes if o]
        if not pendientes:
            return False

        lineas = [
            "@echo off",
            f"set PID={os.getpid()}",
            ":esperar",
            'tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul',
            "if not errorlevel 1 (",
            "  ping -n 2 127.0.0.1 >nul",
            "  goto esperar",
            ")",
        ]
        for origen, destino in pendientes:
            lineas.append(f'move /Y "{origen}" "{destino}" >nul 2>&1')
        if relanzar:
            lineas.append(f'start "" "{relanzar}"')
        lineas.append('del "%~f0"')

        try:
            self.staging.mkdir(parents=True, exist_ok=True)
            script = self.staging / "terminar_update.cmd"
            script.write_text("\r\n".join(lineas) + "\r\n", encoding="ascii")
            subprocess.Popen(
                ["cmd", "/c", "start", "/min", "", str(script)],
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except OSError:
            return False


def _indice_de(carpeta):
    """sha256 -> [rutas] de una carpeta de instalación, leído de su
    `instalado.json`. Vacío si no lo tiene.

    Prueba las ubicaciones conocidas de la carpeta de config. Windows no
    distingue mayúsculas, así que `RECURSOS/CONFIG` encuentra también un
    `Recursos/Config`.
    """
    for intocable in INTOCABLES_POR_DEFECTO:
        ruta = Path(carpeta) / intocable / NOMBRE_INSTALADO
        if ruta.is_file():
            break
    else:
        return {}
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            man = json.load(f)
    except Exception:
        return {}
    indice = {}
    for e in man.get("archivos", []):
        sha = str(e.get("sha256", "")).lower()
        rel = str(e.get("ruta", "")).replace("\\", "/")
        if _es_sha(sha) and rel:
            indice.setdefault(sha, []).append(rel)
    return indice


def _mover_a_viejo(destino):
    """Aparta un archivo en uso renombrándolo. Windows no deja borrar un `.exe` o
    una DLL cargada, pero sí renombrarla dentro del mismo volumen."""
    viejo = destino.with_name(destino.name + SUFIJO_VIEJO + str(os.getpid()))
    contador = 0
    while viejo.exists():
        contador += 1
        viejo = destino.with_name(
            f"{destino.name}{SUFIJO_VIEJO}{os.getpid()}-{contador}"
        )
    os.replace(destino, viejo)
    return viejo


def _colocar(origen, destino, mover):
    """Escribe `origen` sobre `destino`, apartando el destino si está en uso."""
    try:
        if mover:
            os.replace(origen, destino)
        else:
            shutil.copy2(origen, destino)
        return
    except OSError:
        pass

    # Estaba en uso (el propio .exe, una DLL de PySide6): apartarlo y reintentar.
    if destino.exists():
        _mover_a_viejo(destino)
    if mover:
        os.replace(origen, destino)
    else:
        shutil.copy2(origen, destino)


# ==========================================
# ENTORNO
# ==========================================
def raiz_instalaciones():
    """Dónde MINIhub instala las apps.

    `%LOCALAPPDATA%` cumple las dos condiciones que hacen fallar una
    actualización: es escribible sin permisos de administrador (en
    `Program Files` el update falla) y está fuera de OneDrive (la sincronización
    pelea con el renombrado y puede dejar el build hecho de mitades de dos
    versiones).
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "UtilidadesMINI"


def carpeta_de(app):
    """Dónde MINIhub instalaría esta app si no supiera nada más."""
    return raiz_instalaciones() / app


# ==========================================
# REGISTRO DE UBICACIONES
# ==========================================
# Dónde está instalada cada app EN ESTA PC. Lo escribe cada app al arrancar (con
# su APP_VERSION compilada, que es la fuente de verdad) y lo escribe MINIhub
# cuando instala. Sirve para que MINIhub encuentre una copia que no está en
# `raiz_instalaciones()`: las que ya estaban repartidas a mano antes de que
# existiera MINIhub viven en el escritorio, en D:, donde sea. Sin esto, MINIhub
# las daría por no instaladas y pondría una segunda copia al lado.
#
# Va en un archivo local y NO en el FTP, a propósito. Dos razones:
#
# - Todo el sistema está parado sobre que nada sin firmar dispara una escritura.
#   Las credenciales del FTP viajan dentro de cada .exe; si MINIhub leyera de ahí
#   una *ruta* y después instalara en ella, cualquiera que extraiga esas
#   credenciales podría hacer que MINIhub escriba en la carpeta que él elija. La
#   firma no lo salva: la clave privada no puede estar en las PC de los clientes.
# - "Dónde está esta app en ESTA PC" lo contesta esta PC. En el FTP serían un
#   registro por (app x maquina x usuario), que quedan viejos solos, más una
#   escritura de red en cada arranque de cada app.
NOMBRE_REGISTRO = "instalaciones.json"


def ruta_registro():
    return raiz_instalaciones() / NOMBRE_REGISTRO


def _leer_registro():
    try:
        with open(ruta_registro(), "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except Exception:
        return {}


def registrar_ubicacion(app, carpeta, version=None, exe=None):
    """Anota dónde está esta app y en qué versión.

    La llama cada app al arrancar y MINIhub cuando termina de instalar. Nunca
    lanza: correr en el arranque de la app y hacerla fallar por no poder escribir
    un archivo de conveniencia sería mucho peor que no registrarse.

    Dos apps arrancando a la vez pueden pisarse el archivo y perderse un registro.
    No se usa un lock porque no vale la pena: la que perdió se vuelve a anotar en
    su próximo arranque, y mientras tanto MINIhub la busca donde siempre.
    """
    try:
        registro = _leer_registro()
        entrada = dict(registro.get(app) or {})
        entrada["carpeta"] = str(Path(carpeta))
        entrada["visto"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        if version:
            entrada["version"] = str(version)
        if exe:
            entrada["exe"] = str(exe)
        registro[app] = entrada

        destino = ruta_registro()
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_name(f"{destino.name}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=1)
        os.replace(tmp, destino)
        return True
    except Exception:
        return False


def olvidar_ubicacion(app):
    """Saca una app del registro (al desinstalarla)."""
    try:
        registro = _leer_registro()
        if app not in registro:
            return False
        del registro[app]
        destino = ruta_registro()
        tmp = destino.with_name(f"{destino.name}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=1)
        os.replace(tmp, destino)
        return True
    except Exception:
        return False


def ubicacion_registrada(app, exe=None):
    """Dónde dice el registro que está esta app, o None.

    Devuelve None si la carpeta ya no existe, si no tiene el `.exe` esperado o si
    apunta a un lugar donde no corresponde instalar nada. El registro es local (si
    alguien puede escribirlo, ya tiene la sesión del usuario), pero validar es
    barato y evita que una entrada vieja haga que MINIhub escriba en cualquier
    lado.
    """
    entrada = _leer_registro().get(app)
    if not isinstance(entrada, dict):
        return None
    cruda = entrada.get("carpeta")
    if not cruda:
        return None
    try:
        carpeta = Path(cruda).resolve()
    except OSError:
        return None

    if not carpeta.is_dir() or carpeta.parent == carpeta:
        return None            # no existe, o es la raíz de un disco
    if _es_carpeta_del_sistema(carpeta):
        return None
    if exe and not (carpeta / exe).is_file():
        return None            # se movió o se borró: el registro quedó viejo

    return {
        "carpeta": carpeta,
        "version": entrada.get("version") or None,
        "visto": entrada.get("visto") or "",
    }


def _es_carpeta_del_sistema(carpeta):
    """Lugares donde no se instala una app, pase lo que pase."""
    texto = str(carpeta).lower().replace("/", "\\").rstrip("\\")
    for raiz in (os.environ.get("SystemRoot"), os.environ.get("ProgramFiles"),
                 os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramData")):
        if not raiz:
            continue
        raiz = str(raiz).lower().replace("/", "\\").rstrip("\\")
        if texto == raiz or texto.startswith(raiz + "\\"):
            return True
    return False


def proceso_vivo(nombre_exe):
    """True si hay un proceso con ese nombre de ejecutable corriendo.

    MINIhub no actualiza una app que está abierta: serían dos procesos
    escribiendo la misma carpeta. Los nombres del staging y de los `.viejo-<pid>`
    llevan PID así que no se pisarían, pero es mucho más simple pedirle al
    usuario que la cierre.
    """
    if not nombre_exe or os.name != "nt":
        return False
    try:
        salida = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {nombre_exe}", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return nombre_exe.lower() in salida.lower()


def lanzar(exe, cwd=None):
    """Ejecuta un .exe desregistrado de este proceso."""
    exe = Path(exe)
    if not exe.is_file():
        raise FileNotFoundError(f"no existe {exe}")
    subprocess.Popen([str(exe)], cwd=str(cwd or exe.parent), close_fds=True)


# Variables que fuerzan la autoactualización corriendo desde el .py.
# `AGENDA_UPDATE_DEV` es el nombre histórico de AgendaRust y se sigue aceptando.
VARS_DEV = ("MINI_UPDATE_DEV", "AGENDA_UPDATE_DEV")


def modo_activo():
    """La autoactualización solo corre en el `.exe` compilado. En desarrollo se
    saltea (no tendría sentido pisar el código fuente con el build), salvo que se
    pida a propósito con `MINI_UPDATE_DEV=1` para probarla."""
    if getattr(sys, "frozen", False):
        return True
    return any(os.environ.get(v) == "1" for v in VARS_DEV)


def base_dir_de(modulo_main):
    """Carpeta raíz de la app, funcione como script o como `.exe`."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(modulo_main).resolve().parent
