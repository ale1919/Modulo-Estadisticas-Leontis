"""Consultas y cálculos de todas las estadísticas de la app.

Convención de comprobantes (ver AUDITORIA.md §1.1)
-------------------------------------------------
`comprobanteemitido` no guarda solo facturas: también notas de crédito y recibos
de cobranza. Antes, todas las consultas de venta filtraban únicamente por
`Anulado = 0`, así que una nota de crédito **sumaba** en vez de restar y cada
recibo de cobranza se contaba como una venta nueva.

Todo lo que mida ventas tiene que usar `FILTRO_VENTA` y `SIGNO_VENTA`. No los
repitas a mano: si mañana aparece otro tipo de comprobante, se corrige acá y vale
para toda la app.
"""

import pandas as pd
from sqlalchemy import bindparam, text

# Tipos de comprobante, según los usa el propio sistema Leontis.
#   1 = FC A    6 = FC B    11 = FC M     (facturas: suman)
#   3 = NC A    8 = NC B    13 = NC M     (notas de crédito: restan)
# -81 = CO X  -83 = RC X                  (interno y recibo: no son venta)
TIPOS_NOTA_CREDITO = (3, 8, 13)
TIPOS_NO_VENTA = (-81, -83)


def SIGNO_VENTA(alias="ce"):
    """Expresión SQL que vale -1 para notas de crédito y 1 para facturas."""
    prefijo = f"{alias}." if alias else ""
    return (f"CASE WHEN {prefijo}idTipoComprobante IN "
            f"{TIPOS_NOTA_CREDITO} THEN -1 ELSE 1 END")


def FILTRO_VENTA(alias="ce"):
    """Condiciones que dejan solo los comprobantes que son una venta real."""
    prefijo = f"{alias}." if alias else ""
    return (f" AND {prefijo}Anulado = 0"
            f" AND {prefijo}idTipoComprobante NOT IN {TIPOS_NO_VENTA}")


class StatisticsGenerator:
    """Genera todas las estadísticas e informes de la aplicación."""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _get_date_filter(self, days, table_alias='ce', param_name='days'):
        """Fragmento SQL para el filtro de fecha, acotado al día de hoy."""
        prefijo = f"{table_alias}." if table_alias else ""

        if days == -1:
            return f" AND {prefijo}FechaComprobante <= CURDATE()"

        # `FechaComprobante` es DATE: comparar contra NOW() dejaría afuera el día
        # en curso a partir del mediodía. Se compara siempre contra fechas.
        return (f" AND {prefijo}FechaComprobante >= "
                f"DATE_SUB(CURDATE(), INTERVAL :{param_name} DAY)"
                f" AND {prefijo}FechaComprobante <= CURDATE()")

    def _dias_efectivos(self, company_id, days):
        """Cantidad de días del período, para calcular promedios diarios.

        Con "Todo el Historial" (-1) no hay ventana fija: se usa la distancia
        hasta el primer comprobante para que la venta diaria promedio no salga
        dividida por un número inventado.
        """
        if days != -1:
            return max(int(days), 1)

        query = """
            SELECT DATEDIFF(CURDATE(), MIN(FechaComprobante))
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id AND Anulado = 0
        """
        df = self.db_manager._execute_query(query, {"company_id": company_id})
        if df.empty or df.iloc[0, 0] is None:
            return 365
        return max(int(df.iloc[0, 0]), 1)

    # ------------------------------------------------------------------ #
    # Artículos
    # ------------------------------------------------------------------ #

    def get_top_articles_by_value(self, company_id, limit=10, days=90):
        query = f"""
            SELECT
                a.Descripcion AS Articulo,
                SUM(cei.TotalItemConIVA * {SIGNO_VENTA('ce')}) AS 'Total Vendido ($)'
            FROM comprobanteemitidoitems cei
            JOIN articulos a ON cei.idArticulo = a.idArticulo
            JOIN comprobanteemitido ce ON cei.idComprobanteEmitido = ce.idComprobanteEmitido
            WHERE ce.idEmpresa = :company_id
            {FILTRO_VENTA('ce')}
            {self._get_date_filter(days, 'ce')}
            GROUP BY a.idArticulo, a.Descripcion
            HAVING `Total Vendido ($)` > 0
            ORDER BY `Total Vendido ($)` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(
            query, {"company_id": company_id, "limit": limit, "days": days})

    def get_top_articles_by_quantity(self, company_id, limit=10, days=90):
        query = f"""
            SELECT
                a.Descripcion AS Articulo,
                SUM(cei.Cantidad * {SIGNO_VENTA('ce')}) AS 'Cantidad Vendida'
            FROM comprobanteemitidoitems cei
            JOIN articulos a ON cei.idArticulo = a.idArticulo
            JOIN comprobanteemitido ce ON cei.idComprobanteEmitido = ce.idComprobanteEmitido
            WHERE ce.idEmpresa = :company_id
            {FILTRO_VENTA('ce')}
            {self._get_date_filter(days, 'ce')}
            GROUP BY a.idArticulo, a.Descripcion
            HAVING `Cantidad Vendida` > 0
            ORDER BY `Cantidad Vendida` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(
            query, {"company_id": company_id, "limit": limit, "days": days})

    def get_top_articles_for_excel(self, company_id, limit, days, order_by_value=True):
        signo = SIGNO_VENTA('ce')
        order_expression = (f"SUM(cei.TotalItemConIVA * {signo})" if order_by_value
                            else f"SUM(cei.Cantidad * {signo})")
        query = f"""
            SELECT
                a.CodigoArticulo AS 'Código',
                a.Descripcion AS 'Descripción',
                a.PrecioCosto AS 'Precio Costo',
                a.Precio01Neto AS 'Precio Venta s/IVA',
                a.Precio01Final AS 'Precio Venta c/IVA',
                a.ExistenciaActual AS 'Stock',
                SUM(cei.Cantidad * {signo}) AS 'Cantidad Vendida',
                SUM(cei.TotalItemConIVA * {signo}) AS 'Total Vendido'
            FROM comprobanteemitidoitems cei
            JOIN articulos a ON cei.idArticulo = a.idArticulo
            JOIN comprobanteemitido ce ON cei.idComprobanteEmitido = ce.idComprobanteEmitido
            WHERE ce.idEmpresa = :company_id
            {FILTRO_VENTA('ce')}
            {self._get_date_filter(days, 'ce')}
            GROUP BY a.idArticulo, a.CodigoArticulo, a.Descripcion, a.PrecioCosto,
                     a.Precio01Neto, a.Precio01Final, a.ExistenciaActual
            ORDER BY {order_expression} DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(
            query, {"company_id": company_id, "limit": limit, "days": days})

    # ------------------------------------------------------------------ #
    # Clientes
    # ------------------------------------------------------------------ #

    def get_top_customers_by_billing(self, company_id, limit=10,
                                     include_final_consumer=False, days=90):
        # LEFT JOIN a propósito: los tickets sin cliente asociado son ventas a
        # consumidor final y antes desaparecían del informe, con lo que el total
        # de "Top Clientes" nunca cerraba con el de "Ventas por Día".
        query = f"""
            SELECT
                COALESCE(cli.RazonSocial, 'Consumidor Final') AS Cliente,
                SUM(ce.TotalOperacion * {SIGNO_VENTA('ce')}) AS 'Total Facturado ($)'
            FROM comprobanteemitido ce
            LEFT JOIN clientes cli ON ce.idCliente = cli.idCliente
            WHERE ce.idEmpresa = :company_id
            {FILTRO_VENTA('ce')}
            {self._get_date_filter(days, 'ce')}
        """
        if not include_final_consumer:
            # `CodigoCliente` es nullable y `NULL != '0'` evalúa a NULL, no a
            # TRUE: sin el IS NULL, todo cliente sin código se perdía en silencio.
            query += (" AND ce.idCliente IS NOT NULL"
                      " AND (cli.CodigoCliente IS NULL OR cli.CodigoCliente <> '0')")

        query += """
            GROUP BY cli.idCliente, cli.RazonSocial
            HAVING `Total Facturado ($)` > 0
            ORDER BY `Total Facturado ($)` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(
            query, {"company_id": company_id, "limit": limit, "days": days})

    def get_top_clients_for_excel(self, company_id, limit, include_final_consumer, days):
        query = f"""
            SELECT
                cli.CodigoCliente AS 'Código Cliente',
                COALESCE(cli.RazonSocial, 'Consumidor Final') AS 'Razón Social',
                SUM(ce.TotalOperacion * {SIGNO_VENTA('ce')}) AS 'Total Facturado',
                cli.SaldoActual AS 'Saldo Pendiente'
            FROM comprobanteemitido ce
            LEFT JOIN clientes cli ON ce.idCliente = cli.idCliente
            WHERE ce.idEmpresa = :company_id
            {FILTRO_VENTA('ce')}
            {self._get_date_filter(days, 'ce')}
        """
        if not include_final_consumer:
            query += (" AND ce.idCliente IS NOT NULL"
                      " AND (cli.CodigoCliente IS NULL OR cli.CodigoCliente <> '0')")

        query += """
            GROUP BY cli.idCliente, cli.CodigoCliente, cli.RazonSocial, cli.SaldoActual
            HAVING `Total Facturado` > 0
            ORDER BY `Total Facturado` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(
            query, {"company_id": company_id, "limit": limit, "days": days})

    # ------------------------------------------------------------------ #
    # Ventas
    # ------------------------------------------------------------------ #

    def get_sales_over_time(self, company_id, days=90):
        query = f"""
            SELECT
                DATE(FechaComprobante) AS Fecha,
                SUM(TotalOperacion * {SIGNO_VENTA('')}) AS 'Total Ventas ($)'
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id
            {FILTRO_VENTA('')}
            {self._get_date_filter(days, '')}
            GROUP BY DATE(FechaComprobante)
            ORDER BY Fecha ASC;
        """
        return self.db_manager._execute_query(
            query, {"company_id": company_id, "days": days})

    def _sql_medios_de_pago(self):
        """Las cuatro categorías de cobro, como partición exclusiva del total.

        Antes 'Efectivo' y 'Cheque' sumaban campos de pago parcial mientras que
        'Tarjeta' y 'Otros' sumaban el total del comprobante, así que una factura
        pagada mitad y mitad se contaba dos veces y las columnas no sumaban el
        total. Ahora el resto no cubierto por efectivo ni cheque se imputa a
        tarjeta o a cuenta corriente según el medio declarado, y se cumple
        Efectivo + Cheque + Tarjeta + Otros = Total.
        """
        signo = SIGNO_VENTA('')
        resto = "(TotalOperacion - PagoEfectivo - PagoCheques)"
        return {
            'Efectivo': f"SUM(PagoEfectivo * {signo})",
            'Cheque': f"SUM(PagoCheques * {signo})",
            'Tarjeta': (f"SUM(CASE WHEN IdMedioDePago = 2 "
                        f"THEN {resto} * {signo} ELSE 0 END)"),
            'Otros': (f"SUM(CASE WHEN IdMedioDePago <> 2 OR IdMedioDePago IS NULL "
                      f"THEN {resto} * {signo} ELSE 0 END)"),
        }

    def get_sales_by_day_for_excel(self, company_id, days, payment_methods):
        medios = self._sql_medios_de_pago()
        columnas = ",\n                ".join(
            f"{expr} AS '{nombre}'" for nombre, expr in medios.items())

        query = f"""
            SELECT
                DATE(FechaComprobante) AS Fecha,
                {columnas},
                SUM(TotalOperacion * {SIGNO_VENTA('')}) AS 'Total'
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id
            {FILTRO_VENTA('')}
            {self._get_date_filter(days, '')}
            GROUP BY DATE(FechaComprobante)
            ORDER BY Fecha ASC;
        """
        df = self.db_manager._execute_query(
            query, {"company_id": company_id, "days": days})

        if df is not None and not df.empty:
            cols_to_keep = ['Fecha'] + list(payment_methods) + ['Total']
            existing_cols = [col for col in cols_to_keep if col in df.columns]
            return df[existing_cols]
        return df

    def get_sales_by_payment_method_for_chart(self, company_id, days, payment_methods):
        if not payment_methods:
            return pd.DataFrame()

        medios = self._sql_medios_de_pago()
        select_clauses = [f"{expr} AS '{nombre}'"
                          for nombre, expr in medios.items()
                          if nombre in payment_methods]
        if not select_clauses:
            return pd.DataFrame()

        query = f"""
            SELECT
                DATE(FechaComprobante) AS Fecha,
                {', '.join(select_clauses)}
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id
            {FILTRO_VENTA('')}
            {self._get_date_filter(days, '')}
            GROUP BY Fecha
            ORDER BY Fecha ASC;
        """
        df = self.db_manager._execute_query(
            query, {'company_id': company_id, 'days': days})

        if df is not None and not df.empty:
            df.set_index('Fecha', inplace=True)
            return df
        return pd.DataFrame()

    # ------------------------------------------------------------------ #
    # Stock
    # ------------------------------------------------------------------ #

    def get_stock_data_for_excel(self, company_id, option, limit):
        query = ("SELECT CodigoArticulo AS 'Código', Descripcion AS 'Descripción', "
                 "ExistenciaActual AS 'Stock' FROM articulos "
                 "WHERE idEmpresa = :company_id AND Activo = 1")

        if option == "top_mas_stock":
            query += " ORDER BY ExistenciaActual DESC"
        elif option == "top_menos_stock":
            query += " AND ExistenciaActual > 0 ORDER BY ExistenciaActual ASC"
        elif option == "cero_negativo":
            query += " AND ExistenciaActual <= 0 ORDER BY ExistenciaActual ASC"
        elif option == "todos_stock":
            query += " ORDER BY Descripcion ASC"

        if option in ["top_mas_stock", "top_menos_stock"] and limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(
            query, {"company_id": company_id, "limit": limit})

    def get_slob_analysis_for_excel(self, company_id, threshold_days):
        """Artículos con stock positivo sin ventas recientes, o que nunca se
        vendieron. Devuelve un DataFrame vacío si no hay ninguno: el aviso al
        usuario lo da la capa de UI, no una fila de relleno con texto adentro.
        """
        query = """
            SELECT
                CodigoArticulo AS 'Código',
                Descripcion AS 'Descripción',
                ExistenciaActual AS 'Stock Actual',
                FechaUltimaVenta AS 'Última Venta',
                (ExistenciaActual * PrecioCosto) AS 'Valor Inmovilizado ($)'
            FROM articulos
            WHERE idEmpresa = :company_id
              AND Activo = 1
              AND ((DATEDIFF(CURDATE(), FechaUltimaVenta) > :threshold_days)
                   OR (FechaUltimaVenta IS NULL))
              AND ExistenciaActual > 0
            ORDER BY `Valor Inmovilizado ($)` DESC;
        """
        return self.db_manager._execute_query(
            query, {"company_id": company_id, "threshold_days": int(threshold_days)})

    # ------------------------------------------------------------------ #
    # Listados para exportación rápida y para el modal de canasta
    # ------------------------------------------------------------------ #

    def get_all_articles_for_dropdown(self, company_id):
        query = """
            SELECT idArticulo, Descripcion, CodigoArticulo
            FROM articulos
            WHERE idEmpresa = :company_id AND Activo = 1
            ORDER BY Descripcion ASC;
        """
        return self.db_manager._execute_query(query, {"company_id": company_id})

    def get_export_all_clients(self, company_id, mode):
        select_list = [
            "cli.CodigoCliente", "cli.RazonSocial", "cli.CUIT", "cli.NumeroDocumento",
            "cli.Domicilio", "cli.Localidad", "cli.CodigoPostal", "cli.SaldoActual",
            "cli.Notas", "cli.Telefonos", "cli.Email"
        ]

        where_clause = "WHERE cli.idEmpresa = :company_id"
        if mode == 'activos':
            where_clause += " AND cli.Activo = 1"
        else:
            select_list.append("cli.Activo")

        query = f"""
            SELECT {', '.join(select_list)}
            FROM clientes cli
            {where_clause}
            ORDER BY cli.RazonSocial;
        """
        return self.db_manager._execute_query(query, {"company_id": company_id})

    def get_export_all_articles(self, company_id, mode):
        select_list = [
            "a.CodigoArticulo AS 'Codigo-Articulo'", "a.CodigoDeBarras", "a.Codigo01",
            "a.Descripcion", "a.PorcentajeIVA", "a.PorcentajeMarcacion1",
            "a.ExistenciaActual", "a.ExistenciaMinima", "a.PrecioCosto",
            "a.ImpuestosInternos", "a.DescuentoProveedor", "a.Precio01Neto",
            "a.Precio01Final", "p.RazonSocial AS 'Proveedor'",
            "a.FechaUltimaCompra AS 'Última Compra'",
            "a.FechaUltimaVenta AS 'Última Venta'"
        ]

        where_clause = "WHERE a.idEmpresa = :company_id"
        if mode == 'activos':
            where_clause += " AND a.Activo = 1"
        else:
            select_list.insert(2, "a.Activo")

        query = f"""
            SELECT {', '.join(select_list)}
            FROM articulos a
            LEFT JOIN proveedores p ON p.idProveedor = a.idProveedor
            {where_clause}
            ORDER BY a.Descripcion;
        """
        return self.db_manager._execute_query(query, {"company_id": company_id})

    # ------------------------------------------------------------------ #
    # Análisis de canasta
    # ------------------------------------------------------------------ #

    def get_market_basket_analysis(self, company_id, days, mode, association_limit,
                                   manual_article_ids=None):
        """Qué artículos se venden juntos en el mismo comprobante.

        El self-join sobre los ítems es cuadrático por comprobante, así que se
        acota a los que tienen entre 2 y 25 renglones: uno solo no aporta ningún
        par, y una factura de obra con 80 renglones genera 3.160 pares que además
        de tardar ensucian el resultado (todo aparece asociado con todo).
        """
        manual_article_ids = manual_article_ids or []
        date_filter_sql = self._get_date_filter(days, 'ce', param_name='basket_days')

        params = {"company_id": company_id, "assoc_limit": association_limit}
        if days != -1:
            params["basket_days"] = days

        common_ctes = f"""
            WITH ValidTransactions AS (
                SELECT ce.idComprobanteEmitido
                FROM comprobanteemitido ce
                JOIN comprobanteemitidoitems it
                     ON it.idComprobanteEmitido = ce.idComprobanteEmitido
                WHERE ce.idEmpresa = :company_id
                  AND ce.idTipoComprobante NOT IN {TIPOS_NOTA_CREDITO + TIPOS_NO_VENTA}
                  AND ce.Anulado = 0
                  AND it.idArticulo IS NOT NULL
                {date_filter_sql}
                GROUP BY ce.idComprobanteEmitido
                HAVING COUNT(*) BETWEEN 2 AND 25
            ),
            ItemPairs AS (
                SELECT
                    i1.idArticulo AS ArticuloA,
                    i2.idArticulo AS ArticuloB,
                    COUNT(DISTINCT i1.idComprobanteEmitido) AS Frecuencia
                FROM comprobanteemitidoitems i1
                JOIN comprobanteemitidoitems i2
                     ON i1.idComprobanteEmitido = i2.idComprobanteEmitido
                WHERE i1.idComprobanteEmitido IN (SELECT idComprobanteEmitido FROM ValidTransactions)
                  AND i1.idArticulo < i2.idArticulo
                GROUP BY i1.idArticulo, i2.idArticulo
            ),
            UnpivotedAssociations AS (
                SELECT ArticuloA AS idArticulo, ArticuloB AS idArticuloAsociado, Frecuencia FROM ItemPairs
                UNION ALL
                SELECT ArticuloB AS idArticulo, ArticuloA AS idArticuloAsociado, Frecuencia FROM ItemPairs
            ),
            RankedAssociations AS (
                SELECT
                    ua.idArticulo,
                    CONCAT(assoc_art.Descripcion, ' (', ua.Frecuencia, ')') AS AssocText,
                    ua.Frecuencia,
                    ROW_NUMBER() OVER(PARTITION BY ua.idArticulo ORDER BY ua.Frecuencia DESC) as rn
                FROM UnpivotedAssociations ua
                JOIN articulos assoc_art ON ua.idArticuloAsociado = assoc_art.idArticulo
                WHERE assoc_art.Activo = 1 AND assoc_art.idEmpresa = :company_id
            ),
            FilteredTextAssociations AS (
                SELECT
                    idArticulo,
                    GROUP_CONCAT(AssocText ORDER BY Frecuencia DESC SEPARATOR ', ') AS ArticulosAsociados
                FROM RankedAssociations
                WHERE rn <= :assoc_limit OR :assoc_limit = -1
                GROUP BY idArticulo
            ),
            TotalAssociations AS (
                SELECT
                    idArticulo,
                    COUNT(*) AS ArticulosDistintos,
                    SUM(Frecuencia) AS TotalAsociaciones
                FROM UnpivotedAssociations
                GROUP BY idArticulo
            )
        """

        if mode == 'manual':
            if not manual_article_ids:
                return pd.DataFrame()

            query = f"""
                {common_ctes}
                SELECT
                    art_main.CodigoArticulo AS 'Código',
                    art_main.Descripcion AS 'Descripción',
                    art_main.Precio01Neto AS 'Precio sin IVA',
                    (art_main.Precio01Final - art_main.Precio01Neto) AS 'IVA',
                    art_main.Precio01Final AS 'Precio Final',
                    COALESCE(fta.ArticulosAsociados, 'Sin asociaciones en el período') AS 'Artículos Asociados',
                    COALESCE(ta.ArticulosDistintos, 0) AS 'Artículos Distintos',
                    COALESCE(ta.TotalAsociaciones, 0) AS 'Veces Vendidos Juntos'
                FROM articulos art_main
                LEFT JOIN FilteredTextAssociations fta ON art_main.idArticulo = fta.idArticulo
                LEFT JOIN TotalAssociations ta ON art_main.idArticulo = ta.idArticulo
                WHERE art_main.idEmpresa = :company_id AND art_main.Activo = 1
                  AND art_main.idArticulo IN :manual_ids
                ORDER BY `Veces Vendidos Juntos` DESC, art_main.Descripcion ASC
            """
            params["manual_ids"] = [int(x) for x in manual_article_ids]
            # `expanding=True` es lo que convierte la lista en (1, 2, 3). Sin esto
            # SQLAlchemy la trataría como un escalar y solo funcionaba de casualidad
            # porque pymysql sabe escapar tuplas.
            sentencia = text(query).bindparams(
                bindparam("manual_ids", expanding=True))
            return self.db_manager._execute_query(sentencia, params)

        params["limit"] = int(mode)
        query = f"""
            {common_ctes}
            SELECT
                art_main.CodigoArticulo AS 'Código',
                art_main.Descripcion AS 'Descripción',
                art_main.Precio01Neto AS 'Precio sin IVA',
                (art_main.Precio01Final - art_main.Precio01Neto) AS 'IVA',
                art_main.Precio01Final AS 'Precio Final',
                fta.ArticulosAsociados AS 'Artículos Asociados',
                ta.ArticulosDistintos AS 'Artículos Distintos',
                ta.TotalAsociaciones AS 'Veces Vendidos Juntos'
            FROM TotalAssociations ta
            JOIN articulos art_main ON ta.idArticulo = art_main.idArticulo
            LEFT JOIN FilteredTextAssociations fta ON ta.idArticulo = fta.idArticulo
            WHERE art_main.idEmpresa = :company_id AND art_main.Activo = 1
            ORDER BY ta.TotalAsociaciones DESC, art_main.Descripcion ASC
            LIMIT :limit
        """
        return self.db_manager._execute_query(query, params)

    # ------------------------------------------------------------------ #
    # Cuenta corriente
    # ------------------------------------------------------------------ #

    def get_customer_debt_for_chart(self, company_id, limit):
        query = """
            SELECT
                cli.RazonSocial AS Cliente,
                cli.SaldoActual AS 'Saldo Adeudado ($)'
            FROM clientes cli
            WHERE cli.idEmpresa = :company_id AND cli.SaldoActual > 0
            ORDER BY cli.SaldoActual DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(
            query, {"company_id": company_id, "limit": limit})

    def get_customer_debt_for_excel(self, company_id, client_limit, voucher_scope):
        params = {
            "company_id": company_id,
            "client_limit": client_limit,
            "voucher_limit": voucher_scope
        }

        if voucher_scope == 0:
            query_case_1 = """
                SELECT
                    cli.CodigoCliente AS 'Código Cliente',
                    cli.RazonSocial AS 'Cliente',
                    cli.CUIT,
                    cli.NumeroDocumento AS 'DNI',
                    cli.Telefonos AS 'Teléfono',
                    cli.SaldoActual AS 'Saldo Total Adeudado'
                FROM clientes cli
                WHERE cli.idEmpresa = :company_id AND cli.SaldoActual != 0
                ORDER BY cli.SaldoActual DESC
            """
            if client_limit != -1:
                query_case_1 += " LIMIT :client_limit"

            return self.db_manager._execute_query(query_case_1, params)

        client_limit_sql = "LIMIT :client_limit" if client_limit != -1 else ""
        tipos_credito = TIPOS_NOTA_CREDITO + (-83,)

        if voucher_scope == -99:
            voucher_where_filter = ""
            voucher_ranking_filter = ""
        else:
            voucher_where_filter = "AND (ce.TotalOperacion - ce.TotalPagos) != 0"
            voucher_ranking_filter = (
                "WHERE (ov.rn_magnitud <= :voucher_limit OR :voucher_limit = -1)")

        query_case_2 = f"""
            WITH TargetClients AS (
                SELECT
                    idCliente, CodigoCliente, RazonSocial, CUIT, NumeroDocumento,
                    Telefonos, SaldoActual
                FROM clientes
                WHERE idEmpresa = :company_id AND SaldoActual != 0
                ORDER BY SaldoActual DESC
                {client_limit_sql}
            ),

            VoucherList AS (
                SELECT
                    ce.idCliente,
                    ce.FechaComprobante,
                    ce.FechaVencimientoPago,
                    ce.idTipoComprobante,
                    ce.idPuntoVenta,
                    ce.NumeroComprobante,
                    ce.TotalOperacion,

                    CASE
                        WHEN ce.idTipoComprobante IN {tipos_credito}
                        THEN (ce.TotalOperacion - ce.TotalPagos) * -1
                        ELSE (ce.TotalOperacion - ce.TotalPagos)
                    END AS SaldoVoucherFirmado,

                    ROW_NUMBER() OVER(
                        PARTITION BY ce.idCliente
                        ORDER BY (ce.TotalOperacion - ce.TotalPagos) DESC
                    ) as rn_magnitud

                FROM comprobanteemitido ce
                WHERE ce.idEmpresa = :company_id
                    AND ce.Anulado = 0
                    AND ce.idCliente IN (SELECT idCliente FROM TargetClients)
                    {voucher_where_filter}
            )

            SELECT
                ov.FechaComprobante AS 'Fecha',
                tc.CodigoCliente AS 'Código Cliente',
                tc.RazonSocial AS 'Cliente',
                CASE
                    WHEN ov.idTipoComprobante = 1 THEN 'FC A'
                    WHEN ov.idTipoComprobante = 6 THEN 'FC B'
                    WHEN ov.idTipoComprobante = 3 THEN 'NC A'
                    WHEN ov.idTipoComprobante = 8 THEN 'NC B'
                    WHEN ov.idTipoComprobante = 11 THEN 'FC M'
                    WHEN ov.idTipoComprobante = 13 THEN 'NC M'
                    WHEN ov.idTipoComprobante = -81 THEN 'CO X'
                    WHEN ov.idTipoComprobante = -83 THEN 'RC X'
                    ELSE CAST(ov.idTipoComprobante AS CHAR)
                END AS 'T.C.',
                LPAD(ov.idPuntoVenta, 4, '0') AS 'Punto Venta',
                LPAD(ov.NumeroComprobante, 8, '0') AS 'N° Comprobante',
                ov.TotalOperacion AS 'Total Operación',
                ov.SaldoVoucherFirmado AS 'Saldo',
                DATEDIFF(CURDATE(),
                         COALESCE(ov.FechaVencimientoPago, ov.FechaComprobante))
                                        AS 'Días de Mora',
                tc.CUIT,
                tc.NumeroDocumento AS 'DNI',
                tc.Telefonos AS 'Teléfono',
                tc.SaldoActual AS 'Saldo Total Cliente'
            FROM TargetClients tc
            JOIN VoucherList ov ON tc.idCliente = ov.idCliente
            {voucher_ranking_filter}
            ORDER BY
                tc.SaldoActual DESC,
                tc.idCliente,
                ov.FechaComprobante ASC;
        """

        return self.db_manager._execute_query(query_case_2, params)

    def get_aging_cuenta_corriente(self, company_id, limit=-1):
        """Deuda abierta repartida por antigüedad (AUDITORIA.md §3.4).

        El informe de cuenta corriente dice cuánto debe cada cliente, pero no
        hace cuánto. En un corralón que le fía a constructoras, esa es la
        diferencia entre "paga a 30 días" y "plata perdida".
        """
        tipos_credito = TIPOS_NOTA_CREDITO + (-83,)
        query = f"""
            WITH SaldosAbiertos AS (
                SELECT
                    ce.idCliente,
                    COALESCE(ce.FechaVencimientoPago, ce.FechaComprobante) AS Vence,
                    CASE WHEN ce.idTipoComprobante IN {tipos_credito} THEN -1 ELSE 1 END
                        * (ce.TotalOperacion - ce.TotalPagos) AS Saldo
                FROM comprobanteemitido ce
                WHERE ce.idEmpresa = :company_id
                  AND ce.Anulado = 0
                  AND ce.idCliente IS NOT NULL
                  AND (ce.TotalOperacion - ce.TotalPagos) <> 0
            )
            SELECT
                cli.CodigoCliente AS 'Código',
                cli.RazonSocial AS 'Cliente',
                cli.Telefonos AS 'Teléfono',
                cli.SaldoActual AS 'Saldo Total',
                SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) <= 0
                         THEN s.Saldo ELSE 0 END) AS 'Por vencer',
                SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) BETWEEN 1 AND 30
                         THEN s.Saldo ELSE 0 END) AS '1 a 30 días',
                SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) BETWEEN 31 AND 60
                         THEN s.Saldo ELSE 0 END) AS '31 a 60 días',
                SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) BETWEEN 61 AND 90
                         THEN s.Saldo ELSE 0 END) AS '61 a 90 días',
                SUM(CASE WHEN DATEDIFF(CURDATE(), s.Vence) > 90
                         THEN s.Saldo ELSE 0 END) AS 'Más de 90 días',
                MAX(DATEDIFF(CURDATE(), s.Vence)) AS 'Mora Máxima (días)'
            FROM SaldosAbiertos s
            JOIN clientes cli ON cli.idCliente = s.idCliente
            WHERE cli.idEmpresa = :company_id
            GROUP BY cli.idCliente, cli.CodigoCliente, cli.RazonSocial,
                     cli.Telefonos, cli.SaldoActual
            HAVING `Saldo Total` <> 0
            ORDER BY `Más de 90 días` DESC, `Saldo Total` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(
            query, {"company_id": company_id, "limit": limit})

    # ------------------------------------------------------------------ #
    # Rentabilidad y rotación (informes nuevos)
    # ------------------------------------------------------------------ #

    def get_margin_by_article(self, company_id, limit=20, days=90):
        """Margen bruto por artículo (AUDITORIA.md §3.1).

        El costo que se usa es `articulos.PrecioCosto`, o sea el de HOY, no el
        del momento de la venta. Con inflación alta eso subestima el margen de
        las ventas viejas: el informe lo aclara en pantalla.
        """
        signo = SIGNO_VENTA('ce')
        query = f"""
            SELECT
                a.CodigoArticulo AS 'Código',
                a.Descripcion AS 'Descripción',
                SUM(cei.Cantidad * {signo}) AS 'Unidades',
                SUM(cei.TotalItemSinIVA * {signo}) AS 'Facturado s/IVA',
                SUM(cei.Cantidad * a.PrecioCosto * {signo}) AS 'Costo Estimado',
                SUM((cei.TotalItemSinIVA - cei.Cantidad * a.PrecioCosto) * {signo})
                    AS 'Margen Bruto ($)',
                ROUND(100 * SUM((cei.TotalItemSinIVA - cei.Cantidad * a.PrecioCosto) * {signo})
                          / NULLIF(SUM(cei.TotalItemSinIVA * {signo}), 0), 1)
                    AS '% Margen',
                a.ExistenciaActual AS 'Stock'
            FROM comprobanteemitidoitems cei
            JOIN articulos a ON cei.idArticulo = a.idArticulo
            JOIN comprobanteemitido ce ON cei.idComprobanteEmitido = ce.idComprobanteEmitido
            WHERE ce.idEmpresa = :company_id
            {FILTRO_VENTA('ce')}
            {self._get_date_filter(days, 'ce')}
            GROUP BY a.idArticulo, a.CodigoArticulo, a.Descripcion, a.ExistenciaActual
            HAVING `Facturado s/IVA` > 0
            ORDER BY `Margen Bruto ($)` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(
            query, {"company_id": company_id, "limit": limit, "days": days})

    def get_margin_chart(self, company_id, limit=20, days=90):
        """Las dos columnas que el graficador de barras sabe dibujar."""
        df = self.get_margin_by_article(company_id, limit, days)
        if df is None or df.empty:
            return pd.DataFrame()
        return df[['Descripción', 'Margen Bruto ($)']].copy()

    def get_abc_analysis(self, company_id, days=365):
        """Curva ABC de artículos por facturación (AUDITORIA.md §3.2).

        A = el 80% de la facturación, B = hasta el 95%, C = la cola. Con 5.000 a
        20.000 SKU, es lo que dice a qué prestarle atención.
        """
        signo = SIGNO_VENTA('ce')
        query = f"""
            WITH VentasArt AS (
                SELECT
                    cei.idArticulo,
                    SUM(cei.TotalItemSinIVA * {signo}) AS Facturado,
                    SUM(cei.Cantidad * {signo}) AS Unidades,
                    COUNT(DISTINCT ce.idComprobanteEmitido) AS Tickets
                FROM comprobanteemitidoitems cei
                JOIN comprobanteemitido ce
                     ON cei.idComprobanteEmitido = ce.idComprobanteEmitido
                WHERE ce.idEmpresa = :company_id
                  AND cei.idArticulo IS NOT NULL
                {FILTRO_VENTA('ce')}
                {self._get_date_filter(days, 'ce')}
                GROUP BY cei.idArticulo
                HAVING Facturado > 0
            ),
            Acum AS (
                SELECT
                    va.*,
                    SUM(va.Facturado) OVER (ORDER BY va.Facturado DESC
                                            ROWS UNBOUNDED PRECEDING)
                      / NULLIF(SUM(va.Facturado) OVER (), 0) AS PctAcum,
                    ROW_NUMBER() OVER (ORDER BY va.Facturado DESC) AS Ranking
                FROM VentasArt va
            )
            SELECT
                ac.Ranking AS '#',
                a.CodigoArticulo AS 'Código',
                a.Descripcion AS 'Descripción',
                ac.Unidades AS 'Unidades',
                ac.Tickets AS 'Tickets',
                ac.Facturado AS 'Facturado s/IVA',
                ROUND(100 * ac.PctAcum, 1) AS '% Acumulado',
                CASE WHEN ac.PctAcum <= 0.80 THEN 'A'
                     WHEN ac.PctAcum <= 0.95 THEN 'B'
                     ELSE 'C' END AS 'Clase',
                a.ExistenciaActual AS 'Stock',
                ROUND(a.ExistenciaActual * a.PrecioCosto, 2) AS 'Capital Inmovilizado'
            FROM Acum ac
            JOIN articulos a ON a.idArticulo = ac.idArticulo
            ORDER BY ac.Ranking;
        """
        return self.db_manager._execute_query(
            query, {"company_id": company_id, "days": days})

    def get_abc_summary_chart(self, company_id, days=365):
        """Conteo de artículos por clase, para el gráfico del PDF."""
        df = self.get_abc_analysis(company_id, days)
        if df is None or df.empty:
            return pd.DataFrame()
        resumen = (df.groupby('Clase')['Código'].count()
                     .reindex(['A', 'B', 'C'], fill_value=0)
                     .reset_index())
        resumen.columns = ['Clase ABC', 'Cantidad de Artículos']
        return resumen

    def get_purchase_suggestion(self, company_id, days=90, dias_objetivo=30):
        """Qué reponer y a qué proveedor pedírselo (AUDITORIA.md §3.3).

        En una ferretería se compra por proveedor, por flete y por mínimo de
        compra, así que el informe sale agrupado por proveedor y no por artículo.
        """
        dias = self._dias_efectivos(company_id, days)
        signo = SIGNO_VENTA('ce')
        query = f"""
            WITH Consumo AS (
                SELECT cei.idArticulo,
                       SUM(cei.Cantidad * {signo}) AS Unidades
                FROM comprobanteemitidoitems cei
                JOIN comprobanteemitido ce
                     ON cei.idComprobanteEmitido = ce.idComprobanteEmitido
                WHERE ce.idEmpresa = :company_id
                {FILTRO_VENTA('ce')}
                {self._get_date_filter(days, 'ce')}
                GROUP BY cei.idArticulo
            )
            SELECT
                COALESCE(p.RazonSocial, 'SIN PROVEEDOR ASIGNADO') AS 'Proveedor',
                a.CodigoArticulo AS 'Código',
                a.Descripcion AS 'Descripción',
                a.ExistenciaActual AS 'Stock',
                a.ExistenciaMinima AS 'Mínimo',
                ROUND(COALESCE(c.Unidades, 0) / :dias, 2) AS 'Venta Diaria',
                CASE WHEN COALESCE(c.Unidades, 0) <= 0 THEN NULL
                     ELSE FLOOR(a.ExistenciaActual / (c.Unidades / :dias))
                END AS 'Días de Cobertura',
                GREATEST(
                    CEIL(COALESCE(c.Unidades, 0) / :dias * :dias_objetivo
                         - a.ExistenciaActual),
                    CEIL(a.ExistenciaMinima - a.ExistenciaActual),
                    0
                ) AS 'Sugerido a Comprar',
                a.PrecioCosto AS 'Costo Unitario',
                ROUND(GREATEST(
                    CEIL(COALESCE(c.Unidades, 0) / :dias * :dias_objetivo
                         - a.ExistenciaActual),
                    CEIL(a.ExistenciaMinima - a.ExistenciaActual),
                    0
                ) * a.PrecioCosto, 2) AS 'Costo Estimado',
                a.FechaUltimaCompra AS 'Última Compra'
            FROM articulos a
            LEFT JOIN proveedores p ON p.idProveedor = a.idProveedor
            LEFT JOIN Consumo c ON c.idArticulo = a.idArticulo
            WHERE a.idEmpresa = :company_id AND a.Activo = 1
            HAVING `Sugerido a Comprar` > 0
            ORDER BY `Proveedor` ASC, `Costo Estimado` DESC;
        """
        return self.db_manager._execute_query(query, {
            "company_id": company_id,
            "days": days,
            "dias": dias,
            "dias_objetivo": int(dias_objetivo),
        })

    # ------------------------------------------------------------------ #
    # RFM
    # ------------------------------------------------------------------ #

    @staticmethod
    def _quintil(serie, invertir=False):
        """Puntaje 1-5 por quintiles, tolerante a pocos datos y a empates.

        `pd.qcut(..., 5, labels=[...])` levanta ValueError cuando se colapsan
        bins, que es justo lo que pasa en una ferretería de barrio donde casi
        todos los clientes compraron una sola vez. Se va bajando la cantidad de
        grupos hasta que entre.
        """
        etiquetas = [5, 4, 3, 2, 1] if invertir else [1, 2, 3, 4, 5]
        rank = serie.rank(method='first')
        # Se baja hasta 2 grupos, no hasta 1: con un solo grupo todos caerían en
        # el extremo de la escala y el único cliente de una ferretería chica
        # quedaría marcado como "Perdido". Sin al menos dos grupos no hay
        # comparación posible y el puntaje honesto es el del medio.
        for n in (5, 4, 3, 2):
            try:
                labs = etiquetas[-n:] if invertir else etiquetas[:n]
                return pd.qcut(rank, n, labels=labs).astype(int)
            except (ValueError, IndexError):
                continue
        return pd.Series(3, index=serie.index, dtype='int64')

    def get_rfm_analysis_data(self, company_id, days=-1):
        """Segmentación por Recencia, Frecuencia y Monto."""
        query = f"""
            SELECT
                ce.idCliente,
                cli.RazonSocial,
                cli.Telefonos,
                cli.Email,
                DATEDIFF(CURDATE(), MAX(ce.FechaComprobante)) AS Recencia,
                COUNT(DISTINCT ce.idComprobanteEmitido) AS Frecuencia,
                SUM(ce.TotalOperacion * {SIGNO_VENTA('ce')}) AS Monetario
            FROM comprobanteemitido ce
            JOIN clientes cli ON ce.idCliente = cli.idCliente
            WHERE ce.idEmpresa = :company_id
              AND (cli.CodigoCliente IS NULL OR cli.CodigoCliente <> '0')
            {FILTRO_VENTA('ce')}
            {self._get_date_filter(days, 'ce')}
            GROUP BY ce.idCliente, cli.RazonSocial, cli.Telefonos, cli.Email
            HAVING Monetario > 0;
        """
        df_rfm = self.db_manager._execute_query(
            query, {"company_id": company_id, "days": days})

        if df_rfm.empty:
            return pd.DataFrame(), pd.Series(dtype='int64')

        df_rfm['R_Score'] = self._quintil(df_rfm['Recencia'], invertir=True)
        df_rfm['F_Score'] = self._quintil(df_rfm['Frecuencia'])
        df_rfm['M_Score'] = self._quintil(df_rfm['Monetario'])

        df_rfm['RFM_Score_Text'] = (df_rfm['R_Score'].astype(str)
                                    + df_rfm['F_Score'].astype(str)
                                    + df_rfm['M_Score'].astype(str))

        df_rfm['SGM_Campeones'] = (df_rfm['R_Score'] >= 4) & (df_rfm['F_Score'] >= 4)
        df_rfm['SGM_Leales'] = ((df_rfm['R_Score'] >= 3) & (df_rfm['F_Score'] >= 3)
                                & ~df_rfm['SGM_Campeones'])
        df_rfm['SGM_Potenciales'] = (df_rfm['R_Score'] >= 4) & (df_rfm['F_Score'] <= 2)
        df_rfm['SGM_EnRiesgo'] = (df_rfm['R_Score'] <= 2) & (df_rfm['F_Score'] >= 3)
        df_rfm['SGM_Perdidos'] = (df_rfm['R_Score'] <= 2) & (df_rfm['F_Score'] <= 2)
        df_rfm['SGM_Nuevos'] = (df_rfm['R_Score'] == 5) & (df_rfm['F_Score'] == 1)
        df_rfm['SGM_Prometedores'] = (df_rfm['R_Score'] >= 4) & (df_rfm['F_Score'] == 3)
        df_rfm['SGM_NecesitanAtencion'] = (df_rfm['R_Score'] == 3) & (df_rfm['F_Score'] >= 2)

        segment_counts = pd.Series({
            'Campeones': df_rfm['SGM_Campeones'].sum(),
            'Leales': df_rfm['SGM_Leales'].sum(),
            'Potenciales': df_rfm['SGM_Potenciales'].sum(),
            'En Riesgo': df_rfm['SGM_EnRiesgo'].sum(),
            'Perdidos': df_rfm['SGM_Perdidos'].sum(),
            'Nuevos': df_rfm['SGM_Nuevos'].sum(),
            'Prometedores': df_rfm['SGM_Prometedores'].sum(),
            'Necesitan Atención': df_rfm['SGM_NecesitanAtencion'].sum()
        }, dtype='int64')

        return df_rfm, segment_counts

    # ------------------------------------------------------------------ #
    # KPIs del panel de control
    # ------------------------------------------------------------------ #

    def get_kpi_sales_by_payment_last_7_days(self, company_id):
        """Cobros de los últimos 7 días, con la misma definición de medio de
        pago que usa el informe de Ventas (antes eran dos criterios distintos y
        los números no coincidían)."""
        medios = self._sql_medios_de_pago()
        columnas = ",\n                ".join(
            f"{expr} AS '{nombre}'" for nombre, expr in medios.items())

        query = f"""
            SELECT {columnas}
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id
            {FILTRO_VENTA('')}
              AND FechaComprobante >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
              AND FechaComprobante <= CURDATE();
        """
        df = self.db_manager._execute_query(query, {"company_id": company_id})
        if df.empty:
            return pd.DataFrame(columns=['MedioDePago', 'Total'])

        serie = df.iloc[0]
        salida = pd.DataFrame({
            'MedioDePago': serie.index,
            'Total': pd.to_numeric(serie.values, errors='coerce').astype(float),
        })
        salida = salida[salida['Total'].fillna(0) != 0]
        return salida.sort_values('Total', ascending=False).reset_index(drop=True)

    def get_kpi_rfm_risk_count(self, company_id):
        try:
            _, summary_counts = self.get_rfm_analysis_data(company_id)
            if summary_counts.empty:
                return 0
            return int(summary_counts.get('En Riesgo', 0)
                       + summary_counts.get('Perdidos', 0))
        except Exception as e:
            print(f"ERROR KPI RFM: {e}")
            return 0

    def get_kpi_total_debt(self, company_id):
        """Suma de los saldos deudores. Los saldos a favor no se netean: mezclar
        los dos escondería la deuda real detrás de los anticipos."""
        query = """
            SELECT SUM(SaldoActual)
            FROM clientes
            WHERE idEmpresa = :company_id AND SaldoActual > 0;
        """
        df = self.db_manager._execute_query(query, {"company_id": company_id})
        if df.empty or df.iloc[0, 0] is None:
            return 0.0
        return float(df.iloc[0, 0])

    def get_kpi_slob_value(self, company_id, threshold_days=180):
        query = """
            SELECT SUM(ExistenciaActual * PrecioCosto)
            FROM articulos
            WHERE idEmpresa = :company_id
              AND Activo = 1
              AND ((DATEDIFF(CURDATE(), FechaUltimaVenta) > :threshold_days)
                   OR (FechaUltimaVenta IS NULL))
              AND ExistenciaActual > 0;
        """
        df = self.db_manager._execute_query(
            query, {"company_id": company_id, "threshold_days": threshold_days})
        if df.empty or df.iloc[0, 0] is None:
            return 0.0
        return float(df.iloc[0, 0])

    def get_kpi_total_sales_last_30_days(self, company_id):
        query = f"""
            SELECT SUM(TotalOperacion * {SIGNO_VENTA('')})
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id
            {FILTRO_VENTA('')}
              AND FechaComprobante >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
              AND FechaComprobante <= CURDATE();
        """
        df = self.db_manager._execute_query(query, {"company_id": company_id})
        if df.empty or df.iloc[0, 0] is None:
            return 0.0
        return float(df.iloc[0, 0])
