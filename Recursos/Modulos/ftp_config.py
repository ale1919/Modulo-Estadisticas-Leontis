"""Credenciales y rutas del FTP donde viven las releases de todas las apps.

Este módulo está a propósito separado de la lógica de negocio: `nucleo.py` se
copia igual a todas las apps (ver `sincronizar_nucleo.py`) y no puede depender
del `app_logic.py` de ninguna en particular.

Estructura en el FTP
--------------------
    /UtilidadesMINI/
    ├── catalogo.json                qué apps existen (firmado)
    ├── objetos/<xx>/<sha256>        los archivos de TODAS las apps, por contenido
    ├── apps/<APP>/version.json      manifiesto de cada app (firmado)
    └── requisitos/
        ├── requisitos.json          qué necesita el sistema para correrlas (firmado)
        └── <sha256>                 los instaladores (VC++ redist y compañía)

El almacén de objetos es **compartido entre todas las apps** a propósito. Casi
todas son PySide6, así que los ~130 MB de `_internal/` son prácticamente los
mismos en todas: con un almacén por app habría ~1,3 GB en el FTP para ~150 MB de
contenido real. Compartido, la segunda app en adelante sube casi solo su `.exe`.
Del lado del cliente pasa lo mismo: instalar la segunda app copia los objetos de
la primera desde el disco en vez de bajarlos (ver `carpetas_donantes` en
`nucleo.armar_plan`).

Consecuencia a tener presente: **un objeto no se puede borrar por estar en una
versión vieja**, porque puede seguir referenciado por otra app. La recolección de
basura es global y mira todos los manifiestos a la vez
(`publicar_app.py --limpiar-objetos`).

Los manifiestos van en `apps/<APP>/` y no en `/UtilidadesMINI/<APP>/` porque ahí
ya hay carpetas con datos de otras cosas (`AGENDArust` tiene los `.enc` del
sistema de sincronización anterior a SQL Server) y el FTP es IIS, que **no
distingue mayúsculas**: `AgendaRust` y `AGENDArust` serían la misma carpeta.
"""

FTP_CONFIG = {
    "host": "mainsolution.ddns.net",
    "user": "administrador",
    "pass": "ms!574",
}

FTP_UTILIDADES_ROOT = "/UtilidadesMINI"

RUTA_OBJETOS = f"{FTP_UTILIDADES_ROOT}/objetos"
RUTA_CATALOGO = f"{FTP_UTILIDADES_ROOT}/catalogo.json"
RUTA_APPS = f"{FTP_UTILIDADES_ROOT}/apps"
RUTA_REQUISITOS = f"{FTP_UTILIDADES_ROOT}/requisitos"
RUTA_LISTA_REQUISITOS = f"{RUTA_REQUISITOS}/requisitos.json"


def ruta_manifiesto(app):
    """Ruta remota del manifiesto de una app."""
    return f"{RUTA_APPS}/{app}/version.json"


def ruta_objeto(sha256):
    """Ruta remota de un objeto, agrupado por los 2 primeros dígitos del hash
    para no tener miles de archivos en un solo directorio."""
    return f"{RUTA_OBJETOS}/{sha256[:2]}/{sha256}"


def ruta_instalador(sha256):
    """Ruta remota del instalador de un requisito del sistema.

    Va **fuera** de `objetos/` a propósito, aunque también se guarde por
    contenido: la recolección de basura de `objetos/` recorre los manifiestos de
    las apps para saber qué sigue en uso, y un instalador no figura en ninguno.
    Puesto ahí, el primer `--limpiar-objetos` se llevaría el VC++ redist.
    """
    return f"{RUTA_REQUISITOS}/{sha256}"
