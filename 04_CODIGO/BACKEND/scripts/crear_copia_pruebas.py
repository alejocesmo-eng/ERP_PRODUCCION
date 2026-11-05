"""
Crea una base de trabajo nueva a partir de la plantilla sgi_test_template e imprime
la URL para DATABASE_URL (y SGI_TEST_PG_URL). La URL no lleva clave: se usa PGPASSWORD.

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.crear_copia_pruebas                # crea sgi_test_copia
    python -m scripts.crear_copia_pruebas sgi_test_mio   # nombre propio (prefijo sgi_test_)
"""
import argparse

from psycopg2 import errors, sql

from scripts._pg_pruebas import (
    COPIA_POR_DEFECTO,
    PLANTILLA,
    conectar_admin,
    existe_base,
    fallar,
    identificador,
    sesiones_activas,
    url_base,
    validar_nombre,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Crea una copia de pruebas desde {PLANTILLA}.")
    parser.add_argument("nombre", nargs="?", default=COPIA_POR_DEFECTO, help=f"Nombre de la copia (por defecto {COPIA_POR_DEFECTO}).")
    nombre = validar_nombre(parser.parse_args().nombre)

    admin = conectar_admin()
    try:
        cur = admin.cursor()
        if not existe_base(cur, PLANTILLA):
            fallar(f"No existe la plantilla {PLANTILLA}. Ejecute: python -m scripts.preparar_plantilla_pruebas")
        if existe_base(cur, nombre):
            fallar(f"La base {nombre} ya existe. Descartela con: python -m scripts.descartar_copia_pruebas {nombre}")
        try:
            cur.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(identificador(nombre), identificador(PLANTILLA)))
        except errors.ObjectInUse:
            fallar(
                f"No se puede copiar {PLANTILLA}: tiene {sesiones_activas(cur, PLANTILLA)} conexion(es) activa(s). "
                "Cierre las sesiones abiertas sobre la plantilla (psql, pgAdmin, backend o pruebas) y reintente."
            )
    finally:
        admin.close()

    url = url_base(nombre)
    print(f"Copia {nombre} creada desde {PLANTILLA}.")
    print(f"DATABASE_URL={url}")
    print(f"SGI_TEST_PG_URL={url}")


if __name__ == "__main__":
    main()
