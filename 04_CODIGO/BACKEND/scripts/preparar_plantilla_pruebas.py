"""
Construye la plantilla de pruebas sgi_test_template (una sola vez, o con --regenerar
tras un cambio de esquema):

1. Crea la base sgi_test_template.
2. Aplica el esquema (create_all) y carga la semilla con cargar_semilla.cargar_semilla_db().
3. Ejecuta las secciones 1 a 3 de 05_BASE_DATOS/02_DATOS_INICIALES.sql (roles, permisos
   y rol_permisos). Las secciones 4 en adelante no encajan con el esquema de los modelos.
4. Verifica las asignaciones de permisos clave.
5. Marca la base como plantilla (IS_TEMPLATE true).

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.preparar_plantilla_pruebas
    python -m scripts.preparar_plantilla_pruebas --regenerar
"""
import argparse
import os
from pathlib import Path

from psycopg2 import sql

from scripts._pg_pruebas import (
    PLANTILLA,
    conectar,
    conectar_admin,
    existe_base,
    fallar,
    identificador,
    url_base,
)

RUTA_DATOS_INICIALES = Path(__file__).resolve().parents[3] / "05_BASE_DATOS" / "02_DATOS_INICIALES.sql"
MARCA_FIN_PERMISOS = "-- 4. USUARIOS BASE DE PRUEBA"

VERIFICACIONES = (
    ("DISENO tiene PERM_OP_LIBERAR", "DISENO", "PERM_OP_LIBERAR", True),
    ("ALMACEN tiene PERM_ENTREGA_PARCIAL_AUTORIZAR", "ALMACEN", "PERM_ENTREGA_PARCIAL_AUTORIZAR", True),
    ("PRODUCCION no tiene PERM_OP_LIBERAR", "PRODUCCION", "PERM_OP_LIBERAR", False),
)


def _sql_permisos() -> str:
    texto = RUTA_DATOS_INICIALES.read_text(encoding="utf-8-sig")
    if MARCA_FIN_PERMISOS not in texto:
        fallar(f"No se encontro la marca {MARCA_FIN_PERMISOS!r} en {RUTA_DATOS_INICIALES}.")
    return texto.split(MARCA_FIN_PERMISOS, 1)[0]


def _crear_base_vacia(regenerar: bool) -> bool:
    admin = conectar_admin()
    try:
        cur = admin.cursor()
        if existe_base(cur, PLANTILLA):
            if not regenerar:
                print(f"La plantilla {PLANTILLA} ya existe. Use --regenerar para reconstruirla.")
                return False
            cur.execute(sql.SQL("ALTER DATABASE {} IS_TEMPLATE false").format(identificador(PLANTILLA)))
            cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(identificador(PLANTILLA)))
            print(f"Plantilla anterior {PLANTILLA} eliminada.")
        cur.execute(sql.SQL("CREATE DATABASE {}").format(identificador(PLANTILLA)))
        print(f"Base {PLANTILLA} creada.")
        return True
    finally:
        admin.close()


def _cargar_esquema_y_semilla() -> None:
    # load_dotenv() de app.core.config no sobrescribe variables ya definidas:
    # la semilla trabaja sobre la plantilla y nunca sobre la DATABASE_URL del .env.
    os.environ["DATABASE_URL"] = url_base(PLANTILLA)
    import cargar_semilla
    from app.db.database import engine

    try:
        cargar_semilla.cargar_semilla_db()
    finally:
        engine.dispose()


def _cargar_permisos_y_verificar() -> bool:
    conexion = conectar(PLANTILLA)
    try:
        cur = conexion.cursor()
        cur.execute(_sql_permisos())
        print("Secciones 1 a 3 de 02_DATOS_INICIALES.sql aplicadas (roles, permisos y rol_permisos).")
        correcto = True
        for descripcion, rol, permiso, esperado in VERIFICACIONES:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM rol_permisos WHERE id_rol = %s AND id_permiso = %s)",
                (rol, permiso),
            )
            ok = cur.fetchone()[0] is esperado
            correcto = correcto and ok
            print(f"  [{'OK' if ok else 'FALLA'}] {descripcion}")
        return correcto
    finally:
        conexion.close()


def _marcar_plantilla() -> None:
    admin = conectar_admin()
    try:
        admin.cursor().execute(sql.SQL("ALTER DATABASE {} IS_TEMPLATE true").format(identificador(PLANTILLA)))
        print(f"{PLANTILLA} marcada como plantilla (IS_TEMPLATE true).")
    finally:
        admin.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Prepara la plantilla de pruebas {PLANTILLA}.")
    parser.add_argument("--regenerar", action="store_true", help="Elimina y reconstruye la plantilla existente.")
    args = parser.parse_args()

    if not _crear_base_vacia(args.regenerar):
        return
    _cargar_esquema_y_semilla()
    if not _cargar_permisos_y_verificar():
        fallar(f"Verificacion de permisos fallida: {PLANTILLA} no se marco como plantilla. Corrija y use --regenerar.")
    _marcar_plantilla()


if __name__ == "__main__":
    main()
