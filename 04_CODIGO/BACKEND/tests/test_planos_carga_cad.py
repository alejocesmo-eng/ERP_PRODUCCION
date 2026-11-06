import io
import uuid

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import planos as planos_api
from app.api.v1.planos import subir_archivo_cad_por_tipo
from app.db.database import Base
from app.db.models import BOMListaMateriales, Plano, Proyecto


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Proyecto.__table__,
        Plano.__table__,
        BOMListaMateriales.__table__,
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
    return UploadFile(filename=nombre, file=io.BytesIO(b"contenido-cad"))


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

    resultado = subir_archivo_cad_por_tipo(plano.id_plano, tipo, archivo(nombre), db)

    nombre_esperado = f"4009010_PLN_TEST_CAD_v0.1{extension}"
    assert getattr(resultado, campo) == f"/static/planos/{nombre_esperado}"
    assert (directorio_planos / nombre_esperado).read_bytes() == b"contenido-cad"


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
        subir_archivo_cad_por_tipo(plano.id_plano, tipo, archivo(nombre), db)

    assert error.value.status_code == 400


@pytest.mark.parametrize("tipo,nombre", [("pdf", "plano.pdf"), ("step", "modelo.step"), ("dxf", "corte.dxf")])
def test_carga_cad_bloqueada_en_op_liberada(db, directorio_planos, tipo, nombre):
    plano = crear_plano(db, estado_diseno="LIBERADA")

    with pytest.raises(HTTPException) as error:
        subir_archivo_cad_por_tipo(plano.id_plano, tipo, archivo(nombre), db)

    assert error.value.status_code == 409
    assert list(directorio_planos.iterdir()) == []
