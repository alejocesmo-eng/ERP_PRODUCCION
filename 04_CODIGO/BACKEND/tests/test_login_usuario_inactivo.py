# tests/test_login_usuario_inactivo.py
"""
POST /auth/token no entrega token a un usuario con activo = False (401, el mismo código que el
resto de rechazos del login). La clave se valida antes: con clave errada el mensaje es el
genérico, para no revelar que la cuenta existe.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router de auth.
"""
import pytest
from fastapi import FastAPI
from jose import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth
from app.core.security import ALGORITHM, SECRET_KEY, get_password_hash
from app.db.database import Base, get_db
from app.db.models import Rol, Usuario
from tests.ayudantes_usuarios import datos_usuario, id_prueba

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
    for usuario, activo in (("activo", True), ("inactivo", False), ("sin_estado", None)):
        s.add(Usuario(**datos_usuario(usuario), password_hash=get_password_hash(CLAVE), nombre_completo=usuario,
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


def login(client, usuario, clave=CLAVE):
    return client.post("/api/v1/auth/token", data={"username": usuario, "password": clave})


def test_usuario_activo_recibe_token(ctx):
    respuesta = login(ctx, "activo")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["access_token"]
    assert respuesta.json()["nombre_usuario"] == "activo"


def test_el_token_lleva_el_identificador_interno(ctx):
    token = login(ctx, "activo").json()["access_token"]

    assert jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"] == str(id_prueba("activo"))


def test_el_correo_no_sirve_para_entrar(ctx):
    respuesta = login(ctx, "activo@prueba.test")

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == GENERICO


def test_las_mayusculas_y_espacios_del_usuario_no_importan(ctx):
    assert login(ctx, "  Activo ").status_code == 200


def test_usuario_inactivo_no_recibe_token(ctx):
    respuesta = login(ctx, "inactivo")

    assert respuesta.status_code == 401
    assert "access_token" not in respuesta.json()
    assert respuesta.json()["detail"] == "Usuario inactivo. Contacte al administrador."


def test_inactivo_con_clave_errada_recibe_el_mensaje_generico(ctx):
    respuesta = login(ctx, "inactivo", "otra-clave")

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == GENERICO


def test_activo_sin_valor_se_trata_como_activo(ctx):
    # Filas antiguas con activo NULL: no se bloquean (solo False es inactivo)
    assert login(ctx, "sin_estado").status_code == 200
