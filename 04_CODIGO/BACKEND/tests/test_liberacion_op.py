# tests/test_liberacion_op.py
"""
Fase C: liberación de OP.

Regla: cada plano de la OP con PDF, BOM abastecida y estado APROBADO (aprobado_por y
fecha_aprobacion). PERM_OP_LIBERAR la exige; PERM_ADMIN_ALL la salta solo con motivo
de al menos 10 caracteres, con evento de trazabilidad. La misma comprobación en
PATCH /ordenes/liberar/{codigo_op}, PATCH /ordenes/{id_proyecto} y POST /ordenes/.

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*), que trae las
asignaciones de rol_permisos de la migración 16. Cada prueba corre dentro de una
transacción que se revierte al terminar.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v1 import ordenes, planos
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import (
    BOMListaMateriales,
    EstadoOPEnum,
    EstadoPlanoEnum,
    HistorialAccionesDocumento,
    OrdenProduccion,
    Plano,
    Proyecto,
)

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
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")
    app.include_router(planos.router, prefix="/api/v1/planos")
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


def token(rol: str) -> dict:
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_plano(sesion, *, con_pdf=True, estado_bom="EN_ALMACEN", aprobado=True, revision_posterior=False):
    sufijo = uuid.uuid4().hex[:8].upper()
    codigo_op = f"OP-C-{sufijo}"
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(),
        numero_pedido=f"PED-C-{sufijo}",
        codigo_proyecto=f"PRY-C-{sufijo}",
        cliente_nombre="Cliente fase C",
        detalle_producto="Pieza de prueba",
        requisitos_cliente="Según plano",
        confirmado=True,
    )
    plano = Plano(
        id_plano=uuid.uuid4(),
        id_proyecto=proyecto.id_proyecto,
        codigo_op=codigo_op,
        codigo_plano=f"PLN-C-{sufijo}",
        revision="V-01",
        archivo_url=f"/static/planos/PLN-C-{sufijo}.pdf" if con_pdf else None,
    )
    if aprobado:
        aprobado_en = datetime.now(timezone.utc) - timedelta(days=1)
        plano.estado = EstadoPlanoEnum.APROBADO
        plano.aprobado_por = "dibujante1@prueba.test"
        plano.fecha_aprobacion = aprobado_en
        plano.fecha_ultima_revision = aprobado_en + (timedelta(hours=2) if revision_posterior else -timedelta(hours=2))
    sesion.add_all([proyecto, plano])
    sesion.flush()
    if estado_bom:
        sesion.add(BOMListaMateriales(
            plano_id=plano.id_plano,
            codigo_material=f"MAT-C-{sufijo}",
            descripcion="Acero de prueba",
            cantidad_requerida=2,
            unidad_medida="KG",
            estado_abastecimiento=estado_bom,
        ))
    sesion.commit()
    return proyecto, plano


def crear_op(sesion, **kwargs):
    proyecto, plano = crear_plano(sesion, **kwargs)
    op = OrdenProduccion(
        id_op=uuid.uuid4(),
        id_proyecto=proyecto.id_proyecto,
        id_plano=plano.id_plano,
        codigo_op=plano.codigo_op,
        cantidad_fabricar=1,
    )
    sesion.add(op)
    sesion.commit()
    return op


def estado_op(sesion, codigo_op):
    sesion.expire_all()
    op = sesion.query(OrdenProduccion).filter_by(codigo_op=codigo_op).one_or_none()
    return op.estado if op else None


def reserva_stock(sesion, codigo_op):
    sesion.expire_all()
    return sesion.query(OrdenProduccion).filter_by(codigo_op=codigo_op).one().reserva_stock_100


def eventos(sesion, identificador, accion):
    sesion.expire_all()
    return sesion.query(HistorialAccionesDocumento).filter_by(
        identificador_documento=identificador, accion=accion
    ).all()


def liberar(client, op, rol, motivo=None):
    cuerpo = {"motivo": motivo} if motivo is not None else None
    return client.patch(f"/api/v1/ordenes/liberar/{op.codigo_op}", json=cuerpo, headers=token(rol))


def liberar_patch(client, op, rol, motivo=None):
    cuerpo = {"estado": EstadoOPEnum.LIBERADA.value, "motivo": motivo}
    return client.patch(f"/api/v1/ordenes/{op.id_proyecto}", json=cuerpo, headers=token(rol))


def crear_post(client, proyecto, plano, rol, motivo=None):
    cuerpo = {
        "codigo_op": plano.codigo_op,
        "id_proyecto": str(proyecto.id_proyecto),
        "id_plano": str(plano.id_plano),
        "estado": EstadoOPEnum.LIBERADA_PRODUCCION.value,
        "motivo": motivo,
    }
    return client.post("/api/v1/ordenes/", json=cuerpo, headers=token(rol))


@pytest.mark.parametrize(
    "condicion",
    [
        {"con_pdf": False},
        {"estado_bom": None},
        {"estado_bom": "EN_COMPRA"},
        {"aprobado": False},
    ],
    ids=["sin_pdf", "sin_bom", "bom_no_abastecida", "sin_plano_aprobado"],
)
def test_op_no_liberable_si_falta_una_condicion(ctx, condicion):
    client, sesion = ctx
    op = crear_op(sesion, **condicion)

    respuesta = liberar(client, op, "DISENO")

    assert respuesta.status_code == 400, respuesta.text
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.BORRADOR


def test_op_liberable_con_las_tres_condiciones(ctx):
    client, sesion = ctx
    op = crear_op(sesion)

    respuesta = liberar(client, op, "DISENO")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado_operativo"] == "LIBERADA"
    assert respuesta.json()["revisar"] is False
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.LIBERADA
    assert eventos(sesion, op.codigo_op, "OP_LIBERADA")[0].usuario_responsable == "diseno@prueba.test"
    assert eventos(sesion, op.codigo_op, "OP_LIBERADA_EXCEPCION_ADMIN") == []


def test_patch_y_post_liberan_con_las_tres_condiciones(ctx):
    client, sesion = ctx
    op = crear_op(sesion)
    respuesta = liberar_patch(client, op, "DISENO")
    assert respuesta.status_code == 200, respuesta.text
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.LIBERADA

    proyecto, plano = crear_plano(sesion)
    respuesta = crear_post(client, proyecto, plano, "DISENO")
    assert respuesta.status_code == 201, respuesta.text
    assert estado_op(sesion, plano.codigo_op) == EstadoOPEnum.LIBERADA_PRODUCCION


def test_post_sin_estado_crea_la_op_en_borrador_sin_liberarla(ctx):
    client, sesion = ctx
    proyecto, plano = crear_plano(sesion, con_pdf=False, aprobado=False)
    cuerpo = {
        "codigo_op": plano.codigo_op,
        "id_proyecto": str(proyecto.id_proyecto),
        "id_plano": str(plano.id_plano),
    }

    respuesta = client.post("/api/v1/ordenes/", json=cuerpo, headers=token("PRODUCCION"))

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["estado_produccion"] == EstadoOPEnum.BORRADOR.value
    assert estado_op(sesion, plano.codigo_op) == EstadoOPEnum.BORRADOR
    assert reserva_stock(sesion, plano.codigo_op) is False
    assert eventos(sesion, plano.codigo_op, "OP_LIBERADA_EXCEPCION_ADMIN") == []


def test_op_creada_en_borrador_activa_la_reserva_al_liberarla(ctx):
    client, sesion = ctx
    proyecto, plano = crear_plano(sesion)
    cuerpo = {"codigo_op": plano.codigo_op, "id_proyecto": str(proyecto.id_proyecto), "id_plano": str(plano.id_plano)}
    assert client.post("/api/v1/ordenes/", json=cuerpo, headers=token("DISENO")).status_code == 201
    assert reserva_stock(sesion, plano.codigo_op) is False

    respuesta = client.patch(f"/api/v1/ordenes/liberar/{plano.codigo_op}", headers=token("DISENO"))

    assert respuesta.status_code == 200, respuesta.text
    assert reserva_stock(sesion, plano.codigo_op) is True


@pytest.mark.parametrize("ruta", ["liberar", "patch", "post"])
def test_liberacion_activa_reserva_stock_100_en_las_tres_rutas(ctx, ruta):
    client, sesion = ctx
    if ruta == "post":
        proyecto, plano = crear_plano(sesion)
        respuesta = crear_post(client, proyecto, plano, "DISENO")
        codigo_op = plano.codigo_op
    else:
        op = crear_op(sesion)
        assert reserva_stock(sesion, op.codigo_op) is False
        respuesta = (liberar if ruta == "liberar" else liberar_patch)(client, op, "DISENO")
        codigo_op = op.codigo_op

    assert respuesta.status_code in (200, 201), respuesta.text
    assert reserva_stock(sesion, codigo_op) is True


def test_post_no_crea_la_op_si_no_cumple_la_regla(ctx):
    client, sesion = ctx
    proyecto, plano = crear_plano(sesion, aprobado=False)

    respuesta = crear_post(client, proyecto, plano, "DISENO")

    assert respuesta.status_code == 400, respuesta.text
    assert estado_op(sesion, plano.codigo_op) is None


@pytest.mark.parametrize("rol", ["PRODUCCION", "VENTAS"])
def test_liberacion_denegada_sin_perm_op_liberar_en_las_tres_rutas(ctx, rol):
    client, sesion = ctx
    op = crear_op(sesion)
    proyecto, plano = crear_plano(sesion)

    assert liberar(client, op, rol).status_code == 403
    assert liberar_patch(client, op, rol).status_code == 403
    assert crear_post(client, proyecto, plano, rol).status_code == 403
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.BORRADOR
    assert estado_op(sesion, plano.codigo_op) is None


@pytest.mark.parametrize("motivo", [None, "", "corto", "         x"])
def test_admin_sin_motivo_valido_es_denegado(ctx, motivo):
    client, sesion = ctx
    op = crear_op(sesion)
    proyecto, plano = crear_plano(sesion)

    assert liberar(client, op, "ADMIN", motivo).status_code == 403
    assert liberar_patch(client, op, "ADMIN", motivo).status_code == 403
    assert crear_post(client, proyecto, plano, "ADMIN", motivo).status_code == 403
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.BORRADOR
    assert estado_op(sesion, plano.codigo_op) is None


@pytest.mark.parametrize("ruta", ["liberar", "patch", "post"])
def test_admin_con_motivo_libera_saltando_la_regla_y_audita(ctx, ruta):
    client, sesion = ctx
    motivo = "Urgencia del cliente autorizada por Dirección"
    antes = datetime.now(timezone.utc)
    if ruta == "post":
        proyecto, plano = crear_plano(sesion, con_pdf=False, aprobado=False)
        respuesta = crear_post(client, proyecto, plano, "ADMIN", motivo)
        codigo_op, esperado = plano.codigo_op, EstadoOPEnum.LIBERADA_PRODUCCION
    else:
        op = crear_op(sesion, con_pdf=False, aprobado=False)
        respuesta = (liberar if ruta == "liberar" else liberar_patch)(client, op, "ADMIN", motivo)
        codigo_op, esperado = op.codigo_op, EstadoOPEnum.LIBERADA

    assert respuesta.status_code in (200, 201), respuesta.text
    assert estado_op(sesion, codigo_op) == esperado
    assert reserva_stock(sesion, codigo_op) is True
    [evento] = eventos(sesion, codigo_op, "OP_LIBERADA_EXCEPCION_ADMIN")
    assert evento.motivo_observacion == motivo
    assert evento.usuario_responsable == "admin@prueba.test"
    assert evento.fecha_hora >= antes - timedelta(seconds=5)


def test_marca_revisar_cuando_la_revision_es_posterior_a_la_aprobacion(ctx):
    client, sesion = ctx
    op = crear_op(sesion, revision_posterior=True)

    respuesta = liberar(client, op, "DISENO")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["revisar"] is True
    assert respuesta.json()["planos_revisar"] == [f"PLN-C-{op.codigo_op[5:]}"]
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.LIBERADA

    op_patch = crear_op(sesion, revision_posterior=True)
    assert liberar_patch(client, op_patch, "DISENO").json()["revisar"] is True

    proyecto, plano = crear_plano(sesion, revision_posterior=True)
    assert crear_post(client, proyecto, plano, "DISENO").json()["planos_revisar"] == [plano.codigo_plano]


def test_aprobacion_de_diseno_registra_quien_y_cuando(ctx):
    client, sesion = ctx
    _, plano = crear_plano(sesion, aprobado=False)
    antes = datetime.now(timezone.utc)

    respuesta = client.post(f"/api/v1/planos/{plano.id_plano}/aprobar", headers=token("DISENO"))

    assert respuesta.status_code == 200, respuesta.text
    sesion.expire_all()
    plano_db = sesion.get(Plano, plano.id_plano)
    assert plano_db.estado == EstadoPlanoEnum.APROBADO
    assert plano_db.aprobado_por == "diseno@prueba.test"
    assert plano_db.fecha_aprobacion >= antes - timedelta(seconds=5)
    assert respuesta.json()["aprobado_por"] == "diseno@prueba.test"
    [evento] = eventos(sesion, plano.codigo_plano, "PLANO_APROBADO")
    assert evento.usuario_responsable == "diseno@prueba.test"
    assert evento.estado_nuevo == "APROBADO"


@pytest.mark.parametrize("rol", ["PRODUCCION", "ADMIN"])
def test_aprobacion_de_plano_solo_rol_diseno(ctx, rol):
    client, sesion = ctx
    _, plano = crear_plano(sesion, aprobado=False)

    respuesta = client.post(f"/api/v1/planos/{plano.id_plano}/aprobar", headers=token(rol))

    assert respuesta.status_code == 403
    sesion.expire_all()
    assert sesion.get(Plano, plano.id_plano).estado != EstadoPlanoEnum.APROBADO
