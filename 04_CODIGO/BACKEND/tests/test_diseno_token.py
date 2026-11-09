# tests/test_diseno_token.py
"""
Paso 1 de permisos: las rutas de /diseno exigen token (sin restricción de rol todavía).
401 sin token en todas y 200 con token válido en cada una.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router
de diseño (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import diseno
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Plano, SolicitudCambioTecnico, Usuario

RUTAS = [
    ("post", "/api/v1/diseno/op/{id}/iniciar-trabajo"),
    ("post", "/api/v1/diseno/op/{id}/liberar"),
    ("patch", "/api/v1/diseno/ecr/{id}/resolver"),
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
    app.include_router(diseno.router, prefix="/api/v1/diseno")

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


def crear_plano(Sesion, **extra):
    s = Sesion()
    datos = {"id_plano": uuid.uuid4(), "codigo_plano": "PLN-DIS-01", "version": "V-01", "estado_diseno": "PLANIFICADA"}
    datos.update(extra)
    plano = Plano(**datos)
    s.add(plano)
    s.commit()
    s.close()
    return plano


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


def test_sin_token_no_cambia_el_plano(ctx):
    client, Sesion = ctx
    plano = crear_plano(Sesion, archivo_pdf_url="/a.pdf", archivo_step_url="/a.step", archivo_dxf_url="/a.dxf")

    assert client.post(f"/api/v1/diseno/op/{plano.id_plano}/liberar").status_code == 401

    s = Sesion()
    assert s.get(Plano, plano.id_plano).estado_diseno == "PLANIFICADA"
    s.close()


def test_iniciar_trabajo_con_token(ctx):
    client, Sesion = ctx
    plano = crear_plano(Sesion)

    respuesta = client.post(f"/api/v1/diseno/op/{plano.id_plano}/iniciar-trabajo", headers=token())

    assert respuesta.status_code == 200, respuesta.text
    s = Sesion()
    assert s.get(Plano, plano.id_plano).estado_diseno == "EN_DISENO"
    s.close()


def test_liberar_con_token(ctx):
    client, Sesion = ctx
    plano = crear_plano(Sesion, archivo_pdf_url="/a.pdf", archivo_step_url="/a.step", archivo_dxf_url="/a.dxf")

    respuesta = client.post(f"/api/v1/diseno/op/{plano.id_plano}/liberar", headers=token())

    assert respuesta.status_code == 200, respuesta.text
    s = Sesion()
    assert s.get(Plano, plano.id_plano).estado_diseno == "LIBERADA"
    s.close()


def test_resolver_ecr_con_token(ctx):
    client, Sesion = ctx
    plano = crear_plano(Sesion)
    s = Sesion()
    usuario = Usuario(id_usuario=uuid.uuid4(), email="jefe@prueba.test", password_hash="!", nombre_completo="Jefe")
    ecr = SolicitudCambioTecnico(
        id_solicitud=uuid.uuid4(), id_plano=plano.id_plano, version_origen="V-01",
        descripcion_cambio="Corregir cota", solicitado_por=usuario.id_usuario,
    )
    s.add_all([usuario, ecr])
    s.commit()
    s.close()

    respuesta = client.patch(f"/api/v1/diseno/ecr/{ecr.id_solicitud}/resolver", headers=token())

    assert respuesta.status_code == 200, respuesta.text
    s = Sesion()
    assert s.get(SolicitudCambioTecnico, ecr.id_solicitud).estado_solicitud == "RESUELTA"
    s.close()
