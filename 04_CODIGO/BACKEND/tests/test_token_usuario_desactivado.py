# tests/test_token_usuario_desactivado.py
"""
Un token ya emitido deja de servir en cuanto el usuario se desactiva o se elimina:
obtener_usuario_actual revisa el usuario contra la base en cada petición (401). Al reactivarlo
vuelve a servir. Cubre una ruta con solo token y una con requerir_roles.

SQLite en memoria con override de get_db; los routers de auth, empresa y maestros sobre una
aplicación FastAPI mínima. Marcadas usuario_real: no usan el atajo de conftest.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth, maestros
from app.api.v1.endpoints import empresa
from app.core.security import get_password_hash
from app.db.database import Base, get_db
from app.db.models import Rol, Usuario

pytestmark = pytest.mark.usuario_real

CLAVE = "clave-de-prueba-token"
EMAIL = "ventas@prueba.test"
RUTAS = ["/api/v1/configuracion/empresa/", "/api/v1/maestros/socios"]


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, expire_on_commit=False)

    s = Sesion()
    s.add(Rol(id_rol="VENTAS", nombre_rol="Ventas"))
    s.add(Usuario(email=EMAIL, password_hash=get_password_hash(CLAVE), nombre_completo="Ventas", id_rol="VENTAS", activo=True))
    s.commit()
    s.close()

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1/auth")
    app.include_router(empresa.router, prefix="/api/v1/configuracion/empresa")
    app.include_router(maestros.router, prefix="/api/v1/maestros")
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


def cabecera(client):
    respuesta = client.post("/api/v1/auth/token", data={"username": EMAIL, "password": CLAVE})
    assert respuesta.status_code == 200, respuesta.text
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


def fijar_activo(Sesion, valor):
    with Sesion() as s:
        s.query(Usuario).filter(Usuario.email == EMAIL).update({"activo": valor})
        s.commit()


@pytest.mark.parametrize("ruta", RUTAS)
def test_el_token_deja_de_servir_al_desactivar_y_vuelve_al_reactivar(ctx, ruta):
    client, Sesion = ctx
    token = cabecera(client)
    assert client.get(ruta, headers=token).status_code == 200

    fijar_activo(Sesion, False)
    assert client.get(ruta, headers=token).status_code == 401

    fijar_activo(Sesion, True)
    assert client.get(ruta, headers=token).status_code == 200


@pytest.mark.parametrize("ruta", RUTAS)
def test_el_token_de_un_usuario_eliminado_no_sirve(ctx, ruta):
    client, Sesion = ctx
    token = cabecera(client)

    with Sesion() as s:
        s.query(Usuario).filter(Usuario.email == EMAIL).delete()
        s.commit()

    assert client.get(ruta, headers=token).status_code == 401


def test_activo_null_sigue_sirviendo(ctx):
    client, Sesion = ctx
    token = cabecera(client)

    fijar_activo(Sesion, None)

    assert client.get(RUTAS[0], headers=token).status_code == 200
