# tests/test_socios_codigo_nit_pg.py
"""
SCRUM-22 sobre PostgreSQL: con la migración 24 aplicada, codigo_socio es el NIT solo con
números, el alta desde Datos Maestros funciona sin error, la búsqueda por NIT devuelve
codigo_socio y no se crean clientes sin NIT.

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*) con la migración 24
aplicada, dentro de una transacción que se revierte al terminar.
"""
import os
import random
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1 import cotizaciones, maestros
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import SocioNegocio
from app.services import socios as regla

URL_PG = os.environ.get("SGI_TEST_PG_URL")
MIGRACION_24 = Path(__file__).resolve().parents[3] / "05_BASE_DATOS" / "24_MIGRACION_SOCIOS_CODIGO_NIT.sql"

pytestmark = pytest.mark.pg


@pytest.fixture
def ctx():
    assert (make_url(URL_PG).database or "").startswith("sgi_test_"), "Solo se prueba sobre copias sgi_test_*."
    engine = create_engine(URL_PG)
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")

    app = FastAPI()
    app.include_router(maestros.router, prefix="/api/v1/maestros")
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


def token(rol="ADMIN"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def nit_libre(sesion):
    """NIT de 9 dígitos que empieza por 7 y no está en uso en la copia."""
    while True:
        codigo = f"7{random.randint(0, 99_999_999):08d}"
        if not sesion.query(SocioNegocio).filter(SocioNegocio.codigo_socio == codigo).first():
            return codigo


def test_la_migracion_24_dejo_codigo_socio_obligatorio_y_numerico(ctx):
    _, sesion = ctx

    nulo = sesion.execute(text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'socios_negocio' AND column_name = 'codigo_socio'"
    )).scalar_one()
    definicion = sesion.execute(text(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'public.socios_negocio'::regclass AND conname = 'ck_socios_negocio_codigo_nit'"
    )).scalar_one()
    unico = sesion.execute(text(
        "SELECT indisunique FROM pg_index WHERE indexrelid = 'public.ix_socios_negocio_codigo_socio'::regclass"
    )).scalar_one()
    fuera_de_regla = sesion.execute(text(
        "SELECT count(*) FROM socios_negocio WHERE codigo_socio !~ '^[0-9]{5,15}$'"
    )).scalar_one()

    assert nulo == "NO"
    assert "[0-9]{5,15}" in definicion
    assert unico is True
    assert fuera_de_regla == 0


def test_la_base_rechaza_un_codigo_que_no_es_nit(ctx):
    _, sesion = ctx
    with pytest.raises(IntegrityError, match="ck_socios_negocio_codigo_nit"):
        with sesion.begin_nested():
            sesion.execute(text(
                "INSERT INTO socios_negocio (id_socio, codigo_socio, nit_cedula, razon_social, es_cliente, "
                "es_proveedor, condiciones_pago_dias, estado_activo, creado_en, actualizado_en) "
                "VALUES (gen_random_uuid(), 'CLI-S22', 'S22-NO-NIT', 'No NIT', true, false, 30, true, now(), now())"
            ))


@pytest.mark.parametrize("nit", ["800.123.456-1", "900123456 - 7", " 1 020 304 050 ", "12345", "NIT-AB12", "900-123-456", "1234"])
def test_la_regla_sql_de_la_migracion_coincide_con_la_del_backend(ctx, nit):
    _, sesion = ctx
    contenido = MIGRACION_24.read_text(encoding="utf-8-sig")
    assert f"'{regla._FORMATO_NIT.pattern}'" in contenido
    assert f"'{regla._DIGITO_VERIFICACION.pattern}'" in contenido

    codigo_sql = sesion.execute(text(
        "SELECT CASE WHEN btrim(:nit) ~ :formato "
        "THEN regexp_replace(regexp_replace(btrim(:nit), :dv, ''), '[^0-9]', '', 'g') END"
    ), {"nit": nit, "formato": regla._FORMATO_NIT.pattern, "dv": regla._DIGITO_VERIFICACION.pattern}).scalar_one()
    if codigo_sql is not None and not regla.MIN_DIGITOS <= len(codigo_sql) <= regla.MAX_DIGITOS:
        codigo_sql = None

    assert codigo_sql == regla.codigo_socio_o_none(nit)


def test_alta_desde_datos_maestros_y_busqueda_por_nit(ctx):
    client, sesion = ctx
    codigo = nit_libre(sesion)
    nit = f"{codigo[:3]}.{codigo[3:6]}.{codigo[6:]}-4"

    creado = client.post(
        "/api/v1/maestros/socios",
        json={"nit_cedula": nit, "razon_social": "Cliente SCRUM-22 pg", "es_cliente": True, "cuenta_contable_por_cobrar": "130505"},
        headers=token(),
    )

    assert creado.status_code == 201, creado.text
    assert creado.json()["codigo_socio"] == codigo
    encontrados = client.get("/api/v1/maestros/socios", params={"nit": f"{codigo}-4"}, headers=token("VENTAS"))
    assert encontrados.status_code == 200, encontrados.text
    assert [s["codigo_socio"] for s in encontrados.json()] == [codigo]


def test_no_se_crea_cliente_sin_nit(ctx):
    client, sesion = ctx
    antes = sesion.query(SocioNegocio).count()

    desde_maestros = client.post(
        "/api/v1/maestros/socios",
        json={"nit_cedula": "SIN-NIT", "razon_social": "Sin NIT", "es_cliente": True, "cuenta_contable_por_cobrar": "130505"},
        headers=token(),
    )
    desde_cotizacion = client.post(
        "/api/v1/ventas/cotizaciones/",
        json={
            "razon_social": "Sin NIT", "numero_cotizacion": f"COT-S22-{nit_libre(sesion)}",
            "posiciones": [{"descripcion": "Eje", "cantidad": 1, "precio_unitario": 1000}],
        },
        headers=token("VENTAS"),
    )

    assert desde_maestros.status_code == 422
    assert desde_cotizacion.status_code == 400
    assert sesion.query(SocioNegocio).count() == antes
