# tests/test_planos_archivos.py
"""
Fase E2: carga de archivos por plano (migración 19).

/upload-pdf y /upload-cad aceptan PDF, STEP y DXF. Cada carga queda en planos_archivos con
tipo, ruta, nombre_original, tamano_bytes, sha256, revision y subido_por. Un PDF nuevo deja
el anterior como histórico (vigente = false) y planos.archivo_pdf_url sigue al PDF vigente.

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*), dentro de una
transacción que se revierte al terminar; los archivos se escriben en un directorio temporal.
"""
import hashlib
import os
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v1 import planos as planos_api
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import Plano, PlanoArchivo

URL_PG = os.environ.get("SGI_TEST_PG_URL")

pytestmark = pytest.mark.pg

TIPOS = [("plano.PDF", "PDF", "archivo_pdf_url"), ("modelo.stp", "STEP", "archivo_step_url"), ("corte.dxf", "DXF", "archivo_dxf_url")]


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    assert (make_url(URL_PG).database or "").startswith("sgi_test_"), "Solo se prueba sobre copias sgi_test_*."
    monkeypatch.setattr(planos_api, "DIRECTORIO_STATIC_PLANOS", str(tmp_path))
    engine = create_engine(URL_PG)
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")

    app = FastAPI()
    app.include_router(planos_api.router, prefix="/api/v1/planos")
    app.dependency_overrides[get_db] = lambda: sesion
    client = TestClient(app)
    try:
        yield client, sesion, tmp_path
    finally:
        client.close()
        sesion.close()
        transaccion.rollback()
        conexion.close()
        engine.dispose()


def token(rol="DISENO"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_plano(sesion):
    plano = Plano(
        id_plano=uuid.uuid4(),
        codigo_plano=f"PLN-E2-{uuid.uuid4().hex[:8].upper()}",
        version="V-02",
    )
    sesion.add(plano)
    sesion.commit()
    return plano


def subir(client, ruta, plano, nombre, contenido, cabeceras=None, justificacion=None):
    return client.post(
        f"/api/v1/planos/{ruta}/{plano.id_plano}",
        files={"archivo": (nombre, contenido, "application/octet-stream")},
        data={"justificacion": justificacion} if justificacion else None,
        headers=token() if cabeceras is None else cabeceras,
    )


def archivos(sesion, plano, tipo=None):
    sesion.expire_all()
    consulta = sesion.query(PlanoArchivo).filter(PlanoArchivo.id_plano == plano.id_plano)
    if tipo:
        consulta = consulta.filter(PlanoArchivo.tipo == tipo)
    return consulta.order_by(PlanoArchivo.subido_en, PlanoArchivo.vigente).all()


@pytest.mark.parametrize("ruta", ["upload-pdf", "upload-cad"])
def test_carga_de_cada_tipo_registra_hash_tamano_y_sincroniza_la_columna(ctx, ruta):
    client, sesion, directorio = ctx
    plano = crear_plano(sesion)

    for nombre, tipo, campo in TIPOS:
        contenido = f"contenido {tipo} {uuid.uuid4()}".encode()
        respuesta = subir(client, ruta, plano, nombre, contenido)
        assert respuesta.status_code == 200, respuesta.text

        [registro] = archivos(sesion, plano, tipo)
        assert registro.vigente is True
        assert registro.nombre_original == nombre
        assert registro.tamano_bytes == len(contenido)
        assert registro.sha256 == hashlib.sha256(contenido).hexdigest()
        assert registro.revision == "V-02"
        assert registro.subido_por == "diseno@prueba.test"
        assert (directorio / os.path.basename(registro.ruta)).read_bytes() == contenido
        assert getattr(sesion.get(Plano, plano.id_plano), campo) == registro.ruta
        assert respuesta.json()[campo] == registro.ruta

    assert {registro.tipo for registro in archivos(sesion, plano) if registro.vigente} == {"PDF", "STEP", "DXF"}


@pytest.mark.parametrize("ruta", ["upload-pdf", "upload-cad"])
@pytest.mark.parametrize("nombre", ["pieza.iges", "informe.docx", "sin_extension"])
def test_rechaza_un_tipo_no_permitido(ctx, ruta, nombre):
    client, sesion, directorio = ctx
    plano = crear_plano(sesion)

    respuesta = subir(client, ruta, plano, nombre, b"contenido")

    assert respuesta.status_code == 400
    assert "Formato no permitido" in respuesta.json()["detail"]
    assert archivos(sesion, plano) == []
    assert list(directorio.iterdir()) == []


def test_rechaza_tipo_explicito_que_no_coincide_con_la_extension(ctx):
    client, sesion, directorio = ctx
    plano = crear_plano(sesion)

    respuesta = subir(client, "upload-cad", plano, "plano.pdf", b"contenido")
    assert respuesta.status_code == 200
    respuesta = client.post(
        f"/api/v1/planos/upload-cad/{plano.id_plano}/step",
        files={"archivo": ("plano.pdf", b"contenido", "application/pdf")},
        headers=token(),
    )
    assert respuesta.status_code == 400
    assert "Formato inválido para STEP" in respuesta.json()["detail"]


@pytest.mark.parametrize("ruta", ["upload-pdf", "upload-cad"])
def test_rechaza_un_archivo_vacio(ctx, ruta):
    client, sesion, directorio = ctx
    plano = crear_plano(sesion)

    respuesta = subir(client, ruta, plano, "plano.pdf", b"")

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == "El archivo está vacío."
    assert archivos(sesion, plano) == []
    assert list(directorio.iterdir()) == []


def test_segundo_pdf_reemplaza_al_anterior_y_deja_el_historico(ctx):
    client, sesion, directorio = ctx
    plano = crear_plano(sesion)

    assert subir(client, "upload-pdf", plano, "plano_v1.pdf", b"%PDF primera version").status_code == 200
    [primero] = archivos(sesion, plano, "PDF")
    respuesta = subir(
        client, "upload-pdf", plano, "plano_v2.pdf", b"%PDF segunda version",
        justificacion="Corrección de cotas solicitada por el cliente",
    )
    assert respuesta.status_code == 200, respuesta.text

    registros = archivos(sesion, plano, "PDF")
    assert len(registros) == 2
    historico = [r for r in registros if not r.vigente]
    [vigente] = [r for r in registros if r.vigente]
    assert [r.id_archivo for r in historico] == [primero.id_archivo]
    assert vigente.nombre_original == "plano_v2.pdf"
    assert vigente.ruta != primero.ruta
    # El archivo del histórico no se sobrescribe
    assert (directorio / os.path.basename(primero.ruta)).read_bytes() == b"%PDF primera version"
    assert (directorio / os.path.basename(vigente.ruta)).read_bytes() == b"%PDF segunda version"
    plano_db = sesion.get(Plano, plano.id_plano)
    assert plano_db.archivo_pdf_url == vigente.ruta
    assert plano_db.archivo_url == vigente.ruta
    assert respuesta.json()["archivo_pdf_url"] == vigente.ruta


def test_el_mismo_pdf_vigente_no_duplica_el_historico(ctx):
    client, sesion, _ = ctx
    plano = crear_plano(sesion)

    for _ in range(2):
        assert subir(client, "upload-pdf", plano, "plano.pdf", b"%PDF igual").status_code == 200

    [registro] = archivos(sesion, plano, "PDF")
    assert registro.vigente is True


def test_sha256_y_tamano_correctos_en_un_archivo_de_varios_bloques(ctx):
    client, sesion, directorio = ctx
    plano = crear_plano(sesion)
    contenido = os.urandom(planos_api.TAMANO_BLOQUE_CARGA * 2 + 12345)

    assert subir(client, "upload-cad", plano, "modelo.step", contenido).status_code == 200

    [registro] = archivos(sesion, plano, "STEP")
    assert registro.tamano_bytes == len(contenido)
    assert registro.sha256 == hashlib.sha256(contenido).hexdigest()
    assert registro.ruta.endswith(f"_{registro.sha256[:12]}.step")
    assert hashlib.sha256((directorio / os.path.basename(registro.ruta)).read_bytes()).hexdigest() == registro.sha256


def test_plano_de_producto_sin_proyecto_ni_codigo_op_se_lista(ctx):
    client, sesion, _ = ctx
    plano = crear_plano(sesion)

    respuesta = client.get("/api/v1/planos/")

    assert respuesta.status_code == 200, respuesta.text
    [fila] = [p for p in respuesta.json() if p["id_plano"] == str(plano.id_plano)]
    assert fila["id_proyecto"] is None
    assert fila["codigo_op"] is None


def test_la_carga_exige_token(ctx):
    client, sesion, directorio = ctx
    plano = crear_plano(sesion)

    respuesta = subir(client, "upload-pdf", plano, "plano.pdf", b"%PDF", cabeceras={})

    assert respuesta.status_code == 401
    assert archivos(sesion, plano) == []
