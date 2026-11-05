import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import historial
from app.db.database import get_db

# ADR-008: las rutas de historial toman el responsable del JWT; sin token devuelven 401.


def _db_no_usada():
    # FastAPI resuelve get_db antes que el token; la sesión nunca llega a usarse.
    yield None


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(historial.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _db_no_usada
    return TestClient(app)


@pytest.mark.parametrize(
    "metodo, ruta, cuerpo",
    [
        ("get", "/api/v1/historial/PEDIDO/PED-2026-0001", None),
        (
            "post",
            "/api/v1/historial/suspender",
            {"tipo_entidad": "PEDIDO", "identificador": "PED-2026-0001", "motivo": "Prueba"},
        ),
        (
            "post",
            "/api/v1/historial/reactivar",
            {"tipo_entidad": "PEDIDO", "identificador": "PED-2026-0001", "motivo": "Prueba"},
        ),
    ],
    ids=["consultar", "suspender", "reactivar"],
)
def test_ruta_historial_sin_token_devuelve_401(client, metodo, ruta, cuerpo):
    response = client.request(metodo.upper(), ruta, json=cuerpo)
    assert response.status_code == 401, response.text
