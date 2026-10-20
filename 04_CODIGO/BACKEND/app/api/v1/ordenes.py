from typing import List, Optional
from uuid import UUID
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.db.models import Proyecto, Plano, OrdenProduccion, EstadoOPEnum
from app.api.deps import obtener_usuario_actual, requerir_roles

router = APIRouter()

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
        op_db.estado = nuevo_estado
        
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