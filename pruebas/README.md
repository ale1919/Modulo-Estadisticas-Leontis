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
