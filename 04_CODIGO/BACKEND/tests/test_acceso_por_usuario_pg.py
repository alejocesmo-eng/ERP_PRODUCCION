# tests/test_acceso_por_usuario_pg.py
"""
Migración 34 sobre PostgreSQL: usuario único y con formato, correo opcional, usuario deducido del
correo de las cuentas existentes (se detiene sin cambiar nada si hay choques o formato inválido),
usuarios_historial, y reversión que se detiene si hay usuarios sin correo o historial.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py. La 34 se aplica
dentro de la prueba (es idempotente), esté o no aplicada en la copia. Para probar el llenado se
revierte primero dentro de la transacción.
"""
import uuid

import pytest
from sqlalchemy import text

from tests.test_roles_permisos_pg import RUTA_BASE_DATOS, conteo, ejecutar_sql, sesion  # noqa: F401  (sesion es la fixture)

pytestmark = pytest.mark.pg

MIGRACION_34 = RUTA_BASE_DATOS / "34_MIGRACION_ACCESO_POR_USUARIO.sql"
REVERSION_34 = RUTA_BASE_DATOS / "34_REVERSION_ACCESO_POR_USUARIO.sql"


def columna(sesion, nombre):
    return sesion.execute(text(
        "SELECT is_nullable FROM information_schema.columns WHERE table_name = 'usuarios' AND column_name = :c"
    ), {"c": nombre}).scalar()


def existe(sesion, tabla):
    return sesion.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}).scalar() is not None


def asignaciones(sesion):
    return (
        set(sesion.execute(text("SELECT id_usuario, id_rol FROM usuarios")).all()),
        set(sesion.execute(text("SELECT id_rol, id_permiso FROM rol_permisos")).all()),
    )


def sin_34(sesion):
    """Revierte la 34 dentro de la transacción. Se omite si la copia tiene usuarios sin correo."""
    ejecutar_sql(sesion, MIGRACION_34)
    if sesion.execute(text("SELECT count(*) FROM usuarios WHERE email IS NULL")).scalar():
        pytest.skip("La copia tiene usuarios sin correo: la reversión no aplica.")
    sesion.execute(text("DELETE FROM usuarios_historial"))
    ejecutar_sql(sesion, REVERSION_34)


def insertar(sesion, email):
    sesion.execute(text(
        "INSERT INTO usuarios (id_usuario, email, password_hash, nombre_completo, activo) "
        "VALUES (:id, :email, '!SIN_CLAVE', 'Prueba migración 34', true)"
    ), {"id": str(uuid.uuid4()), "email": email})


def test_la_migracion_deja_usuario_obligatorio_correo_opcional_y_es_idempotente(sesion):
    ejecutar_sql(sesion, MIGRACION_34)
    antes = conteo(sesion), asignaciones(sesion)
    ejecutar_sql(sesion, MIGRACION_34)

    assert (conteo(sesion), asignaciones(sesion)) == antes
    assert columna(sesion, "usuario") == "NO" and columna(sesion, "email") == "YES"
    assert existe(sesion, "usuarios_historial")
    assert sesion.execute(text("SELECT count(*) FROM usuarios WHERE usuario !~ '^[a-z0-9._-]{3,50}$'")).scalar() == 0


def test_el_usuario_sale_del_correo_sin_tildes_ni_mayusculas_y_no_toca_roles(sesion):
    sin_34(sesion)
    sufijo = uuid.uuid4().hex[:6]
    insertar(sesion, f"José.Núñez{sufijo}@empresa.test")
    antes = asignaciones(sesion)

    ejecutar_sql(sesion, MIGRACION_34)

    usuario = sesion.execute(text("SELECT usuario FROM usuarios WHERE email = :e"),
                             {"e": f"José.Núñez{sufijo}@empresa.test"}).scalar()
    assert usuario == f"jose.nunez{sufijo}"
    assert asignaciones(sesion) == antes


@pytest.mark.parametrize("correos, mensaje", [
    (["choque.m34@a.test", "choque.m34@b.test"], "mismo usuario"),
    (["ab@corto.test"], "formato inválido"),
    (["con espacio.m34@x.test"], "formato inválido"),
])
def test_se_detiene_sin_cambiar_nada_si_hay_choques_o_formato_invalido(sesion, correos, mensaje):
    sin_34(sesion)
    for correo in correos:
        insertar(sesion, correo)

    with pytest.raises(Exception, match=mensaje):
        with sesion.begin_nested():
            ejecutar_sql(sesion, MIGRACION_34)

    assert columna(sesion, "usuario") is None and not existe(sesion, "usuarios_historial")


def test_formato_unicidad_y_correo_opcional(sesion):
    ejecutar_sql(sesion, MIGRACION_34)
    sufijo = uuid.uuid4().hex[:6]
    insertar_con = text(
        "INSERT INTO usuarios (id_usuario, usuario, email, password_hash, nombre_completo, activo) "
        "VALUES (:id, :usuario, :email, '!SIN_CLAVE', 'Prueba 34', true)"
    )
    sesion.execute(insertar_con, {"id": str(uuid.uuid4()), "usuario": f"sin.correo.{sufijo}", "email": None})
    sesion.execute(insertar_con, {"id": str(uuid.uuid4()), "usuario": f"sin.correo2.{sufijo}", "email": None})

    for usuario, email, restriccion in (
        (f"Mayus.{sufijo}", None, "ck_usuarios_usuario_formato"),
        (f"con espacio{sufijo}", None, "ck_usuarios_usuario_formato"),
        (f"sin.correo.{sufijo}", None, "uq_usuarios_usuario"),
    ):
        with pytest.raises(Exception, match=restriccion):
            with sesion.begin_nested():
                sesion.execute(insertar_con, {"id": str(uuid.uuid4()), "usuario": usuario, "email": email})


def test_la_reversion_se_detiene_con_usuarios_sin_correo_o_historial_y_si_no_deja_los_mismos_conteos(sesion):
    sin_34(sesion)
    antes = conteo(sesion), asignaciones(sesion)
    ejecutar_sql(sesion, MIGRACION_34)
    id_usuario = sesion.execute(text("SELECT id_usuario FROM usuarios LIMIT 1")).scalar_one()

    sesion.execute(text(
        "INSERT INTO usuarios_historial (id_usuario, accion, realizado_por) VALUES (:id, 'EDITADO', :id)"
    ), {"id": id_usuario})
    with pytest.raises(Exception, match="usuarios_historial"):
        with sesion.begin_nested():
            ejecutar_sql(sesion, REVERSION_34)
    sesion.execute(text("DELETE FROM usuarios_historial"))

    correo = sesion.execute(text("SELECT email FROM usuarios WHERE id_usuario = :id"), {"id": id_usuario}).scalar()
    sesion.execute(text("UPDATE usuarios SET email = NULL WHERE id_usuario = :id"), {"id": id_usuario})
    with pytest.raises(Exception, match="sin correo"):
        with sesion.begin_nested():
            ejecutar_sql(sesion, REVERSION_34)
    sesion.execute(text("UPDATE usuarios SET email = :e WHERE id_usuario = :id"), {"e": correo, "id": id_usuario})

    ejecutar_sql(sesion, REVERSION_34)
    ejecutar_sql(sesion, REVERSION_34)  # idempotente

    assert columna(sesion, "usuario") is None and columna(sesion, "email") == "NO"
    assert not existe(sesion, "usuarios_historial")
    assert (conteo(sesion), asignaciones(sesion)) == antes
