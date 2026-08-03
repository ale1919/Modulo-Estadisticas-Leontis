import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PySide6.QtWidgets import QWidget, QVBoxLayout
import numpy as np
import pandas as pd

class MatplotlibWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(facecolor='#FFFFFF')
        self.canvas = FigureCanvas(self.figure)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def plot_bar_chart(self, x_data, y_data, title, xlabel, ylabel):
        self.figure.clear()
        num_bars = len(y_data)
        fig_height = max(6, num_bars * 0.5 + 2) 
        fig_width = 13
        self.figure.set_size_inches(fig_width, fig_height, forward=True)
        
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('#FFFFFF')

        max_len = 45
        original_labels = [str(label) for label in x_data]
        truncated_labels = [
            (label[:max_len] + '...') if len(label) > max_len else label
            for label in original_labels
        ]

        y_pos = np.arange(len(original_labels))
        colors = ['#A9A9A9', '#007ACC'] * (num_bars // 2 + 1)
        bars = ax.barh(y_pos, y_data, color=colors)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(truncated_labels)
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.invert_yaxis()

        is_currency = '$' in xlabel
        if is_currency:
            formatter = ticker.FuncFormatter(lambda val, pos: f'${val:,.0f}')
        else:
            formatter = ticker.FuncFormatter(lambda val, pos: f'{val:,.0f}')
        ax.xaxis.set_major_formatter(formatter)
        
        ax.tick_params(axis='y', labelsize=10)
        ax.tick_params(axis='x', labelsize=10, rotation=0)
        
        for bar in bars:
            width = bar.get_width()
            label_text = f' ${width:,.0f}' if is_currency else f' {width:,.0f}'
            ax.text(width * 1.01, bar.get_y() + bar.get_height() / 2,
                    label_text, ha='left', va='center', fontsize=9)
        
        ax.set_xlim(right=ax.get_xlim()[1] * 1.25)
        self.figure.tight_layout(pad=1.5)
        self.canvas.draw()

    def plot_line_chart(self, x_data, y_data, title, xlabel, ylabel):
        self.figure.clear()
        fig_height, fig_width = 8, 12
        self.figure.set_size_inches(fig_width, fig_height, forward=True)
        
        ax = self.figure.add_subplot(111)
        ax.plot(x_data, y_data, marker='o', linestyle='-', color='#007ACC', markersize=5, label='Total Ventas')
        
        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        
        # Asegurarse de que x_data es de tipo datetime
        if not pd.api.types.is_datetime64_any_dtype(x_data):
            x_data = pd.to_datetime(x_data)
            
        days = (x_data.max() - x_data.min()).days if not x_data.empty else 0
        
        if days <= 30: major_interval = 5; minor_interval = 1
        else: major_interval = 15; minor_interval = 5

        ax.xaxis.set_major_locator(mdates.DayLocator(interval=major_interval))
        ax.xaxis.set_minor_locator(mdates.DayLocator(interval=minor_interval))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b'))
        
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda val, pos: f'${val:,.0f}'))
        ax.grid(which='major', linestyle='-', linewidth='0.6', color='gray', alpha=0.7)
        ax.grid(which='minor', linestyle=':', linewidth='0.5', color='lightgray', alpha=0.7)
        ax.legend()
        
        self.figure.autofmt_xdate(rotation=30, ha='right')
        self.figure.tight_layout()
        self.canvas.draw()
        
    def plot_multi_line_chart(self, df, title, xlabel, ylabel):
        self.figure.clear()
        fig_height, fig_width = 8, 12
        self.figure.set_size_inches(fig_width, fig_height, forward=True)
        ax = self.figure.add_subplot(111)

        if not pd.api.types.is_datetime64_any_dtype(df.index):
            df.index = pd.to_datetime(df.index, errors='coerce')

        for column in df.columns:
            ax.plot(df.index, df[column], marker='o', linestyle='-', markersize=4, label=column)

        ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)

        days = (df.index.max() - df.index.min()).days if not df.empty else 0

        # Calcular dinámicamente para no exceder el límite de Ticks de Matplotlib
        if days <= 30: 
            major_interval = 5; minor_interval = 1
        elif days <= 90: 
            major_interval = 15; minor_interval = 5
        else:
            # Aumentar la escala automáticamente para rangos inmensos
            major_interval = max(15, days // 8) 
            minor_interval = max(5, major_interval // 3)
        
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=int(major_interval)))
        ax.xaxis.set_minor_locator(mdates.DayLocator(interval=int(minor_interval)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b'))

        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda val, pos: f'${val:,.0f}'))
        ax.grid(which='major', linestyle='-', linewidth='0.6', color='gray', alpha=0.7)
        ax.grid(which='minor', linestyle=':', linewidth='0.5', color='lightgray', alpha=0.7)
        ax.legend(title='Medio de Pago')

        self.figure.autofmt_xdate(rotation=30, ha='right')
        self.figure.tight_layout()
        self.canvas.draw()