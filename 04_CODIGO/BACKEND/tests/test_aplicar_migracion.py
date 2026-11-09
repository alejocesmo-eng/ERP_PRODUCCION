# tests/test_aplicar_migracion.py
"""
scripts.aplicar_migracion sin base real: rechaza sgi_db antes de conectar, encuentra la
migración 23 y preparar_sandbox la incluye y la verifica.
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
