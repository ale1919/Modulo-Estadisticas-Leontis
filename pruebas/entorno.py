"""Lo común a las pruebas: el contador de checks y la base sintética.

La base sintética es una base NUEVA y descartable en el MariaDB local
(`est_prueba_<pid>`), creada con el DDL de `SCHEMAS/LEONTIS schema.sql` y
borrada al terminar. No toca `leontis_prueba` ni ninguna otra base.

La conexión sale de un archivo de opciones del cliente (por defecto
`C:\\leontis-prueba\\cliente.cnf`, o `ESTADISTICAS_PRUEBA_CNF`): la contraseña
no aparece en el repo ni en ninguna línea de comandos.
"""

import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

# Que los acentos de los mensajes salgan bien en la consola de Windows.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ACA = Path(__file__).resolve().parent
PROYECTO = ACA.parent
sys.path.insert(0, str(PROYECTO))

from sqlalchemy import create_engine, text  # noqa: E402

CNF = os.environ.get("ESTADISTICAS_PRUEBA_CNF", r"C:\leontis-prueba\cliente.cnf")
SCHEMA = PROYECTO.parents[1] / "SCHEMAS" / "LEONTIS schema.sql"
# El JSON de tipos del ERP. Si está, las pruebas comparan contra él la tabla
# que usa la app: es la fuente de verdad (AUDITORIA.md §7.1).
TIPOS_JSON_ERP = (PROYECTO.parents[0] / "LEONTIS ERP" / "BizSuite.Logic" / "Entidades"
                  / "NoPersistidas" / "TiposDeComprobante.json")

HOY = date.today()


# ---------------------------------------------------------------------- #
# Checks
# ---------------------------------------------------------------------- #

class Checks:
    def __init__(self, nombre):
        self.nombre = nombre
        self.ok = 0
        self.fallos = []

    def check(self, condicion, descripcion):
        if condicion:
            self.ok += 1
        else:
            self.fallos.append(descripcion)
            print(f"FALLA  {descripcion}")
        return condicion

    def igual(self, obtenido, esperado, descripcion, tolerancia=0.005):
        if isinstance(esperado, (int, float)) and isinstance(obtenido, (int, float)):
            bien = abs(float(obtenido) - float(esperado)) <= tolerancia
        else:
            bien = obtenido == esperado
        return self.check(bien, f"{descripcion}: esperado {esperado!r}, obtenido {obtenido!r}")

    def cerrar(self):
        if self.fallos:
            print(f"{self.ok} checks ok, {len(self.fallos)} FALLAN ({self.nombre}).")
            sys.exit(1)
        print(f"{self.ok} checks ok. Todo bien ({self.nombre}).")
        sys.exit(0)


# ---------------------------------------------------------------------- #
# Conexión
# ---------------------------------------------------------------------- #

def motor(base=None):
    if not os.path.isfile(CNF):
        print(f"FALLA  no está el archivo de opciones {CNF} (ESTADISTICAS_PRUEBA_CNF)")
        print("0 checks ok, 1 FALLAN (sin entorno).")
        sys.exit(1)
    args = {"read_default_file": CNF, "charset": "utf8mb4"}
    if base:
        args["database"] = base
    return create_engine("mysql+pymysql://", connect_args=args,
                         pool_pre_ping=True)


def generador(engine):
    """Un StatisticsGenerator de verdad sobre `engine`, sin pasar por el login.

    Se importa acá y no arriba para que las pruebas rápidas, que no tocan la
    base, no carguen la app entera."""
    from Recursos.Modulos.db_connection import DBManager
    from Recursos.Modulos.statistics_generator import StatisticsGenerator
    db = DBManager()
    db.db_engine = engine
    db.db_type = "MariaDB"
    return StatisticsGenerator(db), db


# ---------------------------------------------------------------------- #
# Base sintética
# ---------------------------------------------------------------------- #

def _sentencias_ddl():
    ddl = SCHEMA.read_text(encoding="utf-8")
    ddl = re.sub(r"^--.*$", "", ddl, flags=re.M)
    return [s.strip() for s in ddl.split(";") if s.strip().upper().startswith("CREATE")]


class BaseSintetica:
    """`with BaseSintetica() as b:` crea la base vacía con el esquema de Leontis
    y la borra al salir, pase lo que pase adentro."""

    def __init__(self):
        self.nombre = f"est_prueba_{os.getpid()}"

    def __enter__(self):
        servidor = motor()
        with servidor.begin() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS `{self.nombre}`"))
            c.execute(text(f"CREATE DATABASE `{self.nombre}` CHARACTER SET utf8mb4"))
        servidor.dispose()

        self.engine = motor(self.nombre)
        with self.engine.begin() as c:
            c.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            for sentencia in _sentencias_ddl():
                c.execute(text(sentencia))
        self.sg, self.db = generador(self.engine)
        return self

    def __exit__(self, *exc):
        try:
            self.engine.dispose()
        finally:
            servidor = motor()
            with servidor.begin() as c:
                c.execute(text(f"DROP DATABASE IF EXISTS `{self.nombre}`"))
            servidor.dispose()
        return False

    # -- inserción -------------------------------------------------------- #

    def ejecutar(self, sql, filas):
        with self.engine.begin() as c:
            c.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            if filas:
                c.execute(text(sql), filas)

    def empresa(self, id_empresa):
        self.ejecutar(
            "INSERT INTO empresas (idEmpresa, idTipoResponsable, CUIT, RazonSocial, Activa)"
            " VALUES (:id, 1, '20000000001', :rs, 1)",
            [{"id": id_empresa, "rs": f"Empresa {id_empresa}"}])

    def cliente(self, id_cliente, id_empresa, razon, codigo, saldo=0, activo=1):
        self.ejecutar(
            "INSERT INTO clientes (idCliente, idEmpresa, idTipoResponsable, CodigoCliente,"
            " RazonSocial, SaldoActual, Activo, Telefonos, Email)"
            " VALUES (:id, :e, 5, :cod, :rs, :saldo, :act, '555', 'x@x')",
            [{"id": id_cliente, "e": id_empresa, "cod": codigo, "rs": razon,
              "saldo": saldo, "act": activo}])

    def articulo(self, id_articulo, id_empresa, descripcion, costo=10, stock=0,
                 minimo=0, activo=1, id_proveedor=None, ultima_venta=None,
                 precio_neto=None):
        self.ejecutar(
            "INSERT INTO articulos (idArticulo, idEmpresa, idAlicuotaIVA, idProveedor,"
            " CodigoArticulo, Activo, Descripcion, PorcentajeMarcacion1, ExistenciaActual,"
            " ExistenciaMinima, PrecioCosto, Precio01Neto, Precio01Final, FechaUltimaVenta)"
            " VALUES (:id, :e, 5, :prov, :cod, :act, :desc, 30, :stock, :min, :costo,"
            " :pn, :pf, :uv)",
            [{"id": id_articulo, "e": id_empresa, "prov": id_proveedor,
              "cod": f"A{id_articulo}", "act": activo, "desc": descripcion,
              "stock": stock, "min": minimo, "costo": costo,
              "pn": precio_neto if precio_neto is not None else costo * 1.3,
              "pf": (precio_neto if precio_neto is not None else costo * 1.3) * 1.21,
              "uv": ultima_venta}])

    def comprobante(self, id_comp, id_empresa, tipo, id_cliente, total, fecha,
                    anulado=0, medio=None, pagado=1, fecha_pago="=", total_pagos=None,
                    items=(), vencimiento=None, pago_efectivo=None):
        """`items` = [(idArticulo, cantidad, total_con_iva, total_sin_iva, rentabilidad)].
        `fecha_pago="="` es "el mismo día del comprobante"."""
        if fecha_pago == "=":
            fecha_pago = fecha
        if total_pagos is None:
            total_pagos = total if pagado else 0
        if pago_efectivo is None:
            pago_efectivo = total if pagado else 0
        self.ejecutar(
            "INSERT INTO comprobanteemitido (idComprobanteEmitido, idTipoComprobante,"
            " idEmpresa, idPuntoVenta, idCliente, Anulado, FechaHoraCreacion,"
            " FechaComprobante, NumeroComprobante, TotalOperacion, ConceptosNoGravados,"
            " PercepcionNoCategorizados, OperacionesExentas, PercepcionesImpuestosNacionales,"
            " PercepcionIngresosBrutos, PorcentajePercepcionIngresosBrutos,"
            " PercepcionImpuestosMunicipales, PorcentajePercepcionImpuestosMunicipales,"
            " ImpuestosInternos, OtrosTributos, TotalPagos, Pagado, TotalNetoOperacion,"
            " IVA_1050_NetoGravado, IVA_1050_Liquidado, IIBB_BaseImponible,"
            " IVA_2100_NetoGravado, IVA_2100_Liquidado, TotalEnvases, PagoEfectivo,"
            " PagoCheques, FechaPago, SaldoAnterior, Rentabilidad, FechaVencimientoPago,"
            " IdMedioDePago)"
            " VALUES (:id, :tipo, :e, 1, :cli, :anu, :fecha, :fecha, :id, :total,"
            " 0,0,0,0,0,0,0,0,0,0, :tp, :pag, :neto, 0,0,0, :neto, 0, 0, :pe, 0, :fp, 0,"
            " 0, :venc, :medio)",
            [{"id": id_comp, "tipo": tipo, "e": id_empresa, "cli": id_cliente,
              "anu": anulado, "fecha": fecha, "total": total, "tp": total_pagos,
              "pag": pagado, "neto": round(total / 1.21, 2), "pe": pago_efectivo,
              "fp": fecha_pago, "venc": vencimiento, "medio": medio}])
        self.ejecutar(
            "INSERT INTO comprobanteemitidoitems (idComprobanteEmitido, idArticulo,"
            " Cantidad, PrecioUnitarioSinIVA, PrecioUnitarioConIVA, PorcentajeBonificacion,"
            " SubTotalItemSinIVA, SubTotalItemConIVA, PorcentajeIVA, TotalItemSinIVA,"
            " TotalItemConIVA, Rentabilidad)"
            " VALUES (:c, :a, :q, 0, 0, 0, :sin, :con, 21, :sin, :con, :rent)",
            [{"c": id_comp, "a": a, "q": q, "con": con, "sin": sin, "rent": rent}
             for a, q, con, sin, rent in items])


def dias_atras(n):
    return HOY - timedelta(days=n)
