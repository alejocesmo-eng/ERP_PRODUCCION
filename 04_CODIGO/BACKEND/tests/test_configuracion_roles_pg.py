# tests/test_configuracion_roles_pg.py
"""
Migración 31 y pantalla de Configuración de roles sobre PostgreSQL: PERM_CONFIGURACION_ROLES solo
en ADMIN, rol_permisos_historial creada, OPERARIO, LIDER_MECANIZADOS y JEFE_PRODUCCION reciben 403
(rol leído de la base) y ADMIN entra; cada cambio de permisos queda registrado. La reversión se
detiene si hay cambios registrados y, sin ellos, deshace solo lo que la migración registró.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py; las
migraciones 27 y 31 se aplican dentro de la prueba (son idempotentes).
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.v1 import configuracion_roles
from app.core import roles
from app.core.security import create_access_token
from app.db.database import get_db
from app.services import acceso_bd
from tests.test_roles_permisos_pg import (  # noqa: F401  (sesion es la fixture)
    MIGRACION_27,
    RUTA_BASE_DATOS,
    conteo,
    ejecutar_sql,
    roles_con,
    sesion,
)

pytestmark = pytest.mark.pg

MIGRACION_31 = RUTA_BASE_DATOS / "31_MIGRACION_CONFIGURACION_ROLES.sql"
REVERSION_31 = RUTA_BASE_DATOS / "31_REVERSION_CONFIGURACION_ROLES.sql"
PERMISO = configuracion_roles.PERMISO_CONFIGURACION
RUTA = "/api/v1/configuracion/roles"
SIN_ACCESO = [roles.OPERARIO, roles.LIDER_MECANIZADOS, roles.JEFE_PRODUCCION]


@pytest.fixture
def cliente(sesion):
    ejecutar_sql(sesion, MIGRACION_27)
    ejecutar_sql(sesion, MIGRACION_31)
    sufijo = uuid.uuid4().hex[:8]
    emails = {}
    # El token lleva el id_usuario (migración 34), no el correo
    ids = {}
    for rol in (roles.ADMIN, *SIN_ACCESO):
        emails[rol] = f"cfg31-{rol.lower()}-{sufijo}@prueba.test"
        sesion.execute(
            text("INSERT INTO usuarios (id_usuario, usuario, email, password_hash, nombre_completo, id_rol, activo) "
                 "VALUES (:id, split_part(:email, '@', 1), :email, '!SIN_CLAVE', 'Prueba configuración 31', :rol, true)"),
            {"id": ids.setdefault(rol, str(uuid.uuid4())), "email": emails[rol], "rol": rol},
        )
    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.include_router(configuracion_roles.router, prefix=RUTA)
    app.dependency_overrides[get_db] = lambda: sesion
    with TestClient(app) as client:
        yield client, ids


def cabeceras(id_usuario, rol):
    t = create_access_token({"sub": id_usuario, "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def test_la_migracion_da_el_acceso_solo_a_admin(sesion):
    ejecutar_sql(sesion, MIGRACION_31)
    ejecutar_sql(sesion, MIGRACION_31)  # idempotente

    assert roles_con(sesion, PERMISO) == {roles.ADMIN}
    assert sesion.execute(text("SELECT to_regclass('public.rol_permisos_historial')")).scalar() is not None


@pytest.mark.parametrize("rol", SIN_ACCESO)
def test_operario_lider_mecanizados_y_jefe_produccion_reciben_403(cliente, rol):
    client, ids = cliente
    for metodo, ruta in (("get", f"{RUTA}/"), ("get", f"{RUTA}/permisos"), ("put", f"{RUTA}/{rol}/permisos")):
        extra = {"json": {"permisos": []}} if metodo == "put" else {}
        respuesta = getattr(client, metodo)(ruta, headers=cabeceras(ids[rol], rol), **extra)
        assert respuesta.status_code == 403, ruta
    # Aunque el token diga ADMIN: el rol sale de la base
    assert client.get(f"{RUTA}/", headers=cabeceras(ids[rol], roles.ADMIN)).status_code == 403


def test_admin_entra_y_cada_cambio_queda_registrado(cliente, sesion):
    client, ids = cliente
    admin = cabeceras(ids[roles.ADMIN], roles.ADMIN)
    assert client.get(f"{RUTA}/", headers=admin).status_code == 200

    actuales = sorted(sesion.execute(
        text("SELECT id_permiso FROM rol_permisos WHERE id_rol = :r"), {"r": roles.OPERARIO}
    ).scalars())
    otro = sesion.execute(
        text("SELECT id_permiso FROM permisos WHERE id_permiso <> ALL(:p) AND id_permiso <> :c ORDER BY 1 LIMIT 1"),
        {"p": actuales, "c": PERMISO},
    ).scalar()
    respuesta = client.put(f"{RUTA}/{roles.OPERARIO}/permisos", json={"permisos": [*actuales, otro]}, headers=admin)
    assert respuesta.status_code == 200
    fila = sesion.execute(
        text("SELECT accion, usuario_email, registrado_en FROM rol_permisos_historial "
             "WHERE id_rol = :r AND id_permiso = :p"),
        {"r": roles.OPERARIO, "p": otro},
    ).one()
    assert (fila.accion, fila.usuario_email) == ("ASIGNADO", ids[roles.ADMIN]) and fila.registrado_en

    # ADMIN no se quita el acceso y un rol con usuarios no se elimina
    assert client.put(f"{RUTA}/{roles.ADMIN}/permisos", json={"permisos": []}, headers=admin).status_code == 409
    assert client.delete(f"{RUTA}/{roles.OPERARIO}", headers=admin).status_code == 409


def test_la_reversion_se_detiene_con_cambios_registrados_y_si_no_deja_los_mismos_conteos(sesion):
    ejecutar_sql(sesion, MIGRACION_31)
    con_31 = conteo(sesion)
    registrados = set(sesion.execute(text("SELECT tipo FROM migracion_31_registro")).scalars())
    previos = sesion.execute(text("SELECT count(*) FROM rol_permisos_historial")).scalar()
    sesion.execute(text(
        "INSERT INTO rol_permisos_historial (id_rol, id_permiso, accion, usuario_email) "
        "VALUES ('ADMIN', 'PERM_PRUEBA', 'ASIGNADO', 'rev31@prueba.test')"
    ))

    if "TABLA" in registrados:
        with pytest.raises(Exception, match="respáldelos"):
            with sesion.begin_nested():
                ejecutar_sql(sesion, REVERSION_31)

    sesion.execute(text("DELETE FROM rol_permisos_historial WHERE usuario_email = 'rev31@prueba.test'"))
    if previos:
        pytest.skip("La copia ya tiene cambios registrados en rol_permisos_historial: no se revierte.")
    ejecutar_sql(sesion, REVERSION_31)
    ejecutar_sql(sesion, REVERSION_31)  # idempotente: sin registro no hace nada
    assert sesion.execute(text("SELECT to_regclass('public.migracion_31_registro')")).scalar() is None
    if "PERMISO" in registrados:
        assert not roles_con(sesion, PERMISO)

    ejecutar_sql(sesion, MIGRACION_31)
    assert conteo(sesion) == con_31
    assert roles_con(sesion, PERMISO) == {roles.ADMIN}
