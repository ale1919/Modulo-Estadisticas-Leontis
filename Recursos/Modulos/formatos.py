"""Qué formato lleva cada columna de las exportaciones, decidido por su NOMBRE.

Antes cada informe formateaba columnas por letra (`'K:K'` moneda, `'J:K'`
moneda...). Cada vez que una consulta sumaba o movía una columna, el formato
quedaba corrido en silencio: el DNI salía con `$`, la fecha de última compra como
moneda y el saldo sin formato (AUDITORIA.md §7.3.6 a §7.3.8). Decidirlo por el
nombre hace que una columna nueva o movida se formatee bien sola.

Sin Qt ni xlsxwriter adentro: es lógica pura y se prueba sin interfaz.
"""

import re
import unicodedata

MONEDA = "moneda"
FECHA = "fecha"
PORCENTAJE = "porcentaje"
ENTERO = "entero"
DECIMAL = "decimal"

# Columnas que parecen de dinero por su nombre y NO lo son. Se revisan antes
# que las reglas de abajo.
_NO_MONEDA = ("dni", "cuit", "telefono", "codigo", "n° comprobante", "punto venta",
              "dias", "unidades", "cantidad", "stock", "minimo", "tickets",
              "frecuencia", "recencia", "score", "articulos distintos",
              "veces vendidos", "#", "clientes", "comprobantes")

_PALABRAS_MONEDA = ("($)", "$", "total", "saldo", "precio", "costo", "margen bruto",
                    "facturado", "monetario", "valor", "capital", "importe",
                    "efectivo", "tarjeta", "cheque", "mercado pago", "otros",
                    "cuenta corriente", "iva", "venta perdida",
                    "ticket promedio", "deuda", "presupuestado", "descuento")


def _normalizar(nombre):
    texto = unicodedata.normalize("NFKD", str(nombre))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.strip().lower())


def formato_de_columna(nombre):
    """`MONEDA`, `FECHA`, `PORCENTAJE`, `ENTERO`, `DECIMAL` o None (texto)."""
    n = _normalizar(nombre)
    if not n:
        return None
    if n.startswith("%") or n.endswith("%") or " % " in f" {n} " or n.startswith("var."):
        return PORCENTAJE
    # "Mes" no: sale como texto 'AAAA-MM' y un formato de fecha no le hace nada.
    if n.startswith(("fecha", "ultima ", "ult. ", "primera compra")) \
            or n in ("vence", "vencimiento"):
        return FECHA
    # Los tramos del aging dicen "días" pero son plata.
    if n == "por vencer" or re.fullmatch(r"\d+ a \d+ dias", n) or n.startswith("mas de "):
        return MONEDA
    if n.startswith(("dias", "mora", "clientes", "r_score", "f_score", "m_score")) \
            or n in ("#", "tickets", "comprobantes", "frecuencia", "recencia",
                                              "articulos distintos",
                                              "veces vendidos juntos"):
        return ENTERO
    if any(p in n for p in _NO_MONEDA):
        if n.startswith(("unidades", "cantidad", "stock", "minimo", "venta diaria",
                         "sugerido")):
            return DECIMAL
        return None
    if n.startswith(("venta diaria", "sugerido", "items por")):
        return DECIMAL
    if any(p in n for p in _PALABRAS_MONEDA):
        return MONEDA
    return None


def formatos_por_columna(columnas):
    """{indice: formato} para las columnas que llevan alguno."""
    salida = {}
    for i, nombre in enumerate(columnas):
        f = formato_de_columna(nombre)
        if f:
            salida[i] = f
    return salida


def pesos(valor, decimales=0):
    """`$ 1.234.567` al estilo argentino. None y NaN dan cadena vacía."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return ""
    if numero != numero:            # NaN
        return ""
    texto = f"{abs(numero):,.{decimales}f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if numero < 0 else ''}$ {texto}"


def numero(valor, decimales=0):
    """`1.234,5` al estilo argentino."""
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return ""
    if n != n:
        return ""
    texto = f"{n:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")
