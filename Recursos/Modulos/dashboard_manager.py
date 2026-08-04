import json
import traceback
from datetime import date, datetime

import requests
from PySide6.QtCore import QObject, Signal, Slot

from .rutas import log, recurso

_log = log("dashboard")

# Estos dos archivos son **datos de la app**, no de cada instalación: si mañana
# cambia un endpoint, tiene que llegarle a todos. Por eso viven en
# `Recursos/Datos` y no en `Recursos/Config`, que es la carpeta que el updater
# nunca reemplaza (ver ACTUALIZACIONES.md).
JSON_FILE_DOLAR = recurso("Recursos", "Datos", "dolares.json")
JSON_FILE_INFLACION = recurso("Recursos", "Datos", "inflacion.json")


class ApiConnector:
    """Clase aislada para manejar todas las llamadas de red externas."""
    
    def _parse_inflation_data(self, json_data, parser_type):
        """
        Intenta extraer y validar datos de inflación de diferentes formatos JSON.
        Aplica la lógica de fallback de 3 meses, leyendo desde el inicio de la lista (datos más nuevos).
        """
        data_points = []
        if parser_type == "datos_gob_ar":
            data_points = json_data.get("data", [])
        elif parser_type == "bcra":
            data_points = json_data
            
        if not data_points:
            return None, None

        # Lógica de fallback: intentar con los 3 meses más recientes (posiciones 0, 1, 2)
        for i in range(3):
            if len(data_points) > i:
                entry = data_points[i]
                
                fecha_str, valor = None, None
                if parser_type == "datos_gob_ar" and len(entry) >= 2:
                    fecha_str, valor = entry[0], entry[1]
                elif parser_type == "bcra" and isinstance(entry, dict):
                    fecha_str, valor = entry.get('d'), entry.get('v')

                if fecha_str and valor is not None:
                    try:
                        fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
                        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                        periodo_legible = f"{meses[fecha_dt.month - 1]} {fecha_dt.year}"
                        if i > 0:
                            _log.info(f"Usando dato de inflación de un período anterior ({periodo_legible}).")
                        return periodo_legible, float(valor)
                    except (ValueError, TypeError):
                        continue

        return None, None

    def fetch_inflation_with_fallback(self):
        """
        Itera sobre las fuentes de inflación del JSON y aplica la lógica de fallback.
        """
        try:
            with open(JSON_FILE_INFLACION, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _log.error(f"No se pudo leer o procesar {JSON_FILE_INFLACION}")
            return None, None

        for source in config.get("endpoints", []):
            if not source.get("habilitado", False):
                continue

            nombre = source.get('nombre', 'Fuente desconocida')
            url = source.get('url')
            parser = source.get('parser')
            headers = source.get('headers')

            if not all([url, parser]):
                continue

            _log.info(f"Consultando fuente de inflación: {nombre}...")
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    periodo, valor = self._parse_inflation_data(response.json(), parser)
                    if periodo and valor is not None:
                        _log.info(f"Dato de inflación encontrado en {nombre}.")
                        return periodo, valor
                    else:
                        _log.warning(f"La fuente {nombre} respondió pero no se encontraron datos válidos.")
                else:
                    _log.error(f"La fuente {nombre} devolvió el código {response.status_code}.")
            except requests.exceptions.RequestException as e:
                _log.error(f"Falló la conexión con la fuente {nombre}. Causa: {e}")
            except Exception as e:
                 _log.error(f"Fallo inesperado al procesar la fuente {nombre}. Causa: {e}")


        _log.error(f"Todas las fuentes de inflación fallaron.")
        return None, None


    def fetch_external_data(self):
        """Intenta obtener Dólar e Inflación. Devuelve Nones si falla."""
        _log.debug(f"Iniciando búsqueda de datos económicos externos...")
        results = {
            "dolar_oficial": None, "dolar_blue": None, "dolar_mep": None,
            "ipc_mes": None, "ipc_periodo": None
        }

        try:
            with open(JSON_FILE_DOLAR, 'r', encoding='utf-8') as f:
                dolar_config = json.load(f)
            
            url_oficial = dolar_config['endpoints']['oficial']['url']
            response_oficial = requests.get(url_oficial, timeout=5)
            if response_oficial.status_code == 200:
                results["dolar_oficial"] = response_oficial.json().get('venta')
            
            url_blue = dolar_config['endpoints']['blue']['url']
            response_blue = requests.get(url_blue, timeout=5)
            if response_blue.status_code == 200:
                results["dolar_blue"] = response_blue.json().get('venta')

            url_mep = dolar_config['endpoints']['bolsa']['url']
            response_mep = requests.get(url_mep, timeout=5)
            if response_mep.status_code == 200:
                results["dolar_mep"] = response_mep.json().get('venta')

            _log.debug(f"Dólar/Riesgo obtenidos (MEP: {results['dolar_mep']})")
        except Exception as e:
            _log.error(f"API Dolar: {e}")

        periodo_ipc, valor_ipc = self.fetch_inflation_with_fallback()
        if periodo_ipc and valor_ipc is not None:
            results["ipc_periodo"] = periodo_ipc
            results["ipc_mes"] = valor_ipc
            _log.debug(f"IPC Final Asignado ({results['ipc_periodo']}: {results['ipc_mes']}%)")
        else:
            results["ipc_periodo"] = "N/D"
            results["ipc_mes"] = None
            _log.debug(f"No se pudo obtener el dato de IPC de ninguna fuente.")
            
        return results


class DashboardWorker(QObject):
    """
    Worker que corre en un hilo separado para cargar TODOS los datos del dashboard 
    (KPIs internos y APIs externas) sin congelar la UI.
    """
    data_loaded = Signal(dict)

    def __init__(self, stats_generator, settings, company_id):
        super().__init__()
        self.stats_gen = stats_generator
        self.settings = settings
        self.company_id = company_id
        self.api_connector = ApiConnector()
        self._is_running = False

    def check_and_fetch_external_data(self, force_refresh=False):
        """
        Maneja la lógica de caché. Solo llama a la API si se fuerza (botón manual)
        o si el caché tiene más de 24 horas o está incompleto/inválido.
        """
        CACHE_PREFIX = "admin_panel_cache/"
        today_str = date.today().isoformat()
        last_check_date = self.settings.value(f"{CACHE_PREFIX}last_check_date", "")

        cached_data = {}
        keys_to_load = ["dolar_oficial", "dolar_blue", "dolar_mep", "ipc_mes", "ipc_periodo"]
        
        if not force_refresh and last_check_date == today_str:
            _log.debug(f"Verificando datos económicos cacheadados de hoy.")
            all_valid = True
            
            numeric_keys = {"dolar_oficial", "dolar_blue", "dolar_mep", "ipc_mes"}

            for key in keys_to_load:
                cached_value = self.settings.value(f"{CACHE_PREFIX}{key}", None)
                
                if key in numeric_keys and not isinstance(cached_value, (int, float)):
                    _log.warning(f"La clave '{key}' no es un número válido (valor: {cached_value}).")
                    all_valid = False
                    break
                
                if key == "ipc_periodo" and not cached_value:
                    _log.warning(f"La clave 'ipc_periodo' está vacía.")
                    all_valid = False
                    break

                cached_data[key] = cached_value

            if all_valid:
                _log.debug(f"Los datos cacheadados son válidos y se están utilizando.")
                return cached_data
            else:
                _log.debug(f"Datos incompletos o inválidos detectados, refrescando desde API...")

        _log.debug(f"Caché expirado, inválido o refresco forzado. Llamando a APIs externas...")
        api_data = self.api_connector.fetch_external_data()
        
        self.settings.setValue(f"{CACHE_PREFIX}last_check_date", today_str)
        
        for key in keys_to_load:
            self.settings.setValue(f"{CACHE_PREFIX}{key}", api_data.get(key))

        return api_data

    @Slot(bool)
    def run_all_loads(self, force_api_refresh=False):
        """Punto de entrada del worker. Corre en el hilo secundario.

        El @Slot y la conexión por señal desde MainWindow son lo que hace que
        esto sea cierto: antes se invocaba con `QTimer.singleShot(0, lambda: ...)`,
        que crea el timer en el hilo que lo llama, así que el trabajo terminaba
        corriendo en el hilo de la GUI y la ventana se congelaba igual. El
        `moveToThread` no alcanza por sí solo: llamar a un método directamente lo
        ejecuta siempre en el hilo del que llama.
        """
        if self._is_running:
            _log.debug(f"Carga de dashboard ya está en progreso. Omitiendo.")
            return

        self._is_running = True
        final_results = {}

        try:
            _log.debug(f"Cargando KPIs internos (SQL)...")
            final_results['kpi_sales_7d'] = self.stats_gen.get_kpi_sales_by_payment_last_7_days(self.company_id)
            final_results['kpi_total_debt'] = self.stats_gen.get_kpi_total_debt(self.company_id)
            final_results['kpi_sales_30d'] = self.stats_gen.get_kpi_total_sales_last_30_days(self.company_id)

            _log.debug(f"Cargando KPIs externos (API/Caché)...")
            external_data = self.check_and_fetch_external_data(force_refresh=force_api_refresh)
            final_results.update(external_data)

            _log.debug(f"Carga completa. Emitiendo señal data_loaded.")
            self.data_loaded.emit(final_results)

        except Exception as e:
            _log.error(f"DashboardWorker: {e}\n{traceback.format_exc()}")
            error_dict = {"error": str(e)}
            self.data_loaded.emit(error_dict)
        finally:
            self._is_running = False
