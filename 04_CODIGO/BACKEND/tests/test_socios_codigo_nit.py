# tests/test_socios_codigo_nit.py
"""
SCRUM-22: codigo_socio es el NIT solo con números (sin puntos, guion ni dígito de verificación).
El alta desde Datos Maestros lo asigna, la búsqueda por NIT lo devuelve y no se crean clientes
sin NIT, ni desde Datos Maestros ni desde una cotización.

SQLite en memoria con override de get_db (no toca ninguna base real). La migración 24 y el alta
sobre PostgreSQL se prueban en test_socios_codigo_nit_pg.py.
"""
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import cotizaciones, maestros
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import SocioNegocio
from app.services.socios import codigo_socio_o_none, normalizar_nit

CLIENTE = {
    "razon_social": "Cliente SCRUM-22",
    "es_cliente": True,
    "cuenta_contable_por_cobrar": "130505",
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

    app = FastAPI()
    app.include_router(maestros.router, prefix="/api/v1/maestros")
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


def token(rol="ADMIN"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.parametrize("nit, codigo", [
    ("800.123.456-1", "800123456"),
    ("900123456-7", "900123456"),
    ("900123456 - 7", "900123456"),
    ("900123456", "900123456"),
    (" 1 020 304 050 ", "1020304050"),
    ("12345", "12345"),
])
def test_normaliza_el_nit_a_solo_numeros(nit, codigo):
    assert normalizar_nit(nit) == codigo


@pytest.mark.parametrize("nit", [None, "", "   ", "NIT-AB12CD34", "CLI-1001", "900-123-456", "900123456-77", "1234", "9" * 16])
def test_rechaza_nit_vacio_o_sin_formato(nit):
    with pytest.raises(ValueError):
        normalizar_nit(nit)
    assert codigo_socio_o_none(nit) is None


def test_alta_desde_datos_maestros_asigna_codigo_y_busqueda_por_nit_lo_devuelve(ctx):
    client, _ = ctx

    creado = client.post("/api/v1/maestros/socios", json={**CLIENTE, "nit_cedula": "800.123.456-1"}, headers=token())

    assert creado.status_code == 201, creado.text
    assert creado.json()["codigo_socio"] == "800123456"
    assert creado.json()["nit_cedula"] == "800.123.456-1"
    for nit in ("800123456", "800.123.456-1", "800123456-1"):
        encontrados = client.get("/api/v1/maestros/socios", params={"nit": nit}, headers=token("VENTAS"))
        assert encontrados.status_code == 200, encontrados.text
        assert [s["codigo_socio"] for s in encontrados.json()] == ["800123456"]
    assert client.get("/api/v1/maestros/socios", params={"nit": "900999999"}, headers=token()).json() == []


def test_busqueda_con_nit_sin_formato_responde_422(ctx):
    client, _ = ctx

    respuesta = client.get("/api/v1/maestros/socios", params={"nit": "CLI-1001"}, headers=token())

    assert respuesta.status_code == 422


@pytest.mark.parametrize("nit", ["", "NIT-AB12CD34", "1234"])
def test_alta_sin_nit_valido_se_rechaza(ctx, nit):
    client, Sesion = ctx

    respuesta = client.post("/api/v1/maestros/socios", json={**CLIENTE, "nit_cedula": nit}, headers=token())

    assert respuesta.status_code == 422
    with Sesion() as s:
        assert s.query(SocioNegocio).count() == 0


def test_el_mismo_nit_con_otro_formato_es_duplicado(ctx):
    client, _ = ctx
    assert client.post("/api/v1/maestros/socios", json={**CLIENTE, "nit_cedula": "900123456-7"}, headers=token()).status_code == 201

    repetido = client.post("/api/v1/maestros/socios", json={**CLIENTE, "nit_cedula": "900.123.456"}, headers=token())

    assert repetido.status_code == 409


def test_editar_el_nit_recalcula_el_codigo(ctx):
    client, _ = ctx
    creado = client.post("/api/v1/maestros/socios", json={**CLIENTE, "nit_cedula": "900123456"}, headers=token()).json()

    editado = client.put(
        f"/api/v1/maestros/socios/{creado['id_socio']}", json={**CLIENTE, "nit_cedula": "901.555.777-2"}, headers=token()
    )

    assert editado.status_code == 200, editado.text
    assert editado.json()["codigo_socio"] == "901555777"


def _cotizacion(**cliente):
    return {
        "razon_social": "Cliente desde cotización",
        "numero_cotizacion": "COT-S22-1",
        "posiciones": [{"descripcion": "Eje", "cantidad": 1, "precio_unitario": 1000}],
        **cliente,
    }


@pytest.mark.parametrize("cliente", [{}, {"codigo_cliente": "CLI-1001"}, {"nit": "NIT-AB12"}])
def test_cotizacion_no_crea_cliente_sin_nit(ctx, cliente):
    client, Sesion = ctx

    respuesta = client.post("/api/v1/ventas/cotizaciones/", json=_cotizacion(**cliente), headers=token("VENTAS"))

    assert respuesta.status_code == 400
    assert "sin NIT" in respuesta.json()["detail"]
    with Sesion() as s:
        assert s.query(SocioNegocio).count() == 0


def test_cotizacion_crea_cliente_con_codigo_nit_y_lo_reutiliza(ctx):
    client, Sesion = ctx

    primera = client.post("/api/v1/ventas/cotizaciones/", json=_cotizacion(nit="830.111.222-5"), headers=token("VENTAS"))
    segunda = client.post(
        "/api/v1/ventas/cotizaciones/",
        json={**_cotizacion(codigo_cliente="830111222"), "numero_cotizacion": "COT-S22-2"},
        headers=token("VENTAS"),
    )

    assert primera.status_code == 201, primera.text
    assert segunda.status_code == 201, segunda.text
    with Sesion() as s:
        socios = s.query(SocioNegocio).all()
        assert [(x.codigo_socio, x.nit_cedula) for x in socios] == [("830111222", "830.111.222-5")]
