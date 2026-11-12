# tests/test_busqueda.py
"""
Búsqueda general (reglas/permisos-por-rol-modulo.md, "Búsqueda y expediente"):
- Cada rol encuentra solo sus tipos de dato; los demás no aparecen y no hay 403.
- El rol se lee de usuarios.id_rol en cada consulta, no del token.
- El valor cotizado solo sale con PERM_VALOR_COTIZADO_VER (ADMIN no lo tiene).
- Los costos de la OP (/costos/liquidar y /costos/op) exigen PERM_EXPEDIENTE_COSTOS_VER.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima (no se importa app.main).
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import busqueda, costos
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import (
    Cotizacion, OrdenProduccion, Permiso, Producto, Proyecto, Rol, RolPermiso, SocioNegocio, Usuario,
)

URL = "/api/v1/busqueda/"
PERMISOS = {
    "PERM_VALOR_COTIZADO_VER": [roles.VENTAS, roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD],
    "PERM_EXPEDIENTE_COSTOS_VER": [roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD],
    "PERM_ADMIN_ALL": [roles.ADMIN],
}
ROLES_PRUEBA = [
    roles.ADMIN, roles.VENTAS, roles.JEFE_PRODUCCION, roles.GESTION_CALIDAD, roles.COSTOS,
    roles.LIDER_MECANIZADOS, roles.ALMACEN, roles.OPERARIO, roles.CALIDAD,
]


@pytest.fixture
def ctx():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI()
    app.include_router(busqueda.router, prefix="/api/v1/busqueda")
    app.include_router(costos.router, prefix="/api/v1/costos")
    app.dependency_overrides[get_db] = _get_db

    with Sesion() as s:
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in ROLES_PRUEBA)
        for id_permiso, con_permiso in PERMISOS.items():
            s.add(Permiso(id_permiso=id_permiso, modulo="PRUEBA"))
            s.add_all(RolPermiso(id_rol=rol, id_permiso=id_permiso) for rol in con_permiso)
        s.add_all(
            Usuario(email=f"{rol.lower()}@prueba.test", password_hash="!SIN_CLAVE", nombre_completo=rol, id_rol=rol)
            for rol in ROLES_PRUEBA
        )
        socio = SocioNegocio(codigo_socio="900111222", nit_cedula="900111222", razon_social="Metales Ficticios SAS",
                             es_cliente=True, es_proveedor=False, estado_activo=True)
        producto = Producto(codigo_rn="RN-001-001-000001", descripcion="Eje ficticio")
        s.add_all([socio, producto])
        s.flush()
        s.add(Cotizacion(id_socio=socio.id_socio, numero_cotizacion="COT-BUS-1", valor_total=1500))
        pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido="PED-BUS-1", codigo_proyecto="PED-BUS-1",
                          cliente_nombre="Metales Ficticios SAS", requisitos_cliente="Según plano",
                          cotizacion_total=1500, confirmado=True)
        s.add(pedido)
        s.flush()
        s.add(OrdenProduccion(id_proyecto=pedido.id_proyecto, id_producto=producto.id_producto,
                              codigo_op="OP-BUS-1", cantidad_fabricar=1, unidad_actual="MECANIZADOS"))
        # Otra unidad: el líder de Mecanizados no la encuentra
        s.add(OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op="OP-BUS-2", cantidad_fabricar=1,
                              unidad_actual="SERVICIOS"))
        s.commit()

    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol, rol_en_token=None):
    """Token del usuario de prueba del rol; rol_en_token permite que el token diga otro rol."""
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol_en_token or rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def tipos_encontrados(client, rol, q="bus", **kwargs):
    r = client.get(URL, params={"q": q}, headers=token(rol, **kwargs))
    assert r.status_code == 200, r.text
    return {fila["tipo"] for fila in r.json()["resultados"]}, r.json()


@pytest.mark.parametrize("rol, esperados", [
    (roles.VENTAS, {"COTIZACION", "PEDIDO"}),
    (roles.JEFE_PRODUCCION, {"PEDIDO", "OP"}),
    (roles.GESTION_CALIDAD, {"PEDIDO", "OP"}),
    (roles.COSTOS, {"PEDIDO", "OP"}),
    (roles.LIDER_MECANIZADOS, {"OP"}),
    (roles.ADMIN, {"COTIZACION", "PEDIDO", "OP"}),
    (roles.ALMACEN, set()),
    (roles.OPERARIO, set()),
])
def test_cada_rol_solo_encuentra_sus_tipos(ctx, rol, esperados):
    client, _ = ctx
    assert tipos_encontrados(client, rol)[0] == esperados


def test_busca_por_nombre_clientes_y_productos(ctx):
    client, _ = ctx

    por_cliente, _ = tipos_encontrados(client, roles.VENTAS, q="metales")
    por_producto, datos = tipos_encontrados(client, roles.JEFE_PRODUCCION, q="eje fict")

    assert por_cliente == {"COTIZACION", "PEDIDO", "CLIENTE"}
    assert por_producto == {"OP", "PRODUCTO"}
    assert {f["codigo"] for f in datos["resultados"]} == {"OP-BUS-1", "RN-001-001-000001"}


def test_el_lider_solo_encuentra_las_op_de_su_unidad(ctx):
    client, _ = ctx
    _, lider = tipos_encontrados(client, roles.LIDER_MECANIZADOS, q="OP-BUS")
    _, jefe = tipos_encontrados(client, roles.JEFE_PRODUCCION, q="OP-BUS")

    assert {f["codigo"] for f in lider["resultados"]} == {"OP-BUS-1"}
    assert {f["codigo"] for f in jefe["resultados"] if f["tipo"] == "OP"} == {"OP-BUS-1", "OP-BUS-2"}


def test_lider_de_mecanizados_encuentra_al_cliente_sin_valor_cotizado(ctx):
    client, _ = ctx
    tipos, datos = tipos_encontrados(client, roles.LIDER_MECANIZADOS, q="metales")

    assert tipos == {"CLIENTE"}
    assert datos["valor_cotizado"] is False and datos["costos"] is False


def test_ventas_no_ve_op_ni_recibe_acceso_denegado(ctx):
    client, _ = ctx
    tipos, datos = tipos_encontrados(client, roles.VENTAS, q="OP-BUS")

    assert tipos == set()
    assert datos["expediente_op"] is False and "OP" not in datos["tipos"]


def test_el_rol_se_lee_de_la_base_y_no_del_token(ctx):
    client, Sesion = ctx
    # El token dice VENTAS, pero en la base el usuario es LIDER_MECANIZADOS
    assert tipos_encontrados(client, roles.LIDER_MECANIZADOS, rol_en_token=roles.VENTAS)[0] == {"OP"}

    with Sesion() as s:
        s.query(Usuario).filter_by(email="lider_mecanizados@prueba.test").update({"id_rol": roles.ALMACEN})
        s.commit()
    # Mismo token: el cambio de rol cuenta desde la siguiente consulta
    assert tipos_encontrados(client, roles.LIDER_MECANIZADOS)[0] == set()


def test_valor_cotizado_solo_con_su_permiso(ctx):
    client, _ = ctx

    _, ventas = tipos_encontrados(client, roles.VENTAS)
    _, admin = tipos_encontrados(client, roles.ADMIN)
    _, lider = tipos_encontrados(client, roles.LIDER_MECANIZADOS)

    assert {f["valor_cotizado"] for f in ventas["resultados"]} == {1500.0}
    assert all("valor_cotizado" not in f for f in admin["resultados"]) and admin["valor_cotizado"] is False
    assert lider["valor_cotizado"] is False


def test_calidad_anterior_se_trata_como_gestion_calidad(ctx):
    client, _ = ctx
    tipos, datos = tipos_encontrados(client, roles.CALIDAD)

    assert tipos == {"PEDIDO", "OP"}
    assert datos["costos"] is True and datos["valor_cotizado"] is True


@pytest.mark.parametrize("rol, expediente, costos_op", [
    (roles.JEFE_PRODUCCION, True, True),
    (roles.GESTION_CALIDAD, True, True),
    (roles.COSTOS, True, True),
    (roles.LIDER_MECANIZADOS, True, False),
    (roles.ADMIN, True, False),
    (roles.VENTAS, False, False),
    (roles.ALMACEN, False, False),
])
def test_alcance_del_expediente_y_costos(ctx, rol, expediente, costos_op):
    client, _ = ctx
    alcance = client.get("/api/v1/busqueda/alcance", headers=token(rol)).json()

    assert (alcance["expediente_op"], alcance["costos"]) == (expediente, costos_op)


@pytest.mark.parametrize("ruta", ["/api/v1/costos/liquidar/OP-BUS-1", "/api/v1/costos/op/OP-BUS-1"])
def test_costos_de_la_op_solo_para_roles_de_costos(ctx, ruta):
    client, _ = ctx

    assert client.get(ruta, headers=token(roles.COSTOS)).status_code == 200
    assert client.get(ruta, headers=token(roles.LIDER_MECANIZADOS)).status_code == 403
    assert client.get(ruta, headers=token(roles.ADMIN)).status_code == 403
    # El token no basta: dice COSTOS, pero el usuario es VENTAS en la base
    assert client.get(ruta, headers=token(roles.VENTAS, rol_en_token=roles.COSTOS)).status_code == 403


def test_texto_corto_no_busca(ctx):
    client, _ = ctx
    assert tipos_encontrados(client, roles.ADMIN, q="b")[0] == set()


def test_sin_token_responde_401(ctx):
    client, _ = ctx
    assert client.get(URL, params={"q": "bus"}).status_code == 401
    assert client.get("/api/v1/busqueda/alcance").status_code == 401
