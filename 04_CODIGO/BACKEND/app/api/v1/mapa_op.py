# app/api/v1/mapa_op.py
"""
Mapa de la OP en el modal de expediente (tabla de nodos por rol de Alejo, 2026-11-17;
reglas/mapa-relaciones-op.md del proyecto PRISMA).

- Mapa de relaciones: la OP en el centro y los nodos que el rol ve (roles.ROLES_MAPA_*): pedido,
  cotización (el valor solo con PERM_VALOR_COTIZADO_VER), cliente, otras OP del mismo pedido,
  planos vigentes y recibos de producción (entregas de material a la OP e ingresos a stock PT).
  Las órdenes de compra quedan fuera hasta que exista su modelo.
- Mapa de procesos: cada operación de la ruta de la OP en orden, con máquinas, operarios y minutos
  de operación y setup. Los minutos solo para COSTOS y JEFE_PRODUCCION (roles.ROLES_COSTOS_TIEMPOS).
- Los de producción abren por defecto el de procesos; los demás, el de relaciones. El mapa vive en
  el expediente de OP: un rol fuera de ROLES_EXPEDIENTE_OP (VENTAS, que no ve números de OP, u
  OPERARIO) o sin ningún mapa recibe 403. Los líderes de unidad, solo las OP que ven.
- El rol se lee de la base y los nodos se filtran aquí en cada petición: la interfaz dibuja lo que
  recibe.
"""
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual
from app.api.v1.ordenes import _ops_del_pedido
from app.api.v1.quality_gate import planos_vigentes_de_producto
from app.core import roles
from app.db.database import get_db
from app.db.models import (
    ArticuloInventario, Cotizacion, EntregaMaterialOP, LoteMaterial, MovimientoInventario, OrdenProduccion,
    Proyecto, RegistroTiemposProduccion,
)
from app.db.models_produccion import OperacionOT, RegistroTiempoOperario, SubLoteOperacion
from app.services import unidad_op
from app.services.acceso_bd import PERMISO_VALOR_COTIZADO, puede, rol_en_bd
from app.services.stock_pt import CATEGORIA_PT
from app.services.usuarios import etiquetas_usuarios, mostrar

router = APIRouter()

RELACIONES = "relaciones"
PROCESOS = "procesos"


def _valor(enum_o_texto):
    return getattr(enum_o_texto, "value", enum_o_texto)


def _fecha(valor):
    return valor.isoformat() if valor else None


def _minutos(segundos) -> float:
    return round((segundos or 0) / 60, 2)


def mapas_del_rol(rol: Optional[str]) -> list[str]:
    if rol not in roles.ROLES_EXPEDIENTE_OP:
        return []
    grupos_relaciones = (
        roles.ROLES_MAPA_PEDIDO, roles.ROLES_MAPA_COTIZACION, roles.ROLES_MAPA_CLIENTE, roles.ROLES_MAPA_OTRAS_OP,
        roles.ROLES_MAPA_PLANOS, roles.ROLES_MAPA_RECIBOS,
    )
    mapas = []
    if any(rol in grupo for grupo in grupos_relaciones):
        mapas.append(RELACIONES)
    if rol in roles.ROLES_MAPA_PROCESOS:
        mapas.append(PROCESOS)
    return mapas


def _cotizacion_del_pedido(db: Session, pedido: Proyecto) -> Optional[Cotizacion]:
    """La cotización de origen: un pedido nacido de una cotización tiene cotizacion_total y su número
    es PED-<número de la cotización sin COT->."""
    if pedido.cotizacion_total is None or not (pedido.numero_pedido or "").startswith("PED-"):
        return None
    numero = "COT-" + pedido.numero_pedido[len("PED-"):]
    return db.query(Cotizacion).filter(Cotizacion.numero_cotizacion == numero).first()


def _relaciones(db: Session, op: OrdenProduccion, rol: Optional[str]) -> dict:
    nodos = [{"id": "op", "tipo": "OP", "etiqueta": op.codigo_op, "datos": {"estado": _valor(op.estado)}}]
    aristas = []

    def agregar(nodo: dict, desde: str = "op") -> None:
        nodos.append(nodo)
        aristas.append({"desde": desde, "hasta": nodo["id"]})

    pedido = db.query(Proyecto).filter(Proyecto.id_proyecto == op.id_proyecto).first()
    origen_pedido = "op"
    if pedido and rol in roles.ROLES_MAPA_PEDIDO:
        agregar({"id": "pedido", "tipo": "PEDIDO", "etiqueta": pedido.numero_pedido, "datos": {
            "estado": "CONFIRMADO" if pedido.confirmado else "EN_GESTION",
            "fecha_compromiso": _fecha(pedido.fecha_compromiso),
        }})
        origen_pedido = "pedido"
    if pedido and rol in roles.ROLES_MAPA_COTIZACION:
        cotizacion = _cotizacion_del_pedido(db, pedido)
        if cotizacion:
            datos = {"estado": _valor(cotizacion.estado), "fecha_emision": _fecha(cotizacion.fecha_emision)}
            if puede(db, rol, PERMISO_VALOR_COTIZADO):
                datos["valor_cotizado"] = float(cotizacion.valor_total or 0)
                datos["moneda"] = cotizacion.moneda
            agregar({"id": "cotizacion", "tipo": "COTIZACION", "etiqueta": cotizacion.numero_cotizacion, "datos": datos},
                    origen_pedido)
    if pedido and rol in roles.ROLES_MAPA_CLIENTE:
        agregar({"id": "cliente", "tipo": "CLIENTE", "etiqueta": pedido.cliente_nombre, "datos": {}}, origen_pedido)
    if pedido and rol in roles.ROLES_MAPA_OTRAS_OP:
        for hermana in _ops_del_pedido(db, op, pedido):
            agregar({"id": f"op:{hermana['codigo_op']}", "tipo": "OP_PEDIDO", "etiqueta": hermana["codigo_op"], "datos": {
                "estado": hermana["estado_operativo"], "unidad_actual": hermana["unidad_actual"],
                "porcentaje_avance": hermana["porcentaje_avance"],
            }}, origen_pedido)
    if rol in roles.ROLES_MAPA_PLANOS and op.id_producto:
        for plano in planos_vigentes_de_producto(db, op.id_producto):
            agregar({"id": f"plano:{plano.id_plano}", "tipo": "PLANO", "etiqueta": plano.codigo_plano, "datos": {
                "revision": plano.revision, "estado": _valor(plano.estado),
            }})
    if rol in roles.ROLES_MAPA_RECIBOS:
        entregas = (
            db.query(EntregaMaterialOP, LoteMaterial)
            .outerjoin(LoteMaterial, LoteMaterial.id == EntregaMaterialOP.lote_id)
            .filter(EntregaMaterialOP.op_id == op.id_op).order_by(EntregaMaterialOP.fecha_entrega).all()
        )
        for entrega, lote in entregas:
            agregar({"id": f"entrega:{entrega.id}", "tipo": "ENTREGA_MATERIAL",
                     "etiqueta": lote.codigo_lote if lote else f"Entrega {entrega.id}", "datos": {
                         "numero_colada": lote.numero_colada if lote else None,
                         "cantidad": entrega.cantidad_entregada, "fecha": _fecha(entrega.fecha_entrega),
                     }})
        ingresos = (
            db.query(MovimientoInventario, ArticuloInventario)
            .join(ArticuloInventario, ArticuloInventario.id_articulo == MovimientoInventario.id_articulo)
            .filter(MovimientoInventario.codigo_op == op.codigo_op, ArticuloInventario.categoria == CATEGORIA_PT,
                    MovimientoInventario.cantidad > 0)
            .order_by(MovimientoInventario.creado_en).all()
        )
        for movimiento, articulo in ingresos:
            agregar({"id": f"ingreso:{movimiento.id_movimiento}", "tipo": "INGRESO_PT", "etiqueta": articulo.codigo_sku,
                     "datos": {"producto": articulo.nombre, "cantidad": movimiento.cantidad,
                               "fecha": _fecha(movimiento.creado_en)}})
    return {"nodos": nodos, "aristas": aristas}


def _procesos(db: Session, op: OrdenProduccion, con_tiempos: bool) -> dict:
    operaciones = (
        db.query(OperacionOT).filter(OperacionOT.codigo_op == op.codigo_op)
        .order_by(OperacionOT.secuencia_paso, OperacionOT.nombre_proceso).all()
    )
    ids = [operacion.id_operacion for operacion in operaciones]
    maquinas, operarios = defaultdict(set), defaultdict(set)
    segundos = defaultdict(lambda: {"operacion": 0, "setup": 0})
    if ids:
        # Carga manual (migración 33): una fila por captura, con setup aparte
        for registro in db.query(RegistroTiemposProduccion).filter(RegistroTiemposProduccion.id_operacion.in_(ids)).all():
            maquinas[registro.id_operacion].add(registro.estacion_id)
            operarios[registro.id_operacion].add(registro.operario_id)
            segundos[registro.id_operacion]["operacion"] += registro.segundos_ejecutados or 0
            segundos[registro.id_operacion]["setup"] += registro.segundos_setup or 0
        # Puesto CNC: sublotes de la operación y sus registros de tiempo
        for sublote, registro in (
            db.query(SubLoteOperacion, RegistroTiempoOperario)
            .outerjoin(RegistroTiempoOperario, RegistroTiempoOperario.id_sublote == SubLoteOperacion.id_sublote)
            .filter(SubLoteOperacion.id_operacion.in_(ids)).all()
        ):
            maquinas[sublote.id_operacion].add(registro.maquina_codigo if registro else sublote.maquina_codigo)
            operarios[sublote.id_operacion].add(sublote.operario_nombre or (registro.operario_id if registro else None)
                                                or sublote.operario_id)
            if registro:
                segundos[sublote.id_operacion]["operacion"] += registro.tiempo_produccion_segundos or 0
                segundos[sublote.id_operacion]["setup"] += registro.tiempo_setup_segundos or 0
    # Los operarios de la carga manual se guardan con el id_usuario: se muestran con su usuario
    etiquetas = etiquetas_usuarios(db, [valor for grupo in operarios.values() for valor in grupo])

    nodos = []
    for operacion in operaciones:
        datos = {
            "secuencia": operacion.secuencia_paso,
            "estado": _valor(operacion.estado_operacion),
            "maquinas": sorted(m for m in maquinas[operacion.id_operacion] if m),
            "operarios": sorted({mostrar(etiquetas, o) for o in operarios[operacion.id_operacion] if o}),
        }
        if con_tiempos:
            datos["minutos_operacion"] = _minutos(segundos[operacion.id_operacion]["operacion"])
            datos["minutos_setup"] = _minutos(segundos[operacion.id_operacion]["setup"])
        nodos.append({"id": str(operacion.id_operacion), "tipo": "OPERACION", "etiqueta": operacion.nombre_proceso,
                      "datos": datos})
    aristas = [{"desde": anterior["id"], "hasta": siguiente["id"]} for anterior, siguiente in zip(nodos, nodos[1:])]
    return {"nodos": nodos, "aristas": aristas, "con_tiempos": con_tiempos}


@router.get("/{codigo_op}")
def mapa_de_la_op(codigo_op: str, db: Session = Depends(get_db), usuario: dict = Depends(obtener_usuario_actual)):
    rol = rol_en_bd(db, usuario["id_usuario"])
    mapas = mapas_del_rol(rol)
    if not mapas:
        raise HTTPException(status_code=403, detail="Su rol no ve el mapa de la OP.")
    op = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == codigo_op).first()
    # Una OP fuera del alcance del rol se responde igual que una inexistente
    if not op or not unidad_op.puede_ver_op(rol, op, db):
        raise HTTPException(status_code=404, detail="No se encontró la Orden de Producción indicada.")
    por_defecto = PROCESOS if PROCESOS in mapas and rol in roles.ROLES_MAPA_PROCESOS_POR_DEFECTO else mapas[0]
    return {
        "codigo_op": op.codigo_op,
        "mapas": mapas,
        "por_defecto": por_defecto,
        RELACIONES: _relaciones(db, op, rol) if RELACIONES in mapas else None,
        PROCESOS: _procesos(db, op, rol in roles.ROLES_COSTOS_TIEMPOS) if PROCESOS in mapas else None,
    }
