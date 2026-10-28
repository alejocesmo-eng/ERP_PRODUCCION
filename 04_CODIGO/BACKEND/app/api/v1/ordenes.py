from typing import List, Optional
from uuid import UUID
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.db.models import (
    BOMListaMateriales,
    EntregaMaterialOP,
    InstrumentoMedicion,
    LoteMaterial,
    OTDetalle,
    OrdenProduccion,
    PedidoDetalle,
    Plano,
    Proyecto,
    RegistroTiemposProduccion,
    SolicitudCompra,
    EstadoOPEnum,
)
from app.db.models_calidad import InspeccionCalidad
from app.db.models_produccion import OperacionOT, RegistroTiempoOperario, SubLoteOperacion
from app.api.deps import obtener_usuario_actual, requerir_roles
from app.api.v1.quality_gate import validar_gate_calidad

router = APIRouter()

ROLES_EXPEDIENTE = ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"]


def _valor_enum(valor):
    return valor.value if hasattr(valor, "value") else valor


def _fecha_iso(valor):
    return valor.isoformat() if valor else None


def _serializar_inspeccion(inspeccion):
    return {
        "id_inspeccion": str(inspeccion.id_inspeccion),
        "codigo_plano": inspeccion.codigo_plano,
        "inspector_nombre": inspeccion.inspector_nombre,
        "resultado_inspeccion": inspeccion.resultado_inspeccion,
        "requiere_tratamiento": inspeccion.requiere_tratamiento,
        "descripcion_tratamiento": inspeccion.descripcion_tratamiento,
        "registros_fotograficos": inspeccion.registros_fotograficos or [],
        "observaciones_inspector": inspeccion.observaciones_inspector,
        "fecha_inspeccion": _fecha_iso(inspeccion.fecha_inspeccion),
    }


@router.get("/expediente/{codigo_op}")
def obtener_expediente_op(
    codigo_op: str,
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(requerir_roles(ROLES_EXPEDIENTE)),
):
    op = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == codigo_op).first()
    if not op:
        raise HTTPException(status_code=404, detail="No se encontró la Orden de Producción indicada.")

    proyecto = db.query(Proyecto).filter(Proyecto.id_proyecto == op.id_proyecto).first()
    if not proyecto:
        raise HTTPException(status_code=409, detail="La Orden de Producción no tiene un pedido comercial válido.")

    if op.id_plano:
        planos = db.query(Plano).filter(Plano.id_plano == op.id_plano).all()
    else:
        planos = db.query(Plano).filter(
            Plano.id_proyecto == op.id_proyecto,
            Plano.codigo_op == op.codigo_op,
        ).all()

    plano_ids = [plano.id_plano for plano in planos]
    ot_detalles = db.query(OTDetalle).filter(OTDetalle.ot_id.in_(plano_ids)).all() if plano_ids else []
    detalle_ids = {detalle.detalle_pedido_id for detalle in ot_detalles}
    detalles_pedido = (
        db.query(PedidoDetalle).filter(PedidoDetalle.detalle_id.in_(detalle_ids)).all()
        if detalle_ids else []
    )
    detalle_por_id = {detalle.detalle_id: detalle for detalle in detalles_pedido}
    plano_por_id = {plano.id_plano: plano for plano in planos}

    lineas_bom = (
        db.query(BOMListaMateriales).filter(BOMListaMateriales.plano_id.in_(plano_ids)).all()
        if plano_ids else []
    )
    solicitudes = db.query(SolicitudCompra).filter(
        or_(
            SolicitudCompra.codigo_op == op.codigo_op,
            SolicitudCompra.id_plano.in_(plano_ids) if plano_ids else False,
            SolicitudCompra.codigo_plano.in_([plano.codigo_plano for plano in planos]) if planos else False,
        )
    ).order_by(SolicitudCompra.fecha_solicitud.desc()).all()

    codigo_materiales = {linea.codigo_material for linea in lineas_bom}
    lotes = (
        db.query(LoteMaterial).filter(LoteMaterial.codigo_material.in_(codigo_materiales)).all()
        if codigo_materiales else []
    )
    lotes_por_material = {}
    for lote in lotes:
        lotes_por_material.setdefault(lote.codigo_material, []).append({
            "codigo_lote": lote.codigo_lote,
            "numero_colada": lote.numero_colada,
            "estado_calidad": lote.estado_calidad,
            "almacen_fisico": lote.almacen_fisico,
            "stock_disponible": lote.stock_disponible,
            "stock_reservado": lote.stock_reservado,
            "certificado_calidad_url": lote.certificado_calidad_url,
        })

    bom_por_plano = {}
    for linea in lineas_bom:
        bom_por_plano.setdefault(linea.plano_id, []).append({
            "codigo_material": linea.codigo_material,
            "descripcion": linea.descripcion,
            "cantidad_requerida": linea.cantidad_requerida,
            "unidad_medida": linea.unidad_medida,
            "estado_abastecimiento": linea.estado_abastecimiento,
            "lotes": lotes_por_material.get(linea.codigo_material, []),
        })

    piezas_por_plano = {}
    for relacion in ot_detalles:
        detalle = detalle_por_id.get(relacion.detalle_pedido_id)
        if detalle:
            piezas_por_plano.setdefault(relacion.ot_id, []).append({
                "codigo_pieza": detalle.codigo_producto or str(detalle.detalle_id),
                "nombre": detalle.descripcion,
                "cantidad_requerida": detalle.cantidad_solicitada,
                "cantidad_asignada": relacion.cantidad_asignada,
                "unidad": detalle.unidad,
                "prioridad": detalle.prioridad,
                "observaciones": detalle.observaciones,
            })

    planos_expediente = []
    for plano in planos:
        planos_expediente.append({
            "id_plano": str(plano.id_plano),
            "codigo_plano": plano.codigo_plano,
            "revision": plano.revision,
            "estado_diseno": plano.estado_diseno,
            "dibujante_asignado": plano.dibujante_asignado,
            "unidad_planta": plano.unidad_planta,
            "material_requerido": plano.material_requerido,
            "archivo_url": plano.archivo_url,
            "fecha_entrega_produccion": _fecha_iso(plano.fecha_entrega_produccion),
            "piezas": piezas_por_plano.get(plano.id_plano, []),
            "resumen_bom": bom_por_plano.get(plano.id_plano, []),
        })

    estados_bom = [linea.estado_abastecimiento for linea in lineas_bom]
    estados_solicitud = [solicitud.estado_bom for solicitud in solicitudes if solicitud.estado_bom]
    if estados_bom:
        estado_bom = (
            "ENTREGADO" if all(estado == "ENTREGADO" for estado in estados_bom)
            else "EN_ALMACEN" if all(estado in {"EN_ALMACEN", "ENTREGADO"} for estado in estados_bom)
            else next((estado for estado in estados_bom if estado not in {"EN_ALMACEN", "ENTREGADO"}), "SOLICITADO")
        )
    elif estados_solicitud:
        estado_bom = estados_solicitud[0]
    else:
        estado_bom = "SIN_SOLICITAR"

    gate_aprobado = bool(
        planos
        and all(plano.archivo_url and plano.archivo_url.strip() for plano in planos)
        and lineas_bom
        and all(linea.estado_abastecimiento in {"EN_ALMACEN", "ENTREGADO"} for linea in lineas_bom)
    )
    motivos_gate = []
    if not planos:
        motivos_gate.append("La OP no tiene planos asociados.")
    elif any(not plano.archivo_url or not plano.archivo_url.strip() for plano in planos):
        motivos_gate.append("Faltan planos PDF.")
    if not lineas_bom:
        motivos_gate.append("La OP no tiene líneas de materiales abastecidas.")
    else:
        pendientes = sorted({
            linea.codigo_material for linea in lineas_bom
            if linea.estado_abastecimiento not in {"EN_ALMACEN", "ENTREGADO"}
        })
        if pendientes:
            motivos_gate.append(f"Materiales pendientes en almacén: {', '.join(pendientes)}.")

    operaciones = (
        db.query(OperacionOT).filter(OperacionOT.id_plano.in_(plano_ids)).all()
        if plano_ids else []
    )
    operaciones_por_plano = {}
    for operacion in operaciones:
        operaciones_por_plano[operacion.id_plano] = (
            operaciones_por_plano.get(operacion.id_plano, 0) + (operacion.cantidad_acumulada_ok or 0)
        )
    for plano_data in planos_expediente:
        plano_data["cantidad_ok"] = operaciones_por_plano.get(UUID(plano_data["id_plano"]), 0)
    operacion_ids = [operacion.id_operacion for operacion in operaciones]
    sublotes = (
        db.query(SubLoteOperacion).filter(SubLoteOperacion.id_operacion.in_(operacion_ids)).all()
        if operacion_ids else []
    )
    sublote_ids = [sublote.id_sublote for sublote in sublotes]
    registros_sublote = (
        db.query(RegistroTiempoOperario).filter(RegistroTiempoOperario.id_sublote.in_(sublote_ids)).all()
        if sublote_ids else []
    )
    sublote_por_id = {sublote.id_sublote: sublote for sublote in sublotes}
    operacion_por_id = {operacion.id_operacion: operacion for operacion in operaciones}
    tiempos_mes = [{
        "tipo_registro": "SUBLOTE",
        "codigo_plano": operacion_por_id[operacion_id].codigo_plano,
        "proceso": operacion_por_id[operacion_id].nombre_proceso,
        "numero_sublote": sublote.numero_sublote,
        "operario": sublote.operario_nombre or registro.operario_id,
        "maquina": registro.maquina_codigo or sublote.maquina_codigo,
        "setup_segundos": registro.tiempo_setup_segundos or 0,
        "mecanizado_segundos": registro.tiempo_produccion_segundos or 0,
        "piezas_ok": registro.piezas_conformes_ok or 0,
        "piezas_rechazadas": registro.piezas_defectuosas_scrap or 0,
        "fecha": _fecha_iso(registro.creado_en),
    } for registro in registros_sublote
        for sublote in [sublote_por_id.get(registro.id_sublote)]
        if sublote and (operacion_id := sublote.id_operacion) in operacion_por_id]

    tiempos_mes.extend({
        "tipo_registro": "ORDEN",
        "operario": registro.operario_id,
        "maquina": registro.estacion_id,
        "tipo_tiempo": registro.tipo_tiempo,
        "setup_segundos": registro.segundos_ejecutados if registro.tipo_tiempo == "SETUP" else 0,
        "mecanizado_segundos": registro.segundos_ejecutados if registro.tipo_tiempo != "SETUP" else 0,
        "fecha_inicio": _fecha_iso(registro.fecha_hora_inicio),
        "fecha_fin": _fecha_iso(registro.fecha_hora_fin),
        "observacion": registro.observacion_desviacion,
    } for registro in db.query(RegistroTiemposProduccion).filter(
        RegistroTiemposProduccion.orden_produccion_id == op.id_op
    ).order_by(RegistroTiemposProduccion.fecha_hora_inicio.desc()).all())

    inspecciones = db.query(InspeccionCalidad).filter(
        InspeccionCalidad.codigo_op == op.codigo_op
    ).order_by(InspeccionCalidad.fecha_inspeccion.desc()).all()
    # Fichas de metrología (Opcional - Solo si el modelo existe)
    fichas = []
    try:
        from app.db.models import FichaMetrologia
        fichas = db.query(FichaMetrologia).filter(FichaMetrologia.op_id == op.id_op).all()
    except ImportError:
        fichas = []
    instrumentos_ids = {ficha.instrumento_id for ficha in fichas}
    instrumentos = (
        db.query(InstrumentoMedicion).filter(InstrumentoMedicion.id.in_(instrumentos_ids)).all()
        if instrumentos_ids else []
    )
    instrumento_por_id = {instrumento.id: instrumento for instrumento in instrumentos}
    mediciones = [{
        "instrumento": (
            instrumento_por_id[ficha.instrumento_id].nombre
            if ficha.instrumento_id in instrumento_por_id else str(ficha.instrumento_id)
        ),
        "cota_medida": ficha.cota_medida,
        "tolerancia_min": ficha.tolerancia_min,
        "tolerancia_max": ficha.tolerancia_max,
        "resultado_conforme": ficha.resultado_conforme,
        "fecha_inspeccion": _fecha_iso(ficha.fecha_inspeccion),
    } for ficha in fichas]

    entregas = db.query(EntregaMaterialOP).filter(EntregaMaterialOP.op_id == op.id_op).all()
    cantidad_entregada = sum(entrega.cantidad_entregada for entrega in entregas)
    if not entregas:
        estado_entregas = "SIN_DESPACHO"
    elif cantidad_entregada >= op.cantidad_fabricar:
        estado_entregas = "COMPLETA"
    else:
        estado_entregas = "PARCIAL"
    lote_por_id = {lote.id: lote for lote in lotes}
    return {
        "codigo_op": op.codigo_op,
        "estado_operativo": _valor_enum(op.estado),
        "estado_bom": estado_bom,
        "cantidad_programada": op.cantidad_fabricar,
        "porcentaje_avance": op.porcentaje_avance or 0,
        "observaciones": op.observaciones,
        "pedido": {
            "numero_pedido": proyecto.numero_pedido,
            "cliente": proyecto.cliente_nombre,
            "detalle": proyecto.detalle_producto,
            "cantidad": proyecto.cantidad,
            "requisitos": proyecto.requisitos_cliente,
            "fecha_limite": _fecha_iso(proyecto.fecha_compromiso),
            "estado": "CONFIRMADO" if proyecto.confirmado else "EN_GESTION",
            "estado_entregas": estado_entregas,
            "cantidad_entregada": cantidad_entregada,
        },
        "disenador_responsable": planos[0].dibujante_asignado if planos else None,
        "unidad_planta": planos[0].unidad_planta if planos else None,
        "plano_principal": {
            "archivo_url": planos[0].archivo_url,
            "codigo_plano": planos[0].codigo_plano,
            "revision": planos[0].revision,
        } if planos else None,
        "quality_gate": {
            "aprobado": gate_aprobado,
            "motivos": motivos_gate,
        },
        "planos": planos_expediente,
        "resumen_bom": [material for materiales in bom_por_plano.values() for material in materiales],
        "solicitudes_compra": [{
            "numero_solicitud": solicitud.numero_solicitud,
            "codigo_plano": solicitud.codigo_plano,
            "nombre_item": solicitud.nombre_item,
            "cantidad_solicitada": solicitud.cantidad_solicitada,
            "unidad_medida": solicitud.unidad_medida,
            "estado_bom": solicitud.estado_bom,
            "fecha_solicitud": _fecha_iso(solicitud.fecha_solicitud),
        } for solicitud in solicitudes],
        "despachos_material": [{
            "codigo_lote": lote_por_id[entrega.lote_id].codigo_lote if entrega.lote_id in lote_por_id else None,
            "numero_colada": lote_por_id[entrega.lote_id].numero_colada if entrega.lote_id in lote_por_id else None,
            "cantidad_entregada": entrega.cantidad_entregada,
            "fecha_entrega": _fecha_iso(entrega.fecha_entrega),
        } for entrega in entregas],
        "tiempos_mes": tiempos_mes,
        "inspecciones_calidad": [_serializar_inspeccion(inspeccion) for inspeccion in inspecciones],
        "mediciones_metrologicas": mediciones,
    }


@router.patch("/liberar/{codigo_op}")
def liberar_orden_produccion(
    codigo_op: str,
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(requerir_roles(["ADMIN", "DISENO"])),
):
    op = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == codigo_op).first()
    if not op:
        raise HTTPException(status_code=404, detail="No se encontró la Orden de Producción indicada.")

    plano = db.query(Plano).filter(Plano.id_plano == op.id_plano).first() if op.id_plano else (
        db.query(Plano).filter(
            Plano.id_proyecto == op.id_proyecto,
            Plano.codigo_op == op.codigo_op,
        ).first()
    )
    validar_gate_calidad(db, plano)

    op.estado = EstadoOPEnum.LIBERADA
    op.liberada_en = datetime.now().astimezone()
    try:
        db.commit()
        db.refresh(op)
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo liberar la Orden de Producción.",
        ) from error
    return {
        "codigo_op": op.codigo_op,
        "estado_operativo": _valor_enum(op.estado),
        "liberada_en": _fecha_iso(op.liberada_en),
    }


# --- SCHEMAS PYDANTIC (ESTÁNDAR SAP B1 / ISO 9001:2026) ---

class ItemPiezaPlano(BaseModel):
    id_pieza: Optional[str] = None
    codigo_plano: str
    revision: Optional[str] = "REV-01"
    detalle_pieza: str
    cantidad: int = 1
    material_requerido: Optional[str] = None
    archivo_url: Optional[str] = None
    estado_diseno: Optional[str] = "LIBERADA"

class ItemPedidoCompuesto(BaseModel):
    id_proyecto: UUID
    codigo_op: str
    detalle_producto: Optional[str] = None
    cantidad: int
    codigo_plano: Optional[str] = None
    revision: Optional[str] = None
    archivo_url: Optional[str] = None
    estado_diseno: Optional[str] = None
    estado_produccion: Optional[str] = None
    porcentaje_avance: Optional[float] = 0.0
    fecha_compromiso: Optional[str] = None
    piezas_desglosadas: List[ItemPiezaPlano] = []


class OrdenProduccionCreate(BaseModel):
    codigo_op: str
    id_proyecto: UUID
    id_plano: Optional[UUID] = None
    cantidad_programada: Optional[int] = 1
    observaciones: Optional[str] = None


class OrdenProduccionUpdate(BaseModel):
    estado: Optional[str] = None
    estado_produccion: Optional[str] = None
    porcentaje_avance: Optional[float] = None
    observaciones: Optional[str] = None


class OrdenProduccionVistaResponse(BaseModel):
    id_proyecto: UUID
    codigo_op: str
    numero_pedido: str
    cliente_nombre: str
    ubicacion_cliente: Optional[str] = None
    detalle_producto: Optional[str] = None
    cantidad: int
    requisitos_cliente: str
    
    # Datos del Plano Principal
    id_plano: Optional[UUID] = None
    codigo_plano: Optional[str] = None
    revision: Optional[str] = None
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = None
    material_requerido: Optional[str] = None
    archivo_url: Optional[str] = None
    fecha_entrega_produccion: Optional[str] = None
    
    # Tiempos y Fechas Críticas de Entrega (ISO 9001 / SAP B1)
    fecha_compromiso: Optional[str] = None
    porcentaje_avance: Optional[float] = 0.0
    
    # Estado de Producción
    estado_produccion: str
    observaciones: Optional[str] = None
    creado_en: datetime
    
    # Productos y Piezas desglosadas en el Pedido Agrupador
    productos_componentes: List[ItemPedidoCompuesto] = []

    class Config:
        from_attributes = True


def obtener_componentes_pedido(db: Session, numero_pedido: str) -> List[ItemPedidoCompuesto]:
    """Obtiene todos los sub-productos y piezas asociadas al mismo pedido comercial."""
    if not numero_pedido:
        return []
        
    proyectos_pedido = db.query(Proyecto).filter(Proyecto.numero_pedido == numero_pedido).all()
    componentes = []
    
    for p in proyectos_pedido:
        plano = db.query(Plano).filter(Plano.id_proyecto == p.id_proyecto).first()
        op = db.query(OrdenProduccion).filter(OrdenProduccion.id_proyecto == p.id_proyecto).first()
        
        fecha_comp = str(p.fecha_compromiso) if getattr(p, 'fecha_compromiso', None) else None
        
        # Generar lista de piezas desglosadas
        piezas = []
        if plano:
            piezas.append(ItemPiezaPlano(
                codigo_plano=plano.codigo_plano,
                revision=plano.revision or "REV-01",
                detalle_pieza=p.detalle_producto or "Pieza mecanizada",
                cantidad=p.cantidad or 1,
                material_requerido=plano.material_requerido,
                archivo_url=plano.archivo_url,
                estado_diseno=plano.estado_diseno
            ))
        
        componentes.append(ItemPedidoCompuesto(
            id_proyecto=p.id_proyecto,
            codigo_op=p.codigo_proyecto,
            detalle_producto=p.detalle_producto,
            cantidad=p.cantidad or 1,
            codigo_plano=plano.codigo_plano if plano else None,
            revision=plano.revision if plano else None,
            archivo_url=plano.archivo_url if plano else None,
            estado_diseno=plano.estado_diseno if plano else "PENDIENTE",
            estado_produccion=op.estado.value if op and hasattr(op.estado, 'value') else (str(op.estado) if op else "SIN_LIBERAR"),
            porcentaje_avance=getattr(op, 'porcentaje_avance', 0.0) if op else 0.0,
            fecha_compromiso=fecha_comp,
            piezas_desglosadas=piezas
        ))
    return componentes


# --- ENDPOINTS ---

@router.get("/", response_model=List[OrdenProduccionVistaResponse])
def listar_ordenes_produccion(
    db: Session = Depends(get_db)
):
    """PM-03: Listar todas las Órdenes de Producción en Planta."""
    ordenes_db = db.query(OrdenProduccion).all()
    resultado = []

    for op_db in ordenes_db:
        proj = db.query(Proyecto).filter(Proyecto.id_proyecto == op_db.id_proyecto).first()
        plano = db.query(Plano).filter(Plano.id_plano == op_db.id_plano).first() if op_db.id_plano else (
            db.query(Plano).filter(Plano.id_proyecto == op_db.id_proyecto).first() if proj else None
        )
        
        if not proj:
            continue

        componentes = obtener_componentes_pedido(db, proj.numero_pedido) if proj.numero_pedido else []
        fecha_comp = str(proj.fecha_compromiso) if getattr(proj, 'fecha_compromiso', None) else "2026-11-15"

        resultado.append(OrdenProduccionVistaResponse(
            id_proyecto=proj.id_proyecto,
            codigo_op=op_db.codigo_op or proj.codigo_proyecto,
            numero_pedido=proj.numero_pedido or "PED-2026-088",
            cliente_nombre=proj.cliente_nombre,
            ubicacion_cliente=proj.ubicacion_cliente or "Planta Principal",
            detalle_producto=proj.detalle_producto or "Pieza Mecanizada",
            cantidad=proj.cantidad or 1,
            requisitos_cliente=proj.requisitos_cliente or "Estándar ISO 9001:2026",
            id_plano=plano.id_plano if plano else None,
            codigo_plano=plano.codigo_plano if plano else "PLN-BR-012",
            revision=plano.revision if plano else "REV-01",
            dibujante_asignado=plano.dibujante_asignado if plano else "Ing. Carlos Ruiz",
            unidad_planta=plano.unidad_planta if plano else "Mecanizados",
            material_requerido=plano.material_requerido if plano else "Acero ASTM A105",
            archivo_url=plano.archivo_url if plano else None,
            fecha_entrega_produccion=str(plano.fecha_entrega_produccion) if plano and plano.fecha_entrega_produccion else None,
            fecha_compromiso=fecha_comp,
            porcentaje_avance=getattr(op_db, 'porcentaje_avance', 0.0) or 0.0,
            estado_produccion=op_db.estado.value if hasattr(op_db.estado, 'value') else str(op_db.estado),
            observaciones=op_db.observaciones or "En proceso",
            creado_en=op_db.creado_en or proj.creado_en,
            productos_componentes=componentes
        ))

    return resultado


@router.post("/", response_model=OrdenProduccionVistaResponse, status_code=status.HTTP_201_CREATED)
def crear_orden_produccion(
    op_in: OrdenProduccionCreate,
    db: Session = Depends(get_db)
):
    """PM-03: Crear y liberar nueva Orden de Producción en Planta."""
    proj = db.query(Proyecto).filter(Proyecto.id_proyecto == op_in.id_proyecto).first()
    if not proj:
        raise HTTPException(status_code=404, detail="El proyecto/pedido comercial indicado no existe.")

    # Validar plano si viene especificado
    plano = None
    if op_in.id_plano:
        plano = db.query(Plano).filter(Plano.id_plano == op_in.id_plano).first()
    if not plano:
        plano = db.query(Plano).filter(Plano.id_proyecto == op_in.id_proyecto).first()
    validar_gate_calidad(db, plano)

    # Validar si ya existe una OP con ese código
    op_existente = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == op_in.codigo_op).first()
    if op_existente:
        raise HTTPException(status_code=400, detail=f"Ya existe una Orden de Producción con el código '{op_in.codigo_op}'.")

    nueva_op = OrdenProduccion(
        codigo_op=op_in.codigo_op,
        id_proyecto=proj.id_proyecto,
        id_plano=plano.id_plano if plano else None,
        cantidad_fabricar=op_in.cantidad_programada or proj.cantidad or 1,
        estado=EstadoOPEnum.LIBERADA_PRODUCCION,
        reserva_stock_100=True,
        observaciones=op_in.observaciones or "Liberada a planta para producción",
        porcentaje_avance=0.0
    )

    try:
        db.add(nueva_op)
        db.commit()
        db.refresh(nueva_op)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar la orden de producción: {str(e)}")

    componentes = obtener_componentes_pedido(db, proj.numero_pedido) if proj.numero_pedido else []
    fecha_comp = str(proj.fecha_compromiso) if getattr(proj, 'fecha_compromiso', None) else None

    return OrdenProduccionVistaResponse(
        id_proyecto=proj.id_proyecto,
        codigo_op=nueva_op.codigo_op,
        numero_pedido=proj.numero_pedido,
        cliente_nombre=proj.cliente_nombre,
        ubicacion_cliente=proj.ubicacion_cliente,
        detalle_producto=proj.detalle_producto,
        cantidad=nueva_op.cantidad_fabricar,
        requisitos_cliente=proj.requisitos_cliente,
        id_plano=plano.id_plano if plano else None,
        codigo_plano=plano.codigo_plano if plano else None,
        revision=plano.revision if plano else None,
        dibujante_asignado=plano.dibujante_asignado if plano else None,
        unidad_planta=plano.unidad_planta if plano else None,
        material_requerido=plano.material_requerido if plano else None,
        archivo_url=plano.archivo_url if plano else None,
        fecha_entrega_produccion=str(plano.fecha_entrega_produccion) if plano and plano.fecha_entrega_produccion else None,
        fecha_compromiso=fecha_comp,
        porcentaje_avance=0.0,
        estado_produccion=nueva_op.estado.value if hasattr(nueva_op.estado, 'value') else str(nueva_op.estado),
        observaciones=nueva_op.observaciones,
        creado_en=nueva_op.creado_en,
        productos_componentes=componentes
    )


@router.patch("/{id_proyecto}", response_model=OrdenProduccionVistaResponse)
def actualizar_estado_produccion(
    id_proyecto: UUID,
    op_up: OrdenProduccionUpdate,
    db: Session = Depends(get_db)
):
    """PM-03: Transición de estados en Planta y registro de porcentaje de avance."""
    op_db = db.query(OrdenProduccion).filter(OrdenProduccion.id_proyecto == id_proyecto).first()
    if not op_db:
        # Intento de búsqueda por id_op
        op_db = db.query(OrdenProduccion).filter(OrdenProduccion.id_op == id_proyecto).first()

    if not op_db:
        raise HTTPException(status_code=404, detail="Orden de Producción no encontrada.")

    nuevo_estado = op_up.estado or op_up.estado_produccion
    if nuevo_estado:
        try:
            estado_enum = EstadoOPEnum(nuevo_estado)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"Estado de OP no válido: {nuevo_estado}.") from error
        if estado_enum in {
            EstadoOPEnum.LISTA_PARA_LIBERAR,
            EstadoOPEnum.LIBERADA,
            EstadoOPEnum.LIBERADA_PRODUCCION,
        }:
            plano_gate = db.query(Plano).filter(Plano.id_plano == op_db.id_plano).first() if op_db.id_plano else (
                db.query(Plano).filter(Plano.id_proyecto == op_db.id_proyecto).first()
            )
            validar_gate_calidad(db, plano_gate)
        op_db.estado = estado_enum
        
    if op_up.observaciones is not None:
        op_db.observaciones = op_up.observaciones
        
    if op_up.porcentaje_avance is not None and hasattr(op_db, 'porcentaje_avance'):
        op_db.porcentaje_avance = op_up.porcentaje_avance

    try:
        db.commit()
        db.refresh(op_db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar la orden de producción: {str(e)}")

    proj = db.query(Proyecto).filter(Proyecto.id_proyecto == op_db.id_proyecto).first()
    plano = db.query(Plano).filter(Plano.id_plano == op_db.id_plano).first() if op_db.id_plano else (
        db.query(Plano).filter(Plano.id_proyecto == op_db.id_proyecto).first() if proj else None
    )
    componentes = obtener_componentes_pedido(db, proj.numero_pedido) if proj and proj.numero_pedido else []
    
    fecha_comp = str(proj.fecha_compromiso) if proj and getattr(proj, 'fecha_compromiso', None) else None

    return OrdenProduccionVistaResponse(
        id_proyecto=proj.id_proyecto if proj else op_db.id_proyecto,
        codigo_op=op_db.codigo_op or (proj.codigo_proyecto if proj else "OP-SGI"),
        numero_pedido=proj.numero_pedido if proj else "PED-SGI",
        cliente_nombre=proj.cliente_nombre if proj else "Cliente Planta",
        ubicacion_cliente=proj.ubicacion_cliente if proj else None,
        detalle_producto=proj.detalle_producto if proj else None,
        cantidad=getattr(op_db, 'cantidad_fabricar', 1) or (proj.cantidad if proj else 1),
        requisitos_cliente=proj.requisitos_cliente if proj else "Estándar ISO 9001:2026",
        id_plano=plano.id_plano if plano else None,
        codigo_plano=plano.codigo_plano if plano else None,
        revision=plano.revision if plano else None,
        dibujante_asignado=plano.dibujante_asignado if plano else None,
        unidad_planta=plano.unidad_planta if plano else None,
        material_requerido=plano.material_requerido if plano else None,
        archivo_url=plano.archivo_url if plano else None,
        fecha_entrega_produccion=str(plano.fecha_entrega_produccion) if plano and plano.fecha_entrega_produccion else None,
        fecha_compromiso=fecha_comp,
        porcentaje_avance=getattr(op_db, 'porcentaje_avance', 0.0) or 0.0,
        estado_produccion=op_db.estado.value if hasattr(op_db.estado, 'value') else str(op_db.estado),
        observaciones=op_db.observaciones,
        creado_en=op_db.creado_en,
        productos_componentes=componentes
    )