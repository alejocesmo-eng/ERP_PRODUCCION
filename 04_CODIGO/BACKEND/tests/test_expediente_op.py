import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1 import planos as planos_api
from app.api.v1.calidad import InspeccionCalidadCreate, registrar_inspeccion_calidad
from app.api.v1.ordenes import liberar_orden_produccion, obtener_expediente_op
from app.api.v1.proyectos import obtener_expediente_pedido
from app.services.historial_planos import registrar_evento_plano
from app.db.database import Base
from app.db.models import (
    BOMListaMateriales,
    Cliente,
    EntregaMaterialOP,
    EstadoOPEnum,
    EstadoPlanoEnum,
    FichaMetrologia,
    HistorialAccionesDocumento,
    InstrumentoMedicion,
    LoteMaterial,
    MovimientoKardexSAP,
    OTDetalle,
    OrdenProduccion,
    PedidoDetalle,
    Permiso,
    Plano,
    PlanoArchivo,
    PlanoHistorial,
    Producto,
    Proyecto,
    RegistroTiemposProduccion,
    Rol,
    RolPermiso,
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
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(planos_api, "DIRECTORIO_STATIC_PLANOS", str(tmp_path))
    engine = create_engine("sqlite:///:memory:")
    tablas = [
        Producto.__table__,
        Proyecto.__table__,
        Cliente.__table__,
        PedidoDetalle.__table__,
        Plano.__table__,
        PlanoArchivo.__table__,
        PlanoHistorial.__table__,
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
        HistorialAccionesDocumento.__table__,
        Rol.__table__,
        Permiso.__table__,
        RolPermiso.__table__,
    ]
    Base.metadata.create_all(engine, tables=tablas)
    session = sessionmaker(bind=engine)()
    session.info["directorio"] = tmp_path
    # Asignación de la migración 16: DISENO libera OP
    session.add_all([
        Rol(id_rol="DISENO", nombre_rol="Diseño"),
        Permiso(id_permiso="PERM_OP_LIBERAR", modulo="DISENO"),
        RolPermiso(id_rol="DISENO", id_permiso="PERM_OP_LIBERAR"),
    ])
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tablas)
        engine.dispose()


def crear_expediente(db, con_pdf=True, estado_bom="EN_ALMACEN", aprobado=False):
    id_proyecto = uuid.uuid4()
    id_plano = uuid.uuid4()
    id_op = uuid.uuid4()
    id_detalle = uuid.uuid4()
    producto = Producto(id_producto=uuid.uuid4(), codigo_rn="RN-088-001-000001", descripcion="Conjunto de prueba")
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
        id_producto=producto.id_producto,
        codigo_op="4001234",
        codigo_plano="PLN-88-A",
        revision="REV-02",
        dibujante_asignado="Ana Diseño",
        unidad_planta="Mecanizados",
        archivo_url="/static/planos/PLN-88-A.pdf" if con_pdf else None,
    )
    if aprobado:
        plano.estado = EstadoPlanoEnum.APROBADO
        plano.aprobado_por = "lider.diseno@hd.com"
        plano.fecha_aprobacion = datetime.now(timezone.utc)
    op = OrdenProduccion(
        id_op=id_op,
        id_proyecto=id_proyecto,
        id_plano=id_plano,
        id_producto=producto.id_producto,
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
    db.add_all([producto, proyecto, plano, op, material, detalle, relacion])
    if con_pdf:
        # PDF vigente en planos_archivos con su archivo en disco (condición 1 de la liberación)
        contenido = b"%PDF plano PLN-88-A"
        sha256 = hashlib.sha256(contenido).hexdigest()
        (db.info["directorio"] / "PLN-88-A.pdf").write_bytes(contenido)
        db.add(PlanoArchivo(
            id_plano=id_plano,
            tipo="PDF",
            ruta="/static/planos/PLN-88-A.pdf",
            nombre_original="PLN-88-A.pdf",
            tamano_bytes=len(contenido),
            sha256=sha256,
            revision="REV-02",
            vigente=True,
        ))
    db.commit()
    return op


def test_expediente_retorna_pedido_piezas_bom_y_quality_gate(db):
    crear_expediente(db, aprobado=True)

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
    crear_expediente(db, aprobado=True)

    resultado = liberar_orden_produccion(
        "4001234",
        db=db,
        usuario_actual={"email": "diseno@hd.com", "rol": "DISENO"},
    )

    op = db.query(OrdenProduccion).filter_by(codigo_op="4001234").one()
    assert resultado["estado_operativo"] == "LIBERADA"
    assert op.estado.value == "LIBERADA"
    assert op.liberada_en is not None
    evento = db.query(HistorialAccionesDocumento).filter_by(identificador_documento="4001234").one()
    assert evento.accion == "OP_LIBERADA"
    assert evento.usuario_responsable == "diseno@hd.com"


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


def test_expediente_trae_el_historial_de_cada_plano_en_orden(db):
    crear_expediente(db, aprobado=True)
    plano = db.query(Plano).filter(Plano.codigo_plano == "PLN-88-A").one()
    registrar_evento_plano(db, plano, "CARGA_ARCHIVO", "ana.diseno@hd.com", tipo_archivo="PDF", sha256="b" * 64)
    registrar_evento_plano(db, plano, "APROBACION", "lider.diseno@hd.com")
    db.commit()

    expediente = obtener_expediente_op("4001234", db=db, usuario_actual={"rol": "PRODUCCION"})

    historial = expediente["planos"][0]["historial"]
    assert [(e["tipo_evento"], e["usuario"]) for e in historial] == [
        ("CARGA_ARCHIVO", "ana.diseno@hd.com"),
        ("APROBACION", "lider.diseno@hd.com"),
    ]
    assert historial[0]["sha256"] == "b" * 64
    assert historial[0]["version"] == "REV-02"
