# tests/test_permisos_usuario.py
"""
SCRUM-27, paso 1c:
- GET /auth/permisos devuelve los permisos del rol del token según rol_permisos, para que el
  frontend muestre u oculte módulos (por ejemplo la pestaña de costos del expediente). Solo
  orienta la interfaz: las rutas siguen validando por su cuenta.
- PATCH /ordenes/{id}: LIDER_MECANIZADOS puede terminar la OP y pasarla a inspección de
  CALIDAD_PRODUCTO y cerrarla como respaldo del Jefe de Producción, pero no hacer las demás
  transiciones. Liberar va por PERM_OP_LIBERAR, que no tiene.

SQLite en memoria con override de get_db y tokens firmados en la prueba; aplicación FastAPI
mínima con los routers de auth y ordenes. No toca ninguna base real.
"""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth, ordenes
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Permiso, Rol, RolPermiso
from tests.ayudantes_usuarios import id_prueba

PERMISOS = {
    "ADMIN": ["PERM_ADMIN_ALL"],
    "COSTOS": ["PERM_EXPEDIENTE_COSTOS_VER", "PERM_VALOR_COTIZADO_VER"],
    "LIDER_MECANIZADOS": [],
}


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, expire_on_commit=False)
    with Sesion() as s:
        for id_permiso in {p for lista in PERMISOS.values() for p in lista}:
            s.add(Permiso(id_permiso=id_permiso, modulo="PRUEBA", descripcion=id_permiso))
        for id_rol, lista in PERMISOS.items():
            s.add(Rol(id_rol=id_rol, nombre_rol=id_rol))
            for id_permiso in lista:
                s.add(RolPermiso(id_rol=id_rol, id_permiso=id_permiso))
        s.commit()

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1/auth")
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as cliente:
        yield cliente
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(id_prueba(f'{rol.lower()}')), 'rol': rol})}"}


@pytest.mark.parametrize("rol", sorted(PERMISOS))
def test_permisos_del_rol_del_token(client, rol):
    respuesta = client.get("/api/v1/auth/permisos", headers=token(rol))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"rol": rol, "permisos": sorted(PERMISOS[rol])}


def test_rol_sin_filas_no_tiene_permisos(client):
    assert client.get("/api/v1/auth/permisos", headers=token("GERENCIA")).json()["permisos"] == []


def test_permisos_exige_token(client):
    assert client.get("/api/v1/auth/permisos").status_code == 401


@pytest.mark.parametrize("estado", ["TERMINADA", "EN_INSPECCION"])
def test_lider_de_mecanizados_termina_la_op_y_la_pasa_a_inspeccion(client, estado):
    # Pasa el control de rol; sin OP en la base, la ruta responde 404
    respuesta = client.patch(f"/api/v1/ordenes/{uuid.uuid4()}", json={"estado": estado}, headers=token("LIDER_MECANIZADOS"))

    assert respuesta.status_code == 404


def test_lider_de_mecanizados_cierra_la_op_como_respaldo(client):
    # Pasa el control de rol; sin OP en la base, la ruta responde 404
    respuesta = client.patch(f"/api/v1/ordenes/{uuid.uuid4()}", json={"estado": "CERRADA"}, headers=token("LIDER_MECANIZADOS"))

    assert respuesta.status_code == 404


@pytest.mark.parametrize("rol", ["OPERARIO", "CALIDAD_PRODUCTO", "VENTAS"])
def test_otros_roles_no_cierran_la_op(client, rol):
    respuesta = client.patch(f"/api/v1/ordenes/{uuid.uuid4()}", json={"estado": "CERRADA"}, headers=token(rol))

    assert respuesta.status_code == 403


@pytest.mark.parametrize("estado", ["EN_PRODUCCION", "CANCELADA"])
def test_lider_de_mecanizados_no_hace_las_demas_transiciones(client, estado):
    respuesta = client.patch(f"/api/v1/ordenes/{uuid.uuid4()}", json={"estado": estado}, headers=token("LIDER_MECANIZADOS"))

    assert respuesta.status_code == 403


@pytest.mark.parametrize("rol", ["OPERARIO", "CALIDAD_PRODUCTO", "VENTAS"])
def test_otros_roles_no_terminan_la_op(client, rol):
    respuesta = client.patch(f"/api/v1/ordenes/{uuid.uuid4()}", json={"estado": "TERMINADA"}, headers=token(rol))

    assert respuesta.status_code == 403


@pytest.mark.parametrize("rol", ["JEFE_PRODUCCION", "ADMIN"])
def test_jefe_y_admin_hacen_las_demas_transiciones(client, rol):
    respuesta = client.patch(f"/api/v1/ordenes/{uuid.uuid4()}", json={"estado": "CERRADA"}, headers=token(rol))

    assert respuesta.status_code == 404
