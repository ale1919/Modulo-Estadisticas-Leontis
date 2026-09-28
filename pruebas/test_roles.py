"""Roles de acceso de Leontis: modo usuario, modo avanzado con contraseña.

Tres partes, las tres contra la base sintética:

1. `usa_roles_de_acceso`: cada estado de la preferencia (activada, desactivada,
   sin fila, base de un Leontis anterior sin la tabla o sin la columna, base
   caída). Ante un error que no sea "no existe", se entra con MENOS permisos.
2. `verificar_clave_administrador`: el dominio de la contraseña ingresada y de
   la guardada (espacios, mayúsculas, ñ, vacía, nula, la de otra empresa...).
3. La ventana principal de verdad (sin pantalla): qué se ve y qué se exporta en
   cada modo, desbloquear, cancelar, contraseña mala, volver a bloquear.

La ventana guarda preferencias en el registro: se usan empresas 327xx (idEmpresa es SMALLINT) y sus
grupos se borran al final.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine, text  # noqa: E402

from entorno import CNF, BaseSintetica, Checks  # noqa: E402

C = Checks("roles de acceso")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import main  # noqa: E402
from Recursos.Modulos.db_connection import DBManager  # noqa: E402

CON_ROLES, SIN_ROLES, SIN_FILA, SIN_CLAVE, CLAVE_VACIA, CON_ENIE = (
    32701, 32702, 32703, 32704, 32705, 32706)   # idEmpresa es SMALLINT
PERMITIDOS = {"export_articles", "export_clients", "stock_analysis"}


def preferencia(B, empresa, usa_roles):
    B.ejecutar("INSERT INTO empresaspreferencias (idEmpresa, SolicitarMedioDePago,"
               " SolicitarMedioDePagoAlInicio, UsarRolesAcceso) VALUES (:e, 0, 0, :r)",
               [{"e": empresa, "r": usa_roles}])


def clave(B, empresa, valor):
    B.ejecutar("UPDATE empresas SET PasswordAdministrador = :p WHERE idEmpresa = :e",
               [{"e": empresa, "p": valor}])


# Lo que muestran los carteles, en vez de abrirlos (en offscreen se colgarían).
carteles = []
for nombre in ("warning", "information", "critical"):
    setattr(main.QMessageBox, nombre,
            staticmethod(lambda *a, _n=nombre: carteles.append((_n, a[2] if len(a) > 2 else ""))))
respuestas = []
main.QInputDialog.getText = staticmethod(lambda *a, **k: respuestas.pop(0))
tableros = []
main.MainWindow.setup_dashboard = lambda self: tableros.append(self)

settings = QSettings("Leontis", "AnalizadorEstadisticas")

try:
    with BaseSintetica() as B:
        for e in (CON_ROLES, SIN_ROLES, SIN_FILA, SIN_CLAVE, CLAVE_VACIA, CON_ENIE):
            B.empresa(e)
            B.articulo(e, e, "Articulo")
        preferencia(B, CON_ROLES, 1)
        preferencia(B, SIN_ROLES, 0)
        preferencia(B, SIN_CLAVE, 1)
        preferencia(B, CLAVE_VACIA, 1)
        preferencia(B, CON_ENIE, 1)
        clave(B, CON_ROLES, "Secreta1")
        clave(B, SIN_ROLES, "OtraClave")
        clave(B, CLAVE_VACIA, "   ")
        clave(B, CON_ENIE, "  ñandú  ")

        db = B.db

        # -- 1. la preferencia -------------------------------------------- #
        C.igual(db.usa_roles_de_acceso(CON_ROLES), True, "roles activados")
        C.igual(db.usa_roles_de_acceso(SIN_ROLES), False, "roles desactivados")
        C.igual(db.usa_roles_de_acceso(SIN_FILA), False, "sin fila de preferencias")
        C.igual(db.usa_roles_de_acceso(32000), False, "empresa inexistente")

        # -- 2. la contraseña --------------------------------------------- #
        CASOS = [
            (CON_ROLES, "Secreta1", True, "la correcta"),
            (CON_ROLES, "  Secreta1  ", True, "con espacios alrededor"),
            (CON_ROLES, "Secreta1\t", True, "con un tab al final"),
            (CON_ROLES, "secreta1", False, "otra mayúscula"),
            (CON_ROLES, "SECRETA1", False, "todo en mayúsculas"),
            (CON_ROLES, "Secreta", False, "un carácter de menos"),
            (CON_ROLES, "Secreta12", False, "un carácter de más"),
            (CON_ROLES, "Secre ta1", False, "espacio en el medio"),
            (CON_ROLES, "", False, "vacía"),
            (CON_ROLES, "   ", False, "solo espacios"),
            (CON_ROLES, None, False, "nula"),
            (CON_ROLES, 12345, False, "un número"),
            (CON_ROLES, "' OR '1'='1", False, "inyección SQL"),
            (CON_ROLES, "OtraClave", False, "la de otra empresa"),
            (CON_ROLES, "Secreta1" * 100, False, "muy larga"),
            (CON_ENIE, "ñandú", True, "con ñ y acento"),
            (CON_ENIE, "nandu", False, "sin ñ ni acento"),
            (CON_ENIE, "Ñandú", False, "Ñ mayúscula"),
            (SIN_CLAVE, "", False, "guardada nula, ingresada vacía"),
            (SIN_CLAVE, "cualquiera", False, "guardada nula"),
            (CLAVE_VACIA, "", False, "guardada en blanco, ingresada vacía"),
            (CLAVE_VACIA, "   ", False, "guardada en blanco, ingresada en blanco"),
            (32000, "Secreta1", False, "empresa inexistente"),
        ]
        for empresa, ingresada, esperado, nombre in CASOS:
            ok, motivo = db.verificar_clave_administrador(empresa, ingresada)
            C.igual(ok, esperado, f"clave: {nombre}")
            C.check((motivo is None) == esperado, f"clave: {nombre}, motivo solo si falla")
        _, motivo = db.verificar_clave_administrador(SIN_CLAVE, "x")
        C.check("no tiene contraseña" in motivo, "sin clave: el cartel lo dice")
        _, motivo = db.verificar_clave_administrador(CON_ROLES, "mala")
        C.igual(motivo, "Contraseña incorrecta.", "clave mala: el cartel lo dice")
        _, motivo = db.verificar_clave_administrador(32000, "x")
        C.check("No se encontró la empresa" in motivo, "empresa inexistente: el cartel lo dice")

        # Un valor que no es 0 ni 1 en la preferencia (la columna es TINYINT, así
        # que en una base real no debería pasar): ante la duda, modo usuario.
        import pandas as pd
        real = db._execute_query
        for raro in ("abc", None, 2, "1", "0"):
            db._execute_query = lambda *a, _v=raro, **k: pd.DataFrame({"x": [_v]})
            esperado = {"abc": True, None: True, 2: True, "1": True, "0": False}[raro]
            C.igual(db.usa_roles_de_acceso(CON_ROLES), esperado, f"preferencia con valor {raro!r}")
        db._execute_query = real

        # -- 3. la ventana ------------------------------------------------ #
        def ventana(empresa):
            carteles.clear()
            tableros.clear()
            w = main.MainWindow(db, {"id_empresa": empresa, "razon_social": "Prueba"})
            for _ in range(3):
                app.processEvents()      # los temporizadores de load_settings
            return w

        def pestanas(w):
            t = w.main_tab_widget
            return {t.tabText(i): t.isTabVisible(i) for i in range(t.count())}

        def visibles(w):
            return {k for k, cfg in w.report_widget_config.items()
                    if not cfg["widget"].isHidden()}

        def exporta(w):
            return {d[6] for d in w.logic.generate_statistics()}

        def en_modo_usuario(w, contexto):
            C.igual(w.user_role, "usuario", f"{contexto}: rol")
            C.igual(visibles(w), PERMITIDOS, f"{contexto}: tarjetas visibles")
            p = pestanas(w)
            C.igual(p.get("Panel de Control"), False, f"{contexto}: sin Panel de Control")
            C.igual(p.get("Ventas"), False, f"{contexto}: sin pestaña Ventas")
            for nombre in ("Artículos", "Clientes", "Stock"):
                C.igual(p.get(nombre), True, f"{contexto}: pestaña {nombre}")
            C.check(w.main_tab_widget.isTabVisible(w.main_tab_widget.currentIndex()),
                    f"{contexto}: la pestaña actual es visible")
            C.check(not w.modo_avanzado_btn.isHidden(), f"{contexto}: botón visible")
            C.check("Modo Avanzado" in w.modo_avanzado_btn.text(), f"{contexto}: botón dice Avanzado")
            C.igual(exporta(w), {"stock_analysis"}, f"{contexto}: solo exporta lo permitido")
            for clave_rep in ("sales_over_time", "cta_cte", "margin_by_article", "rfm_segmentation"):
                C.igual(w.reporte_permitido(clave_rep), False, f"{contexto}: {clave_rep} bloqueado")

        def en_modo_admin(w, contexto, con_boton):
            C.igual(w.user_role, "admin", f"{contexto}: rol")
            C.igual(visibles(w), set(w.report_widget_config), f"{contexto}: todas las tarjetas")
            C.check(all(pestanas(w).values()), f"{contexto}: todas las pestañas")
            C.igual(not w.modo_avanzado_btn.isHidden(), con_boton, f"{contexto}: botón")
            if con_boton:
                C.check("Modo Usuario" in w.modo_avanzado_btn.text(),
                        f"{contexto}: botón dice volver a usuario")
            C.check({"sales_over_time", "cta_cte", "rfm_segmentation"} <= exporta(w),
                    f"{contexto}: exporta los informes de administrador")

        # Sin roles: administrador directo, sin botón.
        for empresa, nombre in ((SIN_ROLES, "roles desactivados"), (SIN_FILA, "sin fila")):
            w = ventana(empresa)
            en_modo_admin(w, nombre, con_boton=False)
            C.igual(len(tableros), 1, f"{nombre}: arranca el Panel de Control")
            w.deleteLater()

        # Con roles.
        w = ventana(CON_ROLES)
        en_modo_usuario(w, "al abrir")
        C.igual(len(tableros), 0, "modo usuario: no arranca el Panel de Control")

        respuestas.append(("Secreta1", False))                 # cancelar
        w.alternar_modo_avanzado()
        en_modo_usuario(w, "cancelado")
        C.igual(carteles, [], "cancelado: sin carteles")

        respuestas.append(("mala", True))
        w.alternar_modo_avanzado()
        en_modo_usuario(w, "clave mala")
        C.igual(carteles, [("warning", "Contraseña incorrecta.")], "clave mala: avisa")

        carteles.clear()
        respuestas.append(("  Secreta1 ", True))
        w.alternar_modo_avanzado()
        en_modo_admin(w, "desbloqueado", con_boton=True)
        C.igual(carteles, [], "desbloqueado: sin carteles")
        C.igual(len(tableros), 1, "desbloqueado: arranca el Panel de Control")

        # Parado en una pestaña que el modo usuario no ve, y se bloquea.
        t = w.main_tab_widget
        t.setCurrentIndex([t.tabText(i) for i in range(t.count())].index("Ventas"))
        w.alternar_modo_avanzado()
        en_modo_usuario(w, "vuelto a bloquear")
        C.igual(respuestas, [], "volver a bloquear no pide contraseña")

        # El grupo "Informes Inactivos" de cada pestaña: se ve solo si adentro
        # hay algo que el modo actual puede ver.
        def grupos_visibles(w):
            return {tab for tab, (grupo, _) in w.inactive_reports_map.items()
                    if not grupo.isHidden()}

        w.report_buttons["sales_over_time"].setChecked(False)     # restringido
        app.processEvents()
        C.igual(grupos_visibles(w), set(), "usuario: inactivo restringido no muestra el grupo")
        w.report_buttons["stock_analysis"].setChecked(False)      # permitido
        app.processEvents()
        C.igual(grupos_visibles(w), {"Stock"}, "usuario: inactivo permitido muestra su grupo")
        respuestas.append(("Secreta1", True))
        w.alternar_modo_avanzado()
        C.igual(grupos_visibles(w), {"Stock", "ventas"}, "admin: los dos grupos de inactivos")
        w.alternar_modo_avanzado()
        C.igual(grupos_visibles(w), {"Stock"}, "vuelto a usuario: solo el permitido")
        w.report_buttons["sales_over_time"].setChecked(True)
        w.report_buttons["stock_analysis"].setChecked(True)
        app.processEvents()
        C.igual(grupos_visibles(w), set(), "sin inactivos: ningún grupo")

        # Tildar y destildar tarjetas en modo usuario no las destapa.
        for boton in w.report_buttons.values():
            boton.setChecked(False)
            boton.setChecked(True)
        app.processEvents()
        C.igual(visibles(w), PERMITIDOS, "tildar tarjetas en modo usuario no las muestra")
        w.deleteLater()

        # Con roles y sin contraseña configurada: no desbloquea, y lo dice.
        w = ventana(SIN_CLAVE)
        respuestas.append(("", True))
        w.alternar_modo_avanzado()
        en_modo_usuario(w, "sin clave configurada")
        C.check(carteles and "no tiene contraseña" in carteles[-1][1],
                "sin clave configurada: avisa que falta en Leontis")
        w.deleteLater()

        # -- 1 bis. bases de un Leontis anterior a los roles --------------- #
        B.ejecutar("ALTER TABLE empresaspreferencias DROP COLUMN UsarRolesAcceso", [{}])
        C.igual(db.usa_roles_de_acceso(CON_ROLES), False, "base sin la columna: sin roles")
        B.ejecutar("DROP TABLE empresaspreferencias", [{}])
        C.igual(db.usa_roles_de_acceso(CON_ROLES), False, "base sin la tabla: sin roles")
        w = ventana(CON_ROLES)
        en_modo_admin(w, "base sin la tabla", con_boton=False)
        w.deleteLater()

    # Base caída o inexistente: ante la duda, modo usuario.
    caida = DBManager()
    caida.db_type = "MariaDB"
    caida.db_engine = create_engine(
        "mysql+pymysql://", connect_args={"read_default_file": CNF,
                                          "database": "no_existe_est_prueba"})
    C.igual(caida.usa_roles_de_acceso(CON_ROLES), True, "base inexistente: modo usuario")
    ok, motivo = caida.verificar_clave_administrador(CON_ROLES, "Secreta1")
    C.check(not ok and "conexión" in motivo, "base inexistente: no desbloquea")
    sin_motor = DBManager()
    C.igual(sin_motor.usa_roles_de_acceso(CON_ROLES), True, "sin conexión: modo usuario")
finally:
    for e in (CON_ROLES, SIN_ROLES, SIN_FILA, SIN_CLAVE, CLAVE_VACIA, CON_ENIE):
        settings.remove(f"empresa_{e}")
    settings.sync()

C.cerrar()
