# tests/test_pedido_edicion_lineas.py
"""
Edición de pedidos (PATCH /proyectos/{id_proyecto}) según la regla confirmada por negocio
(2026-11-10): Ventas solo edita un pedido en borrador; al confirmarlo queda bloqueado para
edición y pasa a Diseño, que con Producción crea las OP de sus líneas.

- En borrador, cada línea con detalle_id se actualiza en su sitio y conserva su id y su producto.
- Un pedido confirmado no admite editar, eliminar ni agregar líneas: error y nada cambia.
- Las líneas de un pedido confirmado tienen OP y no se pueden borrar (ni por la API ni en la base:
  ordenes_produccion.id_detalle_pedido tiene ON DELETE RESTRICT).
- Un detalle_id de otro pedido responde 400.

El pedido se confirma con PATCH /proyectos/{id}/confirmar (flujo real) y las OP se crean después
en la base. Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*), dentro de una
transacción que se revierte al terminar.
"""
import os
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1 import proyectos
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import OrdenProduccion, PedidoDetalle, Producto, Proyecto

URL_PG = os.environ.get("SGI_TEST_PG_URL")

pytestmark = pytest.mark.pg


@pytest.fixture
def ctx():
    assert (make_url(URL_PG).database or "").startswith("sgi_test_"), "Solo se prueba sobre copias sgi_test_*."
    engine = create_engine(URL_PG)
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")

    app = FastAPI()
    app.include_router(proyectos.router, prefix="/api/v1/proyectos")
    app.dependency_overrides[get_db] = lambda: sesion
    client = TestClient(app)
    try:
        yield client, sesion
    finally:
        client.close()
        sesion.close()
        transaccion.rollback()
        conexion.close()
        engine.dispose()


def token(rol="VENTAS"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_pedido_borrador(sesion):
    """Pedido en borrador con dos líneas sobre plano, cada una con su producto y sin OP."""
    sufijo = uuid.uuid4().hex[:8].upper()
    productos = [
        Producto(id_producto=uuid.uuid4(), codigo_rn=f"RN-700-800-{uuid.uuid4().int % 1000000:06d}",
                 descripcion=f"Conjunto edición {letra}")
        for letra in "AB"
    ]
    pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido=f"PED-ED-{sufijo}", codigo_proyecto=f"PRY-ED-{sufijo}",
                      cliente_nombre="Cliente edición", requisitos_cliente="Según plano", confirmado=False)
    sesion.add_all([*productos, pedido])
    sesion.flush()
    linea_a = PedidoDetalle(detalle_id=uuid.uuid4(), pedido_id=pedido.id_proyecto, codigo_producto="PROD-A",
                            id_producto=productos[0].id_producto, descripcion="Línea A", cantidad_solicitada=2)
    linea_b = PedidoDetalle(detalle_id=uuid.uuid4(), pedido_id=pedido.id_proyecto, codigo_producto="PROD-B",
                            id_producto=productos[1].id_producto, descripcion="Línea B", cantidad_solicitada=1)
    sesion.add_all([linea_a, linea_b])
    sesion.commit()
    return pedido, linea_a, linea_b


def confirmar_con_ops(client, sesion, pedido, lineas_pedido):
    """Ventas confirma por la API; después Diseño y Producción crean una OP por línea."""
    respuesta = client.patch(f"/api/v1/proyectos/{pedido.id_proyecto}/confirmar", headers=token())
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["confirmado"] is True
    ops = [
        OrdenProduccion(id_op=uuid.uuid4(), id_proyecto=pedido.id_proyecto, id_producto=l.id_producto,
                        id_detalle_pedido=l.detalle_id, codigo_op=f"OP-ED-{uuid.uuid4().hex[:8].upper()}",
                        cantidad_fabricar=l.cantidad_solicitada)
        for l in lineas_pedido
    ]
    sesion.add_all(ops)
    sesion.commit()
    return ops


def linea(detalle_id=None, descripcion="Línea", cantidad=1, codigo="PROD"):
    cuerpo = {"descripcion": descripcion, "cantidad_solicitada": cantidad, "codigo_producto": codigo}
    if detalle_id:
        cuerpo["detalle_id"] = str(detalle_id)
    return cuerpo


def editar(client, pedido, detalles):
    return client.patch(f"/api/v1/proyectos/{pedido.id_proyecto}", json={"detalles": detalles}, headers=token())


def foto_lineas(sesion, pedido):
    sesion.expire_all()
    return {
        l.detalle_id: (l.descripcion, l.cantidad_solicitada, l.codigo_producto, l.id_producto)
        for l in sesion.query(PedidoDetalle).filter_by(pedido_id=pedido.id_proyecto)
    }


def test_editar_linea_de_pedido_en_borrador_conserva_id_y_producto(ctx):
    client, sesion = ctx
    pedido, linea_a, linea_b = crear_pedido_borrador(sesion)
    producto_a = linea_a.id_producto

    respuesta = editar(client, pedido, [
        linea(linea_a.detalle_id, "Línea A modificada", 5, "PROD-A"),
        linea(linea_b.detalle_id, "Línea B", 1, "PROD-B"),
    ])

    assert respuesta.status_code == 200, respuesta.text
    sesion.expire_all()
    actuales = {l.detalle_id: l for l in sesion.query(PedidoDetalle).filter_by(pedido_id=pedido.id_proyecto)}
    assert set(actuales) == {linea_a.detalle_id, linea_b.detalle_id}
    a = actuales[linea_a.detalle_id]
    assert (a.descripcion, a.cantidad_solicitada, a.cantidad_pendiente) == ("Línea A modificada", 5, 5)
    assert a.id_producto == producto_a


@pytest.mark.parametrize("cambio", ["editar", "eliminar", "agregar"])
def test_pedido_confirmado_no_admite_cambios_en_sus_lineas(ctx, cambio):
    client, sesion = ctx
    pedido, linea_a, linea_b = crear_pedido_borrador(sesion)
    confirmar_con_ops(client, sesion, pedido, [linea_a, linea_b])
    antes = foto_lineas(sesion, pedido)
    detalles = {
        "editar": [linea(linea_a.detalle_id, "Línea A modificada", 5, "PROD-A"), linea(linea_b.detalle_id, "Línea B", 1, "PROD-B")],
        "eliminar": [linea(linea_a.detalle_id, "Línea A", 2, "PROD-A")],
        "agregar": [linea(linea_a.detalle_id, "Línea A", 2, "PROD-A"), linea(linea_b.detalle_id, "Línea B", 1, "PROD-B"),
                    linea(None, "Línea C nueva", 3, "PROD-C")],
    }[cambio]

    respuesta = editar(client, pedido, detalles)

    assert respuesta.status_code == 400
    assert "CONFIRMADO" in respuesta.json()["detail"]
    sesion.rollback()  # fin de la petición rechazada: get_db cierra la sesión sin commit
    assert foto_lineas(sesion, pedido) == antes


def test_lineas_de_pedido_confirmado_tienen_op_y_no_se_pueden_borrar(ctx):
    client, sesion = ctx
    pedido, linea_a, linea_b = crear_pedido_borrador(sesion)
    ops = confirmar_con_ops(client, sesion, pedido, [linea_a, linea_b])

    sesion.expire_all()
    for l in (linea_a, linea_b):
        assert sesion.query(OrdenProduccion).filter_by(id_detalle_pedido=l.detalle_id).count() == 1
    # Por la API: el pedido confirmado no admite la edición que quitaría la línea
    assert editar(client, pedido, [linea(linea_a.detalle_id, "Línea A", 2, "PROD-A")]).status_code == 400
    sesion.rollback()
    assert set(foto_lineas(sesion, pedido)) == {linea_a.detalle_id, linea_b.detalle_id}
    # En la base: ON DELETE RESTRICT impide borrar una línea con OP
    with pytest.raises(IntegrityError):
        sesion.execute(text("DELETE FROM pedido_detalles WHERE detalle_id = :id"), {"id": linea_b.detalle_id})
        sesion.flush()
    sesion.rollback()
    assert {op.id_detalle_pedido for op in ops} == {linea_a.detalle_id, linea_b.detalle_id}


def test_detalle_id_de_otro_pedido_da_400(ctx):
    client, sesion = ctx
    pedido, linea_a, _ = crear_pedido_borrador(sesion)
    _, ajena, _ = crear_pedido_borrador(sesion)

    respuesta = editar(client, pedido, [linea(linea_a.detalle_id), linea(ajena.detalle_id)])

    assert respuesta.status_code == 400
    assert str(ajena.detalle_id) in respuesta.json()["detail"]
