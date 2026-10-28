import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.calidad import InspeccionCalidadCreate, registrar_inspeccion_calidad
from app.api.v1.ordenes import liberar_orden_produccion, obtener_expediente_op
from app.api.v1.proyectos import obtener_expediente_pedido
from app.db.database import Base
from app.db.models import (
    BOMListaMateriales,
    Cliente,
    EntregaMaterialOP,
    EstadoOPEnum,
    FichaMetrologia,
    InstrumentoMedicion,
    LoteMaterial,
    MovimientoKardexSAP,
    OTDetalle,
    OrdenProduccion,
    PedidoDetalle,
    Plano,
    Proyecto,
    RegistroTiemposProduccion,
    ServicioTerceroOP,
    SolicitudCompra,
)
from app.db.models_calidad import InspeccionCalidad
from app.db.models_produccion import (
    NotificacionLider,
    OperacionOT,
    RegistroTiempoOperario,
    SubLoteOperacion,
    TipoNotificacionEnum,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tablas = [
        Proyecto.__table__,
        Cliente.__table__,
        PedidoDetalle.__table__,
        Plano.__table__,
        OTDetalle.__table__,
        OrdenProduccion.__table__,
        BOMListaMateriales.__table__,
        SolicitudCompra.__table__,
        LoteMaterial.__table__,
        EntregaMaterialOP.__table__,
        OperacionOT.__table__,
        SubLoteOperacion.__table__,
        RegistroTiempoOperario.__table__,
        RegistroTiemposProduccion.__table__,
        InspeccionCalidad.__table__,
        NotificacionLider.__table__,
        ServicioTerceroOP.__table__,
        InstrumentoMedicion.__table__,
        FichaMetrologia.__table__,
        MovimientoKardexSAP.__table__,
    ]
    Base.metadata.create_all(engine, tables=tablas)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tablas)
        engine.dispose()


def crear_expediente(db, con_pdf=True, estado_bom="EN_ALMACEN"):
    id_proyecto = uuid.uuid4()
    id_plano = uuid.uuid4()
    id_op = uuid.uuid4()
    id_detalle = uuid.uuid4()
    proyecto = Proyecto(
        id_proyecto=id_proyecto,
        numero_pedido="PED-2026-88",
        codigo_proyecto="PRY-88",
        cliente_nombre="Cliente de prueba",
        detalle_producto="Conjunto de prueba",
        requisitos_cliente="Acabado según plano",
        confirmado=True,
    )
    plano = Plano(
        id_plano=id_plano,
        id_proyecto=id_proyecto,
        codigo_op="4001234",
        codigo_plano="PLN-88-A",
        revision="REV-02",
        dibujante_asignado="Ana Diseño",
        unidad_planta="Mecanizados",
        archivo_url="/static/planos/PLN-88-A.pdf" if con_pdf else None,
    )
    op = OrdenProduccion(
        id_op=id_op,
        id_proyecto=id_proyecto,
        id_plano=id_plano,
        codigo_op="4001234",
        cantidad_fabricar=3,
    )
    material = BOMListaMateriales(
        plano_id=id_plano,
        codigo_material="MAT-88",
        descripcion="Acero de prueba",
        cantidad_requerida=5,
        unidad_medida="KG",
        estado_abastecimiento=estado_bom,
    )
    detalle = PedidoDetalle(
        detalle_id=id_detalle,
        pedido_id=id_proyecto,
        codigo_producto="PIEZA-88",
        descripcion="Eje mecanizado",
        cantidad_solicitada=3,
        unidad="UND",
    )
    relacion = OTDetalle(
        detalle_pedido_id=id_detalle,
        ot_id=id_plano,
        cantidad_asignada=3,
    )
    db.add_all([proyecto, plano, op, material, detalle, relacion])
    db.commit()
    return op


def test_expediente_retorna_pedido_piezas_bom_y_quality_gate(db):
    crear_expediente(db)

    expediente = obtener_expediente_op(
        "4001234",
        db=db,
        usuario_actual={"rol": "PRODUCCION"},
    )

    assert expediente["pedido"]["numero_pedido"] == "PED-2026-88"
    assert expediente["planos"][0]["piezas"][0]["codigo_pieza"] == "PIEZA-88"
    assert expediente["resumen_bom"][0]["codigo_material"] == "MAT-88"
    assert expediente["estado_bom"] == "EN_ALMACEN"
    assert expediente["quality_gate"]["aprobado"] is True


def test_expediente_pedido_retorna_posiciones_y_trazabilidad_nm(db):
    op = crear_expediente(db)

    expediente = obtener_expediente_pedido(op.id_proyecto, db=db)

    assert expediente["numero_pedido"] == "PED-2026-88"
    assert expediente["pedido_detalles"][0]["posicion"] == "POS-10"
    assert expediente["pedido_detalles"][0]["codigo_producto"] == "PIEZA-88"
    assert expediente["pedido_detalles"][0]["cantidad_asignada"] == 3
    assert expediente["pedido_detalles"][0]["estado_cobertura"] == "ASIGNADO"
    assert expediente["pedido_detalles"][0]["ot_detalles"][0]["orden_produccion"]["codigo_op"] == "4001234"
    assert expediente["ordenes_produccion"][0]["estado_pdf"] == "CARGA_OK"
    assert expediente["ordenes_produccion"][0]["estado_insumo"] == "EN_ALMACEN"


@pytest.mark.parametrize(
    ("con_pdf", "estado_bom"),
    [(False, "EN_ALMACEN"), (True, "EN_COMPRA")],
)
def test_liberacion_bloquea_op_si_falla_quality_gate(db, con_pdf, estado_bom):
    crear_expediente(db, con_pdf=con_pdf, estado_bom=estado_bom)

    with pytest.raises(HTTPException) as error:
        liberar_orden_produccion(
            "4001234",
            db=db,
            usuario_actual={"rol": "DISENO"},
        )

    assert error.value.status_code == 400
    assert db.query(OrdenProduccion).filter_by(codigo_op="4001234").one().estado.value == "BORRADOR"


def test_liberacion_actualiza_estado_despues_de_validar_gate(db):
    crear_expediente(db)

    resultado = liberar_orden_produccion(
        "4001234",
        db=db,
        usuario_actual={"rol": "DISENO"},
    )

    op = db.query(OrdenProduccion).filter_by(codigo_op="4001234").one()
    assert resultado["estado_operativo"] == "LIBERADA"
    assert op.estado.value == "LIBERADA"
    assert op.liberada_en is not None


def test_expediente_no_expone_otra_op_del_mismo_pedido(db):
    op = crear_expediente(db)
    plano_ajeno = Plano(
        id_proyecto=op.id_proyecto,
        codigo_op="4009999",
        codigo_plano="PLN-AJENO",
        revision="REV-01",
        archivo_url="/static/planos/ajeno.pdf",
    )
    db.add(plano_ajeno)
    db.flush()
    db.add(SolicitudCompra(
        numero_solicitud="PR-OP-AJENA",
        codigo_op="4009999",
        codigo_plano="PLN-AJENO",
        id_proyecto=op.id_proyecto,
        id_plano=plano_ajeno.id_plano,
        nombre_item="Material de otra OP",
        estado_bom="EN_COMPRA",
    ))
    db.commit()

    expediente = obtener_expediente_op(
        "4001234",
        db=db,
        usuario_actual={"rol": "VENTAS"},
    )

    assert [plano["codigo_plano"] for plano in expediente["planos"]] == ["PLN-88-A"]
    assert expediente["solicitudes_compra"] == []


def test_aprobacion_de_despacho_notifica_y_deja_la_orden_lista_para_cierre(db):
    orden = crear_expediente(db)
    orden.estado = EstadoOPEnum.TERMINADA
    db.commit()
    solicitud = InspeccionCalidadCreate(
        codigo_op="4001234",
        codigo_plano="PLN-88-A",
        inspector_nombre="Inspector de calidad",
        resultado_inspeccion="APROBADO_DESPACHO",
        mediciones_dimensionales=[
            {
                "caracteristica": "Diámetro",
                "nominal": 25,
                "tolerancia_min": 24.98,
                "tolerancia_max": 25.02,
                "valor_medido": 25,
            }
        ],
        registros_fotograficos=[
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/T2sAAAAASUVORK5CYII="
        ],
    )

    inspeccion = registrar_inspeccion_calidad(solicitud, db=db)

    notificacion = db.query(NotificacionLider).one()
    assert inspeccion.notificado_jefe_produccion is True
    assert notificacion.tipo_notificacion == TipoNotificacionEnum.CALIDAD_APROBADA_DESPACHO
    assert db.get(OrdenProduccion, orden.id_op).estado == EstadoOPEnum.LISTA_PARA_LIBERAR


def test_tratamiento_termico_registra_servicio_en_la_misma_transaccion(db):
    orden = crear_expediente(db)
    orden.estado = EstadoOPEnum.INSPECCION_CALIDAD
    db.commit()
    solicitud = InspeccionCalidadCreate(
        codigo_op="4001234",
        codigo_plano="PLN-88-A",
        inspector_nombre="Inspector de calidad",
        resultado_inspeccion="APROBADO_TRATAMIENTO",
        descripcion_tratamiento="Temple y revenido",
        piezas_enviadas_tratamiento=2,
        proveedor_tratamiento="Tratamientos Industriales",
        proveedor_tratamiento_email="servicio@example.test",
        mediciones_dimensionales=[
            {
                "caracteristica": "Diámetro",
                "nominal": 25,
                "tolerancia_min": 24.98,
                "tolerancia_max": 25.02,
                "valor_medido": 25,
            }
        ],
        registros_fotograficos=[
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/T2sAAAAASUVORK5CYII="
        ],
    )

    inspeccion = registrar_inspeccion_calidad(solicitud, db=db)

    servicio = db.query(ServicioTerceroOP).one()
    assert inspeccion.informe_tratamiento_html
    assert inspeccion.notificado_jefe_produccion is False
    assert servicio.op_id == orden.id_op
    assert servicio.proveedor == "Tratamientos Industriales"
