# tests/test_aplicar_migracion.py
"""
scripts.aplicar_migracion sin base real: rechaza sgi_db antes de conectar, se conecta exactamente a
la base del argumento (no a la base de mantenimiento de SGI_TEST_PG_ADMIN_URL), no acepta una URL de
administración con clave, no muestra datos de conexión al fallar, encuentra las migraciones y la
reversión 25, y preparar_sandbox las incluye y las verifica.
"""
import sys

import psycopg2
import pytest

from scripts import _pg_pruebas, aplicar_migracion, preparar_sandbox


def test_rechaza_sgi_db_sin_conectar(monkeypatch):
    monkeypatch.setattr(aplicar_migracion, "conectar", lambda base: pytest.fail("No debe conectar"))
    monkeypatch.setattr(sys, "argv", ["aplicar_migracion", "sgi_db", "23"])

    with pytest.raises(SystemExit):
        aplicar_migracion.main()


def test_encuentra_la_migracion_23():
    assert aplicar_migracion.ruta_migracion(23).name == "23_MIGRACION_COTIZACION_ESTADO_EMITIDA.sql"


def test_numero_sin_migracion_falla():
    with pytest.raises(SystemExit):
        aplicar_migracion.ruta_migracion(99)


def test_el_sandbox_aplica_y_verifica_la_migracion_23():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert "23_MIGRACION_COTIZACION_ESTADO_EMITIDA.sql" in nombres
    assert any("migracion 23" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_24():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(24).name == "24_MIGRACION_SOCIOS_CODIGO_NIT.sql"
    assert "24_MIGRACION_SOCIOS_CODIGO_NIT.sql" in nombres
    assert any("migracion 24" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_25():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(25).name == "25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql"
    assert "25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql" in nombres
    assert any("migracion 25" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_26():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(26).name == "26_MIGRACION_COTIZACION_FORMATO.sql"
    assert aplicar_migracion.ruta_migracion(26, reversion=True).name == "26_REVERSION_COTIZACION_FORMATO.sql"
    assert "26_MIGRACION_COTIZACION_FORMATO.sql" in nombres
    assert any("migracion 26" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_27():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(27).name == "27_MIGRACION_ROL_LIDER_MECANIZADOS.sql"
    assert aplicar_migracion.ruta_migracion(27, reversion=True).name == "27_REVERSION_ROL_LIDER_MECANIZADOS.sql"
    # Después de la 25, que crea LIDER_PRODUCCION
    assert nombres.index("27_MIGRACION_ROL_LIDER_MECANIZADOS.sql") > nombres.index("25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql")
    assert any("migracion 27" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_28():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(28).name == "28_MIGRACION_OP_UNIDAD_ACTUAL.sql"
    assert aplicar_migracion.ruta_migracion(28, reversion=True).name == "28_REVERSION_OP_UNIDAD_ACTUAL.sql"
    assert "28_MIGRACION_OP_UNIDAD_ACTUAL.sql" in nombres
    assert any("migracion 28" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_29():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(29).name == "29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql"
    assert aplicar_migracion.ruta_migracion(29, reversion=True).name == "29_REVERSION_ROL_CAPTURISTA_TIEMPOS.sql"
    assert "29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql" in nombres
    assert any("migracion 29" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_30():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(30).name == "30_MIGRACION_TIEMPOS_LIDER_MECANIZADOS.sql"
    assert aplicar_migracion.ruta_migracion(30, reversion=True).name == "30_REVERSION_TIEMPOS_LIDER_MECANIZADOS.sql"
    assert "30_MIGRACION_TIEMPOS_LIDER_MECANIZADOS.sql" in nombres
    assert any("migracion 30" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_31():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(31).name == "31_MIGRACION_CONFIGURACION_ROLES.sql"
    assert aplicar_migracion.ruta_migracion(31, reversion=True).name == "31_REVERSION_CONFIGURACION_ROLES.sql"
    assert "31_MIGRACION_CONFIGURACION_ROLES.sql" in nombres
    assert any("migracion 31" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_32():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(32).name == "32_MIGRACION_ROL_LIDER_SERVICIOS.sql"
    assert aplicar_migracion.ruta_migracion(32, reversion=True).name == "32_REVERSION_ROL_LIDER_SERVICIOS.sql"
    assert "32_MIGRACION_ROL_LIDER_SERVICIOS.sql" in nombres
    assert any("migracion 32" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_33():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(33).name == "33_MIGRACION_CARGA_TIEMPOS_MANUAL.sql"
    assert aplicar_migracion.ruta_migracion(33, reversion=True).name == "33_REVERSION_CARGA_TIEMPOS_MANUAL.sql"
    assert "33_MIGRACION_CARGA_TIEMPOS_MANUAL.sql" in nombres
    assert any("migracion 33" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_34():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(34).name == "34_MIGRACION_ACCESO_POR_USUARIO.sql"
    assert aplicar_migracion.ruta_migracion(34, reversion=True).name == "34_REVERSION_ACCESO_POR_USUARIO.sql"
    assert "34_MIGRACION_ACCESO_POR_USUARIO.sql" in nombres
    assert any("migracion 34" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_el_sandbox_aplica_y_verifica_la_migracion_35():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    assert aplicar_migracion.ruta_migracion(35).name == "35_MIGRACION_CANTIDAD_APROBADA_CALIDAD.sql"
    assert aplicar_migracion.ruta_migracion(35, reversion=True).name == "35_REVERSION_CANTIDAD_APROBADA_CALIDAD.sql"
    assert nombres[-1] == "35_MIGRACION_CANTIDAD_APROBADA_CALIDAD.sql"
    assert any("migracion 35" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


def test_encuentra_la_reversion_25():
    assert aplicar_migracion.ruta_migracion(25, reversion=True).name == "25_REVERSION_ROLES_PERMISOS_POR_ROL.sql"


def test_la_reversion_no_verifica_el_sandbox(monkeypatch):
    """Tras revertir, las verificaciones de las migraciones fallarían: no se ejecutan."""
    ejecutado = []

    class Cursor:
        def execute(self, consulta, *parametros):
            ejecutado.append(consulta)

        def fetchone(self):
            return (1,)

    class Conexion:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(aplicar_migracion, "conectar", lambda base: Conexion())
    monkeypatch.setattr(aplicar_migracion.preparar_sandbox, "_verificar", lambda: pytest.fail("No debe verificar"))
    monkeypatch.setattr(sys, "argv", ["aplicar_migracion", "sgi_sandbox", "25", "--reversion"])

    aplicar_migracion.main()

    assert any("25_REVERSION_ROLES_PERMISOS_POR_ROL.sql" in consulta for consulta in ejecutado)


class _Conexion:
    def __init__(self):
        self.ejecutado = []

    def cursor(self):
        conexion = self

        class Cursor:
            def execute(self, consulta, *parametros):
                conexion.ejecutado.append(consulta)

        return Cursor()

    def close(self):
        pass


def test_se_conecta_a_la_base_del_argumento_aunque_la_url_de_administracion_tenga_otra(monkeypatch):
    # La base de mantenimiento de la URL no existe ("postgre"): no debe abrirse
    monkeypatch.setenv("SGI_TEST_PG_ADMIN_URL", "postgresql://usuario_prueba@localhost:5432/postgre")
    pedidas = []

    def connect(**datos):
        pedidas.append(datos["dbname"])
        return _Conexion()

    monkeypatch.setattr(_pg_pruebas.psycopg2, "connect", connect)
    monkeypatch.setattr(sys, "argv", ["aplicar_migracion", "sgi_test_run", "27"])

    aplicar_migracion.main()

    assert pedidas == ["sgi_test_run"]


def test_la_url_de_administracion_con_clave_se_rechaza_sin_conectar(monkeypatch, capsys):
    monkeypatch.setenv("SGI_TEST_PG_ADMIN_URL", "postgresql://usuario_prueba:clave_prueba@localhost:5432/postgres")
    monkeypatch.setattr(_pg_pruebas.psycopg2, "connect", lambda **datos: pytest.fail("No debe conectar"))
    monkeypatch.setattr(sys, "argv", ["aplicar_migracion", "sgi_test_run", "27"])

    with pytest.raises(SystemExit):
        aplicar_migracion.main()

    error = capsys.readouterr().err
    assert "no debe incluir la clave" in error and "clave_prueba" not in error


def test_si_la_base_no_existe_lo_dice_sin_datos_de_conexion(monkeypatch, capsys):
    monkeypatch.setenv("SGI_TEST_PG_ADMIN_URL", "postgresql://usuario_prueba@servidor-prueba:6543/postgres")

    def connect(**datos):
        raise psycopg2.OperationalError(
            'connection to server at "servidor-prueba" (10.0.0.9), port 6543 failed: '
            'FATAL:  database "sgi_test_run" does not exist'
        )

    monkeypatch.setattr(_pg_pruebas.psycopg2, "connect", connect)
    monkeypatch.setattr(sys, "argv", ["aplicar_migracion", "sgi_test_run", "27"])

    with pytest.raises(SystemExit):
        aplicar_migracion.main()

    error = capsys.readouterr().err
    assert "No se pudo conectar a sgi_test_run: database [oculto] does not exist" in error
    assert not any(dato in error for dato in ("servidor-prueba", "10.0.0.9", "6543", "usuario_prueba"))
