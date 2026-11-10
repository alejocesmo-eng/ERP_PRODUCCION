# tests/test_login_usuario_inactivo.py
"""
POST /auth/token no entrega token a un usuario con activo = False (401, el mismo código que el
resto de rechazos del login). La clave se valida antes: con clave errada el mensaje es el
genérico, para no revelar que la cuenta existe.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router de auth.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth
from app.core.security import get_password_hash
from app.db.database import Base, get_db
from app.db.models import Rol, Usuario

CLAVE = "clave-de-prueba-login"
GENERICO = "Credenciales inválidas o usuario no registrado."


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tablas = [Rol.__table__, Usuario.__table__]
    Base.metadata.create_all(engine, tables=tablas)
    Sesion = sessionmaker(bind=engine, expire_on_commit=False)

    s = Sesion()
    s.add(Rol(id_rol="VENTAS", nombre_rol="Ventas"))
    for email, activo in (("activo@prueba.test", True), ("inactivo@prueba.test", False), ("sin_estado@prueba.test", None)):
        s.add(Usuario(email=email, password_hash=get_password_hash(CLAVE), nombre_completo=email,
                      id_rol="VENTAS", activo=activo))
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
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(engine, tables=tablas)
    engine.dispose()


def login(client, email, clave=CLAVE):
    return client.post("/api/v1/auth/token", data={"username": email, "password": clave})


def test_usuario_activo_recibe_token(ctx):
    respuesta = login(ctx, "activo@prueba.test")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["access_token"]


def test_usuario_inactivo_no_recibe_token(ctx):
    respuesta = login(ctx, "inactivo@prueba.test")

    assert respuesta.status_code == 401
    assert "access_token" not in respuesta.json()
    assert respuesta.json()["detail"] == "Usuario inactivo. Contacte al administrador."


def test_inactivo_con_clave_errada_recibe_el_mensaje_generico(ctx):
    respuesta = login(ctx, "inactivo@prueba.test", "otra-clave")

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == GENERICO


def test_activo_sin_valor_se_trata_como_activo(ctx):
    # Filas antiguas con activo NULL: no se bloquean (solo False es inactivo)
    assert login(ctx, "sin_estado@prueba.test").status_code == 200
