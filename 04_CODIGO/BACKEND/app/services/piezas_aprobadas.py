"""
Piezas aprobadas por Calidad (35_MIGRACION_CANTIDAD_APROBADA_CALIDAD.sql).

Cada inspección APROBADO_DESPACHO registra cuántas piezas aprobó (una INDIVIDUAL o un LOTE). Las
piezas terminadas de una OP son la suma de esas cantidades; la OP queda terminada cuando la suma
iguala su cantidad.
"""
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models_calidad import InspeccionCalidad

TIPOS_APROBACION = ("INDIVIDUAL", "LOTE")
DICTAMEN_DESPACHO = "APROBADO_DESPACHO"


def validar_aprobacion(resultado: str, cantidad: int, tipo: Optional[str]) -> None:
    """Reglas de la cantidad aprobada (las mismas que el CHECK de la migración 35):
    - APROBADO_DESPACHO: con tipo INDIVIDUAL o LOTE, al menos una pieza, e INDIVIDUAL exactamente una.
    - Tratamiento o rechazo: sin piezas ni tipo."""
    if resultado == DICTAMEN_DESPACHO:
        if tipo not in TIPOS_APROBACION:
            raise HTTPException(status_code=422, detail="Indique si aprueba una pieza (INDIVIDUAL) o un lote (LOTE).")
        if cantidad < 1:
            raise HTTPException(status_code=422, detail="Indique cuántas piezas aprueba.")
        if tipo == "INDIVIDUAL" and cantidad != 1:
            raise HTTPException(status_code=422, detail="Una aprobación individual aprueba una sola pieza.")
    elif cantidad or tipo:
        raise HTTPException(status_code=422, detail="Solo la aprobación para despacho registra piezas aprobadas.")


def piezas_aprobadas_por_op(db: Session, codigos_op: Iterable[str]) -> dict:
    """{codigo_op: piezas aprobadas por Calidad}; las OP sin aprobaciones no aparecen."""
    codigos = [codigo for codigo in set(codigos_op) if codigo]
    if not codigos:
        return {}
    filas = (
        db.query(InspeccionCalidad.codigo_op, func.coalesce(func.sum(InspeccionCalidad.cantidad_aprobada), 0))
        .filter(InspeccionCalidad.codigo_op.in_(codigos)).group_by(InspeccionCalidad.codigo_op).all()
    )
    return {codigo: int(total or 0) for codigo, total in filas}


def piezas_aprobadas(db: Session, codigo_op: str) -> int:
    return piezas_aprobadas_por_op(db, [codigo_op]).get(codigo_op, 0)
