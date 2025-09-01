import sys
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog,
                             QPushButton, QCheckBox, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QLabel, QFrame, QStackedWidget, QGridLayout,
                             QMessageBox, QProgressDialog, QStatusBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


import pandas as pd
import os

from data_layer import DataLayer
from analysis_layer import AnalysisLayer
from plot_utils import MatplotlibWidget
from ui_styles import STYLESHEET
from ui_connection_dialog import ConnectionDialog # Importamos nuestro nuevo diálogo

class AnalysisWorker(QThread):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)
    error = pyqtSignal(str)

    def __init__(self, analysis_layer, reports_to_run):
        super().__init__()
        self.analysis_layer = analysis_layer
        self.reports_to_run = reports_to_run

    def run(self):
        results = {}
        total_reports = len(self.reports_to_run)
        
        for i, (key, func) in enumerate(self.reports_to_run.items()):
            try:
                self.progress.emit(int((i / total_reports) * 100), f"Generando: {key}...")
                results[key] = func()
            except Exception as e:
                self.error.emit(f"Error generando el reporte '{key}': {e}")
                results[key] = None
        
        self.progress.emit(100, "Completado.")
        self.finished.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Inicializar capas de lógica
        self.data_layer = DataLayer()

        # La aplicación principal solo continuará si la conexión es exitosa.
        conn_dialog = ConnectionDialog(self)
        if not conn_dialog.exec():
            # Si el usuario cierra el diálogo sin conectar, cerramos la aplicación.
            print("Conexión cancelada por el usuario. La aplicación se cerrará.")
            sys.exit()

        # Si llegamos aquí, la conexión fue exitosa.
        self.connection_info = conn_dialog.get_connection_details()
        
        # Ahora, intentamos conectar el DataLayer con los detalles obtenidos
        status = self.data_layer.connect(self.connection_info)
        
        if "exitosa" not in status:
            QMessageBox.critical(self, "Fallo en Conexión", f"No se pudo establecer la conexión final.\n\n{status}")
            sys.exit()

        self.analysis_layer = AnalysisLayer(self.data_layer)

        # Configuración de la ventana principal
        self.setWindowTitle("Analizador de Datos ERP")
        self.setGeometry(100, 100, 480, 280)
        self.setWindowIcon(QIcon())
        self.setStyleSheet(STYLESHEET)

        self.init_ui()

    def init_ui(self):
        # Contenedor principal
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        # --- Panel de Control (Izquierda) ---
        control_frame = QFrame()
        control_frame.setFixedWidth(300)
        control_layout = QVBoxLayout(control_frame)
        control_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel("Panel de Análisis")
        title_label.setObjectName("titleLabel")
        control_layout.addWidget(title_label)

        self.report_checkboxes = {
            "top_selling": QCheckBox("Artículos más vendidos"),
            "stock_issues": QCheckBox("Stock en cero o negativo"),
            "top_customers": QCheckBox("Clientes con más facturación"),
            "top_suppliers": QCheckBox("Proveedores con más pagos")
        }
        for checkbox in self.report_checkboxes.values():
            checkbox.setChecked(True)
            control_layout.addWidget(checkbox)
            
        self.run_button = QPushButton("Generar Informes")
        self.run_button.setObjectName("GreenButton")
        self.run_button.clicked.connect(self.run_analysis)
        control_layout.addWidget(self.run_button)
        
        control_layout.addStretch()

        # --- Panel de Visualización (Derecha) ---
        self.display_stack = QStackedWidget()
        self.results_widget = QWidget()
        self.results_layout = QGridLayout(self.results_widget)
        self.result_widgets = {}
        self.display_stack.addWidget(self.results_widget)
        
        main_layout.addWidget(control_frame)
        main_layout.addWidget(self.display_stack)

        # --- NUEVO: Barra de Estado ---
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.update_status_bar()

    def update_status_bar(self):
        """Muestra la información de la conexión actual en la barra de estado."""
        info = self.connection_info
        status_text = f"Conectado a: {info.get('db_type')} | Servidor: {info.get('host')} | Base de Datos: {info.get('database')}"
        self.statusBar.showMessage(status_text)
        
    def run_analysis(self):
        reports_to_run = {}
        if self.report_checkboxes["top_selling"].isChecked():
            reports_to_run["Articulos mas vendidos"] = self.analysis_layer.get_top_selling_products
        if self.report_checkboxes["stock_issues"].isChecked():
            reports_to_run["Stock en cero o negativo"] = self.analysis_layer.get_zero_or_negative_stock
        if self.report_checkboxes["top_customers"].isChecked():
            reports_to_run["Clientes con mas facturacion"] = self.analysis_layer.get_top_customers_by_billing
        if self.report_checkboxes["top_suppliers"].isChecked():
            reports_to_run["Proveedores con mas pagos"] = self.analysis_layer.get_top_suppliers_by_payment

        if not reports_to_run:
            print("No se seleccionó ningún informe para generar.")
            return

        generated_reports = {}
        print("Generando informes...")

        for report_name, report_function in reports_to_run.items():
            try:
                df = report_function()
                generated_reports[report_name] = df
                
                if df is not None and not df.empty:
                    print(f"Informe '{report_name}' generado con éxito.")
                else:
                    print(f"No se encontraron datos para el informe: {report_name}")
            
            except Exception as e:
                print(f"Error al generar el informe '{report_name}': {e}")
                generated_reports[report_name] = pd.DataFrame()

        if generated_reports:
            self.save_reports(generated_reports)

    def save_reports(self, reports_data):
        """
        Abre un diálogo para guardar los informes generados en el formato elegido.
        """
        if not reports_data:
            print("No hay datos de informes para guardar.")
            return
    
        valid_reports = {name: df for name, df in reports_data.items() if df is not None and not df.empty}
    
        if not valid_reports:
            QMessageBox.warning(self, "Sin Datos", "No hay datos válidos en los informes generados para guardar.")
            return
    
        filtros = "Archivos PDF (*.pdf);;Archivos Excel (*.xlsx);;Archivos de Texto (*.txt)"
    
        filePath, selected_filter = QFileDialog.getSaveFileName(
            parent=self,
            caption="Guardar Informes",
            directory="",
            filter=filtros
        )
    
        if not filePath:
            print("Guardado cancelado por el usuario.")
            return
    
        try:
            if filePath.lower().endswith('.pdf'):
                doc = SimpleDocTemplate(filePath, pagesize=letter)
                styles = getSampleStyleSheet()
                story = []
                for report_name, df in valid_reports.items():
                    story.append(Paragraph(report_name, styles['h1']))
                    story.append(Spacer(1, 12))
    
                    # Convertir todos los datos del DataFrame a texto para el PDF
                    data = [df.columns.to_list()] + df.astype(str).values.tolist()
    
                    # Cálculo automático del ancho de las columnas
                    col_widths = [None] * len(df.columns) # Dejar que la librería decida
    
                    table_style = TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4C566A")),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#E5E7EB")),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#D1D5DB")),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8), # Reducimos un poco la fuente
                    ])
    
                    t = Table(data, colWidths=col_widths, repeatRows=1)
                    t.setStyle(table_style)
                    story.append(t)
                    story.append(Spacer(1, 24))
                doc.build(story)
    
            elif filePath.lower().endswith('.xlsx'):
                with pd.ExcelWriter(filePath, engine='openpyxl') as writer:
                    for report_name, df in valid_reports.items():
                        sheet_name = report_name.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                        safe_sheet_name = "".join([c for c in sheet_name if c.isalnum() or c in " _-"])[:31]
                        df.to_excel(writer, sheet_name=safe_sheet_name, index=False)
    
            elif filePath.lower().endswith('.txt'):
                with open(filePath, 'w', encoding='utf-8') as f:
                    for report_name, df in valid_reports.items():
                        f.write(f"--- INFORME: {report_name} ---\n\n")
                        f.write(df.to_string(index=False))
                        f.write("\n\n" + "="*80 + "\n\n")
    
            print(f"¡Informes guardados exitosamente en {filePath}!")
            QMessageBox.information(self, "Éxito", f"Informes guardados exitosamente en:\n{filePath}")
    
        except Exception as e:
            print(f"Error al guardar el archivo: {e}")
            QMessageBox.critical(self, "Error al Guardar", f"No se pudo guardar el archivo.\n\nError: {e}")


    def update_progress(self, value, text):
        self.progress_dialog.setValue(value)
        self.progress_dialog.setLabelText(text)

    def cancel_analysis(self):
        if self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            print("Análisis cancelado por el usuario.")

    def display_results(self, results):
        for widget in self.result_widgets.values():
            widget.deleteLater()
        self.result_widgets.clear()

        row, col = 0, 0
        for title, df in results.items():
            if df is not None and not df.empty:
                container = self.create_report_widget(title, df)
                self.results_layout.addWidget(container, row, col)
                self.result_widgets[title] = container
                
                col += 1
                if col > 1:
                    col = 0
                    row += 1
            else:
                 print(f"No se encontraron datos para el informe: {title}")


    def create_report_widget(self, title, df):
        frame = QFrame()
        frame.setObjectName("mainFrame")
        layout = QVBoxLayout(frame)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #81A1C1; padding: 5px;")
        layout.addWidget(title_label)
        
        if "Stock" in title:
            table = self.create_table_from_df(df)
            layout.addWidget(table)
        else:
            plot_widget = MatplotlibWidget()
            labels = df.iloc[:, 0].tolist()
            values = df.iloc[:, 1].tolist()
            plot_widget.plot_bar_chart(labels, values, title, "Cantidad / Monto", "Categoría")
            layout.addWidget(plot_widget)

        return frame

    def create_table_from_df(self, df):
        table = QTableWidget()
        table.setRowCount(df.shape[0])
        table.setColumnCount(df.shape[1])
        table.setHorizontalHeaderLabels(df.columns)

        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                item = QTableWidgetItem(str(df.iloc[i, j]))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)
        
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        return table

    def show_error_message(self, message):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setText("Error")
        msg_box.setInformativeText(message)
        msg_box.setWindowTitle("Error")
        msg_box.exec()