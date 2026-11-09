# tests/test_expediente_pedido_ops.py
"""
GET /proyectos/{id}/expediente: las OP se vinculan también por línea de pedido
(ordenes_produccion.id_detalle_pedido, migración 20), además de la cadena
OTDetalle -> plano -> OP.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router
de proyectos (no se importa app.main) para no tocar ninguna base real.
"""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import proyectos
from app.db.database import Base, get_db
from app.db.models import OrdenProduccion, OTDetalle, PedidoDetalle, Plano, Proyecto


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # expire_on_commit=False: las pruebas leen los ids de los objetos tras cerrar la sesión
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = FastAPI()
    app.include_router(proyectos.router, prefix="/api/v1/proyectos")

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


def crear_pedido(s, numero, lineas=1):
    pedido = Proyecto(
        id_proyecto=uuid.uuid4(),
        numero_pedido=numero,
        codigo_proyecto=f"PRY-{numero}",
        cliente_nombre="Cliente Ficticio SAS",
        requisitos_cliente="Sin especificación",
        confirmado=True,
    )
    s.add(pedido)
    s.flush()
    detalles = []
    for indice in range(lineas):
        detalle = PedidoDetalle(
            detalle_id=uuid.uuid4(),
            pedido_id=pedido.id_proyecto,
            codigo_producto=f"PZA-{indice + 1:03d}",
            descripcion=f"Pieza {indice + 1}",
            cantidad_solicitada=2,
        )
        s.add(detalle)
        detalles.append(detalle)
    s.flush()
    return pedido, detalles


def crear_plano(s, pedido, codigo):
    plano = Plano(id_plano=uuid.uuid4(), id_proyecto=pedido.id_proyecto, codigo_plano=codigo)
    s.add(plano)
    s.flush()
    return plano


def crear_op(s, pedido, codigo, detalle=None, plano=None):
    op = OrdenProduccion(
        id_op=uuid.uuid4(),
        id_proyecto=pedido.id_proyecto,
        codigo_op=codigo,
        id_detalle_pedido=detalle.detalle_id if detalle else None,
        id_plano=plano.id_plano if plano else None,
    )
    s.add(op)
    s.flush()
    return op


def expediente(client, pedido):
    respuesta = client.get(f"/api/v1/proyectos/{pedido.id_proyecto}/expediente")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def codigos(filas):
    return sorted(fila["codigo_op"] for fila in filas)


def test_op_de_linea_sin_plano_aparece_en_el_pedido_y_en_su_linea(ctx):
    client, Sesion = ctx
    s = Sesion()
    pedido, (linea_a, linea_b) = crear_pedido(s, "PED-OPL-1", lineas=2)
    op = crear_op(s, pedido, "OP-LINEA-A", detalle=linea_a)
    s.commit()
    id_op, id_linea_a = str(op.id_op), str(linea_a.detalle_id)
    s.close()

    datos = expediente(client, pedido)

    assert codigos(datos["ordenes_produccion"]) == ["OP-LINEA-A"]
    fila = datos["ordenes_produccion"][0]
    assert fila["id_op"] == id_op
    assert fila["detalle_id"] == id_linea_a
    assert fila["codigo_plano"] is None
    assert fila["estado_pdf"] == "SIN_PLANO"
    assert fila["estado_insumo"] == "SIN_REGISTRO"
    # Sin plano no entra en la lista de planos
    assert datos["planos"] == []
    lineas = {detalle["detalle_id"]: detalle for detalle in datos["detalles"]}
    assert codigos(lineas[id_linea_a]["ordenes_produccion"]) == ["OP-LINEA-A"]
    assert lineas[str(linea_b.detalle_id)]["ordenes_produccion"] == []


def test_op_vinculada_por_plano_y_por_linea_aparece_una_sola_vez(ctx):
    client, Sesion = ctx
    s = Sesion()
    pedido, (linea,) = crear_pedido(s, "PED-OPL-2")
    plano = crear_plano(s, pedido, "PLN-OPL-2")
    s.add(OTDetalle(ot_id=plano.id_plano, detalle_pedido_id=linea.detalle_id, cantidad_asignada=2))
    crear_op(s, pedido, "OP-DOBLE", detalle=linea, plano=plano)
    s.commit()
    s.close()

    datos = expediente(client, pedido)

    assert codigos(datos["ordenes_produccion"]) == ["OP-DOBLE"]
    assert codigos(datos["planos"]) == ["OP-DOBLE"]
    assert datos["ordenes_produccion"][0]["codigo_plano"] == "PLN-OPL-2"
    assert codigos(datos["detalles"][0]["ordenes_produccion"]) == ["OP-DOBLE"]


def test_op_de_linea_con_plano_fuera_de_ot_detalles_trae_los_datos_del_plano(ctx):
    client, Sesion = ctx
    s = Sesion()
    pedido, (linea,) = crear_pedido(s, "PED-OPL-3")
    plano = crear_plano(s, pedido, "PLN-OPL-3")
    crear_op(s, pedido, "OP-PLANO-PROPIO", detalle=linea, plano=plano)
    s.commit()
    s.close()

    datos = expediente(client, pedido)

    assert codigos(datos["ordenes_produccion"]) == ["OP-PLANO-PROPIO"]
    assert datos["ordenes_produccion"][0]["codigo_plano"] == "PLN-OPL-3"
    assert datos["planos"] == []


def test_no_mezcla_las_op_de_otro_pedido(ctx):
    client, Sesion = ctx
    s = Sesion()
    pedido, (linea,) = crear_pedido(s, "PED-OPL-4")
    otro, (linea_otro,) = crear_pedido(s, "PED-OPL-5")
    crear_op(s, pedido, "OP-PROPIA", detalle=linea)
    crear_op(s, otro, "OP-AJENA", detalle=linea_otro)
    s.commit()
    s.close()

    assert codigos(expediente(client, pedido)["ordenes_produccion"]) == ["OP-PROPIA"]
    assert codigos(expediente(client, otro)["ordenes_produccion"]) == ["OP-AJENA"]


def test_la_cadena_por_ot_detalles_se_conserva(ctx):
    client, Sesion = ctx
    s = Sesion()
    pedido, (linea,) = crear_pedido(s, "PED-OPL-6")
    plano = crear_plano(s, pedido, "PLN-OPL-6")
    s.add(OTDetalle(ot_id=plano.id_plano, detalle_pedido_id=linea.detalle_id, cantidad_asignada=1))
    crear_op(s, pedido, "OP-POR-PLANO", plano=plano)
    s.commit()
    s.close()

    datos = expediente(client, pedido)

    assert codigos(datos["ordenes_produccion"]) == ["OP-POR-PLANO"]
    assert codigos(datos["planos"]) == ["OP-POR-PLANO"]
    assert datos["ordenes_produccion"][0]["detalle_id"] is None
    detalle = datos["detalles"][0]
    assert [relacion["orden_produccion"]["codigo_op"] for relacion in detalle["ot_detalles"]] == ["OP-POR-PLANO"]
    # La OP no tiene id_detalle_pedido: no figura en las OP de la línea
    assert detalle["ordenes_produccion"] == []
    assert detalle["estado_cobertura"] == "PARCIAL"
