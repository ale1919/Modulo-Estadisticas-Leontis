"""El RFM contra la base sintética (AUDITORIA.md §7.3.3).

- Frecuencia y recencia cuentan solo compras: una nota de crédito no es una
  visita ni hace reciente a un cliente. El monto sí las descuenta.
- Cada cliente cae en un solo segmento y los conteos suman la cantidad de
  clientes.
- Sin datos: tabla vacía y los siete segmentos en cero (el gráfico no se rompe).
"""

from entorno import BaseSintetica, Checks, dias_atras

C = Checks("RFM contra la base")

with BaseSintetica() as B:
    B.empresa(1)
    B.empresa(2)
    B.articulo(1, 1, "Art")
    B.cliente(1, 1, "CONSUMIDOR FINAL", "0")
    B.cliente(2, 1, "Con devoluciones", "A")
    B.cliente(3, 1, "Solo notas de crédito", "B")
    B.cliente(4, 1, "Devolvió todo", "C")
    B.cliente(5, 1, "Sin código", None)
    k = 0

    def comp(cli, tipo, total, dias):
        global k
        k += 1
        B.comprobante(k, 1, tipo, cli, total, dias_atras(dias), medio=1,
                      items=[(1, 1, total, total / 1.21, 0)])

    # Cliente 2: tres compras (hace 10, 20 y 30 días) y dos NC más recientes.
    for d in (10, 20, 30):
        comp(2, 6, 1000, d)
    comp(2, 8, 200, 2)
    comp(2, -83, 100, 1)
    # Cliente 3: solo NC. Cliente 4: compró y devolvió todo.
    comp(3, 8, 500, 5)
    comp(4, 6, 700, 40)
    comp(4, 3, 700, 39)
    # Consumidor final y un cliente sin código.
    comp(1, 6, 9999, 1)
    comp(5, -81, 300, 100)
    # Presupuesto: no es compra.
    comp(5, -84, 50000, 0)
    # Más clientes, para que los quintiles tengan con qué comparar.
    for c in range(10, 30):
        B.cliente(c, 1, f"Cliente {c}", f"K{c}")
        for d in range(c % 4 + 1):
            comp(c, 6, 100 * c, c + d)

    sg = B.sg
    df, cuentas = sg.get_rfm_analysis_data(1)
    filas = df.set_index("Cliente")

    C.igual(int(filas.loc["Con devoluciones", "Frecuencia"]), 3, "las NC no suman frecuencia")
    C.igual(int(filas.loc["Con devoluciones", "Recencia"]), 10,
            "la recencia es la de la última compra, no la de la última NC")
    C.igual(float(filas.loc["Con devoluciones", "Monetario"]), 2700.0,
            "el monto descuenta las NC")
    C.check("Solo notas de crédito" not in filas.index, "sin compras: afuera")
    C.check("Devolvió todo" not in filas.index, "monto cero: afuera")
    C.check("CONSUMIDOR FINAL" not in filas.index, "consumidor final: afuera")
    C.check("Sin código" in filas.index, "cliente sin código: adentro")
    C.igual(float(filas.loc["Sin código", "Monetario"]), 300.0, "el presupuesto no suma")
    C.igual(int(filas.loc["Sin código", "Frecuencia"]), 1, "el presupuesto no es compra")

    C.igual(int(cuentas.sum()), len(df), "los segmentos suman la cantidad de clientes")
    C.igual(list(cuentas.index), [n for n, _ in sg.SEGMENTOS_RFM], "todos los segmentos, en orden")
    C.check(df["Segmento"].notna().all(), "todo cliente tiene segmento")
    C.check("idCliente" not in df.columns, "no se exporta el id interno")
    for _, fila in df.iterrows():
        C.igual(fila["Segmento"], sg._segmento(fila["R_Score"], fila["F_Score"]),
                f"segmento de {fila['Cliente']}")
    orden = [dict((n, i) for i, (n, _) in enumerate(sg.SEGMENTOS_RFM))[s]
             for s in df["Segmento"]]
    C.check(orden == sorted(orden), "la tabla sale ordenada por segmento")

    C.igual(sg.get_kpi_rfm_risk_count(1), int(cuentas["En Riesgo"] + cuentas["Perdidos"]),
            "KPI de clientes en riesgo")

    vacio, cuentas_vacias = sg.get_rfm_analysis_data(2)
    C.check(vacio.empty, "empresa sin ventas: tabla vacía")
    C.igual(int(cuentas_vacias.sum()), 0, "empresa sin ventas: conteos en cero")
    C.igual(len(cuentas_vacias), len(sg.SEGMENTOS_RFM), "empresa sin ventas: los 7 segmentos")
    C.igual(sg.get_kpi_rfm_risk_count(2), 0, "empresa sin ventas: KPI en cero")
    C.check(B.db.last_error is None, f"ninguna consulta falló ({B.db.last_error})")

C.cerrar()
