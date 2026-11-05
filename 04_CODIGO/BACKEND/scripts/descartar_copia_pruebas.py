"""
Elimina una copia de pruebas creada con crear_copia_pruebas. Cierra las sesiones que
sigan abiertas sobre ella. Nunca elimina la plantilla ni bases sin prefijo sgi_test_.

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.descartar_copia_pruebas                # descarta sgi_test_copia
    python -m scripts.descartar_copia_pruebas sgi_test_mio
"""
import argparse

from psycopg2 import sql

from scripts._pg_pruebas import (
    COPIA_POR_DEFECTO,
    conectar_admin,
    existe_base,
    identificador,
    validar_nombre,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Elimina una copia de pruebas sgi_test_*.")
    parser.add_argument("nombre", nargs="?", default=COPIA_POR_DEFECTO, help=f"Nombre de la copia (por defecto {COPIA_POR_DEFECTO}).")
    nombre = validar_nombre(parser.parse_args().nombre)

    admin = conectar_admin()
    try:
        cur = admin.cursor()
        if not existe_base(cur, nombre):
            print(f"La base {nombre} no existe; nada que descartar.")
            return
        cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(identificador(nombre)))
        print(f"Copia {nombre} eliminada.")
    finally:
        admin.close()


if __name__ == "__main__":
    main()
