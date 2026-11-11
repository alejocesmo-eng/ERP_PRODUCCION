# tests/test_aplicar_migracion.py
"""
scripts.aplicar_migracion sin base real: rechaza sgi_db antes de conectar, encuentra las
migraciones y la reversión 25, y preparar_sandbox las incluye y las verifica.
"""
import sys

import pytest

from scripts import aplicar_migracion, preparar_sandbox


def test_rechaza_sgi_db_sin_conectar(monkeypatch):
    monkeypatch.setattr(aplicar_migracion, "conectar_admin", lambda: pytest.fail("No debe conectar"))
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
    assert nombres[-1] == "25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql"
    assert any("migracion 25" in descripcion for descripcion, _ in preparar_sandbox.VERIFICACIONES)


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

    monkeypatch.setattr(aplicar_migracion, "conectar_admin", Conexion)
    monkeypatch.setattr(aplicar_migracion, "conectar", lambda base: Conexion())
    monkeypatch.setattr(aplicar_migracion.preparar_sandbox, "_verificar", lambda: pytest.fail("No debe verificar"))
    monkeypatch.setattr(sys, "argv", ["aplicar_migracion", "sgi_sandbox", "25", "--reversion"])

    aplicar_migracion.main()

    assert any("25_REVERSION_ROLES_PERMISOS_POR_ROL.sql" in consulta for consulta in ejecutado)
