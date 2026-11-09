# tests/test_planos_token_rutas.py
"""
Paso 1 de permisos (planos): el listado, la descarga CAD y la emisión del token del visor
exigen token (sin restricción de rol). /planos/visor-seguro queda fuera a propósito: lo
protege su propio token temporal firmado, que el visor envía en la URL.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router
de planos (no se importa app.main) para no tocar ninguna base real.
"""
import hashlib
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import planos as planos_api
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Plano, PlanoArchivo

PDF = b"%PDF plano del visor"
STEP = b"ISO-10303-21; modelo de prueba"


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(planos_api, "DIRECTORIO_STATIC_PLANOS", str(tmp_path))
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # expire_on_commit=False: las pruebas leen los ids de los objetos tras cerrar la sesión
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = FastAPI()
    app.include_router(planos_api.router, prefix="/api/v1/planos")

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)

    (tmp_path / "PLN-TOK-01.pdf").write_bytes(PDF)
    (tmp_path / "PLN-TOK-01.step").write_bytes(STEP)
    s = Sesion()
    plano = Plano(
        id_plano=uuid.uuid4(), codigo_plano="PLN-TOK-01", version="V-01", estado_diseno="EN_DISENO",
        archivo_url="/static/planos/PLN-TOK-01.pdf", archivo_pdf_url="/static/planos/PLN-TOK-01.pdf",
    )
    s.add(plano)
    s.flush()
    s.add(PlanoArchivo(
        id_plano=plano.id_plano, tipo="STEP", ruta="/static/planos/PLN-TOK-01.step",
        nombre_original="eje_cliente.step", tamano_bytes=len(STEP), sha256=hashlib.sha256(STEP).hexdigest(),
        vigente=True,
    ))
    s.commit()
    s.close()
    yield client, plano
    client.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol="PRODUCCION"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


RUTAS = ["/api/v1/planos/", "/api/v1/planos/token/{id}", "/api/v1/planos/descargar-cad/{id}/step"]


@pytest.mark.parametrize("ruta", RUTAS)
@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "Bearer token-que-no-es-un-jwt"}],
    ids=["sin_cabecera", "token_invalido"],
)
def test_sin_token_valido_responde_401(ctx, ruta, cabeceras):
    client, plano = ctx

    respuesta = client.get(ruta.format(id=plano.id_plano), headers=cabeceras)

    assert respuesta.status_code == 401


def test_listado_con_token(ctx):
    client, plano = ctx

    respuesta = client.get("/api/v1/planos/", headers=token())

    assert respuesta.status_code == 200, respuesta.text
    assert [p["id_plano"] for p in respuesta.json()] == [str(plano.id_plano)]


@pytest.mark.parametrize("rol", ["PRODUCCION", "VENTAS", "DISENO"])
def test_descarga_cad_funciona_para_un_usuario_autenticado(ctx, rol):
    client, plano = ctx

    respuesta = client.get(f"/api/v1/planos/descargar-cad/{plano.id_plano}/step", headers=token(rol))

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.content == STEP
    assert "eje_cliente.step" in respuesta.headers["content-disposition"]


def test_token_del_visor_con_token_y_visor_seguro_sin_bearer(ctx):
    client, plano = ctx

    emitido = client.get(f"/api/v1/planos/token/{plano.id_plano}", headers=token())
    assert emitido.status_code == 200, emitido.text
    temporal = emitido.json()["token_temporal"]

    # El visor (iframe) no envía Authorization: visor-seguro sigue protegido solo por su token temporal
    visor = client.get("/api/v1/planos/visor-seguro", params={"token": temporal})

    assert visor.status_code == 200, visor.text
    assert visor.content == PDF


def test_visor_seguro_rechaza_un_token_temporal_no_valido(ctx):
    client, _ = ctx

    assert client.get("/api/v1/planos/visor-seguro", params={"token": "no-es-un-token"}).status_code == 401
