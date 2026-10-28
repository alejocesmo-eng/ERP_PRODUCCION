import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.mantenimiento_planta import (
    OrdenMantenimientoCreate,
    solicitar_repuestos_orden_mantenimiento,
)
from app.db.database import Base
from app.db.models import EquipoPlanta, OrdenMantenimiento, SolicitudCompra


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tablas = [
        EquipoPlanta.__table__,
        OrdenMantenimiento.__table__,
        SolicitudCompra.__table__,
    ]
    Base.metadata.create_all(engine, tables=tablas)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tablas)
        engine.dispose()


def test_overhaul_es_un_tipo_valido_de_orden_de_mantenimiento():
    orden = OrdenMantenimientoCreate(
        id_equipo=uuid.uuid4(),
        tipo="OVERHAUL",
        descripcion_falla="Reacondicionamiento general del equipo.",
    )

    assert orden.tipo == "OVERHAUL"


def test_solicitud_de_repuestos_crea_requisicion_idempotente(db):
    equipo = EquipoPlanta(
        codigo_maquina="TORN-CNC-01",
        nombre="Torno CNC",
        centro_trabajo_asociado="CC-100-MECANIZADO",
        estado_maquina="OPERATIVA",
    )
    db.add(equipo)
    db.flush()
    orden = OrdenMantenimiento(
        codigo_otm="OTM-TEST-001",
        id_equipo=equipo.id_equipo,
        tipo="PREVENTIVO",
        descripcion_falla="Cambio programado de rodamiento.",
        repuestos_solicitados_almacen=[
            {
                "nombre_item": "Rodamiento de husillo",
                "cantidad": 1,
                "unidad_medida": "UND",
            }
        ],
    )
    db.add(orden)
    db.commit()

    primera_respuesta = solicitar_repuestos_orden_mantenimiento(orden.id_otm, db=db)
    segunda_respuesta = solicitar_repuestos_orden_mantenimiento(orden.id_otm, db=db)

    assert primera_respuesta["requisiciones"][0]["id_solicitud"]
    assert segunda_respuesta["requisiciones"][0]["id_solicitud"] == primera_respuesta["requisiciones"][0]["id_solicitud"]
    assert db.query(SolicitudCompra).count() == 1
