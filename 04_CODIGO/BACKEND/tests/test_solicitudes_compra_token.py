# tests/test_solicitudes_compra_token.py
"""
Paso 1 de permisos: las 8 rutas de /solicitudes-compra exigen token (sin restricción de rol
todavía). 401 sin token en todas y respuesta correcta con token válido en cada una.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router de
compras (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import solicitudes_compra
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import EjecucionMRP, RequisicionMRP, SolicitudCompra

RUTAS = [
    ("post", "/api/v1/solicitudes-compra/mrp/retales"),
    ("post", "/api/v1/solicitudes-compra/mrp/ejecutar"),
    ("get", "/api/v1/solicitudes-compra/mrp/requisiciones"),
    ("patch", "/api/v1/solicitudes-compra/mrp/requisiciones/{id}"),
    ("get", "/api/v1/solicitudes-compra/"),
    ("get", "/api/v1/solicitudes-compra/verificar-pieza/OP-1/PLN-1"),
    ("post", "/api/v1/solicitudes-compra/"),
    ("patch", "/api/v1/solicitudes-compra/{id}"),
]


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
    app.include_router(solicitudes_compra.router, prefix="/api/v1/solicitudes-compra")

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


def token(rol="ALMACEN"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_requisicion_con_pr(Sesion):
    s = Sesion()
    ejecucion = EjecucionMRP(id_ejecucion=uuid.uuid4())
    solicitud = SolicitudCompra(
        id_solicitud=uuid.uuid4(), numero_solicitud="PR-MRP-1", nombre_item="Barra AISI 1045",
        estado_bom="SOLICITADO",
    )
    requisicion = RequisicionMRP(
        id_requisicion=uuid.uuid4(), id_ejecucion=ejecucion.id_ejecucion, codigo_material="MAT-1045",
        especificacion="Barra AISI 1045", unidad_medida="KG", demanda_bruta=10, stock_libre=0,
        retales_disponibles=0, compras_en_transito=0, stock_reservado=0, requerimiento_neto=10,
        solicitud_id=solicitud.id_solicitud,
    )
    s.add_all([ejecucion, solicitud, requisicion])
    s.commit()
    s.close()
    return requisicion


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS)
@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer token-que-no-es-un-jwt"}],
    ids=["sin_cabecera", "token_invalido"],
)
def test_sin_token_valido_responde_401(ctx, metodo, ruta, cabeceras):
    client, _ = ctx

    respuesta = getattr(client, metodo)(ruta.format(id=uuid.uuid4()), headers=cabeceras)

    assert respuesta.status_code == 401


def test_sin_token_no_se_crea_la_solicitud(ctx):
    client, Sesion = ctx

    respuesta = client.post("/api/v1/solicitudes-compra/", json={"items": [{"descripcion": "Barra", "cantidad": 2}]})

    assert respuesta.status_code == 401
    s = Sesion()
    assert s.query(SolicitudCompra).count() == 0
    s.close()


@pytest.mark.parametrize(
    "ruta",
    ["/mrp/requisiciones", "/", "/verificar-pieza/OP-1/PLN-1"],
)
def test_consultas_con_token_responden_200(ctx, ruta):
    client, _ = ctx

    respuesta = client.get(f"/api/v1/solicitudes-compra{ruta}", headers=token())

    assert respuesta.status_code == 200, respuesta.text


def test_crear_y_actualizar_solicitud_con_token(ctx):
    client, _ = ctx

    creada = client.post(
        "/api/v1/solicitudes-compra/",
        json={"items": [{"descripcion": "Barra AISI 1045", "cantidad": 2, "unidad": "KG"}]},
        headers=token("DISENO"),
    )
    assert creada.status_code == 201, creada.text

    actualizada = client.patch(
        f"/api/v1/solicitudes-compra/{creada.json()['id_solicitud']}",
        json={"estado_bom": "EN_COMPRA"},
        headers=token(),
    )

    assert actualizada.status_code == 200, actualizada.text
    assert actualizada.json()["estado_bom"] == "EN_COMPRA"


def test_registrar_retal_con_token(ctx):
    client, _ = ctx

    respuesta = client.post(
        "/api/v1/solicitudes-compra/mrp/retales",
        json={"codigo_retal": "RET-T-1", "codigo_material": "MAT-1045", "cantidad_disponible": 1.5},
        headers=token(),
    )

    assert respuesta.status_code == 201, respuesta.text


def test_ejecutar_mrp_con_token(ctx):
    client, _ = ctx

    respuesta = client.post("/api/v1/solicitudes-compra/mrp/ejecutar", headers=token())

    assert respuesta.status_code == 201, respuesta.text


def test_actualizar_requisicion_mrp_con_token(ctx):
    client, _ = ctx
    requisicion = crear_requisicion_con_pr(ctx[1])

    respuesta = client.patch(
        f"/api/v1/solicitudes-compra/mrp/requisiciones/{requisicion.id_requisicion}",
        json={"estado_bom": "EN_COMPRA"},
        headers=token(),
    )

    assert respuesta.status_code == 200, respuesta.text
