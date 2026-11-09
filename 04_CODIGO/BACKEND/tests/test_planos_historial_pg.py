# tests/test_planos_historial_pg.py
"""
Migración 21: planos_historial es append-only en PostgreSQL.
El trigger rechaza UPDATE y DELETE, la base exige la justificación y la FK RESTRICT impide
borrar un plano con historial.

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*) con la migración 21
aplicada, dentro de una transacción que se revierte al terminar.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.models import Plano, PlanoHistorial

URL_PG = os.environ.get("SGI_TEST_PG_URL")

pytestmark = pytest.mark.pg

SHA_PRUEBA = "a" * 64


@pytest.fixture
def sesion():
    assert (make_url(URL_PG).database or "").startswith("sgi_test_"), "Solo se prueba sobre copias sgi_test_*."
    engine = create_engine(URL_PG)
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()
        engine.dispose()


def crear_plano_con_evento(sesion):
    sufijo = uuid.uuid4().hex[:8].upper()
    plano = Plano(id_plano=uuid.uuid4(), codigo_plano=f"PLN-HI-{sufijo}", version="V-01", estado_diseno="EN_DISENO")
    sesion.add(plano)
    sesion.flush()
    evento = PlanoHistorial(
        id_plano=plano.id_plano,
        tipo_evento="CAMBIO_ARCHIVO",
        version="V-01",
        estado="EN_DISENO",
        tipo_archivo="PDF",
        sha256=SHA_PRUEBA,
        usuario="dibujante1@prueba.test",
        justificacion="Corrección de cotas en la vista lateral",
    )
    sesion.add(evento)
    sesion.flush()
    return plano, evento


def ejecutar_y_esperar_error(sesion, sentencia, parametros):
    """Ejecuta en un savepoint propio para que el error no aborte la transacción de la prueba."""
    with pytest.raises(DBAPIError) as error:
        with sesion.begin_nested():
            sesion.execute(text(sentencia), parametros)
    return str(error.value.orig)


def test_insert_valido_guarda_el_evento_con_fecha_del_servidor(sesion):
    _, evento = crear_plano_con_evento(sesion)

    fila = sesion.execute(
        text("SELECT tipo_evento, sha256, fecha FROM planos_historial WHERE id_evento = :id"),
        {"id": evento.id_evento},
    ).one()
    assert fila.tipo_evento == "CAMBIO_ARCHIVO"
    assert fila.sha256 == SHA_PRUEBA
    assert fila.fecha is not None


def test_update_es_rechazado_por_el_trigger(sesion):
    _, evento = crear_plano_con_evento(sesion)

    mensaje = ejecutar_y_esperar_error(
        sesion,
        "UPDATE planos_historial SET justificacion = 'Texto reescrito después' WHERE id_evento = :id",
        {"id": evento.id_evento},
    )
    assert "append-only" in mensaje


def test_delete_es_rechazado_por_el_trigger(sesion):
    _, evento = crear_plano_con_evento(sesion)

    mensaje = ejecutar_y_esperar_error(
        sesion, "DELETE FROM planos_historial WHERE id_evento = :id", {"id": evento.id_evento}
    )
    assert "append-only" in mensaje


@pytest.mark.parametrize("justificacion", [None, "corta", "          "])
def test_la_base_exige_justificacion_en_cambio_de_version(sesion, justificacion):
    plano, _ = crear_plano_con_evento(sesion)

    mensaje = ejecutar_y_esperar_error(
        sesion,
        "INSERT INTO planos_historial (id_plano, tipo_evento, version, usuario, justificacion) "
        "VALUES (:id_plano, 'CAMBIO_VERSION', 'V-02', 'dibujante1@prueba.test', :justificacion)",
        {"id_plano": plano.id_plano, "justificacion": justificacion},
    )
    assert "ck_planos_historial_justificacion" in mensaje


def test_la_base_rechaza_un_sha256_con_formato_invalido(sesion):
    plano, _ = crear_plano_con_evento(sesion)

    mensaje = ejecutar_y_esperar_error(
        sesion,
        "INSERT INTO planos_historial (id_plano, tipo_evento, tipo_archivo, sha256, usuario) "
        "VALUES (:id_plano, 'CARGA_ARCHIVO', 'PDF', :sha, 'dibujante1@prueba.test')",
        {"id_plano": plano.id_plano, "sha": "Z" * 64},
    )
    assert "ck_planos_historial_sha256" in mensaje


def test_no_se_puede_borrar_un_plano_con_historial(sesion):
    plano, _ = crear_plano_con_evento(sesion)

    mensaje = ejecutar_y_esperar_error(
        sesion, "DELETE FROM planos WHERE id_plano = :id", {"id": plano.id_plano}
    )
    assert "planos_historial" in mensaje
