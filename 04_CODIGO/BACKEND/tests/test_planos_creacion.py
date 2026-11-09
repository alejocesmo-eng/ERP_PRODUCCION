# tests/test_planos_creacion.py
"""
POST /planos/: creación de planos con y sin piezas.

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
from app.db.models import BOMListaMateriales, Plano, PlanoArchivo, PlanoHistorial, Proyecto


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


def crear_proyecto(Sesion):
    s = Sesion()
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(), numero_pedido="PED-CR-1", codigo_proyecto="PRY-CR-1",
        cliente_nombre="Cliente Ficticio SAS", requisitos_cliente="Según plano",
    )
    s.add(proyecto)
    s.commit()
    s.close()
    return proyecto


def crear(client, proyecto, **cuerpo):
    datos = {"id_proyecto": str(proyecto.id_proyecto), "codigo_op": "OP-CR-1"}
    datos.update(cuerpo)
    return client.post("/api/v1/planos/", json=datos, headers=token())


def leer_planos(Sesion):
    s = Sesion()
    try:
        return s.query(Plano).order_by(Plano.codigo_plano).all()
    finally:
        s.close()


def test_sin_piezas_crea_un_plano_con_los_datos_de_la_cabecera(ctx):
    client, Sesion, _ = ctx
    proyecto = crear_proyecto(Sesion)

    respuesta = crear(
        client, proyecto,
        codigo_plano="PLN-CR-CABECERA", version="V-04", material_requerido="AISI 4140", piezas=[],
    )

    assert respuesta.status_code == 201, respuesta.text
    [plano] = respuesta.json()
    assert (plano["codigo_plano"], plano["version"], plano["material_requerido"]) == ("PLN-CR-CABECERA", "V-04", "AISI 4140")
    s = Sesion()
    [linea] = s.query(BOMListaMateriales).all()
    assert linea.codigo_material == "AISI 4140"
    [evento] = s.query(PlanoHistorial).all()
    assert (evento.tipo_evento, evento.version) == ("CREACION", "V-04")
    s.close()


def test_sin_piezas_y_sin_codigo_de_plano_usa_el_codigo_de_la_op(ctx):
    client, Sesion, _ = ctx
    proyecto = crear_proyecto(Sesion)

    respuesta = crear(client, proyecto)

    assert respuesta.status_code == 201, respuesta.text
    [plano] = respuesta.json()
    assert (plano["codigo_plano"], plano["version"]) == ("OP-CR-1", "V-01")


def test_con_piezas_crea_un_plano_por_pieza(ctx):
    client, Sesion, _ = ctx
    proyecto = crear_proyecto(Sesion)

    respuesta = crear(
        client, proyecto,
        piezas=[{"codigo_plano": "PLN-CR-A", "version": "V-02"}, {"codigo_plano": "PLN-CR-B"}],
    )

    assert respuesta.status_code == 201, respuesta.text
    assert [(p.codigo_plano, p.version) for p in leer_planos(Sesion)] == [("PLN-CR-A", "V-02"), ("PLN-CR-B", "V-01")]


# --- Archivos referenciados por ruta: hash, planos_archivos e historial ---

def tablas(Sesion):
    s = Sesion()
    try:
        return s.query(Plano).count(), s.query(PlanoArchivo).all(), s.query(PlanoHistorial).order_by(PlanoHistorial.fecha).all()
    finally:
        s.close()


def test_archivos_de_las_piezas_se_registran_con_hash_y_evento(ctx):
    client, Sesion, directorio = ctx
    proyecto = crear_proyecto(Sesion)
    (directorio / "PLN-CR-A.pdf").write_bytes(b"%PDF plano A")
    (directorio / "PLN-CR-A.step").write_bytes(b"ISO-10303 modelo A")

    respuesta = crear(
        client, proyecto,
        piezas=[{
            "codigo_plano": "PLN-CR-A",
            "archivo_pdf_url": "/static/planos/PLN-CR-A.pdf",
            "archivo_step_url": "/static/planos/PLN-CR-A.step",
        }],
    )

    assert respuesta.status_code == 201, respuesta.text
    [plano] = respuesta.json()
    assert plano["archivo_pdf_url"] == "/static/planos/PLN-CR-A.pdf"
    assert plano["archivo_step_url"] == "/static/planos/PLN-CR-A.step"
    _, archivos, eventos = tablas(Sesion)
    por_tipo = {a.tipo: a for a in archivos}
    assert set(por_tipo) == {"PDF", "STEP"}
    assert por_tipo["PDF"].sha256 == hashlib.sha256(b"%PDF plano A").hexdigest()
    assert por_tipo["PDF"].tamano_bytes == len(b"%PDF plano A")
    assert all(a.vigente and a.subido_por == "diseno@prueba.test" for a in archivos)
    assert eventos[0].tipo_evento == "CREACION"
    cargas = {e.tipo_archivo: e for e in eventos[1:]}
    assert {e.tipo_evento for e in eventos[1:]} == {"CARGA_ARCHIVO"}
    assert cargas["STEP"].sha256 == hashlib.sha256(b"ISO-10303 modelo A").hexdigest()
    assert cargas["PDF"].justificacion is None


def test_archivo_de_la_cabecera_sin_piezas_se_registra(ctx):
    client, Sesion, directorio = ctx
    proyecto = crear_proyecto(Sesion)
    (directorio / "corte.dxf").write_bytes(b"0 SECTION")

    respuesta = crear(client, proyecto, codigo_plano="PLN-CR-DXF", archivo_dxf_url="/static/planos/corte.dxf")

    assert respuesta.status_code == 201, respuesta.text
    _, [archivo], eventos = tablas(Sesion)
    assert (archivo.tipo, archivo.sha256) == ("DXF", hashlib.sha256(b"0 SECTION").hexdigest())
    assert [e.tipo_evento for e in eventos] == ["CREACION", "CARGA_ARCHIVO"]


@pytest.mark.parametrize(
    "ruta",
    ["/static/planos/no_existe.pdf", "../../fuera_del_almacenamiento.pdf"],
    ids=["inexistente", "ruta_fuera_del_almacenamiento"],
)
def test_archivo_que_no_esta_en_el_almacenamiento_da_422_sin_crear_nada(ctx, ruta):
    client, Sesion, directorio = ctx
    proyecto = crear_proyecto(Sesion)
    (directorio.parent / "fuera_del_almacenamiento.pdf").write_bytes(b"%PDF fuera")

    respuesta = crear(client, proyecto, piezas=[{"codigo_plano": "PLN-CR-X", "archivo_pdf_url": ruta}])

    assert respuesta.status_code == 422
    assert "upload-cad" in respuesta.json()["detail"]
    assert tablas(Sesion) == (0, [], [])


def test_archivo_con_extension_de_otro_tipo_da_400(ctx):
    client, Sesion, directorio = ctx
    proyecto = crear_proyecto(Sesion)
    (directorio / "plano.pdf").write_bytes(b"%PDF")

    respuesta = crear(client, proyecto, piezas=[{"codigo_plano": "PLN-CR-X", "archivo_step_url": "/static/planos/plano.pdf"}])

    assert respuesta.status_code == 400
    assert tablas(Sesion) == (0, [], [])


def test_archivo_vacio_da_400(ctx):
    client, Sesion, directorio = ctx
    proyecto = crear_proyecto(Sesion)
    (directorio / "vacio.pdf").write_bytes(b"")

    respuesta = crear(client, proyecto, piezas=[{"codigo_plano": "PLN-CR-X", "archivo_pdf_url": "/static/planos/vacio.pdf"}])

    assert respuesta.status_code == 400
    assert tablas(Sesion) == (0, [], [])
