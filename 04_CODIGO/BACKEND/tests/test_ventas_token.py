# tests/test_ventas_token.py
"""
Paso de permisos en Ventas: los GET de cotizaciones (el detalle expone los datos del cliente) y
las rutas de pedidos (listado, expediente, creación y edición) exigen token, sin restricción de
rol nueva. 401 sin token o con token inválido y respuesta correcta con token válido; sin token
no se crea ni se modifica ningún pedido.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con los routers de
cotizaciones y proyectos (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import cotizaciones, proyectos
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Cotizacion, EstadoCotizacionEnum, Proyecto, SocioNegocio

PEDIDO = {
    "numero_pedido": "PED-TOKEN-1",
    "cliente_nombre": "Cliente Token SAS",
    "requisitos_cliente": "Sin especificación",
    "detalles": [{"descripcion": "Eje", "cantidad_solicitada": 1}],
}


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    s = Sesion()
    socio = SocioNegocio(
        id_socio=uuid.uuid4(), codigo_socio="900222333", nit_cedula="900222333-1",
        razon_social="Cliente con datos", es_cliente=True, email="compras@cliente.test",
    )
    cotizacion = Cotizacion(
        id_cotizacion=uuid.uuid4(), id_socio=socio.id_socio, numero_cotizacion="COT-TOKEN-1",
        estado=EstadoCotizacionEnum.BORRADOR,
    )
    pedido = Proyecto(
        id_proyecto=uuid.uuid4(), numero_pedido="PED-EXISTENTE", codigo_proyecto="PED-EXISTENTE",
        cliente_nombre="Cliente existente", requisitos_cliente="Sin especificación", confirmado=False,
    )
    s.add_all([socio, cotizacion, pedido])
    s.commit()
    ids = {"cotizacion": cotizacion.id_cotizacion, "pedido": pedido.id_proyecto}
    s.close()

    app = FastAPI()
    app.include_router(cotizaciones.router, prefix="/api/v1")
    app.include_router(proyectos.router, prefix="/api/v1/proyectos")

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)
    yield client, Sesion, ids
    client.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol="VENTAS"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def rutas(ids):
    return [
        ("get", "/api/v1/ventas/cotizaciones/", None, 200),
        ("get", f"/api/v1/ventas/cotizaciones/{ids['cotizacion']}", None, 200),
        ("get", "/api/v1/proyectos/", None, 200),
        ("get", f"/api/v1/proyectos/{ids['pedido']}/expediente", None, 200),
        ("post", "/api/v1/proyectos/", PEDIDO, 201),
        ("patch", f"/api/v1/proyectos/{ids['pedido']}", {"cliente_nombre": "Cliente editado"}, 200),
    ]


@pytest.mark.parametrize("indice", range(6), ids=["cot_lista", "cot_detalle", "ped_lista", "ped_expediente", "ped_crear", "ped_editar"])
@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer token-que-no-es-un-jwt"}],
    ids=["sin_cabecera", "token_invalido"],
)
def test_sin_token_valido_responde_401(ctx, indice, cabeceras):
    client, _, ids = ctx
    metodo, ruta, cuerpo, _ = rutas(ids)[indice]

    respuesta = getattr(client, metodo)(ruta, headers=cabeceras, **({"json": cuerpo} if cuerpo else {}))

    assert respuesta.status_code == 401


@pytest.mark.parametrize("indice", range(6), ids=["cot_lista", "cot_detalle", "ped_lista", "ped_expediente", "ped_crear", "ped_editar"])
def test_con_token_valido_responde(ctx, indice):
    client, _, ids = ctx
    metodo, ruta, cuerpo, esperado = rutas(ids)[indice]

    respuesta = getattr(client, metodo)(ruta, headers=token(), **({"json": cuerpo} if cuerpo else {}))

    assert respuesta.status_code == esperado, respuesta.text


def test_el_detalle_de_cotizacion_no_expone_al_cliente_sin_token(ctx):
    client, _, ids = ctx

    respuesta = client.get(f"/api/v1/ventas/cotizaciones/{ids['cotizacion']}")

    assert respuesta.status_code == 401
    assert "compras@cliente.test" not in respuesta.text
    assert "900222333" not in respuesta.text


def test_sin_token_no_se_crea_ni_modifica_ningun_pedido(ctx):
    client, Sesion, ids = ctx

    assert client.post("/api/v1/proyectos/", json=PEDIDO).status_code == 401
    assert client.patch(f"/api/v1/proyectos/{ids['pedido']}", json={"cliente_nombre": "Intruso"}).status_code == 401

    with Sesion() as s:
        assert s.query(Proyecto).count() == 1
        assert s.get(Proyecto, ids["pedido"]).cliente_nombre == "Cliente existente"
