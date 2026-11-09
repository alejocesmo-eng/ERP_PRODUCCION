# tests/test_pedido_edicion_lineas.py
"""
Edición de pedidos (PATCH /proyectos/{id_proyecto}): cada línea con detalle_id se actualiza en su
sitio y conserva su id y el vínculo con su OP; las líneas sin detalle_id son nuevas; una línea
ausente se elimina salvo que tenga OP asociada (409). En la base, ordenes_produccion.id_detalle_pedido
tiene ON DELETE RESTRICT.

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*), dentro de una
transacción que se revierte al terminar.
"""
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1 import proyectos
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


def crear_pedido_con_op(sesion):
    """Pedido sin confirmar con dos líneas; la línea A tiene producto y una OP."""
    sufijo = uuid.uuid4().hex[:8].upper()
    producto = Producto(id_producto=uuid.uuid4(), codigo_rn=f"RN-700-800-{uuid.uuid4().int % 1000000:06d}",
                        descripcion="Conjunto edición")
    pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido=f"PED-ED-{sufijo}", codigo_proyecto=f"PRY-ED-{sufijo}",
                      cliente_nombre="Cliente edición", requisitos_cliente="Según plano", confirmado=False)
    sesion.add_all([producto, pedido])
    sesion.flush()
    linea_a = PedidoDetalle(detalle_id=uuid.uuid4(), pedido_id=pedido.id_proyecto, codigo_producto="PROD-A",
                            id_producto=producto.id_producto, descripcion="Línea A", cantidad_solicitada=2)
    linea_b = PedidoDetalle(detalle_id=uuid.uuid4(), pedido_id=pedido.id_proyecto, codigo_producto="PROD-B",
                            descripcion="Línea B", cantidad_solicitada=1)
    sesion.add_all([linea_a, linea_b])
    sesion.flush()
    op = OrdenProduccion(id_op=uuid.uuid4(), id_proyecto=pedido.id_proyecto, id_producto=producto.id_producto,
                         id_detalle_pedido=linea_a.detalle_id, codigo_op=f"OP-ED-{sufijo}", cantidad_fabricar=2)
    sesion.add(op)
    sesion.commit()
    return pedido, linea_a, linea_b, op


def linea(detalle_id=None, descripcion="Línea", cantidad=1, codigo="PROD"):
    cuerpo = {"descripcion": descripcion, "cantidad_solicitada": cantidad, "codigo_producto": codigo}
    if detalle_id:
        cuerpo["detalle_id"] = str(detalle_id)
    return cuerpo


def editar(client, pedido, detalles):
    return client.patch(f"/api/v1/proyectos/{pedido.id_proyecto}", json={"detalles": detalles})


def lineas(sesion, pedido):
    sesion.expire_all()
    return {l.detalle_id: l for l in sesion.query(PedidoDetalle).filter_by(pedido_id=pedido.id_proyecto)}


def test_editar_pedido_con_op_conserva_id_y_vinculo(ctx):
    client, sesion = ctx
    pedido, linea_a, linea_b, op = crear_pedido_con_op(sesion)

    respuesta = editar(client, pedido, [
        linea(linea_a.detalle_id, "Línea A modificada", 5, "PROD-A"),
        linea(linea_b.detalle_id, "Línea B", 1, "PROD-B"),
    ])

    assert respuesta.status_code == 200, respuesta.text
    actuales = lineas(sesion, pedido)
    assert set(actuales) == {linea_a.detalle_id, linea_b.detalle_id}
    a = actuales[linea_a.detalle_id]
    assert (a.descripcion, a.cantidad_solicitada, a.cantidad_pendiente) == ("Línea A modificada", 5, 5)
    assert a.id_producto is not None
    assert sesion.get(OrdenProduccion, op.id_op).id_detalle_pedido == linea_a.detalle_id


def test_eliminar_una_linea_con_op_da_409_y_la_conserva(ctx):
    client, sesion = ctx
    pedido, linea_a, linea_b, op = crear_pedido_con_op(sesion)

    respuesta = editar(client, pedido, [linea(linea_b.detalle_id, "Línea B", 1, "PROD-B")])

    assert respuesta.status_code == 409
    assert op.codigo_op in respuesta.json()["detail"]
    sesion.rollback()  # fin de la petición rechazada: get_db cierra la sesión sin commit
    assert set(lineas(sesion, pedido)) == {linea_a.detalle_id, linea_b.detalle_id}


def test_eliminar_una_linea_sin_op_y_agregar_una_nueva(ctx):
    client, sesion = ctx
    pedido, linea_a, linea_b, _ = crear_pedido_con_op(sesion)

    respuesta = editar(client, pedido, [
        linea(linea_a.detalle_id, "Línea A", 2, "PROD-A"),
        linea(None, "Línea C nueva", 3, "PROD-C"),
    ])

    assert respuesta.status_code == 200, respuesta.text
    actuales = lineas(sesion, pedido)
    assert linea_a.detalle_id in actuales
    assert linea_b.detalle_id not in actuales
    [nueva] = [l for i, l in actuales.items() if i != linea_a.detalle_id]
    assert (nueva.descripcion, nueva.cantidad_solicitada) == ("Línea C nueva", 3)


def test_detalle_id_de_otro_pedido_da_400(ctx):
    client, sesion = ctx
    pedido, linea_a, _, _ = crear_pedido_con_op(sesion)
    _, ajena, _, _ = crear_pedido_con_op(sesion)

    respuesta = editar(client, pedido, [linea(linea_a.detalle_id), linea(ajena.detalle_id)])

    assert respuesta.status_code == 400


def test_la_base_impide_borrar_una_linea_con_op(ctx):
    _, sesion = ctx
    _, linea_a, _, _ = crear_pedido_con_op(sesion)

    with pytest.raises(IntegrityError):
        sesion.execute(text("DELETE FROM pedido_detalles WHERE detalle_id = :id"), {"id": linea_a.detalle_id})
        sesion.flush()
    sesion.rollback()
