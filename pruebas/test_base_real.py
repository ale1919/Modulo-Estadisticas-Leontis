"""Los informes de venta contra la copia local de producción (`leontis_prueba`).

**Solo lectura.** La base sintética de `test_ventas_por_tipo.py` barre cada caso
a propósito; esta mira lo que la sintética no puede inventar: los datos como los
dejó el ERP de verdad, con sus NULL, sus cobranzas y sus empresas que no piden
el medio de pago.

El oráculo baja las filas crudas y hace la cuenta en pandas, con su propia
tabla de tipos, sin usar nada del generador.

Necesita el MariaDB local con `leontis_prueba` (ver `LEONTIS ERP/_MODERNIZACION/
ENTORNO-LOCAL.md`, A-3). Sin eso falla: una corrida sin evidencia no corrió.
"""

import os

import pandas as pd
from sqlalchemy import text

from entorno import HOY, Checks, generador, motor

C = Checks("base real (leontis_prueba)")
BASE = os.environ.get("ESTADISTICAS_BASE_REAL", "leontis_prueba")

NOTAS_CREDITO = {3, 8, 13, -83}
NO_VENTA = {-84}


def medio(fila):
    m = fila.IdMedioDePago
    if pd.notna(m):
        return {1: "Efectivo", 2: "Tarjeta", 3: "Cheque", 4: "Mercado Pago"}.get(int(m), "Otros")
    if fila.Pagado == 1 and pd.notna(fila.FechaPago) and fila.FechaPago == fila.FechaComprobante:
        return "Efectivo"
    return "Cuenta Corriente"


engine = motor(BASE)
sg, db = generador(engine)

with engine.connect() as c:
    empresas = pd.read_sql(text("""
        SELECT idEmpresa, COUNT(*) n, SUM(IdMedioDePago IS NULL) nulos
        FROM comprobanteemitido GROUP BY idEmpresa ORDER BY n DESC"""), c)

# Las tres más grandes y la más grande de las que no piden el medio de pago.
elegidas = list(empresas["idEmpresa"].head(3))
sin_medio = empresas[empresas["nulos"] == empresas["n"]]
if not sin_medio.empty:
    elegidas.append(int(sin_medio.iloc[0]["idEmpresa"]))
C.check(len(elegidas) >= 3, f"hay empresas para mirar ({elegidas})")

for emp in elegidas:
    emp = int(emp)
    with engine.connect() as c:
        crudo = pd.read_sql(text("""
            SELECT idTipoComprobante, Anulado, IdMedioDePago, Pagado, FechaPago,
                   FechaComprobante, TotalOperacion
            FROM comprobanteemitido
            WHERE idEmpresa = :e AND FechaComprobante <= CURDATE()"""), c, params={"e": emp})

    v = crudo[(crudo["Anulado"] == 0) & (~crudo["idTipoComprobante"].isin(NO_VENTA))].copy()
    v["signo"] = v["idTipoComprobante"].map(lambda t: -1 if t in NOTAS_CREDITO else 1)
    v["importe"] = v["TotalOperacion"].astype(float) * v["signo"]
    v["medio"] = v.apply(medio, axis=1)
    total = float(v["importe"].sum())
    por_medio = v.groupby("medio")["importe"].sum()

    df = sg.get_sales_over_time(emp, -1)
    C.igual(float(df["Total Ventas ($)"].sum()), total, f"empresa {emp}: ventas por día, total",
            tolerancia=0.05)

    medios = ["Efectivo", "Tarjeta", "Cheque", "Mercado Pago", "Otros", "Cuenta Corriente"]
    df = sg.get_sales_by_day_for_excel(emp, -1, medios)
    C.igual(float(df["Total"].sum()), total, f"empresa {emp}: excel, total", tolerancia=0.05)
    C.igual(float(df[medios].sum().sum()), total,
            f"empresa {emp}: los medios suman el total", tolerancia=0.05)
    for m in medios:
        C.igual(float(df[m].sum()), float(por_medio.get(m, 0.0)),
                f"empresa {emp}: {m}", tolerancia=0.05)

    # El presupuesto existe en la base y no está en el total.
    presup = crudo[(crudo["idTipoComprobante"] == -84) & (crudo["Anulado"] == 0)]
    if not presup.empty:
        C.check(abs(total + float(presup["TotalOperacion"].sum())
                    - float(df["Total"].sum())) > 1,
                f"empresa {emp}: los presupuestos no suman")

    ultimos30 = v[pd.to_datetime(v["FechaComprobante"]) >=
                  pd.Timestamp(HOY) - pd.Timedelta(days=29)]
    C.igual(sg.get_kpi_total_sales_last_30_days(emp), float(ultimos30["importe"].sum()),
            f"empresa {emp}: KPI 30 días", tolerancia=0.05)

C.check(db.last_error is None, f"ninguna consulta falló ({db.last_error})")
engine.dispose()
C.cerrar()
