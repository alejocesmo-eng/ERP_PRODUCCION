# tests/test_capturista_tiempos_pg.py
"""
Migración 29 sobre PostgreSQL: CAPTURISTA_TIEMPOS con un solo permiso, PERM_TIEMPOS_REGISTRAR,
que también tienen OPERARIO, JEFE_PRODUCCION y ADMIN. La reversión se detiene si un usuario tiene
el rol y, sin usuarios, deshace solo lo que la migración registró.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py; la 29 se
aplica dentro de la prueba (es idempotente), esté o no aplicada en la copia.
"""
import uuid

import pytest
from sqlalchemy import text

from app.core import roles
from tests.test_roles_permisos_pg import (  # noqa: F401  (sesion es la fixture)
    RUTA_BASE_DATOS,
    conteo,
    ejecutar_sql,
    roles_con,
    sesion,
)

pytestmark = pytest.mark.pg

MIGRACION_29 = RUTA_BASE_DATOS / "29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql"
REVERSION_29 = RUTA_BASE_DATOS / "29_REVERSION_ROL_CAPTURISTA_TIEMPOS.sql"
PERMISO = "PERM_TIEMPOS_REGISTRAR"


def permisos_de(sesion, id_rol):
    return set(sesion.execute(
        text("SELECT id_permiso FROM rol_permisos WHERE id_rol = :r"), {"r": id_rol}
    ).scalars())


def test_el_capturista_solo_registra_tiempos(sesion):
    ejecutar_sql(sesion, MIGRACION_29)

    assert permisos_de(sesion, roles.CAPTURISTA_TIEMPOS) == {PERMISO}
    assert roles_con(sesion, PERMISO) == {
        roles.OPERARIO, roles.CAPTURISTA_TIEMPOS, roles.JEFE_PRODUCCION, roles.ADMIN,
    }
    nombre = sesion.execute(
        text("SELECT nombre_rol FROM roles WHERE id_rol = :r"), {"r": roles.CAPTURISTA_TIEMPOS}
    ).scalar_one()
    assert nombre == "Capturista de tiempos"


def test_la_reversion_se_detiene_con_usuarios_y_si_no_deja_los_mismos_conteos(sesion):
    ejecutar_sql(sesion, MIGRACION_29)
    con_29 = conteo(sesion)
    # Usuarios que ya tuvieran el rol en la copia (por ejemplo la cuenta demo): se reasignan
    # dentro de la transacción de la prueba
    anteriores = sesion.execute(
        text("SELECT id_usuario FROM usuarios WHERE id_rol = :r"), {"r": roles.CAPTURISTA_TIEMPOS}
    ).scalars().all()
    sesion.execute(text("UPDATE usuarios SET id_rol = 'OPERARIO' WHERE id_rol = :r"), {"r": roles.CAPTURISTA_TIEMPOS})
    sesion.execute(
        text("INSERT INTO usuarios (id_usuario, email, password_hash, nombre_completo, id_rol, activo) "
             "VALUES (:id, :email, '!SIN_CLAVE', 'Prueba reversión 29', :rol, true)"),
        {"id": str(uuid.uuid4()), "email": f"rev29-{uuid.uuid4().hex[:8]}@prueba.test", "rol": roles.CAPTURISTA_TIEMPOS},
    )

    with pytest.raises(Exception, match="reasígnelos"):
        with sesion.begin_nested():
            ejecutar_sql(sesion, REVERSION_29)

    sesion.execute(text("DELETE FROM usuarios WHERE email LIKE 'rev29-%@prueba.test'"))
    registrados = set(sesion.execute(text("SELECT tipo FROM migracion_29_registro")).scalars())
    ejecutar_sql(sesion, REVERSION_29)
    ejecutar_sql(sesion, REVERSION_29)  # idempotente: sin registro no hace nada
    assert sesion.execute(text("SELECT to_regclass('public.migracion_29_registro')")).scalar() is None
    if "ROL" in registrados:
        assert not permisos_de(sesion, roles.CAPTURISTA_TIEMPOS)

    ejecutar_sql(sesion, MIGRACION_29)
    ejecutar_sql(sesion, MIGRACION_29)  # idempotente
    if anteriores:
        sesion.execute(
            text("UPDATE usuarios SET id_rol = :r WHERE id_usuario = ANY(:ids)"),
            {"r": roles.CAPTURISTA_TIEMPOS, "ids": list(anteriores)},
        )
    assert conteo(sesion) == con_29
