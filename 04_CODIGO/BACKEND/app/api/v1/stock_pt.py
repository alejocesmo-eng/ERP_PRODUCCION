# app/api/v1/stock_pt.py
"""OT-2026-008: catálogo de solo lectura de stock de producto terminado para Ventas."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import requerir_roles
from app.core.roles import ROLES_STOCK_PT
from app.db.database import get_db
from app.db.models import ArticuloInventario
from app.services.stock_pt import CATEGORIA_PT, saldo_pt

router = APIRouter(prefix="/ventas/stock-pt", tags=["Ventas / Stock PT"])


class StockPTItem(BaseModel):
    id_articulo: UUID
    codigo_sku: str
    nombre: str
    unidad_medida: Optional[str] = None
    ubicacion: Optional[str] = None
    stock_fisico: float
    stock_comprometido: float
    stock_en_picking: float
    stock_disponible: int
    precio_unitario_valorado: float


class StockPTListado(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[StockPTItem]


def _filtro_texto(q: str):
    patron = f"%{q.strip()}%"
    return or_(
        ArticuloInventario.codigo_sku.ilike(patron),
        ArticuloInventario.nombre.ilike(patron),
        ArticuloInventario.ubicacion.ilike(patron),
    )


@router.get("", response_model=StockPTListado)
def listar_stock_pt(
    q: Optional[str] = Query(default=None, max_length=100),
    solo_con_saldo: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _usuario: dict = Depends(requerir_roles(ROLES_STOCK_PT)),
):
    """Solo ítems con categoría PRODUCTO_TERMINADO (filtro fijo). No reserva ni modifica saldos."""
    consulta = db.query(ArticuloInventario).filter(ArticuloInventario.categoria == CATEGORIA_PT)
    if q and q.strip():
        consulta = consulta.filter(_filtro_texto(q))
    consulta = consulta.order_by(ArticuloInventario.codigo_sku)

    # El saldo es derivado (lotes, reservas y picking): se calcula sobre los candidatos
    # y la paginación se aplica en el servidor sobre el resultado filtrado.
    candidatos = consulta.all()
    saldos = saldo_pt(db, [a.id_articulo for a in candidatos])
    filas = []
    for art in candidatos:
        s = saldos[art.id_articulo]
        if solo_con_saldo and s["stock_disponible"] <= 0:
            continue
        filas.append(StockPTItem(
            id_articulo=art.id_articulo,
            codigo_sku=art.codigo_sku,
            nombre=art.nombre,
            unidad_medida=art.unidad_medida,
            ubicacion=art.ubicacion,
            stock_fisico=s["stock_fisico"],
            stock_comprometido=s["stock_comprometido"],
            stock_en_picking=s["stock_en_picking"],
            stock_disponible=s["stock_disponible"],
            precio_unitario_valorado=s["precio_unitario_valorado"],
        ))
    return StockPTListado(total=len(filas), limit=limit, offset=offset, items=filas[offset:offset + limit])
