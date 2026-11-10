# tests/test_op_no_liberable.py
"""
Una OP CANCELADA o CERRADA no se libera: PATCH /ordenes/liberar/{codigo_op} y PATCH /ordenes/{id}
con estado LIBERADA o LIBERADA_PRODUCCION responden 409 y no cambian el estado, tampoco con la
excepción ADMIN. El estado se valida antes que el permiso y la regla RN-OP-004. Una OP en otro
estado sigue el camino normal (aquí, sin planos, la regla la rechaza con otro código).

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router de
órdenes (no se importa app.main). La versión con la regla completa cumplida está en
test_liberacion_op.py (pg).
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import ordenes
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import EstadoOPEnum, OrdenProduccion, Proyecto

MOTIVO = "Urgencia del cliente autorizada por Dirección"


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = FastAPI()
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")

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


def token(rol):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_op(Sesion, estado):
    with Sesion() as s:
        proyecto = Proyecto(
            id_proyecto=uuid.uuid4(), numero_pedido="PED-NL", codigo_proyecto="PED-NL",
            cliente_nombre="Cliente", requisitos_cliente="Sin especificación",
        )
        op = OrdenProduccion(
            id_op=uuid.uuid4(), id_proyecto=proyecto.id_proyecto, id_producto=uuid.uuid4(),
            codigo_op=f"OP-NL-{uuid.uuid4().hex[:6]}", cantidad_fabricar=1, estado=estado,
        )
        s.add_all([proyecto, op])
        s.commit()
        return op


def estado_y_reserva(Sesion, op):
    with Sesion() as s:
        fila = s.get(OrdenProduccion, op.id_op)
        return fila.estado, fila.reserva_stock_100


def liberar(client, op, ruta, rol, motivo, estado_destino="LIBERADA"):
    if ruta == "liberar":
        return client.patch(f"/api/v1/ordenes/liberar/{op.codigo_op}", json={"motivo": motivo}, headers=token(rol))
    return client.patch(f"/api/v1/ordenes/{op.id_proyecto}", json={"estado": estado_destino, "motivo": motivo},
                        headers=token(rol))


@pytest.mark.parametrize("estado", [EstadoOPEnum.CANCELADA, EstadoOPEnum.CERRADA])
@pytest.mark.parametrize("ruta, destino", [("liberar", "LIBERADA"), ("patch", "LIBERADA"), ("patch", "LIBERADA_PRODUCCION")])
@pytest.mark.parametrize("rol, motivo", [("DISENO", None), ("ADMIN", MOTIVO)], ids=["diseno", "excepcion_admin"])
def test_op_cancelada_o_cerrada_responde_409_y_no_cambia(ctx, estado, ruta, destino, rol, motivo):
    client, Sesion = ctx
    op = crear_op(Sesion, estado)

    respuesta = liberar(client, op, ruta, rol, motivo, destino)

    assert respuesta.status_code == 409, respuesta.text
    assert respuesta.json()["detail"] == f"La OP {op.codigo_op} está {estado.value}: no se puede liberar."
    assert estado_y_reserva(Sesion, op) == (estado, False)


@pytest.mark.parametrize("ruta", ["liberar", "patch"])
def test_op_en_borrador_no_la_frena_esta_regla(ctx, ruta):
    client, Sesion = ctx
    op = crear_op(Sesion, EstadoOPEnum.BORRADOR)

    # Sin planos ni permisos la rechaza la regla de liberación, no el estado
    respuesta = liberar(client, op, ruta, "DISENO", None)

    assert respuesta.status_code != 409
    assert "no se puede liberar" not in respuesta.text
