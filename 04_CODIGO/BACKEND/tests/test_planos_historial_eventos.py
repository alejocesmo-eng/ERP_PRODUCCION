# tests/test_planos_historial_eventos.py
"""
Historial de planos (migración 21): cada ruta de planos registra su evento y la
justificación es obligatoria (422) en cambio de versión, cambio de archivo y revisión.

SQLite en memoria con override de get_db, tokens ficticios y una aplicación FastAPI
mínima con el router de planos (no se importa app.main) para no tocar ninguna base real.
"""
import hashlib
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import planos as planos_api
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import EstadoPlanoEnum, Plano, PlanoArchivo, PlanoHistorial, Proyecto
from app.services.historial_planos import MENSAJE_JUSTIFICACION

JUSTIFICACION = "  Corrección de cotas pedida por el cliente  "


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(planos_api, "DIRECTORIO_STATIC_PLANOS", str(tmp_path))
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # expire_on_commit=False: las pruebas leen los ids de los objetos tras cerrar la sesión
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = FastAPI()
    app.include_router(planos_api.router, prefix="/api/v1/planos")

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)
    yield client, Sesion, tmp_path
    client.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol="DISENO"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_plano(Sesion, **extra):
    s = Sesion()
    datos = {"id_plano": uuid.uuid4(), "codigo_plano": "PLN-HE-01", "version": "V-01", "estado_diseno": "PLANIFICADA"}
    datos.update(extra)
    plano = Plano(**datos)
    s.add(plano)
    s.commit()
    s.close()
    return plano


def leer_plano(Sesion, id_plano):
    s = Sesion()
    try:
        return s.get(Plano, id_plano)
    finally:
        s.close()


def eventos(Sesion, id_plano):
    s = Sesion()
    try:
        return s.query(PlanoHistorial).filter(PlanoHistorial.id_plano == id_plano).order_by(PlanoHistorial.fecha).all()
    finally:
        s.close()


def subir(client, plano, contenido, nombre="plano.pdf", tipo="pdf", justificacion=None):
    return client.post(
        f"/api/v1/planos/upload-cad/{plano.id_plano}/{tipo}",
        files={"archivo": (nombre, contenido, "application/octet-stream")},
        data={"justificacion": justificacion} if justificacion is not None else None,
        headers=token(),
    )


def test_crear_planos_exige_token_y_registra_creacion(ctx):
    client, Sesion, _ = ctx
    s = Sesion()
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(), numero_pedido="PED-HE-1", codigo_proyecto="PRY-HE-1",
        cliente_nombre="Cliente Ficticio SAS", requisitos_cliente="Según plano",
    )
    s.add(proyecto)
    s.commit()
    s.close()
    cuerpo = {"id_proyecto": str(proyecto.id_proyecto), "codigo_op": "OP-HE-1", "codigo_plano": "PLN-HE-NUEVO",
              "piezas": [{"codigo_plano": "PLN-HE-NUEVO", "version": "V-03"}]}

    assert client.post("/api/v1/planos/", json=cuerpo).status_code == 401

    respuesta = client.post("/api/v1/planos/", json=cuerpo, headers=token())
    assert respuesta.status_code == 201, respuesta.text
    [evento] = eventos(Sesion, uuid.UUID(respuesta.json()[0]["id_plano"]))
    assert (evento.tipo_evento, evento.version, evento.estado, evento.usuario) == (
        "CREACION", "V-03", "PLANIFICADA", "diseno@prueba.test"
    )
    assert evento.justificacion is None


def test_primera_carga_registra_carga_archivo_sin_justificacion(ctx):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)

    respuesta = subir(client, plano, b"%PDF primera")

    assert respuesta.status_code == 200, respuesta.text
    [evento] = eventos(Sesion, plano.id_plano)
    assert (evento.tipo_evento, evento.tipo_archivo, evento.sha256, evento.justificacion) == (
        "CARGA_ARCHIVO", "PDF", hashlib.sha256(b"%PDF primera").hexdigest(), None
    )


def test_subir_el_mismo_contenido_no_crea_evento(ctx):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)
    assert subir(client, plano, b"%PDF igual").status_code == 200

    assert subir(client, plano, b"%PDF igual").status_code == 200

    assert [e.tipo_evento for e in eventos(Sesion, plano.id_plano)] == ["CARGA_ARCHIVO"]


@pytest.mark.parametrize("justificacion", [None, "", "corta", "               "])
def test_reemplazo_sin_justificacion_valida_da_422_sin_tocar_disco_ni_historial(ctx, justificacion):
    client, Sesion, directorio = ctx
    plano = crear_plano(Sesion)
    assert subir(client, plano, b"%PDF primera").status_code == 200
    archivos_antes = sorted(p.name for p in directorio.iterdir())

    respuesta = subir(client, plano, b"%PDF segunda", justificacion=justificacion)

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == MENSAJE_JUSTIFICACION
    assert sorted(p.name for p in directorio.iterdir()) == archivos_antes
    assert [e.tipo_evento for e in eventos(Sesion, plano.id_plano)] == ["CARGA_ARCHIVO"]
    s = Sesion()
    [vigente] = s.query(PlanoArchivo).filter(PlanoArchivo.id_plano == plano.id_plano, PlanoArchivo.vigente.is_(True)).all()
    assert vigente.sha256 == hashlib.sha256(b"%PDF primera").hexdigest()
    s.close()


@pytest.mark.parametrize(("tipo", "nombre"), [("pdf", "plano.pdf"), ("step", "modelo.step"), ("dxf", "corte.dxf")])
def test_reemplazo_con_justificacion_registra_cambio_archivo(ctx, tipo, nombre):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)
    assert subir(client, plano, b"contenido uno", nombre=nombre, tipo=tipo).status_code == 200

    respuesta = subir(client, plano, b"contenido dos", nombre=nombre, tipo=tipo, justificacion=JUSTIFICACION)

    assert respuesta.status_code == 200, respuesta.text
    carga, cambio = eventos(Sesion, plano.id_plano)
    assert carga.tipo_evento == "CARGA_ARCHIVO"
    assert (cambio.tipo_evento, cambio.tipo_archivo, cambio.sha256, cambio.justificacion) == (
        "CAMBIO_ARCHIVO", tipo.upper(), hashlib.sha256(b"contenido dos").hexdigest(), JUSTIFICACION.strip()
    )


@pytest.mark.parametrize("justificacion", [None, "corta"])
def test_cambio_de_version_sin_justificacion_da_422_y_no_cambia_el_plano(ctx, justificacion):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)
    cuerpo = {"version": "V-02"}
    if justificacion is not None:
        cuerpo["justificacion"] = justificacion

    respuesta = client.patch(f"/api/v1/planos/{plano.id_plano}", json=cuerpo, headers=token())

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == MENSAJE_JUSTIFICACION
    guardado = leer_plano(Sesion, plano.id_plano)
    assert guardado.version == "V-01"
    assert guardado.fecha_ultima_revision is None
    assert eventos(Sesion, plano.id_plano) == []


def test_cambio_de_version_con_justificacion_registra_evento_y_fecha_de_revision(ctx):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)

    respuesta = client.patch(
        f"/api/v1/planos/{plano.id_plano}", json={"version": "V-02", "justificacion": JUSTIFICACION}, headers=token()
    )

    assert respuesta.status_code == 200, respuesta.text
    [evento] = eventos(Sesion, plano.id_plano)
    assert (evento.tipo_evento, evento.version_anterior, evento.version, evento.justificacion) == (
        "CAMBIO_VERSION", "V-01", "V-02", JUSTIFICACION.strip()
    )
    assert leer_plano(Sesion, plano.id_plano).fecha_ultima_revision is not None


def test_reenviar_el_plano_sin_cambios_no_exige_justificacion_ni_crea_eventos(ctx):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)
    assert subir(client, plano, b"%PDF vigente").status_code == 200
    actual = leer_plano(Sesion, plano.id_plano)

    respuesta = client.patch(
        f"/api/v1/planos/{plano.id_plano}",
        json={
            "version": "V-01",
            "estado_diseno": "PLANIFICADA",
            "archivo_pdf_url": actual.archivo_pdf_url,
            "archivo_step_url": None,
            "observaciones_tecnicas": "Sin cambios técnicos",
        },
        headers=token(),
    )

    assert respuesta.status_code == 200, respuesta.text
    assert [e.tipo_evento for e in eventos(Sesion, plano.id_plano)] == ["CARGA_ARCHIVO"]


@pytest.mark.parametrize("campo", ["archivo_pdf_url", "archivo_step_url", "archivo_dxf_url"])
def test_patch_con_archivo_distinto_da_422_y_no_cambia_el_plano(ctx, campo):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)

    respuesta = client.patch(
        f"/api/v1/planos/{plano.id_plano}", json={campo: "/static/planos/otro.bin"}, headers=token()
    )

    assert respuesta.status_code == 422
    assert campo in respuesta.json()["detail"]
    assert getattr(leer_plano(Sesion, plano.id_plano), campo) is None
    assert eventos(Sesion, plano.id_plano) == []


def test_cambio_de_estado_registra_el_evento_y_el_de_la_orden_pausada(ctx):
    client, Sesion, _ = ctx
    activa = crear_plano(Sesion, codigo_plano="PLN-HE-ACTIVA", estado_diseno="EN_DISENO", dibujante_asignado="Ing. Carlos Ruiz")
    siguiente = crear_plano(Sesion, codigo_plano="PLN-HE-SIGUIENTE", dibujante_asignado="Carlos Ruiz")

    respuesta = client.patch(f"/api/v1/planos/{siguiente.id_plano}", json={"estado_diseno": "EN_DISENO"}, headers=token())

    assert respuesta.status_code == 200, respuesta.text
    [evento_siguiente] = eventos(Sesion, siguiente.id_plano)
    [evento_activa] = eventos(Sesion, activa.id_plano)
    assert (evento_siguiente.tipo_evento, evento_siguiente.estado) == ("CAMBIO_ESTADO", "EN_DISENO")
    assert (evento_activa.tipo_evento, evento_activa.estado) == ("CAMBIO_ESTADO", "PAUSADA")


@pytest.mark.parametrize(("cuerpo", "esperada"), [(None, None), ({"justificacion": "  Revisado con el cliente  "}, "Revisado con el cliente"), ({"justificacion": "ok"}, "ok")])
def test_aprobacion_con_justificacion_opcional(ctx, cuerpo, esperada):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)

    respuesta = client.post(f"/api/v1/planos/{plano.id_plano}/aprobar", json=cuerpo, headers=token())

    assert respuesta.status_code == 200, respuesta.text
    [evento] = eventos(Sesion, plano.id_plano)
    assert (evento.tipo_evento, evento.justificacion, evento.usuario) == ("APROBACION", esperada, "diseno@prueba.test")


@pytest.mark.parametrize("cuerpo", [None, {}, {"justificacion": "corta"}, {"justificacion": "          "}])
def test_revision_sin_justificacion_valida_da_422(ctx, cuerpo):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)

    respuesta = client.post(f"/api/v1/planos/{plano.id_plano}/revision", json=cuerpo, headers=token())

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == MENSAJE_JUSTIFICACION
    assert leer_plano(Sesion, plano.id_plano).fecha_ultima_revision is None
    assert eventos(Sesion, plano.id_plano) == []


def test_revision_de_un_plano_aprobado_lo_marca_para_revisar(ctx):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)
    assert client.post(f"/api/v1/planos/{plano.id_plano}/aprobar", headers=token()).json()["revisar"] is False

    respuesta = client.post(
        f"/api/v1/planos/{plano.id_plano}/revision", json={"justificacion": JUSTIFICACION}, headers=token()
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["revisar"] is True
    assert respuesta.json()["estado"] == EstadoPlanoEnum.APROBADO.value
    assert [(e.tipo_evento, e.justificacion) for e in eventos(Sesion, plano.id_plano)] == [
        ("APROBACION", None), ("REVISION", JUSTIFICACION.strip())
    ]


@pytest.mark.parametrize("rol", ["PRODUCCION", "ADMIN"])
def test_revision_es_solo_de_diseno(ctx, rol):
    client, Sesion, _ = ctx
    plano = crear_plano(Sesion)

    respuesta = client.post(
        f"/api/v1/planos/{plano.id_plano}/revision", json={"justificacion": JUSTIFICACION}, headers=token(rol)
    )

    assert respuesta.status_code == 403
    assert eventos(Sesion, plano.id_plano) == []
