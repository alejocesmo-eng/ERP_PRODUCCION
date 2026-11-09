"""
Aplica una migracion numerada 05_BASE_DATOS/NN_MIGRACION_*.sql sobre una base de pruebas
existente (sgi_test_* o sgi_sandbox). La base operativa sgi_db queda siempre excluida: el
nombre se valida con _pg_pruebas.validar_nombre antes de conectar.

Credenciales solo por variables de entorno, como el resto de scripts (ADR-005):
SGI_TEST_PG_ADMIN_URL (sin clave) y PGPASSWORD. El script no imprime ni guarda credenciales.

En sgi_sandbox, despues de aplicar la migracion ejecuta las verificaciones de preparar_sandbox.

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.aplicar_migracion sgi_test_run 23
    python -m scripts.aplicar_migracion sgi_sandbox 23
"""
import argparse
import re
from pathlib import Path

from scripts import preparar_sandbox
from scripts._pg_pruebas import SANDBOX, conectar, conectar_admin, existe_base, fallar, validar_nombre

RUTA_BASE_DATOS = Path(__file__).resolve().parents[3] / "05_BASE_DATOS"
_MIGRACION = re.compile(r"^(\d{2})_MIGRACION_.+\.sql$")


def ruta_migracion(numero: int) -> Path:
    """La unica NN_MIGRACION_*.sql con ese numero."""
    encontradas = [
        ruta for ruta in RUTA_BASE_DATOS.glob("*_MIGRACION_*.sql")
        if (coincidencia := _MIGRACION.match(ruta.name)) and int(coincidencia.group(1)) == numero
    ]
    if len(encontradas) != 1:
        fallar(f"Se esperaba una migracion {numero:02d}_MIGRACION_*.sql y hay {len(encontradas)}.")
    return encontradas[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Aplica una migracion numerada sobre sgi_test_* o sgi_sandbox.")
    parser.add_argument("base", help="Base destino: sgi_test_* o sgi_sandbox (nunca sgi_db).")
    parser.add_argument("numero", type=int, help="Numero de la migracion, por ejemplo 23.")
    argumentos = parser.parse_args()
    base = validar_nombre(argumentos.base, permitir_sandbox=True)
    ruta = ruta_migracion(argumentos.numero)

    admin = conectar_admin()
    try:
        if not existe_base(admin.cursor(), base):
            fallar(f"No existe la base {base}.")
    finally:
        admin.close()

    conexion = conectar(base)
    try:
        try:
            conexion.cursor().execute(ruta.read_text(encoding="utf-8-sig"))
        except Exception as error:
            # Primera linea del error de PostgreSQL (mensaje SQL; libpq no incluye la clave)
            causa = (str(error).strip().splitlines() or [error.__class__.__name__])[0]
            fallar(f"Fallo la migracion {ruta.name} en {base}: {causa}")
        print(f"Migracion aplicada en {base}: {ruta.name}")
    finally:
        conexion.close()

    if base == SANDBOX:
        preparar_sandbox._verificar()


if __name__ == "__main__":
    main()
