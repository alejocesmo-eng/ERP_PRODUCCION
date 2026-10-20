from typing import List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import OrdenProduccion

router = APIRouter()

# --- ENUMS ---
class TipoDestinoEnum(str, Enum):
    ORDEN_PRODUCCION = "ORDEN_PRODUCCION"
    CENTRO_COSTOS = "CENTRO_COSTOS"
    ASIGNACION_OPERARIO = "ASIGNACION_OPERARIO"
    PRESTAMO_TEMPORAL = "PRESTAMO_TEMPORAL"

class TipoArticuloEnum(str, Enum):
    MATERIA_PRIMA = "MATERIA_PRIMA"
    CONSUMIBLE = "CONSUMIBLE"
    EPP = "EPP"
    REPUESTO = "REPUESTO"
    HERRAMENTAL = "HERRAMENTAL"
    OFICINA = "OFICINA"

# --- SCHEMAS ---
class EntradaConFacturaCreate(BaseModel):
    numero_solicitud_compra: str
    codigo_sku: str
    cantidad_solicitada: float
    cantidad_recibida: float
    numero_factura: str
    factura_digital_url: Optional[str] = None
    numero_lote: Optional[str] = None
    recibido_por: Optional[str] = "Almacén Central"
    id_solicitud: Optional[str] = None
    nombre_item: Optional[str] = None
    categoria: Optional[str] = "MATERIA_PRIMA"
    codigo_op: Optional[str] = None
    codigo_plano: Optional[str] = None
    numero_pedido: Optional[str] = None

class SalidaAlmacenCreate(BaseModel):
    codigo_sku: str
    cantidad_salida: float
    tipo_destino: TipoDestinoEnum
    id_op: Optional[UUID] = None
    centro_costos: Optional[str] = None  # Ej: "Planta Mecanizados", "Mantenimiento"
    operario_responsable: Optional[str] = None
    fecha_devolucion_estimada: Optional[str] = None # Para herramientas de préstamo
    observaciones: Optional[str] = None

# --- ENDPOINTS ---

@router.post("/recepcion-compra", status_code=status.HTTP_201_CREATED)
def registrar_recepcion_compra(
    entrada: EntradaConFacturaCreate,
    db: Session = Depends(get_db)
):
    """
    Entrada de Mercancía: Recibe con Número de Solicitud de Compras, 
    compara cantidades recibidas vs solicitadas y adjunta factura digital.
    """
    discrepancia = entrada.cantidad_recibida != entrada.cantidad_solicitada
    estado_revision = "CONCILIADO" if not discrepancia else "DISCREPANCIA_CANTIDAD"

    return {
        "status": "exito",
        "mensaje": f"📦 Recepción [{entrada.numero_solicitud_compra}] procesada con estado: {estado_revision}.",
        "discrepancia_detectada": discrepancia,
        "estado_revision": estado_revision,
        "entrada": entrada
    }

@router.post("/salidas", status_code=status.HTTP_201_CREATED)
def registrar_salida_almacen(
    salida: SalidaAlmacenCreate,
    db: Session = Depends(get_db)
):
    """
    Registra salidas de inventario asignando a OP, Centro de Costos o Préstamo/Asignación de herramientas.
    """
    if salida.tipo_destino == TipoDestinoEnum.ORDEN_PRODUCCION and not salida.id_op:
        raise HTTPException(
            status_code=400, 
            detail="Para salidas a Órdenes de Producción se exige seleccionar el ID de la OP."
        )

    return {
        "status": "exito",
        "mensaje": f"📤 Salida de {salida.cantidad_salida} unidades del SKU [{salida.codigo_sku}] registrada exitosamente.",
        "detalle_salida": salida
    }