""""Últimos N días" son N días contando hoy, en todos los informes (AUDITORIA.md §7.3.1).

Una venta por día durante 400 días, con importe distinto cada día, más una con
fecha de mañana. Para cada período, cada informe tiene que sumar exactamente los
días que corresponden: ni uno más (el bug era N+1) ni uno menos.
"""

from entorno import BaseSintetica, Checks, dias_atras

C = Checks("períodos")

DIAS = 400
PERIODOS = [1, 2, 7, 15, 30, 60, 90, 180, 365, -1]


def importe(offset):
    return 100 + offset          # distinto cada día: un día de más se nota


with BaseSintetica() as B:
    B.empresa(1)
    B.cliente(10, 1, "Cliente", "C1")
    B.cliente(11, 1, "Otro", "C2")
    B.articulo(20, 1, "Tornillo", costo=10)
    B.articulo(21, 1, "Tuerca", costo=10)
    for offset in range(-1, DIAS):           # -1 = mañana
        total = importe(offset)
        # Dos ítems por comprobante para que la canasta tenga pares.
        B.comprobante(1000 + offset, 1, 6, 10, total, dias_atras(offset), medio=1,
                      items=[(20, 1, total, round(total / 1.21, 2), 0),
                             (21, 1, 0, 0, 0)])

    sg = B.sg

    def esperado(n):
        dias = range(0, DIAS) if n == -1 else range(0, max(n, 1))
        return sum(importe(d) for d in dias), len(dias)

    for n in PERIODOS:
        total, cantidad = esperado(n)
        etiqueta = "todo" if n == -1 else f"{n} días"

        df = sg.get_sales_over_time(1, n)
        C.igual(len(df), cantidad, f"{etiqueta}: días en ventas por día")
        C.igual(float(df["Total Ventas ($)"].sum()), total, f"{etiqueta}: ventas por día")

        df = sg.get_sales_by_day_for_excel(1, n, ["Efectivo"])
        C.igual(float(df["Total"].sum()), total, f"{etiqueta}: excel de ventas")

        df = sg.get_sales_by_payment_method_for_chart(1, n, ["Efectivo"])
        C.igual(float(df["Efectivo"].sum()), total, f"{etiqueta}: gráfico por medio")

        df = sg.get_top_articles_by_value(1, -1, n)
        C.igual(float(df["Total Vendido ($)"].sum()), total, f"{etiqueta}: top artículos $")

        df = sg.get_top_articles_by_quantity(1, -1, n)
        cant = df.set_index("Articulo")["Cantidad Vendida"]
        C.igual(float(cant.get("Tornillo", 0)), cantidad, f"{etiqueta}: top artículos cantidad")
        C.igual(float(cant.get("Tuerca", 0)), cantidad, f"{etiqueta}: la tuerca, sin importe")

        df = sg.get_top_customers_by_billing(1, -1, True, n)
        C.igual(float(df["Total Facturado ($)"].sum()), total, f"{etiqueta}: top clientes")

        df = sg.get_margin_by_article(1, -1, n)
        C.igual(float(df["Unidades"].sum()), cantidad, f"{etiqueta}: margen, unidades")

        df = sg.get_abc_analysis(1, n)
        C.igual(float(df["Unidades"].sum()), cantidad, f"{etiqueta}: ABC, unidades")

        df, _ = sg.get_rfm_analysis_data(1, n)
        C.igual(float(df["Monetario"].sum()), total, f"{etiqueta}: RFM monetario")

        df = sg.get_market_basket_analysis(1, n, 10, -1)
        vistos = df.set_index("Descripción")["Veces Vendidos Juntos"]
        C.igual(int(vistos.get("Tornillo", 0)), cantidad, f"{etiqueta}: canasta")

        # Una unidad por día: la venta diaria tiene que dar exactamente 1.
        df = sg.get_purchase_suggestion(1, n, 30)
        fila = df[df["Descripción"] == "Tornillo"]
        C.igual(float(fila["Venta Diaria"].iloc[0]) if len(fila) else None, 1.0,
                f"{etiqueta}: sugerido de compra, venta diaria")

    # Los KPIs del panel.
    total7, _ = esperado(7)
    total30, _ = esperado(30)
    kpi = sg.get_kpi_sales_by_payment_last_7_days(1)
    C.igual(float(kpi["Total"].sum()), total7, "KPI de 7 días")
    C.igual(sg.get_kpi_total_sales_last_30_days(1), total30, "KPI de 30 días")

    # "Todo el historial" para promedios: desde la primera venta hasta hoy.
    C.igual(sg._dias_efectivos(1, -1), DIAS, "días efectivos de todo el historial")
    C.igual(sg._dias_efectivos(1, 30), 30, "días efectivos de 30")
    C.igual(sg._dias_efectivos(2, -1), 365, "días efectivos sin ventas: 365")

    # Un período 0 (no lo ofrece ningún combo) se trata como "hoy", no revienta.
    df = sg.get_sales_over_time(1, 0)
    C.igual(float(df["Total Ventas ($)"].sum()), importe(0), "período 0 = hoy")
    C.check(B.db.last_error is None, f"ninguna consulta falló ({B.db.last_error})")

C.cerrar()
