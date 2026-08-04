"""Rutas de la app y logging, resueltos igual desde el `.py` y desde el `.exe`.

Antes había tres copias de `resource_path()` (en `main.py`, en `ui_factory.py` y en
`dashboard_manager.py`) con **bases distintas**: la de `main.py` usaba el directorio
del script y las otras dos subían dos niveles. Funcionaba de casualidad porque
`main.py` está en la raíz. Acá hay una sola.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Hay DOS raíces distintas y confundirlas rompe cosas silenciosamente:
#
#   BASE_DIR      la carpeta de la app. Es la que recibe el updater y la que se
#                 anota en instalaciones.json. En onedir es la del .exe.
#   RECURSOS_BASE de dónde salen los archivos empaquetados. PyInstaller onedir
#                 los deja en `_internal/` (= sys._MEIPASS), NO al lado del .exe.
#
# La configuración de cada instalación va bajo BASE_DIR y no bajo RECURSOS_BASE:
# `Recursos/Config` es la carpeta intocable declarada en el catálogo de MINIhub,
# y se define relativa a la carpeta de la app.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
    RECURSOS_BASE = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parents[2]
    RECURSOS_BASE = BASE_DIR

# Datos que se distribuyen con la app y tienen que poder actualizarse.
DATOS_DIR = RECURSOS_BASE / "Recursos" / "Datos"
GRAFICO_DIR = RECURSOS_BASE / "Recursos" / "Grafico"
# Lo propio de cada instalación. El updater no toca nunca esta carpeta.
CONFIG_DIR = BASE_DIR / "Recursos" / "Config"

LOG_FILE = CONFIG_DIR / "estadisticas.log"

_configurado = False


def recurso(*partes):
    """Ruta absoluta a un archivo empaquetado con la app (iconos, datos)."""
    return str(RECURSOS_BASE.joinpath(*partes))


def configurar_logging():
    """Log rotativo en la carpeta de configuración.

    Reemplaza los ~60 `print()` de debug que había repartidos por los módulos.
    Importa porque varios volcaban la consulta SQL entera y hasta la contraseña
    de la base de datos, y en un build `--windowed` no se ven en ningún lado.
    """
    global _configurado
    if _configurado:
        return logging.getLogger("estadisticas")

    logger = logging.getLogger("estadisticas")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formato = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        archivo = RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        archivo.setLevel(logging.DEBUG)
        archivo.setFormatter(formato)
        logger.addHandler(archivo)
    except Exception:
        # Si la carpeta no es escribible (app en una ruta protegida), se sigue
        # sin log en vez de impedir que la app abra.
        pass

    if os.environ.get("ESTADISTICAS_DEBUG"):
        consola = logging.StreamHandler()
        consola.setLevel(logging.DEBUG)
        consola.setFormatter(formato)
        logger.addHandler(consola)

    _configurado = True
    return logger


def log(nombre="estadisticas"):
    configurar_logging()
    return logging.getLogger("estadisticas").getChild(nombre)
