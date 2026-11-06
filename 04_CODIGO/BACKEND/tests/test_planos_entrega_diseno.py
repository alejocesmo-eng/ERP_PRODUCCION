import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.planos import PlanoUpdateRequest, actualizar_plano
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


def crear_plano_en_diseno(db, archivo_pdf_url=None, estado_bom=None):
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(),
        numero_pedido="PED-TEST-RN004",
        codigo_proyecto="PRY-TEST-RN004",
        cliente_nombre="Cliente de prueba",
        detalle_producto="Eje de prueba",
        requisitos_cliente="Plano de prueba",
        confirmado=True,
    )
    plano = Plano(
        id_plano=uuid.uuid4(),
        id_proyecto=proyecto.id_proyecto,
        codigo_op="4009001",
        codigo_plano="PLN-TEST-RN004",
        estado_diseno="EN_DISENO",
        archivo_pdf_url=archivo_pdf_url,
        fecha_inicio_diseno=datetime.now(timezone.utc) - timedelta(minutes=90),
    )
    db.add_all([proyecto, plano])
    if estado_bom:
        db.add(BOMListaMateriales(
            plano_id=plano.id_plano,
            codigo_material="AISI-4140",
            descripcion="Barra AISI 4140",
            cantidad_requerida=1,
            unidad_medida="UND",
            estado_abastecimiento=estado_bom,
        ))
    db.commit()
    return plano


@pytest.mark.parametrize(
    ("archivo_pdf_url", "estado_bom"),
    [
        (None, "SOLICITADO"),
        ("   ", "SOLICITADO"),
        ("/static/planos/op.pdf", "SIN_SOLICITAR"),
        ("/static/planos/op.pdf", None),
    ],
)
def test_entrega_diseno_rechaza_sin_pdf_o_bom_radicada(db, archivo_pdf_url, estado_bom):
    plano = crear_plano_en_diseno(db, archivo_pdf_url, estado_bom)

    with pytest.raises(HTTPException) as error:
        actualizar_plano(plano.id_plano, PlanoUpdateRequest(estado_diseno="LISTA_PARA_LIBERAR"), db)

    assert error.value.status_code == 400
    assert "RN-OP-004" in error.value.detail


def test_entrega_diseno_cierra_cronometro_con_pdf_y_bom_radicada(db):
    plano = crear_plano_en_diseno(db, "/static/planos/op.pdf", "SOLICITADO")

    actualizado = actualizar_plano(plano.id_plano, PlanoUpdateRequest(estado_diseno="LISTA_PARA_LIBERAR"), db)

    assert actualizado.estado_diseno == "LISTA_PARA_LIBERAR"
    assert actualizado.fecha_fin_diseno is not None
    assert actualizado.tiempo_total_diseno_minutos >= 89


def test_liberada_conserva_gate_de_stock_completo(db):
    plano = crear_plano_en_diseno(db, "/static/planos/op.pdf", "SOLICITADO")

    with pytest.raises(HTTPException) as error:
        actualizar_plano(plano.id_plano, PlanoUpdateRequest(estado_diseno="LIBERADA"), db)

    assert error.value.status_code == 400
    assert "pendientes de almacén" in error.value.detail


def crear_plano_dibujante(db, estado, dibujante="Ing. Prueba", **campos):
    sufijo = uuid.uuid4().hex[:6]
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(),
        numero_pedido=f"PED-{sufijo}",
        codigo_proyecto=f"PRY-{sufijo}",
        cliente_nombre="Cliente de prueba",
        detalle_producto="Eje de prueba",
        requisitos_cliente="Plano de prueba",
        confirmado=True,
    )
    plano = Plano(
        id_plano=uuid.uuid4(),
        id_proyecto=proyecto.id_proyecto,
        codigo_op=f"40{sufijo}",
        codigo_plano=f"PLN-{sufijo}",
        estado_diseno=estado,
        dibujante_asignado=dibujante,
        **campos,
    )
    db.add_all([proyecto, plano])
    db.commit()
    return plano


def test_iniciar_otra_orden_pausa_la_activa_del_mismo_dibujante(db):
    activa = crear_plano_dibujante(
        db, "EN_DISENO", fecha_inicio_diseno=datetime.now(timezone.utc) - timedelta(minutes=30)
    )
    ajena = crear_plano_dibujante(db, "EN_DISENO", dibujante="Otro Dibujante")
    siguiente = crear_plano_dibujante(db, "PLANIFICADA")

    actualizar_plano(siguiente.id_plano, PlanoUpdateRequest(estado_diseno="EN_DISENO"), db)

    db.refresh(activa)
    db.refresh(ajena)
    assert activa.estado_diseno == "PAUSADA"
    assert activa.fecha_fin_diseno is not None
    assert activa.tiempo_total_diseno_minutos >= 29
    assert ajena.estado_diseno == "EN_DISENO"
    assert siguiente.estado_diseno == "EN_DISENO"
    assert siguiente.fecha_inicio_diseno is not None


def test_concurrencia_unitaria_reconoce_variantes_del_nombre_del_dibujante(db):
    activa = crear_plano_dibujante(
        db, "EN_DISENO", dibujante="Ing. Andrés Gómez",
        fecha_inicio_diseno=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    nueva = crear_plano_dibujante(db, "PAUSADA", dibujante="andres gomez - Dibujante",
                                  fecha_inicio_diseno=datetime.now(timezone.utc) - timedelta(minutes=50),
                                  fecha_fin_diseno=datetime.now(timezone.utc) - timedelta(minutes=40))

    actualizar_plano(nueva.id_plano, PlanoUpdateRequest(estado_diseno="EN_DISENO"), db)

    db.refresh(activa)
    assert activa.estado_diseno == "PAUSADA"
    assert activa.tiempo_total_diseno_minutos >= 9


def test_reanudar_descuenta_el_tiempo_en_pausa(db):
    ahora = datetime.now(timezone.utc)
    pausada = crear_plano_dibujante(
        db,
        "PAUSADA",
        fecha_inicio_diseno=ahora - timedelta(minutes=120),
        fecha_fin_diseno=ahora - timedelta(minutes=100),
        tiempo_total_diseno_minutos=20,
    )

    reanudada = actualizar_plano(pausada.id_plano, PlanoUpdateRequest(estado_diseno="EN_DISENO"), db)

    trabajado = datetime.now(timezone.utc) - reanudada.fecha_inicio_diseno.replace(tzinfo=timezone.utc)
    assert reanudada.fecha_fin_diseno is None
    assert timedelta(minutes=19) <= trabajado <= timedelta(minutes=21)


@pytest.mark.parametrize(("estado_actual", "estado_nuevo"), [("PLANIFICADA", "PAUSADA"), ("PAUSADA", "LIBERADA")])
def test_rechaza_transiciones_invalidas_de_pausa(db, estado_actual, estado_nuevo):
    plano = crear_plano_dibujante(db, estado_actual)

    with pytest.raises(HTTPException) as error:
        actualizar_plano(plano.id_plano, PlanoUpdateRequest(estado_diseno=estado_nuevo), db)

    assert error.value.status_code == 400
