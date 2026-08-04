"""Ventana que comprueba los requisitos del sistema y los resuelve.

Este archivo es **el mismo en todas las apps**: se edita en MINIhub y se reparte
con `sincronizar_nucleo.py`. Toda la detección, descarga e instalación está en
`requisitos.py`; acá solo hay la ventana y el hilo que la alimenta.

Es la misma forma que el diálogo de actualización (`ui_updater.py`) a propósito:
arranca oculta, se muestra recién a los 800 ms o cuando efectivamente hay algo que
hacer, y la red corre en un `QThread` para que la UI no se congele. En un arranque
normal —que es el 99,9% de los arranques— **no se ve nada y no se toca la red**:
la detección es local y tarda milisegundos.

Política
--------
Igual que con las actualizaciones, la regla es no dejar a nadie afuera de su
herramienta por algo que no es culpa suya. Si un requisito falta y no se puede
instalar solo, se avisa con el nombre exacto de lo que falta y un botón para
instalarlo a mano, pero se entra igual — salvo que el requisito venga marcado
`critico` en el `requisitos.json` firmado, y ahí sí se cierra.

Que el default sea "avisar y entrar" no es descuido: cualquier requisito que
realmente impida funcionar ya habría hecho fallar el arranque del `.exe` antes de
llegar acá (ver el encabezado de `requisitos.py`). O sea que todo lo que este
diálogo llega a detectar, por definición, no impidió abrir la app. Bloquear ahí
sería castigar al usuario por una detección que puede estar equivocada.
"""

from PySide6.QtCore import QEventLoop, QThread, QTimer, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox,
                               QProgressBar, QPushButton, QTextEdit, QVBoxLayout)

from . import nucleo, requisitos
from .version import APP_NAME


def fmt_bytes(n):
    if n <= 0:
        return "0 MB"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


class HiloRequisitos(QThread):
    """Detecta, baja e instala. Todo lo lento, fuera del hilo de la UI."""

    estado = Signal(str)
    faltan = Signal(list, int)        # títulos, bytes a bajar
    progreso = Signal(int, int)
    resultado = Signal(str, str)      # código, detalle

    def __init__(self, nombres=None, parent=None):
        super().__init__(parent)
        self.nombres = nombres
        self._cancelar = False
        self.pendientes = []          # Requisitos que hay que instalar a mano.
        self.criticos = []
        self.reinicio_pendiente = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        try:
            self._trabajar()
        except nucleo.ActualizacionCancelada:
            self.resultado.emit("cancelado", "")
        except Exception as e:
            # Un problema comprobando requisitos no puede impedir abrir la app.
            self.resultado.emit("error", str(e))

    def _trabajar(self):
        self.estado.emit("Comprobando requisitos del sistema…")

        # Primera pasada SIN red: es lo que corre en todos los arranques.
        faltan = requisitos.faltantes(self.nombres, solo_local=True)
        if not faltan:
            self.resultado.emit("ok", "")
            return

        # Recién ahora vale la pena ir al FTP, que es lo único que trae los
        # instaladores. Si no contesta, quedan todos como "a mano".
        self.estado.emit("Buscando cómo resolverlo…")
        sesion = None
        try:
            sesion = nucleo.Sesion()
            faltan = requisitos.faltantes(self.nombres, sesion=sesion)
        except Exception:
            # Ojo: la sesión puede haberse abierto y haber fallado la consulta.
            # Si se pierde la referencia sin cerrarla, queda una conexión FTP
            # colgada hasta que el proceso muera.
            self._cerrar(sesion)
            sesion = None

        if not faltan:
            self.resultado.emit("ok", "")
            return

        self.criticos = [r for r in faltan if r.datos.get("critico")]
        instalables = [r for r in faltan if r.se_puede_instalar and sesion]
        self.pendientes = [r for r in faltan if r not in instalables]

        self.faltan.emit([r.titulo for r in faltan],
                         sum(r.tam for r in instalables))

        if not instalables:
            self._cerrar(sesion)
            self.resultado.emit("manual", self._detalle_manual())
            return

        try:
            for req in instalables:
                if self._cancelar:
                    raise nucleo.ActualizacionCancelada()
                self._resolver(req, sesion)
        finally:
            self._cerrar(sesion)

        if self.pendientes:
            self.resultado.emit("manual", self._detalle_manual())
        elif self.reinicio_pendiente:
            self.resultado.emit("reinicio", "")
        else:
            self.resultado.emit("instalado", "")

    def _resolver(self, req, sesion):
        self.estado.emit(f"Descargando {req.titulo}…")
        try:
            instalador = requisitos.descargar(
                req, sesion=sesion,
                progreso_cb=lambda h, t: self.progreso.emit(h, t),
                cancelar_cb=lambda: self._cancelar,
            )
        except nucleo.ActualizacionCancelada:
            raise
        except Exception as e:
            req.motivo_manual = str(e)
            self.pendientes.append(req)
            return

        self.estado.emit(f"Instalando {req.titulo}… (puede pedir permiso de administrador)")
        res = requisitos.instalar(req, instalador)

        if res.codigo == "reinicio":
            self.reinicio_pendiente = True
        elif not res.bien:
            req.motivo_manual = res.detalle
            req.instalador_bajado = instalador
            self.pendientes.append(req)

    def _detalle_manual(self):
        lineas = []
        for req in self.pendientes:
            motivo = getattr(req, "motivo_manual", "")
            lineas.append(f"• {req.titulo}")
            if req.porque:
                lineas.append(f"    {req.porque}")
            if motivo:
                lineas.append(f"    No se pudo solo: {motivo}")
            if req.arreglo_manual:
                lineas.append(f"    {req.arreglo_manual}")
            elif req.manual:
                lineas.append(f"    Descarga: {req.manual}")
        return "\n".join(lineas)

    @staticmethod
    def _cerrar(sesion):
        if sesion is not None:
            sesion.cerrar()


class DialogoRequisitos(QDialog):
    """Oculta mientras no haga falta; se muestra sola si hay algo que resolver."""

    def __init__(self, nombres=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Requisitos de {APP_NAME}")
        self.setMinimumWidth(520)

        self.continuar_app = True
        self.terminado = False

        layout = QVBoxLayout(self)

        self.lbl_titulo = QLabel("Comprobando requisitos del sistema…")
        self.lbl_titulo.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.lbl_titulo)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setWordWrap(True)
        layout.addWidget(self.lbl_estado)

        self.txt_detalle = QTextEdit()
        self.txt_detalle.setReadOnly(True)
        self.txt_detalle.setMaximumHeight(160)
        self.txt_detalle.hide()
        layout.addWidget(self.txt_detalle)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        botones = QHBoxLayout()
        botones.addStretch(1)
        self.btn_manual = QPushButton("Instalar a mano")
        self.btn_manual.clicked.connect(self._instalar_a_mano)
        self.btn_manual.hide()
        botones.addWidget(self.btn_manual)

        self.btn_reintentar = QPushButton("Volver a comprobar")
        self.btn_reintentar.clicked.connect(self._reintentar)
        self.btn_reintentar.hide()
        botones.addWidget(self.btn_reintentar)

        self.btn_cerrar = QPushButton("Cancelar")
        self.btn_cerrar.clicked.connect(self._on_boton_cerrar)
        botones.addWidget(self.btn_cerrar)
        layout.addLayout(botones)

        self.nombres = nombres
        self.hilo = None
        self._enganchar_hilo()

    def _enganchar_hilo(self):
        self.hilo = HiloRequisitos(self.nombres, self)
        self.hilo.estado.connect(self.lbl_estado.setText)
        self.hilo.faltan.connect(self._on_faltan)
        self.hilo.progreso.connect(self._on_progreso)
        self.hilo.resultado.connect(self._on_resultado)

    def iniciar(self):
        self.hilo.start()
        QTimer.singleShot(800, self._mostrar_si_sigue)

    def _mostrar_si_sigue(self):
        if not self.terminado and not self.isVisible():
            self.show()

    def _on_faltan(self, titulos, bytes_total):
        self.lbl_titulo.setText("Falta algo para que la app funcione bien")
        self.txt_detalle.setPlainText(
            "En esta PC no se detectaron:\n\n" + "\n".join(f"• {t}" for t in titulos)
        )
        self.txt_detalle.show()
        if bytes_total > 0:
            self.lbl_estado.setText(
                f"Se van a descargar e instalar automáticamente "
                f"({fmt_bytes(bytes_total)})."
            )
        self.adjustSize()
        if not self.isVisible():
            self.show()

    def _on_progreso(self, hechos, total):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(hechos)

    def _on_resultado(self, codigo, detalle):
        self.terminado = True
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

        if codigo == "ok":
            self.continuar_app = True
            self.accept()
            return

        if codigo == "instalado":
            self.lbl_titulo.setText("Listo, ya está todo instalado")
            self.lbl_estado.setText(f"Abriendo {APP_NAME}…")
            self.btn_cerrar.setEnabled(False)
            self.continuar_app = True
            QTimer.singleShot(1200, self.accept)
            return

        if codigo == "reinicio":
            self.continuar_app = True
            QMessageBox.information(
                self, "Requisitos",
                "Se instaló lo que faltaba, pero Windows pide reiniciar para "
                f"terminar.\n\n{APP_NAME} se abre igual; si algo funciona raro, "
                "reiniciá la PC.",
            )
            self.accept()
            return

        if codigo == "cancelado":
            # Cancelar la instalación de un requisito no cierra la app: lo que
            # falta puede no hacer falta hoy.
            self.continuar_app = True
            self.reject()
            return

        if codigo == "error":
            self.continuar_app = True
            self.accept()
            return

        # "manual": hay que resolverlo a mano.
        self._pasar_a_manual(detalle)

    def _pasar_a_manual(self, detalle):
        hay_criticos = bool(self.hilo.criticos)
        self.lbl_titulo.setText("Hay que instalar esto a mano")
        self.txt_detalle.setPlainText(detalle)
        self.txt_detalle.show()
        self.progress.hide()

        if hay_criticos:
            self.lbl_estado.setText(
                f"Sin esto {APP_NAME} no puede funcionar. Instalalo y volvé a "
                "comprobar."
            )
            self.btn_cerrar.setText("Salir")
            self.continuar_app = False
        else:
            self.lbl_estado.setText(
                f"{APP_NAME} se puede abrir igual, pero conviene resolverlo: es "
                "la causa más común de que la app deje de arrancar."
            )
            self.btn_cerrar.setText(f"Abrir {APP_NAME} igual")
            self.continuar_app = True

        if any(r.manual or getattr(r, "instalador_bajado", None)
               for r in self.hilo.pendientes):
            self.btn_manual.show()
        self.btn_reintentar.show()
        self.adjustSize()
        if not self.isVisible():
            self.show()

    def _instalar_a_mano(self):
        abiertos = 0
        for req in self.hilo.pendientes:
            if requisitos.abrir_para_instalar_a_mano(
                req, getattr(req, "instalador_bajado", None)
            ):
                abiertos += 1
        if not abiertos:
            QMessageBox.warning(
                self, "Requisitos",
                "No se pudo abrir el instalador ni la página de descarga.\n\n"
                "Buscá 'Microsoft Visual C++ Redistributable x64' en el sitio de "
                "Microsoft, instalalo y volvé a abrir la app.",
            )
            return
        self.lbl_estado.setText(
            "Terminá la instalación en la ventana que se abrió y después apretá "
            "«Volver a comprobar»."
        )

    def _reintentar(self):
        self.terminado = False
        self.btn_manual.hide()
        self.btn_reintentar.hide()
        self.btn_cerrar.setText("Cancelar")
        self.txt_detalle.hide()
        self.progress.show()
        self.progress.setRange(0, 0)
        self.lbl_titulo.setText("Comprobando requisitos del sistema…")
        self._enganchar_hilo()
        self.hilo.start()

    def _on_boton_cerrar(self):
        if self.terminado:
            self.accept() if self.continuar_app else self.reject()
            return
        self.hilo.cancelar()
        self.lbl_estado.setText("Cancelando…")
        self.btn_cerrar.setEnabled(False)

    def closeEvent(self, event):
        if not self.terminado:
            self.hilo.cancelar()
        event.accept()


def chequear_al_inicio(nombres=None):
    """Punto de entrada. Devuelve True si la app tiene que seguir arrancando.

    Se llama desde `main.py` después de crear el QApplication. `nombres` limita el
    chequeo a los requisitos que declara esta app; sin él se chequean todos los
    conocidos, que es lo correcto para las apps PySide6 (necesitan lo mismo).

    Solo corre en el `.exe` compilado, igual que el updater: en desarrollo la
    máquina es la del que programa y ya tiene todo.
    """
    if not nucleo.modo_activo():
        return True

    dlg = DialogoRequisitos(nombres)
    espera = QEventLoop()
    dlg.finished.connect(espera.quit)
    dlg.iniciar()
    espera.exec()

    if dlg.hilo.isRunning():
        dlg.hilo.cancelar()
        dlg.hilo.wait(4000)

    return dlg.continuar_app
