import os
import sys
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QCompleter, QCheckBox, QHBoxLayout, QSpacerItem, QSizePolicy, 
    QWidget, QFrame, QMessageBox, QLayout, QTabWidget, QScrollArea, QTextBrowser
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from .ui_styles import ( 
    GREEN_BUTTON_STYLE, BLUE_BUTTON_STYLE, RED_BUTTON_STYLE,
    get_modern_card_style, get_modern_checkbox_style, MODERN_COMBOBOX_STYLE, FOOTER_FRAME_STYLE,
    BRAND_HEADER_STYLE, MODERN_TAB_STYLE, PENCIL_TOGGLE_BUTTON_STYLE,
    HEADER_HELP_BUTTON_STYLE, BRAND_ACCENT_BUTTON_STYLE
)

# --- INICIO DE CAMBIOS PARA COMPILACIÓN ---

def resource_path(relative_path):
    """
    Obtiene la ruta absoluta a un recurso. Funciona para el modo de desarrollo
    y para el ejecutable creado por PyInstaller.
    """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Si no está compilado, la base es la raíz del proyecto.
        # Se sube dos niveles desde este archivo (.../Recursos/Modulos/ -> ../Recursos/ -> ./)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

    return os.path.join(base_path, relative_path)

# --- FIN DE CAMBIOS PARA COMPILACIÓN ---

class UIFactory:
    def __init__(self, main_window):
        self.main_window = main_window

    def create_connection_panel(self):
        group = QGroupBox("1. Iniciar Sesión")
        layout = QGridLayout(group)
        self.main_window.login_user_input = QLineEdit()
        self.main_window.login_user_input.setPlaceholderText("Nombre de usuario")
        self.main_window.login_pass_input = QLineEdit()
        self.main_window.login_pass_input.setEchoMode(QLineEdit.Password)
        self.main_window.login_pass_input.setPlaceholderText("Contraseña")
        self.main_window.login_btn = QPushButton("Ingresar")
        self.main_window.login_btn.setStyleSheet(GREEN_BUTTON_STYLE)
        layout.addWidget(QLabel("Usuario:"), 0, 0)
        layout.addWidget(self.main_window.login_user_input, 0, 1)
        layout.addWidget(QLabel("Contraseña:"), 1, 0)
        layout.addWidget(self.main_window.login_pass_input, 1, 1)
        layout.addWidget(self.main_window.login_btn, 2, 0, 1, 2)
        group.setMaximumWidth(400)
        return group


    def create_empresa_panel(self):
        header_widget = QWidget()
        header_widget.setObjectName("main_header_widget")
        header_widget.setStyleSheet(BRAND_HEADER_STYLE)
        
        layout = QHBoxLayout(header_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_window.empresa_label = QLabel("...")
        self.main_window.empresa_label.setObjectName("main_header_label")
        self.main_window.empresa_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter) 
        
        layout.addWidget(self.main_window.empresa_label)
        
        layout.addStretch()
        
        self.main_window.instructions_btn = QPushButton("? Instrucciones")
        self.main_window.instructions_btn.setStyleSheet(HEADER_HELP_BUTTON_STYLE)
        self.main_window.instructions_btn.setToolTip("Abrir el manual de instrucciones del analizador")
        layout.addWidget(self.main_window.instructions_btn)

        header_widget.setVisible(False)
        return header_widget

    def _create_period_combo(self):
        combo = QComboBox()
        combo.addItem("Todo el Historial", -1)
        combo.addItem("Últimos 90 días", 90)
        combo.addItem("Últimos 60 días", 60)
        combo.addItem("Últimos 30 días", 30)
        combo.addItem("Últimos 15 días", 15)
        combo.addItem("Últimos 7 días", 7)
        combo.addItem("Últimas 24 horas", 1)
        combo.setCurrentIndex(1) 
        combo.setStyleSheet(MODERN_COMBOBOX_STYLE) 
        
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

        combo.setMinimumWidth(280)
        
        return combo

    def _create_limit_combo(self):
        combo = QComboBox()
        combo.addItem("Top 10", 10)
        combo.addItem("Top 20", 20)
        combo.addItem("Top 50", 50)
        combo.addItem("Top 100", 100)
        combo.addItem("Todos (sin gráfico)", -1)
        combo.setStyleSheet(MODERN_COMBOBOX_STYLE)
        
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

        combo.setMinimumWidth(280)
        
        return combo

    def _create_export_mode_combo(self):
        combo = QComboBox()
        combo.addItem("Exportar solo activos", "activos")
        combo.addItem("Exportar todos (activos e inactivos)", "todos")
        combo.setStyleSheet(MODERN_COMBOBOX_STYLE)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.setMinimumWidth(280)
        return combo

    def _create_debtor_limit_combo(self):
        combo = QComboBox()
        combo.addItem("Top 1 Deudor", 1)
        combo.addItem("Top 3 Deudores", 3)
        combo.addItem("Top 5 Deudores", 5)
        combo.addItem("Top 10 Deudores", 10)
        combo.addItem("Top 20 Deudores", 20)
        combo.addItem("Top 50 Deudores", 50)
        combo.addItem("Todos (Saldo != 0) (sin gráfico)", -1)
        combo.setCurrentIndex(3)
        combo.setStyleSheet(MODERN_COMBOBOX_STYLE)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.setMinimumWidth(280)
        return combo

    def _create_voucher_detail_combo(self):
        combo = QComboBox()
        combo.addItem("Solo Totales de Cliente", 0)
        combo.addItem("Top 1 Comprobante Adeudado", 1)
        combo.addItem("Top 3 Comprobantes Adeudados", 3)
        combo.addItem("Top 5 Comprobantes Adeudados", 5)
        combo.addItem("Top 10 Comprobantes Adeudados", 10)
        combo.addItem("Todos los Comprobantes Adeudados", -1)
        combo.addItem("Todos los Comprobantes (Histórico)", -99)
        combo.setCurrentIndex(0)
        combo.setStyleSheet(MODERN_COMBOBOX_STYLE)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.setMinimumWidth(280)
        return combo


    def _create_report_card(self, key, title, description_text, widgets_list, object_name_key):
        card_container = QWidget()
        card_container_layout = QVBoxLayout(card_container)
        card_container_layout.setContentsMargins(0, 0, 0, 0)
        card_container_layout.setSpacing(5)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(5, 0, 5, 0)

        title_label = QLabel(f"<b>{title}</b>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        toggle_button = QPushButton("✏️")
        toggle_button.setCheckable(True)
        toggle_button.setChecked(True) 
        toggle_button.setToolTip(f"Activar/Desactivar y mostrar/ocultar las opciones para '{title}'")
        toggle_button.setStyleSheet(PENCIL_TOGGLE_BUTTON_STYLE)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(toggle_button)
        
        content_group = QGroupBox()
        content_group.setObjectName(object_name_key) 
        
        content_group_main_layout = QVBoxLayout(content_group)
        content_group_main_layout.setContentsMargins(0, 0, 0, 0)
        content_group_main_layout.setSpacing(0)

        card_scroll_area = QScrollArea()
        card_scroll_area.setWidgetResizable(True)
        card_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        card_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        card_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        card_scroll_area.setStyleSheet("QWidget { background-color: transparent; }") 

        scroll_content_widget = QWidget()

        widgets_layout = QVBoxLayout(scroll_content_widget)
        widgets_layout.setContentsMargins(0, 0, 0, 0)
        widgets_layout.setSpacing(8)
        
        if description_text:
            desc_label = QLabel(description_text)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("""
                font-style: italic; 
                color: #555; 
                padding-bottom: 8px; 
                margin-bottom: 5px;
                border-bottom: 1px solid #EEEEEE;
            """)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            widgets_layout.addWidget(desc_label)
        
        for item in widgets_list:
            if isinstance(item, QWidget):
                widgets_layout.addWidget(item)
            elif isinstance(item, QLayout):
                temp_widget = QWidget()
                temp_widget.setLayout(item)
                widgets_layout.addWidget(temp_widget)
            elif isinstance(item, QSpacerItem):
                widgets_layout.addSpacerItem(item)
            else:
                widgets_layout.addWidget(QLabel(str(item)))
                
        widgets_layout.addStretch() 

        card_scroll_area.setWidget(scroll_content_widget)
        content_group_main_layout.addWidget(card_scroll_area)

        toggle_button.toggled.connect(
            lambda checked, k=key: self.main_window.handle_report_toggle(k, checked)
        )

        card_container_layout.addWidget(header_widget)
        card_container_layout.addWidget(content_group)
        
        self.main_window.report_buttons[key] = toggle_button
        self.main_window.report_cards[key] = content_group
        self.main_window.report_titles[key] = title
        
        return card_container


    def _create_inactive_reports_group(self, tab_key):
        inactive_group = QGroupBox("Informes Inactivos")
        inactive_layout = QVBoxLayout(inactive_group)
        inactive_layout.setSpacing(5)
        inactive_group.setVisible(False)
        
        self.main_window.inactive_reports_map[tab_key] = (inactive_group, inactive_layout)
        return inactive_group


    def create_statistics_panel(self):
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet(MODERN_TAB_STYLE)
        tab_widget.setVisible(False)

        self.main_window.report_buttons = {} 
        self.main_window.report_cards = {}
        self.main_window.report_titles = {}
        
        self.main_window.active_reports_grid_map = {}
        self.main_window.inactive_reports_map = {}
        self.main_window.report_widget_config = {}

        # Se obtiene el estilo dinámico para el checkbox
        modern_checkbox_style = get_modern_checkbox_style()

        self.main_window.top_articles_value_limit_combo = self._create_limit_combo()
        self.main_window.top_articles_value_period_combo = self._create_period_combo()
        card1_widgets = [
            QLabel("Mostrar:"), self.main_window.top_articles_value_limit_combo,
            QLabel("Período:"), self.main_window.top_articles_value_period_combo
        ]
        desc1 = "Muestra los artículos más vendidos según el total facturado ($). Útil para el gráfico PDF."
        card1 = self._create_report_card("top_articles_value", "Artículos por Valor ($)", desc1, card1_widgets, "CardStyle2C")

        self.main_window.top_articles_qty_limit_combo = self._create_limit_combo()
        self.main_window.top_articles_qty_period_combo = self._create_period_combo()
        card2_widgets = [
            QLabel("Mostrar:"), self.main_window.top_articles_qty_limit_combo,
            QLabel("Período:"), self.main_window.top_articles_qty_period_combo
        ]
        desc2 = "Muestra los artículos más vendidos según las unidades vendidas (cantidad). Útil para el gráfico PDF."
        card2 = self._create_report_card("top_articles_qty", "Artículos por Cantidad", desc2, card2_widgets, "CardStyle2C")
        
        self.main_window.top_customers_limit_combo = self._create_limit_combo()
        self.main_window.top_customers_period_combo = self._create_period_combo()
        self.main_window.include_cf_checkbox = QCheckBox("Incluir Consumidor Final")
        self.main_window.include_cf_checkbox.setStyleSheet(modern_checkbox_style)
        card3_widgets = [
            QLabel("Mostrar:"), self.main_window.top_customers_limit_combo,
            QLabel("Período:"), self.main_window.top_customers_period_combo,
            self.main_window.include_cf_checkbox
        ]
        desc3 = "Muestra los clientes que más han comprado (total facturado $). Útil para el gráfico PDF."
        card3 = self._create_report_card("top_customers", "Clientes por Facturación", desc3, card3_widgets, "CardStyle2C1K") 

        self.main_window.sales_period_combo = self._create_period_combo()
        
        payment_layout = QGridLayout()
        payment_layout.setContentsMargins(0, 5, 0, 0)
        payment_layout.setHorizontalSpacing(15)
        payment_layout.setVerticalSpacing(10)

        self.main_window.payment_method_checkboxes = {
            "Efectivo": QCheckBox("Efectivo"), "Tarjeta": QCheckBox("Tarjeta"),
            "Cheque": QCheckBox("Cheque"), "Otros": QCheckBox("Otros")
        }
        
        for chk in self.main_window.payment_method_checkboxes.values():
            chk.setChecked(True)
            chk.setStyleSheet(modern_checkbox_style)

        payment_layout.addWidget(self.main_window.payment_method_checkboxes["Efectivo"], 0, 0)
        payment_layout.addWidget(self.main_window.payment_method_checkboxes["Tarjeta"], 0, 1)
        payment_layout.addWidget(self.main_window.payment_method_checkboxes["Cheque"], 1, 0)
        payment_layout.addWidget(self.main_window.payment_method_checkboxes["Otros"], 1, 1)
        payment_layout.setColumnStretch(2, 1) 

        card4_widgets = [
            QLabel("Período:"),
            self.main_window.sales_period_combo,
            QLabel("Medios de Pago:"),
            payment_layout
        ]
        desc4 = "Grafica la evolución de ventas diarias (Línea) y por medio de pago (Multilínea). Útil para PDF."
        card4 = self._create_report_card("sales_over_time", "Ventas por Día", desc4, card4_widgets, "CardStyle1C4K")
        
        self.main_window.stock_report_combo = QComboBox()
        self.main_window.stock_report_combo.addItem("Top 30 con más stock", "top_mas_stock")
        self.main_window.stock_report_combo.addItem("Top 30 con menos stock (positivo)", "top_menos_stock")
        self.main_window.stock_report_combo.addItem("Artículos con stock Cero o Negativo", "cero_negativo")
        self.main_window.stock_report_combo.addItem("Todos los artículos (Solo Excel)", "todos_stock")
        self.main_window.stock_report_combo.setStyleSheet(MODERN_COMBOBOX_STYLE)
        self.main_window.stock_report_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.main_window.stock_report_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.main_window.stock_report_combo.setMinimumWidth(280)
        
        card5_widgets = [ QLabel("Reporte:"), self.main_window.stock_report_combo ]
        desc5 = "Genera un listado de stock (solo Excel/PDF Tabla). Use el combo para filtrar por existencias."
        card5 = self._create_report_card("stock_analysis", "Análisis de Stock (Tabla)", desc5, card5_widgets, "CardStyle1C")

        self.main_window.basket_mode_combo = QComboBox()
        self.main_window.basket_mode_combo.addItem("Top 10 Asociaciones", 10)
        self.main_window.basket_mode_combo.addItem("Top 20 Asociaciones", 20)
        self.main_window.basket_mode_combo.addItem("Top 50 Asociaciones", 50)
        self.main_window.basket_mode_combo.addItem("Seleccionar Artículos Manualmente", 'manual')
        self.main_window.basket_mode_combo.setStyleSheet(MODERN_COMBOBOX_STYLE)
        self.main_window.basket_mode_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.main_window.basket_mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.main_window.basket_mode_combo.setMinimumWidth(280)
        
        self.main_window.basket_select_btn = QPushButton("Seleccionar...")
        self.main_window.basket_select_btn.setVisible(False)

        self.main_window.basket_assoc_limit_combo = QComboBox()
        self.main_window.basket_assoc_limit_combo.addItem("Top 3", 3)
        self.main_window.basket_assoc_limit_combo.addItem("Top 5", 5)
        self.main_window.basket_assoc_limit_combo.addItem("Top 10", 10)
        self.main_window.basket_assoc_limit_combo.addItem("Top 15", 15)
        self.main_window.basket_assoc_limit_combo.addItem("Top 30", 30)
        self.main_window.basket_assoc_limit_combo.addItem("Todas las asociaciones", -1)
        self.main_window.basket_assoc_limit_combo.setCurrentIndex(1) 
        self.main_window.basket_assoc_limit_combo.setStyleSheet(MODERN_COMBOBOX_STYLE)
        self.main_window.basket_assoc_limit_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.main_window.basket_assoc_limit_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.main_window.basket_assoc_limit_combo.setMinimumWidth(280)

        self.main_window.basket_period_combo = self._create_period_combo()
        card6_widgets = [
            QLabel("Modo de Análisis:"), self.main_window.basket_mode_combo,
            self.main_window.basket_select_btn,
            QLabel("Limitar Asociados a:"), self.main_window.basket_assoc_limit_combo,
            QLabel("Período:"), self.main_window.basket_period_combo
        ]
        desc6 = "Analiza qué artículos se compran juntos (solo Excel/PDF Tabla). Requiere configuración."
        card6 = self._create_report_card("market_basket", "Análisis de Canasta", desc6, card6_widgets, "CardStyle3C1B")

        self.main_window.export_clients_mode_combo = self._create_export_mode_combo()
        self.main_window.export_clients_excel_btn = QPushButton("Exportar Clientes a Excel")
        self.main_window.export_clients_excel_btn.setStyleSheet(GREEN_BUTTON_STYLE)
        card7_widgets = [
            QLabel("Opción:"),
            self.main_window.export_clients_mode_combo,
            self.main_window.export_clients_excel_btn
        ]
        desc7 = "Exporta la base de datos completa de clientes (activos o todos) a un archivo Excel."
        card7 = self._create_report_card("export_clients", "Exportación Rápida de Clientes", desc7, card7_widgets, "CardStyle1C1B")

        self.main_window.export_articles_mode_combo = self._create_export_mode_combo()
        self.main_window.export_articles_excel_btn = QPushButton("Exportar Artículos a Excel")
        self.main_window.export_articles_excel_btn.setStyleSheet(GREEN_BUTTON_STYLE)
        card8_widgets = [
            QLabel("Opción:"),
            self.main_window.export_articles_mode_combo,
            self.main_window.export_articles_excel_btn
        ]
        desc8 = "Exporta la base de datos completa de artículos (activos o todos) a un archivo Excel."
        card8 = self._create_report_card("export_articles", "Exportación Rápida de Artículos", desc8, card8_widgets, "CardStyle1C1B")
        
        self.main_window.cta_cte_cliente_combo = self._create_debtor_limit_combo()
        self.main_window.cta_cte_voucher_combo = self._create_voucher_detail_combo()
        card9_widgets = [
            QLabel("Alcance de Clientes (Gráfico):"),
            self.main_window.cta_cte_cliente_combo,
            QLabel("Detalle de Comprobantes (Exportar):"),
            self.main_window.cta_cte_voucher_combo
        ]
        desc9 = "Analiza saldos deudores (Gráfico PDF) y el detalle de comprobantes (Excel)."
        card9 = self._create_report_card("cta_cte", "Análisis de Cuenta Corriente", desc9, card9_widgets, "CardStyle2C")

        self.main_window.slob_threshold_combo = self._create_slob_threshold_combo()
        card10_widgets = [
            QLabel("Umbral de Inactividad (Stock > 0):"),
            self.main_window.slob_threshold_combo,
        ]
        desc10 = "Calcula el valor del inventario sin rotación (Obsoleto) basado en los días sin ventas (Excel/PDF Tabla)."
        card10 = self._create_report_card("slob_analysis", "Informe de Inventario Obsoleto", desc10, card10_widgets, "CardStyle1C")

        desc_rfm = "Segmenta clientes por Recencia, Frecuencia y Valor (Gráfico PDF y Excel). No requiere configuración."
        card_rfm = self._create_report_card(
            "rfm_segmentation", 
            "Segmentación de Clientes (RFM)", 
            desc_rfm,
            [],
            "CardStyleInfoOnly"
        )

        self.main_window.admin_dashboard_tab = QWidget() 
        admin_tab_layout = QVBoxLayout(self.main_window.admin_dashboard_tab)
        admin_tab_layout.setContentsMargins(15, 15, 15, 15)
        admin_tab_layout.setSpacing(15)

        admin_header_layout = QHBoxLayout()
        admin_title = QLabel("Panel de Control del Administrador")
        admin_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")
        admin_header_layout.addWidget(admin_title)
        admin_header_layout.addStretch()

        self.main_window.admin_sync_button = QPushButton(" Actualizar Datos Externos")
        # Se usa la función resource_path para encontrar el ícono
        sync_icon_path = resource_path(os.path.join("Recursos", "Grafico", "sync-icon.png"))
        self.main_window.admin_sync_button.setIcon(QIcon(sync_icon_path)) 
        self.main_window.admin_sync_button.setStyleSheet(BRAND_ACCENT_BUTTON_STYLE)
        self.main_window.admin_sync_button.setFixedSize(200, 35)
        admin_header_layout.addWidget(self.main_window.admin_sync_button)
        admin_tab_layout.addLayout(admin_header_layout)

        
        def create_kpi_card(title, initial_value="Cargando...", object_name_val="", object_name_card=""):
            card = QWidget()
            card.setObjectName(object_name_card)
            card.setStyleSheet(get_modern_card_style()) 
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(5)
            
            title_label = QLabel(title)
            title_label.setStyleSheet("font-weight: bold; color: #555; font-size: 13px;")
            card_layout.addWidget(title_label)
            
            value_label = QLabel(initial_value)
            value_label.setObjectName(object_name_val) 
            value_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #312093; padding-top: 5px;")
            card_layout.addWidget(value_label)
            card.setMinimumHeight(120)
            return card

        kpi_main_rows_layout = QVBoxLayout()
        kpi_main_rows_layout.setSpacing(15)

        top_row_layout = QHBoxLayout()
        top_row_layout.setSpacing(15)
        
        self.main_window.kpi_sales_30d_card = create_kpi_card("Ventas (Últimos 30 Días)", "$ 0.00", "kpi_val_sales_30d", "kpi_card_main")
        self.main_window.kpi_debt_card = create_kpi_card("Total Cuenta Corriente (Deuda)", "$ 0.00", "kpi_val_debt", "kpi_card_main")
        
        top_row_layout.addWidget(self.main_window.kpi_sales_30d_card)
        top_row_layout.addWidget(self.main_window.kpi_debt_card)
        
        kpi_main_rows_layout.addLayout(top_row_layout)

        middle_row_layout = QHBoxLayout()
        middle_row_layout.setSpacing(15)

        self.main_window.kpi_sales_7d_card = QWidget()
        self.main_window.kpi_sales_7d_card.setObjectName("kpi_card_sales_7d")
        self.main_window.kpi_sales_7d_card.setStyleSheet(get_modern_card_style())
        sales_7d_layout = QVBoxLayout(self.main_window.kpi_sales_7d_card)
        sales_7d_title = QLabel("Ventas por Pago (Últimos 7 Días)")
        sales_7d_title.setStyleSheet("font-weight: bold; color: #555; font-size: 13px;")
        sales_7d_layout.addWidget(sales_7d_title)
        self.main_window.kpi_sales_7d_details = QLabel("Cargando datos...")
        self.main_window.kpi_sales_7d_details.setObjectName("kpi_val_sales_7d")
        self.main_window.kpi_sales_7d_details.setStyleSheet("font-size: 13px; color: #333; padding-top: 5px;")
        self.main_window.kpi_sales_7d_details.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        sales_7d_layout.addWidget(self.main_window.kpi_sales_7d_details)
        sales_7d_layout.addStretch()

        self.main_window.kpi_ipc_card = QWidget()
        self.main_window.kpi_ipc_card.setObjectName("kpi_card_ipc")
        self.main_window.kpi_ipc_card.setStyleSheet(get_modern_card_style())
        ipc_layout = QVBoxLayout(self.main_window.kpi_ipc_card)
        ipc_title = QLabel("Inflación (Último IPC Mensual)")
        ipc_title.setStyleSheet("font-weight: bold; color: #555; font-size: 13px;")
        ipc_layout.addWidget(ipc_title)
        ipc_val_layout = QHBoxLayout()
        self.main_window.kpi_ipc_value_label = QLabel("Cargando...")
        self.main_window.kpi_ipc_value_label.setObjectName("kpi_val_ipc")
        self.main_window.kpi_ipc_value_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #312093;")
        self.main_window.kpi_ipc_periodo_label = QLabel("(Período: N/D)")
        self.main_window.kpi_ipc_periodo_label.setObjectName("kpi_val_ipc_periodo")
        self.main_window.kpi_ipc_periodo_label.setStyleSheet("font-size: 12px; color: #666; padding-top: 4px;")
        ipc_val_layout.addWidget(self.main_window.kpi_ipc_value_label)
        ipc_val_layout.addWidget(self.main_window.kpi_ipc_periodo_label)
        ipc_val_layout.addStretch()
        ipc_layout.addLayout(ipc_val_layout)
        
        middle_row_layout.addWidget(self.main_window.kpi_sales_7d_card, 2, Qt.AlignmentFlag.AlignTop)
        middle_row_layout.addWidget(self.main_window.kpi_ipc_card, 1, Qt.AlignmentFlag.AlignTop)

        kpi_main_rows_layout.addLayout(middle_row_layout)

        admin_tab_layout.addLayout(kpi_main_rows_layout)

        line_frame = QFrame()
        line_frame.setFrameShape(QFrame.Shape.HLine)
        line_frame.setFrameShadow(QFrame.Shadow.Sunken)
        admin_tab_layout.addWidget(line_frame)

        dolar_layout = QHBoxLayout()
        dolar_layout.setSpacing(15)
        self.main_window.kpi_dolar_oficial_card = create_kpi_card("Dólar Oficial", "Cargando...", "kpi_val_dolar_oficial", "kpi_card_dolar")
        self.main_window.kpi_dolar_blue_card = create_kpi_card("Dólar Blue", "Cargando...", "kpi_val_dolar_blue", "kpi_card_dolar")
        self.main_window.kpi_dolar_mep_card = create_kpi_card("Dólar MEP", "Cargando...", "kpi_val_dolar_mep", "kpi_card_dolar")
        
        dolar_layout.addStretch(9)
        dolar_layout.addWidget(self.main_window.kpi_dolar_oficial_card, 11)
        dolar_layout.addWidget(self.main_window.kpi_dolar_blue_card, 11)
        dolar_layout.addWidget(self.main_window.kpi_dolar_mep_card, 11)
        dolar_layout.addStretch(9)
        
        admin_tab_layout.addLayout(dolar_layout)
        
        admin_tab_layout.addStretch()
        
        
        self.main_window.main_tab_widget.addTab(self.main_window.admin_dashboard_tab, "Panel de Control")

        tab_articulos = QWidget()
        layout_articulos_main = QVBoxLayout(tab_articulos)
        layout_articulos_activos = QGridLayout()
        layout_articulos_activos.setSpacing(15)
        layout_articulos_activos.addWidget(card1, 0, 0)
        layout_articulos_activos.addWidget(card2, 0, 1)
        layout_articulos_activos.addWidget(card6, 1, 0, 1, 2)
        layout_articulos_activos.addWidget(card8, 2, 0, 1, 2) 
        layout_articulos_activos.setColumnStretch(0, 1)
        layout_articulos_activos.setColumnStretch(1, 1)
        layout_articulos_main.addLayout(layout_articulos_activos)
        layout_articulos_main.addWidget(self._create_inactive_reports_group("articulos"))
        layout_articulos_main.addStretch(1)
        self.main_window.active_reports_grid_map["articulos"] = layout_articulos_activos
        self.main_window.report_tabs["articulos"] = tab_articulos
        self.main_window.main_tab_widget.addTab(tab_articulos, "Artículos")

        tab_clientes = QWidget()
        layout_clientes_main = QVBoxLayout(tab_clientes)
        layout_clientes_activos = QGridLayout()
        layout_clientes_activos.setSpacing(15)
        layout_clientes_activos.addWidget(card3, 0, 0)
        layout_clientes_activos.addWidget(card9, 1, 0)
        layout_clientes_activos.addWidget(card_rfm, 2, 0)
        layout_clientes_activos.addWidget(card7, 3, 0)
        layout_clientes_activos.setColumnStretch(0, 1)
        layout_clientes_main.addLayout(layout_clientes_activos)
        layout_clientes_main.addWidget(self._create_inactive_reports_group("clientes"))
        layout_clientes_main.addStretch(1)
        self.main_window.active_reports_grid_map["clientes"] = layout_clientes_activos
        self.main_window.report_tabs["clientes"] = tab_clientes
        self.main_window.main_tab_widget.addTab(tab_clientes, "Clientes")

        tab_ventas = QWidget()
        layout_ventas_main = QVBoxLayout(tab_ventas)
        layout_ventas_activos = QGridLayout()
        layout_ventas_activos.setSpacing(15)
        layout_ventas_activos.addWidget(card4, 0, 0)
        layout_ventas_activos.setColumnStretch(0, 1)
        layout_ventas_main.addLayout(layout_ventas_activos)
        layout_ventas_main.addWidget(self._create_inactive_reports_group("ventas"))
        layout_ventas_main.addStretch(1)
        self.main_window.active_reports_grid_map["ventas"] = layout_ventas_activos
        self.main_window.report_tabs["ventas"] = tab_ventas
        self.main_window.main_tab_widget.addTab(tab_ventas, "Ventas")

        tab_Stock = QWidget()
        layout_Stock_main = QVBoxLayout(tab_Stock)
        layout_Stock_activos = QGridLayout()
        layout_Stock_activos.setSpacing(15)
        layout_Stock_activos.addWidget(card5, 0, 0)
        layout_Stock_activos.addWidget(card10, 1, 0)
        layout_Stock_activos.setColumnStretch(0, 1)
        layout_Stock_main.addLayout(layout_Stock_activos)
        layout_Stock_main.addWidget(self._create_inactive_reports_group("Stock"))
        layout_Stock_main.addStretch(1)
        self.main_window.active_reports_grid_map["Stock"] = layout_Stock_activos
        self.main_window.report_tabs["Stock"] = tab_Stock
        self.main_window.main_tab_widget.addTab(tab_Stock, "Stock")
        
        self.main_window.report_widget_config = {
            "top_articles_value": {"widget": card1, "layout": layout_articulos_activos, "pos": (0, 0, 1, 1), "tab_key": "articulos"},
            "top_articles_qty":   {"widget": card2, "layout": layout_articulos_activos, "pos": (0, 1, 1, 1), "tab_key": "articulos"},
            "market_basket":      {"widget": card6, "layout": layout_articulos_activos, "pos": (1, 0, 1, 2), "tab_key": "articulos"},
            "export_articles":    {"widget": card8, "layout": layout_articulos_activos, "pos": (2, 0, 1, 2), "tab_key": "articulos"}, 
            "top_customers":      {"widget": card3, "layout": layout_clientes_activos,  "pos": (0, 0, 1, 1), "tab_key": "clientes"},
            "cta_cte":            {"widget": card9, "layout": layout_clientes_activos,  "pos": (1, 0, 1, 1), "tab_key": "clientes"},
            "rfm_segmentation":   {"widget": card_rfm, "layout": layout_clientes_activos, "pos": (2, 0, 1, 1), "tab_key": "clientes"},
            "export_clients":     {"widget": card7, "layout": layout_clientes_activos,  "pos": (3, 0, 1, 1), "tab_key": "clientes"},
            "sales_over_time":    {"widget": card4, "layout": layout_ventas_activos,    "pos": (0, 0, 1, 1), "tab_key": "ventas"},
            "stock_analysis":     {"widget": card5, "layout": layout_Stock_activos,    "pos": (0, 0, 1, 1), "tab_key": "Stock"},
            "slob_analysis":      {"widget": card10, "layout": layout_Stock_activos,   "pos": (1, 0, 1, 1), "tab_key": "Stock"},
        }

    def create_footer_panel(self):
        footer_frame = QFrame()
        footer_frame.setStyleSheet(FOOTER_FRAME_STYLE)
        footer_frame.setFixedHeight(60) 

        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(15, 10, 15, 10)

        self.main_window.export_excel_btn = QPushButton("Exportar Datos a Excel (.xlsx)")
        self.main_window.export_excel_btn.setStyleSheet(GREEN_BUTTON_STYLE)

        self.main_window.export_pdf_btn = QPushButton("Exportar Gráficos a PDF")
        self.main_window.export_pdf_btn.setStyleSheet(RED_BUTTON_STYLE)

        footer_layout.addStretch() 
        footer_layout.addWidget(self.main_window.export_excel_btn)
        footer_layout.addWidget(self.main_window.export_pdf_btn)

        def update_export_buttons_visibility(index):
            tab_text = self.main_window.main_tab_widget.tabText(index)
            if tab_text == "Panel de Control":
                self.main_window.export_excel_btn.setVisible(False)
                self.main_window.export_pdf_btn.setVisible(False)
            else:
                self.main_window.export_excel_btn.setVisible(True)
                self.main_window.export_pdf_btn.setVisible(True)

        self.main_window.main_tab_widget.currentChanged.connect(update_export_buttons_visibility)

        current_index = self.main_window.main_tab_widget.currentIndex()
        update_export_buttons_visibility(current_index)

        return footer_frame
    
    def _create_slob_threshold_combo(self):
        combo = QComboBox()
        combo.addItem("Más de 5 días sin ventas", 5)
        combo.addItem("Más de 90 días sin ventas", 90)
        combo.addItem("Más de 180 días sin ventas", 180)
        combo.addItem("Más de 365 días (1 año) sin ventas", 365)
        combo.addItem("Más de 730 días (2 años) sin ventas", 730)
        combo.setCurrentIndex(1)
        combo.setStyleSheet(MODERN_COMBOBOX_STYLE)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        combo.setMinimumWidth(280)
        return combo
