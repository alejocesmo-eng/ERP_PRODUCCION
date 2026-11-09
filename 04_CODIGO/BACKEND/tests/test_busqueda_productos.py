# tests/test_busqueda_productos.py
"""
GET /maestros/productos sin base real: token, validación de parámetros, listado sin q y
503 cuando la base no tiene la migración 22. La búsqueda por similitud usa pg_trgm y
unaccent y se prueba en test_busqueda_productos_pg.py.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router
de maestros (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import maestros
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Producto

RUTA = "/api/v1/maestros/productos"


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[Producto.__table__])
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = FastAPI()
    app.include_router(maestros.router, prefix="/api/v1/maestros")

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)
    s = Sesion()
    s.add_all([
        Producto(id_producto=uuid.uuid4(), codigo_rn="RN-088-001-000003", descripcion="Buje de bronce", estado="ACTIVO"),
        Producto(id_producto=uuid.uuid4(), codigo_rn="RN-088-001-000001", descripcion="Eje de transmisión", estado="ACTIVO",
                 codigo_anterior="SKU-TOR-001", familia="Ejes"),
        Producto(id_producto=uuid.uuid4(), codigo_rn="RN-088-001-000002", descripcion="Polea obsoleta", estado="OBSOLETO"),
    ])
    s.commit()
    s.close()
    yield client
    client.close()
    Base.metadata.drop_all(engine, tables=[Producto.__table__])
    engine.dispose()


def token(rol="VENTAS"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def test_exige_token(ctx):
    assert ctx.get(RUTA).status_code == 401


@pytest.mark.parametrize("q", ["a", "  b  ", "x" * 101])
def test_rechaza_busquedas_fuera_de_longitud(ctx, q):
    respuesta = ctx.get(RUTA, params={"q": q}, headers=token())

    assert respuesta.status_code == 422
    assert "entre 2 y 100" in respuesta.json()["detail"]


@pytest.mark.parametrize("limite", [0, 51])
def test_rechaza_limite_fuera_de_rango(ctx, limite):
    assert ctx.get(RUTA, params={"limit": limite}, headers=token()).status_code == 422


@pytest.mark.parametrize("rol", ["VENTAS", "DISENO", "PRODUCCION", "ALMACEN"])
def test_sin_q_lista_los_activos_por_codigo_rn_para_cualquier_rol(ctx, rol):
    respuesta = ctx.get(RUTA, headers=token(rol))

    assert respuesta.status_code == 200
    productos = respuesta.json()
    assert [p["codigo_rn"] for p in productos] == ["RN-088-001-000001", "RN-088-001-000003"]
    assert set(productos[0]) == {
        "id_producto", "codigo_rn", "codigo_anterior", "descripcion", "familia", "estado", "similitud", "coincide_en",
    }
    assert (productos[0]["codigo_anterior"], productos[0]["familia"]) == ("SKU-TOR-001", "Ejes")
    assert productos[0]["similitud"] is None and productos[0]["coincide_en"] is None


def test_sin_q_con_obsoletos_y_limite(ctx):
    todos = ctx.get(RUTA, params={"incluir_obsoletos": True}, headers=token()).json()
    assert [p["codigo_rn"] for p in todos] == ["RN-088-001-000001", "RN-088-001-000002", "RN-088-001-000003"]

    primero = ctx.get(RUTA, params={"incluir_obsoletos": True, "limit": 1}, headers=token()).json()
    assert [p["codigo_rn"] for p in primero] == ["RN-088-001-000001"]


@pytest.mark.parametrize("q", ["", "   "])
def test_q_vacio_equivale_al_listado(ctx, q):
    respuesta = ctx.get(RUTA, params={"q": q}, headers=token())

    assert respuesta.status_code == 200
    assert [p["codigo_rn"] for p in respuesta.json()] == ["RN-088-001-000001", "RN-088-001-000003"]


def test_busqueda_sin_la_migracion_22_responde_503(ctx):
    # SQLite no tiene sgi_normalizar: equivale a una base PostgreSQL sin la migración 22
    respuesta = ctx.get(RUTA, params={"q": "eje"}, headers=token())

    assert respuesta.status_code == 503
    assert "22_MIGRACION_BUSQUEDA_PRODUCTOS" in respuesta.json()["detail"]
