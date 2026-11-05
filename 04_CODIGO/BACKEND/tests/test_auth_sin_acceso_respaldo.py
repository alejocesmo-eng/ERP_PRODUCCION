import os
import secrets

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth
from app.db.database import Base, get_db
from app.db.models import Rol, Usuario

# ADR-006: auth.py ya no concede acceso de respaldo a admin@sgi.com.
EMAIL_RESPALDO = "admin@sgi.com"
RUTA_AUTH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "app", "api", "v1", "auth.py")
)


@pytest.fixture
def client_sin_usuarios():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [Rol.__table__, Usuario.__table__]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1/auth")
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        Base.metadata.drop_all(engine, tables=tables)
        engine.dispose()


def test_respaldo_rechazado_sin_usuario_en_bd(client_sin_usuarios):
    response = client_sin_usuarios.post(
        "/api/v1/auth/token",
        data={"username": EMAIL_RESPALDO, "password": secrets.token_urlsafe(24)},
    )
    assert response.status_code == 401, response.text
    assert "access_token" not in response.json()


def test_auth_sin_constantes_legacy():
    with open(RUTA_AUTH, encoding="utf-8") as archivo:
        assert "LEGACY_" not in archivo.read()
