"""Qué cuenta como venta y en qué medio de pago cae (AUDITORIA.md §7.1 y §7.2).

Barre, en una base sintética, cada tipo de comprobante de Leontis × anulado o no
× cada estado de medio de pago que el ERP puede dejar escrito, y compara cada
informe de venta contra un oráculo escrito acá, aparte del código.

Para poder ver cada tipo por separado, cada tipo le vende a su propio cliente, y
cada estado de pago vende su propio artículo: el total de ese cliente o de ese
artículo es exactamente lo que hizo ese tipo o ese estado.

Una segunda empresa con los mismos comprobantes tiene que no aparecer nunca.
"""

import json
from collections import defaultdict

from entorno import TIPOS_JSON_ERP, BaseSintetica, Checks, dias_atras

from Recursos.Modulos import statistics_generator as SG

C = Checks("ventas por tipo y medio de pago")

# -- El oráculo: lo que Leontis dice de cada tipo -------------------------- #
# (nombre corto, signo). None = no es venta. Escrito a mano a partir del JSON
# del ERP, a propósito sin importar nada de la app.
ORACULO_TIPOS = {
    1: ("FC A", 1), 2: ("ND A", 1), 3: ("NC A", -1),
    6: ("FC B", 1), 7: ("ND B", 1), 8: ("NC B", -1),
    11: ("FC C", 1), 12: ("ND C", 1), 13: ("NC C", -1),
    15: ("RC C", 1), 51: ("FC M", 1),
    -81: ("CO X", 1), -83: ("NC X", -1), -84: ("PRES", None), -88: ("RE X", 1),
}
# Un tipo que Leontis no declara hoy: se cuenta como venta, como antes.
TIPO_DESCONOCIDO = 99

# (nombre, kwargs de comprobante, medio esperado)
FECHA = dias_atras(3)
ESTADOS = [
    ("medio 1", dict(medio=1), "Efectivo"),
    ("medio 2", dict(medio=2), "Tarjeta"),
    ("medio 3", dict(medio=3), "Cheque"),
    ("medio 4", dict(medio=4), "Mercado Pago"),
    ("medio 255", dict(medio=255), "Otros"),
    ("medio 7 (no existe)", dict(medio=7), "Otros"),
    ("contado sin medio", dict(medio=None, pagado=1, fecha_pago="="), "Efectivo"),
    ("cta cte impaga", dict(medio=None, pagado=0, fecha_pago=None), "Cuenta Corriente"),
    ("cta cte cobrada otro día", dict(medio=None, pagado=1, fecha_pago=dias_atras(1)),
     "Cuenta Corriente"),
    ("cta cte con seña", dict(medio=None, pagado=0, fecha_pago="=", total_pagos=None,
                              pago_efectivo=None), "Cuenta Corriente"),
    ("pagado sin fecha de pago", dict(medio=None, pagado=1, fecha_pago=None),
     "Cuenta Corriente"),
]

# -- 1. La tabla de la app contra el JSON del ERP ------------------------- #

C.igual(SG._lista_sql((-84,)), "(-84)", "lista SQL de un elemento")
C.igual(SG._lista_sql((3, -83)), "(3, -83)", "lista SQL de dos")

for t, (nombre, signo) in ORACULO_TIPOS.items():
    C.check(t in SG.TIPOS_COMPROBANTE, f"tipo {t} declarado en la app")
    if t in SG.TIPOS_COMPROBANTE:
        C.igual(SG.TIPOS_COMPROBANTE[t][0], nombre, f"nombre del tipo {t}")
        C.igual(t in SG.TIPOS_NOTA_CREDITO, signo == -1, f"tipo {t} es nota de crédito")
        C.igual(t in SG.TIPOS_NO_VENTA, signo is None, f"tipo {t} no es venta")
C.igual(set(SG.TIPOS_COMPROBANTE), set(ORACULO_TIPOS), "la app no declara tipos de más")

if TIPOS_JSON_ERP.is_file():
    erp = json.loads(TIPOS_JSON_ERP.read_text(encoding="utf-8"))
    C.igual({x["idTipoComprobante"] for x in erp}, set(SG.TIPOS_COMPROBANTE),
            "los mismos tipos que el JSON del ERP")
    for x in erp:
        t = x["idTipoComprobante"]
        if t in SG.TIPOS_COMPROBANTE:
            C.igual(SG.TIPOS_COMPROBANTE[t], (x["NombreCorto"], x["EsCredito"]),
                    f"tipo {t} igual al ERP")
else:
    print(f"aviso  no está {TIPOS_JSON_ERP}: no se compara contra el ERP")

# -- 2. La base sintética -------------------------------------------------- #

with BaseSintetica() as B:
    filas = []          # lo insertado en la empresa 1, para el oráculo
    tipos = list(ORACULO_TIPOS) + [TIPO_DESCONOCIDO]
    k = 0
    for emp, off in ((1, 0), (2, 100000)):
        B.empresa(emp)
        # Los de la otra empresa llevan "E2 " adelante: si se filtran, se ven.
        pre = "" if emp == 1 else "E2 "
        B.cliente(off + 1, emp, f"{pre}CONSUMIDOR FINAL", "0")
        for i, t in enumerate(tipos):
            B.cliente(off + 100 + i, emp, f"{pre}Cliente tipo {t}", f"C{i}")
        for j, _ in enumerate(ESTADOS):
            B.articulo(off + 500 + j, emp, f"{pre}Articulo estado {j}")

        for i, t in enumerate(tipos):
            for j, (_, kwargs, medio) in enumerate(ESTADOS):
                for anulado in (0, 1):
                    k += 1
                    total = 1000 + 13 * k
                    cantidad = k % 5 + 1
                    sin_iva = round(total / 1.21, 2)
                    kw = dict(kwargs)
                    if kw.get("pago_efectivo", "x") is None:     # la seña
                        kw["pago_efectivo"] = round(total / 2, 2)
                        kw["total_pagos"] = round(total / 2, 2)
                    B.comprobante(off + k, emp, t, off + 100 + i, total, FECHA,
                                  anulado=anulado,
                                  items=[(off + 500 + j, cantidad, total, sin_iva, 0)],
                                  **kw)
                    if emp == 1:
                        filas.append(dict(tipo=t, cliente=100 + i, articulo=500 + j,
                                          medio=medio, anulado=anulado, total=total,
                                          cantidad=cantidad, sin_iva=sin_iva))
        # Unas ventas al consumidor final, para el check "incluir CF".
        for n in range(3):
            k += 1
            B.comprobante(off + k, emp, 6, off + 1, 500 + n, FECHA, medio=1,
                          items=[(off + 500, 1, 500 + n, round((500 + n) / 1.21, 2), 0)])
            if emp == 1:
                filas.append(dict(tipo=6, cliente=1, articulo=500, medio="Efectivo",
                                  anulado=0, total=500 + n, cantidad=1,
                                  sin_iva=round((500 + n) / 1.21, 2)))

    # -- el oráculo ------------------------------------------------------- #
    def signo(t):
        return ORACULO_TIPOS.get(t, ("?", 1))[1]

    validas = [f for f in filas if not f["anulado"] and signo(f["tipo"]) is not None]
    total = sum(f["total"] * signo(f["tipo"]) for f in validas)
    por_medio = defaultdict(float)
    por_cliente = defaultdict(float)
    por_articulo = defaultdict(float)
    cant_articulo = defaultdict(float)
    sin_iva_articulo = defaultdict(float)
    for f in validas:
        s = signo(f["tipo"])
        por_medio[f["medio"]] += f["total"] * s
        por_cliente[f["cliente"]] += f["total"] * s
        por_articulo[f["articulo"]] += f["total"] * s
        cant_articulo[f["articulo"]] += f["cantidad"] * s
        sin_iva_articulo[f["articulo"]] += f["sin_iva"] * s

    sg = B.sg

    # Ventas por día
    df = sg.get_sales_over_time(1, 7)
    C.igual(len(df), 1, "ventas por día: un solo día con datos")
    C.igual(float(df["Total Ventas ($)"].sum()), total, "ventas por día: total")

    df = sg.get_sales_by_day_for_excel(1, 7, list(SG.MEDIOS_DE_PAGO))
    C.igual(list(df.columns), ["Fecha", *SG.MEDIOS_DE_PAGO, "Total"], "excel ventas: columnas")
    C.igual(float(df["Total"].sum()), total, "excel ventas: total")
    C.igual(float(df[list(SG.MEDIOS_DE_PAGO)].sum().sum()), total,
            "excel ventas: los medios suman el total")
    for m in SG.MEDIOS_DE_PAGO:
        C.igual(float(df[m].sum()), por_medio[m], f"excel ventas: {m}")
        C.check(por_medio[m] != 0, f"el barrido ejercita el medio {m}")

    for m in SG.MEDIOS_DE_PAGO:
        dfm = sg.get_sales_by_payment_method_for_chart(1, 7, [m])
        C.igual(list(dfm.columns), [m], f"gráfico medio {m}: solo esa columna")
        C.igual(float(dfm[m].sum()), por_medio[m], f"gráfico medio {m}: importe")
    C.check(sg.get_sales_by_payment_method_for_chart(1, 7, []).empty,
            "gráfico sin medios elegidos: vacío")

    kpi = sg.get_kpi_sales_by_payment_last_7_days(1)
    kpi = dict(zip(kpi["MedioDePago"], kpi["Total"]))
    for m in SG.MEDIOS_DE_PAGO:
        C.igual(float(kpi.get(m, 0)), por_medio[m], f"KPI 7 días: {m}")
    C.igual(sg.get_kpi_total_sales_last_30_days(1), total, "KPI 30 días")

    # Artículos
    df = sg.get_top_articles_by_value(1, -1, 7)
    obtenido = dict(zip(df["Articulo"], df["Total Vendido ($)"]))
    for j, (nombre, _, _) in enumerate(ESTADOS):
        esperado = por_articulo[500 + j]
        clave = f"Articulo estado {j}"
        if esperado > 0:
            C.igual(float(obtenido.get(clave, 0)), esperado, f"top artículos $: {nombre}")
        else:
            C.check(clave not in obtenido, f"top artículos $: {nombre} no aparece (<= 0)")

    C.check(not any(str(k).startswith("E2") for k in obtenido),
            "top artículos: sin fugas de la otra empresa")

    df = sg.get_top_articles_by_quantity(1, -1, 7)
    obtenido = dict(zip(df["Articulo"], df["Cantidad Vendida"]))
    for j, (nombre, _, _) in enumerate(ESTADOS):
        esperado = cant_articulo[500 + j]
        if esperado > 0:
            C.igual(float(obtenido.get(f"Articulo estado {j}", 0)), esperado,
                    f"top artículos cant.: {nombre}")

    df = sg.get_top_articles_for_excel(1, -1, 7)
    C.igual(float(df["Total Vendido"].sum()), sum(por_articulo.values()),
            "excel artículos: total")

    df = sg.get_margin_by_article(1, -1, 7)
    obtenido = dict(zip(df["Descripción"], df["Facturado s/IVA"]))
    for j, (nombre, _, _) in enumerate(ESTADOS):
        if sin_iva_articulo[500 + j] > 0:
            C.igual(float(obtenido.get(f"Articulo estado {j}", 0)),
                    sin_iva_articulo[500 + j], f"margen: facturado de {nombre}")

    # Clientes: uno por tipo, así que esto mira cada tipo por separado.
    df = sg.get_top_customers_by_billing(1, -1, True, 7)
    obtenido = dict(zip(df["Cliente"], df["Total Facturado ($)"]))
    for i, t in enumerate(tipos):
        clave = f"Cliente tipo {t}"
        esperado = por_cliente[100 + i]
        if esperado > 0:
            C.igual(float(obtenido.get(clave, 0)), esperado, f"top clientes: tipo {t}")
        else:
            C.check(clave not in obtenido, f"top clientes: tipo {t} no aparece")
    C.igual(float(obtenido.get("CONSUMIDOR FINAL", 0)), por_cliente[1],
            "top clientes: consumidor final incluido")
    C.check(not any(str(k).startswith("E2") for k in obtenido),
            "top clientes: sin fugas de la otra empresa")

    df = sg.get_top_customers_by_billing(1, -1, False, 7)
    C.check("CONSUMIDOR FINAL" not in set(df["Cliente"]),
            "top clientes: consumidor final excluido")

    df = sg.get_top_clients_for_excel(1, -1, True, 7)
    C.igual(float(df["Total Facturado"].sum()),
            sum(v for v in por_cliente.values() if v > 0), "excel clientes: total")

    df_rfm, _ = sg.get_rfm_analysis_data(1, 7)
    obtenido = dict(zip(df_rfm["RazonSocial"], df_rfm["Monetario"]))
    for i, t in enumerate(tipos):
        esperado = por_cliente[100 + i]
        if esperado > 0:
            C.igual(float(obtenido.get(f"Cliente tipo {t}", 0)), esperado,
                    f"RFM monetario: tipo {t}")

    # Cuenta corriente: el nombre del tipo es el de Leontis.
    df = sg.get_customer_debt_for_excel(1, -1, -99)
    C.check(df.empty, "cta. cte. histórico: sin clientes con saldo no hay filas")
    with B.engine.begin() as c:
        from sqlalchemy import text
        c.execute(text("UPDATE clientes SET SaldoActual = 1 WHERE idEmpresa = 1"))
    df = sg.get_customer_debt_for_excel(1, -1, -99)
    nombres = set(zip(df["Cliente"], df["T.C."]))
    for i, t in enumerate(tipos):
        esperado = ORACULO_TIPOS.get(t, (str(t), 1))[0]
        C.check((f"Cliente tipo {t}", esperado) in nombres,
                f"cta. cte.: el tipo {t} se llama {esperado}")

C.cerrar()
