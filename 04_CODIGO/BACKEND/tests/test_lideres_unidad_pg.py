# tests/test_lideres_unidad_pg.py
"""
Migración 32 sobre PostgreSQL: LIDER_SERVICIOS con PERM_OP_CERRAR y PERM_TIEMPOS_REGISTRAR (el de la
migración 29, no uno nuevo), sin costos, valor cotizado, liberación ni retención. LIDER_MECANIZADOS
sigue sin esos permisos. Con el rol leído de la base, los dos líderes ven cliente y OP sin costos ni
valor cotizado, y LIDER_SERVICIOS registra tiempos. La reversión se detiene con usuarios o con
asignaciones posteriores (por ejemplo, desde Configuración) y, sin ellos, deshace solo lo registrado.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py; las migraciones
27, 29, 30 y 32 se aplican dentro de la prueba (son idempotentes).
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.v1 import busqueda, produccion
from app.core import roles
from app.core.security import create_access_token
from app.db.database import get_db
from app.services import acceso_bd
from tests.test_roles_permisos_pg import (  # noqa: F401  (sesion es la fixture)
    MIGRACION_27,
    MIGRACION_29,
    MIGRACION_30,
    RUTA_BASE_DATOS,
    conteo,
    ejecutar_sql,
    sesion,
)

pytestmark = pytest.mark.pg

MIGRACION_32 = RUTA_BASE_DATOS / "32_MIGRACION_ROL_LIDER_SERVICIOS.sql"
REVERSION_32 = RUTA_BASE_DATOS / "32_REVERSION_ROL_LIDER_SERVICIOS.sql"
PROHIBIDOS = {"PERM_EXPEDIENTE_COSTOS_VER", "PERM_VALOR_COTIZADO_VER", "PERM_OP_LIBERAR", "PERM_RETENCION_GESTIONAR"}


def aplicar(sesion):
    for ruta in (MIGRACION_27, MIGRACION_29, MIGRACION_30, MIGRACION_32):
        ejecutar_sql(sesion, ruta)


def permisos_de(sesion, id_rol):
    return set(sesion.execute(
        text("SELECT id_permiso FROM rol_permisos WHERE id_rol = :r"), {"r": id_rol}
    ).scalars())


def test_lider_de_servicios_cierra_y_registra_tiempos_sin_costos_ni_valor_cotizado(sesion):
    aplicar(sesion)
    ejecutar_sql(sesion, MIGRACION_32)  # idempotente

    permisos = permisos_de(sesion, roles.LIDER_SERVICIOS)
    assert {"PERM_OP_CERRAR", acceso_bd.PERMISO_TIEMPOS} <= permisos
    assert not permisos & PROHIBIDOS
    assert sesion.execute(
        text("SELECT count(*) FROM permisos WHERE id_permiso LIKE 'PERM_TIEMPOS%'")
    ).scalar() == 1
    nombre = sesion.execute(
        text("SELECT nombre_rol FROM roles WHERE id_rol = :r"), {"r": roles.LIDER_SERVICIOS}
    ).scalar_one()
    assert nombre == "Líder de Servicios"


def test_lider_de_mecanizados_cierra_sin_liberar_retener_ni_costos(sesion):
    aplicar(sesion)
    permisos = permisos_de(sesion, roles.LIDER_MECANIZADOS)

    assert {"PERM_OP_CERRAR", acceso_bd.PERMISO_TIEMPOS} <= permisos
    assert not permisos & PROHIBIDOS


@pytest.fixture
def cliente(sesion):
    aplicar(sesion)
    sufijo = uuid.uuid4().hex[:8]
    emails = {}
    for rol in (roles.LIDER_MECANIZADOS, roles.LIDER_SERVICIOS):
        emails[rol] = f"lid32-{rol.lower()}-{sufijo}@prueba.test"
        sesion.execute(
            text("INSERT INTO usuarios (id_usuario, email, password_hash, nombre_completo, id_rol, activo) "
                 "VALUES (:id, :email, '!SIN_CLAVE', 'Prueba líderes 32', :rol, true)"),
            {"id": str(uuid.uuid4()), "email": emails[rol], "rol": rol},
        )
    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.add_middleware(acceso_bd.OcultarCamposPorRol)
    app.include_router(busqueda.router, prefix="/api/v1/busqueda")
    app.include_router(produccion.router, prefix="/api/v1/operaciones")
    app.dependency_overrides[get_db] = lambda: sesion
    with TestClient(app) as client:
        yield client, emails


def cabeceras(email, rol):
    t = create_access_token({"sub": email, "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.parametrize("rol", [roles.LIDER_MECANIZADOS, roles.LIDER_SERVICIOS])
def test_los_lideres_ven_cliente_y_op_sin_costos_ni_valor_cotizado(cliente, rol):
    client, emails = cliente
    # El token dice ADMIN: el alcance sale del rol de la base
    alcance = client.get("/api/v1/busqueda/alcance", headers=cabeceras(emails[rol], roles.ADMIN)).json()

    assert set(alcance["tipos"]) == {roles.BUSQUEDA_OP, roles.BUSQUEDA_CLIENTE}
    assert alcance["costos"] is False and alcance["valor_cotizado"] is False


def test_lider_de_servicios_registra_tiempos_hasta_que_se_le_retira_el_permiso(cliente, sesion):
    client, emails = cliente
    ruta = "/api/v1/operaciones/setup/iniciar"
    lider = cabeceras(emails[roles.LIDER_SERVICIOS], roles.LIDER_SERVICIOS)
    # Cuerpo vacío: pasa el permiso y llega a la validación del endpoint
    assert client.post(ruta, json={}, headers=lider).status_code == 422

    # Como al retirarlo desde Configuración: aplica en la siguiente consulta, sin reiniciar
    sesion.execute(text("DELETE FROM rol_permisos WHERE id_rol = :r AND id_permiso = :p"),
                   {"r": roles.LIDER_SERVICIOS, "p": acceso_bd.PERMISO_TIEMPOS})
    assert client.post(ruta, json={}, headers=lider).status_code == 403


def test_la_reversion_se_detiene_con_usuarios_o_asignaciones_y_si_no_deja_los_mismos_conteos(sesion):
    aplicar(sesion)
    con_32 = conteo(sesion)
    anteriores = sesion.execute(
        text("SELECT id_usuario FROM usuarios WHERE id_rol = :r"), {"r": roles.LIDER_SERVICIOS}
    ).scalars().all()
    sesion.execute(text("UPDATE usuarios SET id_rol = 'JEFE_PRODUCCION' WHERE id_rol = :r"),
                   {"r": roles.LIDER_SERVICIOS})
    sesion.execute(
        text("INSERT INTO usuarios (id_usuario, email, password_hash, nombre_completo, id_rol, activo) "
             "VALUES (:id, :email, '!SIN_CLAVE', 'Prueba reversión 32', :rol, true)"),
        {"id": str(uuid.uuid4()), "email": f"rev32-{uuid.uuid4().hex[:8]}@prueba.test", "rol": roles.LIDER_SERVICIOS},
    )
    registrados = set(sesion.execute(text("SELECT tipo FROM migracion_32_registro")).scalars())
    if "ROL" in registrados:
        with pytest.raises(Exception, match="reasígnelos"):
            with sesion.begin_nested():
                ejecutar_sql(sesion, REVERSION_32)
    sesion.execute(text("DELETE FROM usuarios WHERE email LIKE 'rev32-%@prueba.test'"))

    if "ROL" in registrados:
        # Asignación posterior (como desde Configuración de roles): la reversión se detiene
        sesion.execute(text("INSERT INTO rol_permisos (id_rol, id_permiso) VALUES (:r, 'PERM_PEDIDO_CERRAR') "
                            "ON CONFLICT DO NOTHING"), {"r": roles.LIDER_SERVICIOS})
        with pytest.raises(Exception, match="posteriores"):
            with sesion.begin_nested():
                ejecutar_sql(sesion, REVERSION_32)
        sesion.execute(text("DELETE FROM rol_permisos WHERE id_rol = :r AND id_permiso = 'PERM_PEDIDO_CERRAR'"),
                       {"r": roles.LIDER_SERVICIOS})

    ejecutar_sql(sesion, REVERSION_32)
    ejecutar_sql(sesion, REVERSION_32)  # idempotente: sin registro no hace nada
    assert sesion.execute(text("SELECT to_regclass('public.migracion_32_registro')")).scalar() is None
    if "ROL" in registrados:
        assert sesion.execute(
            text("SELECT count(*) FROM roles WHERE id_rol = :r"), {"r": roles.LIDER_SERVICIOS}
        ).scalar() == 0

    ejecutar_sql(sesion, MIGRACION_32)
    if anteriores:
        sesion.execute(text("UPDATE usuarios SET id_rol = :r WHERE id_usuario = ANY(:ids)"),
                       {"r": roles.LIDER_SERVICIOS, "ids": list(anteriores)})
    assert conteo(sesion) == con_32
