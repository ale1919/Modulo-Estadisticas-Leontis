# -*- mode: python ; coding: utf-8 -*-
#
# Build **onedir**, no onefile. Es deliberado y no conviene cambiarlo:
#
# - El updater aprovecha que el 98% del peso (los ~130 MB de _internal) casi nunca
#   cambia, así que una versión nueva son ~3 MB. En onefile habría que bajar el
#   paquete entero cada vez.
# - Onefile descomprime PySide6 a %TEMP% en cada ejecución: el arranque pasa de
#   ~1 s a 5-10 s y aumenta la fricción con los antivirus.
#
# El nombre del .exe tampoco es negociable: `publicar_app.py` verifica que
# `ModuloEstadisticasLeontis.exe` exista de verdad en el build antes de publicar,
# porque es lo que declara el catálogo y lo que MINIhub va a ejecutar.

from PyInstaller.utils.hooks import collect_all

datas = [
    # Iconos y logos que la app carga en tiempo de ejecución.
    ('Recursos/Grafico', 'Recursos/Grafico'),
    # Endpoints de dólar e inflación. Van en Recursos/Datos, NO en
    # Recursos/Config: Config es la carpeta intocable del updater y lo que se
    # ponga ahí no se actualiza nunca en la PC del cliente.
    ('Recursos/Datos', 'Recursos/Datos'),
]
binaries = []
hiddenimports = [
    # SQLAlchemy resuelve el driver por nombre, así que PyInstaller no lo ve.
    'pymysql',
    'sqlalchemy.dialects.mysql',
]

# cryptography lo usa el núcleo para verificar la firma Ed25519 del manifiesto.
# Sin esto la app arranca pero rechaza toda actualización.
for paquete in ('cryptography', 'pymysql'):
    d, b, h = collect_all(paquete)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Otros bindings de Qt: si quedan, compiten con PySide6 en tiempo de carga.
        'PyQt5', 'PyQt6', 'PySide2',
        # Backends de matplotlib y GUIs que esta app no usa.
        'tkinter', 'matplotlib.backends.backend_tkagg',
        # Dependencias opcionales pesadas que arrastra pandas y que acá no se
        # tocan: son ~45 MB de _internal para nada.
        'IPython', 'jupyter', 'notebook', 'scipy', 'pytest', 'sphinx',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ModuloEstadisticasLeontis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['Recursos/Grafico/favicon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ModuloEstadisticasLeontis',
)
