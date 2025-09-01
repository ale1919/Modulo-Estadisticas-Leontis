STYLESHEET = """
/* --- Estilos Generales --- */
QMainWindow {
    background-color: #F9FAFB;
}

QDialog {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
}

QLabel {
    color: #374151;
    font-size: 14px;
}

QLineEdit, QComboBox {
    border: 1px solid #D1D5DB;
    border-radius: 4px;
    padding: 5px;
    background-color: #FFFFFF;
    selection-background-color: #3B82F6;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3B82F6;
}

/* --- Estilo base de todos los botones --- */
QPushButton {
    background-color: #FFFFFF;
    color: #374151;
    border: 1px solid #D1D5DB;
    padding: 10px 20px;
    border-radius: 6px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #F3F4F6;
}

QPushButton:pressed {
    background-color: #E5E7EB;
}

/* --- QTableView --- */
QTableView {
    border: 1px solid #D1D5DB;
    gridline-color: #E5E7EB;
    selection-background-color: #3B82F6;
    selection-color: white;
    background-color: #FFFFFF;
    alternate-background-color: #F9FAFB;
}

QHeaderView::section {
    background-color: #F3F4F6;
    padding: 5px;
    border: 1px solid #D1D5DB;
    font-weight: bold;
    color: #374151;
}

/* --- QGroupBox --- */
QGroupBox {
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    margin-top: 10px;
    padding: 10px;
    font-weight: bold;
    color: #374151;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 10px;
}

/* --- Widgets personalizados --- */
QWidget#EvenRowWidget {
    background-color: #F9FAFB;
}

QWidget#OddRowWidget {
    background-color: #FFFFFF;
}

QLineEdit#EvenRowWidget, QComboBox#EvenRowWidget {
    background-color: #F9FAFB;
}

QLineEdit#OddRowWidget, QComboBox#OddRowWidget {
    background-color: #FFFFFF;
}

/* --- Colores de Botones Específicos (al final para sobrescribir el estilo base) --- */
QPushButton#GreenButton {
    background-color: #16A34A; 
    color: white; 
    border: none;
}
QPushButton#GreenButton:hover { background-color: #15803D; }

QPushButton#BlueButton {
    background-color: #2563EB; 
    color: white; 
    border: none;
}
QPushButton#BlueButton:hover { background-color: #1D4ED8; }

QPushButton#RedButton {
    background-color: #EF4444; 
    color: white; 
    border: none;
}
QPushButton#RedButton:hover { background-color: #DC2626; }

QPushButton#YellowButton {
    background-color: #FBBF24; 
    color: #422006; 
    border: none;
}
QPushButton#YellowButton:hover { background-color: #F59E0B; }
"""
