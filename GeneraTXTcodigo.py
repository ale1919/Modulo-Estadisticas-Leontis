import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkFont

# --- CONFIGURACIÓN ---
ARCHIVO_CONFIG = "config_unificador.json"
config_data = {}

# --- FUNCIONES DE LÓGICA ---

def cargar_configuracion():
    """Carga la configuración (selección y última ruta) desde un archivo JSON."""
    global config_data
    try:
        if os.path.exists(ARCHIVO_CONFIG):
            with open(ARCHIVO_CONFIG, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                if 'seleccion' not in config_data:
                    config_data['seleccion'] = []
                if 'last_path' not in config_data:
                    config_data['last_path'] = os.path.expanduser("~")
                return
    except (json.JSONDecodeError, IOError):
        pass
    config_data = {"seleccion": [], "last_path": os.path.expanduser("~")}

def guardar_configuracion_y_cerrar():
    """Guarda la selección actual y la última ruta en el archivo JSON y cierra la app."""
    global config_data
    seleccionados = [lista_archivos_total[i] for i, var in enumerate(vars_seleccion) if var.get()]
    config_data['seleccion'] = seleccionados
    
    with open(ARCHIVO_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4)
    
    root.destroy()

def unificar_codigo():
    """Unifica el contenido de los archivos seleccionados en un único archivo de texto."""
    global config_data
    seleccionados = [lista_archivos_total[i] for i, var in enumerate(vars_seleccion) if var.get()]
    
    if not seleccionados:
        messagebox.showwarning("Advertencia", "No has seleccionado ningún archivo.")
        return
    
    if len(seleccionados) == 1:
        nombre_inicial = os.path.splitext(os.path.basename(seleccionados[0]))[0]
    else:
        nombre_inicial = "Codigo Actual"

    output_file = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Archivos de texto", "*.txt")],
        title="Guardar código unificado como",
        initialfile=f"{nombre_inicial}.txt",
        initialdir=config_data.get('last_path', os.path.expanduser("~"))
    )
    
    if not output_file:
        return
    
    config_data['last_path'] = os.path.dirname(output_file)
    
    try:
        with open(output_file, "w", encoding="utf-8") as outfile:
            for file in seleccionados:
                file_path = os.path.join(root_dir, file)
                outfile.write(f"# --- Contenido de: {file} ---\n\n")
                try:
                    with open(file_path, "r", encoding="utf-8") as infile:
                        outfile.write(infile.read() + "\n\n")
                except Exception as read_error:
                    outfile.write(f"*** No se pudo leer el archivo: {read_error} ***\n\n")
        
        messagebox.showinfo("Éxito", f"Archivo creado exitosamente en:\n{output_file}")
        guardar_configuracion_y_cerrar()

    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error al generar el archivo:\n{str(e)}")

def toggle_seleccionar_todo():
    """Alterna el estado de todos los checkboxes."""
    if btn_seleccionar.config('text')[-1] == 'Seleccionar Todo':
        for var in vars_seleccion:
            var.set(True)
        btn_seleccionar.config(text="Deseleccionar Todo")
    else:
        for var in vars_seleccion:
            var.set(False)
        btn_seleccionar.config(text="Seleccionar Todo")

# --- INICIALIZACIÓN DE LA APP ---

root_dir = os.path.dirname(os.path.abspath(__file__))

# extensiones soportadas
EXTENSIONES = (".py", ".txt", ".json", ".htm", ".html", ".css", ".js")

# recorremos recursivamente todas las subcarpetas
lista_archivos_total = []
for carpeta, _, archivos in os.walk(root_dir):
    for archivo in archivos:
        if archivo.endswith(EXTENSIONES):
            # ignorar el propio script y el archivo de config
            if archivo == os.path.basename(__file__) or archivo == ARCHIVO_CONFIG:
                continue
            ruta_relativa = os.path.relpath(os.path.join(carpeta, archivo), root_dir)
            lista_archivos_total.append(ruta_relativa)

lista_archivos_total.sort()

cargar_configuracion()
seleccion_guardada = config_data.get('seleccion', [])

# --- CREACIÓN DE LA INTERFAZ GRÁFICA ---

root = tk.Tk()
root.title("Unificador de Código y Archivos")
root.geometry("600x600")
root.minsize(400, 350)
root.protocol("WM_DELETE_WINDOW", guardar_configuracion_y_cerrar)

main_frame = tk.Frame(root, padx=10, pady=10)
main_frame.pack(fill=tk.BOTH, expand=True)

# --- MARCO PARA CHECKBOXES CON SCROLL ---
checkbox_container = tk.Frame(main_frame)
checkbox_container.pack(fill='both', expand=True)

canvas = tk.Canvas(checkbox_container, borderwidth=0, highlightthickness=0)
vsb = tk.Scrollbar(checkbox_container, orient="vertical", command=canvas.yview)
canvas.configure(yscrollcommand=vsb.set)
vsb.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)

frame_checkboxes = tk.Frame(canvas)
canvas.create_window((0,0), window=frame_checkboxes, anchor="nw")
frame_checkboxes.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

# scroll con rueda
def _on_mousewheel(event):
    if event.num == 4 or event.delta > 0:
        canvas.yview_scroll(-1, "units")
    elif event.num == 5 or event.delta < 0:
        canvas.yview_scroll(1, "units")

frame_checkboxes.bind_all("<MouseWheel>", _on_mousewheel)
frame_checkboxes.bind_all("<Button-4>", _on_mousewheel)
frame_checkboxes.bind_all("<Button-5>", _on_mousewheel)

bold_font = tkFont.Font(family="Arial", size=10, weight="bold")

# --- CREACIÓN DE CHECKBOXES ---
vars_seleccion = []
tk.Label(frame_checkboxes, text="Archivos encontrados", font=bold_font, anchor='w').pack(fill='x', pady=(5, 2))

for archivo in lista_archivos_total:
    var = tk.BooleanVar(value=archivo in seleccion_guardada)
    vars_seleccion.append(var)
    cb = tk.Checkbutton(frame_checkboxes, text=archivo, variable=var, anchor='w')
    cb.pack(fill='x', padx=15, pady=2)

# --- BOTONES DE ACCIÓN ---
frame_botones = tk.Frame(main_frame)
frame_botones.pack(pady=(15, 5), fill='x')

btn_seleccionar = tk.Button(frame_botones, text="Seleccionar Todo", command=toggle_seleccionar_todo)
btn_seleccionar.pack(side='left', expand=True, padx=5)

btn_generar = tk.Button(frame_botones, text="Generar Archivo Unificado", command=unificar_codigo, font=('Arial', 10, 'bold'))
btn_generar.pack(side='left', expand=True, padx=5)

root.mainloop()
