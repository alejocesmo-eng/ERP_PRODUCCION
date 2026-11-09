# tests/test_planos_creacion.py
"""
POST /planos/: creación de planos con y sin piezas.

SQLite en memoria con override de get_db, tokens ficticios y una aplicación FastAPI
mínima con el router de planos (no se importa app.main) para no tocar ninguna base real.
"""
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
from app.db.models import BOMListaMateriales, Plano, PlanoHistorial, Proyecto


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
    yield client, Sesion, tmp_path
    client.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol="DISENO"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_proyecto(Sesion):
    s = Sesion()
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(), numero_pedido="PED-CR-1", codigo_proyecto="PRY-CR-1",
        cliente_nombre="Cliente Ficticio SAS", requisitos_cliente="Según plano",
    )
    s.add(proyecto)
    s.commit()
    s.close()
    return proyecto


def crear(client, proyecto, **cuerpo):
    datos = {"id_proyecto": str(proyecto.id_proyecto), "codigo_op": "OP-CR-1"}
    datos.update(cuerpo)
    return client.post("/api/v1/planos/", json=datos, headers=token())


def leer_planos(Sesion):
    s = Sesion()
    try:
        return s.query(Plano).order_by(Plano.codigo_plano).all()
    finally:
        s.close()


def test_sin_piezas_crea_un_plano_con_los_datos_de_la_cabecera(ctx):
    client, Sesion, _ = ctx
    proyecto = crear_proyecto(Sesion)

    respuesta = crear(
        client, proyecto,
        codigo_plano="PLN-CR-CABECERA", version="V-04", material_requerido="AISI 4140", piezas=[],
    )

    assert respuesta.status_code == 201, respuesta.text
    [plano] = respuesta.json()
    assert (plano["codigo_plano"], plano["version"], plano["material_requerido"]) == ("PLN-CR-CABECERA", "V-04", "AISI 4140")
    s = Sesion()
    [linea] = s.query(BOMListaMateriales).all()
    assert linea.codigo_material == "AISI 4140"
    [evento] = s.query(PlanoHistorial).all()
    assert (evento.tipo_evento, evento.version) == ("CREACION", "V-04")
    s.close()


def test_sin_piezas_y_sin_codigo_de_plano_usa_el_codigo_de_la_op(ctx):
    client, Sesion, _ = ctx
    proyecto = crear_proyecto(Sesion)

    respuesta = crear(client, proyecto)

    assert respuesta.status_code == 201, respuesta.text
    [plano] = respuesta.json()
    assert (plano["codigo_plano"], plano["version"]) == ("OP-CR-1", "V-01")


def test_con_piezas_crea_un_plano_por_pieza(ctx):
    client, Sesion, _ = ctx
    proyecto = crear_proyecto(Sesion)

    respuesta = crear(
        client, proyecto,
        piezas=[{"codigo_plano": "PLN-CR-A", "version": "V-02"}, {"codigo_plano": "PLN-CR-B"}],
    )

    assert respuesta.status_code == 201, respuesta.text
    assert [(p.codigo_plano, p.version) for p in leer_planos(Sesion)] == [("PLN-CR-A", "V-02"), ("PLN-CR-B", "V-01")]
