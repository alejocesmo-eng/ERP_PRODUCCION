# tests/test_rol_lider_mecanizados_pg.py
"""
Migración 27 sobre PostgreSQL: LIDER_PRODUCCION pasa a LIDER_MECANIZADOS ("Líder de Mecanizados")
con sus usuarios y asignaciones, recibe PERM_OP_CERRAR (cierra OP como respaldo del Jefe de
Producción) y no libera, no retiene ni ve costos o valor cotizado. La reversión devuelve el rol
anterior a los mismos usuarios y la migración se puede volver a aplicar.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py; la 27 se
aplica dentro de la prueba (es idempotente), esté o no aplicada en la copia.
"""
import uuid

import pytest
from sqlalchemy import text

from app.core import roles
from tests.test_roles_permisos_pg import (  # noqa: F401  (sesion es la fixture)
    MIGRACION_25,
    MIGRACION_27,
    REVERSION_27,
    conteo,
    ejecutar_sql,
    sesion,
)

pytestmark = pytest.mark.pg

ANTERIOR = "LIDER_PRODUCCION"


def existe_rol(sesion, id_rol):
    return sesion.execute(text("SELECT count(*) FROM roles WHERE id_rol = :r"), {"r": id_rol}).scalar() == 1


def permisos_de(sesion, id_rol):
    return set(sesion.execute(
        text("SELECT id_permiso FROM rol_permisos WHERE id_rol = :r"), {"r": id_rol}
    ).scalars())


def rol_de(sesion, id_usuario):
    return sesion.execute(text("SELECT id_rol FROM usuarios WHERE id_usuario = :id"), {"id": id_usuario}).scalar_one()


def registro_25(sesion, id_rol):
    if sesion.execute(text("SELECT to_regclass('public.migracion_25_registro')")).scalar() is None:
        return 0
    return sesion.execute(
        text("SELECT count(*) FROM migracion_25_registro WHERE id_rol = :r"), {"r": id_rol}
    ).scalar()


def test_el_rol_queda_renombrado_con_cierre_de_op_y_sin_costos(sesion):
    ejecutar_sql(sesion, MIGRACION_27)

    assert existe_rol(sesion, roles.LIDER_MECANIZADOS) and not existe_rol(sesion, ANTERIOR)
    nombre = sesion.execute(
        text("SELECT nombre_rol FROM roles WHERE id_rol = :r"), {"r": roles.LIDER_MECANIZADOS}
    ).scalar_one()
    assert nombre == "Líder de Mecanizados"
    permisos = permisos_de(sesion, roles.LIDER_MECANIZADOS)
    assert "PERM_OP_CERRAR" in permisos
    assert not permisos & {
        "PERM_OP_LIBERAR", "PERM_RETENCION_GESTIONAR", "PERM_VALOR_COTIZADO_VER", "PERM_EXPEDIENTE_COSTOS_VER",
    }
    assert registro_25(sesion, ANTERIOR) == 0


def test_los_usuarios_pasan_al_rol_nuevo_y_vuelven_con_la_reversion(sesion):
    ejecutar_sql(sesion, MIGRACION_27)
    con_27 = conteo(sesion)
    ejecutar_sql(sesion, REVERSION_27)
    assert existe_rol(sesion, ANTERIOR) and not existe_rol(sesion, roles.LIDER_MECANIZADOS)
    assert "PERM_OP_CERRAR" not in permisos_de(sesion, ANTERIOR)

    id_usuario = str(uuid.uuid4())
    sesion.execute(
        text("INSERT INTO usuarios (id_usuario, email, password_hash, nombre_completo, id_rol, activo) "
             "VALUES (:id, :email, '!SIN_CLAVE', 'Prueba migración 27', :rol, true)"),
        {"id": id_usuario, "email": f"mig27-{uuid.uuid4().hex[:8]}@prueba.test", "rol": ANTERIOR},
    )

    ejecutar_sql(sesion, MIGRACION_27)
    ejecutar_sql(sesion, MIGRACION_27)  # idempotente
    assert rol_de(sesion, id_usuario) == roles.LIDER_MECANIZADOS
    assert conteo(sesion)[:3] == con_27[:3]

    ejecutar_sql(sesion, REVERSION_27)
    ejecutar_sql(sesion, REVERSION_27)  # idempotente: sin registro no hace nada
    assert rol_de(sesion, id_usuario) == ANTERIOR
    assert registro_25(sesion, roles.LIDER_MECANIZADOS) == 0

    ejecutar_sql(sesion, MIGRACION_27)
    assert rol_de(sesion, id_usuario) == roles.LIDER_MECANIZADOS


def test_si_la_25_vuelve_a_crear_el_rol_anterior_la_27_lo_retira(sesion):
    ejecutar_sql(sesion, MIGRACION_27)
    con_27 = conteo(sesion)

    ejecutar_sql(sesion, MIGRACION_25)
    assert existe_rol(sesion, ANTERIOR)
    ejecutar_sql(sesion, MIGRACION_27)

    assert not existe_rol(sesion, ANTERIOR)
    assert registro_25(sesion, ANTERIOR) == 0
    assert conteo(sesion) == con_27
