# tests/test_catalogos_token.py
"""
Paso de permisos en catálogos: GET /inventario/categorias y GET /materiales/ exigen token, sin
restricción de rol nueva (eran las últimas rutas de datos abiertas). 401 sin token o con token
inválido y 200 con token válido.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con los routers de
inventario y materiales (no se importa app.main) para no tocar ninguna base real.
"""
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import inventario, materiales
from app.core.security import create_access_token
from app.db.database import Base, get_db

RUTAS = ["/api/v1/inventario/categorias", "/api/v1/materiales/"]


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = FastAPI()
    app.include_router(inventario.router, prefix="/api/v1/inventario")
    app.include_router(materiales.router, prefix="/api/v1/materiales")

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as cliente:
        yield cliente
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol="ALMACEN"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.parametrize("ruta", RUTAS)
@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer token-que-no-es-un-jwt"}],
    ids=["sin_cabecera", "token_invalido"],
)
def test_sin_token_valido_responde_401(client, ruta, cabeceras):
    assert client.get(ruta, headers=cabeceras).status_code == 401


@pytest.mark.parametrize("ruta", RUTAS)
def test_con_token_valido_responde_200(client, ruta):
    respuesta = client.get(ruta, headers=token())

    assert respuesta.status_code == 200, respuesta.text
