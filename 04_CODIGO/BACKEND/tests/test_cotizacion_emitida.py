# tests/test_cotizacion_emitida.py
"""
Enviar al cliente una cotización en BORRADOR la deja en EMITIDA (antes respondía 500 porque
EMITIDA no existía en EstadoCotizacionEnum). Los demás estados no cambian al reenviar.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router de
cotizaciones (no se importa app.main) para no tocar ninguna base real. La migración 23 sobre
PostgreSQL se prueba en test_cotizacion_emitida_pg.py.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import cotizaciones
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Cotizacion, EstadoCotizacionEnum, SocioNegocio

CORREO = {"destinatario": "compras@cliente.test", "asunto": "Oferta", "mensaje": "Adjuntamos la oferta."}


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = FastAPI()
    app.include_router(cotizaciones.router, prefix="/api/v1")

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)
    yield client, Sesion
    client.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol="VENTAS"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_cotizacion(Sesion, estado):
    s = Sesion()
    socio = SocioNegocio(
        id_socio=uuid.uuid4(), codigo_socio="900111222", nit_cedula="900111222-3",
        razon_social="Cliente de prueba", es_cliente=True,
    )
    cotizacion = Cotizacion(
        id_cotizacion=uuid.uuid4(), id_socio=socio.id_socio, numero_cotizacion="COT-EMI-1", estado=estado,
    )
    s.add_all([socio, cotizacion])
    s.commit()
    s.close()
    return cotizacion


def estado_guardado(Sesion, id_cotizacion):
    s = Sesion()
    estado = s.get(Cotizacion, id_cotizacion).estado
    s.close()
    return estado


def test_el_enum_conserva_los_estados_y_agrega_emitida():
    assert [e.value for e in EstadoCotizacionEnum] == ["BORRADOR", "EMITIDA", "ENVIADA", "APROBADA", "RECHAZADA"]


def test_enviar_borrador_al_cliente_la_deja_emitida(ctx):
    client, Sesion = ctx
    cotizacion = crear_cotizacion(Sesion, EstadoCotizacionEnum.BORRADOR)

    respuesta = client.post(
        f"/api/v1/ventas/cotizaciones/{cotizacion.id_cotizacion}/enviar-cliente", json=CORREO, headers=token(),
    )

    assert respuesta.status_code == 200, respuesta.text
    assert estado_guardado(Sesion, cotizacion.id_cotizacion) == EstadoCotizacionEnum.EMITIDA


@pytest.mark.parametrize(
    "estado",
    [EstadoCotizacionEnum.EMITIDA, EstadoCotizacionEnum.ENVIADA, EstadoCotizacionEnum.APROBADA, EstadoCotizacionEnum.RECHAZADA],
)
def test_reenviar_no_cambia_un_estado_que_no_es_borrador(ctx, estado):
    client, Sesion = ctx
    cotizacion = crear_cotizacion(Sesion, estado)

    respuesta = client.post(
        f"/api/v1/ventas/cotizaciones/{cotizacion.id_cotizacion}/enviar-cliente", json=CORREO, headers=token(),
    )

    assert respuesta.status_code == 200, respuesta.text
    assert estado_guardado(Sesion, cotizacion.id_cotizacion) == estado
