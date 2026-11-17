# tests/test_roles_permisos_pg.py
"""
SCRUM-27 paso 1b sobre PostgreSQL: con la migración 25 aplicada están los 16 roles del catálogo
y el reparto de permisos de reglas/permisos-por-rol-modulo.md, con PERM_OP_LIBERAR solo en
LIDER_DISENO y DIBUJANTE; la reversión deshace solo lo que la migración registró, se detiene si un usuario tiene un rol nuevo y la migración se puede
volver a aplicar.
Las migraciones 27 (LIDER_PRODUCCION pasa a LIDER_MECANIZADOS), 29 (CAPTURISTA_TIEMPOS) y 30 (tiempos
de LIDER_MECANIZADOS) se aplican dentro de cada prueba que las necesita (son idempotentes) y se
revierten, en orden inverso, antes de revertir la 25.

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*) con la migración 25
aplicada, dentro de una transacción que se revierte al terminar. Los archivos SQL se ejecutan
sin sus BEGIN/COMMIT para que queden dentro de esa transacción.
"""
import os
import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.deps import rol_tiene_permiso
from app.core import roles

URL_PG = os.environ.get("SGI_TEST_PG_URL")
RUTA_BASE_DATOS = Path(__file__).resolve().parents[3] / "05_BASE_DATOS"
MIGRACION_25 = RUTA_BASE_DATOS / "25_MIGRACION_ROLES_PERMISOS_POR_ROL.sql"
REVERSION_25 = RUTA_BASE_DATOS / "25_REVERSION_ROLES_PERMISOS_POR_ROL.sql"
MIGRACION_27 = RUTA_BASE_DATOS / "27_MIGRACION_ROL_LIDER_MECANIZADOS.sql"
REVERSION_27 = RUTA_BASE_DATOS / "27_REVERSION_ROL_LIDER_MECANIZADOS.sql"
MIGRACION_29 = RUTA_BASE_DATOS / "29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql"
REVERSION_29 = RUTA_BASE_DATOS / "29_REVERSION_ROL_CAPTURISTA_TIEMPOS.sql"
MIGRACION_30 = RUTA_BASE_DATOS / "30_MIGRACION_TIEMPOS_LIDER_MECANIZADOS.sql"
REVERSION_30 = RUTA_BASE_DATOS / "30_REVERSION_TIEMPOS_LIDER_MECANIZADOS.sql"
# Crea LIDER_SERVICIOS, que está en el catálogo (roles.ROLES_CATALOGO)
MIGRACION_32 = RUTA_BASE_DATOS / "32_MIGRACION_ROL_LIDER_SERVICIOS.sql"

pytestmark = pytest.mark.pg


@pytest.fixture
def sesion():
    assert (make_url(URL_PG).database or "").startswith("sgi_test_"), "Solo se prueba sobre copias sgi_test_*."
    engine = create_engine(URL_PG)
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()
        engine.dispose()


def ejecutar_sql(sesion, ruta):
    """Ejecuta el archivo sin BEGIN/COMMIT, dentro de la transacción de la prueba."""
    cuerpo = re.sub(r"^(BEGIN|COMMIT);\s*$", "", ruta.read_text(encoding="utf-8-sig"), flags=re.MULTILINE)
    # Cursor del driver: sin parámetros, los % de RAISE no se interpretan
    sesion.connection().connection.driver_connection.cursor().execute(cuerpo)


def roles_con(sesion, id_permiso):
    return set(sesion.execute(
        text("SELECT id_rol FROM rol_permisos WHERE id_permiso = :p"), {"p": id_permiso}
    ).scalars())


def conteo(sesion):
    return sesion.execute(text(
        "SELECT (SELECT count(*) FROM roles), (SELECT count(*) FROM permisos), "
        "(SELECT count(*) FROM rol_permisos), (SELECT count(*) FROM usuarios)"
    )).one()


def test_las_migraciones_25_27_29_y_32_dejan_los_roles_del_catalogo(sesion):
    ejecutar_sql(sesion, MIGRACION_27)
    ejecutar_sql(sesion, MIGRACION_29)
    ejecutar_sql(sesion, MIGRACION_32)
    existentes = set(sesion.execute(text("SELECT id_rol FROM roles")).scalars())

    assert set(roles.ROLES_CATALOGO) <= existentes
    assert sesion.execute(text("SELECT to_regclass('public.migracion_25_registro')")).scalar() is not None


def test_perm_op_liberar_solo_en_lider_de_diseno_y_dibujante(sesion):
    assert roles_con(sesion, "PERM_OP_LIBERAR") == {roles.LIDER_DISENO, roles.DIBUJANTE}


def test_solo_el_lider_de_diseno_aprueba_planos(sesion):
    assert roles_con(sesion, "PERM_PLANO_APROBAR") == {roles.LIDER_DISENO}
    assert {roles.LIDER_DISENO, roles.DIBUJANTE} <= roles_con(sesion, "PERM_PLANO_GESTION")


def test_valor_cotizado_solo_para_los_cuatro_roles_decididos(sesion):
    assert roles_con(sesion, "PERM_VALOR_COTIZADO_VER") == {
        roles.VENTAS, roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD,
    }


def test_costos_del_expediente_sin_ventas(sesion):
    assert roles_con(sesion, "PERM_EXPEDIENTE_COSTOS_VER") == {
        roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD,
    }


def test_aprobaciones_de_compras_metas_y_retencion(sesion):
    assert roles_con(sesion, "PERM_SOLICITUD_COMPRA_APROBAR") == {roles.JEFE_PRODUCCION, roles.SECRETARIA_GERENCIA}
    assert roles_con(sesion, "PERM_ORDEN_COMPRA_APROBAR") == {roles.DIRECTOR_PRODUCCION, roles.LIDER_LOGISTICA}
    assert roles_con(sesion, "PERM_METAS_APROBAR") == {roles.GERENCIA}
    assert roles_con(sesion, "PERM_METAS_PROPONER") == {roles.GESTION_CALIDAD}
    assert roles_con(sesion, "PERM_RETENCION_GESTIONAR") == {
        roles.VENTAS, roles.JEFE_PRODUCCION, roles.DIRECTOR_PRODUCCION,
    }
    assert rol_tiene_permiso(sesion, roles.CALIDAD_PRODUCTO, "PERM_CALIDAD_APROBAR")


def test_reversion_y_reaplicacion_dejan_los_mismos_conteos(sesion):
    ejecutar_sql(sesion, MIGRACION_27)
    ejecutar_sql(sesion, MIGRACION_29)
    ejecutar_sql(sesion, MIGRACION_30)
    con_27 = conteo(sesion)
    # La 29 y la 27 se revierten antes que la 25 (sus asignaciones son posteriores a la 25). La guarda
    # de la 29 exige que nadie tenga CAPTURISTA_TIEMPOS: se reasignan y se restauran al final
    capturistas = sesion.execute(
        text("SELECT id_usuario FROM usuarios WHERE id_rol = :r"), {"r": roles.CAPTURISTA_TIEMPOS}
    ).scalars().all()
    sesion.execute(text("UPDATE usuarios SET id_rol = 'OPERARIO' WHERE id_rol = :r"), {"r": roles.CAPTURISTA_TIEMPOS})
    ejecutar_sql(sesion, REVERSION_30)
    ejecutar_sql(sesion, REVERSION_29)
    ejecutar_sql(sesion, REVERSION_27)
    con_25 = conteo(sesion)
    registrados = set(sesion.execute(
        text("SELECT id_rol FROM migracion_25_registro WHERE tipo = 'ROL'")
    ).scalars())
    retirados_op_liberar = set(sesion.execute(text(
        "SELECT id_rol FROM migracion_25_registro WHERE tipo = 'ROL_PERMISO_RETIRADO' AND id_permiso = 'PERM_OP_LIBERAR'"
    )).scalars())
    # La guarda de la reversión exige que ningún usuario tenga un rol de la 25 (los usuarios demo sí
    # los tienen): se reasignan a un rol anterior dentro de la transacción y se restauran al final.
    usuarios_con_rol_25 = sesion.execute(text(
        "SELECT u.id_usuario, u.id_rol FROM usuarios u "
        "JOIN migracion_25_registro r ON r.tipo = 'ROL' AND r.id_rol = u.id_rol"
    )).all()
    if usuarios_con_rol_25:
        rol_temporal = sesion.execute(text(
            "SELECT id_rol FROM roles WHERE id_rol NOT IN "
            "(SELECT id_rol FROM migracion_25_registro WHERE tipo = 'ROL' AND id_rol IS NOT NULL) "
            "ORDER BY id_rol = 'ADMIN' DESC, id_rol LIMIT 1"
        )).scalar_one()
        sesion.execute(
            text("UPDATE usuarios SET id_rol = :rol WHERE id_usuario = :id"),
            [{"rol": rol_temporal, "id": id_usuario} for id_usuario, _ in usuarios_con_rol_25],
        )

    ejecutar_sql(sesion, REVERSION_25)

    existentes = set(sesion.execute(text("SELECT id_rol FROM roles")).scalars())
    assert not registrados & existentes
    assert sesion.execute(text("SELECT to_regclass('public.migracion_25_registro')")).scalar() is None
    assert roles_con(sesion, "PERM_OP_LIBERAR") == retirados_op_liberar
    assert conteo(sesion)[3] == con_25[3], "La reversión no toca usuarios."

    ejecutar_sql(sesion, REVERSION_25)  # idempotente: sin registro no hace nada
    ejecutar_sql(sesion, MIGRACION_25)
    ejecutar_sql(sesion, MIGRACION_25)  # idempotente
    sesion.execute(
        text("UPDATE usuarios SET id_rol = :rol WHERE id_usuario = :id"),
        [{"rol": rol, "id": id_usuario} for id_usuario, rol in usuarios_con_rol_25],
    )

    assert conteo(sesion) == con_25
    assert roles_con(sesion, "PERM_OP_LIBERAR") == {roles.LIDER_DISENO, roles.DIBUJANTE}
    ejecutar_sql(sesion, MIGRACION_27)
    ejecutar_sql(sesion, MIGRACION_29)
    ejecutar_sql(sesion, MIGRACION_30)
    if capturistas:
        sesion.execute(
            text("UPDATE usuarios SET id_rol = :r WHERE id_usuario = ANY(:ids)"),
            {"r": roles.CAPTURISTA_TIEMPOS, "ids": list(capturistas)},
        )
    assert conteo(sesion) == con_27


def test_la_reversion_se_detiene_si_un_usuario_tiene_un_rol_nuevo(sesion):
    registrados = sesion.execute(
        text("SELECT id_rol FROM migracion_25_registro WHERE tipo = 'ROL' ORDER BY id_rol")
    ).scalars().all()
    if not registrados:
        pytest.skip("La copia ya tenía todos los roles: la migración 25 no creó ninguno.")
    sesion.execute(
        text("INSERT INTO usuarios (id_usuario, email, password_hash, nombre_completo, id_rol, activo) "
             "VALUES (:id, :email, '!SIN_CLAVE', 'Prueba reversión 25', :rol, true)"),
        {"id": str(uuid.uuid4()), "email": f"rev25-{uuid.uuid4().hex[:8]}@prueba.test", "rol": registrados[0]},
    )
    antes = conteo(sesion)

    with pytest.raises(Exception, match="reasígnelos"):
        with sesion.begin_nested():
            ejecutar_sql(sesion, REVERSION_25)

    assert conteo(sesion) == antes
