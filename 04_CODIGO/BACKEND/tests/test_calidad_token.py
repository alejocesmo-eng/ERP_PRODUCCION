# tests/test_calidad_token.py
"""
Paso 1 de permisos: las 9 rutas de /calidad exigen token (sin restricción de rol todavía).
401 sin token en todas y respuesta correcta con token válido en cada una.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router
de calidad (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import calidad
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import AccionCAPA, EstadoOPEnum, NoConformidad, OrdenProduccion, Proyecto

RUTAS = [
    ("get", "/api/v1/calidad/ordenes-abiertas"),
    ("get", "/api/v1/calidad/inspeccion"),
    ("get", "/api/v1/calidad/ordenes-terminadas"),
    ("post", "/api/v1/calidad/inspeccionar"),
    ("get", "/api/v1/calidad/no-conformidades"),
    ("post", "/api/v1/calidad/no-conformidades"),
    ("get", "/api/v1/calidad/rnc"),
    ("post", "/api/v1/calidad/rnc/{id}/acciones-capa"),
    ("patch", "/api/v1/calidad/acciones-capa/{id}/cerrar"),
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
    app.include_router(calidad.router, prefix="/api/v1/calidad")

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


def token(rol="CALIDAD"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_op_terminada(Sesion, codigo_op="OP-CAL-1"):
    s = Sesion()
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(), numero_pedido="PED-CAL-1", codigo_proyecto="PRY-CAL-1",
        cliente_nombre="Cliente Ficticio SAS", requisitos_cliente="Según plano", confirmado=True,
    )
    orden = OrdenProduccion(
        id_op=uuid.uuid4(), id_proyecto=proyecto.id_proyecto, codigo_op=codigo_op,
        cantidad_fabricar=2, estado=EstadoOPEnum.TERMINADA,
    )
    s.add_all([proyecto, orden])
    s.commit()
    s.close()
    return orden


def crear_nc(Sesion, codigo="NC-CAL-1"):
    s = Sesion()
    nc = NoConformidad(id_nc=uuid.uuid4(), codigo_nc=codigo, descripcion="Diámetro fuera de tolerancia")
    s.add(nc)
    s.commit()
    s.close()
    return nc


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


def test_sin_token_no_se_registra_la_no_conformidad(ctx):
    client, Sesion = ctx

    respuesta = client.post("/api/v1/calidad/no-conformidades", json={"codigo_nc": "NC-SIN-TOKEN", "descripcion": "x"})

    assert respuesta.status_code == 401
    s = Sesion()
    assert s.query(NoConformidad).count() == 0
    s.close()


@pytest.mark.parametrize(
    "ruta",
    ["ordenes-abiertas", "inspeccion", "ordenes-terminadas", "no-conformidades", "rnc"],
)
def test_consultas_con_token_responden_200(ctx, ruta):
    client, Sesion = ctx
    crear_op_terminada(Sesion)

    respuesta = client.get(f"/api/v1/calidad/{ruta}", headers=token())

    assert respuesta.status_code == 200, respuesta.text
    assert isinstance(respuesta.json(), list)


def test_inspeccionar_con_token(ctx):
    client, Sesion = ctx
    crear_op_terminada(Sesion)

    respuesta = client.post(
        "/api/v1/calidad/inspeccionar",
        json={
            "codigo_op": "OP-CAL-1",
            "codigo_plano": "PLN-CAL-1",
            "inspector_nombre": "Inspector de calidad",
            "resultado_inspeccion": "APROBADO_DESPACHO",
            "mediciones_dimensionales": [
                {"caracteristica": "Diámetro", "nominal": 25, "tolerancia_min": 24.98, "tolerancia_max": 25.02, "valor_medido": 25},
            ],
            # La inspección exige al menos una fotografía JPG o PNG (PNG de 1x1)
            "registros_fotograficos": [
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/T2sAAAAASUVORK5CYII="
            ],
        },
        headers=token(),
    )

    assert respuesta.status_code == 201, respuesta.text


def test_registrar_no_conformidad_con_token(ctx):
    client, Sesion = ctx

    respuesta = client.post(
        "/api/v1/calidad/no-conformidades",
        json={"codigo_nc": "NC-CAL-2", "descripcion": "Rebaba en el chavetero"},
        headers=token(),
    )

    assert respuesta.status_code == 201, respuesta.text
    s = Sesion()
    assert s.query(NoConformidad).filter(NoConformidad.codigo_nc == "NC-CAL-2").count() == 1
    s.close()


def test_crear_y_cerrar_capa_con_token(ctx):
    client, Sesion = ctx
    nc = crear_nc(Sesion)

    creada = client.post(
        f"/api/v1/calidad/rnc/{nc.id_nc}/acciones-capa",
        json={"accion_correctiva": "Ajustar el offset del torno", "fecha_compromiso": date.today().isoformat()},
        headers=token(),
    )
    assert creada.status_code == 201, creada.text
    s = Sesion()
    [accion] = s.query(AccionCAPA).all()
    s.close()

    cerrada = client.patch(
        f"/api/v1/calidad/acciones-capa/{accion.id_capa}/cerrar",
        json={"evidencia_cierre": "Medición conforme en tres lotes"},
        headers=token(),
    )

    assert cerrada.status_code == 200, cerrada.text
    assert cerrada.json()["estado_cierre"] == "CERRADA"
