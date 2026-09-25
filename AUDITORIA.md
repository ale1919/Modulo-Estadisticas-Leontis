# Auditoría — Módulo de Estadísticas Leontis (usuario final)

Fecha: 2026-08-03
Alcance: `main.py`, `Recursos/Modulos/*`, contrastado contra
`PROYECTOS 8-10/SCHEMAS/LEONTIS schema.sql`.

Repo: https://github.com/ale1919/Modulo-Estadisticas-Leontis
(la carpeta local **no** es un repo git — `git status` falla; ver §2.9)

---

## Índice

1. [Errores por severidad](#1-errores-por-severidad)
2. [Mejoras técnicas](#2-mejoras-técnicas)
3. [Estadísticas nuevas propuestas](#3-estadísticas-nuevas-propuestas)
4. [Índices SQL recomendados](#4-índices-sql-recomendados)
5. [Plan de trabajo sugerido](#5-plan-de-trabajo-sugerido)
6. [Bitácora](#6-bitácora)
7. [Segunda auditoría (2026-09-25): contrastada contra el código de Leontis](#7-segunda-auditoría-2026-09-25)

---

# 1. Errores por severidad

## 🔴 CRÍTICOS — los números que muestra la app están mal

### 1.1 Las ventas incluyen notas de crédito y recibos de cobranza

**Archivo:** `Recursos/Modulos/statistics_generator.py` — afecta a
`get_top_articles_by_value`, `get_top_articles_by_quantity`,
`get_top_customers_by_billing`, `get_sales_over_time`,
`get_sales_by_day_for_excel`, `get_sales_by_payment_method_for_chart`,
`get_top_articles_for_excel`, `get_top_clients_for_excel`,
`get_rfm_analysis_data`, `get_kpi_total_sales_last_30_days`,
`get_kpi_sales_by_payment_last_7_days`.

Todas filtran únicamente por `ce.Anulado = 0`. Ninguna filtra por
`idTipoComprobante`. Pero la propia app, en `get_customer_debt_for_excel:444`,
declara que:

```python
CREDIT_TYPES_TUPLE = "(3, 8, 13, -83)"   # NC A, NC B, NC M, RC X (recibo)
```

Es decir: `comprobanteemitido` guarda **notas de crédito y recibos de cobranza
mezclados con las facturas**. Consecuencia directa:

- Una NC de $100.000 **suma** $100.000 a "Ventas por Día" en vez de restar.
  Error de $200.000 en la serie.
- Cada **recibo de cobranza** (`-83`) se cuenta como si fuera una venta nueva.
  En un corralón con mucha cuenta corriente esto puede inflar la facturación
  reportada un 30-50%.
- El "Top Clientes" premia al cliente que más devuelve mercadería.
- El RFM clasifica como "Campeón" a quien más notas de crédito recibió.

Esto invalida prácticamente todos los informes de venta. **Es el bug más
importante del proyecto.**

**Corrección** — centralizar el criterio en un helper y usarlo en todas partes:

```python
# statistics_generator.py
# Convención Leontis: 1/6/11 = facturas, 3/8/13 = notas de crédito,
# -81 = comprobante interno, -83 = recibo de cobranza.
TIPOS_NOTA_CREDITO = (3, 8, 13)
TIPOS_NO_VENTA     = (-81, -83)

SIGNO_VENTA_SQL = """
    CASE WHEN {a}.idTipoComprobante IN (3, 8, 13) THEN -1 ELSE 1 END
"""

FILTRO_VENTA_SQL = """
    AND {a}.Anulado = 0
    AND {a}.idTipoComprobante NOT IN (-81, -83)
"""
```

y luego, por ejemplo en `get_sales_over_time`:

```sql
SELECT DATE(FechaComprobante) AS Fecha,
       SUM(TotalOperacion * CASE WHEN idTipoComprobante IN (3,8,13)
                                 THEN -1 ELSE 1 END) AS 'Total Ventas ($)'
FROM comprobanteemitido
WHERE idEmpresa = :company_id
  AND Anulado = 0
  AND idTipoComprobante NOT IN (-81, -83)
  ...
```

> ⚠️ Antes de aplicarlo, confirmá los IDs contra la tabla real de tipos de
> comprobante de Leontis. Los valores de arriba salen del propio código
> (`statistics_generator.py:444` y `:499-507`), pero conviene validarlos con un
> `SELECT idTipoComprobante, COUNT(*) FROM comprobanteemitido GROUP BY 1`.

---

### 1.2 El desglose por medio de pago suma peras con manzanas

**Archivo:** `statistics_generator.py:146-202`

```sql
SUM(PagoEfectivo)                                            AS 'Efectivo',
SUM(CASE WHEN IdMedioDePago = 2 THEN TotalOperacion END)     AS 'Tarjeta',
SUM(PagoCheques)                                             AS 'Cheque',
SUM(CASE WHEN IdMedioDePago NOT IN (1,2,4) AND PagoEfectivo = 0
              AND PagoCheques = 0 THEN TotalOperacion END)   AS 'Otros',
SUM(TotalOperacion)                                          AS 'Total'
```

Tres problemas encadenados:

1. **Efectivo y Cheque** suman campos de *pago parcial* (`PagoEfectivo`,
   `PagoCheques`), mientras que **Tarjeta y Otros** suman el *total del
   comprobante*. No son la misma magnitud.
2. Una factura de $100.000 pagada $40.000 en efectivo con `IdMedioDePago = 2`
   suma $40.000 a Efectivo **y** $100.000 a Tarjeta → $140.000 sobre $100.000
   reales.
3. La columna `Total` no es la suma de las otras columnas, así que el gráfico
   multilínea nunca cierra con el gráfico de total.

Además el esquema ya trae **`comprobanteemitido.MediosDePagoDetalle
VARCHAR(1000)`**, que es la fuente correcta y está sin usar.

**Corrección mínima** (sin parsear el detalle): definir las categorías como
partición exclusiva del total.

```sql
SELECT DATE(FechaComprobante) AS Fecha,
       SUM(PagoEfectivo * sg)                                  AS 'Efectivo',
       SUM(PagoCheques  * sg)                                  AS 'Cheque',
       SUM(CASE WHEN IdMedioDePago = 2
                THEN (TotalOperacion - PagoEfectivo - PagoCheques) * sg
                ELSE 0 END)                                    AS 'Tarjeta',
       SUM(CASE WHEN IdMedioDePago <> 2 OR IdMedioDePago IS NULL
                THEN (TotalOperacion - PagoEfectivo - PagoCheques) * sg
                ELSE 0 END)                                    AS 'Otros/Cta.Cte.',
       SUM(TotalOperacion * sg)                                AS 'Total'
FROM (SELECT ce.*, CASE WHEN ce.idTipoComprobante IN (3,8,13)
                        THEN -1 ELSE 1 END AS sg
      FROM comprobanteemitido ce) ce
WHERE ...
```

Ahora `Efectivo + Cheque + Tarjeta + Otros = Total` siempre.

**Bonus:** el resto de la operación que no está en efectivo ni cheque **es
cuenta corriente**, y eso ya es un dato útil por sí solo para una ferretería.

---

### 1.3 Dos definiciones distintas de "medio de pago" en la misma app

`get_sales_by_day_for_excel:146` usa una lógica y
`get_kpi_sales_by_payment_last_7_days:643` usa otra completamente distinta
(un `CASE` con prioridades). El KPI del panel y el informe de Ventas dan
números diferentes para el mismo período. Unificar en una sola función.

---

### 1.4 Rol de administrador forzado para todos los usuarios

**Archivo:** `main.py:247-251`

```python
is_admin = api_result.get("isPermitirFacturaElectronicaProduccion", False)
# user_role_found = "admin" if is_admin else "usuario"

# Forzar modo admin para pruebas:
user_role_found = "admin"
```

Código de prueba que quedó en producción. **Todo usuario ve el Panel de Control
y todos los informes**, incluidos deuda total y cuenta corriente, sin importar
lo que devuelva la API. `apply_role_restrictions()` (`main.py:733`) nunca se
ejecuta en su rama restrictiva.

Descomentar la línea real y borrar el forzado.

---

### 1.5 `QMessageBox` desde el hilo secundario → riesgo de crash

**Archivo:** `db_connection.py:20` y `:39`

`_execute_query` levanta `QMessageBox.critical(...)` cuando falla. Ese método lo
llama `DashboardWorker`, que vive en un `QThread` (`main.py:713-719`). Crear
widgets Qt fuera del hilo GUI es comportamiento indefinido: en Windows suele
terminar en cierre silencioso de la app.

**Corrección:** `_execute_query` debe *solo* loguear y devolver/propagar; que la
capa de UI decida cómo mostrar el error.

```python
except Exception as e:
    print(f"--- [ERROR SQL] ---\n{query}\n{params}\n{e}\n-------------------")
    self.last_error = str(e)
    return pd.DataFrame()
```

Lo mismo aplica al `QMessageBox` de `db_connection.py:20`.

---

### 1.6 El hilo del dashboard no hace nada: el trabajo corre igual en la UI

**Archivo:** `main.py:1523-1524`

```python
def trigger_dashboard_load(self, force_refresh):
    QTimer.singleShot(0, lambda: self.dashboard_worker.run_all_loads(...))
```

`QTimer.singleShot` crea el timer **en el hilo que lo llama** (el GUI), por lo
que el `lambda` se ejecuta en el event loop del GUI. El `moveToThread` de la
línea 719 no cambia eso: llamar a un método de un objeto directamente lo ejecuta
en el hilo del *llamador*, no en el del objeto.

Resultado: las tres consultas SQL + las cuatro llamadas HTTP a dolarapi/BCRA
**congelan la ventana** al abrir la app y en cada "Actualizar Datos Externos".
Toda la arquitectura de threading está presente pero inoperante.

**Corrección:** disparar por señal (conexión en cola automática entre hilos).

```python
# main.py
class MainWindow(QMainWindow):
    request_dashboard_load = Signal(bool)      # nuevo

    def setup_dashboard(self):
        ...
        self.request_dashboard_load.connect(self.dashboard_worker.run_all_loads)

    def trigger_dashboard_load(self, force_refresh):
        self.reset_dashboard_labels_to_loading()
        self.request_dashboard_load.emit(force_refresh)   # cruza al worker thread
```

```python
# dashboard_manager.py
from PySide6.QtCore import Slot

@Slot(bool)
def run_all_loads(self, force_api_refresh=False):
    ...
```

(Requiere además arreglar 1.5, porque una vez que corra de verdad en otro hilo,
el `QMessageBox` de `_execute_query` sí va a explotar.)

---

### 1.7 El "Análisis de Canasta" puede colgar la aplicación

**Archivo:** `statistics_generator.py:258-268`

```sql
FROM comprobanteemitidoitems i1
JOIN comprobanteemitidoitems i2 ON i1.idComprobanteEmitido = i2.idComprobanteEmitido
```

Self-join cuadrático sobre los ítems. Con "Todo el Historial" seleccionado
(opción por defecto disponible en el combo) y un corralón con 200.000 ítems, el
producto cartesiano por comprobante es enorme, **y corre en el hilo GUI** (no
hay worker para los informes, solo para el dashboard). La app queda "No
responde" indefinidamente, sin barra de progreso ni cancelación.

**Mitigaciones, en orden de esfuerzo:**

1. Prohibir "Todo el Historial" en la tarjeta de canasta (máximo 365 días).
2. Acotar a comprobantes con más de 1 ítem y descartar los de más de N ítems
   (una factura de obra con 80 renglones genera 3.160 pares y ensucia el
   resultado):
   ```sql
   ValidTransactions AS (
       SELECT ce.idComprobanteEmitido
       FROM comprobanteemitido ce
       JOIN comprobanteemitidoitems it USING (idComprobanteEmitido)
       WHERE ce.idEmpresa = :company_id AND ce.Anulado = 0
         AND ce.idTipoComprobante NOT IN (3,8,13,-81,-83)
         {date_filter}
       GROUP BY ce.idComprobanteEmitido
       HAVING COUNT(*) BETWEEN 2 AND 25
   )
   ```
3. Mover toda la generación de informes a un `QThread` con diálogo de progreso
   cancelable.
4. Agregar el índice de §4 sobre `comprobanteemitido`.

---

## 🟠 IMPORTANTES

### 1.8 No se guardan las preferencias al cerrar con la X

`save_settings()` solo se invoca desde `ask_next_action()` (`main.py:906`),
o sea únicamente si el usuario exporta algo **y** después elige "Cerrar el
programa". `closeEvent` (`main.py:1581`) no la llama.

Esto contradice el manual de la propia app: *"se guardan automáticamente al
cerrar el programa"* (`main.py:551`).

```python
def closeEvent(self, event):
    self.save_settings()          # <-- agregar
    try:
        if self.dashboard_thread and self.dashboard_thread.isRunning():
            ...
```

### 1.9 La selección manual de artículos de la canasta no se restaura

`main.py:1507` — `QSettings` en Windows guarda las listas en el registro como
**strings**. Al releer, `manual_basket_selection` es `['12','45']`, pero
`ArticleSelectionDialog.set_selection` compara contra `row['idArticulo']`, que
es `int`. Ningún ítem aparece tildado; el usuario cree que perdió la selección.

```python
raw = self.settings.value("manual_basket_selection", []) or []
self.manual_basket_selection = [int(x) for x in raw]
```

### 1.10 `QSettings` es global, no por empresa

Con un usuario que tiene varias empresas (el flujo de `CompanySelectionDialog`
existe), `manual_basket_selection` guarda IDs de artículos de la empresa A y se
reutilizan en la empresa B — donde esos IDs son otros artículos, o no existen.

Prefijar todas las claves con la empresa:

```python
self.settings = QSettings("Leontis", "AnalizadorEstadisticas")
...
self.settings.beginGroup(f"empresa_{config_data['id_empresa']}")
```

### 1.11 Los clientes con `CodigoCliente` NULL desaparecen sin aviso

`statistics_generator.py:73` y `:135`:

```sql
AND cli.CodigoCliente != '0'
```

`CodigoCliente` es `VARCHAR(10)` **nullable**. En SQL, `NULL != '0'` evalúa a
`NULL`, no a `TRUE` → la fila se descarta. Cualquier cliente cargado sin código
queda fuera del Top Clientes, en silencio.

```sql
AND (cli.CodigoCliente IS NULL OR cli.CodigoCliente <> '0')
```

Relacionado: el `JOIN clientes` de esas mismas consultas descarta los
comprobantes con `idCliente IS NULL` (ticket a consumidor final sin cliente
asociado, que el esquema contempla con `ClienteApellidoNombre`). Por eso el
total de "Top Clientes" **nunca** cuadra con "Ventas por Día". Usar `LEFT JOIN`
y agrupar los nulos como "Consumidor Final".

### 1.12 El RFM se rompe con pocos clientes

`statistics_generator.py:607-615`. `pd.qcut(..., 5, labels=[5,4,3,2,1],
duplicates='drop')` lanza `ValueError: Bin labels must be one fewer than the
number of bin edges` cuando se colapsan bins — que es exactamente lo que pasa
con menos de ~10 clientes o con muchos empates (típico en una ferretería de
barrio donde casi todos compraron 1 sola vez).

El `except` de la línea 611 hace un fallback que **usa la misma técnica** y
falla igual → la excepción se propaga y aborta la exportación completa.

```python
def _score(serie, invertir=False):
    """Quintiles robustos: si no hay 5 grupos distintos, usa los que haya."""
    etiquetas = [5, 4, 3, 2, 1] if invertir else [1, 2, 3, 4, 5]
    rank = serie.rank(method='first')
    for n in (5, 4, 3, 2, 1):
        try:
            labs = etiquetas[:n] if not invertir else etiquetas[-n:]
            return pd.qcut(rank, n, labels=labs).astype(int)
        except ValueError:
            continue
    return pd.Series(3, index=serie.index)   # todos iguales → puntaje medio

df_rfm['R_Score'] = _score(df_rfm['Recencia'], invertir=True)
df_rfm['F_Score'] = _score(df_rfm['Frecuencia'])
df_rfm['M_Score'] = _score(df_rfm['Monetario'])
```

Además el RFM no tiene filtro de período: promedia toda la historia, así que un
cliente que compraba en 2019 arrastra "Frecuencia" alta para siempre. Agregar el
combo de período como en las demás tarjetas.

### 1.13 "Ventas por Día" con "Todo el Historial" puede reventar matplotlib

`matplotlib_widget.py:86-90` — `plot_line_chart` fija
`major_interval = 15 / minor_interval = 5` para cualquier rango > 30 días. Con
5 años de datos son 365 ticks menores; con 15 años supera el límite de 1.000
ticks de matplotlib y lanza `Locator attempting to generate N ticks`.

`plot_multi_line_chart` (línea 121-128) **sí** escala dinámicamente. Copiar esa
lógica a `plot_line_chart`.

### 1.14 `QMessageBox.critical(self, ...)` con un objeto que no es widget

`db_connection.py:207`, dentro del `except` de `setup_empresa_and_ui`:

```python
except Exception as e:
    QMessageBox.critical(self, "Error", ...)   # self es AppLogic, no un QWidget
```

Levanta `TypeError` dentro del manejador de excepciones y **enmascara el error
original**. Debe ser `self.window`.

### 1.15 Fuga de figuras y widgets en la exportación a Excel

`main.py:1244` llama a `create_chart_image_in_memory`, que instancia un
`MatplotlibWidget()` (un `QWidget` completo con canvas) por cada gráfico y nunca
lo cierra. En la ruta PDF sí hay `plt.close(fig)` (línea 1024); en la de Excel
no. Exportar varias veces en una sesión acumula figuras y termina en el warning
de matplotlib `More than 20 figures have been opened`.

```python
finally:
    plt.close(chart_exporter.figure)
    chart_exporter.deleteLater()
```

Y de paso: para exportar a imagen no hace falta un `QWidget`; alcanza con
`matplotlib.figure.Figure` puro.

---

## 🟡 MENORES / calidad

| # | Ubicación | Problema |
|---|---|---|
| 1.16 | `ui_factory.py:448` | `Recursos/Grafico/sync-icon.png` **no existe** en el proyecto. El botón "Actualizar Datos Externos" queda sin icono. |
| 1.17 | `ui_factory.py:259-261` | `create_statistics_panel` crea un `QTabWidget` local que nunca se usa ni se agrega a nada. Código muerto. |
| 1.18 | `main.py:1180` | Dentro del bloque de `market_basket`, el `for i in range(len(df_excel))` **pisa** la variable `i` del `enumerate` externo. Hoy no rompe por suerte; es una bomba de tiempo. Renombrar a `fila_idx`. |
| 1.19 | `db_connection.py:239` | `limit = 30 if "30" in limit_text else -1` — parsea el **texto** del combo. Si alguien cambia la etiqueta a "Top 30 artículos con más stock" sigue andando, pero si la cambia a "Los 30 primeros" también... y si pone "Top 50" devuelve -1 (todos). Usar `currentData()`. |
| 1.20 | `statistics_generator.py:204-219` | `get_stock_data_for_excel` no filtra `Activo = 1`: el informe de stock incluye artículos dados de baja. |
| 1.21 | `statistics_generator.py:235` | `manual_article_ids=[]` — argumento mutable por defecto. |
| 1.22 | `statistics_generator.py:321` | `art_main.idArticulo IN :manual_ids` con una tupla y `text()` plano funciona "de casualidad" (pymysql escapa tuplas). Rompe al actualizar SQLAlchemy. Usar `bindparam("manual_ids", expanding=True)`. |
| 1.23 | `statistics_generator.py:292-298` | La columna se llama `'Nro. Asociaciones'` pero es `SUM(Frecuencia)` (suma de co-ocurrencias), no la cantidad de artículos asociados. Nombre engañoso. |
| 1.24 | `statistics_generator.py:21` | `days == 1` ("Últimas 24 horas") compara un campo `DATE` contra `NOW()`; en la práctica devuelve "solo hoy", no las últimas 24 h. |
| 1.25 | `statistics_generator.py:559-571` | `get_slob_analysis_for_excel` devuelve un DataFrame *placeholder* con texto en vez de vacío. Cualquier consumidor que sume la columna obtiene un 0 falso en lugar de "sin datos". |
| 1.26 | `main.py:1007-1008` | `if report_name == "rfm_segmentation": pass` — no-op. |
| 1.27 | `main.py:1133` | `sheet_name = titulo[:31]` sin sanitizar ni desduplicar. Si dos informes colapsan al mismo nombre, xlsxwriter aborta la exportación entera. |
| 1.28 | `main.py:1-28` | Imports sin usar: `Table`, `QAbstractItemView`, `QGroupBox`, `QComboBox`, `QSpacerItem`, `QSizePolicy`, `QSize`, `QFont`, `QPainter`, `QColor`, `json`. Ídem `db_connection.py`: `sys`, `StatisticsGenerator`, `HIGHLIGHTED_COMBO_STYLE`. |
| 1.29 | `main.py:1036`, `1262`, `1326` | `retry_btn = msg_box.addButton(...)` asignado y nunca leído. |

---

# 2. Mejoras técnicas

## 2.1 Seguridad — credenciales expuestas 🔴

Tres problemas encadenados en `main.py` / `db_connection.py`:

```python
self.API_BASE_URL = "http://sistema.leontis.com.ar:65081"   # main.py:61  ← HTTP plano
```

1. **Login por HTTP sin TLS.** Base64 no es cifrado: usuario y contraseña viajan
   en claro y son legibles por cualquiera en la red (WiFi del local, ISP).

   > **Comprobado el 2026-08-04: el servidor NO soporta HTTPS en el puerto
   > 65081.** Un handshake TLS contra él devuelve `WRONG_VERSION_NUMBER`, que es
   > la respuesta HTTP en texto plano al `ClientHello`. Cambiar el esquema a
   > `https://` rompe el login por completo, y así fue como se rompió en la
   > primera pasada de estas correcciones.
   >
   > `Modulo Servicios` y el importador desde Eslaboon usan el mismo `http://`,
   > así que **esto no se arregla en esta app**: hay que ponerle certificado al
   > servidor y después migrar los tres módulos. Mientras tanto la app acepta
   > `ESTADISTICAS_API_URL` para probar el `https://` sin recompilar.
2. **`main.py:241`** imprime la cadena de conexión decodificada — con host,
   usuario y **contraseña de la base de datos** — a stdout.
3. **`db_connection.py:144`** vuelve a imprimir la URL completa de SQLAlchemy,
   contraseña incluida.
4. **La contraseña se inyecta cruda en la URL de SQLAlchemy.** Si trae `@`, `:`,
   `/` o `#`, la URL se parsea mal y la conexión falla con un error que no dice
   nada útil. Hay que escaparla con `urllib.parse.quote_plus`. El mismo problema
   está en `Modulo Servicios/RECURSOS/MODULOS/db_writer.py:10` y en el importador
   desde Eslaboon; **conviene arreglarlo también ahí**.

En el `.exe` compilado con consola, o si alguien redirige stdout a un log, queda
la credencial de la BD del cliente en texto plano.

```python
# db_connection.py
url_segura = f"mysql+pymysql://{user}:***@{host}:{port}/{database}"
print(f"DEBUG: Conectando a MariaDB con: {url_segura}")
```

Y en `main.py:241`, borrar el print o loguear solo el host.

**Adicional:** el esquema muestra `usuarios.Password VARCHAR(50)` y
`vendedores.Password VARCHAR(45)` — largos compatibles con texto plano o MD5,
no con un hash moderno. Está fuera del alcance de esta app, pero vale
levantarlo con el equipo del backend.

## 2.2 Logging en vez de `print`

Hay ~60 `print()` de debug repartidos por todos los módulos, incluyendo el
volcado completo de cada consulta SQL con sus parámetros
(`db_connection.py:23-25`). En un build `--windowed` no se ven; en uno con
consola son ruido y filtran datos.

Reemplazar por `logging` con niveles y un `RotatingFileHandler` a
`Recursos/Config/logs/` (carpeta que el updater no toca, según `CLAUDE.md`).

## 2.3 Informes en segundo plano con progreso cancelable

Hoy toda la generación de informes corre en el hilo GUI. `export_to_excel`
llega a hacer 10+ consultas pesadas seguidas, con
`QApplication.processEvents()` (`main.py:1444`) como único paliativo — que
además reentra en el event loop y permite al usuario tocar botones a mitad de
una exportación.

La infraestructura ya existe (`DashboardWorker`): generalizarla a un
`ReportWorker` que reciba la lista de informes y emita progreso.

## 2.4 Caché de consultas dentro de una exportación

`export_to_pdf` y `export_to_excel` llaman a
`self.logic.generate_statistics()` **y además** a
`get_detailed_data_for_report()` para el mismo informe. En el caso del RFM,
`get_rfm_analysis_data` se ejecuta **dos veces** (una para el gráfico en
`db_connection.py:359`, otra para el detalle en `:260`), recalculando todo el
análisis sobre la base completa. Lo mismo con stock, canasta y SLOB.

Un caché por `(report_key, params)` con vida de una exportación corta los
tiempos a la mitad.

## 2.5 Duplicación de `resource_path`

Definida tres veces idéntica: `main.py:31`, `ui_factory.py:19`,
`dashboard_manager.py:11` — con **bases distintas** (`main.py` usa el directorio
del script; los otros suben dos niveles). Funciona por casualidad porque
`main.py` está en la raíz. Extraer a `Recursos/Modulos/rutas.py`.

## 2.6 `pool_pre_ping` solo en un camino de conexión

`connect_with_connection_string` usa `pool_pre_ping=True` (bien), pero
`connect_to_database` y `connect_to_server` no. Con una sesión larga (la app
queda abierta todo el día en el mostrador) MySQL cierra la conexión por
`wait_timeout` y el siguiente informe falla. Agregar `pool_pre_ping=True` y
`pool_recycle=3600` en todos.

## 2.7 `_execute_query` abre conexión nueva por consulta

Y ejecuta `SET SESSION group_concat_max_len` cada vez, incluso en consultas que
no usan `GROUP_CONCAT`. Con el engine de SQLAlchemy y su pool esto es barato,
pero conviene moverlo a un evento `connect` del engine.

## 2.8 Falta configuración de build

`CLAUDE.md` lo marca explícitamente: **no hay `.spec` ni `.bat`**. Para entrar al
sistema de MINIhub hace falta:

- `ModuloEstadisticasLeontis.spec` → **onedir**, nunca onefile.
- El `.exe` debe llamarse `ModuloEstadisticasLeontis.exe`.
- `Recursos/Config` queda fuera de lo que el updater pisa.
- Falta también `requirements.txt` (dependencias detectadas: `PySide6`,
  `pandas`, `matplotlib`, `sqlalchemy`, `pymysql`, `requests`, `xlsxwriter`,
  `openpyxl`, `numpy`).
- No están `nucleo.py`, `ftp_config.py` ni `ui_updater.py` — la integración con
  el updater está pendiente. Ver `ACTUALIZACIONES.md`.

## 2.9 Higiene del repositorio

- La carpeta local **no es un repo git** (`git status` → *not a git
  repository*), pese a que `CLAUDE.md` apunta a un remoto en GitHub. Está
  desconectada del repo.
- `Recursos/Modulos/__pycache__/*.pyc` versionado.
- `Recursos/Grafico.rar` (85 KB) versionado — un `.rar` no va al repo.
- Falta `.gitignore` (`__pycache__/`, `*.pyc`, `build/`, `dist/`, `*.spec` si se
  genera, `Recursos/Config/*.log`).

## 2.10 Sin tests

Cero cobertura. Los cálculos de negocio (signo de comprobantes, RFM, ABC, aging)
son puros y perfectamente testeables sin base de datos: separar la lógica de
pandas de la capa SQL y agregar `pytest` con DataFrames sintéticos. Dado el bug
§1.1, esto no es un lujo.

## 2.11 Detalles de UX

- **Sin indicador de progreso real** en exportaciones largas — solo texto en la
  barra de estado, con la ventana congelada (§2.3).
- **`ask_next_action`** propone "Cerrar el programa" después de *cada*
  exportación exitosa. Es intrusivo; un mensaje en la barra de estado y un botón
  "Abrir carpeta" sería mejor.
- **El PDF corta a 100 filas** (`main.py:945`, `:972`) sin avisar en pantalla —
  solo en el título del gráfico.
- **Los informes no se previsualizan**: hay un `MatplotlibWidget` capaz de
  renderizar en la app, pero solo se usa para exportar a archivo. Mostrar el
  gráfico en la propia tarjeta antes de exportar sería una mejora grande y
  barata (el widget ya existe).

---

# 3. Estadísticas nuevas propuestas

Contexto: pequeño comercio, ferretería, corralón de materiales. Lo que sigue
está ordenado por **impacto sobre la caja del negocio**.

Datos del esquema que hoy la app **no usa en absoluto**:

| Fuente sin explotar | Qué habilita |
|---|---|
| `comprobanteemitidoitems.Rentabilidad`, `articulos.PrecioCosto` | Margen real por artículo, cliente y vendedor |
| `articulos.ExistenciaMinima`, `FechaUltimaCompra`, `CantidadUltimaCompra` | Reposición y sugerido de compra |
| `articulos.idProveedor` + tabla `proveedores` | Análisis por proveedor/marca |
| **Tabla `comprobantescompras` completa** | Compras, IVA crédito, evolución de costos |
| **Tabla `movimientoscaja` completa** | Flujo de caja real (ingresos/egresos) |
| `comprobanteemitido.FechaHoraCreacion` | Ventas por hora y día de semana |
| `comprobanteemitido.idVendedor` + `vendedores.ComisionFija` | Rendimiento y comisiones |
| `comprobanteemitido.idTipoReparto`, `clientes.Localidad` | Análisis por zona / logística |
| `comprobanteemitido.FechaVencimientoPago`, `TotalPagos`, `Pagado` | Aging real de cuenta corriente |
| `articulos.FechaUltimaActualizacionPrecio`, `PorcentajeMarcacion1` | Erosión de margen por inflación |
| `comprobanteemitidoitems.PorcentajeBonificacion` | Control de descuentos otorgados |
| `articulos.EsVentaPorPeso`, `IncluyeEnvase`, `EnvasesAdeudados` | Granel y envases |

Notación usada abajo:

```sql
-- CTE base reutilizable (aplica el fix de §1.1)
WITH Ventas AS (
    SELECT ce.*,
           CASE WHEN ce.idTipoComprobante IN (3,8,13) THEN -1 ELSE 1 END AS sg
    FROM comprobanteemitido ce
    WHERE ce.idEmpresa = :company_id
      AND ce.Anulado = 0
      AND ce.idTipoComprobante NOT IN (-81,-83)
      AND ce.FechaComprobante >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
)
```

---

## 3.1 🥇 Margen bruto por artículo (no solo facturación)

**Por qué:** es *la* estadística que le falta a esta app. En ferretería el
margen va del 8% (cemento, hierro, chapa) al 60% (bulonería, herramientas
menores). El artículo que más factura casi nunca es el que más gana. Hoy la app
solo muestra facturación, que para tomar decisiones de compra es engañoso.

```sql
SELECT
    a.CodigoArticulo                                        AS 'Código',
    a.Descripcion                                           AS 'Descripción',
    SUM(cei.Cantidad * v.sg)                                AS 'Unidades',
    SUM(cei.TotalItemSinIVA * v.sg)                         AS 'Facturado s/IVA',
    SUM(cei.Cantidad * a.PrecioCosto * v.sg)                AS 'Costo',
    SUM((cei.TotalItemSinIVA - cei.Cantidad * a.PrecioCosto) * v.sg)
                                                            AS 'Margen Bruto ($)',
    ROUND(100 * SUM((cei.TotalItemSinIVA - cei.Cantidad * a.PrecioCosto) * v.sg)
              / NULLIF(SUM(cei.TotalItemSinIVA * v.sg), 0), 1)
                                                            AS '% Margen',
    a.ExistenciaActual                                      AS 'Stock'
FROM Ventas v
JOIN comprobanteemitidoitems cei ON cei.idComprobanteEmitido = v.idComprobanteEmitido
JOIN articulos a               ON a.idArticulo = cei.idArticulo
GROUP BY a.idArticulo, a.CodigoArticulo, a.Descripcion, a.ExistenciaActual
HAVING `Facturado s/IVA` > 0
ORDER BY `Margen Bruto ($)` DESC;
```

> El esquema trae `comprobanteemitidoitems.Rentabilidad` precalculada. Si ese
> campo está poblado y es confiable en las instalaciones reales, usarlo es más
> exacto (captura el costo **al momento de la venta**, no el costo actual).
> Vale correr `SELECT COUNT(*), SUM(Rentabilidad<>0) FROM comprobanteemitidoitems`
> en una base real para decidir. El cálculo de arriba usa el costo de hoy, lo
> que en Argentina distorsiona hacia atrás — señalarlo en el informe.

**Gráfico sugerido:** barras horizontales duales (facturación vs margen), o
scatter `% margen` × `facturación` con el tamaño del punto = stock.

---

## 3.2 🥇 Curva ABC (Pareto 80/20) de artículos

**Por qué:** una ferretería maneja 5.000-20.000 SKU y no puede prestarle
atención a todos. La regla es que ~20% de los artículos genera ~80% de la venta.
Saber cuáles son los "A" define qué nunca puede faltar, dónde se negocia precio
con el proveedor y qué se puede discontinuar.

```sql
WITH VentasArt AS (
    SELECT cei.idArticulo,
           SUM(cei.TotalItemSinIVA * v.sg) AS Facturado,
           SUM(cei.Cantidad * v.sg)        AS Unidades,
           COUNT(DISTINCT v.idComprobanteEmitido) AS Tickets
    FROM Ventas v
    JOIN comprobanteemitidoitems cei ON cei.idComprobanteEmitido = v.idComprobanteEmitido
    WHERE cei.idArticulo IS NOT NULL
    GROUP BY cei.idArticulo
    HAVING Facturado > 0
),
Acum AS (
    SELECT va.*,
           SUM(va.Facturado) OVER (ORDER BY va.Facturado DESC
                                   ROWS UNBOUNDED PRECEDING)
             / NULLIF(SUM(va.Facturado) OVER (), 0) AS PctAcum,
           ROW_NUMBER() OVER (ORDER BY va.Facturado DESC) AS Ranking
    FROM VentasArt va
)
SELECT
    ac.Ranking                                     AS '#',
    a.CodigoArticulo                               AS 'Código',
    a.Descripcion                                  AS 'Descripción',
    ac.Unidades                                    AS 'Unidades',
    ac.Tickets                                     AS 'Tickets',
    ac.Facturado                                   AS 'Facturado',
    ROUND(100 * ac.PctAcum, 1)                     AS '% Acumulado',
    CASE WHEN ac.PctAcum <= 0.80 THEN 'A'
         WHEN ac.PctAcum <= 0.95 THEN 'B'
         ELSE 'C' END                              AS 'Clase',
    a.ExistenciaActual                             AS 'Stock',
    ROUND(a.ExistenciaActual * a.PrecioCosto, 2)   AS 'Capital Inmovilizado'
FROM Acum ac
JOIN articulos a ON a.idArticulo = ac.idArticulo
ORDER BY ac.Ranking;
```

**Alerta automática de alto valor:** artículos **clase A con stock 0** = venta
que se está perdiendo hoy. Es el informe que más rápido paga el software.

---

## 3.3 🥇 Cobertura de stock y sugerido de compra por proveedor

**Por qué:** en una ferretería se compra **por proveedor** (por flete y por
mínimo de compra). El informe operativo que se usa todas las semanas es "qué le
pido a cada proveedor". El esquema tiene todo: `ExistenciaMinima`,
`idProveedor`, `PrecioCosto`, `FechaUltimaCompra`.

```sql
WITH Consumo AS (
    SELECT cei.idArticulo, SUM(cei.Cantidad * v.sg) AS Unidades
    FROM Ventas v
    JOIN comprobanteemitidoitems cei ON cei.idComprobanteEmitido = v.idComprobanteEmitido
    GROUP BY cei.idArticulo
)
SELECT
    COALESCE(p.RazonSocial, 'SIN PROVEEDOR')            AS 'Proveedor',
    a.CodigoArticulo                                    AS 'Código',
    a.Descripcion                                       AS 'Descripción',
    a.ExistenciaActual                                  AS 'Stock',
    a.ExistenciaMinima                                  AS 'Mínimo',
    ROUND(COALESCE(c.Unidades, 0) / :days, 2)           AS 'Venta Diaria',
    CASE WHEN COALESCE(c.Unidades, 0) <= 0 THEN NULL
         ELSE FLOOR(a.ExistenciaActual / (c.Unidades / :days))
    END                                                 AS 'Días de Cobertura',
    GREATEST(
        CEIL(COALESCE(c.Unidades,0) / :days * :dias_objetivo - a.ExistenciaActual),
        CEIL(a.ExistenciaMinima - a.ExistenciaActual),
        0
    )                                                   AS 'Sugerido a Comprar',
    a.PrecioCosto                                       AS 'Costo Unit.',
    a.FechaUltimaCompra                                 AS 'Últ. Compra'
FROM articulos a
LEFT JOIN proveedores p ON p.idProveedor = a.idProveedor
LEFT JOIN Consumo    c  ON c.idArticulo  = a.idArticulo
WHERE a.idEmpresa = :company_id AND a.Activo = 1
HAVING `Sugerido a Comprar` > 0
ORDER BY `Proveedor`,
         `Sugerido a Comprar` * a.PrecioCosto DESC;
```

`:dias_objetivo` sale de un combo nuevo ("cubrir 15 / 30 / 45 / 60 días").
La exportación a Excel debería generar **una hoja por proveedor** — así se manda
por WhatsApp tal cual.

---

## 3.4 🥇 Aging de cuenta corriente (0-30 / 31-60 / 61-90 / +90)

**Por qué:** el informe actual de cuenta corriente lista saldos, pero no dice
**hace cuánto** se debe. En un corralón que le fía a constructoras, la
antigüedad de la deuda es la diferencia entre "cliente que paga a 30 días" y
"plata perdida". El esquema tiene `FechaVencimientoPago` y `TotalPagos`, ambos
sin usar.

```sql
WITH SaldosAbiertos AS (
    SELECT ce.idCliente,
           COALESCE(ce.FechaVencimientoPago, ce.FechaComprobante) AS Vence,
           CASE WHEN ce.idTipoComprobante IN (3,8,13,-83) THEN -1 ELSE 1 END
             * (ce.TotalOperacion - ce.TotalPagos)                AS Saldo
    FROM comprobanteemitido ce
    WHERE ce.idEmpresa = :company_id
      AND ce.Anulado = 0
      AND (ce.TotalOperacion - ce.TotalPagos) <> 0
)
SELECT
    cli.RazonSocial                                       AS 'Cliente',
    cli.Telefonos                                         AS 'Teléfono',
    cli.SaldoActual                                       AS 'Saldo Total',
    SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) <= 0                THEN s.Saldo ELSE 0 END) AS 'Por vencer',
    SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) BETWEEN  1 AND  30  THEN s.Saldo ELSE 0 END) AS '1-30',
    SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) BETWEEN 31 AND  60  THEN s.Saldo ELSE 0 END) AS '31-60',
    SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) BETWEEN 61 AND  90  THEN s.Saldo ELSE 0 END) AS '61-90',
    SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) >  90               THEN s.Saldo ELSE 0 END) AS '+90 (incobrable?)',
    MAX(DATEDIFF(CURDATE(), s.Vence))                     AS 'Mora Máx. (días)'
FROM SaldosAbiertos s
JOIN clientes cli ON cli.idCliente = s.idCliente
GROUP BY cli.idCliente, cli.RazonSocial, cli.Telefonos, cli.SaldoActual
HAVING `Saldo Total` <> 0
ORDER BY `+90 (incobrable?)` DESC, `Saldo Total` DESC;
```

**Gráfico:** barras apiladas por tramo. **KPI del panel:** "% de la deuda con
más de 90 días" — si supera el 15% hay un problema serio de cobranza.

---

## 3.5 🥈 Ventas ajustadas por inflación (pesos constantes y en USD)

**Por qué:** la app **ya baja el IPC y las tres cotizaciones del dólar**
(`dashboard_manager.py`), pero solo los muestra como número suelto en el panel.
En Argentina, "facturé 40% más que el año pasado" con 120% de inflación
significa que **vendí menos**. Deflactar la serie de ventas es la mejora de
mayor relación valor/esfuerzo del proyecto, porque la infraestructura de datos
ya está construida.

Implementación (lado Python, la serie de IPC ya viene completa de datos.gob.ar —
hoy `_parse_inflation_data` solo lee los índices 0 a 2 y descarta el resto):

```python
def deflactar(df_ventas, serie_ipc, mes_base=None):
    """df_ventas: columnas [Mes, Total]. serie_ipc: Series indexada por Mes
    con la variación mensual en %. Devuelve el total a precios del mes base."""
    indice = (1 + serie_ipc / 100).cumprod()
    base = indice.loc[mes_base or indice.index.max()]
    df = df_ventas.set_index('Mes')
    df['Total Real'] = df['Total'] * (base / indice.reindex(df.index))
    return df.reset_index()
```

**Tres presentaciones, misma serie:**
1. Ventas nominales vs ventas a precios de hoy (dos líneas).
2. Ventas en USD (dividiendo por la cotización histórica).
3. **Variación real interanual mensual**: `% nominal − % inflación`.

El esquema incluso guarda `empresas.DolarCotizacion` y
`proveedores.DolarCotizacion`, útil para artículos importados (herramienta
eléctrica, griferías).

---

## 3.6 🥈 Erosión de margen / precios desactualizados

**Por qué:** con remarcaciones constantes de proveedores, es habitual que el
costo suba y el precio de venta quede viejo. El resultado es vender **por debajo
del costo de reposición** sin notarlo. El esquema tiene
`PorcentajeMarcacion1` (la marcación *configurada*) y
`FechaUltimaActualizacionPrecio`: se puede comparar contra la marcación *real*.

```sql
SELECT
    a.CodigoArticulo                                   AS 'Código',
    a.Descripcion                                      AS 'Descripción',
    a.PrecioCosto                                      AS 'Costo',
    a.Precio01Neto                                     AS 'Precio Neto',
    a.PorcentajeMarcacion1                             AS '% Marcación Config.',
    ROUND(100 * (a.Precio01Neto - a.PrecioCosto)
              / NULLIF(a.PrecioCosto, 0), 2)           AS '% Marcación Real',
    ROUND(100 * (a.Precio01Neto - a.PrecioCosto) / NULLIF(a.PrecioCosto, 0)
          - a.PorcentajeMarcacion1, 2)                 AS 'Desvío (p.p.)',
    a.FechaUltimaActualizacionPrecio                   AS 'Últ. Act. Precio',
    DATEDIFF(CURDATE(), a.FechaUltimaActualizacionPrecio) AS 'Días sin actualizar',
    a.ExistenciaActual                                 AS 'Stock',
    ROUND(a.ExistenciaActual * a.PrecioCosto, 2)       AS 'Capital en Riesgo'
FROM articulos a
WHERE a.idEmpresa = :company_id
  AND a.Activo = 1
  AND a.PrecioCosto > 0
  AND a.ExistenciaActual > 0
  AND (100 * (a.Precio01Neto - a.PrecioCosto) / a.PrecioCosto)
      < (a.PorcentajeMarcacion1 - :tolerancia_pp)
ORDER BY `Desvío (p.p.)` ASC;
```

**Caso extremo a destacar en rojo:** `Precio01Neto <= PrecioCosto` → se está
vendiendo a pérdida **ahora mismo**.

---

## 3.7 🥈 Ventas por hora y día de la semana (mapa de calor)

**Por qué:** define horarios de atención y turnos del personal de mostrador. Una
ferretería típicamente tiene un pico el sábado a la mañana y muerto los martes a
la tarde. `FechaHoraCreacion` está sin usar.

```sql
SELECT
    WEEKDAY(v.FechaHoraCreacion)                        AS DiaNum,
    ELT(WEEKDAY(v.FechaHoraCreacion) + 1,
        'Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo') AS 'Día',
    HOUR(v.FechaHoraCreacion)                           AS 'Hora',
    COUNT(DISTINCT v.idComprobanteEmitido)              AS 'Tickets',
    SUM(v.TotalOperacion * v.sg)                        AS 'Facturado',
    ROUND(SUM(v.TotalOperacion * v.sg)
          / NULLIF(COUNT(DISTINCT v.idComprobanteEmitido), 0), 2) AS 'Ticket Prom.'
FROM Ventas v
WHERE v.FechaHoraCreacion IS NOT NULL
GROUP BY DiaNum, HOUR(v.FechaHoraCreacion)
ORDER BY DiaNum, `Hora`;
```

**Gráfico:** heatmap 7×14 con `matplotlib.pyplot.imshow` — visualmente potente y
trivial de implementar con lo que ya está.

---

## 3.8 🥈 Ticket promedio, ítems por ticket y evolución mensual

**Por qué:** KPI comercial básico que hoy falta por completo. Si la facturación
sube pero el ticket promedio baja, el crecimiento es solo inflación.

```sql
SELECT
    DATE_FORMAT(v.FechaComprobante, '%Y-%m')            AS 'Mes',
    COUNT(DISTINCT v.idComprobanteEmitido)              AS 'Tickets',
    COUNT(DISTINCT v.idCliente)                         AS 'Clientes Distintos',
    SUM(v.TotalOperacion * v.sg)                        AS 'Facturado',
    ROUND(SUM(v.TotalOperacion * v.sg)
          / NULLIF(COUNT(DISTINCT v.idComprobanteEmitido), 0), 2) AS 'Ticket Promedio',
    ROUND(COUNT(cei.idComprobanteEmitidoItem)
          / NULLIF(COUNT(DISTINCT v.idComprobanteEmitido), 0), 2) AS 'Ítems por Ticket'
FROM Ventas v
LEFT JOIN comprobanteemitidoitems cei
       ON cei.idComprobanteEmitido = v.idComprobanteEmitido
GROUP BY `Mes`
ORDER BY `Mes` DESC;
```

---

## 3.9 🥈 Flujo de caja diario (tabla `movimientoscaja`, hoy sin tocar)

**Por qué:** la app mide facturación, no **plata**. Con cuenta corriente, facturar
no es cobrar. `movimientoscaja` tiene ingresos y egresos reales con medio de pago.

```sql
SELECT
    mc.FechaMovimiento                                                     AS 'Fecha',
    SUM(CASE WHEN mc.IngresoEgreso = 1 THEN mc.Importe ELSE 0 END)         AS 'Ingresos',
    SUM(CASE WHEN mc.IngresoEgreso <> 1 THEN mc.Importe ELSE 0 END)        AS 'Egresos',
    SUM(CASE WHEN mc.IngresoEgreso = 1 THEN mc.Importe ELSE -mc.Importe END) AS 'Neto del Día',
    SUM(SUM(CASE WHEN mc.IngresoEgreso = 1 THEN mc.Importe ELSE -mc.Importe END))
        OVER (ORDER BY mc.FechaMovimiento)                                 AS 'Saldo Acumulado'
FROM movimientoscaja mc
WHERE mc.IdEmpresa = :company_id
  AND mc.FechaMovimiento >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
GROUP BY mc.FechaMovimiento
ORDER BY mc.FechaMovimiento;
```

Complemento — **ranking de egresos** (a dónde se va la plata):

```sql
SELECT mc.Descripcion AS 'Concepto',
       COUNT(*)       AS 'Movimientos',
       SUM(mc.Importe) AS 'Total Egresado'
FROM movimientoscaja mc
WHERE mc.IdEmpresa = :company_id AND mc.IngresoEgreso <> 1
  AND mc.FechaMovimiento >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
GROUP BY mc.Descripcion
ORDER BY `Total Egresado` DESC;
```

> Verificar la convención de `IngresoEgreso` (`SMALLINT DEFAULT 1`) contra datos
> reales antes de fijar el signo.

---

## 3.10 🥈 Compras y posición de IVA (tabla `comprobantescompras`, sin tocar)

**Por qué:** cierra el círculo. Con ventas + compras se obtiene el margen real
del negocio y la **posición mensual de IVA** — dato que el ferretero mira todos
los meses y hoy calcula a mano.

```sql
SELECT t.Mes,
       SUM(t.Debito)                AS 'IVA Débito (Ventas)',
       SUM(t.Credito)               AS 'IVA Crédito (Compras)',
       SUM(t.Debito) - SUM(t.Credito) AS 'Posición IVA (a pagar)',
       SUM(t.NetoVenta)             AS 'Neto Ventas',
       SUM(t.NetoCompra)            AS 'Neto Compras'
FROM (
    SELECT DATE_FORMAT(FechaComprobante, '%Y-%m') AS Mes,
           (IVA_2100_Liquidado + IVA_1050_Liquidado)
             * CASE WHEN idTipoComprobante IN (3,8,13) THEN -1 ELSE 1 END AS Debito,
           0                                                              AS Credito,
           TotalNetoOperacion
             * CASE WHEN idTipoComprobante IN (3,8,13) THEN -1 ELSE 1 END AS NetoVenta,
           0                                                              AS NetoCompra
    FROM comprobanteemitido
    WHERE idEmpresa = :company_id AND Anulado = 0
      AND idTipoComprobante NOT IN (-81, -83)
    UNION ALL
    SELECT DATE_FORMAT(FechaComprobante, '%Y-%m'),
           0,
           (IVA_2100_Liquidado + IVA_1050_Liquidado),
           0,
           TotalNetoOperacion
    FROM comprobantescompras
    WHERE IdEmpresa = :company_id
) t
GROUP BY t.Mes
ORDER BY t.Mes DESC;
```

Y el **ranking de proveedores por compra**:

```sql
SELECT p.RazonSocial                              AS 'Proveedor',
       COUNT(*)                                   AS 'Comprobantes',
       SUM(cc.TotalOperacion)                     AS 'Total Comprado',
       SUM(cc.PercepcionesImpuestosNacionales
         + cc.PercepcionIIBB
         + cc.PercepcionImpuestosMunicipales)     AS 'Percepciones Sufridas',
       MAX(cc.FechaComprobante)                   AS 'Última Compra'
FROM comprobantescompras cc
JOIN proveedores p ON p.idProveedor = cc.IdProveedor
WHERE cc.IdEmpresa = :company_id
  AND cc.FechaComprobante >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
GROUP BY p.idProveedor, p.RazonSocial
ORDER BY `Total Comprado` DESC;
```

---

## 3.11 🥉 Concentración de clientes (riesgo comercial)

**Por qué:** en corralones es habitual que 3 constructoras sean el 60% de la
facturación. Si una se va o entra en default, el negocio se cae. Es un dato que
el dueño rara vez tiene cuantificado.

```sql
WITH PorCliente AS (
    SELECT COALESCE(v.idCliente, 0) AS idCliente,
           SUM(v.TotalOperacion * v.sg) AS Facturado
    FROM Ventas v GROUP BY COALESCE(v.idCliente, 0)
),
Rank AS (
    SELECT pc.*, ROW_NUMBER() OVER (ORDER BY pc.Facturado DESC) AS rn,
           SUM(pc.Facturado) OVER () AS TotalGeneral
    FROM PorCliente pc WHERE pc.Facturado > 0
)
SELECT
    COALESCE(cli.RazonSocial, 'Consumidor Final')      AS 'Cliente',
    r.Facturado                                        AS 'Facturado',
    ROUND(100 * r.Facturado / r.TotalGeneral, 2)       AS '% del Total',
    ROUND(100 * SUM(r.Facturado) OVER (ORDER BY r.Facturado DESC
                                       ROWS UNBOUNDED PRECEDING)
              / r.TotalGeneral, 2)                     AS '% Acumulado',
    cli.SaldoActual                                    AS 'Deuda Actual'
FROM Rank r
LEFT JOIN clientes cli ON cli.idCliente = r.idCliente
ORDER BY r.rn
LIMIT 25;
```

**KPI del panel:** "% de facturación en el top 5 clientes". Por encima del 50%
es riesgo alto.

---

## 3.12 🥉 Clientes fugados (churn) con lista de contacto

**Por qué:** complementa el RFM existente con algo **accionable**: una lista de
teléfonos para llamar. Los segmentos RFM son abstractos; "estos 12 clientes que
compraban todos los meses no vienen hace 90 días, acá está el teléfono" se
ejecuta el mismo día.

```sql
SELECT
    cli.RazonSocial                                     AS 'Cliente',
    cli.Telefonos                                       AS 'Teléfono',
    cli.Email                                           AS 'Email',
    cli.Localidad                                       AS 'Localidad',
    MAX(ce.FechaComprobante)                            AS 'Última Compra',
    DATEDIFF(CURDATE(), MAX(ce.FechaComprobante))       AS 'Días sin comprar',
    COUNT(DISTINCT ce.idComprobanteEmitido)             AS 'Compras Históricas',
    SUM(ce.TotalOperacion)                              AS 'Facturación Histórica',
    ROUND(SUM(ce.TotalOperacion)
          / NULLIF(COUNT(DISTINCT ce.idComprobanteEmitido), 0), 2) AS 'Ticket Promedio',
    cli.SaldoActual                                     AS 'Deuda Pendiente'
FROM comprobanteemitido ce
JOIN clientes cli ON cli.idCliente = ce.idCliente
WHERE ce.idEmpresa = :company_id AND ce.Anulado = 0
  AND ce.idTipoComprobante NOT IN (3,8,13,-81,-83)
GROUP BY cli.idCliente, cli.RazonSocial, cli.Telefonos, cli.Email,
         cli.Localidad, cli.SaldoActual
HAVING `Días sin comprar` BETWEEN :umbral_dias AND :limite_dias
   AND `Compras Históricas` >= :min_compras
ORDER BY `Facturación Histórica` DESC;
```

---

## 3.13 🥉 Rendimiento por vendedor y comisiones

`comprobanteemitido.idVendedor` y `vendedores.ComisionFija` están sin usar.

```sql
SELECT
    ven.ApellidoNombre                              AS 'Vendedor',
    COUNT(DISTINCT v.idComprobanteEmitido)          AS 'Comprobantes',
    COUNT(DISTINCT v.idCliente)                     AS 'Clientes Atendidos',
    SUM(v.TotalOperacion * v.sg)                    AS 'Facturado',
    SUM(v.Rentabilidad   * v.sg)                    AS 'Margen Generado',
    ROUND(SUM(v.TotalOperacion * v.sg)
          / NULLIF(COUNT(DISTINCT v.idComprobanteEmitido), 0), 2) AS 'Ticket Promedio',
    ven.ComisionFija                                AS 'Comisión Config.'
FROM Ventas v
JOIN vendedores ven ON ven.idVendedor = v.idVendedor
GROUP BY ven.idVendedor, ven.ApellidoNombre, ven.ComisionFija
ORDER BY `Facturado` DESC;
```

> `ComisionFija DECIMAL(19,2)` es ambiguo: puede ser porcentaje o monto fijo.
> Verificar con datos reales antes de calcular la comisión devengada.

---

## 3.14 🥉 Ventas por zona de reparto y localidad

`comprobanteemitido.idTipoReparto` + `clientes.Localidad` — relevante para
materiales de construcción, donde el flete define la rentabilidad de la venta.

```sql
SELECT
    COALESCE(tr.Descripcion, 'Sin reparto asignado')  AS 'Zona / Reparto',
    COALESCE(cli.Localidad, 'Sin localidad')          AS 'Localidad',
    COUNT(DISTINCT v.idComprobanteEmitido)            AS 'Entregas',
    COUNT(DISTINCT v.idCliente)                       AS 'Clientes',
    SUM(v.TotalOperacion * v.sg)                      AS 'Facturado',
    ROUND(SUM(v.TotalOperacion * v.sg)
          / NULLIF(COUNT(DISTINCT v.idComprobanteEmitido), 0), 2) AS 'Ticket Prom.'
FROM Ventas v
LEFT JOIN tiposderepartos tr ON tr.idTipoReparto = v.idTipoReparto
LEFT JOIN clientes cli       ON cli.idCliente    = v.idCliente
GROUP BY tr.idTipoReparto, tr.Descripcion, cli.Localidad
ORDER BY `Facturado` DESC;
```

---

## 3.15 🥉 Estacionalidad e interanual

La construcción es fuertemente estacional (obra parada por lluvia, feria de
enero, empuje de primavera). Comparar contra el mismo mes del año anterior es
más informativo que contra el mes previo.

```sql
WITH Mensual AS (
    SELECT DATE_FORMAT(ce.FechaComprobante, '%Y-%m') AS Mes,
           SUM(ce.TotalOperacion
               * CASE WHEN ce.idTipoComprobante IN (3,8,13) THEN -1 ELSE 1 END) AS Total
    FROM comprobanteemitido ce
    WHERE ce.idEmpresa = :company_id AND ce.Anulado = 0
      AND ce.idTipoComprobante NOT IN (-81,-83)
    GROUP BY Mes
)
SELECT Mes                                       AS 'Mes',
       Total                                     AS 'Facturado',
       LAG(Total, 12) OVER (ORDER BY Mes)        AS 'Mismo Mes Año Ant.',
       ROUND(100 * (Total / NULLIF(LAG(Total, 12) OVER (ORDER BY Mes), 0) - 1), 1)
                                                 AS 'Var. Interanual %'
FROM Mensual
ORDER BY Mes DESC;
```

Combinar con §3.5 para obtener la **variación interanual real** (descontando
inflación), que es el número que de verdad importa.

---

## 3.16 🥉 Descuentos otorgados

`comprobanteemitidoitems.PorcentajeBonificacion` y
`clientes.BonificacionGeneral` están sin usar. Un 5% de descuento sistemático
sobre un margen del 20% se lleva un cuarto de la ganancia.

```sql
SELECT
    COALESCE(cli.RazonSocial, 'Consumidor Final')                AS 'Cliente',
    SUM(cei.SubTotalItemSinIVA * v.sg)                           AS 'Bruto s/Desc.',
    SUM((cei.SubTotalItemSinIVA - cei.TotalItemSinIVA) * v.sg)   AS 'Descuento ($)',
    ROUND(100 * SUM((cei.SubTotalItemSinIVA - cei.TotalItemSinIVA) * v.sg)
              / NULLIF(SUM(cei.SubTotalItemSinIVA * v.sg), 0), 2) AS '% Desc. Prom.',
    cli.BonificacionGeneral                                      AS '% Bonif. Config.'
FROM Ventas v
JOIN comprobanteemitidoitems cei ON cei.idComprobanteEmitido = v.idComprobanteEmitido
LEFT JOIN clientes cli           ON cli.idCliente = v.idCliente
GROUP BY cli.idCliente, cli.RazonSocial, cli.BonificacionGeneral
HAVING `Descuento ($)` > 0
ORDER BY `Descuento ($)` DESC;
```

> Verificar contra datos reales que `SubTotalItemSinIVA` sea efectivamente el
> importe **antes** de la bonificación y `TotalItemSinIVA` el de **después**.
> El esquema no lo documenta.

---

## 3.17 🥉 Tasa de anulación (control interno)

```sql
SELECT DATE_FORMAT(FechaComprobante, '%Y-%m')                   AS 'Mes',
       COUNT(*)                                                 AS 'Emitidos',
       SUM(Anulado)                                             AS 'Anulados',
       ROUND(100 * SUM(Anulado) / COUNT(*), 2)                  AS '% Anulación',
       SUM(CASE WHEN Anulado = 1 THEN TotalOperacion ELSE 0 END) AS 'Monto Anulado'
FROM comprobanteemitido
WHERE idEmpresa = :company_id
GROUP BY `Mes`
ORDER BY `Mes` DESC;
```

Un salto en la tasa de anulación suele indicar error de capacitación o, en el
peor caso, faltante de caja.

---

## 3.18 Complementos menores, todos con datos ya disponibles

| Informe | Campos | Utilidad |
|---|---|---|
| **Artículos clase A sin stock** | ABC (§3.2) + `ExistenciaActual = 0` | Venta que se pierde hoy |
| **Cruce ABC × SLOB** | §3.2 + SLOB existente | Clase C + sin rotación = liquidar |
| **Envases adeudados** | `clientes.EnvasesAdeudados`, `TotalEnvases` | Recuperar envases prestados |
| **Venta por peso / granel** | `articulos.EsVentaPorPeso` | Arena, cal, cemento a granel |
| **Artículos sin código de barras** | `CodigoDeBarras IS NULL` | Calidad de datos, previo a lector |
| **Vencimiento de CAE / certificado AFIP** | `empresas.AFIP_CertificadoVencimiento` | Alerta antes de que se corte la facturación |
| **Comprobantes impagos por punto de venta** | `idPuntoVenta`, `Pagado` | Control por sucursal/mostrador |
| **Cross-sell faltante** | Extensión de la canasta existente | "Vendió cemento y no hierro" |

---

# 4. Índices SQL recomendados

InnoDB crea índices automáticamente para las FK, así que
`comprobanteemitidoitems.idComprobanteEmitido` y `.idArticulo` ya están
cubiertos. Lo que falta y explica la lentitud actual:

```sql
-- El filtro que usan TODAS las consultas de venta. Hoy hace full scan.
CREATE INDEX ix_ce_empresa_fecha
    ON comprobanteemitido (idEmpresa, Anulado, FechaComprobante);

-- Cuenta corriente y análisis por cliente.
CREATE INDEX ix_ce_cliente_fecha
    ON comprobanteemitido (idCliente, FechaComprobante);

-- Listados de artículos y stock.
CREATE INDEX ix_art_empresa_activo
    ON articulos (idEmpresa, Activo);

-- SLOB / inventario obsoleto.
CREATE INDEX ix_art_ultima_venta
    ON articulos (idEmpresa, FechaUltimaVenta);

-- Compras (§3.10).
CREATE INDEX ix_cc_empresa_fecha
    ON comprobantescompras (IdEmpresa, FechaComprobante);

-- Caja (§3.9).
CREATE INDEX ix_mc_empresa_fecha
    ON movimientoscaja (IdEmpresa, FechaMovimiento);
```

⚠️ Estos `CREATE INDEX` corren sobre la base **del cliente**. Coordinar con quien
administre las instalaciones; no los ejecutes desde esta app.

---

# 5. Plan de trabajo sugerido

**Etapa 0 — poner el repo en condiciones**
Inicializar git contra el remoto de GitHub, agregar `.gitignore`, sacar
`__pycache__` y `Grafico.rar`, crear `requirements.txt`. Commit checkpoint antes
de tocar código (lo pide `ACTUALIZACIONES.md`).

**Etapa 1 — corregir los números (§1.1, §1.2, §1.3, §1.11)**
Nada más importa si los totales están mal. Es un cambio acotado: un helper de
signo/filtro y aplicarlo a ~11 consultas. Validar contra un reporte contable
conocido de una instalación real antes de publicar.

**Etapa 2 — estabilidad (§1.4, §1.5, §1.6, §1.7, §1.12, §1.13, §2.1)**
Rol de admin, threading real, crash del `QMessageBox` fuera del hilo GUI, RFM
robusto, y las credenciales fuera de los logs.

**Etapa 3 — pulido (§1.8 a §1.29, §2.2 a §2.7)**
Persistencia de settings, fugas de memoria, código muerto, logging.

**Etapa 4 — build e integración MINIhub (§2.8)**
`.spec` onedir + `ModuloEstadisticasLeontis.exe`, sincronizar `nucleo.py` /
`ftp_config.py` / `ui_updater.py` desde `MINIhub/RECURSOS/MODULOS/`, publicar con
`python publicar_app.py --app ModuloEstadisticasLeontis`.

**Etapa 5 — estadísticas nuevas**
Por valor entregado: §3.1 margen → §3.2 ABC → §3.3 sugerido de compra →
§3.4 aging → §3.5 inflación → el resto.

---

# 6. Bitácora

## 0.1.0 — primera publicación

Aplicadas las etapas 0 a 4 y los cuatro informes de §3.1 a §3.4.

## 0.1.1 — el login roto

**Qué pasó.** La §2.1 decía "debe ser `https://`" y en 0.1.0 se cambió el esquema
por defecto. **El servidor no habla TLS en el puerto 65081**, así que el login
dejó de funcionar para todos. Se detectó recién con la app ya publicada.

**Por qué se escapó.** El cambio se hizo porque el problema de seguridad es real,
pero no se probó contra el servidor, que era lo único que podía confirmarlo. Que
`Modulo Servicios` y el importador desde Eslaboon usaran los dos `http://` era la
pista de que el `https://` no estaba disponible, y estaba a un `grep` de
distancia.

**La lección, para la próxima.** Un cambio de endpoint, esquema o credenciales
**se prueba contra el servidor real antes de publicar**, aunque el arreglo sea
obviamente correcto en abstracto. Y cuando hay varias apps hablando con la misma
API, lo que hacen las otras es evidencia sobre lo que el servidor soporta.

```bash
# Lo que había que correr antes de tocar el esquema:
python -c "import requests; print(requests.post('https://sistema.leontis.com.ar:65081/login', json={}, timeout=10).status_code)"
```

---

# 7. Segunda auditoría (2026-09-25)

Alcance: versión 0.1.2, contrastada esta vez **contra el código de Leontis**
(clon local de solo lectura en `LEONTIS/LEONTIS ERP`), no solo contra el
esquema. La primera auditoría dedujo el significado de los tipos de comprobante
y de los campos de pago mirando esta misma app; leyendo el ERP que los escribe,
varias de esas deducciones resultan equivocadas.

**Estado:** §7.1 y §7.2 aplicadas el 2026-09-25 (con `-81` como venta, confirmado
por el usuario, y `-88` también, igual que la Caja Diaria del ERP). El resto,
pendiente.

## 7.1 🔴 Los tipos de comprobante están mal mapeados

Fuente de verdad: `BizSuite.Logic/Entidades/NoPersistidas/TiposDeComprobante.json`.

| id | Leontis dice | La app asume | Efecto hoy |
|---|---|---|---|
| 11 / 13 | **FC C / NC C** | "FC M / NC M" | Solo etiqueta mal en el Excel de cta. cte. |
| 2 / 7 / 12 | ND A / B / C | — | Suman: correcto |
| 15 | RC C (recibo C, en libro IVA) | — | Suma como venta. **A confirmar** si el cliente lo usa como factura o como recibo |
| 51 | FC M | — | Suma: correcto, pero sin etiqueta en el Excel |
| -81 | **CO X: venta sin factura** | "comprobante interno, no es venta" | **Toda la venta en X queda fuera de todos los informes** |
| -83 | **NC X: nota de crédito X** (`EsCredito`) | "recibo de cobranza" | Se excluye; debería restar |
| -84 | **PRESUPUESTO** | — | **Se cuenta como venta** en todos los informes |
| -88 | REMITO X | — | Se cuenta como venta. **A confirmar** si después se factura (doble conteo) |

El ERP confirma el tratamiento del presupuesto: no mueve stock
(`lgComprobantes.cs:61`) y su propia Caja Diaria lo excluye (`lgVentas.cs:85`).

**Corrección propuesta:** derivar signo y filtro del JSON de Leontis (copiado a
`Recursos/Datos`) en vez de listas a mano: `EsCredito` → −1, `-84` fuera,
y un check *"Incluir comprobantes X"* (default: sí) para el que quiera ver solo
lo fiscal. Antes de publicar, en una base real:

```sql
SELECT idTipoComprobante, COUNT(*), SUM(TotalOperacion)
FROM comprobanteemitido WHERE Anulado = 0 GROUP BY 1;
```

El aging y el detalle de cta. cte. también toman presupuestos como deuda
abierta, y el ERP los suma al `SaldoActual` del cliente (`lgComprobantes.cs:90`):
puede ser que el saldo mismo esté inflado. Eso es de Leontis, no de acá, pero
conviene saberlo antes de leer el informe.

## 7.2 🔴 El desglose por medio de pago mide otra cosa

En Leontis, al emitir al **contado** `PagoEfectivo = TotalComprobante` sea cual
sea el medio (`frmEmitirComprobantes.cs:486` y `:535`); el medio real va en
`IdMedioDePago` (1 Efectivo, 2 Posnet, 3 Cheques, **4 Mercado Pago**, 255 Otros —
enum en `ComprobanteEmitido.cs:11`). En **cuenta corriente**
`PagoEfectivo = seña` e `IdMedioDePago = NULL`.

Con eso, la partición de §1.2 queda así:

- **"Efectivo"** = todo lo cobrado al contado (efectivo + posnet + Mercado Pago…).
- **"Tarjeta"** ≈ 0 siempre (el resto de una venta contado es cero).
- **"Otros"** = en realidad es **cuenta corriente**.
- **Mercado Pago no aparece** como medio de pago.

Y no coincide con la Caja Diaria del ERP, que suma `TotalOperacion` por
`IdMedioDePago` (`frmCajaDiaria.cs:55-59`): el dueño compara las dos pantallas y
ve números distintos. **Corrección:** la misma definición que el ERP, con cinco
medios + "Cuenta Corriente", aplicada también al KPI de 7 días.

## 7.3 🟠 Bugs nuevos

| # | Dónde | Qué pasa |
|---|---|---|
| 7.3.1 | `statistics_generator._get_date_filter` | `>= CURDATE() - N DAY AND <= CURDATE()` son **N+1 días**. "Últimas 24 horas" trae ayer y hoy; "30 días" son 31. La venta diaria del sugerido de compra sale inflada (N+1)/N (+14% con 7 días). |
| 7.3.2 | `_quintil` | `rank(method='first')` desempata **por orden de fila**: dos clientes con 1 compra cada uno pueden quedar con F=1 y F=3. Donde la mayoría compró una vez, el RFM es casi aleatorio. |
| 7.3.3 | `get_rfm_analysis_data` | Los segmentos se superponen (Nuevos ⊂ Potenciales, Prometedores ⊂ Leales, Necesitan Atención ∩ Leales) y hay huecos (R=3, F=1 no cae en ninguno). El gráfico suma más clientes de los que hay. Hace falta una sola columna `Segmento` con reglas excluyentes. |
| 7.3.4 | `dashboard_manager.check_and_fetch_external_data` | QSettings en el registro devuelve los `float` como `str` (verificado: `'1234.5' str`). El `isinstance(..., (int, float))` falla siempre: **el caché de 24 h nunca se usa** y cada arranque pega a las 4 APIs. |
| 7.3.5 | `main.export_to_pdf` / `export_to_excel` | "Margen Bruto" con *Todos (sin gráfico)* **igual intenta graficar**: el filtro es `"top" in report_name`. Con miles de artículos, `fig_height = n*0.5+2` pide una figura de miles de pulgadas. |
| 7.3.6 | Excel de cta. cte. | Formato por **letra** con las columnas corridas: en el detalle `K` es **DNI** (sale con `$`) y el saldo total del cliente (`M`) queda sin formato; en "Solo totales" se formatea `E` (Teléfono) y no `F` (Saldo). |
| 7.3.7 | Excel del RFM | `F` (Frecuencia) sale como moneda y `G` (Monetario) no. El formato condicional busca `"Si"`/`"No"` pero las columnas son booleanas: nunca pinta. Se exporta `idCliente` crudo. |
| 7.3.8 | Excel del sugerido de compra | `J:K` como moneda: `K` es la fecha de última compra, e `I` (costo unitario) queda sin formato. |
| 7.3.9 | `get_customer_debt_for_excel` | "Top N comprobantes adeudados" ordena por `TotalOperacion - TotalPagos` sin signo: una **nota de crédito** sin aplicar aparece como "el comprobante más adeudado". |
| 7.3.10 | `generate_statistics` | El caché de §2.4 solo cubre el detalle: margen, ABC y RFM se calculan **dos veces** por exportación (gráfico + detalle). |
| 7.3.11 | `MainWindow` | Título fijo "v4.2"; la versión real es `APP_VERSION = 0.1.2`. |
| 7.3.12 | Combos de período | No hay 180 ni 365 días: ABC, RFM y sugerido de compra solo eligen entre 90 días o "Todo el historial" (y con inflación el historial completo pesa casi solo lo último). |

## 7.4 🟡 A validar contra una base real

- **Costo:** el ERP arma el precio sobre `PrecioCosto * (1 - DescuentoProveedor/100)`
  (`DtoListaPrecios.cs:96`), pero su propia `Rentabilidad` usa `PrecioCosto`
  crudo, igual que esta app. Hay que decidir cuál es el costo "real".
- **Artículos en dólares** (`idMoneda = 2`): la conversión está comentada en el
  ERP. Si hay artículos con costo en USD, capital inmovilizado, SLOB y sugerido
  de compra los suman como si fueran pesos.
- **Margen:** `comprobanteemitidoitems.Rentabilidad` se guarda al emitir con el
  costo de ese momento (`ItemComprobante.cs:74`). Usarla en vez de
  `Cantidad * PrecioCosto de hoy` elimina la distorsión por inflación que la
  tarjeta advierte en pantalla. Solo se desvía si alguien usó "Recalcular
  rentabilidad" en el ERP, que toma el costo actual.

## 7.5 Rendimiento

1. **Canasta:** en MariaDB un CTE referenciado varias veces se evalúa en cada
   referencia, así que `ItemPairs` (el self-join caro) corre hasta 4 veces.
   Traer `(idComprobante, idArticulo)` de los comprobantes válidos y contar pares
   en pandas es mucho más barato, y en modo manual permite filtrar primero.
2. **Doble cálculo por exportación** (7.3.10): caché por `(informe, parámetros)`
   que cubra también los gráficos.
3. **Informes en el hilo de la GUI** (pendiente de §2.3): `ReportWorker` con
   barra de progreso y botones deshabilitados. Hoy `status_bar_message` llama a
   `processEvents()` y se puede lanzar una segunda exportación en medio de la
   primera.
4. **Modal de artículos:** 20.000 `QListWidgetItem` armados con `iterrows()` y
   filtrados de a uno. `QTableView` + `QSortFilterProxyModel` es instantáneo, y
   la lista puede cargarse al abrir el modal, no al iniciar sesión.
5. **Caché del panel roto** (7.3.4): 4 llamadas HTTP en cada arranque.
6. Los índices de §4 siguen siendo lo que más impacta en bases grandes.

## 7.6 Estadísticas nuevas (además de las de §3 que faltan)

1. **Caja por medio de pago igual a la del ERP** (el arreglo de 7.2), con Mercado
   Pago y Cuenta Corriente separados, y su evolución.
2. **Comparativo contra el período anterior y el mismo período del año pasado**,
   nominal y **real** (deflactado por IPC). La app ya baja el IPC pero se queda
   con el último mes; guardar la serie completa alcanza.
3. **Días de cobranza por cliente (DSO):** `FechaPago - FechaComprobante` en
   cuenta corriente. Cuánto tarda en pagar cada cliente, no solo cuánto debe.
4. **Presupuestos:** cantidad, monto y **tasa de conversión** (presupuesto que
   terminó en venta al mismo cliente dentro de N días), y la lista de los
   grandes sin convertir para llamar. Los datos ya están (`-84`).
5. **Precios atrasados contra la inflación:** `FechaUltimaActualizacionPrecio` +
   IPC acumulado desde esa fecha = "este precio perdió ~X% real". Con stock y
   rotación, dice qué remarcar primero. La marcación correcta es la del ERP (con
   `DescuentoProveedor`), no la de §3.6.
6. **Quiebres de stock con venta perdida estimada:** artículos A/B con stock ≤ 0
   × venta diaria.
7. **Clientes nuevos y retención por mes** (cohortes por primera compra).
8. **Ventas por punto de venta** (`puntosdeventa.Descripcion`).

## 7.7 Mejoras visuales y de uso

- **Vista previa dentro de la app:** el `MatplotlibWidget` ya existe y solo se
  usa para exportar. Un botón "Ver" por tarjeta con el gráfico y la tabla
  (`QTableView` sobre el DataFrame) evita exportar para mirar.
- **Panel de control con contexto:** cada KPI con su variación contra el período
  anterior (▲▼ %) y una mini-serie de 30 días. Sumar los KPIs escritos y no
  mostrados (`get_kpi_slob_value`, `get_kpi_rfm_risk_count`) y "% de deuda con
  más de 90 días".
- **El ✏️ no dice "incluir en la exportación":** un lápiz se lee como "editar".
  Un interruptor o check con leyenda.
- **Un selector de período por pestaña** (o global) con rangos de negocio: este
  mes, mes anterior, año en curso, 180/365 días y desde/hasta con calendario.
- **Formato argentino** en gráficos y PDF: `$ 1.234.567` y meses en castellano.
  Hoy sale `$1,234,567` y el eje dice `15-Sep`, sin año aunque el rango abarque
  varios.
- **Gráficos:** barras de un color de la marca (#312093) en vez de gris/azul
  alternado; ventas diarias con los días sin venta en cero (hoy une el sábado
  con el lunes), media móvil de 7 días y sin marcadores con cientos de puntos.
- **PDF:** portada con empresa, fecha, período y resumen de KPIs; números de
  página; tablas con números formateados y alineados a la derecha.
- **Excel:** formato por **nombre de columna** en vez de por letra (arregla
  7.3.6 a 7.3.8 de raíz), paneles inmovilizados, autofiltro y fila de totales.
- **Después de exportar:** el cartel "¿Exportar otro / Cerrar el programa?"
  cansa. Un aviso no bloqueante con "Abrir archivo" y "Abrir carpeta".
