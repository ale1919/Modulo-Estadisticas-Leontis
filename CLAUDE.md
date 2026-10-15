# CLAUDE.md — Módulo de Estadísticas

<!-- COMUN:INICIO -->
## Antes de nada: la documentación común

> **Lo primero de esta sesión: abrí `../../DOCUMENTACION/ARRANQUE-DE-SESION.md`
> y seguilo.** Antes de leer código y antes de planificar nada. Dice cómo se
> arranca; **no está copiado acá a propósito** —vive en un solo lugar para que no
> haya diecisiete versiones distintas—, pero abrirlo no es opcional.

El resto de las reglas que valen para **todos** los proyectos están en
`../../DOCUMENTACION`. Empezá por su **`LEEME.md`**, que dice qué leer
según lo que vayas a hacer.

| Documento | Cuándo |
|---|---|
| `DOCUMENTACION/PERMISOS.md` | Qué se hace sin preguntar y qué requiere aprobación |
| `DOCUMENTACION/HERRAMIENTAS.md` | **Antes de abrir código**: los índices contestan sin leer archivos |
| `DOCUMENTACION/PRUEBAS.md` | Antes de escribir o tocar una prueba |
| `DOCUMENTACION/ARRANQUE-DE-SESION.md` | Al empezar. No es opcional |
| `DOCUMENTACION/CIERRE-DE-SESION.md` | Al terminar. No es opcional |
| `DOCUMENTACION/REGLA-DE-ORO.md` | Si el código puede llegar a un cliente |

Lo mínimo que hay que saber sin abrirlas:

- **Leer nunca se pregunta.** Cualquier archivo, de cualquier tipo. Y el permiso
  se pide **una vez por tarea, no una vez por paso**.
- **Preguntale al índice antes de abrir código**:
  `python HERRAMIENTAS/preguntar.py donde <nombre>` / `usa <nombre>` / `doc "texto"`.
- **No audites leyendo: escribí las pruebas**, y que barran el dominio de cada
  dato (bien, vacío, mal formado, muy largo, muy corto) contra cada preferencia.
  Escribirlas al cerrar es obligatorio; **correrlas se le ofrece al usuario, no
  se lanza sola**. Las baterías solo crecen (hay un trinquete).
- **Antes de tocar código, el plan.** Clasificar el esfuerzo de cada tarea,
  elegir modelo y esfuerzo, decidir qué se delega a un subagente, y mostrarlo
  todo junto: **un solo permiso para la sesión entera**.
- **Se corre lo que el cambio toca, no todo**:
  `python HERRAMIENTAS/correr_todo.py --proyecto <el tuyo> --tocados --plan`
  dice qué pruebas cubren lo cambiado y qué quedó sin ninguna.
- **Una herramienta que sirva más allá de esta sesión va a `HERRAMIENTAS/`**,
  con su `README.md`. Antes de escribir una, buscala: puede que ya exista.

> Este bloque lo genera `HERRAMIENTAS/repartir_bloque.py`. Editá **abajo** de los
> marcadores: lo de acá adentro se pisa en la próxima corrida.
<!-- COMUN:FIN -->

<!-- MINIHUB:INICIO -->
## ⚠️ Antes de tocar esta app: leé `ACTUALIZACIONES.md`

Esta app forma parte del sistema de actualización automática de **MINIhub**
(`../MINIhub/`, o donde esté relativo a acá: `PROYECTOS 8-10/MINIhub`).

**[`ACTUALIZACIONES.md`](ACTUALIZACIONES.md)** de esta carpeta explica qué hay que
hacer para sumarla al sistema, qué hay que resolver **en esta app en particular**
antes de empezar, y en qué orden trabajar (auditoría → commit checkpoint →
integración → compilar y publicar → commit final). Leelo completo antes de empezar.

Puntos que importan aunque vengas a hacer otra cosa:

- Si en esta carpeta existen `Recursos/Modulos/nucleo.py`, `ftp_config.py` o
  `ui_updater.py`, **son copias y no se editan acá**. Se editan en
  `MINIhub/RECURSOS/MODULOS/` y se reparten con `python sincronizar_nucleo.py
  --app ModuloEstadisticasLeontis --aplicar`.
- El `.exe` de esta app tiene que llamarse `ModuloEstadisticasLeontis.exe` y el build tiene que ser
  **onedir**, nunca onefile.
- `Recursos/Config` es la carpeta que el updater no toca nunca. Todo lo que sea de cada
  instalación va ahí; nada que tenga que actualizarse puede estar ahí.
- El `CHANGELOG.md` de esta carpeta es lo que MINIhub muestra en el botón
  **Changelog** de la tarjeta. **Al publicar una versión nueva hay que agregarle
  su sección**, arriba de todo: el publicador se lo lleva entero dentro del
  manifiesto firmado.
- Publicar se hace desde MINIhub (`python publicar_app.py --app ModuloEstadisticasLeontis`), no desde
  este repo.

Contexto completo del sistema: `MINIhub/CLAUDE.md`. El razonamiento detrás de cada
decisión: `UTILIDADES/AGENDA RUST/ACTUALIZACIONES.md`.
<!-- MINIHUB:FIN -->

## Qué es

Estadísticas de Leontis para el usuario final: informes de venta, stock, clientes y
cuenta corriente, con gráficos y exportación a PDF y Excel.

- **Entrada:** `main.py`
- **Interfaz:** PySide6
- **Repo:** https://github.com/ale1919/Modulo-Estadisticas-Leontis

## Cómo correr

```bash
python main.py
```

Para ver el log en consola además del archivo: `ESTADISTICAS_DEBUG=1 python main.py`.
Para probar el camino del updater en desarrollo: `MINI_UPDATE_DEV=1 python main.py`.

Compilar (onedir, obligatorio):

```bash
python -m PyInstaller ModuloEstadisticasLeontis.spec --noconfirm
```

## Arquitectura

| Archivo | Rol |
|---|---|
| `main.py` | Login contra la API, ventana principal, exportadores a PDF y Excel |
| `Recursos/Modulos/rutas.py` | Rutas (`BASE_DIR` vs `RECURSOS_BASE`) y logging |
| `Recursos/Modulos/db_connection.py` | `DBManager` (conexión) y `AppLogic` (qué informe pide qué) |
| `Recursos/Modulos/statistics_generator.py` | **Todo el SQL.** Una consulta por informe |
| `Recursos/Modulos/ui_factory.py` | Construye las tarjetas de informe y las pestañas |
| `Recursos/Modulos/dashboard_manager.py` | Panel de admin: KPIs y APIs de dólar/IPC, en un `QThread` |
| `Recursos/Modulos/matplotlib_widget.py` | Los tres tipos de gráfico (barras, línea, multilínea) |
| `Recursos/Modulos/ui_styles.py` | Hoja de estilos |
| `Recursos/Modulos/{nucleo,ftp_config,ui_updater,requisitos,ui_requisitos}.py` | Núcleo de MINIhub. **No se editan acá** |

### Lo que no es obvio

- **`FILTRO_VENTA` y `SIGNO_VENTA` (en `statistics_generator.py`) son obligatorios
  en toda consulta que mida ventas.** `comprobanteemitido` mezcla facturas con
  notas de crédito y recibos de cobranza: sin eso, una NC suma en vez de restar y
  cada recibo se cuenta como venta nueva. Fue el bug más caro de la auditoría.
  Los IDs de tipo de comprobante están arriba de ese archivo.
- **`BASE_DIR` ≠ `RECURSOS_BASE`.** El primero es la carpeta de la app (la que
  actualiza el updater); el segundo es de dónde salen los archivos empaquetados,
  que en onedir es `_internal/` (`sys._MEIPASS`). Confundirlos hace que la app
  compilada no encuentre sus iconos ni sus JSON.
- **`Recursos/Config` es la carpeta intocable**: ahí van el log y lo de cada
  instalación. **`Recursos/Datos`** tiene `dolares.json` e `inflacion.json`, que
  son datos de la app y por eso están afuera de `Config`: si estuvieran adentro,
  un endpoint nuevo no le llegaría nunca a nadie.
- **El `DashboardWorker` se dispara por señal** (`request_dashboard_load`), no
  llamando al método. Un `QTimer.singleShot` o una llamada directa lo ejecutarían
  en el hilo de la GUI aunque el objeto esté en otro hilo.
- **Nada de `QMessageBox` en `db_connection._execute_query`**: lo llama el worker
  desde un hilo secundario y crear widgets fuera del hilo GUI cierra la app sin
  aviso. El error queda en `last_error` y en el log.
- Los informes que son solo tabla están en `MainWindow.REPORTES_SOLO_TABLA`.

## Estado

Funcional y publicado en MINIhub (`ModuloEstadisticasLeontis`).

Pendientes conocidos, todos anotados en [`AUDITORIA.md`](AUDITORIA.md):

- **El login va por `http://` porque el servidor no habla TLS en el puerto 65081**
  (un handshake devuelve `WRONG_VERSION_NUMBER`). Es lo mismo que hacen
  `Modulo Servicios` y el importador desde Eslaboon. Sigue siendo un problema
  real: por ahí viajan usuario, contraseña y la cadena de conexión a la base del
  cliente, y Base64 no cifra nada. Cuando el servidor tenga certificado se prueba
  con `ESTADISTICAS_API_URL=https://...` y recién ahí se cambia el default.
- Los informes corren en el hilo de la GUI: en bases grandes la ventana se
  congela. Está la infraestructura (`DashboardWorker`) para generalizarlo.
- Faltan los índices SQL de la §4 de la auditoría; hay que coordinarlos con quien
  administre las bases de los clientes.
- Las estadísticas de la §3 de la auditoría que todavía no se implementaron
  (ventas ajustadas por inflación, flujo de caja, IVA, ventas por hora, etc.).
- No hay tests automatizados de la lógica de negocio.
- **El build arrastra `tables` (PyTables/HDF5, ~13 MB) y sus DLL**, que son una
  dependencia opcional de pandas que esta app no usa. Se puede sumar a `excludes`
  en el `.spec` y bajar el peso; no se hizo en 0.1.0 para no publicar dos
  versiones seguidas por un cambio de empaquetado. Es lo mismo que ya le pasó a
  `ModuloEslaboonComit` (ver `MINIhub/CLAUDE.md`).
