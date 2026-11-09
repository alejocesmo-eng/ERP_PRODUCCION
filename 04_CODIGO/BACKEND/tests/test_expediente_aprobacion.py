# tests/test_expediente_aprobacion.py
"""
Expediente de la OP con el criterio por producto (D0 adaptado en E3).

El expediente muestra los planos vigentes del producto de la OP (la misma selección que la
liberación), con su aprobación de Diseño (estado, aprobado_por, fecha_aprobacion,
fecha_ultima_revision, revisar) y los archivos vigentes de planos_archivos por tipo.
quality_gate.aprobado aplica la misma regla que la liberación sobre ese conjunto.

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
from app.db.models import BOMListaMateriales, EstadoPlanoEnum, OrdenProduccion, Plano, PlanoArchivo, Producto, Proyecto

URL_PG = os.environ.get("SGI_TEST_PG_URL")

pytestmark = pytest.mark.pg

COMPLETO = {"con_pdf": True, "step": False, "estado_bom": "EN_ALMACEN", "aprobado": True, "revision": None}


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


def token(rol: str) -> dict:
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_proyecto(sesion):
    sufijo = uuid.uuid4().hex[:8].upper()
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(),
        numero_pedido=f"PED-EX-{sufijo}",
        codigo_proyecto=f"PRY-EX-{sufijo}",
        cliente_nombre="Cliente expediente",
        detalle_producto="Conjunto de prueba",
        requisitos_cliente="Según plano",
        confirmado=True,
    )
    sesion.add(proyecto)
    sesion.flush()
    return proyecto


def registrar_archivo(sesion, plano, tipo):
    contenido = f"{tipo} {plano.codigo_plano}".encode()
    sha256 = hashlib.sha256(contenido).hexdigest()
    nombre = f"{plano.codigo_plano}_{sha256[:12]}.{tipo.lower()}"
    (sesion.info["directorio"] / nombre).write_bytes(contenido)
    sesion.add(PlanoArchivo(
        id_plano=plano.id_plano, tipo=tipo, ruta=f"/static/planos/{nombre}", nombre_original=nombre,
        tamano_bytes=len(contenido), sha256=sha256, revision=plano.version, vigente=True,
        subido_por="dibujante1@prueba.test",
    ))


def crear_op(sesion, *configuraciones, proyecto_planos=None, proyecto_op=None):
    """OP de un producto RN con un plano vigente por configuración.
    revision: "posterior" o "anterior" a la aprobación, o None."""
    sufijo = uuid.uuid4().hex[:8].upper()
    producto = Producto(
        id_producto=uuid.uuid4(),
        codigo_rn=f"RN-500-600-{uuid.uuid4().int % 1000000:06d}",
        codigo_anterior=f"PROD-EX-{sufijo}",
        descripcion="Conjunto expediente",
    )
    sesion.add(producto)
    sesion.flush()
    planos_op = []
    for indice, config in enumerate(configuraciones):
        config = {**COMPLETO, **config}
        plano = Plano(
            id_plano=uuid.uuid4(),
            id_producto=producto.id_producto,
            id_proyecto=proyecto_planos.id_proyecto if proyecto_planos else None,
            codigo_plano=f"PLN-EX-{sufijo}-{indice}",
            version="V-01",
        )
        aprobado_en = datetime.now(timezone.utc) - timedelta(days=1)
        if config["aprobado"]:
            plano.estado = EstadoPlanoEnum.APROBADO
            plano.aprobado_por = "dibujante1@prueba.test"
            plano.fecha_aprobacion = aprobado_en
        if config["revision"]:
            desfase = timedelta(hours=2) if config["revision"] == "posterior" else -timedelta(hours=2)
            plano.fecha_ultima_revision = aprobado_en + desfase
        sesion.add(plano)
        sesion.flush()
        if config["con_pdf"]:
            registrar_archivo(sesion, plano, "PDF")
        if config["step"]:
            registrar_archivo(sesion, plano, "STEP")
        if config["estado_bom"]:
            sesion.add(BOMListaMateriales(
                plano_id=plano.id_plano,
                codigo_material=f"MAT-EX-{sufijo}-{indice}",
                descripcion="Acero de prueba",
                cantidad_requerida=2,
                unidad_medida="KG",
                estado_abastecimiento=config["estado_bom"],
            ))
        planos_op.append(plano)
    proyecto_op = proyecto_op or crear_proyecto(sesion)
    op = OrdenProduccion(
        id_op=uuid.uuid4(),
        id_proyecto=proyecto_op.id_proyecto,
        id_producto=producto.id_producto,
        codigo_op=f"OP-EX-{sufijo}",
        cantidad_fabricar=1,
    )
    sesion.add(op)
    sesion.commit()
    return op, planos_op


def expediente(client, op):
    respuesta = client.get(f"/api/v1/ordenes/expediente/{op.codigo_op}", headers=token("PRODUCCION"))
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


# --- D0 adaptado al producto ---

def test_expediente_devuelve_la_aprobacion_de_cada_plano(ctx):
    client, sesion = ctx
    op, planos_op = crear_op(sesion, {}, {"aprobado": False}, {"revision": "posterior"})

    datos = {plano["codigo_plano"]: plano for plano in expediente(client, op)["planos"]}

    assert set(datos) == {plano.codigo_plano for plano in planos_op}
    for plano in planos_op:
        fila = datos[plano.codigo_plano]
        for campo in ("estado", "aprobado_por", "fecha_aprobacion", "fecha_ultima_revision", "revisar"):
            assert campo in fila
        assert fila["aprobado_por"] == plano.aprobado_por
        assert fila["estado"] == (plano.estado.value if plano.estado else None)
    aprobado = datos[planos_op[0].codigo_plano]
    assert aprobado["estado"] == "APROBADO"
    assert datetime.fromisoformat(aprobado["fecha_aprobacion"]) == planos_op[0].fecha_aprobacion
    sin_aprobar = datos[planos_op[1].codigo_plano]
    assert sin_aprobar["estado"] != "APROBADO"
    assert sin_aprobar["aprobado_por"] is None
    assert sin_aprobar["fecha_aprobacion"] is None
    assert datos[planos_op[2].codigo_plano]["fecha_ultima_revision"] is not None


@pytest.mark.parametrize(
    ("config", "esperado"),
    [
        ({"revision": "posterior"}, True),
        ({"revision": "anterior"}, False),
        ({"revision": None}, False),
        ({"aprobado": False, "revision": "posterior"}, False),
    ],
    ids=["revision_posterior", "revision_anterior", "sin_revision", "sin_aprobacion"],
)
def test_marca_revisar_en_expediente_y_en_plano_response(ctx, config, esperado):
    client, sesion = ctx
    op, [plano] = crear_op(sesion, config)

    assert expediente(client, op)["planos"][0]["revisar"] is esperado

    listado = client.get("/api/v1/planos/").json()
    [plano_response] = [item for item in listado if item["id_plano"] == str(plano.id_plano)]
    assert plano_response["revisar"] is esperado
    for campo in ("estado", "aprobado_por", "fecha_aprobacion", "fecha_ultima_revision"):
        assert campo in plano_response


def test_quality_gate_falso_si_un_plano_no_esta_aprobado_aunque_tenga_pdf_y_bom(ctx):
    client, sesion = ctx
    op, planos_op = crear_op(sesion, {}, {"aprobado": False}, {})

    gate = expediente(client, op)["quality_gate"]

    assert gate["aprobado"] is False
    assert any(planos_op[1].codigo_plano in motivo and "APROBADO" in motivo for motivo in gate["motivos"])
    # Coincide con la liberación
    assert client.patch(f"/api/v1/ordenes/liberar/{op.codigo_op}", headers=token("DISENO")).status_code == 400


@pytest.mark.parametrize(
    "fallo",
    [{"aprobado": False}, {"con_pdf": False}, {"estado_bom": None}, {"estado_bom": "EN_COMPRA"}],
    ids=["sin_aprobar", "sin_pdf", "sin_bom", "bom_no_abastecida"],
)
def test_quality_gate_falso_si_un_plano_falla_cualquier_condicion(ctx, fallo):
    client, sesion = ctx
    op, _ = crear_op(sesion, {}, {}, fallo)

    assert expediente(client, op)["quality_gate"]["aprobado"] is False
    assert client.patch(f"/api/v1/ordenes/liberar/{op.codigo_op}", headers=token("DISENO")).status_code == 400


def test_quality_gate_verdadero_cuando_los_tres_planos_cumplen(ctx):
    client, sesion = ctx
    op, planos_op = crear_op(sesion, {}, {}, {"revision": "posterior"})

    datos = expediente(client, op)

    assert len(datos["planos"]) == 3
    assert datos["quality_gate"] == {"aprobado": True, "motivos": []}
    # Coincide con la liberación; "revisar" solo avisa
    respuesta = client.patch(f"/api/v1/ordenes/liberar/{op.codigo_op}", headers=token("DISENO"))
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["planos_revisar"] == [planos_op[2].codigo_plano]


# --- E3: selección por producto y archivos vigentes ---

def test_expediente_muestra_los_planos_del_producto_incluidos_los_de_otro_pedido(ctx):
    client, sesion = ctx
    otro_pedido = crear_proyecto(sesion)
    op, planos_op = crear_op(sesion, {}, {}, proyecto_planos=otro_pedido)
    # Plano de otro producto en el mismo pedido de la OP: no se muestra
    ajeno = Plano(
        id_plano=uuid.uuid4(),
        id_proyecto=op.id_proyecto,
        codigo_op=op.codigo_op,
        codigo_plano=f"PLN-AJENO-{uuid.uuid4().hex[:6]}",
        version="V-01",
    )
    sesion.add(ajeno)
    sesion.commit()

    datos = expediente(client, op)

    assert {p["codigo_plano"] for p in datos["planos"]} == {p.codigo_plano for p in planos_op}
    assert datos["producto"]["codigo_rn"].startswith("RN-500-600-")
    assert datos["quality_gate"]["aprobado"] is True


def test_expediente_muestra_los_archivos_vigentes_por_tipo(ctx):
    client, sesion = ctx
    op, [plano] = crear_op(sesion, {"step": True})
    sesion.expire_all()
    vigentes = {a.tipo: a for a in sesion.query(PlanoArchivo).filter_by(id_plano=plano.id_plano, vigente=True)}

    [fila] = expediente(client, op)["planos"]

    assert fila["archivo_pdf_url"] == fila["archivo_url"] == vigentes["PDF"].ruta
    assert fila["archivo_step_url"] == vigentes["STEP"].ruta
    assert fila["archivo_dxf_url"] is None
    assert set(fila["archivos"]) == {"PDF", "STEP"}
    assert fila["archivos"]["PDF"]["sha256"] == vigentes["PDF"].sha256
    assert fila["archivos"]["PDF"]["tamano_bytes"] == vigentes["PDF"].tamano_bytes


def test_expediente_de_op_sin_producto_no_muestra_planos_y_no_aprueba(ctx):
    client, sesion = ctx
    proyecto = crear_proyecto(sesion)
    plano = Plano(id_plano=uuid.uuid4(), id_proyecto=proyecto.id_proyecto, codigo_op="OP-SIN-PROD",
                  codigo_plano=f"PLN-SP-{uuid.uuid4().hex[:6]}", version="V-01")
    op = OrdenProduccion(id_op=uuid.uuid4(), id_proyecto=proyecto.id_proyecto, id_plano=plano.id_plano,
                         codigo_op=f"OP-SP-{uuid.uuid4().hex[:6]}", cantidad_fabricar=1)
    sesion.add_all([plano, op])
    sesion.commit()

    datos = expediente(client, op)

    assert datos["planos"] == []
    assert datos["producto"] is None
    assert datos["quality_gate"]["aprobado"] is False
    assert "no tiene producto asignado" in datos["quality_gate"]["motivos"][0]


# --- Historial de planos (migración 21) ---

def test_expediente_trae_la_linea_de_tiempo_de_cada_plano(ctx):
    client, sesion = ctx
    op, [plano] = crear_op(sesion, {"aprobado": False})
    justificacion = "Revisión de tolerancias con el cliente"

    assert client.post(f"/api/v1/planos/{plano.id_plano}/aprobar", headers=token("DISENO")).status_code == 200
    respuesta = client.post(
        f"/api/v1/planos/{plano.id_plano}/revision", json={"justificacion": justificacion}, headers=token("DISENO")
    )
    assert respuesta.status_code == 200, respuesta.text

    [fila] = expediente(client, op)["planos"]
    assert [(e["tipo_evento"], e["usuario"], e["justificacion"]) for e in fila["historial"]] == [
        ("APROBACION", "diseno@prueba.test", None),
        ("REVISION", "diseno@prueba.test", justificacion),
    ]
    assert fila["revisar"] is True
    assert client.get(f"/api/v1/planos/{plano.id_plano}/historial", headers=token("PRODUCCION")).json() == fila["historial"]
