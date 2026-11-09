# tests/test_planos_historial_modelo.py
"""
Migración 21: restricciones del modelo PlanoHistorial (SQLite en memoria).
El trigger append-only es de PostgreSQL y se prueba en test_planos_historial_pg.py.
"""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Plano, PlanoHistorial, Proyecto


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tables = [Proyecto.__table__, Plano.__table__, PlanoHistorial.__table__]
    Base.metadata.create_all(engine, tables=tables)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tables)
        engine.dispose()


@pytest.fixture
def plano(db):
    plano = Plano(id_plano=uuid.uuid4(), codigo_plano="PLN-HIST-01", version="V-01", estado_diseno="EN_DISENO")
    db.add(plano)
    db.commit()
    return plano


def evento(plano, tipo_evento, justificacion=None, **extra):
    return PlanoHistorial(
        id_plano=plano.id_plano,
        tipo_evento=tipo_evento,
        version=plano.version,
        estado=plano.estado_diseno,
        usuario="dibujante1@prueba.test",
        justificacion=justificacion,
        **extra,
    )


@pytest.mark.parametrize("tipo_evento", ["CAMBIO_VERSION", "CAMBIO_ARCHIVO", "REVISION"])
@pytest.mark.parametrize("justificacion", [None, "", "corta", "          ", "  nueve   "])
def test_eventos_que_exigen_justificacion_rechazan_menos_de_10_caracteres(db, plano, tipo_evento, justificacion):
    db.add(evento(plano, tipo_evento, justificacion))

    with pytest.raises(IntegrityError):
        db.commit()


@pytest.mark.parametrize("tipo_evento", ["CAMBIO_VERSION", "CAMBIO_ARCHIVO", "REVISION"])
def test_eventos_que_exigen_justificacion_aceptan_10_caracteres(db, plano, tipo_evento):
    # 10 caracteres tras quitar los espacios de los extremos
    db.add(evento(plano, tipo_evento, "  diez letra  "))
    db.commit()

    assert db.query(PlanoHistorial).count() == 1


@pytest.mark.parametrize("tipo_evento", ["CREACION", "CARGA_ARCHIVO", "CAMBIO_ESTADO", "APROBACION"])
def test_eventos_sin_justificacion_obligatoria(db, plano, tipo_evento):
    db.add(evento(plano, tipo_evento))
    db.commit()

    guardado = db.query(PlanoHistorial).one()
    assert guardado.tipo_evento == tipo_evento
    assert guardado.fecha is not None


def test_rechaza_tipo_de_evento_desconocido(db, plano):
    db.add(evento(plano, "BORRADO"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_rechaza_tipo_de_archivo_desconocido(db, plano):
    db.add(evento(plano, "CARGA_ARCHIVO", tipo_archivo="IGES"))

    with pytest.raises(IntegrityError):
        db.commit()
