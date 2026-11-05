# tests/test_config_variables_obligatorias.py
"""
OT-2026-001 / ADR-005 — CA-10: variables de entorno obligatorias sin valor por defecto.

Cada caso se ejecuta en un subproceso de Python aislado para no alterar los módulos
ya importados por el resto de la suite (app.core.config y app.api.v1.planos se evalúan
al importarse). Dentro del subproceso se anula dotenv.load_dotenv para que el .env local
no influya: solo cuentan las variables que el caso define. Datos ficticios únicamente.
"""
import os
import subprocess
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VARIABLES = ("DATABASE_URL", "SECRET_KEY", "JWT_SECRET_KEY_PLANOS")
VALORES_FICTICIOS = {
    "DATABASE_URL": "sqlite://",
    "SECRET_KEY": "clave_solo_para_pruebas_sesion_ca10",
    "JWT_SECRET_KEY_PLANOS": "clave_solo_para_pruebas_planos_ca10",
}


def _importar_en_subproceso(modulo: str, variables: dict) -> subprocess.CompletedProcess:
    entorno = {k: v for k, v in os.environ.items() if k not in VARIABLES}
    entorno.update(variables)
    codigo = (
        "import dotenv; dotenv.load_dotenv = lambda *a, **k: False\n"
        f"import {modulo}\n"
        "print('IMPORT_OK')\n"
    )
    return subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=BACKEND_DIR,
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def _sin(nombre: str) -> dict:
    return {k: v for k, v in VALORES_FICTICIOS.items() if k != nombre}


def _con_vacia(nombre: str) -> dict:
    variables = dict(VALORES_FICTICIOS)
    variables[nombre] = ""
    return variables


@pytest.mark.parametrize(
    "modulo, variables, faltante",
    [
        ("app.core.config", {}, "DATABASE_URL"),
        ("app.core.config", _sin("DATABASE_URL"), "DATABASE_URL"),
        ("app.core.config", _con_vacia("DATABASE_URL"), "DATABASE_URL"),
        ("app.core.config", _sin("SECRET_KEY"), "SECRET_KEY"),
        ("app.core.config", _con_vacia("SECRET_KEY"), "SECRET_KEY"),
        ("app.api.v1.planos", _sin("JWT_SECRET_KEY_PLANOS"), "JWT_SECRET_KEY_PLANOS"),
        ("app.api.v1.planos", _con_vacia("JWT_SECRET_KEY_PLANOS"), "JWT_SECRET_KEY_PLANOS"),
    ],
    ids=[
        "config_sin_ninguna",
        "config_sin_database_url",
        "config_database_url_vacia",
        "config_sin_secret_key",
        "config_secret_key_vacia",
        "planos_sin_jwt_planos",
        "planos_jwt_planos_vacia",
    ],
)
def test_arranque_falla_y_nombra_la_variable_faltante(modulo, variables, faltante):
    resultado = _importar_en_subproceso(modulo, variables)

    assert resultado.returncode != 0, "El módulo no debe importarse sin la variable obligatoria"
    assert "IMPORT_OK" not in resultado.stdout
    assert "RuntimeError" in resultado.stderr
    assert f"Falta la variable de entorno obligatoria {faltante}" in resultado.stderr
    # El mensaje no debe exponer ningún valor de las demás variables definidas.
    for nombre, valor in variables.items():
        if valor and nombre != faltante:
            assert valor not in resultado.stderr


def test_arranque_correcto_con_las_tres_variables_definidas():
    resultado = _importar_en_subproceso("app.main", VALORES_FICTICIOS)

    assert resultado.returncode == 0, resultado.stderr[-2000:]
    assert "IMPORT_OK" in resultado.stdout
