import os
from typing import List, Optional
from uuid import UUID
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import get_db
from app.db.models import (
    Cotizacion,
    PosicionCotizacion,
    Proyecto,
    PedidoDetalle,
    OTDetalle,
    Plano,
    OrdenProduccion,
    SocioNegocio,
    EstadoOPEnum,
    EstadoCotizacionEnum
)
from app.db.models_rea import EvaluacionRea, EstadoEvaluacionReaEnum

router = APIRouter()

# =============================================================================
# SCHEMAS PYDANTIC
# =============================================================================

from pydantic import BaseModel, Field

class PosicionCotizacionCreate(BaseModel):
    numero_producto: Optional[str] = None
    descripcion: str
    cantidad: int = Field(1, ge=1)
    precio_unitario: float = Field(0, ge=0)
    descuento_pct: float = Field(0, ge=0, le=100)
    unidad: str = "UND"
    vinculo_plano_catalogo: Optional[str] = None

class CotizacionCreate(BaseModel):
    id_socio: UUID
    codigo_cliente: str
    numero_cotizacion: str
    fecha_emision: Optional[date] = None
    fecha_vigencia: Optional[date] = None
    condiciones_pago: Optional[str] = None
    condiciones_comerciales: Optional[str] = None
    impuesto_pct: float = Field(19.0, ge=0)
    posiciones: List[PosicionCotizacionCreate]
    viabilidad_tecnica: bool = False

    @property
    def calcular_total(self) -> float:
        subtotal = sum(
            (p.cantidad * p.precio_unitario * (1 - p.descuento_pct / 100))
            for p in self.posiciones
        )
        return round(subtotal * (1 + self.impuesto_pct / 100), 2)

class CotizacionResponse(BaseModel):
    id_cotizacion: UUID
    numero_cotizacion: str
    estado: EstadoCotizacionEnum
    valor_total: float
    fecha_emision: date
    id_socio: UUID
    codigo_cliente: Optional[str] = None

    class Config:
        from_attributes = True

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/cotizaciones/", response_model=CotizacionResponse, status_code=status.HTTP_201_CREATED)
def crear_cotizacion(cotizacion_in: CotizacionCreate, db: Session = Depends(get_db)):
    try:
        total_calculado = cotizacion_in.calcular_total

        nueva_cot = Cotizacion(
            id_socio=cotizacion_in.id_socio,
            numero_cotizacion=cotizacion_in.numero_cotizacion,
            fecha_emision=cotizacion_in.fecha_emision or date.today(),
            fecha_vigencia=cotizacion_in.fecha_vigencia,
            valor_total=total_calculado,
            condiciones_comerciales=f"Impuesto: {cotizacion_in.impuesto_pct}% | Pago: {cotizacion_in.condiciones_pago} | {cotizacion_in.condiciones_comerciales or ''}",
            estado=EstadoCotizacionEnum.BORRADOR
        )
        db.add(nueva_cot)
        db.flush()

        for pos in cotizacion_in.posiciones:
            nueva_pos = PosicionCotizacion(
                id_cotizacion=nueva_cot.id_cotizacion,
                numero_producto=pos.numero_producto,
                descripcion=pos.descripcion,
                cantidad=pos.cantidad,
                precio_unitario=pos.precio_unitario,
                vinculo_plano_catalogo=pos.vinculo_plano_catalogo
            )
            db.add(nueva_pos)

        db.commit()
        db.refresh(nueva_cot)
        return nueva_cot
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error al crear cotización: {str(e)}")

@router.patch("/cotizaciones/{id_cotizacion}/aprobar-y-generar-pedido")
def aprobar_cotizacion_y_generar_pedido(id_cotizacion: UUID, db: Session = Depends(get_db)):
    """
    Aprobación de Cotización -> Generación de Pedido Comercial -> Disparador de OPs.
    Sujeto a Quality Gate: Evaluación REA debe estar APROBADA.
    """
    cot = db.query(Cotizacion).filter(Cotizacion.id_cotizacion == id_cotizacion).first()
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada.")

    # --- QUALITY GATE: VERIFICACIÓN REA ---
    rea = db.query(EvaluacionRea).filter(EvaluacionRea.id_cotizacion == id_cotizacion).first()
    if not rea or rea.estado != EstadoEvaluacionReaEnum.APROBADO:
        estado_actual = rea.estado if rea else "NO REALIZADA"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Bloqueo de calidad: La evaluación REA está en estado [{estado_actual}]. Debe estar APROBADA para generar el pedido."
        )
    # --------------------------------------

    try:
        # 1. Aprobar Cotización
        cot.estado = EstadoCotizacionEnum.APROBADA

        # 2. Crear Pedido Comercial (Proyecto)
        socio = db.query(SocioNegocio).filter(SocioNegocio.id_socio == cot.id_socio).first()

        nuevo_pedido = Proyecto(
            numero_pedido=f"PED-COT-{cot.numero_cotizacion}",
            codigo_proyecto=f"PROJ-COT-{cot.numero_cotizacion}",
            cliente_nombre=socio.razon_social if socio else "Cliente no registrado",
            contacto_nombre=socio.email if socio else None,
            ubicacion_cliente=socio.direccion if socio else None,
            cantidad=sum(p.cantidad for p in cot.posiciones),
            detalle_producto=f"Pedido derivado de Cotización {cot.numero_cotizacion}",
            requisitos_cliente=cot.condiciones_comerciales or "Según cotización aprobada",
            fecha_compromiso=cot.fecha_vigencia,
            cotizacion_total=cot.valor_total,
            confirmado=True,
        )
        db.add(nuevo_pedido)
        db.flush()

        # 3. Crear Posiciones del Pedido y Disparar OPs
        for pos_cot in cot.posiciones:
            detalle_pedido = PedidoDetalle(
                pedido_id=nuevo_pedido.id_proyecto,
                codigo_producto=pos_cot.numero_producto,
                descripcion=pos_cot.descripcion,
                cantidad_solicitada=pos_cot.cantidad,
                unidad="UND",
                cantidad_pendiente=pos_cot.cantidad,
                prioridad="MEDIA"
            )
            db.add(detalle_pedido)
            db.flush()

            # Disparador de Orden de Producción
            op_codigo = f"OP-COT-{cot.numero_cotizacion}-{pos_cot.id_posicion.hex[:4].upper()}"

            # Crear el Plano (OT) primero para vincular la OP
            nuevo_plano = Plano(
                id_proyecto=nuevo_pedido.id_proyecto,
                codigo_op=op_codigo,
                codigo_plano=pos_cot.vinculo_plano_catalogo or f"PLN-COT-{pos_cot.id_posicion.hex[:4].upper()}",
                version="V-01",
                estado_diseno="ASIGNADA",
                material_requerido=pos_cot.numero_producto,
                fecha_entrega_produccion=cot.fecha_vigencia
            )
            db.add(nuevo_plano)
            db.flush()

            # Crear la Orden de Producción
            nueva_op = OrdenProduccion(
                id_proyecto=nuevo_pedido.id_proyecto,
                id_plano=nuevo_plano.id_plano,
                codigo_op=op_codigo,
                cantidad_fabricar=pos_cot.cantidad,
                estado=EstadoOPEnum.BORRADOR,
                observaciones=f"Generada automáticamente desde Cotización {cot.numero_cotizacion}"
            )
            db.add(nueva_op)

            # Vincular PedidoDetalle con Plano (OTDetalle)
            vinculo = OTDetalle(
                detalle_pedido_id=detalle_pedido.detalle_id,
                ot_id=nuevo_plano.id_plano,
                cantidad_asignada=pos_cot.cantidad
            )
            db.add(vinculo)

        db.commit()
        return {"mensaje": "Cotización aprobada y Pedido Comercial generado con sus OPs", "pedido_id": nuevo_pedido.id_proyecto}

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en el flujo de conversión: {str(e)}")