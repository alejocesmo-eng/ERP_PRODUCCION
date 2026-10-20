# app/api/v1/proyectos.py
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, Field, validator

from app.db.database import get_db
from app.db.models import Proyecto, PedidoDetalle, OTDetalle, Plano

router = APIRouter()

# =============================================================================
# SCHEMAS PYDANTIC (PM-01 VENTAS / PEDIDOS COMERCIALES)
# =============================================================================

class PedidoDetalleItem(BaseModel):
    detalle_id: Optional[UUID] = None
    codigo_producto: Optional[str] = None
    descripcion: str = Field(..., description="Nombre / Detalle de la pieza o servicio")
    tipo: Optional[str] = "pieza"
    cantidad_solicitada: int = Field(1, ge=1)
    unidad: Optional[str] = "UND"
    prioridad: Optional[str] = "MEDIA"
    fecha_compromiso: Optional[date] = None
    requisitos_especificos: Optional[str] = None
    observaciones: Optional[str] = None

    @validator('fecha_compromiso', pre=True)
    def parse_fechas_vacias(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    @validator('cantidad_solicitada', pre=True)
    def parse_cantidad(cls, v):
        if v == "" or v is None:
            return 1
        try:
            return int(v)
        except (ValueError, TypeError):
            return 1

    class Config:
        extra = "ignore"


class ProyectoCreate(BaseModel):
    numero_pedido: str = Field(..., description="N° Pedido Comercial Agrupador (ej. PED-2026-088)")
    codigo_proyecto: Optional[str] = None
    cliente_nombre: str = Field(..., description="Nombre o Razón Social del Cliente")
    contacto_nombre: Optional[str] = None
    contacto_telefono: Optional[str] = None
    contacto_email: Optional[str] = None
    ubicacion_cliente: Optional[str] = "Planta Principal"
    cantidad: Optional[int] = 1
    detalle_producto: Optional[str] = None
    requisitos_cliente: Optional[str] = Field(default="Sin especificación", description="Requisitos técnicos o normas aplicables")
    fecha_compromiso: Optional[date] = None
    detalles: Optional[List[PedidoDetalleItem]] = Field(default_factory=list)

    @validator('fecha_compromiso', pre=True)
    def parse_fechas_vacias(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    @validator('cantidad', pre=True)
    def parse_cantidad(cls, v):
        if v == "" or v is None:
            return 1
        try:
            return int(v)
        except (ValueError, TypeError):
            return 1

    class Config:
        extra = "ignore"


class ProyectoUpdate(BaseModel):
    numero_pedido: Optional[str] = None
    cliente_nombre: Optional[str] = None
    contacto_nombre: Optional[str] = None
    contacto_telefono: Optional[str] = None
    contacto_email: Optional[str] = None
    ubicacion_cliente: Optional[str] = None
    requisitos_cliente: Optional[str] = None
    fecha_compromiso: Optional[date] = None
    detalles: Optional[List[PedidoDetalleItem]] = None

    @validator('fecha_compromiso', pre=True)
    def parse_fechas_vacias(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    class Config:
        extra = "ignore"


class OTDetalleResponse(BaseModel):
    ot_detalle_id: UUID
    ot_id: UUID
    cantidad_asignada: int

    class Config:
        from_attributes = True


class PedidoDetalleResponse(BaseModel):
    detalle_id: UUID
    codigo_producto: Optional[str] = None
    descripcion: str
    tipo: str
    cantidad_solicitada: int
    unidad: str
    cantidad_asignada: int
    cantidad_pendiente: int
    estado_asignacion: Optional[str] = "SIN_ASIGNAR"
    prioridad: str
    fecha_compromiso: Optional[date] = None
    requisitos_especificos: Optional[str] = None
    observaciones: Optional[str] = None
    ot_detalles: List[OTDetalleResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ProyectoResponse(BaseModel):
    id_proyecto: UUID
    numero_pedido: str
    codigo_proyecto: str
    cliente_nombre: str
    contacto_nombre: Optional[str] = None
    contacto_telefono: Optional[str] = None
    contacto_email: Optional[str] = None
    ubicacion_cliente: Optional[str] = None
    cantidad: Optional[int] = 1
    detalle_producto: Optional[str] = None
    requisitos_cliente: Optional[str] = None
    fecha_compromiso: Optional[date] = None
    confirmado: bool
    creado_en: datetime
    detalles: List[PedidoDetalleResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


# =============================================================================
# ENDPOINTS API (PM-01)
# =============================================================================

@router.get("/", response_model=List[ProyectoResponse])
def listar_proyectos(db: Session = Depends(get_db)):
    proyectos_db = db.query(Proyecto).order_by(Proyecto.creado_en.desc()).all()
    
    for p in proyectos_db:
        num_ped = getattr(p, 'numero_pedido', None) or getattr(p, 'codigo_proyecto', 'S/P')
        p.numero_pedido = num_ped
        p.codigo_proyecto = getattr(p, 'codigo_proyecto', None) or f"PED-{num_ped}"
        
        for det in p.detalles:
            cant_sol = det.cantidad_solicitada or 0
            cant_asig = sum(rel.cantidad_asignada for rel in det.ot_detalles) if det.ot_detalles else 0
            cant_pend = cant_sol - cant_asig
            
            det.cantidad_asignada = cant_asig
            det.cantidad_pendiente = cant_pend if cant_pend >= 0 else 0
            
            if cant_asig == 0:
                det.estado_asignacion = "SIN_ASIGNAR"
            elif cant_asig < cant_sol:
                det.estado_asignacion = "PARCIALMENTE_ASIGNADA"
            else:
                det.estado_asignacion = "TOTALMENTE_ASIGNADA"
                
    return proyectos_db


@router.post("/", response_model=ProyectoResponse, status_code=status.HTTP_201_CREATED)
def crear_proyecto(proyecto_in: ProyectoCreate, db: Session = Depends(get_db)):
    codigo_ref = proyecto_in.codigo_proyecto or proyecto_in.numero_pedido or "PED-001"

    nuevo_proyecto = Proyecto(
        codigo_proyecto=codigo_ref,
        numero_pedido=proyecto_in.numero_pedido,
        cliente_nombre=proyecto_in.cliente_nombre,
        contacto_nombre=proyecto_in.contacto_nombre,
        contacto_telefono=proyecto_in.contacto_telefono,
        contacto_email=proyecto_in.contacto_email,
        ubicacion_cliente=proyecto_in.ubicacion_cliente or "Planta Principal",
        cantidad=proyecto_in.cantidad or 1,
        detalle_producto=proyecto_in.detalle_producto or "Lote de Piezas Solicitadas",
        requisitos_cliente=proyecto_in.requisitos_cliente or "Sin especificación",
        fecha_compromiso=proyecto_in.fecha_compromiso,
        confirmado=False
    )

    try:
        db.add(nuevo_proyecto)
        db.flush()

        if proyecto_in.detalles:
            for item in proyecto_in.detalles:
                detalle_db = PedidoDetalle(
                    pedido_id=nuevo_proyecto.id_proyecto,
                    codigo_producto=item.codigo_producto,
                    descripcion=item.descripcion,
                    tipo=item.tipo or "pieza",
                    cantidad_solicitada=item.cantidad_solicitada,
                    unidad=item.unidad or "UND",
                    cantidad_asignada=0,
                    cantidad_pendiente=item.cantidad_solicitada,
                    prioridad=item.prioridad or "MEDIA",
                    fecha_compromiso=item.fecha_compromiso or proyecto_in.fecha_compromiso,
                    requisitos_especificos=item.requisitos_especificos,
                    observaciones=item.observaciones
                )
                db.add(detalle_db)

        db.commit()
        db.refresh(nuevo_proyecto)
        return nuevo_proyecto
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al guardar pedido comercial en base de datos: {str(e)}"
        )


@router.patch("/{id_proyecto}", response_model=ProyectoResponse)
def actualizar_proyecto(id_proyecto: UUID, proyecto_up: ProyectoUpdate, db: Session = Depends(get_db)):
    proyecto = db.query(Proyecto).filter(Proyecto.id_proyecto == id_proyecto).first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="Pedido comercial no encontrado.")

    if proyecto.confirmado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="❌ Bloqueo ISO 9001: No se puede modificar un Pedido Comercial que ya ha sido CONFIRMADO."
        )

    datos_dict = proyecto_up.dict(exclude_unset=True, exclude={"detalles"})
    for campo, valor in datos_dict.items():
        if hasattr(proyecto, campo) and valor is not None:
            setattr(proyecto, campo, valor)

    try:
        if proyecto_up.detalles is not None:
            # Eliminación limpia con flush previa a la reinserción
            db.query(PedidoDetalle).filter(PedidoDetalle.pedido_id == id_proyecto).delete()
            db.flush()
            
            for item in proyecto_up.detalles:
                nuevo_det = PedidoDetalle(
                    pedido_id=id_proyecto,
                    codigo_producto=item.codigo_producto,
                    descripcion=item.descripcion,
                    tipo=item.tipo or "pieza",
                    cantidad_solicitada=item.cantidad_solicitada,
                    unidad=item.unidad or "UND",
                    cantidad_asignada=0,
                    cantidad_pendiente=item.cantidad_solicitada,
                    prioridad=item.prioridad or "MEDIA",
                    fecha_compromiso=item.fecha_compromiso or proyecto.fecha_compromiso,
                    requisitos_especificos=item.requisitos_especificos,
                    observaciones=item.observaciones
                )
                db.add(nuevo_det)

        if proyecto.detalles and len(proyecto.detalles) > 0:
            proyecto.detalle_producto = proyecto.detalles[0].descripcion

        db.commit()
        db.refresh(proyecto)
        return proyecto
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar pedido comercial: {str(e)}"
        )


@router.patch("/{id_proyecto}/confirmar", response_model=ProyectoResponse)
def confirmar_proyecto(id_proyecto: UUID, db: Session = Depends(get_db)):
    proyecto = db.query(Proyecto).filter(Proyecto.id_proyecto == id_proyecto).first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="Pedido comercial no encontrado.")

    try:
        proyecto.confirmado = True
        db.commit()
        db.refresh(proyecto)
        return proyecto
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al confirmar pedido: {str(e)}"
        )