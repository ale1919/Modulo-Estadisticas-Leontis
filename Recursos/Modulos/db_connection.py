"""Conexión a la base y orquestación de los informes."""

import re
import urllib.parse

import pandas as pd
from PySide6.QtWidgets import QMessageBox
from sqlalchemy import create_engine, text
from sqlalchemy.sql.elements import TextClause

from .rutas import log

_log = log("db")


def _ocultar_password(texto):
    """Tapa la contraseña de una URL o cadena de conexión antes de loguearla."""
    texto = re.sub(r"(://[^:/@]+:)[^@]*(@)", r"\1***\2", str(texto))
    texto = re.sub(r"(?i)\b(pwd|password)\s*=\s*[^;]*", r"\1=***", texto)
    return texto


class DBManager:
    def __init__(self):
        self.server_engine = None
        self.db_engine = None
        self.db_type = None
        # Última falla de consulta, para que la capa de UI pueda mostrarla. El
        # driver corre en un hilo secundario y desde ahí no se pueden crear
        # widgets de Qt.
        self.last_error = None

    def _execute_query(self, query, params=None):
        """Ejecuta una consulta y devuelve un DataFrame.

        NO abre ventanas: esto lo llama también el DashboardWorker desde un
        QThread, y crear un QMessageBox fuera del hilo de la GUI es
        comportamiento indefinido (en Windows suele cerrar la app sin decir
        nada). El error queda en `last_error` y en el log; quien decide cómo
        mostrarlo es la UI.
        """
        if not self.db_engine:
            self.last_error = "No hay conexión activa con la base de datos."
            _log.error(self.last_error)
            return pd.DataFrame()

        sentencia = query if isinstance(query, TextClause) else text(query)
        _log.debug("Consulta con params=%s", params)

        try:
            with self.db_engine.connect() as connection:
                if self.db_type in ("MariaDB", "MySQL"):
                    connection.execute(
                        text("SET SESSION group_concat_max_len = 100000;"))

                df = pd.read_sql_query(sentencia, connection, params=params)
                _log.debug("Resultado: %d filas", len(df))
                self.last_error = None
                return df
        except Exception as e:
            self.last_error = str(e)
            _log.error("Falló la consulta (%s)\n%s\nparams=%s",
                       e, str(sentencia), params)
            return pd.DataFrame()

    def connect_to_server(self, db_type, host, port, user, password):
        self.db_type = db_type
        _log.info("Conectando al servidor %s en %s:%s", db_type, host, port)
        try:
            if self.db_type in ("MariaDB", "MySQL"):
                port_str = f":{port}" if port else ":3306"
                url = f"mysql+pymysql://{user}:{password}@{host}{port_str}"
            elif self.db_type == "SQL Server":
                driver = "ODBC Driver 17 for SQL Server"
                params = (f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE=master;"
                          f"UID={user};PWD={password};TrustServerCertificate=yes;")
                url = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(params)}"
            else:
                raise ValueError(f"Tipo de base de datos no soportado: {self.db_type}")

            self.server_engine = create_engine(
                url, pool_pre_ping=True, pool_recycle=3600)
            with self.server_engine.connect():
                pass
            _log.info("Conexión al servidor exitosa.")
            return True, "Conexión al servidor exitosa."
        except Exception as e:
            self.server_engine = None
            error_str = str(e).lower()
            if any(t in error_str for t in
                   ("1045", "access denied", "18456", "login failed")):
                _log.warning("Credenciales rechazadas por el servidor.")
                return False, "Usuario o contraseña incorrectos."
            _log.error("Error de conexión al servidor: %s", _ocultar_password(e))
            return False, f"Error al conectar al servidor:\n{str(e)}"

    def list_databases(self):
        if not self.server_engine:
            return []
        try:
            dbs = []
            with self.server_engine.connect() as connection:
                if self.db_type in ("MariaDB", "MySQL"):
                    result = connection.execute(text("SHOW DATABASES;"))
                    system_dbs = {'information_schema', 'mysql',
                                  'performance_schema', 'sys'}
                    dbs = sorted([r[0] for r in result if r[0] not in system_dbs])
                elif self.db_type == "SQL Server":
                    result = connection.execute(
                        text("SELECT name FROM sys.databases WHERE database_id > 4;"))
                    dbs = sorted([r[0] for r in result])
            _log.info("Se encontraron %d bases de datos.", len(dbs))
            return dbs
        except Exception as e:
            _log.error("Error al listar bases de datos: %s", e)
            return []

    def connect_to_database(self, db_type, host, port, user, password, db_name):
        self.db_type = db_type
        _log.info("Conectando a la base '%s'...", db_name)
        try:
            if self.db_type in ("MariaDB", "MySQL"):
                port_str = f":{port}" if port else ":3306"
                url = f"mysql+pymysql://{user}:{password}@{host}{port_str}/{db_name}"
            elif self.db_type == "SQL Server":
                driver = "ODBC Driver 17 for SQL Server"
                params = (f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={db_name};"
                          f"UID={user};PWD={password};TrustServerCertificate=yes;")
                url = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(params)}"
            else:
                raise ValueError(f"Tipo de base de datos no soportado: {self.db_type}")

            self.db_engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
            with self.db_engine.connect():
                pass
            _log.info("Conexión a la base exitosa.")
            return True, f"Conectado a la base de datos '{db_name}'."
        except Exception as e:
            self.db_engine = None
            _log.error("Error al conectar a la base: %s", _ocultar_password(e))
            return False, f"Error al conectar a la base de datos:\n{str(e)}"

    def connect_with_connection_string(self, connection_string):
        """Conecta usando la `cadenaConexion` que devuelve la API de login."""
        self.db_type = "MariaDB"

        try:
            conn_str = connection_string.strip()
            conn_parts = {
                k.strip().lower(): v.strip()
                for k, v in (part.split("=", 1)
                             for part in conn_str.split(";")
                             if part.strip() and "=" in part)
            }

            host = conn_parts.get("server")
            port = conn_parts.get("port", "3306")
            user = conn_parts.get("uid")
            password = conn_parts.get("pwd")
            database = conn_parts.get("database")

            if not host or not user or not database:
                return False, "La cadena de conexión de la API está incompleta."

            sqlalchemy_url = (
                f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
                "?charset=utf8mb4"
            )

            # Nunca loguear la URL entera: lleva la contraseña de la base del
            # cliente en texto plano.
            _log.info("Conectando a MariaDB %s:%s/%s como %s",
                      host, port, database, user)

            self.db_engine = create_engine(
                sqlalchemy_url, pool_pre_ping=True, pool_recycle=3600)

            with self.db_engine.connect():
                pass

            _log.info("Conexión a MariaDB exitosa.")
            return True, "Conectado correctamente a MariaDB."

        except Exception as e:
            self.db_engine = None
            _log.error("Error al conectar: %s", _ocultar_password(e))
            return False, f"Error al conectar: {_ocultar_password(e)}"

    def get_empresas(self):
        query = ("SELECT idEmpresa, RazonSocial FROM empresas "
                 "WHERE Activa = 1 ORDER BY RazonSocial;")
        return self._execute_query(query)


class AppLogic:
    def __init__(self, main_window):
        self.window = main_window
        self.db_manager = self.window.db_manager
        self.config_data = None
        self.selected_empresa_id = None

    def setup_empresa_and_ui(self):
        """Configura la UI con la empresa que devolvió el login."""
        try:
            razon_social = self.config_data.get("razon_social")
            empresa_id = self.config_data.get("id_empresa")

            if not razon_social or empresa_id is None:
                QMessageBox.critical(
                    self.window, "Error de Configuración",
                    "La respuesta de la API no contiene 'razon_social' o 'id_empresa'.")
                return

            self.selected_empresa_id = empresa_id
            self.window.empresa_label.setText(f"{razon_social}")
            self.window.empresa_group.setVisible(True)
            self.window.selection_group.setVisible(True)
            self.window.status_bar_message(
                "Listo. Seleccione los informes y presione un botón para exportar.")

            try:
                articles_df = self.window.stats_generator.get_all_articles_for_dropdown(
                    self.selected_empresa_id)
                if not articles_df.empty:
                    self.window.all_articles_df = articles_df
                    _log.info("Cargados %d artículos para el modal de canasta.",
                              len(articles_df))
                else:
                    _log.warning("No se encontraron artículos para el modal de canasta.")
            except Exception as e:
                _log.error("No se pudieron cargar los artículos: %s", e)

        except Exception as e:
            # Antes acá decía `QMessageBox.critical(self, ...)`, y `self` es
            # AppLogic, no un QWidget: el TypeError tapaba el error original.
            _log.exception("No se pudo configurar la empresa.")
            QMessageBox.critical(self.window, "Error",
                                 f"No se pudo configurar la empresa:\n{e}")
            self.window.status_bar_message("Error al configurar la empresa.")

    # ------------------------------------------------------------------ #
    # Datos detallados por informe (hoja de Excel / tabla del PDF)
    # ------------------------------------------------------------------ #

    def get_detailed_data_for_report(self, report_name, empresa_id):
        """Devuelve el DataFrame detallado de un informe.

        Los resultados se cachean por exportación: `export_to_pdf` y
        `export_to_excel` piden el mismo informe dos veces (una para el gráfico y
        otra para el detalle), y algunos —el RFM, la canasta— recalculan todo
        sobre la base entera.
        """
        cache = getattr(self.window, "_cache_informes", None)
        if cache is not None and report_name in cache:
            return cache[report_name]

        df = self._calcular_detalle(report_name, empresa_id)

        if cache is not None:
            cache[report_name] = df
        return df

    def _calcular_detalle(self, report_name, empresa_id):
        _log.debug("Generando detalle de '%s'", report_name)
        w = self.window
        sg = w.stats_generator

        if report_name == "top_articles_value":
            return sg.get_top_articles_for_excel(
                empresa_id,
                w.top_articles_value_limit_combo.currentData(),
                w.top_articles_value_period_combo.currentData(),
                order_by_value=True)

        if report_name == "top_articles_qty":
            return sg.get_top_articles_for_excel(
                empresa_id,
                w.top_articles_qty_limit_combo.currentData(),
                w.top_articles_qty_period_combo.currentData(),
                order_by_value=False)

        if report_name == "top_customers":
            return sg.get_top_clients_for_excel(
                empresa_id,
                w.top_customers_limit_combo.currentData(),
                w.include_cf_checkbox.isChecked(),
                w.top_customers_period_combo.currentData())

        if report_name in ("sales_over_time", "sales_by_payment"):
            methods = [n for n, chk in w.payment_method_checkboxes.items()
                       if chk.isChecked()]
            return sg.get_sales_by_day_for_excel(
                empresa_id, w.sales_period_combo.currentData(), methods)

        if report_name == "stock_analysis":
            option = w.stock_report_combo.currentData()
            limit = w.stock_limit_combo.currentData()
            return sg.get_stock_data_for_excel(empresa_id, option, limit)

        if report_name == "market_basket":
            return sg.get_market_basket_analysis(
                empresa_id,
                w.basket_period_combo.currentData(),
                w.basket_mode_combo.currentData(),
                w.basket_assoc_limit_combo.currentData(),
                w.manual_basket_selection)

        if report_name == "cta_cte":
            return sg.get_customer_debt_for_excel(
                empresa_id,
                w.cta_cte_cliente_combo.currentData(),
                w.cta_cte_voucher_combo.currentData())

        if report_name == "aging_cta_cte":
            return sg.get_aging_cuenta_corriente(
                empresa_id, w.aging_limit_combo.currentData())

        if report_name == "slob_analysis":
            return sg.get_slob_analysis_for_excel(
                empresa_id, w.slob_threshold_combo.currentData())

        if report_name == "rfm_segmentation":
            df_full, _ = sg.get_rfm_analysis_data(empresa_id)
            return df_full

        if report_name == "margin_by_article":
            return sg.get_margin_by_article(
                empresa_id,
                w.margin_limit_combo.currentData(),
                w.margin_period_combo.currentData())

        if report_name == "abc_analysis":
            return sg.get_abc_analysis(empresa_id, w.abc_period_combo.currentData())

        if report_name == "purchase_suggestion":
            return sg.get_purchase_suggestion(
                empresa_id,
                w.purchase_period_combo.currentData(),
                w.purchase_target_combo.currentData())

        return pd.DataFrame()

    # ------------------------------------------------------------------ #
    # Datos para los gráficos
    # ------------------------------------------------------------------ #

    def generate_statistics(self):
        """Arma la lista de informes activos.

        Cada elemento es
        `(df_grafico, titulo, xlabel, ylabel, tipo_grafico, limite, clave)`.
        `df_grafico` en None significa "este informe es solo tabla".
        """
        empresa_id = self.selected_empresa_id
        if empresa_id is None:
            QMessageBox.warning(self.window, "Error",
                                "No se ha configurado ninguna empresa.")
            return []

        sg = self.window.stats_generator
        if not sg:
            QMessageBox.critical(self.window, "Error",
                                 "El generador de estadísticas no está inicializado.")
            return []

        w = self.window
        w.status_bar_message(f"Generando datos para la empresa ID: {empresa_id}...")
        all_report_data = []

        def activo(clave):
            boton = w.report_buttons.get(clave)
            return boton is not None and boton.isChecked()

        def texto_periodo(days):
            return "Todo el Historial" if days == -1 else f"Últimos {days} días"

        def texto_limite(limit):
            return f"Top {limit}" if limit != -1 else "Todos los"

        try:
            if activo("top_articles_value"):
                limit = w.top_articles_value_limit_combo.currentData()
                days = w.top_articles_value_period_combo.currentData()
                title = (f"{texto_limite(limit)} {w.report_titles['top_articles_value']} "
                         f"({texto_periodo(days)})")
                df = sg.get_top_articles_by_value(empresa_id, limit, days)
                all_report_data.append((df, title, "Total Vendido ($)", "Artículo",
                                        False, limit, "top_articles_value"))

            if activo("top_articles_qty"):
                limit = w.top_articles_qty_limit_combo.currentData()
                days = w.top_articles_qty_period_combo.currentData()
                title = (f"{texto_limite(limit)} {w.report_titles['top_articles_qty']} "
                         f"({texto_periodo(days)})")
                df = sg.get_top_articles_by_quantity(empresa_id, limit, days)
                all_report_data.append((df, title, "Cantidad Vendida", "Artículo",
                                        False, limit, "top_articles_qty"))

            if activo("margin_by_article"):
                limit = w.margin_limit_combo.currentData()
                days = w.margin_period_combo.currentData()
                title = (f"{texto_limite(limit)} Artículos por Margen Bruto "
                         f"({texto_periodo(days)})")
                df = sg.get_margin_chart(empresa_id, limit, days)
                all_report_data.append((df, title, "Margen Bruto ($)", "Artículo",
                                        False, limit, "margin_by_article"))

            if activo("abc_analysis"):
                days = w.abc_period_combo.currentData()
                title = f"Curva ABC de Artículos ({texto_periodo(days)})"
                df = sg.get_abc_summary_chart(empresa_id, days)
                all_report_data.append((df, title, "Cantidad de Artículos", "Clase ABC",
                                        False, None, "abc_analysis"))

            if activo("top_customers"):
                limit = w.top_customers_limit_combo.currentData()
                days = w.top_customers_period_combo.currentData()
                title = (f"{texto_limite(limit)} {w.report_titles['top_customers']} "
                         f"({texto_periodo(days)})")
                df = sg.get_top_customers_by_billing(
                    empresa_id, limit, w.include_cf_checkbox.isChecked(), days)
                all_report_data.append((df, title, "Total Facturado ($)", "Cliente",
                                        False, limit, "top_customers"))

            if activo("sales_over_time"):
                days = w.sales_period_combo.currentData()
                methods = [n for n, chk in w.payment_method_checkboxes.items()
                           if chk.isChecked()]

                df_total = sg.get_sales_over_time(empresa_id, days)
                all_report_data.append(
                    (df_total, f"Total de Ventas por Día ({texto_periodo(days)})",
                     "Fecha", "Total Ventas ($)", True, None, "sales_over_time"))

                df_methods = sg.get_sales_by_payment_method_for_chart(
                    empresa_id, days, methods)
                all_report_data.append(
                    (df_methods, f"Ventas por Medio de Pago ({texto_periodo(days)})",
                     "Fecha", "Total Venta ($)", "multi-line", None, "sales_by_payment"))

            if activo("stock_analysis"):
                all_report_data.append(
                    (None, "Análisis de Stock", "", "", False, 0, "stock_analysis"))

            if activo("market_basket"):
                mode = w.basket_mode_combo.currentData()
                if mode == 'manual' and not w.manual_basket_selection:
                    QMessageBox.warning(
                        w, "Dato Faltante",
                        "Para 'Análisis de Canasta' manual, debe elegir al menos "
                        "un artículo.")
                    w.status_bar_message(
                        "Análisis de Canasta omitido: no se seleccionaron artículos.",
                        5000)
                else:
                    all_report_data.append(
                        (None, "Análisis de Canasta", "", "", False, 0, "market_basket"))

            if activo("slob_analysis"):
                title = f"Inventario Obsoleto ({w.slob_threshold_combo.currentText()})"
                all_report_data.append((None, title, "", "", False, 0, "slob_analysis"))

            if activo("purchase_suggestion"):
                title = ("Sugerido de Compra por Proveedor "
                         f"({w.purchase_target_combo.currentText()})")
                all_report_data.append(
                    (None, title, "", "", False, 0, "purchase_suggestion"))

            if activo("cta_cte"):
                limit = w.cta_cte_cliente_combo.currentData()
                title = (f"{w.report_titles['cta_cte']}: "
                         f"{w.cta_cte_cliente_combo.currentText()}")
                if limit == -1:
                    title = "Todos los Clientes con Saldo"
                df = sg.get_customer_debt_for_chart(empresa_id, limit)
                all_report_data.append((df, title, "Saldo Adeudado ($)", "Cliente",
                                        False, limit, "cta_cte"))

            if activo("aging_cta_cte"):
                all_report_data.append(
                    (None, "Antigüedad de la Deuda (Aging)", "", "", False, 0,
                     "aging_cta_cte"))

            if activo("rfm_segmentation"):
                _, summary_counts = sg.get_rfm_analysis_data(empresa_id)
                df_chart = summary_counts.reset_index()
                df_chart.columns = ['Segmento', 'Cantidad de Clientes']
                all_report_data.append(
                    (df_chart, "Resumen de Segmentación de Clientes (RFM)",
                     "Cantidad de Clientes", "Segmento", False, None,
                     "rfm_segmentation"))

            if not all_report_data:
                QMessageBox.information(
                    w, "Información", "No se seleccionó ninguna estadística.")
            else:
                w.status_bar_message("Datos generados, listos para exportar.", 3000)

        except Exception as e:
            _log.exception("Error al generar los datos de los informes.")
            QMessageBox.critical(w, "Error",
                                 f"Ocurrió un error al generar los datos:\n{e}")
            w.status_bar_message(f"Error al generar datos: {e}")

        return all_report_data
