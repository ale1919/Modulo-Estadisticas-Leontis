"""Autoactualización de la app, antes de abrir su ventana principal.

Este archivo es **el mismo en todas las apps**: se edita en MINIhub y se reparte
con `sincronizar_nucleo.py`. Lo único que cambia entre apps es el `APP_NAME` de su
`version.py`, y de ahí salen todos los textos.

Cada app se actualiza a sí misma con `Instalacion(APP_NAME, su propia carpeta)`,
el mismo mecanismo con el que MINIhub instala y actualiza a las demás. Las dos
cosas tienen que existir: la gente abre el `.exe` desde un acceso directo sin
pasar por MINIhub, así que si una app no se autoactualiza, el que la abra directo
se queda con código viejo.

La política es "obligatoria con aviso": si hay versión nueva se muestra qué cambió
y se baja sin preguntar, y al terminar se reinicia. Cancelar cierra la app en vez
de dejar entrar con una versión vieja (son apps de trabajo en testeo y no sirve
que reporten bugs ya arreglados).

Con una excepción a propósito: si la actualización **no se puede** aplicar (el FTP
no responde, la carpeta no es escribible, un objeto llegó corrupto), se avisa y se
entra igual con la versión que hay. Dejar a alguien afuera de su herramienta por
un problema del FTP es peor que tenerlo una versión atrás.

Toda la red y el hasheo corren en un QThread; la UI solo pinta progreso.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QEventLoop, QThread, QTimer, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox,
                               QProgressBar, QPushButton, QTextEdit, QVBoxLayout)

from . import nucleo
from .version import APP_NAME, APP_VERSION


# Cuánto se espera antes de mostrar el diálogo si el chequeo todavía no terminó.
# Medido contra el FTP real, leer un manifiesto tarda ~700 ms: con el umbral en
# 800 ms el diálogo alcanzaba a aparecer y desaparecer en un arranque normal, que
# es justo lo que arranca oculto para evitar. Con 2,5 s no se ve nunca cuando no
# hay nada que hacer, y sigue dando señal de vida si el FTP está colgado (su
# timeout es de 12 s).
MS_ANTES_DE_MOSTRAR = 2500


def fmt_bytes(n):
    if n <= 0:
        return "0 MB"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


class HiloAutoActualizacion(QThread):
    """Chequea el manifiesto de MINIhub, baja lo que falta y lo aplica."""

    estado = Signal(str)
    disponible = Signal(str, str, int)   # versión, notas, bytes a bajar
    progreso = Signal(int, int)          # bytes hechos, bytes totales
    resultado = Signal(str, str)         # código, detalle

    def __init__(self, instalacion, parent=None):
        super().__init__(parent)
        self.instalacion = instalacion
        self._cancelar = False
        self.pendientes = []

    def cancelar(self):
        self._cancelar = True

    def run(self):
        try:
            self.estado.emit("Buscando actualizaciones…")
            # Con el FTP caído no se espera: antes cada arranque perdía 12 s acá, con
            # el diálogo en pantalla y «Cancelar y salir» como único botón. La sonda
            # tarda como mucho `TIMEOUT_SONDA_FTP`, menos de lo que tarda en aparecer
            # el diálogo. Es lo mismo que cualquier otro fallo del FTP: se sigue.
            if not nucleo.ftp_responde():
                self.resultado.emit("sin-red", "el servidor FTP no responde")
                return
            try:
                manifiesto = nucleo.obtener_manifiesto(
                    APP_NAME, timeout=nucleo.TIMEOUT_FTP_CHEQUEO)
            except Exception as e:
                # FTP caído, sin red, todavía no se publicó, firma inválida:
                # nada de esto justifica frenar el arranque.
                self.resultado.emit("sin-red", str(e))
                return

            remota = manifiesto.get("version", "")
            if not nucleo.es_mas_nueva(remota, APP_VERSION):
                self.resultado.emit("al-dia", remota)
                return

            if not self.instalacion.escribible():
                self.resultado.emit("no-escribible", remota)
                return

            self.estado.emit("Comparando archivos…")
            plan = self.instalacion.armar_plan(manifiesto)
            self.instalacion.podar_staging(plan)
            if not plan.hay_algo_que_hacer:
                # Mismo contenido con otro número de versión.
                self.resultado.emit("al-dia", remota)
                return

            self.disponible.emit(plan.version, plan.notas, plan.bytes_a_bajar)
            if self._cancelar:
                self.resultado.emit("cancelado", "")
                return

            self.estado.emit(f"Descargando {fmt_bytes(plan.bytes_a_bajar)}…")
            self.instalacion.descargar_objetos(
                plan,
                progreso_cb=lambda h, t: self.progreso.emit(h, t),
                cancelar_cb=lambda: self._cancelar,
            )

            self.estado.emit("Instalando…")
            self.pendientes = self.instalacion.aplicar(plan)
            self.instalacion.registrar_instalado(manifiesto)

            self.resultado.emit(
                "reinicio-pendiente" if self.pendientes else "actualizado", remota
            )

        except nucleo.ActualizacionCancelada:
            self.resultado.emit("cancelado", "")
        except Exception as e:
            self.resultado.emit("error", str(e))


class DialogoAutoActualizacion(QDialog):
    """Ventana de progreso. Arranca oculta: se muestra solo si el chequeo tarda o
    si efectivamente hay versión nueva, para no hacer parpadear nada en cada
    arranque."""

    def __init__(self, instalacion, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Actualización de {APP_NAME}")
        self.setMinimumWidth(480)
        # Con ventana detrás (MINIhub, que se autoactualiza con su ventana ya
        # abierta) el diálogo es modal: mientras se reemplaza el build no se
        # puede seguir usando la app que se está reemplazando.
        if parent is not None:
            self.setModal(True)

        self.continuar_app = True
        self.reiniciar_app = False
        self.terminado = False

        layout = QVBoxLayout(self)

        self.lbl_titulo = QLabel("Buscando actualizaciones…")
        self.lbl_titulo.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.lbl_titulo)

        self.lbl_estado = QLabel(f"Versión instalada: {APP_VERSION}")
        layout.addWidget(self.lbl_estado)

        self.txt_notas = QTextEdit()
        self.txt_notas.setReadOnly(True)
        self.txt_notas.setMaximumHeight(140)
        self.txt_notas.hide()
        layout.addWidget(self.txt_notas)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)   # Indeterminado mientras chequea.
        layout.addWidget(self.progress)

        botones = QHBoxLayout()
        botones.addStretch(1)
        self.btn_cancelar = QPushButton("Cancelar y salir")
        self.btn_cancelar.clicked.connect(self._pedir_cancelar)
        botones.addWidget(self.btn_cancelar)
        layout.addLayout(botones)

        self.hilo = HiloAutoActualizacion(instalacion, self)
        self.hilo.estado.connect(self.lbl_estado.setText)
        self.hilo.disponible.connect(self._on_disponible)
        self.hilo.progreso.connect(self._on_progreso)
        self.hilo.resultado.connect(self._on_resultado)
        self.instalacion = instalacion

    def iniciar(self):
        self.hilo.start()
        # Si hay una ventana detrás, el chequeo no se anuncia: la app ya está en
        # pantalla y un cartel que aparece y se va solo es peor que nada. El
        # diálogo sale igual apenas se sepa que hay versión nueva
        # (`_on_disponible`) o que algo falló. Sin ventana detrás —el resto de
        # las apps, que chequean antes de abrir la suya— la pantalla estaría
        # vacía, y ahí sí conviene mostrar que se está haciendo algo.
        if self.parent() is None:
            QTimer.singleShot(MS_ANTES_DE_MOSTRAR, self._mostrar_si_sigue)

    def _mostrar_si_sigue(self):
        if not self.terminado and not self.isVisible():
            self.show()

    def _on_disponible(self, version, notas, bytes_total):
        self.lbl_titulo.setText(f"Nueva versión de {APP_NAME}: {version}")
        self.lbl_estado.setText(
            f"Tenés la {APP_VERSION}. Se van a descargar {fmt_bytes(bytes_total)}."
        )
        if notas:
            self.txt_notas.setPlainText(notas)
            self.txt_notas.show()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.adjustSize()
        if not self.isVisible():
            self.show()

    def _on_progreso(self, hechos, total):
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(hechos)
            self.lbl_estado.setText(
                f"Descargando… {fmt_bytes(hechos)} de {fmt_bytes(total)}"
            )

    def _on_resultado(self, codigo, detalle):
        self.terminado = True

        if codigo in ("al-dia", "sin-red"):
            self.continuar_app = True
            self.accept()
            return

        if codigo == "cancelado":
            self.continuar_app = False
            self.reject()
            return

        if codigo in ("actualizado", "reinicio-pendiente"):
            self.lbl_titulo.setText(f"Actualizado a la versión {detalle}")
            self.lbl_estado.setText("Reiniciando…")
            self.progress.setRange(0, 1)
            self.progress.setValue(1)
            self.btn_cancelar.setEnabled(False)
            self.continuar_app = False
            self.reiniciar_app = True
            if codigo == "reinicio-pendiente":
                # Quedaron archivos trabados por otro programa: los termina un
                # .cmd cuando este proceso cierre, y él relanza la app.
                self.instalacion.lanzar_ayudante(
                    self.hilo.pendientes, relanzar=sys.executable
                )
                self.reiniciar_app = False
            QTimer.singleShot(1200, self.accept)
            return

        # "error" o "no-escribible": se avisa y se entra igual.
        self.continuar_app = True
        self._avisar_falla(codigo, detalle)
        self.accept()

    def _avisar_falla(self, codigo, detalle):
        if codigo == "no-escribible":
            texto = (
                f"Hay una versión nueva de {APP_NAME} ({detalle}) pero no se puede "
                "escribir en su carpeta, así que no se actualizó.\n\n"
                "Movela a una carpeta propia (por ejemplo dentro de tu usuario) en "
                "vez de Archivos de programa, y volvé a abrirla."
            )
        else:
            texto = (
                "No se pudo completar la actualización:\n\n"
                f"{detalle}\n\nSe abre la versión que ya tenías."
            )
        if self.instalacion.en_onedrive():
            texto += (
                f"\n\nOjo: {APP_NAME} está dentro de OneDrive. La sincronización "
                "interfiere con el reemplazo de archivos; conviene moverla afuera."
            )
        QMessageBox.warning(self, "Actualización", texto)

    def _pedir_cancelar(self):
        if self.terminado:
            return
        r = QMessageBox.question(
            self, "Cancelar actualización",
            f"La actualización es obligatoria: si cancelás, {APP_NAME} se cierra."
            "\n\n¿Cancelar y salir?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if r != QMessageBox.Yes:
            return
        self.btn_cancelar.setEnabled(False)
        self.lbl_estado.setText("Cancelando…")
        self.hilo.cancelar()

    def closeEvent(self, event):
        if not self.terminado:
            event.ignore()
            self._pedir_cancelar()
            return
        event.accept()


def chequear_al_inicio(carpeta, parent=None):
    """Punto de entrada. Devuelve True si la app tiene que seguir arrancando y
    False si tiene que cerrarse (porque se actualizó y se relanzó, o porque el
    usuario canceló).

    Se llama desde `main.py` después de crear el QApplication y antes de construir
    la ventana principal.

    `parent` es para el caso de MINIhub, que lo llama **con su ventana ya
    abierta**: ahí el chequeo no tiene por qué mostrar nada (la app ya está en
    pantalla) y el diálogo, cuando haga falta, sale modal encima de ella. El
    resto de las apps lo llaman sin padre y nada cambia para ellas.
    """
    # Anotarse en el registro local de instalaciones, para que MINIhub sepa dónde
    # está esta app aunque no la haya instalado él. Es el caso de todas las copias
    # que se repartieron a mano antes de que MINIhub existiera: viven en el
    # escritorio, en D:, donde cada uno las haya dejado. Sin esto, MINIhub las
    # daría por no instaladas y pondría una segunda copia al lado.
    #
    # Se registra la APP_VERSION **compilada**, que es la fuente de verdad de qué
    # versión es esta: `instalado.json` solo existe si la copia pasó alguna vez por
    # el updater, y estas no pasaron.
    #
    # Solo desde el .exe: registrar el árbol de código en desarrollo haría que
    # MINIhub ofreciera "actualizar" el repositorio fuente.
    if getattr(sys, "frozen", False):
        nucleo.registrar_ubicacion(
            APP_NAME, carpeta, version=APP_VERSION,
            exe=Path(sys.executable).name,
        )

    if not nucleo.modo_activo():
        return True

    instalacion = nucleo.Instalacion(APP_NAME, carpeta)
    # Restos de la actualización anterior: ahora sí se pueden borrar, el proceso
    # que los tenía abiertos ya murió. El staging no, que son los objetos ya
    # bajados de una descarga que se cortó; los que ya no sirvan los saca
    # `podar_staging()` cuando el plan diga qué hace falta.
    instalacion.limpiar_rastros(incluir_staging=False)

    dlg = DialogoAutoActualizacion(instalacion, parent)
    espera = QEventLoop()
    dlg.finished.connect(espera.quit)
    dlg.iniciar()
    espera.exec()

    if dlg.hilo.isRunning():
        dlg.hilo.cancelar()
        dlg.hilo.wait(4000)

    if dlg.reiniciar_app:
        try:
            nucleo.lanzar(sys.executable, carpeta)
        except Exception:
            pass
    return dlg.continuar_app
