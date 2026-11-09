# tests/test_planos_patch_token.py
"""
PATCH /planos/{id} exige token (cambios de estado de Diseño y cronómetro).

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router
de planos (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import planos
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Plano


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # expire_on_commit=False: las pruebas leen los ids de los objetos tras cerrar la sesión
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = FastAPI()
    app.include_router(planos.router, prefix="/api/v1/planos")

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


def token(rol="DISENO"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_plano(Sesion):
    s = Sesion()
    plano = Plano(
        id_plano=uuid.uuid4(),
        codigo_plano="PLN-TOKEN-01",
        version="v0.1",
        estado_diseno="PLANIFICADA",
    )
    s.add(plano)
    s.commit()
    s.close()
    return plano


def leer_plano(Sesion, id_plano):
    s = Sesion()
    try:
        return s.get(Plano, id_plano)
    finally:
        s.close()


@pytest.mark.parametrize(
    "cabeceras",
    [
        {},
        {"Authorization": "Bearer token-que-no-es-un-jwt"},
    ],
    ids=["sin_cabecera", "token_invalido"],
)
def test_patch_plano_sin_token_valido_da_401_y_no_cambia_el_plano(ctx, cabeceras):
    client, Sesion = ctx
    plano = crear_plano(Sesion)

    respuesta = client.patch(
        f"/api/v1/planos/{plano.id_plano}",
        json={"estado_diseno": "EN_DISENO", "observaciones_tecnicas": "No debe guardarse"},
        headers=cabeceras,
    )

    assert respuesta.status_code == 401
    guardado = leer_plano(Sesion, plano.id_plano)
    assert guardado.estado_diseno == "PLANIFICADA"
    assert guardado.observaciones_tecnicas is None


@pytest.mark.parametrize("rol", ["DISENO", "PRODUCCION"])
def test_patch_plano_con_token_guarda_el_cambio(ctx, rol):
    client, Sesion = ctx
    plano = crear_plano(Sesion)

    respuesta = client.patch(
        f"/api/v1/planos/{plano.id_plano}",
        json={"observaciones_tecnicas": "Chaflán 1x45 en ambos extremos"},
        headers=token(rol),
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["observaciones_tecnicas"] == "Chaflán 1x45 en ambos extremos"
    assert leer_plano(Sesion, plano.id_plano).observaciones_tecnicas == "Chaflán 1x45 en ambos extremos"
