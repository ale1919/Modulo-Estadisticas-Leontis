# ACTUALIZACIONES.md — Módulo de Estadísticas

Cómo sumar esta app al sistema de actualización automática de **MINIhub**.

> Este archivo lo genera `MINIhub/generar_guias.py`. Si encontrás algo mal que
> aplica a **todas** las apps, arreglalo ahí y volvé a generar. Si es solo de esta
> app, editá acá y dejalo dicho en el commit (una regeneración lo pisaría).

---

## Para Claude: qué se espera de esta sesión

Trabajá en este orden y **no lo saltees**:

1. **Auditoría completa del código.** Leelo entero, buscá bugs reales y arreglalos.
   Nada de esto tiene que ver todavía con las actualizaciones.
2. **Commit checkpoint.** Con la auditoría cerrada y la app funcionando, commiteá.
   Ese commit es el punto al que volver si la integración sale mal.
3. **Recién ahí, leé este documento completo** y hacé la integración (secciones de
   abajo).
4. **Compilar y publicar** al FTP.
5. **Commit y push final.**

Los pasos 1 y 2 primero **a propósito**: si mezclás arreglos de bugs con la
integración del updater en un solo commit, cuando algo falle no vas a saber cuál de
las dos cosas lo rompió. Y el paso 4 antes del 5 porque publicar reescribe
`version.py`, así que ese cambio tiene que entrar en el commit final.

### Antes de tocar código, leé

| Archivo | Para qué |
|---|---|
| `MINIhub/CLAUDE.md` | **Obligatorio.** Cómo está armado el sistema y qué no hay que "simplificar" |
| `UTILIDADES/AGENDA RUST/ACTUALIZACIONES.md` | El *por qué* de cada decisión. Secciones 2, 4 y 12 |
| `UTILIDADES/AGENDA RUST/main.py` y `RECURSOS/MODULOS/version.py` | El ejemplo ya hecho y funcionando |

---

## Qué es este sistema, en corto

Cada app publicada tiene en el FTP un `version.json` **firmado con Ed25519** con la
lista de sus archivos (ruta, tamaño, SHA-256). Los archivos viven en un almacén
**compartido entre todas las apps**, guardados por contenido:
`objetos/<xx>/<sha256>`.

Al arrancar, la app compara su `APP_VERSION` compilada contra el manifiesto y baja
**solo los hashes que no tiene**. En un build onedir de PyInstaller el 98% del peso
son los ~130 MB de `_internal/`, que casi nunca cambian: un cambio de código son
~3 MB. Y como el almacén es compartido, si otra app PySide6 ya está instalada, esos
130 MB se copian del disco y no se bajan.

MINIhub hace lo que una app no puede hacer sola: descubrirlas, instalarlas de cero,
mostrar el estado de todas juntas y crear los accesos directos. **Las dos cosas
tienen que existir**: la gente abre el `.exe` desde un acceso directo sin pasar por
MINIhub, así que una app que no se autoactualiza se queda con código viejo.

Las apps se instalan en `C:\MainSolution\<App>\`, al lado de los sistemas de
gestión: una ruta igual en todas las PC, escribible sin ser administrador y fuera
de OneDrive (la sincronización pelea con el renombrado de archivos y puede dejar el
build hecho de mitades de dos versiones).

Además, al arrancar cada app se **anota a sí misma** en
`%LOCALAPPDATA%\UtilidadesMINI\instalaciones.json` —eso sigue siendo por usuario,
a propósito—: dónde está y qué `APP_VERSION` tiene. Eso es lo que hace que MINIhub
encuentre una copia que él no instaló (las que se repartieron a mano viven en el
escritorio, en `D:`, donde sea) y la actualice **en su lugar** en vez de poner una
segunda al lado. Lo hace
`chequear_al_inicio()`, así que sale gratis con solo integrarlo — **salvo que
tengas que forkear `ui_updater.py`**, en cuyo caso el fork también tiene que llamar
a `nucleo.registrar_ubicacion()`.

La firma **no es opcional**. Las credenciales del FTP están hardcodeadas y viajan
dentro de cada `.exe`, y el FTP es texto plano. Sin firma, cualquiera que las
extraiga podría reemplazar un objeto y su código se ejecutaría solo en la PC de
todos: el auto-update convierte una fuga de credenciales en ejecución remota de
código en toda la oficina.

---

## Los datos de esta app

| | |
|---|---|
| Nombre en el catálogo | `ModuloEstadisticasLeontis` |
| Categoría | LEONTIS |
| Carpeta | `C:\Users\alema\OneDrive\Escritorio\PROYECTOS 8-10\LEONTIS\ESTADISTICAS LEONTIS - USUARIO FINAL` |
| Entrada | `main.py` |
| Paquete del núcleo | `Recursos.Modulos` |
| Binding de Qt | PySide6 |
| Ejecutable esperado | `ModuloEstadisticasLeontis.exe` |
| Carpeta intocable | `Recursos/Config` |
| Repo | `https://github.com/ale1919/Modulo-Estadisticas-Leontis` |
| Se instala en | `C:\MainSolution\ModuloEstadisticasLeontis\` |

El **ejecutable esperado** es lo que dice el catálogo y no es negociable sin tocarlo:
`publicar_app.py` verifica que ese archivo exista de verdad en el build antes de
publicar. Si no coincide, MINIhub instalaría la app y después no podría abrirla, y el
error aparecería recién en la PC del técnico.

La **carpeta intocable** es lo único que el updater no toca nunca: no se publica, no
se reemplaza y no se borra. Ahí va la configuración de cada instalación. Si un
archivo de usuario queda afuera de esa carpeta, una actualización se lo pisa.

### Estado de partida

- **La app:** Funcional. Usa matplotlib para los gráficos y exporta a PDF.
- **Git:** **No es un repo todavía.** El repo remoto existe y está vacío: `https://github.com/ale1919/Modulo-Estadisticas-Leontis`.
- **Build:** **No tiene `.spec` ni `.bat`.** Hay que crear la configuración de build desde cero.

---

## ⚠️ Lo que hay que resolver en esta app antes de integrar

1. **Esta app usa `Recursos/Modulos` y `Recursos/Config`, con otra capitalización que el resto.** El núcleo va en `Recursos/Modulos/` y se importa como `Recursos.Modulos.nucleo`. **No la "corrijas" a mayúsculas** sin revisar todos los imports: en Windows funciona igual, pero `sincronizar_nucleo.py` busca la carpeta con el nombre que tenga y cambiarla a medias rompe los imports.

   Su entrada en `catalogo_base.json` ya dice `"intocables": ["Recursos/Config"]`, con la capitalización real. (Desde el arreglo de `ruta_segura()` la comparación no distingue mayúsculas, así que igual estaría protegida — pero mejor que el catálogo diga la verdad.)

2. **Hay que inicializar el repo** y **crear el `.spec`** (onedir).

3. **matplotlib infla el build.** Es una dependencia grande y con muchos datos (fuentes, backends). No es un problema —el almacén de objetos es compartido, así que se sube una vez— pero la **primera** publicación de esta app va a subir bastante más que las demás, porque matplotlib no lo trae ninguna otra. Contá con eso y no la canceles a mitad.

### Además, para tener en cuenta

`Recursos/Config/` tiene `dolares.json` e `inflacion.json`. Ojo: **esos dos parecen datos de la app, no del usuario.** Si los actualizás vos y querés que a todos les lleguen los valores nuevos, **no pueden estar en la carpeta intocable** — el updater nunca los va a reemplazar. Moverlos a `Recursos/Datos/` y dejar en `Config/` solo lo que es de cada instalación. Esto hay que decidirlo antes de la primera publicación, porque después cambiar de lugar un archivo que ya está en la PC de todos es más trabajo.

---

## Los pasos

### 1. Auditoría y commit checkpoint

Auditá el código y arreglá los bugs que encuentres. **Este repo todavía no está inicializado**: antes del checkpoint hay que hacer `git init -b main`, agregar un `.gitignore` (copiá el de MINIhub como base: tiene las entradas del updater), configurar el remote y hacer el primer commit.

### 2. La carpeta del núcleo

El núcleo va en `Recursos/Modulos/`. Esa carpeta ya existe, no hay que crear nada.

Tienen que existir los `__init__.py` de todos los niveles (`RECURSOS/__init__.py` y
`RECURSOS/MODULOS/__init__.py`, con la capitalización que use esta app). Sin eso los
imports relativos del núcleo no funcionan.

### 3. `version.py`

Creá `Recursos/Modulos/version.py` con exactamente esto:

```python
"""Versión de la app. Fuente única: la lee el núcleo para comparar contra el
manifiesto del FTP, y la reescribe el publicador de MINIhub al publicar.
"""

APP_NAME = "ModuloEstadisticasLeontis"
APP_VERSION = "0.1.0"
```

`APP_NAME` tiene que ser **exactamente** `ModuloEstadisticasLeontis`: con eso se busca el manifiesto
en el FTP y el núcleo rechaza un manifiesto que diga ser de otra app.

No le agregues nada más: el publicador edita ese archivo con una expresión regular
sobre la línea de `APP_VERSION`.

### 4. Traer el núcleo

Desde `MINIhub/`:

```bash
python sincronizar_nucleo.py --app ModuloEstadisticasLeontis --aplicar
```

Copia `nucleo.py`, `ftp_config.py` y `ui_updater.py`. **Esos tres archivos no se
editan acá.** Son el mismo archivo en todas las apps; se editan en MINIhub y se
reparten con ese comando, que sin `--aplicar` solo compara y avisa cuál copia se
quedó atrás. Si los tocás en esta carpeta, la próxima sincronización te los pisa.

### 5. Enganchar el chequeo en `main.py`

Al principio del archivo, la raíz de la app tiene que salir bien tanto corriendo
desde el `.py` como desde el `.exe`:

```python
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent
```

`Path(__file__).parent` a secas **no sirve**: compilado apunta a otro lugar y el
updater terminaría comparando la carpeta equivocada.

Y en la función que arranca la app, después de crear el `QApplication` y **antes** de
construir la ventana principal:

```python
from Recursos.Modulos.ui_updater import chequear_al_inicio

...
app = QApplication(sys.argv)
# (estilos, icono, lo que ya tenga)

if not chequear_al_inicio(BASE_DIR):
    return          # se actualizó y se relanzó, o el usuario canceló

ventana = MainWindow()
ventana.show()
sys.exit(app.exec())
```

Devuelve `False` cuando la app **no** tiene que seguir arrancando. Respetá eso: si
seguís de largo, quedan dos procesos.

### 6. Confirmar la carpeta intocable

La entrada de `ModuloEstadisticasLeontis` en `MINIhub/RECURSOS/DATOS/catalogo_base.json` dice
`"intocables": ["Recursos/Config"]`. Verificá que **todo** lo que sea de cada
instalación viva ahí adentro: credenciales, preferencias, caches, logs, lo que la app
escriba en tiempo de ejecución.

Al revés también importa: si un archivo **sí** tiene que llegarles actualizado a
todos (datos de la app, plantillas, un icono), **no puede estar** en esa carpeta,
porque el updater nunca lo va a reemplazar.

### 7. El build: onedir y con el nombre correcto

El `.exe` tiene que ser `ModuloEstadisticasLeontis.exe` y el build **onedir**, no onefile. Onefile rompe el
diseño entero: el updater existe justamente porque el peso está en archivos que no
cambian, y en onefile todo es un solo archivo. Además el arranque diario pasa de ~1 s
a 5-10 s porque PySide6 se descomprime a `%TEMP%` cada vez.

Usá `MINIhub/MINIhub.spec` como referencia; tiene el comentario que explica esto.

Que el `dist/` **no** incluya: la carpeta intocable, `venv*/`, `build/`, `__pycache__`,
caches ni archivos de prueba. Lo que entra al `dist/` se publica.

### 8. Registrar cómo se compila

En `MINIhub/proyectos.json`, la entrada de `ModuloEstadisticasLeontis` tiene que tener el comando de
build para que `publicar_app.py --compilar` funcione:

```json
"ModuloEstadisticasLeontis": {
  "carpeta": "C:\\Users\\alema\\OneDrive\\Escritorio\\PROYECTOS 8-10\\LEONTIS\\ESTADISTICAS LEONTIS - USUARIO FINAL",
  "dist": "dist/ModuloEstadisticasLeontis",
  "compilar": ["python", "-m", "PyInstaller", "ModuloEstadisticasLeontis.spec", "--noconfirm"]
}
```

Si esta app compila con un `.bat`, poné el `.bat`:
`"compilar": ["cmd", "/c", "compila.bat"]`.

### 9. `CHANGELOG.md`

Creá un `CHANGELOG.md` en la raíz de esta app (`C:\Users\alema\OneDrive\Escritorio\PROYECTOS 8-10\LEONTIS\ESTADISTICAS LEONTIS - USUARIO FINAL`). MINIhub lo muestra en
el botón **Changelog** de la tarjeta de Módulo de Estadísticas: es lo que el técnico lee para
saber qué cambió antes de actualizar.

Lo lee `publicar_app.py` de la carpeta del proyecto y lo mete **dentro del
manifiesto firmado**, así que no hay que agregarlo a los `datas` del `.spec` ni
publicarlo aparte: no es un archivo del build, es documentación del repo.

Arrancá con esto:

```markdown
# Changelog — Módulo de Estadísticas

Qué cambió en cada versión. Lo lee el técnico desde MINIhub.

## 0.1.0 — AAAA-MM-DD

Primera versión publicada en el sistema de actualización de MINIhub.
```

Dos cosas, las dos importan:

- **Escribí para el que usa el programa, no para el que lo programó.** "Ya no se
  cuelga al importar un Excel con celdas combinadas" sirve; "refactor de
  `importador.py`" no le dice nada a nadie.
- **Una sección por versión publicada, la más nueva arriba.** Va el archivo
  entero en cada publicación, así que se ve el historial completo, no solo lo
  último.

Si no lo creás, la app se publica igual: MINIhub muestra las notas de la versión
(el `--notas` de la publicación) y avisa que esta app todavía no tiene changelog.

---

## Verificación (antes de publicar)

Desde la carpeta de esta app:

```bash
python -c "from Recursos.Modulos import nucleo; from Recursos.Modulos.version import APP_NAME, APP_VERSION; \
import Recursos.Modulos.ftp_config as f; print(APP_NAME, APP_VERSION); \
print(f.ruta_manifiesto(APP_NAME)); print(nucleo.CLAVE_PUBLICA_HEX[:16])"
```

Tiene que imprimir `ModuloEstadisticasLeontis 0.1.0`, la ruta
`/UtilidadesMINI/apps/ModuloEstadisticasLeontis/version.json`, y la clave pública tiene que empezar
con `8ff92f7b34fe7d0a`. **Si la clave es otra, pará**: significa que el núcleo no
está sincronizado y ningún cliente aceptaría lo que publiques.

Que la app siga abriendo normalmente:

```bash
python main.py
```

En desarrollo el updater **no corre** (no tendría sentido pisar el código fuente con
el build). Para probar ese camino:

```bash
MINI_UPDATE_DEV=1 python main.py
```

Como esta app todavía no está publicada, el chequeo tiene que fallar por "no
encuentro el manifiesto", no mostrar nada y **dejar entrar igual**. Eso es lo
correcto: si el FTP no responde, se entra con la versión que haya.

Y desde `MINIhub/`, que el núcleo quede idéntico:

```bash
python sincronizar_nucleo.py --app ModuloEstadisticasLeontis
```

Tiene que decir `Al día`.

---

## Publicar

Desde `MINIhub/`, **primero simulando**:

```bash
python publicar_app.py --app ModuloEstadisticasLeontis --version 0.1.0 --notas "Primera publicacion." --simular
```

Revisá lo que imprime: cantidad de archivos, peso, que **no aparezca nada de la
carpeta intocable** en el manifiesto (`version.json.simulado.ModuloEstadisticasLeontis`) y que el
`CHANGELOG.md` se haya leído (lo dice con la cantidad de caracteres; si no lo
encuentra, avisa).

Si está bien:

```bash
python publicar_app.py --app ModuloEstadisticasLeontis --version 0.1.0 --notas "Primera publicacion." --compilar
```

Sube primero **todos** los objetos que falten y **al final** el `version.json`. Ese
orden importa: hasta que no está el manifiesto nuevo, los clientes siguen viendo la
versión anterior, así que ninguno puede encontrarse bajando objetos a medio subir.

Después, abrí MINIhub y comprobá que la tarjeta de **Módulo de Estadísticas** pasó de
"Sin publicar" a "Instalar", que instala, y que el botón "Abrir" la ejecuta.

**El primer build hay que repartirlo a mano una vez**: los `.exe` que ya están
instalados no saben buscar actualizaciones. A partir de ahí lo hace MINIhub.

---

## Commit y push final

Incluí el `version.py` con la versión que quedó publicada. Si en este repo se
versiona el `dist/` (mirá el `.gitignore`), incluilo también.

---

## Qué NO hacer

- **No edites `nucleo.py`, `ftp_config.py` ni `ui_updater.py` en esta carpeta.** Son
  copias. Se editan en MINIhub y se reparten con `sincronizar_nucleo.py`.
- **No generes una clave de firma nueva.** Hay una sola para todas las apps, y ya
  existe. Generar otra deja a todos los `.exe` ya repartidos sin poder actualizarse
  nunca más.
- **No pongas la app en `Program Files`** ni dentro de OneDrive. En `Program Files` la
  actualización falla sin permisos de administrador; en OneDrive la sincronización
  pelea con el renombrado de archivos y puede dejar el build hecho de mitades de dos
  versiones. El núcleo detecta las dos cosas y avisa, pero mejor no llegar ahí.
- **No publiques una versión que no sea mayor que la anterior**: los clientes la
  ignoran. El publicador lo verifica y aborta.
- **No pongas un archivo que tenga que actualizarse dentro de la carpeta intocable.**
  Nunca le va a llegar a nadie.
- **No te saltees `--simular`** en la primera publicación de esta app.
