# tests/test_costos_token.py
"""
Paso 1 de permisos: las 7 rutas de /costos exigen token (sin restricción de rol todavía).
401 sin token en todas y respuesta correcta con token válido en cada una.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router
de costos (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import costos
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import CentroTrabajo, OrdenProduccion, Proyecto

CODIGO_OP = "OP-COS-1"
RUTAS = [
    ("get", f"/api/v1/costos/liquidar/{CODIGO_OP}"),
    ("get", "/api/v1/costos/oee"),
    ("get", f"/api/v1/costos/op/{CODIGO_OP}"),
    ("post", f"/api/v1/costos/op/{CODIGO_OP}/consumos"),
    ("post", f"/api/v1/costos/op/{CODIGO_OP}/servicios-terceros"),
    ("post", "/api/v1/costos/centros-trabajo"),
    ("put", "/api/v1/costos/centros-trabajo/CT-COS-1"),
]
CENTRO = {"codigo_centro": "CT-COS-1", "tarifa_hora_mecanizado": "85000", "tarifa_hora_setup": "60000"}


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
    app.include_router(costos.router, prefix="/api/v1/costos")

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)
    s = Sesion()
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(), numero_pedido="PED-COS-1", codigo_proyecto="PRY-COS-1",
        cliente_nombre="Cliente Ficticio SAS", requisitos_cliente="Según plano", confirmado=True,
    )
    s.add_all([
        proyecto,
        OrdenProduccion(id_op=uuid.uuid4(), id_proyecto=proyecto.id_proyecto, codigo_op=CODIGO_OP, cantidad_fabricar=1),
    ])
    s.commit()
    s.close()
    yield client, Sesion
    client.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol="ADMIN"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS)
@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer token-que-no-es-un-jwt"}],
    ids=["sin_cabecera", "token_invalido"],
)
def test_sin_token_valido_responde_401(ctx, metodo, ruta, cabeceras):
    client, _ = ctx

    respuesta = getattr(client, metodo)(ruta, headers=cabeceras)

    assert respuesta.status_code == 401


def test_sin_token_no_se_crea_el_centro_de_trabajo(ctx):
    client, Sesion = ctx

    assert client.post("/api/v1/costos/centros-trabajo", json=CENTRO).status_code == 401

    s = Sesion()
    assert s.query(CentroTrabajo).count() == 0
    s.close()


@pytest.mark.parametrize("ruta", [f"/api/v1/costos/liquidar/{CODIGO_OP}", "/api/v1/costos/oee", f"/api/v1/costos/op/{CODIGO_OP}"])
def test_consultas_con_token_responden_200(ctx, ruta):
    client, _ = ctx

    respuesta = client.get(ruta, headers=token())

    assert respuesta.status_code == 200, respuesta.text


def test_registrar_consumo_con_token(ctx):
    client, _ = ctx

    respuesta = client.post(
        f"/api/v1/costos/op/{CODIGO_OP}/consumos",
        json={"codigo_material": "MAT-1045", "descripcion_material": "Barra AISI 1045", "cantidad": 2,
              "unidad_medida": "KG", "costo_unitario": "12000"},
        headers=token(),
    )

    assert respuesta.status_code == 201, respuesta.text


def test_registrar_servicio_tercero_con_token(ctx):
    client, _ = ctx

    respuesta = client.post(
        f"/api/v1/costos/op/{CODIGO_OP}/servicios-terceros",
        json={"proveedor": "Tratamientos Andinos", "descripcion": "Temple", "numero_factura": "FE-101", "costo": "350000"},
        headers=token(),
    )

    assert respuesta.status_code == 201, respuesta.text


def test_crear_y_actualizar_centro_de_trabajo_con_token(ctx):
    client, Sesion = ctx

    creado = client.post("/api/v1/costos/centros-trabajo", json=CENTRO, headers=token())
    assert creado.status_code == 201, creado.text

    actualizado = client.put(
        "/api/v1/costos/centros-trabajo/CT-COS-1",
        json={**CENTRO, "tarifa_hora_mecanizado": "90000"},
        headers=token(),
    )

    assert actualizado.status_code == 200, actualizado.text
    s = Sesion()
    assert float(s.query(CentroTrabajo).one().tarifa_hora_mecanizado) == 90000
    s.close()
