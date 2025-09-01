from PyQt6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

class MatplotlibWidget(QWidget):
    """
    Widget de PyQt para incrustar un gráfico de Matplotlib.
    """
    def __init__(self, parent=None):
        super(MatplotlibWidget, self).__init__(parent)
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        
        # Estilo oscuro para los gráficos
        plt.style.use('dark_background')
        self.figure.patch.set_facecolor('#2E3440')

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def plot_bar_chart(self, x, y, title, xlabel, ylabel):
        """
        Dibuja un gráfico de barras horizontales.
        """
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        bars = ax.barh(x, y, color='#88C0D0')
        ax.set_title(title, color='#ECEFF4', fontsize=16, fontweight='bold')
        ax.set_xlabel(xlabel, color='#D8DEE9')
        ax.set_ylabel(ylabel, color='#D8DEE9')
        
        # Ajustar colores de los ejes y ticks
        ax.tick_params(axis='x', colors='#D8DEE9')
        ax.tick_params(axis='y', colors='#D8DEE9')
        ax.spines['bottom'].set_color('#4C566A')
        ax.spines['top'].set_color('#4C566A') 
        ax.spines['right'].set_color('#4C566A')
        ax.spines['left'].set_color('#4C566A')
        ax.set_facecolor('#3B4252')
        
        # Invertir el eje y para que el más alto esté arriba
        ax.invert_yaxis()
        
        # Añadir etiquetas de valor en las barras
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 0.01 * max(y), bar.get_y() + bar.get_height()/2,
                    f'{width:,.0f}',
                    ha='left', va='center', color='#ECEFF4', fontsize=10)

        self.figure.tight_layout()
        self.canvas.draw()

