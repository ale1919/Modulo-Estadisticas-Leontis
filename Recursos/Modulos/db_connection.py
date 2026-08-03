import pandas as pd
import urllib.parse
import sys
from PySide6.QtWidgets import QMessageBox

from sqlalchemy import create_engine, text
from .statistics_generator import StatisticsGenerator
from .ui_styles import HIGHLIGHTED_COMBO_STYLE
# from .crypto_manager import CryptoManager

class DBManager:
    def __init__(self):
        self.server_engine = None
        self.db_engine = None
        self.db_type = None


    def _execute_query(self, query, params=None):
        if not self.db_engine:
            QMessageBox.critical(None, "Error de Conexión", "No hay conexión activa con la base de datos.")
            return pd.DataFrame()
        
        print("\n--- [DEBUG] Ejecutando Consulta ---")
        print(f"Query: {query}")
        print(f"Params: {params}")

        try:
            with self.db_engine.connect() as connection:
                if self.db_type in ("MariaDB", "MySQL"):
                    connection.execute(text("SET SESSION group_concat_max_len = 100000;"))
                
                df = pd.read_sql_query(text(query), connection, params=params)
                print(f"Resultado: {len(df)} filas obtenidas.")
                print("--- [DEBUG] Fin de Consulta ---\n")
                return df
        except Exception as e:
            error_msg = f"Ocurrió un error al ejecutar la consulta:\n\nQuery:\n{query}\n\nParams:\n{params}\n\nError:\n{e}"
            print(f"--- [ERROR SQL] ---\n{error_msg}\n-------------------")
            QMessageBox.critical(None, "Error en Consulta SQL", error_msg)
            return pd.DataFrame()

    def connect_to_server(self, db_type, host, port, user, password):
        self.db_type = db_type
        print(f"DEBUG: Intentando conectar al servidor {db_type} en {host}:{port} con usuario {user}.")
        try:
            url = ""
            if self.db_type in ("MariaDB", "MySQL"):
                port_str = f":{port}" if port else ":3306"
                url = f"mysql+pymysql://{user}:{password}@{host}{port_str}"
            elif self.db_type == "SQL Server":
                driver = "ODBC Driver 17 for SQL Server"
                params = f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE=master;UID={user};PWD={password};TrustServerCertificate=yes;"
                quoted_params = urllib.parse.quote_plus(params)
                url = f"mssql+pyodbc:///?odbc_connect={quoted_params}"
            else:
                raise ValueError(f"Tipo de base de datos no soportado: {self.db_type}")

            self.server_engine = create_engine(url)
            with self.server_engine.connect(): pass
            print("DEBUG: Conexión al servidor exitosa.")
            return True, "Conexión al servidor exitosa."
        except Exception as e:
            self.server_engine = None
            error_str = str(e).lower()
            if "1045" in error_str or "access denied" in error_str or "18456" in error_str or "login failed" in error_str:
                print("DEBUG: Error de autenticación (usuario/contraseña incorrectos).")
                return False, "Usuario o contraseña incorrectos."
            print(f"DEBUG: Error de conexión genérico al servidor: {e}")
            return False, f"Error al conectar al servidor:\n{str(e)}"

    def list_databases(self):
        if not self.server_engine: return []
        print("DEBUG: Listando bases de datos...")
        try:
            with self.server_engine.connect() as connection:
                if self.db_type in ("MariaDB", "MySQL"):
                    query = "SHOW DATABASES;"
                    result = connection.execute(text(query))
                    system_dbs = {'information_schema', 'mysql', 'performance_schema', 'sys'}
                    dbs = sorted([row[0] for row in result if row[0] not in system_dbs])
                elif self.db_type == "SQL Server":
                    query = "SELECT name FROM sys.databases WHERE database_id > 4;"
                    result = connection.execute(text(query))
                    dbs = sorted([row[0] for row in result])
                print(f"DEBUG: Se encontraron {len(dbs)} bases de datos.")
                return dbs
        except Exception as e:
            print(f"DEBUG: Error al listar bases de datos: {e}")
            return []

    def connect_to_database(self, db_type, host, port, user, password, db_name):
        self.db_type = db_type
        print(f"DEBUG: Intentando conectar a la base de datos '{db_name}'...")
        try:
            url = ""
            if self.db_type in ("MariaDB", "MySQL"):
                port_str = f":{port}" if port else ":3306"
                url = f"mysql+pymysql://{user}:{password}@{host}{port_str}/{db_name}"
            elif self.db_type == "SQL Server":
                driver = "ODBC Driver 17 for SQL Server"
                params = f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={db_name};UID={user};PWD={password};TrustServerCertificate=yes;"
                quoted_params = urllib.parse.quote_plus(params)
                url = f"mssql+pyodbc:///?odbc_connect={quoted_params}"

            self.db_engine = create_engine(url)
            with self.db_engine.connect(): pass
            print("DEBUG: Conexión a la base de datos exitosa.")
            return True, f"Conectado a la base de datos '{db_name}'."
        except Exception as e:
            self.db_engine = None
            print(f"DEBUG: Error al conectar a la base de datos: {e}")
            return False, f"Error al conectar a la base de datos:\n{str(e)}"

    def connect_with_connection_string(self, connection_string):
        """
        Conexión correcta a MariaDB usando la cadenaConexion que viene de la API.
        """
        self.db_type = "MariaDB"
    
        try:
            conn_str = connection_string.strip()
    
            # Parsear formato key=value;
            conn_parts = {
                k.strip().lower(): v.strip()
                for k, v in (part.split("=", 1) for part in conn_str.split(";") if part.strip() and "=" in part)
            }
    
            host = conn_parts.get("server")
            port = conn_parts.get("port", "3306")
            user = conn_parts.get("uid")
            password = conn_parts.get("pwd")
            database = conn_parts.get("database")
    
            if not host or not user or not database:
                return False, "La cadena de conexión de la API está incompleta."
    
            # Construir URL MariaDB para SQLAlchemy
            sqlalchemy_url = (
                f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
                "?charset=utf8mb4"
            )
    
            print(f"DEBUG: Conectando a MariaDB con: {sqlalchemy_url}")
    
            self.db_engine = create_engine(sqlalchemy_url, pool_pre_ping=True)
    
            with self.db_engine.connect():
                pass
            
            print("DEBUG: Conexión a MariaDB exitosa.")
            return True, "Conectado correctamente a MariaDB."
    
        except Exception as e:
            self.db_engine = None
            print(f"ERROR: {e}")
            return False, f"Error al conectar: {e}"


    def get_empresas(self):
        print("DEBUG: Obteniendo lista de empresas activas...")
        query = "SELECT idEmpresa, RazonSocial FROM empresas WHERE Activa = 1 ORDER BY RazonSocial;"
        return self._execute_query(query)


class AppLogic:
    def __init__(self, main_window):
        self.window = main_window
        self.db_manager = self.window.db_manager
        # self.crypto_manager = CryptoManager() 
        self.config_data = None
        self.selected_empresa_id = None
            
    def setup_empresa_and_ui(self):
        """Configura la UI con la empresa del archivo de config y muestra los paneles."""
        try:
            # Ahora lee 'razon_social' y 'id_empresa' directamente del config_data
            # que vino de la API de login.
            razon_social = self.config_data.get("razon_social") 
            empresa_id = self.config_data.get("id_empresa")

            if not razon_social or empresa_id is None:
                QMessageBox.critical(self.window, "Error de Configuración",
                                     "La respuesta de la API no contiene 'razon_social' o 'id_empresa'.")
                return

            self.selected_empresa_id = empresa_id
            self.window.empresa_label.setText(f"{razon_social}")
            self.window.empresa_group.setVisible(True)
            self.window.selection_group.setVisible(True)
            self.window.status_bar_message("Listo. Seleccione los informes y presione un botón para exportar.")

            try:
                articles_df = self.window.stats_generator.get_all_articles_for_dropdown(self.selected_empresa_id)
                if not articles_df.empty:
                    self.window.all_articles_df = articles_df
                    print(f"DEBUG: Cargados {len(articles_df)} artículos para el modal de análisis de canasta.")
                else:
                    # self.window.report_cards["market_basket"].setEnabled(False)
                    print("WARN: No se encontraron artículos, deshabilitando Análisis de Canasta.")

            except Exception as e:
                print(f"ERROR: No se pudieron cargar los artículos para el análisis de canasta: {e}")
                # self.window.report_cards["market_basket"].setEnabled(False)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo configurar la empresa:\n{e}")
            self.window.status_bar_message("Error al configurar la empresa.")

    
    def get_detailed_data_for_report(self, report_name, empresa_id):
        print(f"DEBUG: get_detailed_data_for_report llamado para '{report_name}'")
        sg = self.window.stats_generator

        if report_name == "top_articles_value":
            limit = self.window.top_articles_value_limit_combo.currentData()
            days = self.window.top_articles_value_period_combo.currentData()
            return sg.get_top_articles_for_excel(empresa_id, limit, days, order_by_value=True)

        elif report_name == "top_articles_qty":
            limit = self.window.top_articles_qty_limit_combo.currentData()
            days = self.window.top_articles_qty_period_combo.currentData()
            return sg.get_top_articles_for_excel(empresa_id, limit, days, order_by_value=False)
            
        elif report_name == "top_customers":
            limit = self.window.top_customers_limit_combo.currentData()
            include_cf = self.window.include_cf_checkbox.isChecked()
            days = self.window.top_customers_period_combo.currentData()
            return sg.get_top_clients_for_excel(empresa_id, limit, include_cf, days)

        elif report_name == "sales_over_time" or report_name == "sales_by_payment":
            days = self.window.sales_period_combo.currentData()
            methods = [name for name, chk in self.window.payment_method_checkboxes.items() if chk.isChecked()]
            return sg.get_sales_by_day_for_excel(empresa_id, days, methods)
        
        elif report_name == "stock_analysis":
            option = self.window.stock_report_combo.currentData()
            limit_text = self.window.stock_report_combo.currentText()
            limit = 30 if "30" in limit_text else -1 
            return sg.get_stock_data_for_excel(empresa_id, option, limit)

        elif report_name == "market_basket":
            mode = self.window.basket_mode_combo.currentData()
            days = self.window.basket_period_combo.currentData()
            manual_ids = self.window.manual_basket_selection
            assoc_limit = self.window.basket_assoc_limit_combo.currentData()
            return sg.get_market_basket_analysis(empresa_id, days, mode, assoc_limit, manual_ids)
        
        # Lógica de datos para Análisis de Cta Cte
        elif report_name == "cta_cte":
            client_limit = self.window.cta_cte_cliente_combo.currentData()
            voucher_limit = self.window.cta_cte_voucher_combo.currentData()
            return sg.get_customer_debt_for_excel(empresa_id, client_limit, voucher_limit)
        
        elif report_name == "slob_analysis":
            threshold = self.window.slob_threshold_combo.currentData()
            return sg.get_slob_analysis_for_excel(empresa_id, threshold)
        
        elif report_name == "rfm_segmentation":
            df_full, _ = sg.get_rfm_analysis_data(empresa_id)
            return df_full
          
        return pd.DataFrame()

    def generate_statistics(self):
        empresa_id = self.selected_empresa_id
        if empresa_id is None:
            QMessageBox.warning(self.window, "Error", "No se ha configurado ninguna empresa.")
            return []

        sg = self.window.stats_generator
        if not sg:
            QMessageBox.critical(self.window, "Error", "El generador de estadísticas no está inicializado.")
            return []

        self.window.status_bar_message(f"Generando datos para la empresa ID: {empresa_id}...")
        all_report_data = []
        try:
            
            if self.window.report_buttons["top_articles_value"].isChecked():
                limit = self.window.top_articles_value_limit_combo.currentData()
                days = self.window.top_articles_value_period_combo.currentData()
                period_text = "Todo el Historial" if days == -1 else f"Últimos {days} días"
                limit_text = f"Top {limit}" if limit != -1 else "Todos los"
                base_title = self.window.report_titles['top_articles_value']
                title = f"{limit_text} {base_title} ({period_text})"
                df = sg.get_top_articles_by_value(empresa_id, limit, days)
                all_report_data.append((df, title, "Total Vendido ($)", "Artículo", False, limit, "top_articles_value"))

            if self.window.report_buttons["top_articles_qty"].isChecked():
                limit = self.window.top_articles_qty_limit_combo.currentData()
                days = self.window.top_articles_qty_period_combo.currentData()
                period_text = "Todo el Historial" if days == -1 else f"Últimos {days} días"
                limit_text = f"Top {limit}" if limit != -1 else "Todos los"
                base_title = self.window.report_titles['top_articles_qty']
                title = f"{limit_text} {base_title} ({period_text})"
                df = sg.get_top_articles_by_quantity(empresa_id, limit, days)
                all_report_data.append((df, title, "Cantidad Vendida", "Artículo", False, limit, "top_articles_qty"))
            
            if self.window.report_buttons["top_customers"].isChecked():
                limit = self.window.top_customers_limit_combo.currentData()
                include_cf = self.window.include_cf_checkbox.isChecked()
                days = self.window.top_customers_period_combo.currentData()
                period_text = "Todo el Historial" if days == -1 else f"Últimos {days} días"
                limit_text = f"Top {limit}" if limit != -1 else "Todos los"
                base_title = self.window.report_titles['top_customers']
                title = f"{limit_text} {base_title} ({period_text})"
                df = sg.get_top_customers_by_billing(empresa_id, limit, include_cf, days)
                all_report_data.append((df, title, "Total Facturado ($)", "Cliente", False, limit, "top_customers"))
            
            if self.window.report_buttons["sales_over_time"].isChecked():
                days = self.window.sales_period_combo.currentData()
                period_text = "Todo el Historial" if days == -1 else f"Últimos {days} días"
                methods = [name for name, chk in self.window.payment_method_checkboxes.items() if chk.isChecked()]

                df_total = sg.get_sales_over_time(empresa_id, days)
                title_total = f"Total de Ventas por Día ({period_text})"
                all_report_data.append((df_total, title_total, "Fecha", "Total Ventas ($)", True, None, "sales_over_time"))
                
                df_methods = sg.get_sales_by_payment_method_for_chart(empresa_id, days, methods)
                title_methods = f"Ventas por Medio de Pago ({period_text})"
                all_report_data.append((df_methods, title_methods, "Fecha", "Total Venta ($)", "multi-line", None, "sales_by_payment"))

            if self.window.report_buttons["stock_analysis"].isChecked():
                 all_report_data.append((None, "Análisis de Stock", "", "", False, 0, "stock_analysis"))

            if self.window.report_buttons["market_basket"].isChecked():
                mode = self.window.basket_mode_combo.currentData()
                if mode == 'manual' and not self.window.manual_basket_selection:
                    QMessageBox.warning(self.window, "Dato Faltante", 
                                        "Para 'Análisis de Canasta' manual, debe elegir al menos un artículo.")
                    self.window.status_bar_message("Análisis de Canasta omitido: No se seleccionaron artículos.", 5000)
                else:
                    all_report_data.append((None, "Análisis de Canasta", "", "", False, 0, "market_basket"))

             # Lógica para incluir SLOB en el exportador (solo tabla)
            if self.window.report_buttons["slob_analysis"].isChecked():
                threshold_text = self.window.slob_threshold_combo.currentText()
                title = f"Inventario Obsoleto ({threshold_text})"
                all_report_data.append((None, title, "", "", False, 0, "slob_analysis"))
            
            # Lógica de datos para Gráfico de Cta Cte
            if self.window.report_buttons["cta_cte"].isChecked():
                limit = self.window.cta_cte_cliente_combo.currentData()
                limit_text = self.window.cta_cte_cliente_combo.currentText()
                base_title = self.window.report_titles['cta_cte']
                
                title = f"{base_title}: {limit_text}"
                # Lógica especial para el título si se seleccionan todos
                if limit == -1:
                    title = "Todos los Clientes con Saldo" # Sobrescribir el título

                df = sg.get_customer_debt_for_chart(empresa_id, limit)
                # El xlabel es 'Saldo Adeudado ($)' y el ylabel 'Cliente'. ChartType = False (Barra horizontal)
                all_report_data.append((df, title, "Saldo Adeudado ($)", "Cliente", False, limit, "cta_cte"))

            if self.window.report_buttons["rfm_segmentation"].isChecked():
                # Llamar al motor RFM. Solo necesitamos el summary_counts para el gráfico del PDF.
                _ , summary_counts = sg.get_rfm_analysis_data(empresa_id)
                
                # Convertir la Serie de conteos a un DataFrame que el plotter (MatplotlibWidget) pueda usar
                df_chart = summary_counts.reset_index()
                df_chart.columns = ['Segmento', 'Cantidad de Clientes']
                
                title = "Resumen de Segmentación de Clientes (RFM)"
                
                all_report_data.append((df_chart, title, "Cantidad de Clientes", "Segmento", False, None, "rfm_segmentation"))
            
            if not all_report_data:
                QMessageBox.information(self.window, "Información", "No se seleccionó ninguna estadística para generar.")
            else:
                 self.window.status_bar_message("Datos generados, listos para exportar.", 3000)

        except Exception as e:
            QMessageBox.critical(self.window, "Error", f"Ocurrió un error al generar los datos:\n{e}")
            self.window.status_bar_message(f"Error al generar datos: {e}")
        
        return all_report_data