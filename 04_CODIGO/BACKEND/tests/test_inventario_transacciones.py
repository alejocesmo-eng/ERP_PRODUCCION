from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.almacen import (
    EntradaConFacturaCreate,
    SalidaAlmacenCreate,
    TipoDestinoEnum,
    TrasladoAlmacenCreate,
    registrar_recepcion_compra,
    registrar_salida_almacen,
    registrar_traslado_almacen,
)
from app.api.v1.inventario import CalidadLoteUpdate, actualizar_estado_calidad_lote
from app.db.database import Base
from app.db.models import (
    ArticuloInventario,
    BOMListaMateriales,
    CatalogoMaterialSAP,
    CentroAlmacen,
    ClaseMovimientoSAP,
    ConsumoMaterialOP,
    LoteMaterial,
    MetodoValoracionSAP,
    MovimientoInventario,
    MovimientoKardexSAP,
    OrdenProduccion,
    RequisicionMRP,
    RegistroCalidadLote,
    SolicitudCompra,
    TrazabilidadRequisicionMRP,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tablas = [
        ArticuloInventario.__table__,
        CentroAlmacen.__table__,
        CatalogoMaterialSAP.__table__,
        BOMListaMateriales.__table__,
        LoteMaterial.__table__,
        MovimientoInventario.__table__,
        MovimientoKardexSAP.__table__,
        RegistroCalidadLote.__table__,
        SolicitudCompra.__table__,
        RequisicionMRP.__table__,
        TrazabilidadRequisicionMRP.__table__,
        OrdenProduccion.__table__,
        ConsumoMaterialOP.__table__,
    ]
    Base.metadata.create_all(engine, tables=tablas)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tablas)
        engine.dispose()


def crear_articulo_y_requisicion(db, estado="EN_COMPRA"):
    centro = CentroAlmacen(
        codigo_centro="CENTRO-01-FUNZA",
        nombre_centro="Centro Funza",
        almacenes=["BOD-MP-01", "BOD-CUARENTENA-QM", "BOD-HERR-02"],
    )
    articulo = ArticuloInventario(
        codigo_sku="MAT-101",
        nombre="Acero de prueba",
        categoria="MATERIA_PRIMA",
        unidad_medida="KG",
        stock_actual=0,
        stock_reservado=0,
        costo_unitario=0,
        metodo_valoracion="FIFO",
    )
    articulo.catalogo_sap = CatalogoMaterialSAP(
        sku_codigo="MAT-101",
        descripcion_tecnica="Acero de prueba",
        tipo_material_sap="ROH",
        unidad_medida="KG",
        clase_valoracion="3000-MP",
        cuenta_contable_activo="143505 - Inventario Materia Prima",
        cuenta_contable_gasto="710505 - Consumo de Materia Prima",
        cuenta_contable_transitoria="220505 - Recepción de facturas por conciliar",
        centro_costo_defecto="CC-100-PLANTA",
        metodo_valoracion=MetodoValoracionSAP.FIFO,
        precio_unitario_valorado=0,
        stock_seguridad=0,
        punto_reorden=0,
        codigo_centro="CENTRO-01-FUNZA",
        almacen_fisico="BOD-MP-01",
    )
    solicitud = SolicitudCompra(
        numero_solicitud="PR-TEST-101",
        nombre_item="Acero de prueba",
        codigo_sku="MAT-101",
        cantidad_solicitada=10,
        unidad_medida="KG",
        estado=estado,
        estado_bom=estado,
    )
    db.add_all([centro, articulo, solicitud])
    db.commit()
    return articulo, solicitud


def registrar_entrada(db, solicitud, cantidad=10, codigo_lote="LOT-TEST-101"):
    return registrar_recepcion_compra(
        EntradaConFacturaCreate(
            numero_solicitud_compra=solicitud.numero_solicitud,
            id_solicitud=solicitud.id_solicitud,
            codigo_sku="MAT-101",
            cantidad_solicitada=Decimal("10"),
            cantidad_recibida=Decimal(str(cantidad)),
            costo_unitario=Decimal("4.25"),
            numero_factura="FAC-TEST-101",
            numero_lote=codigo_lote,
            numero_colada="COL-TEST-101",
        ),
        db,
        {"email": "qa@example.test"},
    )


def test_recepcion_101_cuarentena_y_bloqueo_hasta_liberacion(db):
    _, solicitud = crear_articulo_y_requisicion(db)
    plano_id = uuid4()
    solicitud.id_plano = plano_id
    bom = BOMListaMateriales(
        plano_id=plano_id,
        codigo_material="MAT-101",
        descripcion="Acero de prueba",
        cantidad_requerida=10,
        unidad_medida="KG",
        estado_abastecimiento="EN_COMPRA",
    )
    db.add(bom)
    db.commit()

    resultado = registrar_entrada(db, solicitud)

    lote = db.query(LoteMaterial).one()
    assert resultado["estado_calidad"] == "CUARENTENA"
    assert resultado["estado_requisicion"] == "EN_COMPRA"
    assert solicitud.estado == "RECIBIDA_QM"
    assert lote.stock_disponible == 10
    assert lote.numero_colada == "COL-TEST-101"
    assert db.query(MovimientoInventario).one().tipo_movimiento == "101"
    documento_entrada = db.query(MovimientoKardexSAP).filter(
        MovimientoKardexSAP.clase_movimiento == ClaseMovimientoSAP.ENTRADA_COMPRA_101
    ).one()
    assert documento_entrada.almacen_destino == "BOD-CUARENTENA-QM"
    assert documento_entrada.cuenta_debito == "143505 - Inventario Materia Prima"
    assert documento_entrada.cuenta_credito == "220505 - Recepción de facturas por conciliar"

    with pytest.raises(HTTPException) as error:
        registrar_salida_almacen(
            SalidaAlmacenCreate(
                codigo_sku="MAT-101",
                cantidad_salida=Decimal("1"),
                tipo_destino=TipoDestinoEnum.CENTRO_COSTOS,
            ),
            db,
            {"email": "qa@example.test"},
        )
    assert error.value.status_code == 409

    actualizar_estado_calidad_lote(
        lote.id,
        CalidadLoteUpdate(estado_calidad="LIBERADO", motivo="Certificado 3.1 validado."),
        db,
        {"email": "qa@example.test"},
    )
    assert db.query(RegistroCalidadLote).one().estado_nuevo == "LIBERADO"
    assert solicitud.estado_bom == "EN_ALMACEN"
    assert solicitud.estado == "EN_ALMACEN"
    db.refresh(bom)
    assert bom.estado_abastecimiento == "EN_ALMACEN"
    movimiento_qm = db.query(MovimientoKardexSAP).filter(
        MovimientoKardexSAP.clase_movimiento == ClaseMovimientoSAP.TRASLADO_311
    ).one()
    assert movimiento_qm.almacen_origen == "BOD-CUARENTENA-QM"
    assert movimiento_qm.almacen_destino == "BOD-MP-01"


def test_consumo_261_actualiza_stock_y_costo_real_op(db):
    articulo, solicitud = crear_articulo_y_requisicion(db)
    registrar_entrada(db, solicitud)
    lote = db.query(LoteMaterial).one()
    lote.estado_calidad = "LIBERADO"
    lote.inspeccionado_calidad = True
    lote.stock_reservado = 5
    articulo.stock_reservado = 5
    op = OrdenProduccion(
        id_proyecto=uuid4(),
        codigo_op="OP-TEST-101",
        cantidad_fabricar=1,
    )
    db.add(op)
    db.commit()

    resultado = registrar_salida_almacen(
        SalidaAlmacenCreate(
            codigo_sku="MAT-101",
            cantidad_salida=Decimal("2"),
            tipo_destino=TipoDestinoEnum.ORDEN_PRODUCCION,
            codigo_op=op.codigo_op,
        ),
        db,
        {"email": "qa@example.test"},
    )

    movimiento = db.query(MovimientoInventario).filter(
        MovimientoInventario.tipo_movimiento == "261"
    ).one()
    consumo = db.query(ConsumoMaterialOP).one()
    assert resultado["valor_total"] == 8.5
    assert movimiento.cantidad == 2
    assert articulo.stock_actual == 8
    assert lote.stock_disponible == 8
    assert articulo.stock_reservado == 3
    assert lote.stock_reservado == 3
    assert consumo.op_id == op.id_op
    assert consumo.costo_unitario == Decimal("4.2500")
    documento_op = db.query(MovimientoKardexSAP).filter(
        MovimientoKardexSAP.clase_movimiento == ClaseMovimientoSAP.CONSUMO_OP_261
    ).one()
    assert documento_op.referencia_op == "OP-TEST-101"
    assert documento_op.cuenta_debito == "710505 - Consumo de Materia Prima"
    assert documento_op.cuenta_credito == "143505 - Inventario Materia Prima"


def test_traslado_311_conserva_valor_y_actualiza_ubicacion(db):
    _, solicitud = crear_articulo_y_requisicion(db)
    registrar_entrada(db, solicitud)
    lote = db.query(LoteMaterial).one()
    lote.estado_calidad = "LIBERADO"
    lote.inspeccionado_calidad = True
    lote.almacen_fisico = "BOD-MP-01"
    db.commit()
    db.add(
        CentroAlmacen(
            codigo_centro="CENTRO-02-PLANTA",
            nombre_centro="Centro mecanizado",
            almacenes=["BOD-MP-02"],
        )
    )
    db.commit()

    respuesta = registrar_traslado_almacen(
        TrasladoAlmacenCreate(
            codigo_lote=lote.codigo_lote,
            codigo_centro_destino="CENTRO-02-PLANTA",
            almacen_destino="BOD-MP-02",
        ),
        db,
        {"email": "qa@example.test"},
    )

    documento = db.query(MovimientoKardexSAP).filter(
        MovimientoKardexSAP.clase_movimiento == ClaseMovimientoSAP.TRASLADO_311
    ).one()
    assert respuesta["numero_documento_material"] == documento.numero_documento_material
    assert documento.almacen_origen == "BOD-MP-01"
    assert documento.almacen_destino == "BOD-MP-02"
    assert documento.cuenta_debito == documento.cuenta_credito
    assert lote.almacen_fisico == "BOD-MP-02"


def test_recepcion_rechaza_requisicion_que_no_esta_en_compra(db):
    _, solicitud = crear_articulo_y_requisicion(db, estado="SOLICITADO")

    with pytest.raises(HTTPException) as error:
        registrar_entrada(db, solicitud)

    assert error.value.status_code == 409
    assert db.query(MovimientoInventario).count() == 0
    assert db.query(LoteMaterial).count() == 0


def test_recepcion_parcial_conserva_saldo_en_compra(db):
    _, solicitud = crear_articulo_y_requisicion(db)

    primer_ingreso = registrar_entrada(db, solicitud, cantidad=4)
    segundo_ingreso = registrar_entrada(
        db,
        solicitud,
        cantidad=6,
        codigo_lote="LOT-TEST-102",
    )

    assert primer_ingreso["estado_requisicion"] == "EN_COMPRA"
    assert primer_ingreso["cantidad_pendiente"] == 6
    assert segundo_ingreso["estado_requisicion"] == "EN_COMPRA"
    assert solicitud.estado == "RECIBIDA_QM"
    assert segundo_ingreso["cantidad_pendiente"] == 0
    assert db.query(MovimientoInventario).filter(
        MovimientoInventario.tipo_movimiento == "101"
    ).count() == 2
