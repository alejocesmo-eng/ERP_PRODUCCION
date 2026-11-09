# tests/test_liberacion_producto.py
"""
Fase E3: liberación por producto y creación de la OP desde la línea de pedido.

La OP toma id_producto de la línea de pedido (POST /ordenes/ con detalle_id). La liberación
evalúa los planos vigentes de ese producto (última fila por creado_en de cada codigo_plano,
sin OBSOLETO): PDF vigente en planos_archivos con archivo en disco, BOM abastecida y plano
APROBADO. Sin id_producto, 400 sin otro criterio. STEP y DXF no bloquean.

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*), dentro de una
transacción que se revierte al terminar; los archivos se escriben en un directorio temporal.
"""
import hashlib
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
    OrdenProduccion,
    PedidoDetalle,
    Plano,
    PlanoArchivo,
    Producto,
    Proyecto,
)

URL_PG = os.environ.get("SGI_TEST_PG_URL")

pytestmark = pytest.mark.pg

COMPLETO = {"pdf": True, "step": False, "dxf": False, "estado_bom": "EN_ALMACEN", "aprobado": True}


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    assert (make_url(URL_PG).database or "").startswith("sgi_test_"), "Solo se prueba sobre copias sgi_test_*."
    monkeypatch.setattr(planos, "DIRECTORIO_STATIC_PLANOS", str(tmp_path))
    engine = create_engine(URL_PG)
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    sesion.info["directorio"] = tmp_path

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


def token(rol="DISENO"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def sufijo():
    return uuid.uuid4().hex[:8].upper()


def crear_proyecto(sesion):
    s = sufijo()
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(),
        numero_pedido=f"PED-E3-{s}",
        codigo_proyecto=f"PRY-E3-{s}",
        cliente_nombre="Cliente E3",
        requisitos_cliente="Según plano",
        confirmado=True,
    )
    sesion.add(proyecto)
    sesion.flush()
    return proyecto


def registrar_archivo(sesion, plano, tipo, vigente=True, en_disco=True):
    contenido = f"{tipo} {plano.codigo_plano} {uuid.uuid4()}".encode()
    sha256 = hashlib.sha256(contenido).hexdigest()
    nombre = f"{plano.codigo_plano}_{sha256[:12]}.{tipo.lower()}"
    if en_disco:
        (sesion.info["directorio"] / nombre).write_bytes(contenido)
    sesion.add(PlanoArchivo(
        id_plano=plano.id_plano, tipo=tipo, ruta=f"/static/planos/{nombre}", nombre_original=nombre,
        tamano_bytes=len(contenido), sha256=sha256, revision=plano.version, vigente=vigente,
    ))


def crear_plano(sesion, producto, proyecto=None, codigo_plano=None, creado_en=None, estado=None, **config):
    config = {**COMPLETO, **config}
    plano = Plano(
        id_plano=uuid.uuid4(),
        id_producto=producto.id_producto,
        id_proyecto=proyecto.id_proyecto if proyecto else None,
        codigo_plano=codigo_plano or f"PLN-E3-{sufijo()}",
        version="V-01",
        creado_en=creado_en or datetime.now(timezone.utc),
    )
    if config["aprobado"]:
        plano.estado = EstadoPlanoEnum.APROBADO
        plano.aprobado_por = "dibujante1@prueba.test"
        plano.fecha_aprobacion = datetime.now(timezone.utc) - timedelta(days=1)
    if estado:
        plano.estado = estado
    sesion.add(plano)
    sesion.flush()
    if config["pdf"]:
        registrar_archivo(sesion, plano, "PDF", en_disco=config.get("pdf_en_disco", True))
    for tipo in ("STEP", "DXF"):
        if config[tipo.lower()]:
            registrar_archivo(sesion, plano, tipo)
    if config["estado_bom"]:
        sesion.add(BOMListaMateriales(
            plano_id=plano.id_plano, codigo_material=f"MAT-E3-{sufijo()}", descripcion="Acero",
            cantidad_requerida=1, unidad_medida="KG", estado_abastecimiento=config["estado_bom"],
        ))
    sesion.flush()
    return plano


def crear_producto(sesion, *configuraciones, proyecto=None):
    producto = Producto(
        id_producto=uuid.uuid4(),
        codigo_rn=f"RN-300-400-{uuid.uuid4().int % 1000000:06d}",
        descripcion="Conjunto E3",
    )
    sesion.add(producto)
    sesion.flush()
    planos_producto = [crear_plano(sesion, producto, proyecto, **config) for config in configuraciones]
    sesion.commit()
    return producto, planos_producto


def crear_linea(sesion, proyecto, producto):
    linea = PedidoDetalle(
        detalle_id=uuid.uuid4(),
        pedido_id=proyecto.id_proyecto,
        codigo_producto=f"PROD-E3-{sufijo()}",
        id_producto=producto.id_producto if producto else None,
        descripcion="Línea E3",
        cantidad_solicitada=2,
    )
    sesion.add(linea)
    sesion.commit()
    return linea


def crear_op(sesion, producto, proyecto=None):
    proyecto = proyecto or crear_proyecto(sesion)
    op = OrdenProduccion(
        id_op=uuid.uuid4(),
        id_proyecto=proyecto.id_proyecto,
        id_producto=producto.id_producto if producto else None,
        codigo_op=f"OP-E3-{sufijo()}",
        cantidad_fabricar=1,
    )
    sesion.add(op)
    sesion.commit()
    return op


def liberar(client, op, rol="DISENO", motivo=None):
    return client.patch(
        f"/api/v1/ordenes/liberar/{op.codigo_op}",
        json={"motivo": motivo} if motivo else None,
        headers=token(rol),
    )


def estado_op(sesion, codigo_op):
    sesion.expire_all()
    op = sesion.query(OrdenProduccion).filter_by(codigo_op=codigo_op).one_or_none()
    return op.estado if op else None


# --- OP sin producto ---

@pytest.mark.parametrize(("rol", "motivo"), [("DISENO", None), ("ADMIN", "Urgencia autorizada por Dirección")])
def test_op_sin_id_producto_no_libera_y_devuelve_400(ctx, rol, motivo):
    client, sesion = ctx
    op = crear_op(sesion, None)

    respuesta = liberar(client, op, rol, motivo)

    assert respuesta.status_code == 400
    assert "no tiene producto asignado" in respuesta.json()["detail"]
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.BORRADOR
    respuesta = client.patch(
        f"/api/v1/ordenes/{op.id_proyecto}", json={"estado": "LIBERADA", "motivo": motivo}, headers=token(rol)
    )
    assert respuesta.status_code == 400
    assert "no tiene producto asignado" in respuesta.json()["detail"]


def test_op_sin_id_producto_sigue_exigiendo_permiso(ctx):
    client, sesion = ctx
    op = crear_op(sesion, None)

    assert liberar(client, op, "PRODUCCION").status_code == 403


# --- Producto con tres planos ---

def test_producto_con_tres_planos_uno_sin_aprobar_no_libera(ctx):
    client, sesion = ctx
    producto, planos_producto = crear_producto(sesion, {}, {"aprobado": False}, {})
    op = crear_op(sesion, producto)

    respuesta = liberar(client, op)

    assert respuesta.status_code == 400
    assert planos_producto[1].codigo_plano in respuesta.json()["detail"]
    assert "APROBADO" in respuesta.json()["detail"]
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.BORRADOR


def test_producto_con_tres_planos_aprobados_con_pdf_vigente_libera(ctx):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {}, {}, {})
    op = crear_op(sesion, producto)

    respuesta = liberar(client, op)

    assert respuesta.status_code == 200, respuesta.text
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.LIBERADA


def test_step_o_dxf_faltante_no_bloquea(ctx):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {"step": True, "dxf": True}, {"step": True}, {"dxf": True})
    op = crear_op(sesion, producto)

    assert liberar(client, op).status_code == 200


@pytest.mark.parametrize(
    ("config", "mensaje"),
    [
        ({"pdf": False, "step": True, "dxf": True}, "no tiene un PDF vigente"),
        ({"pdf": True, "pdf_en_disco": False}, "no existe en el almacenamiento"),
    ],
    ids=["sin_registro_pdf", "pdf_sin_archivo_en_disco"],
)
def test_pdf_faltante_bloquea(ctx, config, mensaje):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {}, config, {})
    op = crear_op(sesion, producto)

    respuesta = liberar(client, op)

    assert respuesta.status_code == 400
    assert mensaje in respuesta.json()["detail"]
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.BORRADOR


def test_pdf_solo_historico_no_cuenta_como_vigente(ctx):
    client, sesion = ctx
    producto, [plano] = crear_producto(sesion, {"pdf": False})
    registrar_archivo(sesion, plano, "PDF", vigente=False)
    sesion.commit()
    op = crear_op(sesion, producto)

    respuesta = liberar(client, op)

    assert respuesta.status_code == 400
    assert "no tiene un PDF vigente" in respuesta.json()["detail"]


def alterar_pdf_en_disco(sesion, plano):
    sesion.expire_all()
    pdf = sesion.query(PlanoArchivo).filter_by(id_plano=plano.id_plano, tipo="PDF", vigente=True).one()
    (sesion.info["directorio"] / os.path.basename(pdf.ruta)).write_bytes(b"%PDF contenido alterado")


@pytest.mark.parametrize("ruta", ["liberar", "patch", "post"])
def test_pdf_alterado_en_disco_impide_la_liberacion_con_409(ctx, ruta):
    client, sesion = ctx
    producto, planos_producto = crear_producto(sesion, {}, {}, {})
    alterar_pdf_en_disco(sesion, planos_producto[1])
    if ruta == "post":
        linea = crear_linea(sesion, crear_proyecto(sesion), producto)
        codigo_op = f"OP-E3-{sufijo()}"
        respuesta = client.post(
            "/api/v1/ordenes/",
            json={"codigo_op": codigo_op, "detalle_id": str(linea.detalle_id), "estado": "LIBERADA_PRODUCCION"},
            headers=token(),
        )
        assert estado_op(sesion, codigo_op) is None
    else:
        op = crear_op(sesion, producto)
        if ruta == "liberar":
            respuesta = liberar(client, op)
        else:
            respuesta = client.patch(f"/api/v1/ordenes/{op.id_proyecto}", json={"estado": "LIBERADA"}, headers=token())
        assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.BORRADOR

    assert respuesta.status_code == 409, respuesta.text
    assert planos_producto[1].codigo_plano in respuesta.json()["detail"]
    assert "sha256" in respuesta.json()["detail"]


def test_pdf_integro_permite_la_liberacion_y_el_expediente_lo_aprueba(ctx):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {}, {}, {})
    op = crear_op(sesion, producto)

    gate = client.get(f"/api/v1/ordenes/expediente/{op.codigo_op}", headers=token("PRODUCCION")).json()["quality_gate"]
    assert gate == {"aprobado": True, "motivos": []}
    assert liberar(client, op).status_code == 200


def test_expediente_no_aprueba_un_pdf_alterado(ctx):
    client, sesion = ctx
    producto, planos_producto = crear_producto(sesion, {}, {})
    alterar_pdf_en_disco(sesion, planos_producto[0])
    op = crear_op(sesion, producto)

    gate = client.get(f"/api/v1/ordenes/expediente/{op.codigo_op}", headers=token("PRODUCCION")).json()["quality_gate"]

    assert gate["aprobado"] is False
    assert any("sha256" in motivo for motivo in gate["motivos"])


RUTAS_LIBERACION = ["liberar", "patch_liberada", "post_liberada", "patch_lista", "post_lista", "plano_liberada"]
CASOS_REGLA = {
    "sin_pdf_vigente": ({"pdf": False}, 400),
    "pdf_alterado": ({}, 409),
    "plano_sin_aprobar": ({"aprobado": False}, 400),
    "bom_solo_radicada": ({"estado_bom": "SOLICITADO"}, 400),
    "cumple": ({}, None),
}


def ejecutar_ruta(client, sesion, ruta, producto, plano):
    """Lleva la OP (o el plano) al estado de la ruta y devuelve (respuesta, código de éxito, comprobación de estado)."""
    if ruta == "plano_liberada":
        respuesta = client.patch(
            f"/api/v1/planos/{plano.id_plano}", json={"estado_diseno": "LIBERADA"}, headers=token()
        )
        if respuesta.status_code != 200:
            sesion.rollback()  # fin de la petición rechazada: get_db cierra la sesión sin commit
        sesion.expire_all()
        return respuesta, 200, sesion.get(Plano, plano.id_plano).estado_diseno == "LIBERADA"
    if ruta.startswith("post_"):
        estado = "LIBERADA_PRODUCCION" if ruta == "post_liberada" else "LISTA_PARA_LIBERAR"
        linea = crear_linea(sesion, crear_proyecto(sesion), producto)
        codigo_op = f"OP-E3-{sufijo()}"
        respuesta = client.post(
            "/api/v1/ordenes/",
            json={"codigo_op": codigo_op, "detalle_id": str(linea.detalle_id), "estado": estado},
            headers=token(),
        )
        return respuesta, 201, estado_op(sesion, codigo_op) is not None
    op = crear_op(sesion, producto)
    if ruta == "liberar":
        respuesta = liberar(client, op)
    elif ruta == "patch_liberada":
        respuesta = client.patch(f"/api/v1/ordenes/{op.id_proyecto}", json={"estado": "LIBERADA"}, headers=token())
    else:
        respuesta = client.patch(
            f"/api/v1/ordenes/{op.id_proyecto}", json={"estado": "LISTA_PARA_LIBERAR"}, headers=token("PRODUCCION")
        )
    return respuesta, 200, estado_op(sesion, op.codigo_op) != EstadoOPEnum.BORRADOR


@pytest.mark.parametrize("caso", list(CASOS_REGLA))
@pytest.mark.parametrize("ruta", RUTAS_LIBERACION)
def test_cada_ruta_de_liberacion_aplica_la_misma_regla(ctx, ruta, caso):
    client, sesion = ctx
    config, codigo_rechazo = CASOS_REGLA[caso]
    producto, [plano] = crear_producto(sesion, config)
    if caso == "pdf_alterado":
        alterar_pdf_en_disco(sesion, plano)

    respuesta, codigo_exito, cambio_estado = ejecutar_ruta(client, sesion, ruta, producto, plano)

    if codigo_rechazo is None:
        assert respuesta.status_code == codigo_exito, respuesta.text
        assert cambio_estado
    else:
        assert respuesta.status_code == codigo_rechazo, respuesta.text
        assert not cambio_estado


@pytest.mark.parametrize("estado_bom", ["SOLICITADO", "EN_COMPRA"])
def test_liberacion_de_op_con_bom_solo_radicada_no_pasa(ctx, estado_bom):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {"estado_bom": estado_bom})
    op = crear_op(sesion, producto)

    respuesta = liberar(client, op)

    assert respuesta.status_code == 400
    assert "pendientes de almacén" in respuesta.json()["detail"]
    assert estado_op(sesion, op.codigo_op) == EstadoOPEnum.BORRADOR


def test_bom_no_abastecida_bloquea(ctx):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {}, {"estado_bom": "EN_COMPRA"})
    op = crear_op(sesion, producto)

    assert liberar(client, op).status_code == 400


# --- Planos vigentes: última fila por creado_en, sin OBSOLETO ---

def test_cuenta_la_ultima_revision_de_cada_plano(ctx):
    client, sesion = ctx
    ahora = datetime.now(timezone.utc)
    producto, _ = crear_producto(sesion)
    crear_plano(sesion, producto, codigo_plano="PLN-E3-REV", creado_en=ahora - timedelta(days=2))
    crear_plano(sesion, producto, codigo_plano="PLN-E3-REV", creado_en=ahora, aprobado=False)
    sesion.commit()
    op = crear_op(sesion, producto)

    respuesta = liberar(client, op)

    assert respuesta.status_code == 400
    assert "PLN-E3-REV" in respuesta.json()["detail"]


def test_la_revision_obsoleta_no_cuenta(ctx):
    client, sesion = ctx
    ahora = datetime.now(timezone.utc)
    producto, _ = crear_producto(sesion)
    crear_plano(sesion, producto, codigo_plano="PLN-E3-OBS", creado_en=ahora - timedelta(days=2))
    crear_plano(sesion, producto, codigo_plano="PLN-E3-OBS", creado_en=ahora, aprobado=False,
                estado=EstadoPlanoEnum.OBSOLETO, pdf=False)
    sesion.commit()
    op = crear_op(sesion, producto)

    assert liberar(client, op).status_code == 200


def test_producto_sin_planos_vigentes_no_libera(ctx):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {"estado": EstadoPlanoEnum.OBSOLETO})
    op = crear_op(sesion, producto)

    respuesta = liberar(client, op)

    assert respuesta.status_code == 400
    assert "no tiene planos vigentes" in respuesta.json()["detail"]


def test_op_de_un_pedido_libera_con_planos_creados_en_otro_pedido(ctx):
    client, sesion = ctx
    otro_pedido = crear_proyecto(sesion)
    producto, _ = crear_producto(sesion, {}, {}, proyecto=otro_pedido)
    op = crear_op(sesion, producto, proyecto=crear_proyecto(sesion))

    assert liberar(client, op).status_code == 200


# --- POST /ordenes/ desde la línea de pedido ---

def test_post_toma_id_producto_de_la_linea_de_pedido(ctx):
    client, sesion = ctx
    producto, planos_producto = crear_producto(sesion, {}, {})
    proyecto = crear_proyecto(sesion)
    linea = crear_linea(sesion, proyecto, producto)
    codigo_op = f"OP-E3-{sufijo()}"

    respuesta = client.post(
        "/api/v1/ordenes/", json={"codigo_op": codigo_op, "detalle_id": str(linea.detalle_id)}, headers=token()
    )

    assert respuesta.status_code == 201, respuesta.text
    sesion.expire_all()
    op = sesion.query(OrdenProduccion).filter_by(codigo_op=codigo_op).one()
    assert op.id_producto == producto.id_producto
    assert op.id_proyecto == proyecto.id_proyecto
    assert op.id_plano in {plano.id_plano for plano in planos_producto}
    assert op.estado == EstadoOPEnum.BORRADOR
    assert sesion.get(PedidoDetalle, linea.detalle_id).codigo_producto == linea.codigo_producto


def crear_op_por_post(client, linea):
    codigo_op = f"OP-E3-{sufijo()}"
    respuesta = client.post(
        "/api/v1/ordenes/", json={"codigo_op": codigo_op, "detalle_id": str(linea.detalle_id)}, headers=token()
    )
    return respuesta, codigo_op


def test_una_op_activa_por_linea_y_cancelada_libera_la_linea(ctx):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {})
    linea = crear_linea(sesion, crear_proyecto(sesion), producto)

    primera, codigo_primera = crear_op_por_post(client, linea)
    assert primera.status_code == 201, primera.text
    sesion.expire_all()
    op_primera = sesion.query(OrdenProduccion).filter_by(codigo_op=codigo_primera).one()
    assert op_primera.id_detalle_pedido == linea.detalle_id

    segunda, codigo_segunda = crear_op_por_post(client, linea)
    assert segunda.status_code == 409
    assert codigo_primera in segunda.json()["detail"]
    assert estado_op(sesion, codigo_segunda) is None

    cancelar = client.patch(
        f"/api/v1/ordenes/{op_primera.id_op}", json={"estado": "CANCELADA"}, headers=token("PRODUCCION")
    )
    assert cancelar.status_code == 200, cancelar.text

    tercera, codigo_tercera = crear_op_por_post(client, linea)
    assert tercera.status_code == 201, tercera.text
    assert estado_op(sesion, codigo_tercera) == EstadoOPEnum.BORRADOR
    assert estado_op(sesion, codigo_primera) == EstadoOPEnum.CANCELADA


def test_varias_op_de_productos_distintos_del_mismo_pedido(ctx):
    client, sesion = ctx
    proyecto = crear_proyecto(sesion)
    producto_a, _ = crear_producto(sesion, {})
    producto_b, _ = crear_producto(sesion, {})
    linea_a = crear_linea(sesion, proyecto, producto_a)
    linea_b = crear_linea(sesion, proyecto, producto_b)

    assert crear_op_por_post(client, linea_a)[0].status_code == 201
    assert crear_op_por_post(client, linea_b)[0].status_code == 201
    assert crear_op_por_post(client, linea_a)[0].status_code == 409


def test_post_con_estado_liberado_aplica_la_regla_del_producto(ctx):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {}, {"aprobado": False})
    linea = crear_linea(sesion, crear_proyecto(sesion), producto)
    codigo_op = f"OP-E3-{sufijo()}"

    respuesta = client.post(
        "/api/v1/ordenes/",
        json={"codigo_op": codigo_op, "detalle_id": str(linea.detalle_id), "estado": "LIBERADA_PRODUCCION"},
        headers=token(),
    )

    assert respuesta.status_code == 400
    assert estado_op(sesion, codigo_op) is None


def test_linea_de_pedido_sin_producto_devuelve_400(ctx):
    client, sesion = ctx
    linea = crear_linea(sesion, crear_proyecto(sesion), None)
    codigo_op = f"OP-E3-{sufijo()}"

    respuesta = client.post(
        "/api/v1/ordenes/", json={"codigo_op": codigo_op, "detalle_id": str(linea.detalle_id)}, headers=token()
    )

    assert respuesta.status_code == 400
    assert "La línea de pedido no tiene producto asignado" in respuesta.json()["detail"]
    assert estado_op(sesion, codigo_op) is None


@pytest.mark.parametrize("caso", ["detalle_inexistente", "sin_detalle_id", "pedido_distinto", "plano_de_otro_producto"])
def test_post_valida_la_linea_de_pedido(ctx, caso):
    client, sesion = ctx
    producto, _ = crear_producto(sesion, {})
    _, [plano_ajeno] = crear_producto(sesion, {})
    linea = crear_linea(sesion, crear_proyecto(sesion), producto)
    cuerpo = {"codigo_op": f"OP-E3-{sufijo()}", "detalle_id": str(linea.detalle_id)}
    esperado = 400
    if caso == "detalle_inexistente":
        cuerpo["detalle_id"], esperado = str(uuid.uuid4()), 404
    elif caso == "sin_detalle_id":
        del cuerpo["detalle_id"]
        esperado = 422
    elif caso == "pedido_distinto":
        cuerpo["id_proyecto"] = str(crear_proyecto(sesion).id_proyecto)
    else:
        cuerpo["id_plano"] = str(plano_ajeno.id_plano)

    respuesta = client.post("/api/v1/ordenes/", json=cuerpo, headers=token())

    assert respuesta.status_code == esperado, respuesta.text
    assert estado_op(sesion, cuerpo["codigo_op"]) is None
