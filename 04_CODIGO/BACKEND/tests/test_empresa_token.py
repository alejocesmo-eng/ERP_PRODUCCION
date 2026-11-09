# tests/test_empresa_token.py
"""
Paso 1 de permisos: las 2 rutas de /configuracion/empresa exigen token (sin restricción de
rol todavía). 401 sin token en ambas y respuesta correcta con token válido.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router de
empresa (no se importa app.main) para no tocar ninguna base real.
"""
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import empresa
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import EmpresaEmisora

RUTA = "/api/v1/configuracion/empresa/"


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
    app.include_router(empresa.router, prefix="/api/v1/configuracion/empresa")

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


def token(rol="ADMIN"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.parametrize("metodo", ["get", "put"])
@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer token-que-no-es-un-jwt"}],
    ids=["sin_cabecera", "token_invalido"],
)
def test_sin_token_valido_responde_401(ctx, metodo, cabeceras):
    client, _ = ctx

    respuesta = getattr(client, metodo)(RUTA, headers=cabeceras)

    assert respuesta.status_code == 401


def test_sin_token_no_se_crea_ni_modifica_la_empresa(ctx):
    client, Sesion = ctx

    assert client.get(RUTA).status_code == 401
    assert client.put(RUTA, json={"razon_social": "Intrusa S.A.S"}).status_code == 401

    s = Sesion()
    assert s.query(EmpresaEmisora).count() == 0
    s.close()


def test_obtener_empresa_con_token(ctx):
    client, _ = ctx

    respuesta = client.get(RUTA, headers=token())

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["codigo_empresa"] == "HD-01"


def test_actualizar_empresa_con_token(ctx):
    client, Sesion = ctx
    assert client.get(RUTA, headers=token()).status_code == 200

    respuesta = client.put(RUTA, json={"telefono": "(601) 555 0101"}, headers=token())

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["telefono"] == "(601) 555 0101"
    s = Sesion()
    assert s.query(EmpresaEmisora).one().telefono == "(601) 555 0101"
    s.close()
