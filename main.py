import base64
import io
import os
import sys
import traceback
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib.backends.backend_pdf import PdfPages
from PySide6.QtCore import QSettings, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QStatusBar, QTabWidget, QTextBrowser,
    QVBoxLayout, QWidget
)

from Recursos.Modulos.dashboard_manager import DashboardWorker
from Recursos.Modulos.db_connection import AppLogic, DBManager
from Recursos.Modulos.matplotlib_widget import MatplotlibWidget
from Recursos.Modulos.rutas import BASE_DIR, configurar_logging, log, recurso
from Recursos.Modulos.statistics_generator import StatisticsGenerator
from Recursos.Modulos.ui_factory import UIFactory
from Recursos.Modulos.ui_styles import (
    BRAND_ACCENT_BUTTON_STYLE, MODERN_CARD_STYLE, MODERN_TAB_STYLE
)
from Recursos.Modulos.ui_requisitos import chequear_al_inicio as chequear_requisitos
from Recursos.Modulos.ui_updater import chequear_al_inicio

_log = log("main")

FAVICON_PATH = recurso("Recursos", "Grafico", "favicon.ico")
LOGO_SQUARE_PATH = recurso("Recursos", "Grafico", "logo-square.png")



class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.valid_db_manager = None
        self.valid_config_data = None
        self.valid_user_role = None
        
        self.db_manager = DBManager()
        # HTTP, no HTTPS: el servidor NO habla TLS en este puerto. Un handshake
        # contra él devuelve WRONG_VERSION_NUMBER, que es lo que pasa cuando del
        # otro lado hay HTTP plano. Es lo mismo que usan los módulos hermanos
        # (`Modulo Servicios` y el importador desde Eslaboon).
        #
        # Queda pendiente y es un problema real de seguridad: por acá viajan el
        # usuario, la contraseña y —de vuelta— la cadena de conexión a la base
        # del cliente. Base64 no cifra nada, así que todo eso es legible para
        # cualquiera en la red del local. Cuando el servidor tenga certificado,
        # se pasa a https con ESTADISTICAS_API_URL y después se cambia el default.
        self.API_BASE_URL = os.environ.get(
            "ESTADISTICAS_API_URL", "http://sistema.leontis.com.ar:65081")

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        self.setWindowTitle("Iniciar Sesión - Analizador Leontis")
        self.setWindowIcon(QIcon(FAVICON_PATH))
        self.setFixedSize(400, 540)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        card_widget = QWidget()
        card_widget.setObjectName("card_widget")
        main_layout.addWidget(card_widget)
        
        card_layout = QVBoxLayout(card_widget)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(30, 25, 30, 25)
        header_layout.setSpacing(15)

        self.logo_label = QLabel()
        pixmap = QPixmap(LOGO_SQUARE_PATH)
        self.logo_label.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.logo_label)

        self.title_label = QLabel("Iniciar Sesión")
        font = self.title_label.font()
        font.setPointSize(16)
        self.title_label.setFont(font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("title_label")
        header_layout.addWidget(self.title_label)
        card_layout.addWidget(header_widget)

        # Se define el widget del cuerpo y su layout principal
        body_widget = QWidget()
        body_widget.setObjectName("body_widget")
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(30, 25, 30, 30)
        body_layout.setSpacing(15)

        self.user_label = QLabel("Usuario:")
        body_layout.addWidget(self.user_label)
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Ingrese su nombre de usuario")
        body_layout.addWidget(self.user_input)

        self.pass_label = QLabel("Contraseña:")
        body_layout.addWidget(self.pass_label)

        # --- Layout horizontal para el campo de contraseña y el botón ---
        password_layout = QHBoxLayout()
        password_layout.setSpacing(5)
        password_layout.setContentsMargins(0, 0, 0, 0)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Ingrese su contraseña")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.toggle_password_btn = QPushButton("👁️")
        self.toggle_password_btn.setCheckable(True)
        self.toggle_password_btn.setFixedSize(38, 38)
        self.toggle_password_btn.setToolTip("Mostrar/Ocular contraseña")
        self.toggle_password_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 18px;
                color: #555;
            }
            QPushButton:checked {
                background-color: #e0e0e0;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border-radius: 4px;
            }
        """)

        password_layout.addWidget(self.pass_input)
        password_layout.addWidget(self.toggle_password_btn)

        body_layout.addLayout(password_layout)
        # --- Fin del layout horizontal ---

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setObjectName("error_label")
        body_layout.addWidget(self.error_label)

        body_layout.addStretch()

        self.login_btn = QPushButton("Ingresar")
        self.login_btn.setStyleSheet(BRAND_ACCENT_BUTTON_STYLE)
        self.login_btn.setFixedHeight(40)
        body_layout.addWidget(self.login_btn)

        card_layout.addWidget(body_widget)
        self.apply_styles()
        
    def toggle_password_visibility(self, checked):
        """
        Cambia el modo de eco del campo de contraseña basado en el estado
        del botón 'toggle'.
        """
        if checked:
            # Si el botón está presionado (checked), mostrar contraseña
            self.pass_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            # Si no, ocultarla
            self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)


    def apply_styles(self):
        self.setStyleSheet(f"""
            LoginDialog {{ background-color: #f0f2f5; }}
            QWidget#card_widget {{ background-color: #ffffff; border: 1px solid #E0E0E0; border-radius: 8px; }}
            QWidget#header_widget {{ background-color: #312093; border-top-left-radius: 8px; border-top-right-radius: 8px; border-bottom: 1px solid #312093; }}
            QLabel#title_label {{ color: #ffffff; font-weight: 600; }}
            QWidget#body_widget {{ background-color: #ffffff; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; }}
            QWidget#body_widget QLabel {{ font-size: 13px; color: #333333; }}
            QLabel#error_label {{ color: #D32F2F; font-size: 12px; font-weight: bold; }}
            QLineEdit {{ border: 1px solid #ccc; border-radius: 5px; padding: 10px 8px; font-size: 14px; background-color: #ffffff; color: #333333; }}
            QLineEdit:focus {{ border: 2px solid #a1b1f6; }}
        """)

    def connect_signals(self):
        self.login_btn.clicked.connect(self.attempt_login)
        self.pass_input.returnPressed.connect(self.attempt_login)
        self.user_input.returnPressed.connect(self.pass_input.setFocus)
        self.toggle_password_btn.toggled.connect(self.toggle_password_visibility)

    def attempt_login(self):
        username = self.user_input.text()
        password = self.pass_input.text()

        if not username or not password:
            self.show_error("Por favor, ingrese usuario y contraseña.")
            return

        self.login_btn.setText("Validando...")
        self.login_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            # 1. Codificar credenciales
            user_b64 = base64.b64encode(username.encode('utf-8')).decode('utf-8')
            pass_b64 = base64.b64encode(password.encode('utf-8')).decode('utf-8')

            # 2. Preparar payload y URL
            payload = {
                "Usuario": user_b64,
                "Password": pass_b64
            }
            login_url = f"{self.API_BASE_URL}/login"

            # 3. Llamar a la API
            response = requests.post(login_url, json=payload, timeout=15)

            # 4. Procesar respuesta de la API
            if response.status_code == 200:
                api_result = response.json()

                # 5. Extraer datos de la API (basado en el JSON que proveíste)
                connection_string = api_result.get("cadenaConexion")
                allowed_company_ids = api_result.get("idEmpresasHabilitadas")

                # La API devuelve la cadena de conexión en Base64. Debemos decodificarla.
                if connection_string:
                    try:
                        # Nunca loguear la cadena decodificada: lleva el usuario y
                        # la contraseña de la base de datos del cliente.
                        connection_string = base64.b64decode(connection_string).decode('utf-8')
                        _log.info("Cadena de conexión recibida y decodificada.")
                    except Exception as e:
                        self.show_error(f"Error de API: La 'cadenaConexion' no se pudo decodificar. Error: {e}")
                        _log.error("No se pudo decodificar la cadena de conexión en Base64.")
                        return

                # El rol sale de lo que dice la API. Antes esto estaba forzado a
                # "admin" con un comentario de "para pruebas", así que todo usuario
                # veía el Panel de Control y todos los informes.
                is_admin = api_result.get("isPermitirFacturaElectronicaProduccion", False)
                user_role_found = "admin" if is_admin else "usuario"

                if not connection_string:
                    self.show_error("Error de API: La respuesta no contiene la 'cadenaConexion'.")
                    _log.warning("La API respondió OK pero sin 'cadenaConexion'.")
                    return

                if not allowed_company_ids:
                    self.show_error("Error de API: La respuesta no contiene 'idEmpresasHabilitadas'.")
                    _log.warning("La API respondió OK pero sin 'idEmpresasHabilitadas'.")
                    return

                # 2. Verificar que la 'cadenaConexion' sea *mínimamente* válida
                #    Esto evita pasar strings vacíos o basura a db_connection.py
                conn_str_lower = connection_string.lower()
                if "server=" not in conn_str_lower and "data source=" not in conn_str_lower and "dsn=" not in conn_str_lower:
                    self.show_error(f"Error de API: La 'cadenaConexion' recibida no es válida (falta 'Server=' o 'DSN=').")
                    _log.warning("La API devolvió una 'cadenaConexion' sin Server=/DSN=.")
                    return

                # 6. Conectar a la base de datos usando la cadena de conexión
                success, message = self.db_manager.connect_with_connection_string(connection_string)

                if success:
                    # 7. Obtener la lista de empresas válidas
                    df_empresas = self.db_manager.get_empresas()
                    valid_empresas_df = df_empresas[df_empresas['idEmpresa'].isin(allowed_company_ids)]

                    if valid_empresas_df.empty:
                        self.show_error("Login exitoso, pero su usuario no tiene empresas activas asignadas.")
                        return

                    elif len(valid_empresas_df) == 1:
                        # Caso simple: 1 sola empresa
                        selected_id = valid_empresas_df.iloc[0]['idEmpresa']
                        selected_name = valid_empresas_df.iloc[0]['RazonSocial']
                        
                        config_data = {
                            "id_empresa": int(selected_id),
                            "razon_social": selected_name
                        }
                    else:
                        # Caso complejo: >1 empresa, mostrar diálogo de selección
                        self.show_error("") # Limpiar error
                        self.login_btn.setText("Seleccione Empresa...")
                        QApplication.processEvents()
                        
                        dialog = CompanySelectionDialog(valid_empresas_df, self)
                        if dialog.exec():
                            selected_id, selected_name = dialog.get_selection()
                            config_data = {
                                "id_empresa": int(selected_id),
                                "razon_social": selected_name
                            }
                        else:
                            # Usuario cerró el diálogo de selección
                            self.show_error("Selección de empresa cancelada.")
                            return
                    
                    # 8. Guardar datos y aceptar
                    self.valid_db_manager = self.db_manager
                    self.valid_config_data = config_data
                    self.valid_user_role = user_role_found
                    self.accept()

                else:
                    self.show_error(f"Error de Conexión a BD:\n{message}")
            
            elif response.status_code == 401 or response.status_code == 403:
                self.show_error("Usuario o contraseña incorrectos.")
            else:
                self.show_error(f"Error del servidor de login (Código: {response.status_code}).")

        except requests.exceptions.Timeout:
            self.show_error("Error de red: El servidor de login no respondió (Timeout).")
        except requests.exceptions.ConnectionError:
            self.show_error("Error de red: No se pudo conectar al servidor de login.")
        except Exception as e:
            self.show_error(f"Error inesperado durante el login:\n{e}\n{traceback.format_exc()}")
        
        # Asegurarse de reactivar el botón en caso de error
        self.login_btn.setText("Ingresar")
        self.login_btn.setEnabled(True)


    def show_error(self, message):
        self.error_label.setText(message)
        self.login_btn.setText("Ingresar")
        self.login_btn.setEnabled(True)


# --- NUEVA CLASE AÑADIDA ---
class CompanySelectionDialog(QDialog):
    """Diálogo para que el usuario seleccione una empresa si tiene más de una."""
    def __init__(self, empresas_df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Empresa")
        self.setWindowIcon(QIcon(FAVICON_PATH))
        self.setMinimumWidth(400)
        self.setModal(True)

        self.empresas_df = empresas_df
        self.selected_id = None
        self.selected_name = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Su usuario tiene acceso a múltiples empresas.\nPor favor, seleccione una para continuar:"))

        self.list_widget = QListWidget()
        for _, row in self.empresas_df.iterrows():
            item_text = row['RazonSocial']
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, row['idEmpresa'])
            self.list_widget.addItem(list_item)
        
        layout.addWidget(self.list_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.on_accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)

        # Seleccionar el primer item por defecto
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        
        self.list_widget.itemDoubleClicked.connect(self.on_accept)

    def on_accept(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            self.selected_id = current_item.data(Qt.ItemDataRole.UserRole)
            self.selected_name = current_item.text()
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Debe seleccionar una empresa.")

    def get_selection(self):
        return self.selected_id, self.selected_name


class ArticleSelectionDialog(QDialog):
    def __init__(self, all_articles_df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Artículos Manualmente")
        self.setMinimumSize(500, 400)
        self.all_articles_df = all_articles_df
        self.selected_ids = set()

        layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por código o descripción...")
        layout.addWidget(self.search_input)

        self.article_list_widget = QListWidget()
        layout.addWidget(self.article_list_widget)

        button_layout = QHBoxLayout()
        self.accept_btn = QPushButton("Aceptar")
        self.cancel_btn = QPushButton("Cancelar")
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.accept_btn)
        layout.addLayout(button_layout)

        self.populate_list(self.all_articles_df)

        self.search_input.textChanged.connect(self.filter_list)
        self.accept_btn.clicked.connect(self.on_accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.article_list_widget.itemChanged.connect(self.on_item_changed)

    def populate_list(self, df):
        self.article_list_widget.blockSignals(True)
        self.article_list_widget.clear()
        for _, row in df.iterrows():
            item_text = f"{row['Descripcion']} (Código: {row['CodigoArticulo']})"
            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.ItemDataRole.UserRole, row['idArticulo'])
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            
            if row['idArticulo'] in self.selected_ids:
                list_item.setCheckState(Qt.CheckState.Checked)
            else:
                list_item.setCheckState(Qt.CheckState.Unchecked)
            
            self.article_list_widget.addItem(list_item)
        self.article_list_widget.blockSignals(False)

    def filter_list(self, text):
        search_term = text.lower()
        for i in range(self.article_list_widget.count()):
            item = self.article_list_widget.item(i)
            item_text = item.text().lower()
            if search_term in item_text:
                item.setHidden(False)
            else:
                item.setHidden(True)

    def on_item_changed(self, item):
        article_id = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self.selected_ids.add(article_id)
        else:
            self.selected_ids.discard(article_id)
    
    def set_selection(self, selected_ids_list):
        self.selected_ids = set(selected_ids_list)
        self.article_list_widget.blockSignals(True)
        for i in range(self.article_list_widget.count()):
            item = self.article_list_widget.item(i)
            article_id = item.data(Qt.ItemDataRole.UserRole)
            if article_id in self.selected_ids:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
        self.article_list_widget.blockSignals(False)

    def on_accept(self):
        self.accept()

    def get_selected_ids(self):
        return list(self.selected_ids)


class InstructionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instrucciones - Analizador de Estadísticas Leontis")
        self.setWindowIcon(QIcon(FAVICON_PATH)) 
        self.setMinimumSize(750, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        text_browser = QTextBrowser()
        text_browser.setReadOnly(True)
        text_browser.setOpenExternalLinks(True) 
        text_browser.setHtml(self.get_instructions_html())
        layout.addWidget(text_browser)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject) 
        layout.addWidget(button_box)
        
        self.setStyleSheet("QDialog { background-color: #f5f5f5; }")

    def get_instructions_html(self):

        html = """
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
                line-height: 1.5; 
                font-size: 14px; 
                background-color: #ffffff;
                padding: 15px;
            }
            h1 { 
                color: #312093; 
                border-bottom: 2px solid #a1b1f6; 
                padding-bottom: 5px; 
                font-size: 20px;
            }
            h2 { 
                color: #444; 
                border-bottom: 1px solid #ccc; 
                padding-bottom: 3px; 
                margin-top: 25px;
                font-size: 17px;
            }
            h3 { 
                color: #1E40AF; 
                margin-top: 20px; 
                margin-bottom: 5px; 
                font-size: 15px;
            }
            p { margin-bottom: 10px; }
            ul { margin-left: 20px; padding-left: 5px;}
            li { margin-bottom: 8px; }
            code { 
                background-color: #f0f2f5; 
                padding: 2px 5px; 
                border-radius: 4px; 
                border: 1px solid #e0e0e0;
                font-family: Consolas, monospace;
            }
            strong { color: #000; }
        </style>
        
        <h1>Analizador de Estadísticas Leontis</h1>
        <p>Este programa se conecta a la base de datos de su sistema Leontis para generar informes y exportaciones que le ayudan a comprender mejor su negocio.</p>
        
        <h2>Conceptos Generales</h2>
        <ul>
            <li><strong>Activación de Informes:</strong> Cada tarjeta de informe tiene un botón de lápiz (✏️) a la derecha del título. Si el botón está <b>activo (azul)</b>, el informe se incluirá en las exportaciones (PDF/Excel) de la barra inferior. Si está <b>inactivo (gris)</b>, se omitirá de esas exportaciones.</li>
            
            <li><strong>Memoria de Sesión:</strong> ¡El programa recuerda sus elecciones! El estado de cada botón de lápiz (activo/inactivo) y la selección de cada menú desplegable (Período, Límite, etc.) <b>se guardan automáticamente</b> al cerrar el programa y se restauran la próxima vez que inicia sesión.</li>
            
            <li><strong>Exportación PDF vs Excel (Botones Inferiores):</strong>
                <ul>
                    <li>El botón <b>Exportar a PDF</b> (Rojo) está diseñado para <b>Gráficos y Resúmenes Visuales</b>. Generará un PDF con los gráficos de barras y líneas de los informes activos (ej: Top 10 Clientes, Ventas por Día). Los informes que son solo tablas (como Stock o Canasta) se añadirán como tablas de resumen.</li>
                    <li>El botón <b>Exportar a Excel</b> (Verde) está diseñado para <b>Datos Detallados</b>. Crea un archivo Excel donde CADA informe activo (seleccionado con ✏️) genera su propia hoja de cálculo con los datos completos (el "drill-down"), ideal para análisis profundo.</li>
                </ul>
            </li>
        </ul>

        <h2>Descripción de Informes y Opciones</h2>

        <h2 id="articulos">Pestaña: Artículos</h2>
        
        <h3>Artículos por Valor ($) / Cantidad</h3>
        <p>Estos dos informes generan los gráficos "Top" para el PDF, mostrando los artículos más vendidos. El informe de Excel asociado contiene datos detallados de stock, precios y costos.</p>
        <ul>
            <li><strong>Mostrar:</strong> Limita el gráfico del PDF (ej: Top 10). Si elige <code>Todos (sin gráfico)</code>, se omitirá del PDF pero se incluirá la lista completa en el Excel detallado.</li>
            <li><strong>Período:</strong> Filtra las ventas al período de tiempo seleccionado (ej: últimos 90 días).</li>
        </ul>

        <h3>Análisis de Canasta</h3>
        <p>Genera un informe (solo tabla para Excel/PDF) que muestra qué artículos se compran frecuentemente <b>juntos en la misma factura</b>.</p>
        <ul>
            <li><strong>Modo de Análisis:</strong> <code>Top N Asociaciones</code> busca los artículos más populares en general. <code>Manual</code> le permite elegir artículos específicos para ver con qué otros se vendieron.</li>
            <li><strong>Limitar Asociados a:</strong> Controla cuántos artículos "comprados-juntos" se muestran en la lista de resultados (ej: mostrar solo los 5 más comunes para cada artículo principal).</li>
            <li><strong>Período:</strong> El rango de tiempo para buscar facturas.</li>
        </ul>
        
        <h3>Exportación Rápida de Artículos</h3>
        <p>Este <b>no usa los botones inferiores</b>. Es un botón de exportación directa que genera un Excel con su base de datos de artículos (stock, precios, códigos, etc.).</p>
        <ul>
            <li><strong>Opción:</strong> Permite elegir si desea solo artículos 'Activos' en el sistema o absolutamente todos.</li>
        </ul>

        <h2 id="clientes">Pestaña: Clientes</h2>

        <h3>Clientes por Facturación</h3>
        <p>Genera el gráfico "Top Clientes" para el PDF, basado en su facturación total en el período.</p>
        <ul>
            <li><strong>Mostrar:</strong> Límite para el gráfico PDF (ej: Top 10).</li>
            <li><strong>Período:</strong> Filtra las ventas al período de tiempo seleccionado.</li>
            <li><strong>Incluir Consumidor Final:</strong> Si está marcado, incluye al cliente "Consumidor Final" genérico en el cálculo, que a menudo distorsiona el gráfico "Top". Se recomienda mantenerlo desmarcado.</li>
        </ul>

        <h3>Análisis de Cuenta Corriente</h3>
        <p>Analiza las deudas de clientes. Genera un gráfico PDF con los mayores deudores y un informe Excel extremadamente detallado.</p>
        <ul>
            <li><strong>Alcance de Clientes (Gráfico):</strong> Define el límite para el gráfico PDF (ej: Top 10 Deudores).</li>
            <li><strong>Detalle de Comprobantes (Exportar):</strong> Controla el nivel de detalle <b>solo para el Excel</b>:
                <ul>
                    <li><code>Solo Totales</code>: Una fila por cliente con su saldo total.</li>
                    <li><code>Top N Adeudados</code>: Muestra solo los N comprobantes impagos más grandes de cada cliente.</li>
                    <li><code>Todos los Adeudados</code>: Muestra todos los comprobantes con saldo pendiente de cada cliente.</li>
                    <li><code>Histórico</code>: Muestra todos los movimientos (pagos e impagos) de la cuenta corriente de los clientes seleccionados en el "Alcance".</li>
                </ul>
            </li>
        </ul>

        <h3>Segmentación de Clientes (RFM)</h3>
        <p>Analiza a todos sus clientes (excepto C.F.) y los puntúa según <b>Recencia</b> (qué tan reciente compró), <b>Frecuencia</b> (qué tan seguido compra) y <b>Monetario</b> (cuánto gasta). Luego, los agrupa en segmentos de negocio (Campeones, Leales, En Riesgo, Perdidos, etc.). No requiere configuración.</p>
        <p>Este informe genera un gráfico resumen de conteos para el PDF y una hoja de Excel detallada con la puntuación y segmento de cada cliente, ideal para exportar y realizar acciones de marketing.</p>

        <h3>Exportación Rápida de Clientes</h3>
        <p>Igual que la exportación de artículos, este es un botón directo (no usa el footer) para descargar la base de datos de clientes (saldos, contacto, CUIT, etc.) a Excel.</p>

        <h2 id="ventas">Pestaña: Ventas</h2>
        <h3>Ventas por Día</h3>
        <p>Genera dos gráficos para el PDF: un gráfico de línea con el <b>Total de Ventas</b> por día, y un gráfico multilínea mostrando la venta diaria separada por <b>Medio de Pago</b>.</p>
        <ul>
            <li><strong>Período:</strong> Rango de tiempo para el gráfico.</li>
            <li><strong>Medios de Pago:</strong> Define qué líneas se incluyen en el gráfico multilínea (afecta también al Excel).</li>
        </ul>

        <h2 id="stock">Pestaña: Stock</h2>
        <h3>Análisis de Stock (Tabla)</h3>
        <p>Genera un informe de tabla (solo Excel/PDF) listando artículos según sus existencias. No genera gráfico.</p>
        <ul>
            <li><strong>Reporte:</strong> Permite filtrar por más stock, menos stock (solo positivos), o stock cero/negativo. La opción "Todos" es solo para Excel.</li>
        </ul>

        <h3>Informe de Inventario Obsoleto (SLOB)</h3>
        <p>Genera un informe de tabla (solo Excel/PDF) que calcula el <b>valor inmovilizado</b>. Busca artículos que SÍ tienen stock positivo pero que <b>no se han vendido</b> en el umbral de tiempo seleccionado (ej: stock positivo que no rota hace 180 días). También incluye artículos con stock que <b>nunca se han vendido</b>.</p>
        <ul>
            <li><strong>Umbral de Inactividad:</strong> Define el tiempo mínimo sin ventas para considerar un artículo como obsoleto (ej: Más de 90 días).</li>
        </ul>
        """
        return html


class MainWindow(QMainWindow):
    # Dispara la carga del dashboard EN EL HILO DEL WORKER. Una señal conectada a
    # un slot de un QObject que vive en otro hilo usa conexión en cola, que es lo
    # único que efectivamente cruza de hilo.
    request_dashboard_load = Signal(bool)

    def __init__(self, db_manager, config_data, user_role="usuario"):
        super().__init__()
        self.setWindowTitle("Analizador de Estadísticas Leontis v4.2")
        self.resize(1100, 700)
        self.setMinimumSize(900, 600)

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: #F0F2F5; }}
            {MODERN_CARD_STYLE}
        """)

        self.setWindowIcon(QIcon(FAVICON_PATH))

        # Las preferencias se guardan POR EMPRESA. Con un usuario que tiene varias,
        # la selección manual de artículos de la canasta son IDs que en otra
        # empresa apuntan a otro artículo o no existen.
        self.settings = QSettings("Leontis", "AnalizadorEstadisticas")
        empresa_id = (config_data or {}).get("id_empresa")
        self.settings_prefix = f"empresa_{empresa_id}/" if empresa_id else ""

        self.db_manager = db_manager
        self.stats_generator = StatisticsGenerator(self.db_manager)
        self.user_role = user_role

        # Cachea el detalle de cada informe mientras dura una exportación:
        # `generate_statistics()` y `get_detailed_data_for_report()` piden lo mismo
        # dos veces, y el RFM o la canasta recalculan sobre la base entera.
        self._cache_informes = {}

        self.report_short_names = {
            "top_articles_value": "ArtValor", "top_articles_qty": "ArtCant",
            "top_customers": "Clientes", "sales_over_time": "VentasDia",
            "sales_by_payment": "VentasDia", "stock_analysis": "Stock",
            "market_basket": "Canasta",
            "export_clients": "ExportClientes", "export_articles": "ExportArticulos",
            "cta_cte": "CtaCte",
            "slob_analysis": "StockObsoleto",
            "rfm_segmentation": "RFM",
            "margin_by_article": "Margen",
            "abc_analysis": "ABC",
            "purchase_suggestion": "SugeridoCompra",
            "aging_cta_cte": "Aging",
        }

        self.report_buttons = {}  
        self.report_cards = {}    
        self.report_titles = {}   

        self.active_reports_grid_map = {}
        self.inactive_reports_map = {}
        self.report_widget_config = {}
        self.report_tabs = {}

        self.all_articles_df = pd.DataFrame() 
        self.manual_basket_selection = []
        
        self.ui_factory = UIFactory(self)
        
        self.init_ui()
        
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.statusBar().addWidget(self.status_label, 1)

        self.logic = AppLogic(self)
        self.logic.config_data = config_data
        
        self.connect_signals()
        
        self.dashboard_thread = None
        self.dashboard_worker = None
        
        self.is_loading_settings = False
        
        self.conn_group.setVisible(False) 
        self.load_settings()
        self.logic.setup_empresa_and_ui()
        
        self.apply_role_restrictions()


    def setup_dashboard(self):
        if self.dashboard_thread is not None:
            return

        self.dashboard_thread = QThread(self)
        self.dashboard_worker = DashboardWorker(
            self.stats_generator,
            self.settings,
            self.logic.selected_empresa_id
        )
        self.dashboard_worker.moveToThread(self.dashboard_thread)
        self.dashboard_worker.data_loaded.connect(self.populate_dashboard_cards)
        # Esta conexión es la que hace que el trabajo corra de verdad en el otro
        # hilo: emisor en el hilo GUI, receptor en el del worker.
        self.request_dashboard_load.connect(self.dashboard_worker.run_all_loads)
        self.admin_sync_button.clicked.connect(self.trigger_manual_dashboard_sync)
        self.dashboard_thread.start()
        self.trigger_dashboard_load(force_refresh=False)


    def _is_layout_visibly_empty(self, layout):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget() and not item.widget().isHidden():
                return False
        return True

    def apply_role_restrictions(self):
        admin_tab_index = self.main_tab_widget.indexOf(self.admin_dashboard_tab)

        if admin_tab_index != -1:
            if self.user_role == "admin":
                _log.info("Rol Admin: se muestra el Panel de Control.")
                self.main_tab_widget.setTabVisible(admin_tab_index, True)
                self.setup_dashboard()
            else:
                _log.info("Rol Usuario: se oculta el Panel de Control.")
                self.main_tab_widget.setTabVisible(admin_tab_index, False)
        else:
            _log.warning("No se encontró la pestaña 'admin_dashboard_tab'.")
            
        if self.user_role == "admin":
            _log.debug("Sesión de Administrador: sin restricciones de informes.")
            return

        _log.debug("Sesión de Usuario: aplicando restricciones de rol.")
        
        allowed_reports = {
            "export_articles",
            "export_clients",
            "stock_analysis"
        }

        for key, config in self.report_widget_config.items():
            if key not in allowed_reports:
                try:
                    report_card_widget = config.get("widget")
                    if report_card_widget:
                        report_card_widget.setVisible(False)

                except Exception as e:
                    _log.warning("No se pudo restringir la tarjeta '%s': %s", key, e)

        for inactive_group, inactive_layout in self.inactive_reports_map.values():
            if self._is_layout_visibly_empty(inactive_layout):
                inactive_group.setVisible(False)

        tab_has_visible_content = {}
        for tab_key in self.report_tabs.keys():
            tab_has_visible_content[tab_key] = False

        for report_key in allowed_reports:
            if report_key in self.report_widget_config:
                tab_key = self.report_widget_config[report_key]["tab_key"]
                if tab_key in tab_has_visible_content:
                    tab_has_visible_content[tab_key] = True
        
        for tab_key, has_content in tab_has_visible_content.items():
            if not has_content:
                tab_widget_to_hide = self.report_tabs.get(tab_key)
                if tab_widget_to_hide:
                    index = self.main_tab_widget.indexOf(tab_widget_to_hide)
                    if index != -1:
                        self.main_tab_widget.setTabVisible(index, False)


    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll_content_widget = QWidget()
        scroll_content_layout = QVBoxLayout(scroll_content_widget)
        scroll_content_layout.setContentsMargins(0, 0, 0, 0)
        scroll_content_layout.setSpacing(0)

        self.conn_group = self.ui_factory.create_connection_panel()
        login_layout = QHBoxLayout()
        login_layout.addStretch()
        login_layout.addWidget(self.conn_group)
        login_layout.addStretch()
        scroll_content_layout.addLayout(login_layout)

        self.empresa_group = self.ui_factory.create_empresa_panel()
        scroll_content_layout.addWidget(self.empresa_group)

        self.main_tab_widget = QTabWidget()
        self.main_tab_widget.setStyleSheet(MODERN_TAB_STYLE)
        scroll_content_layout.addWidget(self.main_tab_widget)
        self.selection_group = self.main_tab_widget 

        self.ui_factory.create_statistics_panel() 

        scroll_content_layout.addStretch(1)

        main_scroll_area = QScrollArea()
        main_scroll_area.setWidgetResizable(True)
        main_scroll_area.setWidget(scroll_content_widget)
        main_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        main_scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        main_layout.addWidget(main_scroll_area)

        self.footer_widget = self.ui_factory.create_footer_panel()
        main_layout.addWidget(self.footer_widget)
        
        self.setStatusBar(QStatusBar(self))

    # Informes que son solo tabla: no generan gráfico y en el PDF salen como
    # tabla renderizada. Tenerlos en un solo lugar evita que cada rama del
    # exportador arrastre su propia lista.
    REPORTES_SOLO_TABLA = ("stock_analysis", "market_basket", "slob_analysis",
                           "purchase_suggestion", "aging_cta_cte")

    # Columnas que conviene recortar en el PDF para que la tabla entre a lo ancho.
    TRUNCAR_EN_PDF = {
        "stock_analysis": {"Código": 15, "Descripción": 15},
        "market_basket": {"Código": 15, "Descripción": 30, "Artículos Asociados": 45},
        "purchase_suggestion": {"Proveedor": 22, "Código": 12, "Descripción": 28},
        "aging_cta_cte": {"Cliente": 25, "Teléfono": 15},
    }

    def create_chart_image_in_memory(self, df, title, xlabel, ylabel, chart_type):
        """Dibuja el gráfico y devuelve (figura, PNG en memoria).

        Quien recibe la figura es responsable de cerrarla con `plt.close()`.
        """
        if df is None or df.empty:
            return None, None

        chart_exporter = MatplotlibWidget()
        try:
            if chart_type == "multi-line":
                chart_exporter.plot_multi_line_chart(df, title, xlabel, ylabel)
            elif chart_type is True:
                df_copy = df.copy()
                df_copy.iloc[:, 0] = pd.to_datetime(df_copy.iloc[:, 0], errors='coerce')
                df_copy.dropna(subset=[df_copy.columns[0]], inplace=True)
                if df_copy.empty:
                    plt.close(chart_exporter.figure)
                    return None, None
                chart_exporter.plot_line_chart(
                    df_copy.iloc[:, 0], df_copy.iloc[:, 1], title, xlabel, ylabel)
            else:
                chart_exporter.plot_bar_chart(
                    df.iloc[:, 0], df.iloc[:, 1], title, xlabel, ylabel)

            img_buffer = io.BytesIO()
            chart_exporter.figure.savefig(
                img_buffer, format='png', bbox_inches='tight', dpi=150)
            img_buffer.seek(0)
            return chart_exporter.figure, img_buffer
        except Exception:
            plt.close(chart_exporter.figure)
            _log.exception("No se pudo generar el gráfico '%s'", title)
            return None, None
        finally:
            # El QWidget contenedor no se necesita para exportar: si no se
            # descarta, cada exportación deja uno vivo con su canvas.
            chart_exporter.deleteLater()

    def _truncar_para_pdf(self, df, report_name):
        """Recorta las columnas largas para que la tabla entre en la página."""
        reglas = self.TRUNCAR_EN_PDF.get(report_name)
        if not reglas or df is None or df.empty:
            return df

        df = df.copy()
        for columna, largo in reglas.items():
            if columna in df.columns:
                df[columna] = df[columna].apply(
                    lambda v, n=largo: v[:n] + ".." if isinstance(v, str) and len(v) > n else v)
        return df

    def _titulo_tabla_pdf(self, report_name, titulo_por_defecto):
        """Título del informe-tabla, con la opción elegida en la tarjeta."""
        if report_name == "stock_analysis":
            return (f"Análisis de Stock: {self.stock_report_combo.currentText()}"
                    f" ({self.stock_limit_combo.currentText()})")
        if report_name == "slob_analysis":
            return ("Informe de Inventario Obsoleto\n"
                    f"({self.slob_threshold_combo.currentText()})")
        if report_name == "market_basket":
            modo = self.basket_mode_combo.currentText()
            if self.basket_mode_combo.currentData() == 'manual':
                modo = f"Manual ({len(self.manual_basket_selection)} art.)"
            return (f"Análisis de Canasta: {modo}\n"
                    f"(Período: {self.basket_period_combo.currentText()})")
        if report_name == "purchase_suggestion":
            return ("Sugerido de Compra por Proveedor\n"
                    f"({self.purchase_target_combo.currentText()})")
        if report_name == "aging_cta_cte":
            return ("Antigüedad de la Deuda por Cliente\n"
                    f"({self.aging_limit_combo.currentText()})")
        return titulo_por_defecto

    def _figura_de_tabla_para_pdf(self, report_name, empresa_id, titulo,
                                  limite_filas=100):
        """Arma la figura-tabla de un informe que no tiene gráfico."""
        df = self.logic.get_detailed_data_for_report(report_name, empresa_id)
        if df is None or df.empty:
            return None

        if len(df) > limite_filas:
            titulo = f"(Primeras {limite_filas} filas de {len(df)}) {titulo}"
            df = df.head(limite_filas)

        return self._create_table_figure(self._truncar_para_pdf(df, report_name), titulo)

    def _create_table_figure(self, df, title):
        if df is None or df.empty:
            return None
        
        if isinstance(df.index, pd.RangeIndex):
            df_display = df.reset_index(drop=True)
        else:
            df_display = df.reset_index()

        cols = df_display.columns
        num_rows, num_cols = df_display.shape
        
        fig_height = min(10, num_rows * 0.3 + 1.5)
        fig_width = min(15, num_cols * 1.8)

        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.axis('tight')
        ax.axis('off')
        
        the_table = ax.table(cellText=df_display.values, colLabels=cols, loc='center', cellLoc='left')
        the_table.auto_set_font_size(False)
        the_table.set_fontsize(9)
        the_table.scale(1.2, 1.2)

        for (i, j), cell in the_table.get_celld().items():
            if i == 0:
                cell.set_facecolor("#D7E4BC")
                cell.set_text_props(weight='bold')
        
        ax.set_title(title, weight='bold', size='large', pad=20)
        fig.tight_layout()
        
        return fig

    def ask_next_action(self):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Exportación Completa")
        msg_box.setText("¿Qué desea hacer a continuación?")
        
        btn_another = msg_box.addButton("Exportar otro informe", QMessageBox.ActionRole)
        btn_close = msg_box.addButton("Cerrar el programa", QMessageBox.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_close:
            self.save_settings()
            self.close()

    def export_to_pdf(self):
        empresa_id = self.logic.selected_empresa_id
        if not empresa_id: return

        self._cache_informes.clear()
        self.status_bar_message("Generando datos para el PDF...", 0)
        report_data_list = self.logic.generate_statistics()
        
        if not report_data_list:
            self.status_bar_message("No se seleccionó ningún informe o no se pudieron generar datos.", 5000)
            return

        last_dir = self.settings.value("last_export_dir", os.path.expanduser("~"))
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_keys = [data[6] for data in report_data_list]
        short_names = [self.report_short_names.get(k) for k in report_keys]
        unique_short_names = sorted(list(set(filter(None, short_names))))
        report_filename_part = "_".join(unique_short_names)
        
        if not report_filename_part: report_filename_part = "Reporte"

        default_filename = os.path.join(last_dir, f"{date_str}_{report_filename_part}.pdf")
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar como PDF", default_filename, "Archivos PDF (*.pdf)")
        
        if not file_path:
            self.status_bar_message("Exportación a PDF cancelada.", 3000)
            return
        
        self.settings.setValue("last_export_dir", os.path.dirname(file_path))

        all_figures = []
        for idx, (df, title, xlabel, ylabel, chart_type, limit, report_name) in enumerate(report_data_list):
            self.status_bar_message(
                f"Procesando sección ({idx+1}/{len(report_data_list)}): {title}...", 0)

            if report_name in self.REPORTES_SOLO_TABLA:
                figure = self._figura_de_tabla_para_pdf(
                    report_name, empresa_id, self._titulo_tabla_pdf(report_name, title))
                if figure:
                    all_figures.append(figure)
                continue

            # "Todos (sin gráfico)": el usuario pidió el listado completo, que va
            # al Excel. Un gráfico de barras con 4000 filas no se lee.
            if ("top" in report_name or "cta_cte" in report_name) and limit == -1:
                continue

            figure, _ = self.create_chart_image_in_memory(df, title, xlabel, ylabel, chart_type)
            if figure:
                all_figures.append(figure)
        
        if all_figures:
            while True:
                try:
                    self.status_bar_message("Escribiendo archivo PDF... Por favor, espere.", 0)
                    with PdfPages(file_path) as pdf:
                        for fig in all_figures:
                            pdf.savefig(fig, bbox_inches='tight')
                            plt.close(fig)
                    
                    self.status_bar_message(f"¡Éxito! Informe guardado en {file_path}", 7000)
                    self.ask_next_action()
                    break

                except PermissionError as e:
                    error_msg = f"No se pudo guardar el archivo PDF (Permiso Denegado):\n\n{file_path}\n\nAsegúrese de que el archivo NO esté abierto y presione 'Reintentar'.\n\nDetalle: {e}"
                    msg_box = QMessageBox(self)
                    msg_box.setIcon(QMessageBox.Warning)
                    msg_box.setWindowTitle("Error de Permisos")
                    msg_box.setText(error_msg)
                    retry_btn = msg_box.addButton("Reintentar", QMessageBox.ActionRole)
                    cancel_btn = msg_box.addButton("Cancelar Exportación", QMessageBox.RejectRole)
                    
                    msg_box.exec()
                    
                    if msg_box.clickedButton() == cancel_btn:
                        self.status_bar_message("Exportación a PDF cancelada por el usuario.", 5000)
                        break
                except Exception as e:
                    self.status_bar_message(f"Error al guardar el PDF: {e}", 7000)
                    QMessageBox.critical(self, "Error de Exportación", f"No se pudo guardar el archivo PDF:\n{e}")
                    break
        else:
            QMessageBox.information(self, "Sin Contenido", "No se generó contenido exportable.")
            self.status_bar_message("No se pudo generar ningún gráfico o tabla para la exportación.", 5000)

    def export_to_excel(self):
        empresa_id = self.logic.selected_empresa_id
        if not empresa_id: return

        self._cache_informes.clear()
        self.status_bar_message("Generando datos para Excel...", 0)

        try:
            report_data_list = self.logic.generate_statistics()
        except Exception as e:
            QMessageBox.critical(self, "Error Crítico", f"Falló la generación de datos antes de crear el Excel:\n{e}")
            return

        if not report_data_list:
            self.status_bar_message("No se seleccionó ningún informe.", 5000); return

        last_dir = self.settings.value("last_export_dir", os.path.expanduser("~"))

        date_str = datetime.now().strftime("%Y-%m-%d")
        report_keys = [data[6] for data in report_data_list]
        short_names = [self.report_short_names.get(k) for k in report_keys]
        unique_short_names = sorted(list(set(filter(None, short_names))))
        report_filename_part = "_".join(unique_short_names)

        if not report_filename_part: report_filename_part = "Reporte_Detallado"

        default_filename = os.path.join(last_dir, f"{date_str}_{report_filename_part}.xlsx")
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar como Excel", default_filename, "Archivos Excel (*.xlsx)")

        if not file_path:
            self.status_bar_message("Exportación a Excel cancelada.", 3000); return

        self.settings.setValue("last_export_dir", os.path.dirname(file_path))

        while True:
            try:
                self.status_bar_message("Creando archivo Excel... Por favor, espere.", 0)
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    workbook = writer.book
                    header_format = workbook.add_format({'bold': True, 'valign': 'top', 'fg_color': '#D7E4BC', 'border': 1, 'text_wrap': True})
                    currency_format = workbook.add_format({'num_format': '$#,##0.00'})
                    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})

                    title_format = workbook.add_format({
                        'bold': True,
                        'font_size': 14,
                        'font_color': '#312093',
                        'align': 'left',
                        'valign': 'vcenter'
                    })

                    zebra_format = workbook.add_format({'bg_color': '#F2F2F2'})

                    red_text_format = workbook.add_format({'font_color': '#D00000'})
                    
                    seg_green_format = workbook.add_format({
                        'bg_color': '#C6EFCE',
                        'font_color': '#006100'
                    })
                    
                    seg_red_format = workbook.add_format({
                        'bg_color': '#FFC7CE',
                        'font_color': '#9C0006'
                    })
                    
                    default_cell_format = workbook.add_format()

                    hojas_usadas = set()

                    for idx, (df_chart, title, xlabel, ylabel, chart_type, limit, report_name) in enumerate(report_data_list):
                        progress_text = f"Procesando hoja ({idx+1}/{len(report_data_list)}): {title}..."
                        self.status_bar_message(progress_text, 0)

                        try:
                            if report_name == "sales_over_time":
                                continue

                            df_excel = self.logic.get_detailed_data_for_report(report_name, empresa_id)
                            if df_excel is None or df_excel.empty: continue
                            
                            key_para_titulo = "sales_over_time" if report_name == "sales_by_payment" else report_name

                            base_spanish_title = self.report_titles.get(key_para_titulo, "Reporte")

                            sheet_name = self._nombre_de_hoja(base_spanish_title, hojas_usadas)

                            df_excel.to_excel(writer, sheet_name=sheet_name, index=False, startrow=2, header=False)
                            worksheet = writer.sheets[sheet_name]
                            
                            worksheet.merge_range(0, 0, 0, len(df_excel.columns) - 1, f"Reporte: {title}", title_format)
                            
                            for col_num, value in enumerate(df_excel.columns.values):
                                worksheet.write(1, col_num, value, header_format)
                            
                            worksheet.autofit()

                            data_rows = len(df_excel)
                            if data_rows > 0:
                                worksheet.conditional_format(
                                    2, 0, data_rows + 1, len(df_excel.columns) - 1,
                                    {
                                        'type': 'formula',
                                        'criteria': '=MOD(ROW(), 2) = 0',
                                        'format': zebra_format
                                    }
                                )
                            
                            worksheet.autofit()
                            
                            if report_name in ["top_articles_value", "top_articles_qty"]:
                                worksheet.set_column('C:E', 15, currency_format)
                                worksheet.set_column('H:H', 18, currency_format)
                            if report_name == "top_customers":
                                 worksheet.set_column('C:D', 18, currency_format)
                            if "sales" in report_name:
                                 worksheet.set_column('A:A', 15, date_format)
                                 worksheet.set_column('B:Z', 18, currency_format)
                            if report_name == "market_basket":
                                worksheet.set_column('C:E', 18, currency_format)
                                worksheet.set_column('F:F', 70)
                                worksheet.set_column('G:G', 15)

                                # Nombres de variable propios: antes el índice del
                                # bucle interno pisaba el del `enumerate` de los
                                # informes, que es la variable que numera las hojas.
                                target_col_idx = -1
                                for col_idx, col_name in enumerate(df_excel.columns):
                                    if col_name == 'Artículos Asociados':
                                        target_col_idx = col_idx
                                        break

                                if target_col_idx != -1:
                                    for fila in range(len(df_excel)):
                                        cell_text = str(df_excel.iat[fila, target_col_idx])
                                        items = cell_text.split(', ')

                                        segments_to_write = []

                                        for item_idx, item in enumerate(items):
                                            text_to_add = item if item_idx == len(items) - 1 else item + ", "

                                            if item_idx % 2 == 0:
                                                if item_idx == 0:
                                                    segments_to_write.extend([default_cell_format, text_to_add])
                                                else:
                                                    segments_to_write.append(text_to_add)
                                            else:
                                                segments_to_write.extend([red_text_format, text_to_add])

                                        if segments_to_write:
                                            # xlsxwriter corrompe el Excel si usas rich_string con menos de 3 argumentos
                                            if len(segments_to_write) <= 2:
                                                worksheet.write_string(fila + 2, target_col_idx, segments_to_write[1], default_cell_format)
                                            else:
                                                worksheet.write_rich_string(fila + 2, target_col_idx, *segments_to_write)

                            if report_name == "cta_cte":
                                if 'Fecha' in df_excel.columns:
                                    worksheet.set_column('A:A', 15, date_format)
                                    worksheet.set_column('G:H', 18, currency_format)
                                    worksheet.set_column('K:K', 18, currency_format)
                                else:
                                    worksheet.set_column('E:E', 18, currency_format)

                            if report_name == "rfm_segmentation":
                                worksheet.set_column('D:D', 20)
                                worksheet.set_column('E:E', 25)
                                worksheet.set_column('F:F', 25, currency_format)

                                data_rows = len(df_excel)
                                if data_rows > 0:
                                    data_range = (2, 10, data_rows + 1, 14)
                                    
                                    worksheet.conditional_format(data_range[0], data_range[1], data_range[2], data_range[3], {
                                        'type': 'cell',
                                        'criteria': '==',
                                        'value': '"Si"',
                                        'format': seg_green_format
                                    })
                                    
                                    worksheet.conditional_format(data_range[0], data_range[1], data_range[2], data_range[3], {
                                        'type': 'cell',
                                        'criteria': '==',
                                        'value': '"No"',
                                        'format': seg_red_format
                                    })

                            if report_name == "slob_analysis":
                                worksheet.set_column('E:E', 20, currency_format)

                            if report_name == "margin_by_article":
                                worksheet.set_column('D:F', 18, currency_format)

                            if report_name == "abc_analysis":
                                worksheet.set_column('F:F', 18, currency_format)
                                worksheet.set_column('J:J', 20, currency_format)

                            if report_name == "purchase_suggestion":
                                worksheet.set_column('A:A', 28)
                                worksheet.set_column('C:C', 35)
                                worksheet.set_column('J:K', 18, currency_format)

                            if report_name == "aging_cta_cte":
                                worksheet.set_column('B:B', 30)
                                worksheet.set_column('D:I', 16, currency_format)

                            is_top_all_report = ("top" in report_name or "cta_cte" in report_name) and limit == -1

                            if report_name not in self.REPORTES_SOLO_TABLA and not is_top_all_report:
                                figura, img_buffer = self.create_chart_image_in_memory(
                                    df_chart, title, xlabel, ylabel, chart_type)
                                try:
                                    # Solo insertar si la imagen es válida (> 1 KB)
                                    if img_buffer and img_buffer.getbuffer().nbytes > 1000:
                                        worksheet.insert_image(
                                            2, len(df_excel.columns) + 1, '',
                                            {'image_data': img_buffer})
                                finally:
                                    # En la ruta del PDF las figuras se cierran al
                                    # escribirlas; acá no se cerraban nunca y cada
                                    # exportación dejaba unas cuantas abiertas.
                                    if figura is not None:
                                        plt.close(figura)

                        except Exception as e:
                            _log.exception("Error al procesar el reporte '%s'", title)
                            QMessageBox.warning(self, "Error en Reporte", f"Ocurrió un error al procesar el reporte '{title}':\n{e}\n\nSe continuará con los demás.")

                self.status_bar_message(f"¡Éxito! Informe guardado en {file_path}", 7000)
                self.ask_next_action()
                break

            except PermissionError as e:
                error_msg = f"No se pudo guardar el archivo Excel (Permiso Denegado):\n\n{file_path}\n\nAsegúrese de que el archivo NO esté abierto y presione 'Reintentar'.\n\nDetalle: {e}"
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Warning)
                msg_box.setWindowTitle("Error de Permisos")
                msg_box.setText(error_msg)
                retry_btn = msg_box.addButton("Reintentar", QMessageBox.ActionRole)
                cancel_btn = msg_box.addButton("Cancelar Exportación", QMessageBox.RejectRole)
                
                msg_box.exec()
                
                if msg_box.clickedButton() == cancel_btn:
                    self.status_bar_message("Exportación a Excel cancelada por el usuario.", 5000)
                    break
            except Exception as e:
                self.status_bar_message(f"Error al exportar a Excel: {e}", 7000)
                QMessageBox.critical(self, "Error de Exportación", f"No se pudo guardar el archivo Excel:\n{e}")
                break

    @staticmethod
    def _nombre_de_hoja(titulo, usados):
        """Nombre de hoja válido y único.

        Excel prohíbe []:*?/\\ y corta en 31 caracteres. Dos informes cuyos
        títulos coincidan al truncarse harían abortar la exportación entera con
        un "Sheetname already used", así que se desambigua con un sufijo.
        """
        limpio = titulo.split('(')[0].strip()
        for caracter in '[]:*?/\\':
            limpio = limpio.replace(caracter, ' ')
        limpio = ' '.join(limpio.split())[:31] or "Reporte"

        candidato, n = limpio, 2
        while candidato.lower() in usados:
            sufijo = f" {n}"
            candidato = limpio[:31 - len(sufijo)] + sufijo
            n += 1

        usados.add(candidato.lower())
        return candidato

    def export_quick_clients_excel(self):
        mode = self.export_clients_mode_combo.currentData()
        empresa_id = self.logic.selected_empresa_id
        
        self._execute_quick_export(
            report_key_name="Listado_Clientes",
            df_provider_func=lambda: self.stats_generator.get_export_all_clients(empresa_id, mode)
        )

    def export_quick_articles_excel(self):
        mode = self.export_articles_mode_combo.currentData()
        empresa_id = self.logic.selected_empresa_id

        self._execute_quick_export(
            report_key_name="Listado_Articulos",
            df_provider_func=lambda: self.stats_generator.get_export_all_articles(empresa_id, mode)
        )
        
    def _execute_quick_export(self, report_key_name, df_provider_func):
        self.status_bar_message(f"Generando {report_key_name}...", 0)
        
        try:
            df = df_provider_func()
            if df is None or df.empty:
                QMessageBox.information(self, "Sin Datos", "La consulta no devolvió resultados.")
                self.status_bar_message("Exportación rápida: No se encontraron datos.", 4000)
                return

            last_dir = self.settings.value("last_export_dir", os.path.expanduser("~"))
            date_str = datetime.now().strftime("%Y-%m-%d")
            default_filename = os.path.join(last_dir, f"{date_str}_{report_key_name}.xlsx")
            
            file_path, _ = QFileDialog.getSaveFileName(self, f"Guardar {report_key_name}", default_filename, "Archivos Excel (*.xlsx)")
            
            if not file_path:
                self.status_bar_message("Exportación rápida cancelada.", 3000)
                return

            self.settings.setValue("last_export_dir", os.path.dirname(file_path))

            while True:
                try:
                    df.to_excel(file_path, index=False, engine='xlsxwriter')
                    self.status_bar_message(f"¡Éxito! Archivo guardado en {file_path}", 7000)
                    self.ask_next_action()
                    break
                except PermissionError:
                    msg_box = QMessageBox(self)
                    msg_box.setIcon(QMessageBox.Warning)
                    msg_box.setWindowTitle("Error de Permisos")
                    msg_box.setText(f"No se pudo guardar el archivo. Asegúrese de que no esté abierto en Excel y reintente.")
                    retry_btn = msg_box.addButton("Reintentar", QMessageBox.ActionRole)
                    cancel_btn = msg_box.addButton("Cancelar", QMessageBox.RejectRole)
                    msg_box.exec()
                    if msg_box.clickedButton() == cancel_btn:
                        break
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Ocurrió un error inesperado al guardar el archivo:\n{e}")
                    break

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Ocurrió un error al generar los datos para la exportación:\n{e}")
            self.status_bar_message("Error al generar datos para exportación rápida.", 5000)

    def show_instructions_modal(self):
        dialog = InstructionsDialog(self)
        dialog.exec()

    def handle_report_toggle(self, key, is_active):
        if key not in self.report_widget_config:
            _log.warning("Clave de reporte desconocida: %s", key)
            return

        config = self.report_widget_config[key]
        widget_container = config["widget"]
        content_group = self.report_cards[key]
        active_grid = config["layout"]
        original_pos = config["pos"]
        tab_key = config["tab_key"]

        inactive_group, inactive_layout = self.inactive_reports_map[tab_key]

        content_group.setVisible(is_active)

        if is_active:
            inactive_layout.removeWidget(widget_container)
            active_grid.addWidget(widget_container, original_pos[0], original_pos[1], original_pos[2], original_pos[3])
        else:
            active_grid.removeWidget(widget_container)
            inactive_layout.addWidget(widget_container)
            inactive_group.setVisible(True)

        if inactive_layout.count() == 0:
            inactive_group.setVisible(False)

        if tab_key == "articulos":
            self.reflow_articles_grid()

    def reflow_articles_grid(self):
        grid = self.active_reports_grid_map["articulos"]
        
        card1_active = self.report_buttons["top_articles_value"].isChecked()
        card2_active = self.report_buttons["top_articles_qty"].isChecked()

        card1_widget = self.report_widget_config["top_articles_value"]["widget"]
        card2_widget = self.report_widget_config["top_articles_qty"]["widget"]


        if card1_active:
            card1_widget.setParent(None)
        if card2_active:
            card2_widget.setParent(None)

        if card1_active and card2_active:
            grid.addWidget(card1_widget, 0, 0, 1, 1)
            grid.addWidget(card2_widget, 0, 1, 1, 1)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
        
        elif card1_active:
            grid.addWidget(card1_widget, 0, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 0)
        
        elif card2_active:
            grid.addWidget(card2_widget, 0, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 0)
        
        else:
            grid.setColumnStretch(0, 0)
            grid.setColumnStretch(1, 0)
        
        pass


    def connect_signals(self):
        self.basket_mode_combo.currentIndexChanged.connect(self.on_basket_mode_changed)
        self.basket_select_btn.clicked.connect(self.open_article_selection_modal)

        self.export_pdf_btn.clicked.connect(self.export_to_pdf)
        self.export_excel_btn.clicked.connect(self.export_to_excel)
        
        self.export_clients_excel_btn.clicked.connect(self.export_quick_clients_excel)
        self.export_articles_excel_btn.clicked.connect(self.export_quick_articles_excel)
        
        self.instructions_btn.clicked.connect(self.show_instructions_modal)
        
    def on_basket_mode_changed(self):
        mode = self.basket_mode_combo.currentData()
        is_manual = (mode == 'manual')
        self.basket_select_btn.setVisible(is_manual)

    def open_article_selection_modal(self):
        if self.all_articles_df.empty:
            QMessageBox.warning(self, "Datos no disponibles", "No se han cargado artículos.")
            return
        
        dialog = ArticleSelectionDialog(self.all_articles_df, self)
        dialog.set_selection(self.manual_basket_selection) 
        
        if dialog.exec():
            self.manual_basket_selection = dialog.get_selected_ids()
            self.status_bar_message(f"{len(self.manual_basket_selection)} artículos seleccionados para análisis.", 4000)

    def status_bar_message(self, msg, duration=0):
        self.status_label.setText(msg)
        if duration > 0:
            QTimer.singleShot(duration, self.status_label.clear)
        QApplication.processEvents()

    # Combos cuya posición se recuerda: atributo -> índice por defecto.
    COMBOS_PERSISTIDOS = {
        "top_articles_value_limit_combo": 0, "top_articles_value_period_combo": 1,
        "top_articles_qty_limit_combo": 0, "top_articles_qty_period_combo": 1,
        "top_customers_limit_combo": 0, "top_customers_period_combo": 1,
        "sales_period_combo": 1,
        "stock_report_combo": 0, "stock_limit_combo": 0,
        "basket_mode_combo": 0, "basket_period_combo": 1, "basket_assoc_limit_combo": 1,
        "export_clients_mode_combo": 0, "export_articles_mode_combo": 0,
        "cta_cte_cliente_combo": 3, "cta_cte_voucher_combo": 0,
        "slob_threshold_combo": 1,
        "margin_limit_combo": 1, "margin_period_combo": 1,
        "abc_period_combo": 0,
        "purchase_period_combo": 1, "purchase_target_combo": 1,
        "aging_limit_combo": 3,
    }

    def _clave(self, nombre):
        """Clave de QSettings con el prefijo de la empresa activa."""
        return f"{self.settings_prefix}{nombre}"

    def save_settings(self):
        if self.is_loading_settings:
            return

        _log.debug("Guardando preferencias del usuario.")

        for name, button in self.report_buttons.items():
            self.settings.setValue(self._clave(f"stat_{name}_active"), button.isChecked())

        for atributo, _ in self.COMBOS_PERSISTIDOS.items():
            combo = getattr(self, atributo, None)
            if combo is not None:
                self.settings.setValue(self._clave(f"{atributo}_index"),
                                       combo.currentIndex())

        self.settings.setValue(self._clave("include_cf_checked"),
                               self.include_cf_checkbox.isChecked())
        for name, chk in self.payment_method_checkboxes.items():
            self.settings.setValue(self._clave(f"payment_{name}_checked"), chk.isChecked())

        # Como lista de strings: QSettings en Windows los devuelve así de todos
        # modos, y guardarlos ya normalizados hace que leerlos sea simétrico.
        self.settings.setValue(self._clave("manual_basket_selection"),
                               [str(x) for x in self.manual_basket_selection])

        self.settings.sync()

    def load_settings(self):
        self.is_loading_settings = True
        try:
            _log.debug("Cargando preferencias del usuario.")

            for name, button in self.report_buttons.items():
                is_active = self.settings.value(
                    self._clave(f"stat_{name}_active"), True, type=bool)
                if button.isChecked() != is_active:
                    button.setChecked(is_active)
                else:
                    QTimer.singleShot(
                        0, lambda n=name, a=is_active: self.handle_report_toggle(n, a))

            for atributo, por_defecto in self.COMBOS_PERSISTIDOS.items():
                combo = getattr(self, atributo, None)
                if combo is None:
                    continue
                indice = self.settings.value(
                    self._clave(f"{atributo}_index"), por_defecto, type=int)
                # Un índice guardado por una versión con más opciones dejaría el
                # combo en -1 y `currentData()` devolvería None.
                if 0 <= indice < combo.count():
                    combo.setCurrentIndex(indice)
                else:
                    combo.setCurrentIndex(min(por_defecto, combo.count() - 1))

            self.include_cf_checkbox.setChecked(
                self.settings.value(self._clave("include_cf_checked"), False, type=bool))

            for name, chk in self.payment_method_checkboxes.items():
                chk.setChecked(self.settings.value(
                    self._clave(f"payment_{name}_checked"), True, type=bool))

            # QSettings devuelve strings: sin convertir a int, la comparación
            # contra `idArticulo` (int) del modal fallaba siempre y la selección
            # guardada aparecía vacía.
            guardado = self.settings.value(self._clave("manual_basket_selection"), []) or []
            if isinstance(guardado, str):
                guardado = [guardado]
            seleccion = []
            for valor in guardado:
                try:
                    seleccion.append(int(valor))
                except (TypeError, ValueError):
                    continue
            self.manual_basket_selection = seleccion

            QTimer.singleShot(10, self.on_basket_mode_changed)

        finally:
            self.is_loading_settings = False

    def trigger_dashboard_load(self, force_refresh):
        self.reset_dashboard_labels_to_loading()
        self.request_dashboard_load.emit(bool(force_refresh))

    def trigger_manual_dashboard_sync(self):
        _log.debug("Refresco manual de la API del panel.")
        self.status_bar_message("Sincronizando datos externos (API)...", 3000)
        self.trigger_dashboard_load(force_refresh=True)

    def reset_dashboard_labels_to_loading(self):
        loading_text = "Actualizando..."
        self.findChild(QLabel, "kpi_val_sales_30d").setText(loading_text)
        self.findChild(QLabel, "kpi_val_debt").setText(loading_text)
        
        self.kpi_sales_7d_details.setText(loading_text)
        
        self.findChild(QLabel, "kpi_val_dolar_oficial").setText(loading_text)
        self.findChild(QLabel, "kpi_val_dolar_blue").setText(loading_text)
        self.findChild(QLabel, "kpi_val_dolar_mep").setText(loading_text)
        self.findChild(QLabel, "kpi_val_ipc").setText(loading_text)
        self.findChild(QLabel, "kpi_val_ipc_periodo").setText("(Período: N/D)")

    def populate_dashboard_cards(self, results):
        _log.debug("Datos del DashboardWorker recibidos; poblando tarjetas KPI.")

        if results.get("error"):
            QMessageBox.warning(self, "Error de Dashboard", f"No se pudieron cargar los datos del panel: {results.get('error')}")
            return

        def f_curr(val): return f"$ {val:,.2f}" if isinstance(val, (int, float)) else "$ 0.00"
        def f_int(val): return f"{val:,.0f}" if isinstance(val, (int, float)) else "0"
        def f_api(val): return f"$ {val:,.2f}" if isinstance(val, (int, float)) else "N/D"
        def f_api_riesgo(val): return f"{val:,.0f} pts" if isinstance(val, (int, float)) else "N/D"
        def f_api_ipc(val): return f"{val:.2f} %" if isinstance(val, (int, float)) else "N/D"
        def f_ipc_periodo(val): return f"(Período: {val})" if val else "(Período: N/D)"
        
        self.findChild(QLabel, "kpi_val_sales_30d").setText(f_curr(results.get('kpi_sales_30d')))
        self.findChild(QLabel, "kpi_val_debt").setText(f_curr(results.get('kpi_total_debt')))
        
        df_sales_7d = results.get('kpi_sales_7d')
        html_7d = "<p>No se registraron ventas en los últimos 7 días.</p>"
        if df_sales_7d is not None and not df_sales_7d.empty:
            html_parts = []
            for _, row in df_sales_7d.iterrows():
                html_parts.append(f"<b>{row['MedioDePago']}:</b> &nbsp;&nbsp; {f_curr(row['Total'])}")
            html_7d = "<br>".join(html_parts)
            
        self.kpi_sales_7d_details.setText(html_7d)

        self.findChild(QLabel, "kpi_val_dolar_oficial").setText(f_api(results.get('dolar_oficial')))
        self.findChild(QLabel, "kpi_val_dolar_blue").setText(f_api(results.get('dolar_blue')))
        self.findChild(QLabel, "kpi_val_dolar_mep").setText(f_api(results.get('dolar_mep')))
        self.findChild(QLabel, "kpi_val_ipc").setText(f_api_ipc(results.get('ipc_mes')))
        self.findChild(QLabel, "kpi_val_ipc_periodo").setText(f_ipc_periodo(results.get('ipc_periodo')))

        self.status_bar_message("Panel de Control actualizado.", 4000)

    def closeEvent(self, event):
        """Guarda las preferencias y cierra el hilo del dashboard."""
        # Antes esto solo pasaba si el usuario exportaba algo y encima elegía
        # "Cerrar el programa" en el cartel del final: cerrando con la X se
        # perdía todo, en contra de lo que promete el manual de la app.
        try:
            self.save_settings()
        except Exception:
            _log.exception("No se pudieron guardar las preferencias al cerrar.")

        try:
            if self.dashboard_thread and self.dashboard_thread.isRunning():
                self.dashboard_thread.quit()
                self.dashboard_thread.wait(3000)
        except Exception as e:
            _log.warning("No se pudo cerrar el dashboard_thread: %s", e)

        super().closeEvent(event)


def main():
    configurar_logging()
    _log.info("Iniciando Analizador de Estadísticas Leontis.")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(FAVICON_PATH))

    # Que el sistema tenga lo que la app necesita (el redistribuible de Visual
    # C++ y compañía). La primera pasada es local y no toca la red: en un
    # arranque normal no se ve ninguna ventana.
    if not chequear_requisitos():
        return 0

    # Autoactualización antes de todo lo demás: si hay versión nueva, la instala
    # y relanza el .exe. Devuelve False cuando la app NO tiene que seguir
    # arrancando; si se sigue de largo quedan dos procesos. En desarrollo (.py)
    # no hace nada.
    if not chequear_al_inicio(BASE_DIR):
        return 0

    login_dialog = LoginDialog()

    if not login_dialog.exec():
        return 0

    try:
        window = MainWindow(
            db_manager=login_dialog.valid_db_manager,
            config_data=login_dialog.valid_config_data,
            user_role=login_dialog.valid_user_role,
        )
    except Exception:
        # Sin esto, en el .exe compilado (sin consola) un error al construir la
        # ventana hace que la app simplemente no aparezca: sin cartel, sin nada.
        _log.exception("No se pudo construir la ventana principal.")
        QMessageBox.critical(
            None, "Analizador de Estadísticas Leontis",
            "La app no pudo abrirse.\n\n"
            f"{traceback.format_exc()}\n\nEl detalle quedó en el log.")
        return 1

    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())