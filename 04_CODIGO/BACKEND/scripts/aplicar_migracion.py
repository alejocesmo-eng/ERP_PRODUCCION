"""
Aplica una migracion numerada 05_BASE_DATOS/NN_MIGRACION_*.sql, o con --reversion su
NN_REVERSION_*.sql, sobre una base de pruebas existente (sgi_test_* o sgi_sandbox). La base
operativa sgi_db queda siempre excluida: el nombre se valida con _pg_pruebas.validar_nombre antes de conectar.

Credenciales solo por variables de entorno, como el resto de scripts (ADR-005):
SGI_TEST_PG_ADMIN_URL (sin clave) y PGPASSWORD. El script no imprime ni guarda credenciales.

Se conecta directamente a la base pedida, con el host, puerto y usuario de SGI_TEST_PG_ADMIN_URL;
no abre la base de mantenimiento de esa URL. Si la base no existe o rechaza la conexion, lo informa
con el mensaje del servidor, sin host, puerto, usuario ni clave.

En sgi_sandbox, despues de aplicar la migracion ejecuta las verificaciones de preparar_sandbox.

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.aplicar_migracion sgi_test_run 23
    python -m scripts.aplicar_migracion sgi_sandbox 23
    python -m scripts.aplicar_migracion sgi_test_run 25 --reversion
"""
import argparse
import re
from pathlib import Path

import psycopg2

from scripts import preparar_sandbox
from scripts._pg_pruebas import SANDBOX, conectar, fallar, validar_nombre

RUTA_BASE_DATOS = Path(__file__).resolve().parents[3] / "05_BASE_DATOS"
_MIGRACION = re.compile(r"^(\d{2})_MIGRACION_.+\.sql$")
_REVERSION = re.compile(r"^(\d{2})_REVERSION_.+\.sql$")


def ruta_migracion(numero: int, reversion: bool = False) -> Path:
    """La unica NN_MIGRACION_*.sql (o NN_REVERSION_*.sql) con ese numero."""
    tipo, patron = ("REVERSION", _REVERSION) if reversion else ("MIGRACION", _MIGRACION)
    encontradas = [
        ruta for ruta in RUTA_BASE_DATOS.glob(f"*_{tipo}_*.sql")
        if (coincidencia := patron.match(ruta.name)) and int(coincidencia.group(1)) == numero
    ]
    if len(encontradas) != 1:
        fallar(f"Se esperaba una {numero:02d}_{tipo}_*.sql y hay {len(encontradas)}.")
    return encontradas[0]


def motivo_rechazo(error: Exception) -> str:
    """Lo que dice el servidor tras FATAL, sin lo que va entre comillas (usuario, base). El resto del
    mensaje de libpq trae host y puerto: no se muestra."""
    fatal = re.search(r"FATAL:\s*(.+)", str(error))
    texto = fatal.group(1).strip() if fatal else error.__class__.__name__
    return re.sub(r"«[^»]*»|\"[^\"]*\"", "[oculto]", texto)


def conectar_destino(base: str):
    """Conexion a exactamente la base del argumento (ya validada como sgi_test_* o sgi_sandbox)."""
    try:
        return conectar(base)
    except psycopg2.OperationalError as error:
        fallar(f"No se pudo conectar a {base}: {motivo_rechazo(error)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Aplica una migracion numerada sobre sgi_test_* o sgi_sandbox.")
    parser.add_argument("base", help="Base destino: sgi_test_* o sgi_sandbox (nunca sgi_db).")
    parser.add_argument("numero", type=int, help="Numero de la migracion, por ejemplo 23.")
    parser.add_argument("--reversion", action="store_true", help="Aplica NN_REVERSION_*.sql en lugar de la migracion.")
    argumentos = parser.parse_args()
    base = validar_nombre(argumentos.base, permitir_sandbox=True)
    ruta = ruta_migracion(argumentos.numero, argumentos.reversion)

    conexion = conectar_destino(base)
    try:
        try:
            conexion.cursor().execute(ruta.read_text(encoding="utf-8-sig"))
        except Exception as error:
            # Primera linea del error de PostgreSQL (mensaje SQL; libpq no incluye la clave)
            causa = (str(error).strip().splitlines() or [error.__class__.__name__])[0]
            fallar(f"Fallo {ruta.name} en {base}: {causa}")
        print(f"Aplicada en {base}: {ruta.name}")
    finally:
        conexion.close()

    if base == SANDBOX and not argumentos.reversion:
        preparar_sandbox._verificar()


if __name__ == "__main__":
    main()
