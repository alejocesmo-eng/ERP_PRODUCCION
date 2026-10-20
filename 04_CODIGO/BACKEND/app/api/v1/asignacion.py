# 04_CODIGO/BACKEND/app/services/asignacion.py
"""
Lógica única de cantidades y estados (PDF puntos 4, 5 y 6).
La usan proyectos.py y planos.py para que ambos calculen igual.

SUPUESTO: OTDetalle tiene (ot_detalle_id, ot_id, detalle_id, cantidad_asignada)
y ot_id apunta a Plano.id_plano (hoy Plano hace de OT).
"""
from typing import Dict, Iterable, Tuple
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import OTDetalle, Plano

ESTADO_OT_ANULADA = "ANULADA"

# Estados del Pedido que hoy se pueden calcular con los datos existentes.
# (EN_PRODUCCION ... CERRADO dependen de Producción/Calidad/Entregas, aún no integrados.)
ESTADOS_PEDIDO_CERRADOS = {"ENTREGADO", "CERRADO", "CANCELADO"}


def _ot_activa():
    return or_(Plano.estado_diseno.is_(None), Plano.estado_diseno != ESTADO_OT_ANULADA)


def cantidades_asignadas(db: Session, detalle_ids: Iterable[UUID]) -> Dict[UUID, int]:
    """Suma lo asignado por línea, ignorando OTs ANULADAS (anular libera cantidad)."""
    ids = list(detalle_ids)
    if not ids:
        return {}
    filas = (
        db.query(OTDetalle.detalle_id, func.coalesce(func.sum(OTDetalle.cantidad_asignada), 0))
        .join(Plano, Plano.id_plano == OTDetalle.ot_id)
        .filter(OTDetalle.detalle_id.in_(ids))
        .filter(_ot_activa())
        .group_by(OTDetalle.detalle_id)
        .all()
    )
    return {detalle_id: int(total) for detalle_id, total in filas}


def estado_asignacion_linea(solicitada: int, asignada: int) -> str:
    if asignada <= 0:
        return "SIN_ASIGNAR"
    if asignada < solicitada:
        return "PARCIALMENTE_ASIGNADA"
    return "TOTALMENTE_ASIGNADA"


def estado_pedido(confirmado: bool, lineas: Iterable[Tuple[int, int]]) -> str:
    """
    lineas = [(solicitada, asignada), ...]
    RECIBIDO              -> aún no confirmado
    EN_ESTRUCTURACION     -> confirmado, sin nada asignado a OT
    PARCIALMENTE_ASIGNADO -> alguna línea con pendiente
    ASIGNADO              -> todas las líneas cubiertas
    """
    lineas = list(lineas)
    total_asig = sum(a for _, a in lineas)
    if total_asig == 0:
        return "EN_ESTRUCTURACION" if confirmado else "RECIBIDO"
    if all(a >= s for s, a in lineas):
        return "ASIGNADO"
    return "PARCIALMENTE_ASIGNADO"
