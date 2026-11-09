import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import planos as planos_api
from app.api.v1.planos import PlanoUpdateRequest, actualizar_plano
from app.db.database import Base
from app.db.models import BOMListaMateriales, EstadoPlanoEnum, Plano, PlanoArchivo, Proyecto


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(planos_api, "DIRECTORIO_STATIC_PLANOS", str(tmp_path))
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Proyecto.__table__,
        Plano.__table__,
        BOMListaMateriales.__table__,
        PlanoArchivo.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    session = sessionmaker(bind=engine)()
    session.info["directorio"] = tmp_path
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tables)
        engine.dispose()


PDF_PRUEBA = b"%PDF plano PLN-TEST-RN004"


def crear_plano_en_diseno(db, con_pdf=True, estado_bom=None, aprobado=True):
    """Plano en diseño; con_pdf registra un PDF vigente en planos_archivos con su archivo en disco."""
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
        fecha_inicio_diseno=datetime.now(timezone.utc) - timedelta(minutes=90),
    )
    if aprobado:
        plano.estado = EstadoPlanoEnum.APROBADO
        plano.aprobado_por = "lider.diseno@prueba.test"
        plano.fecha_aprobacion = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.add_all([proyecto, plano])
    if con_pdf:
        (db.info["directorio"] / "PLN-TEST-RN004.pdf").write_bytes(PDF_PRUEBA)
        plano.archivo_pdf_url = "/static/planos/PLN-TEST-RN004.pdf"
        db.add(PlanoArchivo(
            id_plano=plano.id_plano,
            tipo="PDF",
            ruta="/static/planos/PLN-TEST-RN004.pdf",
            nombre_original="PLN-TEST-RN004.pdf",
            tamano_bytes=len(PDF_PRUEBA),
            sha256=hashlib.sha256(PDF_PRUEBA).hexdigest(),
            vigente=True,
        ))
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
    ("con_pdf", "estado_bom", "aprobado", "texto"),
    [
        (False, "SOLICITADO", True, "no tiene un PDF vigente"),
        (True, "SIN_SOLICITAR", True, "BOM sin solicitar"),
        (True, None, True, "BOM sin solicitar"),
        (True, "SOLICITADO", False, "APROBADO"),
    ],
    ids=["sin_pdf_vigente", "bom_sin_solicitar", "sin_bom", "plano_sin_aprobar"],
)
def test_entrega_diseno_rechaza_sin_pdf_sin_aprobar_o_sin_bom_radicada(db, con_pdf, estado_bom, aprobado, texto):
    plano = crear_plano_en_diseno(db, con_pdf, estado_bom, aprobado)

    with pytest.raises(HTTPException) as error:
        actualizar_plano(plano.id_plano, PlanoUpdateRequest(estado_diseno="LISTA_PARA_LIBERAR"), db)

    assert error.value.status_code == 400
    assert texto in error.value.detail
    db.rollback()  # fin de la petición: get_db cierra la sesión sin commit
    db.refresh(plano)
    assert plano.estado_diseno == "EN_DISENO"


@pytest.mark.parametrize("estado_bom", ["SOLICITADO", "EN_COMPRA"])
def test_entrega_diseno_pasa_con_bom_radicada_y_cierra_cronometro(db, estado_bom):
    plano = crear_plano_en_diseno(db, True, estado_bom)

    actualizado = actualizar_plano(plano.id_plano, PlanoUpdateRequest(estado_diseno="LISTA_PARA_LIBERAR"), db)

    assert actualizado.estado_diseno == "LISTA_PARA_LIBERAR"
    assert actualizado.fecha_fin_diseno is not None
    assert actualizado.tiempo_total_diseno_minutos >= 89


def test_entrega_diseno_verifica_el_hash_del_pdf(db):
    plano = crear_plano_en_diseno(db, True, "SOLICITADO")
    (db.info["directorio"] / "PLN-TEST-RN004.pdf").write_bytes(b"%PDF alterado")

    with pytest.raises(HTTPException) as error:
        actualizar_plano(plano.id_plano, PlanoUpdateRequest(estado_diseno="LISTA_PARA_LIBERAR"), db)

    assert error.value.status_code == 409
    assert "sha256" in error.value.detail


def test_liberada_conserva_gate_de_stock_completo(db):
    plano = crear_plano_en_diseno(db, True, "SOLICITADO")

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


def test_observaciones_tecnicas_se_guardan_sin_alterar_estado_ni_cronometro(db):
    inicio = datetime.now(timezone.utc) - timedelta(minutes=15)
    plano = crear_plano_dibujante(db, "EN_DISENO", fecha_inicio_diseno=inicio)
    nota = "Dejar sobremedida de 0.3 mm para rectificado; tolerancia h7 en Ø 50."

    actualizado = actualizar_plano(plano.id_plano, PlanoUpdateRequest(observaciones_tecnicas=nota), db)

    assert actualizado.observaciones_tecnicas == nota
    assert actualizado.estado_diseno == "EN_DISENO"
    assert actualizado.fecha_inicio_diseno.replace(tzinfo=timezone.utc) == inicio
