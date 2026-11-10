# tests/test_mantenimiento_token.py
"""
Paso de permisos en Mantenimiento: las rutas de overhaul a clientes (/mantenimientos) y de
mantenimiento de planta (/mantenimientos/planta) exigen token, sin restricción de rol nueva.
401 sin token o con token inválido; con token válido los GET responden 200 y las escrituras
llegan a su validación normal (no 401).

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con los dos routers,
montados como en app.main (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import mantenimiento_planta, mantenimientos
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import EquipoPlanta, MantenimientoMaquina

BASE = "/api/v1/mantenimientos"
OTRO = str(uuid.uuid4())
LECTURAS = [
    f"{BASE}/monitor-kits",
    f"{BASE}/planta/equipos",
    f"{BASE}/planta/ordenes",
]
ESCRITURAS = [
    ("post", f"{BASE}/nuevo"),
    ("patch", f"{BASE}/999"),
    ("post", f"{BASE}/999/piezas/carga-masiva"),
    ("patch", f"{BASE}/999/confirmar-cotizacion"),
    ("post", f"{BASE}/planta/equipos"),
    ("patch", f"{BASE}/planta/equipos/{OTRO}"),
    ("post", f"{BASE}/planta/ordenes"),
    ("post", f"{BASE}/planta/ordenes/{OTRO}/repuestos"),
    ("patch", f"{BASE}/planta/ordenes/{OTRO}/estado"),
]
TODAS = [("get", r) for r in LECTURAS] + [("get", f"{BASE}/999/piezas")] + ESCRITURAS


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
    app.include_router(mantenimientos.router, prefix=BASE)
    app.include_router(mantenimiento_planta.router, prefix=BASE)

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


@pytest.mark.parametrize("metodo, ruta", TODAS, ids=[f"{m}:{r}" for m, r in TODAS])
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


@pytest.mark.parametrize("metodo, ruta", ESCRITURAS + [("get", f"{BASE}/999/piezas")], ids=lambda x: str(x))
def test_escrituras_con_token_pasan_la_autenticacion(ctx, metodo, ruta):
    client, _ = ctx

    # Cuerpo vacío o id inexistente: con token la petición llega al endpoint (404 o 422), no 401
    assert llamar(client, metodo, ruta, token()).status_code in (200, 404, 409, 422)


def test_sin_token_no_se_crea_nada(ctx):
    client, Sesion = ctx

    assert client.post(f"{BASE}/planta/equipos", json={"codigo": "EQ-X", "nombre": "Torno"}).status_code == 401
    assert client.post(f"{BASE}/nuevo", json={"cliente": "X"}).status_code == 401

    with Sesion() as s:
        assert s.query(EquipoPlanta).count() == 0
        assert s.query(MantenimientoMaquina).count() == 0
