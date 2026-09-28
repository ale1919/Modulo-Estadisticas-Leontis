# Pruebas del Módulo de Estadísticas

```bash
python pruebas/correr_todas.py            # todas
python pruebas/correr_todas.py --rapidas  # las que no necesitan MariaDB
python pruebas/test_ventas_por_tipo.py    # una sola
```

Método: `PROYECTOS 8-10/DOCUMENTACION/PRUEBAS.md`. Las baterías solo crecen.

## Qué necesitan

Casi todas necesitan el **MariaDB local** de la máquina de desarrollo (el de la
copia de producción de Leontis, `LEONTIS ERP/_MODERNIZACION/ENTORNO-LOCAL.md`,
A-3). La conexión sale de `C:\leontis-prueba\cliente.cnf` o de la variable
`ESTADISTICAS_PRUEBA_CNF`: **ninguna contraseña en el repo**.

| Prueba | Base | Qué mira |
|---|---|---|
| `test_ventas_por_tipo.py` | sintética, **se crea y se borra** (`est_prueba_<pid>`) | Cada tipo de comprobante × anulado × cada estado de medio de pago, en cada informe de venta, contra un oráculo propio. Y la tabla de tipos contra el JSON del ERP |
| `test_base_real.py` | `leontis_prueba`, **solo lectura** | Totales y medios de pago de las empresas más grandes contra un oráculo en pandas sobre las filas crudas |
| `test_periodos.py` | sintética | Una venta por día durante 400 días: cada período (hoy, 2, 7… 365, todo) trae exactamente N días en cada informe y en los KPI |
| `test_rfm_base.py` | sintética | Frecuencia y recencia sin notas de crédito, un segmento por cliente, conteos que suman el total, empresa sin ventas |
| `test_rfm.py` | ninguna (rápida) | Puntaje por quintiles: empates iguales, monótono, 1 a 5, 300 series al azar con semilla fija; los 25 casos de R×F contra una tabla a mano |
| `test_formatos.py` | ninguna (rápida) | El formato de Excel de TODAS las columnas que devuelven los informes, por nombre; formato argentino de pesos y números |
| `test_dashboard_cache.py` | ninguna (rápida), QSettings real | El caché de 24 h del panel con lo que de verdad devuelve el registro de Windows (los `float` vuelven como texto) |

La base sintética se arma con el DDL de `PROYECTOS 8-10/SCHEMAS/LEONTIS schema.sql`.

## Qué NO cubren

- La interfaz (PySide6): se prueba lo que calcula, no lo que dibuja.
- La seña de una venta en cuenta corriente: el comprobante entero va a "Cuenta
  Corriente" aunque haya entrado una parte en efectivo. Es a propósito: el ERP
  pisa `PagoEfectivo` al cobrar, así que la seña original no se puede recuperar.

### Mutantes que sobreviven, y por qué son equivalentes

Medido con `HERRAMIENTAS/mutar` el 2026-09-25 sobre las tablas de tipos y medios
de pago de `statistics_generator.py`: **86 de 90** detectados. Los 4 que quedan
no cambian ningún resultado:

- `SIGNO_VENTA(alias='ce')` y `FILTRO_VENTA(alias='ce')` con el default vacío:
  todos los llamadores pasan el alias explícito.
- El `'.'` de `MEDIO_DE_PAGO_SQL`: hoy solo se llama sin alias.
- El espacio entre ramas de `NOMBRE_TIPO_SQL`: `'FC A'WHEN` es SQL válido.

Tanda 2 (2026-09-28):

- `formatos.py`: **148 de 150**. Los 2 que quedan son los espacios de
  `" % " in f" {n} "`; sacarlos solo cambia el caso de un `%` al principio o al
  final, que ya atrapan `startswith` y `endswith`.
- `_quintil` / `_segmento`: los que quedan son `clip(1, 5)` → `clip(1, 6)`
  (el percentil nunca pasa de 1, así que el puntaje nunca pasa de 5).
