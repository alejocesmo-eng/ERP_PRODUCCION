"""
Cuenta roles, permisos y usuarios por rol en una base de pruebas (sgi_test_* o sgi_sandbox),
para comparar antes y después de 25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql y de su reversión.
Solo lee: no cambia nada. La base operativa sgi_db queda excluida (_pg_pruebas.validar_nombre).

Credenciales solo por variables de entorno, como el resto de scripts (ADR-005):
SGI_TEST_PG_ADMIN_URL (sin clave) y PGPASSWORD. El script no imprime ni guarda credenciales.

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.contar_roles_permisos sgi_test_run
"""
import argparse

from app.core.roles import ROLES_ANTERIORES, ROLES_CATALOGO
from scripts._pg_pruebas import conectar, conectar_admin, existe_base, fallar, validar_nombre

CONSULTA_ROLES = """
SELECT r.id_rol,
       (SELECT count(*) FROM usuarios u WHERE u.id_rol = r.id_rol) AS usuarios,
       (SELECT count(*) FROM usuarios u WHERE u.id_rol = r.id_rol AND u.activo) AS activos,
       (SELECT string_agg(rp.id_permiso, ', ' ORDER BY rp.id_permiso)
          FROM rol_permisos rp WHERE rp.id_rol = r.id_rol) AS permisos
  FROM roles r
 ORDER BY r.id_rol
"""


def _origen(id_rol: str) -> str:
    if id_rol in ROLES_CATALOGO:
        return "catalogo"
    if id_rol in ROLES_ANTERIORES:
        return "anterior"
    return "fuera"


def contar(cur) -> dict:
    """Totales y filas por rol: (id_rol, origen, usuarios, activos, permisos)."""
    cur.execute(CONSULTA_ROLES)
    filas = [(id_rol, _origen(id_rol), usuarios, activos, permisos or "") for id_rol, usuarios, activos, permisos in cur.fetchall()]
    cur.execute("SELECT count(*) FROM permisos")
    permisos = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM rol_permisos")
    asignaciones = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM usuarios WHERE id_rol IS NULL")
    sin_rol = cur.fetchone()[0]
    cur.execute("SELECT to_regclass('public.migracion_25_registro') IS NOT NULL")
    registro = None
    if cur.fetchone()[0]:
        cur.execute("SELECT tipo, count(*) FROM migracion_25_registro GROUP BY tipo ORDER BY tipo")
        registro = dict(cur.fetchall())
    return {
        "filas": filas,
        "roles": len(filas),
        "permisos": permisos,
        "asignaciones": asignaciones,
        "usuarios": sum(fila[2] for fila in filas) + sin_rol,
        "sin_rol": sin_rol,
        "faltan_catalogo": sorted(set(ROLES_CATALOGO) - {fila[0] for fila in filas}),
        "registro_25": registro,
    }


def imprimir(base: str, conteo: dict) -> None:
    print(f"Base: {base}")
    print(f"{'Rol':<22}{'Origen':<10}{'Usuarios':>9}{'Activos':>9}  Permisos")
    for id_rol, origen, usuarios, activos, permisos in conteo["filas"]:
        print(f"{id_rol:<22}{origen:<10}{usuarios:>9}{activos:>9}  {permisos}")
    print()
    print(f"Roles: {conteo['roles']}")
    print(f"Permisos: {conteo['permisos']}")
    print(f"Asignaciones rol_permisos: {conteo['asignaciones']}")
    print(f"Usuarios: {conteo['usuarios']} (sin rol: {conteo['sin_rol']})")
    faltan = conteo["faltan_catalogo"]
    print(f"Roles del catalogo que faltan: {', '.join(faltan) if faltan else 'ninguno'}")
    registro = conteo["registro_25"]
    if registro is None:
        print("migracion_25_registro: no existe (migracion 25 sin aplicar o revertida)")
    else:
        print("migracion_25_registro: " + ", ".join(f"{tipo}={n}" for tipo, n in registro.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Cuenta roles, permisos y usuarios por rol (solo lectura).")
    parser.add_argument("base", help="Base: sgi_test_* o sgi_sandbox (nunca sgi_db).")
    base = validar_nombre(parser.parse_args().base, permitir_sandbox=True)

    admin = conectar_admin()
    try:
        if not existe_base(admin.cursor(), base):
            fallar(f"No existe la base {base}.")
    finally:
        admin.close()

    conexion = conectar(base)
    try:
        conexion.set_session(readonly=True)
        imprimir(base, contar(conexion.cursor()))
    finally:
        conexion.close()


if __name__ == "__main__":
    main()
