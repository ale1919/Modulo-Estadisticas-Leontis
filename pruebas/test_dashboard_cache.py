"""El caché de 24 h de dólar e IPC del Panel de Control (AUDITORIA.md §7.3.4).

Usa un QSettings REAL (en el registro, bajo una organización de prueba que se
borra al final), porque el bug estaba justamente en lo que devuelve el registro:
los float vuelven como texto. Con un diccionario de mentira la prueba pasaba y
la app seguía rota.
"""

from datetime import date, timedelta

from PySide6.QtCore import QSettings

from entorno import Checks

from Recursos.Modulos.dashboard_manager import DashboardWorker, _como_numero

C = Checks("caché del panel")

# -- _como_numero ---------------------------------------------------------- #
for valor, esperado in [
    (1234.5, 1234.5), (10, 10.0), (0, 0.0), (-3.5, -3.5),
    ("1234.5", 1234.5), (" 77 ", 77.0), ("0", 0.0), ("1e3", 1000.0),
    (None, None), ("", None), ("   ", None), ("abc", None), ("1,5", None),
    (True, None), (float("nan"), None), ("nan", None), ("inf", None), ([], None),
]:
    C.igual(_como_numero(valor), esperado, f"_como_numero({valor!r})")


class ApiFalsa:
    def __init__(self, datos):
        self.datos = datos
        self.llamadas = 0

    def fetch_external_data(self):
        self.llamadas += 1
        return dict(self.datos)


BUENOS = {"dolar_oficial": 1450.5, "dolar_blue": 1500.0, "dolar_mep": 1480.25,
          "ipc_mes": 2.7, "ipc_periodo": "Agosto 2026"}
PREFIJO = "admin_panel_cache/"

settings = QSettings("LeontisPruebas", "EstadisticasCachePanel")
try:
    def worker(datos=BUENOS):
        settings.clear()
        settings.sync()
        w = DashboardWorker(stats_generator=None, settings=settings, company_id=1)
        w.api_connector = ApiFalsa(datos)
        return w

    # 1. Primera vez: consulta. Segunda, el mismo día: usa el caché.
    w = worker()
    r1 = w.check_and_fetch_external_data()
    C.igual(w.api_connector.llamadas, 1, "primera carga consulta las APIs")
    C.igual(r1, BUENOS, "la primera carga devuelve lo de la API")
    settings.sync()
    r2 = w.check_and_fetch_external_data()
    C.igual(w.api_connector.llamadas, 1, "segunda carga del día usa el caché")
    for k in BUENOS:
        C.igual(r2.get(k), BUENOS[k], f"el caché devuelve {k}")
    C.check(all(isinstance(r2[k], float) for k in ("dolar_oficial", "dolar_blue",
                                                   "dolar_mep", "ipc_mes")),
            "los números del caché vuelven como número")

    # 2. Forzado: consulta aunque haya caché.
    w.check_and_fetch_external_data(force_refresh=True)
    C.igual(w.api_connector.llamadas, 2, "el botón de actualizar consulta igual")

    # 3. Otro día: consulta.
    settings.setValue(f"{PREFIJO}last_check_date",
                      (date.today() - timedelta(days=1)).isoformat())
    w.check_and_fetch_external_data()
    C.igual(w.api_connector.llamadas, 3, "caché de ayer: consulta")

    # 4. Caché incompleto o con basura: consulta.
    for clave, valor in [("dolar_blue", None), ("dolar_mep", "abc"),
                         ("ipc_mes", ""), ("ipc_periodo", ""), ("ipc_periodo", None)]:
        w = worker()
        w.check_and_fetch_external_data()
        settings.setValue(f"{PREFIJO}{clave}", valor)
        settings.sync()
        w.check_and_fetch_external_data()
        C.igual(w.api_connector.llamadas, 2, f"caché con {clave}={valor!r}: consulta")

    # 5. Si la API falló (Nones), no queda un caché "válido" de Nones.
    fallida = dict.fromkeys(BUENOS)
    w = worker(fallida)
    w.check_and_fetch_external_data()
    w.check_and_fetch_external_data()
    C.igual(w.api_connector.llamadas, 2, "con la API caída se reintenta")
finally:
    settings.clear()
    settings.sync()

C.cerrar()
