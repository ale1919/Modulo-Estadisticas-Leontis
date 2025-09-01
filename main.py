import sys
from PyQt6.QtWidgets import QApplication
from ui_main_window import MainWindow
from ui_styles import STYLESHEET

def main():
    """
    Punto de entrada principal de la aplicación.
    """
    # Crear la aplicación
    app = QApplication(sys.argv)
    
    # Crear y mostrar la ventana principal
    window = MainWindow()
    window.show()
    
    # Iniciar el bucle de eventos de la aplicación
    sys.exit(app.exec())

if __name__ == '__main__':
    # Asegurarse de que el script se ejecute solo cuando es llamado directamente
    main()

