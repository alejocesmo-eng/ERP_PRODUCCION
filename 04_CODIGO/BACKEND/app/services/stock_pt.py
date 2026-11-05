# app/services/stock_pt.py
"""
OT-2026-008: saldo vendible de producto terminado (PT) y picking derivado.

Disponible = max(vendible_liberado - reservado_OP - comprometido - en_picking, 0)
- vendible_liberado - reservado_OP: cálculo vigente de inventario (lotes LIBERADO acotados
  por stock_actual, menos el mayor entre stock_reservado del artículo y de los lotes).
- comprometido: suma de líneas de picking con picking PENDIENTE.
- en_picking: suma de líneas de picking con picking EN_PICKING.
Comprometido y En Picking se derivan de las tablas de picking; no se almacenan.
"""
from decimal import Decimal, ROUND_FLOOR
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    ArticuloInventario,
    CatalogoMaterialSAP,
    LoteMaterial,
    OrdenPicking,
    OrdenPickingDetalle,
    Proyecto,
)

CATEGORIA_PT = "PRODUCTO_TERMINADO"
ORIGEN_STOCK_PT = "STOCK_PT"
ORIGEN_PLANO = "PLANO"
_CUANTO = Decimal("0.001")


def _dec(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(_CUANTO)


def _entero_disponible(valor: Decimal) -> int:
    return int(max(valor, Decimal("0")).to_integral_value(rounding=ROUND_FLOOR))


def saldo_pt(db: Session, ids_articulo: Iterable) -> dict:
    """
    Devuelve {id_articulo: {fisico, comprometido, en_picking, disponible, ...}} para los
    artículos indicados. Lee el estado actual; el bloqueo de filas lo toma quien llama.
    """
    ids = list(dict.fromkeys(ids_articulo))
    if not ids:
        return {}

    articulos = (
        db.query(ArticuloInventario)
        .filter(ArticuloInventario.id_articulo.in_(ids))
        .all()
    )
    skus = [a.codigo_sku for a in articulos]

    liberado: dict = {}
    reservado_lotes: dict = {}
    if skus:
        for lote in db.query(LoteMaterial).filter(LoteMaterial.codigo_material.in_(skus)).all():
            estado = lote.estado_calidad or (
                "LIBERADO" if lote.inspeccionado_calidad else "CUARENTENA"
            )
            if estado == "LIBERADO":
                liberado[lote.codigo_material] = liberado.get(lote.codigo_material, Decimal("0")) + max(
                    _dec(lote.stock_disponible), Decimal("0")
                )
            reservado_lotes[lote.codigo_material] = reservado_lotes.get(
                lote.codigo_material, Decimal("0")
            ) + max(_dec(lote.stock_reservado), Decimal("0"))

    picking: dict = {}
    filas = (
        db.query(
            OrdenPickingDetalle.id_articulo,
            OrdenPicking.estado,
            func.coalesce(func.sum(OrdenPickingDetalle.cantidad), 0),
        )
        .join(OrdenPicking, OrdenPicking.id_picking == OrdenPickingDetalle.id_picking)
        .filter(
            OrdenPickingDetalle.id_articulo.in_(ids),
            OrdenPicking.estado.in_(["PENDIENTE", "EN_PICKING"]),
        )
        .group_by(OrdenPickingDetalle.id_articulo, OrdenPicking.estado)
        .all()
    )
    for id_art, estado, total in filas:
        picking.setdefault(id_art, {})[estado] = _dec(total)

    precios: dict = {}
    for cat in db.query(CatalogoMaterialSAP).filter(CatalogoMaterialSAP.id_articulo.in_(ids)).all():
        precios[cat.id_articulo] = cat.precio_unitario_valorado

    resultado = {}
    for art in articulos:
        fisico = max(_dec(art.stock_actual), Decimal("0"))
        vendible = min(liberado.get(art.codigo_sku, Decimal("0")), fisico)
        reservado_op = max(_dec(art.stock_reservado), reservado_lotes.get(art.codigo_sku, Decimal("0")))
        comprometido = picking.get(art.id_articulo, {}).get("PENDIENTE", Decimal("0"))
        en_picking = picking.get(art.id_articulo, {}).get("EN_PICKING", Decimal("0"))
        disponible = _entero_disponible(vendible - reservado_op - comprometido - en_picking)
        precio = precios.get(art.id_articulo)
        resultado[art.id_articulo] = {
            "articulo": art,
            "stock_fisico": float(fisico),
            "stock_comprometido": float(comprometido),
            "stock_en_picking": float(en_picking),
            "stock_disponible": disponible,
            "precio_unitario_valorado": float(precio if precio is not None else (art.costo_unitario or 0)),
        }
    return resultado


def _error_400(detail) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def validar_lineas_stock(db: Session, lineas: Iterable, bloquear: bool = False) -> dict:
    """
    Valida las líneas con origen STOCK_PT (objetos con origen, id_articulo y
    cantidad_solicitada). Agrupa por artículo y compara la suma con el disponible.
    Si bloquear=True toma FOR UPDATE de los artículos en orden fijo por id_articulo.
    Devuelve {id_articulo: ArticuloInventario} para que quien llama sobrescriba SKU,
    descripción y unidad desde la base. Lanza HTTP 400 si no cumple.
    """
    lineas_stock = [
        l for l in lineas if (getattr(l, "origen", None) or ORIGEN_PLANO) == ORIGEN_STOCK_PT
    ]
    if not lineas_stock:
        return {}

    pedido_por_articulo: dict = {}
    for linea in lineas_stock:
        if linea.id_articulo is None:
            raise _error_400("La línea de stock PT requiere id_articulo.")
        cantidad = linea.cantidad_solicitada
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad < 1:
            raise _error_400("La cantidad de una línea de stock PT debe ser un entero mayor o igual a 1.")
        pedido_por_articulo[linea.id_articulo] = pedido_por_articulo.get(linea.id_articulo, 0) + cantidad

    ids_ordenados = sorted(pedido_por_articulo, key=lambda x: str(x))
    consulta = db.query(ArticuloInventario).filter(ArticuloInventario.id_articulo.in_(ids_ordenados))
    if bloquear:
        consulta = consulta.order_by(ArticuloInventario.id_articulo).with_for_update()
    articulos = {a.id_articulo: a for a in consulta.all()}

    for id_art in ids_ordenados:
        art = articulos.get(id_art)
        if art is None:
            raise _error_400("El artículo de stock PT indicado no existe.")
        if art.categoria != CATEGORIA_PT:
            raise _error_400(f"El artículo {art.codigo_sku} no es producto terminado y no puede cargarse desde stock PT.")

    saldos = saldo_pt(db, ids_ordenados)
    for id_art in ids_ordenados:
        disponible = saldos[id_art]["stock_disponible"]
        if pedido_por_articulo[id_art] > disponible:
            art = articulos[id_art]
            unidad = art.unidad_medida or "UND"
            raise _error_400({
                "codigo": "STOCK_INSUFICIENTE",
                "sku": art.codigo_sku,
                "disponible": disponible,
                "unidad": unidad,
                "mensaje": f"Cantidad excede el saldo vendible real (Disponible: {disponible} {unidad.lower()})",
            })
    return articulos


def _siguiente_codigo_picking(db: Session, anio: int) -> str:
    prefijo = f"PCK-{anio}-"
    ultimos = [
        c for (c,) in db.query(OrdenPicking.codigo_picking)
        .filter(OrdenPicking.codigo_picking.like(f"{prefijo}%"))
        .all()
    ]
    mayor = 0
    for codigo in ultimos:
        try:
            mayor = max(mayor, int(codigo.rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return f"{prefijo}{mayor + 1:04d}"


def crear_picking_para_pedido(
    db: Session,
    proyecto: Proyecto,
    lineas_stock: list,
    usuario: Optional[str] = None,
    anio: Optional[int] = None,
) -> OrdenPicking:
    """
    Crea la orden de picking (estado PENDIENTE) con las líneas STOCK_PT del pedido y marca
    esas líneas como asignadas. No hace commit: lo controla confirmar_proyecto.
    """
    from datetime import date

    picking = OrdenPicking(
        codigo_picking=_siguiente_codigo_picking(db, anio or date.today().year),
        id_proyecto=proyecto.id_proyecto,
        estado="PENDIENTE",
        creado_por=usuario,
    )
    db.add(picking)
    db.flush()
    for linea in lineas_stock:
        db.add(OrdenPickingDetalle(
            id_picking=picking.id_picking,
            detalle_pedido_id=linea.detalle_id,
            id_articulo=linea.id_articulo,
            cantidad=Decimal(linea.cantidad_solicitada),
        ))
        linea.cantidad_asignada = linea.cantidad_solicitada
        linea.cantidad_pendiente = 0
    db.flush()
    return picking
