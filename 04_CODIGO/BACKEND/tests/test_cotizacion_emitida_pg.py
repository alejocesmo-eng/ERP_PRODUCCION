# tests/test_cotizacion_emitida_pg.py
"""
Migración 23 sobre PostgreSQL: cotizaciones.estado acepta EMITIDA sin perder BORRADOR,
ENVIADA, APROBADA ni RECHAZADA, y enviar al cliente una cotización en BORRADOR la guarda
en EMITIDA.

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*) con la migración 23
aplicada, dentro de una transacción que se revierte al terminar. El cliente y la cotización
se crean con el flujo normal de Ventas (POST /ventas/cotizaciones/), que registra el socio
de negocio antes de la cotización y respeta cotizaciones_id_socio_fkey.
"""
import os
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v1 import cotizaciones
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import Cotizacion, SocioNegocio

URL_PG = os.environ.get("SGI_TEST_PG_URL")

pytestmark = pytest.mark.pg

ESTADOS = {"BORRADOR", "EMITIDA", "ENVIADA", "APROBADA", "RECHAZADA"}

# Valores aceptados por cotizaciones.estado: etiquetas del ENUM o, si la columna es texto,
# la restricción chk_cotizaciones_estado
CONSULTA_TIPO = text("""
    SELECT t.typtype = 'e', a.atttypid
      FROM pg_attribute a JOIN pg_type t ON t.oid = a.atttypid
     WHERE a.attrelid = 'public.cotizaciones'::regclass AND a.attname = 'estado' AND NOT a.attisdropped
""")


@pytest.fixture
def ctx():
    assert (make_url(URL_PG).database or "").startswith("sgi_test_"), "Solo se prueba sobre copias sgi_test_*."
    engine = create_engine(URL_PG)
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")

    app = FastAPI()
    app.include_router(cotizaciones.router, prefix="/api/v1")
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


def test_la_base_acepta_emitida_y_conserva_los_demas_estados(ctx):
    _, sesion = ctx
    es_enum, tipo = sesion.execute(CONSULTA_TIPO).one()

    if es_enum:
        etiquetas = sesion.execute(
            text("SELECT enumlabel FROM pg_enum WHERE enumtypid = :tipo ORDER BY enumsortorder"), {"tipo": tipo}
        ).scalars().all()
        assert set(etiquetas) == ESTADOS
        assert etiquetas.index("EMITIDA") == etiquetas.index("BORRADOR") + 1
    else:
        definicion = sesion.execute(text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'public.cotizaciones'::regclass AND conname = 'chk_cotizaciones_estado'"
        )).scalar_one()
        assert all(f"'{estado}'" in definicion for estado in ESTADOS)


def test_enviar_borrador_al_cliente_la_guarda_emitida(ctx):
    client, sesion = ctx
    sufijo = uuid.uuid4().hex[:10].upper()
    codigo_cliente = f"CLI-T23-{sufijo}"

    # Flujo normal de Ventas: el cliente nuevo se registra en socios_negocio y luego la cotización
    creada = client.post(
        "/api/v1/ventas/cotizaciones/",
        json={
            "codigo_cliente": codigo_cliente,
            "razon_social": "Cliente prueba migración 23",
            "nit": f"T23{sufijo}",
            "contacto_email": "compras@cliente.test",
            "numero_cotizacion": f"COT-T23-{sufijo}",
            "posiciones": [{"descripcion": "Eje de prueba", "cantidad": 1, "precio_unitario": 1000}],
        },
        headers=token(),
    )
    assert creada.status_code == 201, creada.text
    assert creada.json()["estado"] == "BORRADOR"
    id_cotizacion = uuid.UUID(creada.json()["id_cotizacion"])

    socio = sesion.query(SocioNegocio).filter(SocioNegocio.codigo_socio == codigo_cliente).one()
    assert socio.es_cliente
    assert sesion.get(Cotizacion, id_cotizacion).id_socio == socio.id_socio

    respuesta = client.post(
        f"/api/v1/ventas/cotizaciones/{id_cotizacion}/enviar-cliente",
        json={"destinatario": "compras@cliente.test", "asunto": "Oferta", "mensaje": "Adjuntamos la oferta."},
        headers=token(),
    )

    assert respuesta.status_code == 200, respuesta.text
    guardado = sesion.execute(
        text("SELECT estado::text FROM cotizaciones WHERE id_cotizacion = :id"), {"id": id_cotizacion}
    ).scalar_one()
    assert guardado == "EMITIDA"
