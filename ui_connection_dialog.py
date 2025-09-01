from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QGroupBox, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QMessageBox, QCheckBox,
                             QHBoxLayout, QApplication)
from PyQt6.QtCore import Qt
import os
import db_utils 
from ui_styles import STYLESHEET

class ConnectionDialog(QDialog):
    """
    Diálogo mejorado para gestionar la conexión en dos pasos,
    con agenda y memoria de la última sesión.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.connection_details = {}
        self.server_connection = None

        self.setWindowTitle("Configurar Conexión a Base de Datos")
        self.setMinimumWidth(600)
        self.setModal(True)
        self.setObjectName("ConnectionDialog")

        from ui_styles import STYLESHEET
        self.setStyleSheet(STYLESHEET)

        self.init_ui()
        self.load_server_agenda()
        self.update_ui_for_db_type()
        self.load_last_used_server()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        connection_group = QGroupBox("Parámetros de Conexión")
        connection_group.setAlignment(Qt.AlignmentFlag.AlignCenter)

        grid = QGridLayout(connection_group)
        grid.setHorizontalSpacing(15)
        grid.setVerticalSpacing(10)

        # --- Definición de Widgets ---
        self.db_type_combo = QComboBox()
        self.servers_combo = QComboBox()
        self.save_server_button = QPushButton("Guardar")
        self.remove_server_button = QPushButton("Eliminar")
        self.host_entry = QLineEdit("localhost\\SQLEXPRESS")
        self.port_entry = QLineEdit()
        self.win_auth_checkbox = QCheckBox("Usar Autenticación de Windows")
        self.user_label = QLabel("Usuario:")
        self.user_entry = QLineEdit("sa")
        self.password_label = QLabel("Contraseña:")
        self.password_entry = QLineEdit()
        self.list_dbs_button = QPushButton("1. Listar Bases de Datos del Servidor")
        self.database_combo = QComboBox()
        self.connect_button = QPushButton("2. Analizar Base de Datos Seleccionada")

        # --- Aplicación de Nombres de Objeto para Estilos ---
        self.db_type_combo.setObjectName("OddRowWidget")
        self.servers_combo.setObjectName("EvenRowWidget")
        self.host_entry.setObjectName("OddRowWidget")
        self.port_entry.setObjectName("EvenRowWidget")
        self.user_entry.setObjectName("OddRowWidget")
        self.password_entry.setObjectName("EvenRowWidget")
        self.database_combo.setObjectName("OddRowWidget")
        
        # Asignamos nombres a TODOS los botones para controlarlos desde el CSS
        self.save_server_button.setObjectName("YellowButton") # Botón Guardar (Amarillo)
        self.remove_server_button.setObjectName("RedButton") # Botón Eliminar (Rojo)
        self.list_dbs_button.setObjectName("GreenButton") # Botón Listar (Verde)
        self.connect_button.setObjectName("BlueButton") # Botón Analizar (Azul)

        # --- Estructura del Layout ---
        row = 0
        grid.addWidget(QLabel("Tipo de BD:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.db_type_combo, row, 1, 1, 2)

        row += 1
        grid.addWidget(QLabel("Servidores Guardados:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.servers_combo, row, 1)
        
        agenda_buttons_layout = QHBoxLayout()
        agenda_buttons_layout.addWidget(self.save_server_button)
        agenda_buttons_layout.addWidget(self.remove_server_button)
        grid.addLayout(agenda_buttons_layout, row, 2)
        
        row += 1
        grid.addWidget(QLabel("Host/Servidor:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.host_entry, row, 1, 1, 2)

        row += 1
        grid.addWidget(QLabel("Puerto:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.port_entry, row, 1, 1, 2)
        
        row += 1
        grid.addWidget(self.win_auth_checkbox, row, 1, 1, 2)

        row += 1
        grid.addWidget(self.user_label, row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.user_entry, row, 1, 1, 2)
        
        row += 1
        grid.addWidget(self.password_label, row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.password_entry, row, 1, 1, 2)

        row += 1
        grid.addWidget(self.list_dbs_button, row, 1, 1, 2)

        row += 1
        grid.addWidget(QLabel("Base de Datos:"), row, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.database_combo, row, 1, 1, 2)

        main_layout.addWidget(connection_group)
        main_layout.addWidget(self.connect_button)
        
        # --- Conexión de Señales ---
        self.db_type_combo.addItems(["SQL Server", "MySQL"])
        self.db_type_combo.currentTextChanged.connect(self.update_ui_for_db_type)
        self.servers_combo.addItem("-- Nuevo Servidor --")
        self.servers_combo.currentIndexChanged.connect(self.load_selected_server)
        self.save_server_button.clicked.connect(self.save_current_server)
        self.remove_server_button.clicked.connect(self.remove_selected_server)
        self.win_auth_checkbox.setChecked(True)
        self.win_auth_checkbox.toggled.connect(self.toggle_user_pass_fields)
        self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.list_dbs_button.clicked.connect(self.list_available_databases)
        self.connect_button.clicked.connect(self.finalize_connection)
        
        self.reset_ui_state()

    def load_last_used_server(self):
        """Carga la configuración de la última conexión exitosa."""
        last_server_details = db_utils.load_last_server()
        if last_server_details:
            print("Cargando configuración de la última sesión...")
            self.db_type_combo.setCurrentText(last_server_details.get("db_type", "SQL Server"))
            self.host_entry.setText(last_server_details.get("host", ""))
            self.port_entry.setText(last_server_details.get("port", ""))
            self.win_auth_checkbox.setChecked(last_server_details.get("use_win_auth", True))
            
            if not last_server_details.get("use_win_auth", True):
                self.user_entry.setText(last_server_details.get("user", ""))
            
            self.servers_combo.setCurrentIndex(0)

    def finalize_connection(self):
        database = self.database_combo.currentText()
        if not database:
            QMessageBox.warning(self, "Sin Selección", "Por favor, seleccione una base de datos de la lista.")
            return

        self.connection_details = {
            'db_type': self.db_type_combo.currentText(),
            'host': self.host_entry.text(),
            'port': self.port_entry.text(),
            'database': database,
            'user': self.user_entry.text(),
            'password': self.password_entry.text(),
            'use_win_auth': self.win_auth_checkbox.isChecked()
        }
        
        db_utils.save_last_server(self.connection_details)
        
        self.accept()

    def reset_ui_state(self):
        self.database_combo.clear()
        self.database_combo.setEnabled(False)
        self.connect_button.setEnabled(False)
        self.toggle_user_pass_fields()
        if self.server_connection:
            try:
                self.server_connection.close()
            except Exception as e:
                print(f"Error cerrando conexión previa (ignorable): {e}")
            self.server_connection = None

    def update_ui_for_db_type(self):
        db_type = self.db_type_combo.currentText()
        is_sql_server = (db_type == "SQL Server")
        
        self.win_auth_checkbox.setVisible(is_sql_server)
        self.port_entry.setPlaceholderText("1433 (por defecto)" if is_sql_server else "3306 (por defecto)")
        self.reset_ui_state()
        
    def toggle_user_pass_fields(self):
        use_win_auth = self.win_auth_checkbox.isVisible() and self.win_auth_checkbox.isChecked()
        self.user_label.setEnabled(not use_win_auth)
        self.user_entry.setEnabled(not use_win_auth)
        self.password_label.setEnabled(not use_win_auth)
        self.password_entry.setEnabled(not use_win_auth)

    def list_available_databases(self):
        self.reset_ui_state()
        db_type = self.db_type_combo.currentText()
        server = self.host_entry.text()
        port = self.port_entry.text()
        user = self.user_entry.text()
        password = self.password_entry.text()
        use_win_auth = self.win_auth_checkbox.isChecked()

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.server_connection = db_utils.get_server_connection(db_type, server, port, user, password, use_win_auth)
            databases = db_utils.list_databases(self.server_connection, db_type)
            QApplication.restoreOverrideCursor()

            if databases:
                self.database_combo.addItems(databases)
                self.database_combo.setEnabled(True)
                self.connect_button.setEnabled(True)
                QMessageBox.information(self, "Éxito", f"Se encontraron {len(databases)} bases de datos en '{server}'.")
            else:
                QMessageBox.warning(self, "Sin Resultados", "Conexión exitosa, pero no se encontraron bases de datos o no tiene permisos para verlas.")

        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error de Conexión al Servidor", f"No se pudo conectar al servidor. Verifique los datos.\n\nError: {e}")

    def load_server_agenda(self):
        self.servers_agenda = db_utils.load_servers()
        self.servers_combo.blockSignals(True)
        self.servers_combo.clear()
        self.servers_combo.addItem("-- Nuevo Servidor --")
        self.servers_combo.addItems(sorted(self.servers_agenda.keys()))
        self.servers_combo.blockSignals(False)

    def load_selected_server(self):
        server_name = self.servers_combo.currentText()
        self.reset_ui_state()
        if server_name and server_name != "-- Nuevo Servidor --":
            config = self.servers_agenda.get(server_name, {})
            self.db_type_combo.setCurrentText(config.get("db_type", "SQL Server"))
            self.host_entry.setText(config.get("host", ""))
            self.port_entry.setText(config.get("port", ""))
            self.user_entry.setText(config.get("user", ""))
            self.win_auth_checkbox.setChecked(config.get("win_auth", True))
            self.password_entry.clear()
            
            if os.path.exists("analyzer_last_server.json"):
                os.remove("analyzer_last_server.json")

    def save_current_server(self):
        from PyQt6.QtWidgets import QInputDialog
        server_name, ok = QInputDialog.getText(self, "Guardar Servidor", "Ingrese un nombre para esta configuración:")
        if ok and server_name:
            config = {
                "db_type": self.db_type_combo.currentText(),
                "host": self.host_entry.text(),
                "port": self.port_entry.text(),
                "user": self.user_entry.text(),
                "win_auth": self.win_auth_checkbox.isChecked()
            }
            self.servers_agenda[server_name] = config
            db_utils.save_servers(self.servers_agenda)
            self.load_server_agenda()
            self.servers_combo.setCurrentText(server_name)
            QMessageBox.information(self, "Éxito", f"Servidor '{server_name}' guardado.")

    def remove_selected_server(self):
        server_name = self.servers_combo.currentText()
        if not server_name or server_name == "-- Nuevo Servidor --":
            return
        reply = QMessageBox.question(self, "Confirmar", f"¿Eliminar '{server_name}' de la agenda?")
        if reply == QMessageBox.StandardButton.Yes:
            if server_name in self.servers_agenda:
                del self.servers_agenda[server_name]
                db_utils.save_servers(self.servers_agenda)
                self.load_server_agenda()
                self.host_entry.clear()
                self.port_entry.clear()
                self.user_entry.clear()
                self.password_entry.clear()

    def get_connection_details(self):
        return self.connection_details
