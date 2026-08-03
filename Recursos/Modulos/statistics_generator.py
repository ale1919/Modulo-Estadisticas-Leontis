import pandas as pd
from sqlalchemy import text
from PySide6.QtWidgets import QMessageBox

class StatisticsGenerator:
    """
    Clase para generar todas las estadísticas y consultas a la base de datos
    necesarias para los informes de la aplicación.
    """
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def _get_date_filter(self, days, table_alias='ce', param_name='days'):
        """
        Genera el fragmento SQL para el filtro de fecha, con límite superior en el día de hoy.
        """
        if days == -1:
            return f" AND {table_alias}.FechaComprobante <= CURDATE()"
        
        if days == 1:
            return f" AND {table_alias}.FechaComprobante >= DATE_SUB(NOW(), INTERVAL 1 DAY) AND {table_alias}.FechaComprobante <= NOW()"
            
        return f" AND {table_alias}.FechaComprobante >= DATE_SUB(CURDATE(), INTERVAL :{param_name} DAY) AND {table_alias}.FechaComprobante <= CURDATE()"


    def get_top_articles_by_value(self, company_id, limit=10, days=90):
        query = f"""
            SELECT
                a.Descripcion AS Articulo,
                SUM(cei.TotalItemConIVA) AS 'Total Vendido ($)'
            FROM comprobanteemitidoitems cei
            JOIN articulos a ON cei.idArticulo = a.idArticulo
            JOIN comprobanteemitido ce ON cei.idComprobanteEmitido = ce.idComprobanteEmitido
            WHERE ce.idEmpresa = :company_id AND ce.Anulado = 0
            {self._get_date_filter(days, 'ce')}
            GROUP BY a.idArticulo, a.Descripcion
            ORDER BY `Total Vendido ($)` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"
        
        return self.db_manager._execute_query(query, {"company_id": company_id, "limit": limit, "days": days})

    def get_top_articles_by_quantity(self, company_id, limit=10, days=90):
        query = f"""
            SELECT
                a.Descripcion AS Articulo,
                SUM(cei.Cantidad) AS 'Cantidad Vendida'
            FROM comprobanteemitidoitems cei
            JOIN articulos a ON cei.idArticulo = a.idArticulo
            JOIN comprobanteemitido ce ON cei.idComprobanteEmitido = ce.idComprobanteEmitido
            WHERE ce.idEmpresa = :company_id AND ce.Anulado = 0
            {self._get_date_filter(days, 'ce')}
            GROUP BY a.idArticulo, a.Descripcion
            ORDER BY `Cantidad Vendida` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(query, {"company_id": company_id, "limit": limit, "days": days})
        
    def get_top_customers_by_billing(self, company_id, limit=10, include_final_consumer=False, days=90):
        query = f"""
            SELECT
                cli.RazonSocial AS Cliente,
                SUM(ce.TotalOperacion) AS 'Total Facturado ($)'
            FROM comprobanteemitido ce
            JOIN clientes cli ON ce.idCliente = cli.idCliente
            WHERE ce.idEmpresa = :company_id AND ce.Anulado = 0
            {self._get_date_filter(days, 'ce')}
        """
        if not include_final_consumer:
            query += " AND cli.CodigoCliente != '0'"
            
        query += """
            GROUP BY cli.idCliente, cli.RazonSocial
            ORDER BY `Total Facturado ($)` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(query, {"company_id": company_id, "limit": limit, "days": days})

    def get_sales_over_time(self, company_id, days=90):
        query = f"""
            SELECT
                DATE(FechaComprobante) AS Fecha,
                SUM(TotalOperacion) AS 'Total Ventas ($)'
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id AND Anulado = 0
            {self._get_date_filter(days, 'comprobanteemitido')}
            GROUP BY DATE(FechaComprobante)
            ORDER BY Fecha ASC;
        """
        return self.db_manager._execute_query(query, {"company_id": company_id, "days": days})
        
    def get_top_articles_for_excel(self, company_id, limit, days, order_by_value=True):
        order_expression = "SUM(cei.TotalItemConIVA)" if order_by_value else "SUM(cei.Cantidad)"
        query = f"""
            SELECT
                a.CodigoArticulo AS 'Código',
                a.Descripcion AS 'Descripción',
                a.PrecioCosto AS 'Precio Costo',
                a.Precio01Neto AS 'Precio Venta s/IVA',
                a.Precio01Final AS 'Precio Venta c/IVA',
                a.ExistenciaActual AS 'Stock',
                SUM(cei.Cantidad) AS 'Cantidad Vendida',
                SUM(cei.TotalItemConIVA) AS 'Total Vendido'
            FROM comprobanteemitidoitems cei
            JOIN articulos a ON cei.idArticulo = a.idArticulo
            JOIN comprobanteemitido ce ON cei.idComprobanteEmitido = ce.idComprobanteEmitido
            WHERE ce.idEmpresa = :company_id AND ce.Anulado = 0
            {self._get_date_filter(days, 'ce')}
            GROUP BY a.idArticulo, a.CodigoArticulo, a.Descripcion, a.PrecioCosto, a.Precio01Neto, a.Precio01Final, a.ExistenciaActual
            ORDER BY {order_expression} DESC
        """
        if limit != -1:
            query += " LIMIT :limit"
        
        return self.db_manager._execute_query(query, {"company_id": company_id, "limit": limit, "days": days})

    def get_top_clients_for_excel(self, company_id, limit, include_final_consumer, days):
        query = f"""
            SELECT
                cli.CodigoCliente AS 'Código Cliente',
                cli.RazonSocial AS 'Razón Social',
                SUM(ce.TotalOperacion) AS 'Total Facturado',
                cli.SaldoActual AS 'Saldo Pendiente'
            FROM comprobanteemitido ce
            JOIN clientes cli ON ce.idCliente = cli.idCliente
            WHERE ce.idEmpresa = :company_id AND ce.Anulado = 0
            {self._get_date_filter(days, 'ce')}
        """
        if not include_final_consumer:
            query += " AND cli.CodigoCliente != '0'"
            
        query += """
            GROUP BY cli.idCliente, cli.CodigoCliente, cli.RazonSocial, cli.SaldoActual
            ORDER BY `Total Facturado` DESC
        """
        if limit != -1:
            query += " LIMIT :limit"
            
        return self.db_manager._execute_query(query, {"company_id": company_id, "limit": limit, "days": days})

    def get_sales_by_day_for_excel(self, company_id, days, payment_methods):
        query = f"""
            SELECT
                DATE(FechaComprobante) AS Fecha,
                SUM(PagoEfectivo) AS 'Efectivo',
                SUM(CASE WHEN IdMedioDePago = 2 THEN TotalOperacion ELSE 0 END) AS 'Tarjeta',
                SUM(PagoCheques) AS 'Cheque',
                SUM(CASE WHEN IdMedioDePago NOT IN (1, 2, 4) AND PagoEfectivo = 0 AND PagoCheques = 0 THEN TotalOperacion ELSE 0 END) AS 'Otros',
                SUM(TotalOperacion) AS 'Total'
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id AND Anulado = 0
            {self._get_date_filter(days, 'comprobanteemitido')}
            GROUP BY DATE(FechaComprobante)
            ORDER BY Fecha ASC;
        """
        df = self.db_manager._execute_query(query, {"company_id": company_id, "days": days})
        
        if df is not None and not df.empty:
            cols_to_keep = ['Fecha'] + payment_methods + ['Total']
            existing_cols = [col for col in cols_to_keep if col in df.columns]
            return df[existing_cols]
        return df
        
    def get_sales_by_payment_method_for_chart(self, company_id, days, payment_methods):
        if not payment_methods:
            return pd.DataFrame()
        
        select_clauses = []
        if 'Efectivo' in payment_methods:
            select_clauses.append("SUM(PagoEfectivo) AS 'Efectivo'")
        if 'Tarjeta' in payment_methods:
            select_clauses.append("SUM(CASE WHEN IdMedioDePago = 2 THEN TotalOperacion ELSE 0 END) AS 'Tarjeta'")
        if 'Cheque' in payment_methods:
            select_clauses.append("SUM(PagoCheques) AS 'Cheque'")
        if 'Otros' in payment_methods:
            select_clauses.append("SUM(CASE WHEN IdMedioDePago NOT IN (1, 2, 4) AND PagoEfectivo = 0 AND PagoCheques = 0 THEN TotalOperacion ELSE 0 END) AS 'Otros'")
            
        if not select_clauses:
             return pd.DataFrame()

        query = f"""
            SELECT
                DATE(FechaComprobante) AS Fecha,
                {', '.join(select_clauses)}
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id AND Anulado = 0
            {self._get_date_filter(days, 'comprobanteemitido')}
            GROUP BY Fecha
            ORDER BY Fecha ASC;
        """
        
        df = self.db_manager._execute_query(query, {'company_id': company_id, 'days': days})
        
        if df is not None and not df.empty:
            df.set_index('Fecha', inplace=True)
            return df
        return pd.DataFrame()

    def get_stock_data_for_excel(self, company_id, option, limit):
        query = "SELECT CodigoArticulo AS 'Código', Descripcion AS 'Descripción', ExistenciaActual AS 'Stock' FROM articulos WHERE idEmpresa = :company_id"
        
        if option == "top_mas_stock":
            query += " ORDER BY Stock DESC"
        elif option == "top_menos_stock":
            query += " AND ExistenciaActual > 0 ORDER BY Stock ASC"
        elif option == "cero_negativo":
            query += " AND ExistenciaActual <= 0 ORDER BY Stock ASC"
        elif option == "todos_stock":
            query += " ORDER BY Descripcion ASC"
        
        if option in ["top_mas_stock", "top_menos_stock"] and limit != -1:
            query += " LIMIT :limit"

        return self.db_manager._execute_query(query, {"company_id": company_id, "limit": limit})


    def get_all_articles_for_dropdown(self, company_id):
        """
        Obtiene todos los artículos activos, incluyendo su código, para el modal
        de búsqueda del análisis de canasta.
        """
        query = """
            SELECT idArticulo, Descripcion, CodigoArticulo 
            FROM articulos 
            WHERE idEmpresa = :company_id AND Activo = 1 
            ORDER BY Descripcion ASC;
        """
        return self.db_manager._execute_query(query, {"company_id": company_id})

    def get_market_basket_analysis(self, company_id, days, mode, association_limit, manual_article_ids=[]):
        """
        Ejecuta el análisis de canasta de mercado.
        - Modo 'manual': Filtra por una lista de IDs de artículos.
        - Modo numérico (10, 20, 50): Devuelve el Top N de artículos con más asociaciones.
        - association_limit: Limita cuántos artículos asociados se muestran en el resultado.
        """
        date_filter_sql = self._get_date_filter(days, 'ce', param_name='basket_days')
        
        params = {
            "company_id": company_id,
            "assoc_limit": association_limit
        }
        if days > 1:
            params["basket_days"] = days

        common_ctes = f"""
            WITH ValidTransactions AS (
                SELECT DISTINCT ce.idComprobanteEmitido
                FROM comprobanteemitido ce
                WHERE ce.idEmpresa = :company_id AND ce.Anulado = 0
                {date_filter_sql}
            ),
            ItemPairs AS (
                SELECT 
                    i1.idArticulo AS ArticuloA,
                    i2.idArticulo AS ArticuloB,
                    COUNT(DISTINCT i1.idComprobanteEmitido) AS Frecuencia
                FROM comprobanteemitidoitems i1
                JOIN comprobanteemitidoitems i2 ON i1.idComprobanteEmitido = i2.idComprobanteEmitido
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
                    SUM(Frecuencia) AS TotalAsociaciones
                FROM UnpivotedAssociations
                GROUP BY idArticulo
            )
        """

        if mode == 'manual':
            if not manual_article_ids:
                return pd.DataFrame()
                
            params["manual_ids"] = tuple(manual_article_ids)
            
            query = f"""
                {common_ctes}
                SELECT 
                    art_main.CodigoArticulo AS 'Código',
                    art_main.Descripcion AS 'Descripción',
                    art_main.Precio01Neto AS 'Precio sin IVA',
                    (art_main.Precio01Final - art_main.Precio01Neto) AS 'IVA',
                    art_main.Precio01Final AS 'Precio Final',
                    COALESCE(fta.ArticulosAsociados, 'Sin asociaciones en el período') AS 'Artículos Asociados',
                    COALESCE(ta.TotalAsociaciones, 0) AS 'Nro. Asociaciones'
                FROM articulos art_main
                LEFT JOIN FilteredTextAssociations fta ON art_main.idArticulo = fta.idArticulo
                LEFT JOIN TotalAssociations ta ON art_main.idArticulo = ta.idArticulo
                WHERE art_main.idEmpresa = :company_id AND art_main.Activo = 1
                  AND art_main.idArticulo IN :manual_ids
                ORDER BY `Nro. Asociaciones` DESC, art_main.Descripcion ASC
            """
            return self.db_manager._execute_query(query, params)

        else:
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
                    ta.TotalAsociaciones AS 'Nro. Asociaciones'
                FROM TotalAssociations ta 
                JOIN articulos art_main ON ta.idArticulo = art_main.idArticulo
                LEFT JOIN FilteredTextAssociations fta ON ta.idArticulo = fta.idArticulo
                WHERE art_main.idEmpresa = :company_id AND art_main.Activo = 1
                ORDER BY ta.TotalAsociaciones DESC, art_main.Descripcion ASC
                LIMIT :limit
            """
            return self.db_manager._execute_query(query, params)

    def get_export_all_clients(self, company_id, mode):
        """
        Obtiene todos los clientes para la exportación rápida de Excel, 
        según el modo (solo activos o todos).
        """
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
        """
        Obtiene todos los artículos para la exportación rápida de Excel, 
        según el modo (solo activos o todos).
        """
        select_list = [
            "a.CodigoArticulo AS 'Codigo-Articulo'", "a.CodigoDeBarras", "a.Codigo01", "a.Descripcion",
            "a.PorcentajeIVA", "a.PorcentajeMarcacion1", "a.ExistenciaActual", "a.PrecioCosto",
            "a.ImpuestosInternos", "a.DescuentoProveedor", "a.Precio01Neto", "a.Precio01Final"
        ]
        
        where_clause = "WHERE a.idEmpresa = :company_id"
        if mode == 'activos':
            where_clause += " AND a.Activo = 1"
        else:
            select_list.insert(2, "a.Activo")

        query = f"""
            SELECT {', '.join(select_list)}
            FROM articulos a
            {where_clause}
            ORDER BY a.Descripcion;
        """
        return self.db_manager._execute_query(query, {"company_id": company_id})

    def get_customer_debt_for_chart(self, company_id, limit):
        """
        Obtiene los clientes deudores para el gráfico de barras.
        """
        query = """
            SELECT
                cli.RazonSocial AS Cliente,
                cli.SaldoActual AS 'Saldo Adeudado ($)'
            FROM clientes cli
            WHERE cli.idEmpresa = :company_id AND cli.SaldoActual != 0
            ORDER BY cli.SaldoActual DESC
        """
        if limit != -1:
            query += " LIMIT :limit"
        
        return self.db_manager._execute_query(query, {"company_id": company_id, "limit": limit})

    def get_customer_debt_for_excel(self, company_id, client_limit, voucher_scope):
        """
        Obtiene el análisis detallado de Cta. Cte. para Excel.
        """
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
                    cli.SaldoActual AS 'Saldo Total Adeudado'
                FROM clientes cli
                WHERE cli.idEmpresa = :company_id AND cli.SaldoActual != 0
                ORDER BY cli.SaldoActual DESC
            """
            if client_limit != -1:
                query_case_1 += " LIMIT :client_limit"
            
            return self.db_manager._execute_query(query_case_1, params)

        client_limit_sql = "LIMIT :client_limit" if client_limit != -1 else ""
        
        CREDIT_TYPES_TUPLE = "(3, 8, 13, -83)"

        voucher_where_filter = ""
        voucher_ranking_filter = ""

        if voucher_scope == -99: 
            voucher_where_filter = "AND 1=1"
            voucher_ranking_filter = "WHERE 1=1"
        else:
            voucher_where_filter = "AND (ce.TotalOperacion - ce.TotalPagos) != 0"
            voucher_ranking_filter = "WHERE (ov.rn_magnitud <= :voucher_limit OR :voucher_limit = -1)"


        query_case_2 = f"""
            WITH TargetClients AS (
                SELECT 
                    idCliente, CodigoCliente, RazonSocial, CUIT, NumeroDocumento, SaldoActual
                FROM clientes
                WHERE idEmpresa = :company_id AND SaldoActual != 0
                ORDER BY SaldoActual DESC
                {client_limit_sql} 
            ),
            
            VoucherList AS (
                SELECT
                    ce.idCliente,
                    ce.FechaComprobante,
                    ce.idTipoComprobante,
                    ce.idPuntoVenta,
                    ce.NumeroComprobante,
                    ce.TotalOperacion,
                    
                    CASE 
                        WHEN ce.idTipoComprobante IN {CREDIT_TYPES_TUPLE}
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
                tc.CUIT,
                tc.NumeroDocumento AS 'DNI',
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
    
    def get_slob_analysis_for_excel(self, company_id, threshold_days):
        """
        Identifica artículos con stock positivo que no han tenido ventas
        recientes o que nunca se han vendido.
        """
        
        query = """
            SELECT
                CodigoArticulo AS 'Código',
                Descripcion AS 'Descripción',
                ExistenciaActual AS 'Stock Actual',
                FechaUltimaVenta AS 'Última Venta',
                (ExistenciaActual * PrecioCosto) AS 'Valor Inmovilizado ($)'
            FROM
                articulos
            WHERE
                idEmpresa = :company_id
                AND (
                    (DATEDIFF(CURDATE(), FechaUltimaVenta) > :threshold_days) 
                    OR 
                    (FechaUltimaVenta IS NULL)
                )
                AND ExistenciaActual > 0
            ORDER BY
                `Valor Inmovilizado ($)` DESC;
        """
        
        params = {
            "company_id": company_id,
            "threshold_days": int(threshold_days) 
        }
        
        df = self.db_manager._execute_query(query, params)

        if df.empty:
            placeholder_data = {
                'Código': ['-'],
                'Descripción': ["No hay articulos que cumplan con las condiciones de busqueda"],
                'Stock Actual': [0],
                'Última Venta': [None],
                'Valor Inmovilizado ($)': [0]
            }
            return pd.DataFrame(placeholder_data)
            
        return df
    
    def get_rfm_analysis_data(self, company_id):
        """
        Realiza el análisis RFM completo (Recencia, Frecuencia, Monetario).
        """
        query = """
            SELECT
                ce.idCliente,
                cli.RazonSocial,
                cli.Telefonos,
                cli.Email,
                DATEDIFF(CURDATE(), MAX(ce.FechaComprobante)) AS Recencia,
                COUNT(DISTINCT ce.idComprobanteEmitido) AS Frecuencia,
                SUM(ce.TotalOperacion) AS Monetario
            FROM
                comprobanteemitido ce
            JOIN
                clientes cli ON ce.idCliente = cli.idCliente
            WHERE
                ce.idEmpresa = :company_id
                AND ce.Anulado = 0
                AND cli.CodigoCliente != '0'
            GROUP BY
                ce.idCliente, cli.RazonSocial, cli.Telefonos, cli.Email
            HAVING
                SUM(ce.TotalOperacion) > 0;
        """
        df_rfm = self.db_manager._execute_query(query, {"company_id": company_id})
    
        if df_rfm.empty:
            print("DEBUG RFM: No se encontraron datos de clientes para segmentar.")
            return pd.DataFrame(), pd.Series(dtype='int64')
    
        print(f"DEBUG RFM: Calculando quintiles para {len(df_rfm)} clientes identificados.")
    
        try:
            df_rfm['R_Score'] = pd.qcut(df_rfm['Recencia'], 5, labels=[5, 4, 3, 2, 1], duplicates='drop').astype(int)
            df_rfm['F_Score'] = pd.qcut(df_rfm['Frecuencia'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5]).astype(int)
            df_rfm['M_Score'] = pd.qcut(df_rfm['Monetario'], 5, labels=[1, 2, 3, 4, 5]).astype(int)
        except Exception as e:
            print(f"WARN RFM: El cálculo de quintiles falló ({e}). Usando ranking denso como fallback.")
            df_rfm['R_Score'] = pd.qcut(df_rfm['Recencia'].rank(method='dense'), 5, labels=[5, 4, 3, 2, 1], duplicates='drop').astype(int)
            df_rfm['F_Score'] = pd.qcut(df_rfm['Frecuencia'].rank(method='dense'), 5, labels=[1, 2, 3, 4, 5], duplicates='drop').astype(int)
            df_rfm['M_Score'] = pd.qcut(df_rfm['Monetario'].rank(method='dense'), 5, labels=[1, 2, 3, 4, 5], duplicates='drop').astype(int)
    
        df_rfm['RFM_Score_Text'] = df_rfm['R_Score'].astype(str) + df_rfm['F_Score'].astype(str) + df_rfm['M_Score'].astype(str)
    
        df_rfm['SGM_Campeones'] = (df_rfm['R_Score'] >= 4) & (df_rfm['F_Score'] >= 4)
        df_rfm['SGM_Leales'] = (df_rfm['R_Score'] >= 3) & (df_rfm['F_Score'] >= 3) & ~df_rfm['SGM_Campeones']
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
    
        print("DEBUG RFM: Segmentación completada con matriz RFM clásica.")
    
        return df_rfm, segment_counts

    def get_kpi_sales_by_payment_last_7_days(self, company_id):
        """
        Devuelve un DataFrame con el total facturado por medio de pago
        en los últimos 7 días.
        """
        query = """
            SELECT 
                CASE 
                    WHEN PagoEfectivo > 0 AND (IdMedioDePago = 1 OR IdMedioDePago IS NULL) THEN 'Efectivo'
                    WHEN IdMedioDePago = 2 THEN 'Tarjeta'
                    WHEN PagoCheques > 0 OR IdMedioDePago = 4 THEN 'Cheque'
                    ELSE 'Otros' 
                END AS MedioDePago,
                SUM(TotalOperacion) AS Total
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id AND Anulado = 0
              AND FechaComprobante >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY MedioDePago
            ORDER BY Total DESC;
        """
        return self.db_manager._execute_query(query, {"company_id": company_id})

    def get_kpi_rfm_risk_count(self, company_id):
        """
        Obtiene el conteo total de clientes en segmentos de riesgo.
        """
        try:
            _ , summary_counts = self.get_rfm_analysis_data(company_id)
            if summary_counts.empty:
                return 0
            
            risk_count = summary_counts.get('En Riesgo', 0) + summary_counts.get('Perdidos', 0)
            return int(risk_count)
        except Exception as e:
            print(f"ERROR KPI RFM: {e}")
            return 0

    def get_kpi_total_debt(self, company_id):
        """Devuelve el SUM total de SaldoActual de todos los clientes."""
        query = """
            SELECT SUM(SaldoActual) 
            FROM clientes 
            WHERE idEmpresa = :company_id AND SaldoActual != 0;
        """
        df = self.db_manager._execute_query(query, {"company_id": company_id})
        if df.empty or df.iloc[0, 0] is None:
            return 0.0
        return float(df.iloc[0, 0])

    def get_kpi_slob_value(self, company_id, threshold_days=180):
        """Devuelve el valor SUM total del stock obsoleto (SLOB)."""
        query = """
            SELECT SUM(ExistenciaActual * PrecioCosto)
            FROM articulos
            WHERE
                idEmpresa = :company_id
                AND (
                    (DATEDIFF(CURDATE(), FechaUltimaVenta) > :threshold_days) 
                    OR 
                    (FechaUltimaVenta IS NULL)
                )
                AND ExistenciaActual > 0;
        """
        params = {"company_id": company_id, "threshold_days": threshold_days}
        df = self.db_manager._execute_query(query, params)
        if df.empty or df.iloc[0, 0] is None:
            return 0.0
        return float(df.iloc[0, 0])

    def get_kpi_total_sales_last_30_days(self, company_id):
        """Devuelve el SUM total de TotalOperacion de los últimos 30 días."""
        query = """
            SELECT SUM(TotalOperacion) 
            FROM comprobanteemitido
            WHERE idEmpresa = :company_id AND Anulado = 0
              AND FechaComprobante >= DATE_SUB(CURDATE(), INTERVAL 30 DAY);
        """
        df = self.db_manager._execute_query(query, {"company_id": company_id})
        if df.empty or df.iloc[0, 0] is None:
            return 0.0
        return float(df.iloc[0, 0])
