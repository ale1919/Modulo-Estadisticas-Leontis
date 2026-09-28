"""El formato de cada columna de cada exportación, por nombre (AUDITORIA.md §7.3.6-8),
y el formato argentino de números. Sin base ni interfaz: es de las rápidas.

La tabla de abajo es la lista COMPLETA de columnas que hoy devuelven los
informes. Si un informe suma una columna, se agrega acá con su formato.
"""

import math

from entorno import Checks

from Recursos.Modulos.formatos import (
    DECIMAL, ENTERO, FECHA, MONEDA, PORCENTAJE, formato_de_columna, formatos_por_columna,
    numero, pesos)

C = Checks("formatos")
M, F, P, E, D, T = MONEDA, FECHA, PORCENTAJE, ENTERO, DECIMAL, None

COLUMNAS = {
    # artículos (Excel)
    "Código": T, "Descripción": T, "Precio Costo": M, "Precio Venta s/IVA": M,
    "Precio Venta c/IVA": M, "Stock": D, "Cantidad Vendida": D, "Total Vendido": M,
    "Total Vendido ($)": M,
    # clientes
    "Código Cliente": T, "Razón Social": T, "Total Facturado": M, "Saldo Pendiente": M,
    "Total Facturado ($)": M, "Cliente": T,
    # ventas
    "Fecha": F, "Efectivo": M, "Tarjeta": M, "Cheque": M, "Mercado Pago": M,
    "Otros": M, "Cuenta Corriente": M, "Total": M, "Total Ventas ($)": M,
    # canasta
    "Precio sin IVA": M, "IVA": M, "Precio Final": M, "Artículos Asociados": T,
    "Artículos Distintos": E, "Veces Vendidos Juntos": E,
    # cuenta corriente
    "CUIT": T, "DNI": T, "Teléfono": T, "Saldo Total Adeudado": M, "T.C.": T,
    "Punto Venta": T, "N° Comprobante": T, "Total Operación": M, "Saldo": M,
    "Días de Mora": E, "Saldo Total Cliente": M, "Saldo Adeudado ($)": M,
    # aging
    "Saldo Total": M, "Por vencer": M, "1 a 30 días": M, "31 a 60 días": M,
    "61 a 90 días": M, "Más de 90 días": M, "Mora Máxima (días)": E,
    # SLOB
    "Stock Actual": D, "Última Venta": F, "Valor Inmovilizado ($)": M,
    # RFM
    "RazonSocial": T, "Telefonos": T, "Email": T, "Recencia": E, "Frecuencia": E,
    "Monetario": M, "R_Score": E, "F_Score": E, "M_Score": E, "Segmento": T,
    # margen
    "Unidades": D, "Facturado s/IVA": M, "Costo Estimado": M, "Margen Bruto ($)": M,
    "% Margen": P,
    # ABC
    "#": E, "Tickets": E, "% Acumulado": P, "Clase": T, "Capital Inmovilizado": M,
    # sugerido de compra
    "Proveedor": T, "Mínimo": D, "Venta Diaria": D, "Días de Cobertura": E,
    "Sugerido a Comprar": D, "Costo Unitario": M, "Última Compra": F,
    # nombres que van a usar los informes nuevos
    "Vence": F, "Vencimiento": F, "Primera Compra": F, "Comprobantes": E,
    "Clientes Distintos": E, "Tasa % Conversión": P, "Var. Interanual": P,
    "Mes": T, "Ítems por Ticket": D, "Ticket Promedio": M,
}

for columna, esperado in COLUMNAS.items():
    C.igual(formato_de_columna(columna), esperado, f"formato de '{columna}'")
    # El mismo nombre en mayúsculas, sin acentos y con espacios de más.
    variante = "  " + columna.upper().replace("Í", "I").replace("Ó", "O") + " "
    C.igual(formato_de_columna(variante), esperado, f"formato de '{variante}'")

for vacio in ("", "   ", None):
    C.igual(formato_de_columna(vacio if vacio is not None else ""), None,
            f"columna vacía {vacio!r}")
C.igual(formato_de_columna(123), None, "columna con nombre numérico")

C.igual(formatos_por_columna(["Fecha", "Cliente", "Saldo"]), {0: F, 2: M},
        "formatos_por_columna")
C.igual(formatos_por_columna([]), {}, "formatos_por_columna vacío")
C.igual(formatos_por_columna(["% Margen", "Días de Mora", "Stock", "Cliente"]),
        {0: P, 1: E, 2: D}, "formatos_por_columna con los cinco tipos")
C.igual(len({M, F, P, E, D}), 5, "los cinco formatos son distintos")
C.check(all(isinstance(x, str) and x for x in (M, F, P, E, D)), "los formatos no son vacíos")

# -- formato argentino ----------------------------------------------------- #
CASOS_PESOS = [
    (0, 0, "$ 0"), (1234567, 0, "$ 1.234.567"), (1234567.891, 2, "$ 1.234.567,89"),
    (-1500, 0, "-$ 1.500"), (999.5, 0, "$ 1.000"), (0.004, 2, "$ 0,00"),
    ("2500", 0, "$ 2.500"), (None, 0, ""), (float("nan"), 0, ""), ("abc", 0, ""),
    (12, 2, "$ 12,00"), (1e12, 0, "$ 1.000.000.000.000"),
]
C.igual(pesos(1234.56), "$ 1.235", "pesos sin decimales por defecto")
C.igual(numero(1234.56), "1.235", "numero sin decimales por defecto")
for valor, dec, esperado in CASOS_PESOS:
    C.igual(pesos(valor, dec), esperado, f"pesos({valor!r}, {dec})")

CASOS_NUMERO = [
    (0, 0, "0"), (1234.5, 1, "1.234,5"), (-7, 0, "-7"), (None, 0, ""),
    (math.nan, 0, ""), ("x", 0, ""), (1000000, 0, "1.000.000"),
]
for valor, dec, esperado in CASOS_NUMERO:
    C.igual(numero(valor, dec), esperado, f"numero({valor!r}, {dec})")

C.cerrar()
