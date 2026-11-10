# tests/test_produccion_token.py
"""
Paso de permisos en Producción: la cola de planta y los sublotes (/operaciones), el puesto CNC
(setup, mecanizado, pausa), la carga de máquinas y el listado de OP (/ordenes/) exigen token,
sin restricción de rol nueva. 401 sin token o con token inválido; con token válido los GET
responden 200 y las escrituras llegan a su validación normal (no 401).

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con los routers de
producción (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import carga_maquinas, ordenes, produccion
from app.api.v1.endpoints.produccion import cola_router
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models_produccion import SubLoteOperacion

SUBLOTE = str(uuid.uuid4())
LECTURAS = [
    "/api/v1/operaciones/sublotes",
    "/api/v1/produccion/carga-maquinas",
    "/api/v1/ordenes/",
]
ESCRITURAS = [
    ("post", "/api/v1/operaciones/setup/iniciar"),
    ("post", "/api/v1/operaciones/mecanizado/conmutar"),
    ("post", "/api/v1/operaciones/pausa/turno"),
    ("post", "/api/v1/operaciones/sublotes/reordenar"),
    ("patch", f"/api/v1/operaciones/sublotes/{SUBLOTE}/estado"),
    ("post", "/api/v1/operaciones/sublotes/crear"),
    ("post", "/api/v1/operaciones/sublotes/finalizar"),
    ("patch", f"/api/v1/produccion/carga-maquinas/sublotes/{SUBLOTE}/maquina"),
]
TODAS = [("get", ruta) for ruta in LECTURAS] + ESCRITURAS


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
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")
    app.include_router(produccion.router, prefix="/api/v1/operaciones")
    app.include_router(cola_router, prefix="/api/v1/operaciones")
    app.include_router(carga_maquinas.router, prefix="/api/v1/produccion")

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


def token(rol="PRODUCCION"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def llamar(client, metodo, ruta, cabeceras):
    extra = {} if metodo == "get" else {"json": {}}
    return getattr(client, metodo)(ruta, headers=cabeceras, **extra)


@pytest.mark.parametrize("metodo, ruta", TODAS, ids=[r for _, r in TODAS])
@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer token-que-no-es-un-jwt"}],
    ids=["sin_cabecera", "token_invalido"],
)
def test_sin_token_valido_responde_401(ctx, metodo, ruta, cabeceras):
    client, _ = ctx

    assert llamar(client, metodo, ruta, cabeceras).status_code == 401


@pytest.mark.parametrize("ruta", LECTURAS)
def test_lecturas_con_token_responden_200(ctx, ruta):
    client, _ = ctx

    respuesta = client.get(ruta, headers=token())

    assert respuesta.status_code == 200, respuesta.text


@pytest.mark.parametrize("metodo, ruta", ESCRITURAS, ids=[r for _, r in ESCRITURAS])
def test_escrituras_con_token_pasan_la_autenticacion(ctx, metodo, ruta):
    client, _ = ctx

    # Cuerpo vacío: con token la petición llega a la validación del endpoint (422 o 404), no 401
    assert llamar(client, metodo, ruta, token()).status_code in (404, 409, 422)


def test_sin_token_no_se_crea_ningun_sublote(ctx):
    client, Sesion = ctx
    cuerpo = {"codigo_op": "OP-X", "id_plano": str(uuid.uuid4()), "secuencia_paso": 10, "cantidad_asignada": 1,
              "maquina": "CNC-1", "operario_nombre": "Operario"}

    assert client.post("/api/v1/operaciones/sublotes/crear", json=cuerpo).status_code == 401

    with Sesion() as s:
        assert s.query(SubLoteOperacion).count() == 0
