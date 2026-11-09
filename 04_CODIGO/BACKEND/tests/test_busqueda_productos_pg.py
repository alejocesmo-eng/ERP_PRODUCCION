# tests/test_busqueda_productos_pg.py
"""
GET /maestros/productos con pg_trgm y unaccent (migración 22): búsqueda sin distinguir
mayúsculas ni acentos, tolerante a errores de tipeo y ordenada por similitud.

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*) con la migración 22
aplicada, dentro de una transacción que se revierte al terminar. Los productos usan la
palabra inventada "Xilofrán" y códigos RN-977-*; las aserciones se limitan a esos productos
para no depender del catálogo que ya tenga la base.
"""
import os
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v1 import maestros
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import Producto

URL_PG = os.environ.get("SGI_TEST_PG_URL")

pytestmark = pytest.mark.pg

RUTA = "/api/v1/maestros/productos"


@pytest.fixture
def ctx():
    assert (make_url(URL_PG).database or "").startswith("sgi_test_"), "Solo se prueba sobre copias sgi_test_*."
    engine = create_engine(URL_PG)
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")

    app = FastAPI()
    app.include_router(maestros.router, prefix="/api/v1/maestros")
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


def crear_producto(sesion, descripcion, codigo_anterior=None, estado="ACTIVO"):
    producto = Producto(
        id_producto=uuid.uuid4(),
        codigo_rn=f"RN-977-{uuid.uuid4().int % 1000:03d}-{uuid.uuid4().int % 1000000:06d}",
        codigo_anterior=codigo_anterior,
        descripcion=descripcion,
        estado=estado,
    )
    sesion.add(producto)
    sesion.flush()
    return producto


def buscar(client, q, **params):
    respuesta = client.get(RUTA, params={"q": q, **params}, headers=token())
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def propios(resultado, *productos):
    """Filas del resultado que son productos de la prueba, en el orden devuelto."""
    ids = {str(producto.id_producto) for producto in productos}
    return [fila for fila in resultado if fila["id_producto"] in ids]


@pytest.mark.parametrize("q", ["EJE TRANSMISION XILOFRAN", "eje transmisión xilofrán", "  Eje   de TRANSMISIÓN  xilofrán "])
def test_descripcion_sin_distinguir_mayusculas_acentos_ni_espacios(ctx, q):
    client, sesion = ctx
    eje = crear_producto(sesion, "Eje de transmisión Xilofrán")

    [fila] = propios(buscar(client, q), eje)

    assert fila["coincide_en"] == "descripcion"
    assert fila["similitud"] >= maestros.UMBRAL_SIMILITUD_PRODUCTOS


def test_codigo_rn_sin_guiones_ni_mayusculas_es_coincidencia_exacta(ctx):
    client, sesion = ctx
    eje = crear_producto(sesion, "Eje Xilofrán")
    q = eje.codigo_rn.replace("-", "").lower()

    resultado = buscar(client, q)

    assert resultado[0]["id_producto"] == str(eje.id_producto)
    assert (resultado[0]["similitud"], resultado[0]["coincide_en"]) == (1.0, "codigo_rn")


def test_prefijo_del_codigo_rn_puntua_0_9(ctx):
    client, sesion = ctx
    eje = crear_producto(sesion, "Eje Xilofrán")

    [fila] = propios(buscar(client, eje.codigo_rn[:10]), eje)

    assert (fila["similitud"], fila["coincide_en"]) == (0.9, "codigo_rn")


def test_codigo_anterior_con_otro_formato(ctx):
    client, sesion = ctx
    eje = crear_producto(sesion, "Eje Xilofrán", codigo_anterior="SKU-XLF-7731")

    [fila] = propios(buscar(client, "sku xlf 7731"), eje)

    assert (fila["similitud"], fila["coincide_en"]) == (1.0, "codigo_anterior")


@pytest.mark.parametrize("q", ["xilofram", "xilfran", "transmicion xilofran"])
def test_tolera_errores_de_tipeo(ctx, q):
    client, sesion = ctx
    eje = crear_producto(sesion, "Eje de transmisión Xilofrán")

    [fila] = propios(buscar(client, q), eje)

    assert fila["similitud"] >= maestros.UMBRAL_SIMILITUD_PRODUCTOS


def test_ordena_por_similitud_y_en_empate_por_codigo_rn(ctx):
    client, sesion = ctx
    eje = crear_producto(sesion, "Eje de transmisión Xilofrán")
    polea = crear_producto(sesion, "Polea de transmisión Xilofrán larga")
    buje = crear_producto(sesion, "Buje Xilofrán cónico")

    resultado = buscar(client, "transmision xilofran", limit=50)

    similitudes = [fila["similitud"] for fila in resultado]
    assert similitudes == sorted(similitudes, reverse=True)
    filas = propios(resultado, eje, polea, buje)
    assert filas[-1]["id_producto"] == str(buje.id_producto)
    assert filas[-1]["similitud"] < filas[0]["similitud"]
    empatados = [fila for fila in filas if fila["similitud"] == filas[0]["similitud"]]
    assert [fila["codigo_rn"] for fila in empatados] == sorted(fila["codigo_rn"] for fila in empatados)


def test_obsoletos_solo_si_se_piden(ctx):
    client, sesion = ctx
    obsoleto = crear_producto(sesion, "Xilofrán descontinuado", estado="OBSOLETO")

    assert propios(buscar(client, "xilofran descontinuado"), obsoleto) == []
    [fila] = propios(buscar(client, "xilofran descontinuado", incluir_obsoletos=True), obsoleto)
    assert fila["estado"] == "OBSOLETO"


def test_respeta_el_limite(ctx):
    client, sesion = ctx
    for indice in range(4):
        crear_producto(sesion, f"Xilofrán variante {indice}")

    assert len(buscar(client, "xilofran", limit=2)) == 2


def test_no_devuelve_productos_por_debajo_del_umbral_que_no_contienen_el_texto(ctx):
    client, sesion = ctx
    eje = crear_producto(sesion, "Eje de transmisión Xilofrán")
    ajeno = crear_producto(sesion, "Rodamiento Quentaril sellado")

    resultado = buscar(client, "xilofran", limit=50)

    assert propios(resultado, eje)
    assert propios(resultado, ajeno) == []
