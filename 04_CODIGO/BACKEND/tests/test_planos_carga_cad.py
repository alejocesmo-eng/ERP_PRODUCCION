import hashlib
import io
import uuid

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import planos as planos_api
from app.api.v1.planos import descargar_cad_plano, subir_archivo_cad_por_tipo
from app.db.database import Base
from app.db.models import BOMListaMateriales, Plano, PlanoArchivo, Proyecto

USUARIO = {"email": "dibujante1@prueba.test", "rol": "DISENO"}
CONTENIDO = b"contenido-cad"
SHA_CONTENIDO = hashlib.sha256(CONTENIDO).hexdigest()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Proyecto.__table__,
        Plano.__table__,
        BOMListaMateriales.__table__,
        PlanoArchivo.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tables)
        engine.dispose()


@pytest.fixture(autouse=True)
def directorio_planos(tmp_path, monkeypatch):
    monkeypatch.setattr(planos_api, "DIRECTORIO_STATIC_PLANOS", str(tmp_path))
    return tmp_path


def crear_plano(db, estado_diseno="EN_DISENO"):
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(),
        numero_pedido="PED-TEST-CAD",
        codigo_proyecto="PRY-TEST-CAD",
        cliente_nombre="Cliente de prueba",
        detalle_producto="Eje de prueba",
        requisitos_cliente="Plano de prueba",
        confirmado=True,
    )
    plano = Plano(
        id_plano=uuid.uuid4(),
        id_proyecto=proyecto.id_proyecto,
        codigo_op="4009010",
        codigo_plano="PLN/TEST CAD",
        version="v0.1",
        estado_diseno=estado_diseno,
    )
    db.add_all([proyecto, plano])
    db.commit()
    return plano


def archivo(nombre):
    return UploadFile(filename=nombre, file=io.BytesIO(CONTENIDO))


@pytest.mark.parametrize(
    ("tipo", "nombre", "campo", "extension"),
    [
        ("pdf", "plano.PDF", "archivo_pdf_url", ".pdf"),
        ("step", "modelo.stp", "archivo_step_url", ".step"),
        ("step", "modelo.step", "archivo_step_url", ".step"),
        ("dxf", "corte.dxf", "archivo_dxf_url", ".dxf"),
    ],
)
def test_carga_cad_guarda_archivo_y_actualiza_columna(db, directorio_planos, tipo, nombre, campo, extension):
    plano = crear_plano(db)

    resultado = subir_archivo_cad_por_tipo(plano.id_plano, tipo, archivo(nombre), db, USUARIO)

    nombre_esperado = f"PLN_TEST_CAD_v0.1_{SHA_CONTENIDO[:12]}{extension}"
    assert getattr(resultado, campo) == f"/static/planos/{nombre_esperado}"
    assert (directorio_planos / nombre_esperado).read_bytes() == CONTENIDO
    registro = db.query(PlanoArchivo).filter_by(id_plano=plano.id_plano).one()
    assert (registro.tipo, registro.sha256, registro.tamano_bytes, registro.vigente) == (
        tipo.upper(), SHA_CONTENIDO, len(CONTENIDO), True
    )


@pytest.mark.parametrize(
    ("tipo", "nombre"),
    [
        ("pdf", "modelo.step"),
        ("step", "plano.pdf"),
        ("dxf", "modelo.stp"),
        ("iges", "modelo.iges"),
    ],
)
def test_carga_cad_rechaza_extension_o_tipo_invalido(db, tipo, nombre):
    plano = crear_plano(db)

    with pytest.raises(HTTPException) as error:
        subir_archivo_cad_por_tipo(plano.id_plano, tipo, archivo(nombre), db, USUARIO)

    assert error.value.status_code == 400


@pytest.mark.parametrize("tipo,nombre", [("pdf", "plano.pdf"), ("step", "modelo.step"), ("dxf", "corte.dxf")])
def test_carga_cad_bloqueada_en_op_liberada(db, directorio_planos, tipo, nombre):
    plano = crear_plano(db, estado_diseno="LIBERADA")

    with pytest.raises(HTTPException) as error:
        subir_archivo_cad_por_tipo(plano.id_plano, tipo, archivo(nombre), db, USUARIO)

    assert error.value.status_code == 409
    assert list(directorio_planos.iterdir()) == []


def registrar_archivo(db, directorio, plano, tipo, nombre_disco, contenido, vigente=True, nombre_original=None):
    """Registro en planos_archivos con su archivo en disco (sin pasar por la carga)."""
    if nombre_disco:
        (directorio / nombre_disco).write_bytes(contenido)
    db.add(PlanoArchivo(
        id_plano=plano.id_plano,
        tipo=tipo,
        ruta=f"/static/planos/{nombre_disco or 'no_existe.bin'}",
        nombre_original=nombre_original or nombre_disco or "no_existe.bin",
        tamano_bytes=len(contenido),
        sha256=hashlib.sha256(contenido).hexdigest(),
        vigente=vigente,
    ))
    db.commit()


@pytest.mark.parametrize("tipo", ["step", "dxf", "STEP"])
def test_descarga_cad_sirve_el_archivo_vigente_y_no_el_historico(db, directorio_planos, tipo):
    plano = crear_plano(db)
    extension = tipo.lower()
    registrar_archivo(db, directorio_planos, plano, extension.upper(), f"historico.{extension}", b"viejo", vigente=False)
    registrar_archivo(
        db, directorio_planos, plano, extension.upper(), f"vigente.{extension}", b"nuevo",
        nombre_original=f"pieza_cliente.{extension}",
    )

    respuesta = descargar_cad_plano(plano.id_plano, tipo, db)

    assert respuesta.path == str(directorio_planos / f"vigente.{extension}")
    assert f"pieza_cliente.{extension}" in respuesta.headers["content-disposition"]


def test_descarga_cad_no_usa_la_columna_antigua_como_respaldo(db, directorio_planos):
    plano = crear_plano(db)
    (directorio_planos / "solo_columna.step").write_bytes(b"step antiguo")
    plano.archivo_step_url = "/static/planos/solo_columna.step"
    db.commit()

    with pytest.raises(HTTPException) as error:
        descargar_cad_plano(plano.id_plano, "step", db)

    assert error.value.status_code == 404
    assert "vigente" in error.value.detail


def test_descarga_cad_sin_vigente_da_404_aunque_haya_historico(db, directorio_planos):
    plano = crear_plano(db)
    registrar_archivo(db, directorio_planos, plano, "DXF", "historico.dxf", b"viejo", vigente=False)

    with pytest.raises(HTTPException) as error:
        descargar_cad_plano(plano.id_plano, "dxf", db)

    assert error.value.status_code == 404


def test_descarga_cad_vigente_sin_archivo_en_disco_da_404(db, directorio_planos):
    plano = crear_plano(db)
    registrar_archivo(db, directorio_planos, plano, "STEP", None, b"registrado")

    with pytest.raises(HTTPException) as error:
        descargar_cad_plano(plano.id_plano, "step", db)

    assert error.value.status_code == 404
    assert error.value.detail == "Archivo físico no encontrado."


@pytest.mark.parametrize("tipo", ["pdf", "iges", ""])
def test_descarga_cad_rechaza_tipo_invalido(db, tipo):
    plano = crear_plano(db)

    with pytest.raises(HTTPException) as error:
        descargar_cad_plano(plano.id_plano, tipo, db)

    assert error.value.status_code == 400


def test_descarga_cad_plano_inexistente_da_404(db):
    with pytest.raises(HTTPException) as error:
        descargar_cad_plano(uuid.uuid4(), "step", db)

    assert error.value.status_code == 404
    assert error.value.detail == "Plano no encontrado."
