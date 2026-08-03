"""
Este módulo contiene las hojas de estilo (stylesheets) para la aplicación.
"""
import os
import sys

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

def get_modern_checkbox_style():
    """
    Genera el CSS para el QCheckBox, usando una ruta absoluta a la imagen
    del checkmark para que funcione correctamente cuando está compilado.
    """
    # Se reemplazan las barras invertidas por barras normales para compatibilidad con CSS/URL
    checkmark_path = resource_path(os.path.join("Recursos", "Grafico", "Checkmark.png")).replace('\\', '/')
    
    return f"""
        QCheckBox {{
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 24px;
            height: 24px;
            border: 1px solid #B0B0B0;
            border-radius: 4px;
            background-color: white;
        }}
        QCheckBox::indicator:hover {{
            border: 1px solid #007ACC;
        }}
        QCheckBox::indicator:checked {{
            border: 1px solid #007ACC;
            border-radius: 4px;
            background-color: #007ACC;
            background-image: url({checkmark_path});
            background-repeat: no-repeat;
            background-position: center;
        }}
    """

def get_modern_card_style():
    """
    Devuelve el CSS para las tarjetas. Se mantiene como función por consistencia,
    aunque actualmente no tenga rutas dinámicas.
    """
    return """
        QGroupBox#CardStyle2C,
        QGroupBox#CardStyle2C1K,
        QGroupBox#CardStyle1C4K,
        QGroupBox#CardStyle1C,
        QGroupBox#CardStyle3C1B,
        QGroupBox#CardStyleInfoOnly,
        QGroupBox#CardStyle1C1B,
        QWidget#kpi_card_main,
        QWidget#kpi_card_dolar
        {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 15px; 
        }

        QWidget#kpi_card_sales_7d,
        QWidget#kpi_card_ipc
        {
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 8px 15px;
        }

        QGroupBox#CardStyle2C1K,
        QGroupBox#CardStyle3C1B
        {
            min-height: 288px;
        }

        QGroupBox#CardStyle1C4K 
        {
            min-height: 204px;
        }

        QGroupBox#CardStyle2C 
        {
            min-height: 205px;
        }

        QGroupBox#CardStyle1C1B
        {
            min-height: 190px;
        }

        QGroupBox#CardStyle1C
        {
            min-height: 84px;
        }
        QGroupBox#CardStyleInfoOnly
        {
            min-height: 60px;
            padding-top: 10px;
            padding-bottom: 10px;
        }
    """

# --- FIN DE CAMBIOS PARA COMPILACIÓN ---


GREEN_BUTTON_STYLE = """
QPushButton {
    background-color: #4CAF50;
    color: white;
    border-radius: 5px;
    padding: 8px 12px;
    font-size: 14px;
    font-weight: bold;
    border: 1px solid #388E3C;
}
QPushButton:hover {
    background-color: #45a049;
}
QPushButton:pressed {
    background-color: #388E3C;
}
"""

YELLOW_BUTTON_STYLE = """
QPushButton {
    background-color: #FFC107;
    color: black;
    border-radius: 5px;
    padding: 8px 12px;
    font-size: 14px;
    font-weight: bold;
    border: 1px solid #FFA000;
}
QPushButton:hover {
    background-color: #ffca2c;
}
QPushButton:pressed {
    background-color: #ffb300;
}
"""

BLUE_BUTTON_STYLE = """
QPushButton {
    background-color: #007ACC;
    color: white;
    border-radius: 5px;
    padding: 8px 12px;
    font-size: 14px;
    font-weight: bold;
    border: 1px solid #005C99;
}
QPushButton:hover {
    background-color: #0088E0;
}
QPushButton:pressed {
    background-color: #005C99;
}
"""

RED_BUTTON_STYLE = """
QPushButton {
    background-color: #D32F2F;
    color: white;
    border-radius: 5px;
    padding: 8px 12px;
    font-size: 14px;
    font-weight: bold;
    border: 1px solid #B71C1C;
}
QPushButton:hover {
    background-color: #E53935;
}
QPushButton:pressed {
    background-color: #B71C1C;
}
"""

HIGHLIGHTED_COMBO_STYLE = """
QComboBox {
    border: 2px solid #007ACC;
    border-radius: 5px;
    padding: 1px 18px 1px 3px;
    min-width: 6em;
}
"""

BRAND_ACCENT_BUTTON_STYLE = """
QPushButton {
    background-color: #a1b1f6;
    color: #312093;
    border-radius: 5px;
    padding: 8px 12px;
    font-size: 14px;
    font-weight: bold;
    border: 1px solid #a1b1f6;
}
QPushButton:hover {
    background-color: #b1c0f8;
}
QPushButton:pressed {
    background-color: #90a0e0;
}
"""

PENCIL_TOGGLE_BUTTON_STYLE = """
QPushButton {
    background-color: #E8EDF2;
    border: 1px solid #C5D0DB;
    color: #3F4E5A;
    padding: 4px;
    font-size: 10pt;
    font-weight: bold;
    border-radius: 4px;
    min-width: 26px;
    max-width: 26px;
    min-height: 22px;
    max-height: 22px;
}
QPushButton:hover {
    background-color: #D0D8E2;
    border-color: #A3B4C2;
}
QPushButton:checked {
    background-color: #DBEAFE;
    border: 1px solid #3B82F6;
    color: #1E40AF;
}
"""


MODERN_COMBOBOX_STYLE = """
QComboBox {
    border: 1px solid #B0B0B0;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 32px;
    font-size: 14px;
}
QComboBox:hover {
    border: 1px solid #007ACC;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left-width: 1px;
    border-left-color: #B0B0B0;
    border-left-style: solid;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}
QComboBox::down-arrow {
    image: url(none);
}

/* --- SELECCIÓN DEL TEXTO --- */
QComboBox QAbstractItemView {
    border: 1px solid #B0B0B0;
    background-color: white;
    /* Color de fondo azul claro al seleccionar */
    selection-background-color: #a1b1f6; 
    /* Color de texto oscuro al seleccionar (para contraste) */
    selection-color: #312093; 
    outline: 0px; /* Quita un borde de foco que puede aparecer */
}
"""

MODERN_CARD_STYLE = get_modern_card_style()

FOOTER_FRAME_STYLE = """
QFrame {
    background-color: #F8F9FA;
    border-top: 1px solid #E0E0E0;
}
"""

BRAND_HEADER_STYLE = """
QWidget#main_header_widget {
    background-color: #312093;
    border-bottom: 2px solid #a1b1f6;
}
QLabel#main_header_label {
    font-size: 18px;
    font-weight: bold;
    padding: 10px 15px;
    color: #ffffff;
}
"""

MODERN_TAB_STYLE = """
QTabWidget::pane {
    border: none;
    background-color: #F0F2F5;
    padding: 25px 15px 15px 15px;
}
QTabBar::tab {
    background: #E0E0E0;
    border: 1px solid #C0C0C0;
    border-bottom: none;
    padding: 10px 25px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
    color: #555;
    margin-right: 2px;
}
QTabBar::tab:hover {
    background: #EDEDED;
    border-bottom: 2px solid #a1b1f6;
}
QTabBar::tab:selected {
    background: #F0F2F5;
    border: 1px solid #C0C0C0;
    border-bottom: 1px solid #F0F2F5;
    color: #312093;
}
"""

HEADER_HELP_BUTTON_STYLE = """
QPushButton {
    background-color: transparent;
    color: #FFFFFF;
    border: 1px solid #a1b1f6;
    border-radius: 5px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: bold;
    margin-right: 15px;
}
QPushButton:hover {
    background-color: #a1b1f6;
    color: #312093;
}
QPushButton:pressed {
    background-color: #90a0e0;
    color: #312093;
}
"""
