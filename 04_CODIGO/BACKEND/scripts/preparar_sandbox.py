"""
Prepara la base local sgi_sandbox para pruebas manuales de la aplicacion:

1. Crea sgi_sandbox desde la plantilla sgi_test_template (CREATE DATABASE ... TEMPLATE).
2. Aplica en orden las migraciones 05_BASE_DATOS/NN_MIGRACION_*.sql desde la 17. La plantilla
   se construye con create_all, que no instala triggers, extensiones, funciones ni indices
   de expresion (migraciones 21 y 22), y puede ser anterior a los modelos de 18 a 21.
   Todas son idempotentes.
3. Verifica el trigger del historial de planos, las extensiones pg_trgm y unaccent y la
   funcion sgi_normalizar.

Credenciales solo por variables de entorno, como el resto de scripts (ADR-005):
SGI_TEST_PG_ADMIN_URL (sin clave) y PGPASSWORD. El script no imprime ni guarda credenciales.

Si sgi_sandbox ya existe se detiene; con --regenerar la elimina y la vuelve a crear despues
de pedir confirmacion escribiendo su nombre.

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.preparar_sandbox
    python -m scripts.preparar_sandbox --regenerar
"""
import argparse
import re
import sys
from pathlib import Path

from psycopg2 import errors, sql

from scripts._pg_pruebas import (
    PLANTILLA,
    SANDBOX,
    conectar,
    conectar_admin,
    existe_base,
    fallar,
    identificador,
    sesiones_activas,
    validar_nombre,
)

RUTA_BASE_DATOS = Path(__file__).resolve().parents[3] / "05_BASE_DATOS"
PRIMERA_MIGRACION = 17
_MIGRACION = re.compile(r"^(\d{2})_MIGRACION_.+\.sql$")

VERIFICACIONES = (
    (
        "Trigger append-only del historial de planos (migracion 21)",
        "SELECT 1 FROM pg_trigger WHERE tgname = 'trg_planos_historial_inmutable'",
    ),
    ("Extension pg_trgm (migracion 22)", "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"),
    ("Extension unaccent (migracion 22)", "SELECT 1 FROM pg_extension WHERE extname = 'unaccent'"),
    ("Funcion sgi_normalizar (migracion 22)", "SELECT 1 FROM pg_proc WHERE proname = 'sgi_normalizar'"),
)


def migraciones_sandbox() -> list[Path]:
    """Migraciones NN_MIGRACION_*.sql desde la 17, en orden numerico."""
    encontradas = []
    for ruta in RUTA_BASE_DATOS.glob("*_MIGRACION_*.sql"):
        coincidencia = _MIGRACION.match(ruta.name)
        if coincidencia and int(coincidencia.group(1)) >= PRIMERA_MIGRACION:
            encontradas.append((int(coincidencia.group(1)), ruta))
    return [ruta for _, ruta in sorted(encontradas)]


def confirmar_regeneracion(leer=input) -> bool:
    """Pide escribir el nombre de la base; cualquier otra respuesta cancela."""
    if leer is input and not sys.stdin.isatty():
        fallar("--regenerar necesita confirmacion interactiva: ejecute el script desde una terminal.")
    respuesta = leer(f"Se eliminara {SANDBOX} y todos sus datos. Escriba {SANDBOX} para confirmar: ")
    return respuesta.strip() == SANDBOX


def _crear_sandbox(regenerar: bool) -> None:
    admin = conectar_admin()
    try:
        cur = admin.cursor()
        if not existe_base(cur, PLANTILLA):
            fallar(f"No existe la plantilla {PLANTILLA}. Ejecute: python -m scripts.preparar_plantilla_pruebas")
        if existe_base(cur, SANDBOX):
            if not regenerar:
                fallar(f"La base {SANDBOX} ya existe. Use --regenerar para eliminarla y crearla de nuevo.")
            if not confirmar_regeneracion():
                fallar("Regeneracion cancelada: no se modifico nada.")
            activas = sesiones_activas(cur, SANDBOX)
            if activas:
                fallar(
                    f"{SANDBOX} tiene {activas} conexion(es) activa(s). Detenga el backend y cierre "
                    "psql o pgAdmin sobre esa base antes de regenerarla."
                )
            cur.execute(sql.SQL("DROP DATABASE {}").format(identificador(SANDBOX)))
            print(f"Base {SANDBOX} eliminada.")
        try:
            cur.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(identificador(SANDBOX), identificador(PLANTILLA)))
        except errors.ObjectInUse:
            fallar(
                f"No se puede copiar {PLANTILLA}: tiene {sesiones_activas(cur, PLANTILLA)} conexion(es) activa(s). "
                "Cierre las sesiones abiertas sobre la plantilla y reintente."
            )
        print(f"Base {SANDBOX} creada desde {PLANTILLA}.")
    finally:
        admin.close()


def _aplicar_migraciones() -> None:
    conexion = conectar(SANDBOX)
    try:
        cur = conexion.cursor()
        for ruta in migraciones_sandbox():
            try:
                cur.execute(ruta.read_text(encoding="utf-8-sig"))
            except Exception as error:
                # Primera linea del error de PostgreSQL (mensaje SQL; libpq no incluye la clave)
                causa = (str(error).strip().splitlines() or [error.__class__.__name__])[0]
                fallar(
                    f"Fallo la migracion {ruta.name}: {causa}. {SANDBOX} quedo a medio migrar; "
                    "corrija la causa y vuelva a crearla con --regenerar."
                )
            print(f"Migracion aplicada: {ruta.name}")
    finally:
        conexion.close()


def _verificar() -> None:
    conexion = conectar(SANDBOX)
    try:
        cur = conexion.cursor()
        faltantes = []
        for descripcion, consulta in VERIFICACIONES:
            cur.execute(consulta)
            if cur.fetchone() is None:
                faltantes.append(descripcion)
        if faltantes:
            fallar("Verificacion incompleta en sgi_sandbox: " + "; ".join(faltantes))
        print("Verificacion correcta: historial append-only y busqueda de productos instalados.")
    finally:
        conexion.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Prepara {SANDBOX} desde {PLANTILLA} con las migraciones recientes.")
    parser.add_argument("--regenerar", action="store_true", help=f"Elimina {SANDBOX} (con confirmacion) y la crea de nuevo.")
    regenerar = parser.parse_args().regenerar
    validar_nombre(SANDBOX, permitir_sandbox=True)

    _crear_sandbox(regenerar)
    _aplicar_migraciones()
    _verificar()
    print(
        f"{SANDBOX} lista. Para el backend use como DATABASE_URL la conexion de SGI_TEST_PG_ADMIN_URL "
        f"con la base {SANDBOX}; la clave sigue solo en PGPASSWORD."
    )


if __name__ == "__main__":
    main()
