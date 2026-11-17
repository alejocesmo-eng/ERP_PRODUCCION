# tests/test_indicadores.py
"""
GET /api/v1/indicadores/: responde 200 y KPI-OP-01 cuenta las OP con reserva_stock_100
(antes consultaba OrdenProduccion.stock_disponible_100, que no existe, y respondía 500).

SQLite en memoria con override de get_db y token firmado en la prueba; aplicación FastAPI
mínima con el router de indicadores. No toca ninguna base real.
"""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import indicadores
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import OrdenProduccion, Proyecto
from tests.ayudantes_usuarios import id_prueba


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, expire_on_commit=False)

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI()
    app.include_router(indicadores.router, prefix="/api/v1/indicadores")
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


def token():
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(id_prueba('gestioncal')), 'rol': 'GESTION_CALIDAD'})}"}


def crear_ops(Sesion, reservas):
    with Sesion() as s:
        proyecto = Proyecto(
            id_proyecto=uuid.uuid4(),
            numero_pedido="PED-KPI-01",
            codigo_proyecto="PRY-KPI-01",
            cliente_nombre="Cliente de prueba",
            requisitos_cliente="Sin requisitos",
            confirmado=True,
        )
        s.add(proyecto)
        s.flush()
        for indice, reserva in enumerate(reservas):
            s.add(OrdenProduccion(
                id_proyecto=proyecto.id_proyecto,
                codigo_op=f"OP-KPI-{indice}",
                cantidad_fabricar=1,
                reserva_stock_100=reserva,
            ))
        s.commit()


def kpi(respuesta, codigo):
    return next(item for item in respuesta.json()["kpis"] if item["codigo_kpi"] == codigo)


def test_indicadores_responde_200_sin_datos(ctx):
    client, _ = ctx

    respuesta = client.get("/api/v1/indicadores/", headers=token())

    assert respuesta.status_code == 200
    assert {item["codigo_kpi"] for item in respuesta.json()["kpis"]} == {"KPI-VEN-01", "KPI-DSN-01", "KPI-OP-01", "KPI-NC-01"}


def test_kpi_op_cuenta_las_op_con_reserva_stock_100(ctx):
    client, Sesion = ctx
    crear_ops(Sesion, [True, False, False, True])

    respuesta = client.get("/api/v1/indicadores/", headers=token())

    assert respuesta.status_code == 200
    assert kpi(respuesta, "KPI-OP-01")["valor_actual"] == 50.0
    assert respuesta.json()["resumen_general"]["total_ordenes_produccion"] == 4


def test_indicadores_exige_token(ctx):
    client, _ = ctx

    assert client.get("/api/v1/indicadores/").status_code == 401
