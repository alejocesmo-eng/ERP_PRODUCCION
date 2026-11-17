# app/api/v1/busqueda.py
"""
Búsqueda general de PRISMA por código o nombre (reglas/permisos-por-rol-modulo.md, "Búsqueda y
expediente"). Cada rol encuentra solo los tipos de dato de TIPOS_BUSQUEDA_POR_ROL; los demás
tipos no se consultan ni aparecen (sin "Acceso denegado"). El rol se lee de la base en cada
consulta. El valor cotizado solo sale con PERM_VALOR_COTIZADO_VER. El líder de una unidad solo
encuentra las OP que están en ella (app/services/unidad_op.py).

Las relaciones entre resultados (OP -> pedido -> cotización) quedan para una segunda etapa.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual
from app.core import roles
from app.db.database import get_db
from app.db.models import Cotizacion, OrdenProduccion, Producto, Proyecto, SocioNegocio
from app.services import unidad_op
from app.services.acceso_bd import PERMISO_COSTOS, PERMISO_VALOR_COTIZADO, puede, rol_en_bd

router = APIRouter()

LONGITUD_MINIMA = 2
MAXIMO_POR_TIPO = 10


def _alcance(db: Session, rol: str | None) -> dict:
    return {
        "tipos": list(roles.TIPOS_BUSQUEDA_POR_ROL.get(rol, [])),
        "expediente_op": rol in roles.ROLES_EXPEDIENTE_OP,
        "costos": puede(db, rol, PERMISO_COSTOS),
        "valor_cotizado": puede(db, rol, PERMISO_VALOR_COTIZADO),
    }


def _contiene(texto: str, *columnas):
    patron = f"%{texto.lower()}%"
    return or_(*(func.lower(columna).like(patron) for columna in columnas))


def _valor(valor):
    return valor.value if hasattr(valor, "value") else valor


def _cotizaciones(db: Session, texto: str, valor_cotizado: bool) -> list[dict]:
    filas = (
        db.query(Cotizacion, SocioNegocio.razon_social)
        .outerjoin(SocioNegocio, SocioNegocio.id_socio == Cotizacion.id_socio)
        .filter(_contiene(texto, Cotizacion.numero_cotizacion, SocioNegocio.razon_social, Cotizacion.referencia))
        .order_by(Cotizacion.numero_cotizacion).limit(MAXIMO_POR_TIPO).all()
    )
    return [{
        "tipo": roles.BUSQUEDA_COTIZACION,
        "codigo": cot.numero_cotizacion,
        "nombre": razon_social or "",
        "estado": _valor(cot.estado),
        **({"valor_cotizado": float(cot.valor_total or 0), "moneda": cot.moneda or "COP"} if valor_cotizado else {}),
    } for cot, razon_social in filas]


def _pedidos(db: Session, texto: str, valor_cotizado: bool) -> list[dict]:
    filas = (
        db.query(Proyecto)
        .filter(_contiene(texto, Proyecto.numero_pedido, Proyecto.cliente_nombre, Proyecto.detalle_producto))
        .order_by(Proyecto.numero_pedido).limit(MAXIMO_POR_TIPO).all()
    )
    return [{
        "tipo": roles.BUSQUEDA_PEDIDO,
        "codigo": pedido.numero_pedido,
        "nombre": pedido.cliente_nombre or "",
        "estado": "CONFIRMADO" if pedido.confirmado else "EN_GESTION",
        **({"valor_cotizado": float(pedido.cotizacion_total) if pedido.cotizacion_total is not None else None}
           if valor_cotizado else {}),
    } for pedido in filas]


def _ordenes(db: Session, texto: str, rol: str | None) -> list[dict]:
    filas = (
        unidad_op.filtrar_op_visibles(db.query(OrdenProduccion, Producto.descripcion), rol)
        .outerjoin(Producto, Producto.id_producto == OrdenProduccion.id_producto)
        .filter(_contiene(texto, OrdenProduccion.codigo_op, Producto.descripcion, Producto.codigo_rn))
        .order_by(OrdenProduccion.codigo_op).limit(MAXIMO_POR_TIPO).all()
    )
    return [{
        "tipo": roles.BUSQUEDA_OP,
        "codigo": op.codigo_op,
        "nombre": descripcion or "",
        "estado": _valor(op.estado),
    } for op, descripcion in filas]


def _clientes(db: Session, texto: str) -> list[dict]:
    filas = (
        db.query(SocioNegocio)
        .filter(SocioNegocio.es_cliente.is_(True))
        .filter(_contiene(texto, SocioNegocio.codigo_socio, SocioNegocio.nit_cedula, SocioNegocio.razon_social))
        .order_by(SocioNegocio.razon_social).limit(MAXIMO_POR_TIPO).all()
    )
    return [{
        "tipo": roles.BUSQUEDA_CLIENTE,
        "codigo": socio.nit_cedula,
        "nombre": socio.razon_social,
        "estado": "ACTIVO" if socio.estado_activo else "INACTIVO",
    } for socio in filas]


def _productos(db: Session, texto: str) -> list[dict]:
    filas = (
        db.query(Producto)
        .filter(_contiene(texto, Producto.codigo_rn, Producto.codigo_anterior, Producto.descripcion))
        .order_by(Producto.codigo_rn).limit(MAXIMO_POR_TIPO).all()
    )
    return [{
        "tipo": roles.BUSQUEDA_PRODUCTO,
        "codigo": producto.codigo_rn,
        "nombre": producto.descripcion,
        "estado": producto.estado,
    } for producto in filas]


@router.get("/alcance")
def alcance_busqueda(db: Session = Depends(get_db), usuario: dict = Depends(obtener_usuario_actual)):
    """Qué tipos encuentra el rol y si abre el expediente de OP; sin tipos, la caja no se muestra."""
    return _alcance(db, rol_en_bd(db, usuario["id_usuario"]))


@router.get("/")
def buscar(
    q: str = Query(..., max_length=100),
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    rol = rol_en_bd(db, usuario["id_usuario"])
    alcance = _alcance(db, rol)
    texto = q.strip()
    if len(texto) < LONGITUD_MINIMA or not alcance["tipos"]:
        return {"resultados": [], **alcance}

    tipos = set(alcance["tipos"])
    resultados = []
    if roles.BUSQUEDA_COTIZACION in tipos:
        resultados += _cotizaciones(db, texto, alcance["valor_cotizado"])
    if roles.BUSQUEDA_PEDIDO in tipos:
        resultados += _pedidos(db, texto, alcance["valor_cotizado"])
    if roles.BUSQUEDA_OP in tipos:
        resultados += _ordenes(db, texto, rol)
    if roles.BUSQUEDA_CLIENTE in tipos:
        resultados += _clientes(db, texto)
    if roles.BUSQUEDA_PRODUCTO in tipos:
        resultados += _productos(db, texto)
    return {"resultados": resultados, **alcance}
