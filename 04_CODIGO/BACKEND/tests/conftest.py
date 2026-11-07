import sys
import os

import pytest
from sqlalchemy.engine import make_url

# OT-2026-001 (RK-1, decisión G2-5): variables obligatorias para las pruebas marcadas pg.
# Las pruebas no leen DATABASE_URL del .env: la base de pruebas sale solo de SGI_TEST_PG_URL.
# Si falta o no apunta a una base sgi_test_*, cada prueba pg falla con el motivo (no se omite)
# y DATABASE_URL queda en una base inexistente. No hay respaldo a sgi_db ni a SQLite.
# Los mensajes nunca muestran la URL ni la contraseña.
VARIABLE_URL_PRUEBAS = "SGI_TEST_PG_URL"
PREFIJO_BD_PRUEBAS = "sgi_test_"
URL_SIN_BASE_PRUEBAS = "postgresql://sin-base-pruebas.invalid/sgi_test_sin_definir"
_error_base_pruebas = None


def _url_base_pruebas() -> str:
    url = os.environ.get(VARIABLE_URL_PRUEBAS)
    if not url:
        raise pytest.UsageError(
            f"Falta la variable de entorno {VARIABLE_URL_PRUEBAS}. Defínala con la URL de la "
            f"base PostgreSQL de pruebas ({PREFIJO_BD_PRUEBAS}*) antes de ejecutar la suite."
        )
    try:
        nombre_bd = make_url(url).database or ""
    except Exception:
        raise pytest.UsageError(
            f"La variable {VARIABLE_URL_PRUEBAS} no contiene una URL de base de datos válida."
        ) from None
    if not nombre_bd.startswith(PREFIJO_BD_PRUEBAS):
        raise pytest.UsageError(
            f"La variable {VARIABLE_URL_PRUEBAS} no apunta a una base {PREFIJO_BD_PRUEBAS}*. "
            "Se aborta la suite para no tocar una base que no es de pruebas."
        )
    return url


def pytest_configure(config):
    global _error_base_pruebas
    try:
        url = _url_base_pruebas()
    except pytest.UsageError as error:
        _error_base_pruebas = str(error)
        url = URL_SIN_BASE_PRUEBAS
    # Se asigna (no setdefault) para que el load_dotenv() de app.core.config no imponga el .env:
    # load_dotenv no sobrescribe variables ya presentes en el entorno.
    os.environ["DATABASE_URL"] = url
    os.environ.setdefault("SECRET_KEY", "clave_solo_para_pruebas_sesion_no_usar_en_produccion")
    os.environ.setdefault("JWT_SECRET_KEY_PLANOS", "clave_solo_para_pruebas_planos_no_usar_en_produccion")


def pytest_runtest_setup(item):
    if _error_base_pruebas and item.get_closest_marker("pg"):
        pytest.fail(f"Prueba pg sin base de pruebas: {_error_base_pruebas}", pytrace=False)


# Asegurar que el directorio de la aplicación backend esté en sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
