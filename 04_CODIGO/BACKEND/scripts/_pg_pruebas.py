"""
Utilidades comunes para la base de pruebas PostgreSQL (plantilla + copias desechables).

Credenciales solo por variables de entorno (ADR-005):
- SGI_TEST_PG_ADMIN_URL: conexion de administracion SIN clave, por ejemplo
  postgresql://usuario_bd_local@localhost:5432/postgres. El usuario necesita CREATEDB.
- PGPASSWORD: clave de ese usuario; la leen libpq y psycopg2 sin que aparezca en ninguna URL.

Solo se opera sobre bases cuyo nombre empieza por sgi_test_, y sobre sgi_sandbox cuando el
llamador lo pide de forma explicita (preparar_sandbox). La base operativa sgi_db queda
siempre excluida.
"""
import os
import re
import sys

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url

PLANTILLA = "sgi_test_template"
COPIA_POR_DEFECTO = "sgi_test_copia"
BASE_OPERATIVA = "sgi_db"
# Base local para pruebas manuales de la aplicacion; sin prefijo sgi_test_, por lo que el
# conftest no la acepta como base de pruebas automaticas
SANDBOX = "sgi_sandbox"
_NOMBRE_VALIDO = re.compile(r"^sgi_test_[a-z0-9_]+$")


def fallar(mensaje: str) -> None:
    print(f"ERROR: {mensaje}", file=sys.stderr)
    sys.exit(1)


def url_admin():
    valor = os.environ.get("SGI_TEST_PG_ADMIN_URL")
    if not valor:
        fallar(
            "Falta la variable de entorno SGI_TEST_PG_ADMIN_URL "
            "(ejemplo: postgresql://usuario_bd_local@localhost:5432/postgres). "
            "La clave va en PGPASSWORD."
        )
    url = make_url(valor)
    if url.password:
        fallar("SGI_TEST_PG_ADMIN_URL no debe incluir la clave. Defina PGPASSWORD en la sesion.")
    if (url.database or "").lower() == BASE_OPERATIVA:
        fallar(f"SGI_TEST_PG_ADMIN_URL apunta a {BASE_OPERATIVA} (base operativa). Use la base de mantenimiento postgres.")
    return url


def validar_nombre(nombre: str, permitir_plantilla: bool = False, permitir_sandbox: bool = False) -> str:
    if nombre.lower() == BASE_OPERATIVA:
        fallar(f"{BASE_OPERATIVA} es la base operativa: operacion rechazada.")
    if permitir_sandbox and nombre == SANDBOX:
        return nombre
    if not _NOMBRE_VALIDO.match(nombre):
        fallar(f"Nombre de base no permitido: {nombre!r}. Debe empezar por sgi_test_ y usar solo [a-z0-9_].")
    if nombre == PLANTILLA and not permitir_plantilla:
        fallar(f"{PLANTILLA} es la plantilla; regenerela con preparar_plantilla_pruebas --regenerar.")
    return nombre


def conectar(base: str):
    """Conexion psycopg2 en autocommit; la clave la toma libpq de PGPASSWORD."""
    url = url_admin()
    if base != (url.database or "postgres"):
        validar_nombre(base, permitir_plantilla=True, permitir_sandbox=True)
    conexion = psycopg2.connect(
        host=url.host or "localhost",
        port=url.port or 5432,
        user=url.username,
        dbname=base,
    )
    conexion.autocommit = True
    return conexion


def conectar_admin():
    url = url_admin()
    return conectar(url.database or "postgres")


def url_base(nombre: str) -> str:
    """URL SQLAlchemy sin clave para DATABASE_URL o SGI_TEST_PG_URL."""
    url = url_admin().set(drivername="postgresql", database=nombre)
    return url.render_as_string(hide_password=False)


def existe_base(cursor, nombre: str) -> bool:
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nombre,))
    return cursor.fetchone() is not None


def sesiones_activas(cursor, nombre: str) -> int:
    cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = %s", (nombre,))
    return cursor.fetchone()[0]


def identificador(nombre: str):
    return sql.Identifier(nombre)
