# tests/test_expediente_division.py
"""
División del expediente (2026-11-17; reglas/permisos-por-rol-modulo.md, "Búsqueda y expediente"):
- Expediente del pedido: VENTAS, JEFE_PRODUCCION, COSTOS, GESTION_CALIDAD, LIDER_MECANIZADOS y
  LIDER_SERVICIOS. El valor cotizado solo con PERM_VALOR_COTIZADO_VER (los líderes no lo tienen).
  VENTAS no ve números de OP ni datos de producción. Los demás roles reciben 403.
- Expediente de OP: los de antes más DIBUJANTE, LIDER_DISENO y CALIDAD_PRODUCTO, estos sin costos
  (PERM_EXPEDIENTE_COSTOS_VER) y sin valor cotizado. Costos: JEFE_PRODUCCION, COSTOS y GESTION_CALIDAD.
- El rol se lee de la base en cada petición, no del token.

SQLite en memoria con override de get_db; aplicación FastAPI mínima con la misma dependencia global
y el mismo middleware que app.main (no se importa app.main).
"""
import json
import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import costos, ordenes, proyectos
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import (
    EstadoOPEnum, OrdenProduccion, OTDetalle, PedidoDetalle, Permiso, Plano, Producto, Proyecto, Rol, RolPermiso,
    Usuario,
)
from app.services import acceso_bd
from tests.ayudantes_usuarios import datos_usuario, id_prueba

MEC, SER = roles.LIDER_MECANIZADOS, roles.LIDER_SERVICIOS
ROLES_PRUEBA = [
    roles.ADMIN, roles.VENTAS, roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD, MEC, SER,
    roles.DIBUJANTE, roles.LIDER_DISENO, roles.CALIDAD_PRODUCTO, roles.DIRECTOR_PRODUCCION, roles.OPERARIO,
]
# Como la migración 25
PERMISOS = {
    acceso_bd.PERMISO_VALOR_COTIZADO: [roles.VENTAS, roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD],
    acceso_bd.PERMISO_COSTOS: [roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD],
}
VALOR = 4321000
PEDIDO_OK = [roles.VENTAS, roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD, MEC, SER]
PEDIDO_NO = [roles.ADMIN, roles.DIBUJANTE, roles.LIDER_DISENO, roles.CALIDAD_PRODUCTO, roles.DIRECTOR_PRODUCCION,
             roles.OPERARIO]


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

    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.add_middleware(acceso_bd.OcultarCamposPorRol)
    app.include_router(proyectos.router, prefix="/api/v1/proyectos")
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")
    app.include_router(costos.router, prefix="/api/v1/costos")
    app.dependency_overrides[get_db] = _get_db
    with Sesion() as s:
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in ROLES_PRUEBA)
        s.add_all(Permiso(id_permiso=permiso, modulo="PRUEBA") for permiso in PERMISOS)
        s.add_all(RolPermiso(id_rol=rol, id_permiso=permiso) for permiso, lista in PERMISOS.items() for rol in lista)
        s.add_all(Usuario(**datos_usuario(rol.lower()), password_hash="!", nombre_completo=rol, id_rol=rol)
                  for rol in ROLES_PRUEBA)
        pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido="PED-DIV-1", codigo_proyecto="PED-DIV-1",
                          cliente_nombre="Cliente ficticio", requisitos_cliente="Según plano", confirmado=True,
                          cotizacion_total=VALOR)
        producto = Producto(id_producto=uuid.uuid4(), codigo_rn="RN-DIV-1", descripcion="Brida ficticia")
        s.add_all([pedido, producto])
        s.flush()
        linea = PedidoDetalle(pedido_id=pedido.id_proyecto, codigo_producto="RN-DIV-1", descripcion="Brida",
                              cantidad_solicitada=2, unidad="UN")
        plano = Plano(codigo_plano="PLN-DIV-1", id_producto=producto.id_producto, id_proyecto=pedido.id_proyecto,
                      unidad_planta="Mecanizados")
        s.add_all([linea, plano])
        s.flush()
        s.add(OTDetalle(ot_id=plano.id_plano, detalle_pedido_id=linea.detalle_id, cantidad_asignada=2))
        # TERMINADA en Mecanizados: la ven el líder de Mecanizados y CALIDAD_PRODUCTO (inspección)
        s.add(OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op="OP-DIV-1", cantidad_fabricar=2,
                              unidad_actual="MECANIZADOS", estado=EstadoOPEnum.TERMINADA, id_plano=plano.id_plano,
                              id_producto=producto.id_producto, id_detalle_pedido=linea.detalle_id))
        s.commit()
        id_pedido = pedido.id_proyecto
    with TestClient(app) as client:
        yield client, id_pedido
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol, rol_en_token=None):
    t = create_access_token({"sub": str(id_prueba(rol.lower())), "rol": rol_en_token or rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def expediente_pedido(client, id_pedido, rol, **kwargs):
    return client.get(f"/api/v1/proyectos/{id_pedido}/expediente", headers=token(rol, **kwargs))


# --- Expediente del pedido ----------------------------------------------------------------------

@pytest.mark.parametrize("rol", PEDIDO_OK)
def test_el_expediente_del_pedido_lo_abren_sus_seis_roles(ctx, rol):
    client, id_pedido = ctx
    respuesta = expediente_pedido(client, id_pedido, rol)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["numero_pedido"] == "PED-DIV-1"


@pytest.mark.parametrize("rol", PEDIDO_NO)
def test_los_demas_roles_reciben_403_en_el_expediente_del_pedido(ctx, rol):
    client, id_pedido = ctx
    assert expediente_pedido(client, id_pedido, rol).status_code == 403


def test_el_rol_del_expediente_del_pedido_se_lee_de_la_base(ctx):
    client, id_pedido = ctx
    # El token dice JEFE_PRODUCCION, pero el usuario es DIBUJANTE en la base
    assert expediente_pedido(client, id_pedido, roles.DIBUJANTE, rol_en_token=roles.JEFE_PRODUCCION).status_code == 403


@pytest.mark.parametrize("rol, ve_valor", [
    (roles.VENTAS, True), (roles.JEFE_PRODUCCION, True), (roles.COSTOS, True), (roles.GESTION_CALIDAD, True),
    (MEC, False), (SER, False),
])
def test_valor_cotizado_en_el_pedido_solo_con_el_permiso(ctx, rol, ve_valor):
    client, id_pedido = ctx
    datos = expediente_pedido(client, id_pedido, rol).json()

    assert ("valor_total_cotizado" in datos) is ve_valor
    assert (str(VALOR) in json.dumps(datos)) is ve_valor


def test_ventas_no_ve_numeros_de_op_ni_produccion(ctx):
    client, id_pedido = ctx
    ventas = expediente_pedido(client, id_pedido, roles.VENTAS).json()
    jefe = expediente_pedido(client, id_pedido, roles.JEFE_PRODUCCION).json()

    texto = json.dumps(ventas)
    assert "OP-DIV" not in texto and "PLN-DIV-1" not in texto
    assert not {"ordenes_produccion", "planos", "centro_costo_imputado"} & set(ventas)
    for linea in ventas["pedido_detalles"]:
        assert not {"ot_detalles", "ordenes_produccion", "estado_produccion", "porcentaje_avance"} & set(linea)
    # Control: el Jefe sí ve las OP del pedido
    assert "OP-DIV-1" in json.dumps(jefe) and jefe["ordenes_produccion"]


# --- Expediente de OP ---------------------------------------------------------------------------

@pytest.mark.parametrize("rol", [roles.DIBUJANTE, roles.LIDER_DISENO, roles.CALIDAD_PRODUCTO])
def test_diseno_y_calidad_de_producto_abren_el_expediente_de_op_sin_costos_ni_valor(ctx, rol):
    client, _ = ctx
    respuesta = client.get("/api/v1/ordenes/expediente/OP-DIV-1", headers=token(rol))

    assert respuesta.status_code == 200, respuesta.text
    assert str(VALOR) not in respuesta.text
    assert client.get("/api/v1/costos/liquidar/OP-DIV-1", headers=token(rol)).status_code == 403


@pytest.mark.parametrize("rol", [roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD])
def test_los_costos_del_expediente_de_op(ctx, rol):
    client, _ = ctx
    assert client.get("/api/v1/costos/liquidar/OP-DIV-1", headers=token(rol)).status_code == 200


@pytest.mark.parametrize("rol", [roles.VENTAS, roles.OPERARIO])
def test_ventas_y_operario_no_abren_el_expediente_de_op(ctx, rol):
    client, _ = ctx
    assert client.get("/api/v1/ordenes/expediente/OP-DIV-1", headers=token(rol)).status_code == 403
