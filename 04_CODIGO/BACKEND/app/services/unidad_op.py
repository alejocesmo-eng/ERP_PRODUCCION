"""
Unidad actual de la OP y traslado obligatorio (28_MIGRACION_OP_UNIDAD_ACTUAL.sql,
reglas/permisos-por-rol-modulo.md del proyecto PRISMA).

- La OP está en una unidad: Mecanizados, Servicios, Metalistería, Tercero o Despacho. Mientras no
  llega a ninguna, queda SIN_ASIGNAR.
- Al liberarla, el sistema la asigna a la unidad de sus planos vigentes (asignación inicial). Desde
  ahí solo cambia con un traslado: lo hace CALIDAD_PRODUCTO (ROLES_CAMBIAR_UNIDAD_OP); ningún
  otro rol, tampoco ADMIN. LIDER_MECANIZADOS y LIDER_SERVICIOS no cambian la unidad. Cuando exista
  LIDER_METALISTERIA (roles.LIDERES_CAMBIAN_UNIDAD), trasladará las OP de su unidad hacia otras.
- El líder de cada unidad solo ve las OP de su unidad; CALIDAD_PRODUCTO, las que le llegan para
  inspección y las que están en Tercero (vuelven por Calidad). LIDER_SERVICIOS además ve las OP de
  su área desde que se crean: aún sin unidad, si los planos vigentes de su producto son de su unidad
  (roles.LIDERES_VEN_DESDE_CREACION).
- Los movimientos de Almacén y del transportador en la cadena del tercero no cambian la unidad:
  la OP queda en Tercero hasta que Calidad la traslade.
"""
import unicodedata
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.core import roles
from app.db.models import EstadoOPEnum, OrdenProduccion, Plano, TrasladoUnidadOP

MECANIZADOS = "MECANIZADOS"
SERVICIOS = "SERVICIOS"
METALISTERIA = "METALISTERIA"
TERCERO = "TERCERO"
DESPACHO = "DESPACHO"
SIN_ASIGNAR = "SIN_ASIGNAR"

# Destinos válidos de un traslado (SIN_ASIGNAR no es destino)
UNIDADES = [MECANIZADOS, SERVICIOS, METALISTERIA, TERCERO, DESPACHO]
ETIQUETAS = {
    MECANIZADOS: "Mecanizados",
    SERVICIOS: "Servicios",
    METALISTERIA: "Metalistería",
    TERCERO: "Tercero",
    DESPACHO: "Despacho",
    SIN_ASIGNAR: "Sin asignar",
}
# Unidades de proceso de planos.unidad_planta (sin tildes ni mayúsculas)
_UNIDAD_DE_PROCESO = {"mecanizados": MECANIZADOS, "servicios": SERVICIOS, "metalisteria": METALISTERIA}

# OP que le llegan a Calidad para inspección
ESTADOS_INSPECCION = [EstadoOPEnum.TERMINADA, EstadoOPEnum.INSPECCION_CALIDAD, EstadoOPEnum.EN_INSPECCION]

MENSAJE_SIN_DESTINO = "Indique la unidad destino del traslado."


def unidad_de_proceso(texto: Optional[str]) -> Optional[str]:
    """MECANIZADOS, SERVICIOS o METALISTERIA a partir de planos.unidad_planta; None si no se reconoce."""
    if not texto:
        return None
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return _UNIDAD_DE_PROCESO.get(sin_tildes.strip().lower())


def unidad_de_planos(planos: Iterable[Plano]) -> Optional[str]:
    """La unidad común de los planos; None si no hay o si no coinciden."""
    unidades = {unidad_de_proceso(plano.unidad_planta) for plano in planos}
    return unidades.pop() if len(unidades) == 1 and None not in unidades else None


def unidad_del_lider(rol: Optional[str]) -> Optional[str]:
    return roles.UNIDAD_POR_LIDER.get(rol)


def _sin_unidad(op: OrdenProduccion) -> bool:
    return (op.unidad_actual or SIN_ASIGNAR) == SIN_ASIGNAR


def unidad_de_producto(db: Session, id_producto) -> Optional[str]:
    """Unidad de los planos vigentes del producto (la misma selección que la liberación)."""
    from app.api.v1.quality_gate import planos_vigentes_de_producto

    return unidad_de_planos(planos_vigentes_de_producto(db, id_producto)) if id_producto else None


def productos_de_unidad(db: Session, unidad: str) -> set:
    """Productos de OP aún sin unidad cuyos planos vigentes son de la unidad indicada."""
    ids = {
        id_producto for (id_producto,) in db.query(OrdenProduccion.id_producto).filter(
            OrdenProduccion.id_producto.isnot(None),
            or_(OrdenProduccion.unidad_actual.is_(None), OrdenProduccion.unidad_actual == SIN_ASIGNAR),
        ).distinct().all()
    }
    return {id_producto for id_producto in ids if unidad_de_producto(db, id_producto) == unidad}


def filtrar_op_visibles(consulta: Query, rol: Optional[str]) -> Query:
    """Restringe una consulta de OrdenProduccion a lo que ve el rol según su unidad.
    Los demás roles siguen con el acceso de su ruta."""
    unidad = unidad_del_lider(rol)
    if unidad and rol in roles.LIDERES_VEN_DESDE_CREACION:
        productos = productos_de_unidad(consulta.session, unidad)
        return consulta.filter(or_(
            OrdenProduccion.unidad_actual == unidad,
            (or_(OrdenProduccion.unidad_actual.is_(None), OrdenProduccion.unidad_actual == SIN_ASIGNAR))
            & OrdenProduccion.id_producto.in_(productos),
        ))
    if unidad:
        return consulta.filter(OrdenProduccion.unidad_actual == unidad)
    if rol == roles.CALIDAD_PRODUCTO:
        return consulta.filter(or_(
            OrdenProduccion.estado.in_(ESTADOS_INSPECCION),
            OrdenProduccion.unidad_actual == TERCERO,
        ))
    return consulta


def puede_ver_op(rol: Optional[str], op: OrdenProduccion, db: Optional[Session] = None) -> bool:
    """Con db, LIDERES_VEN_DESDE_CREACION ven también las OP de su área que aún no tienen unidad."""
    unidad = unidad_del_lider(rol)
    if unidad and op.unidad_actual == unidad:
        return True
    if unidad and rol in roles.LIDERES_VEN_DESDE_CREACION and db is not None and _sin_unidad(op):
        return unidad_de_producto(db, op.id_producto) == unidad
    if unidad:
        return False
    if rol == roles.CALIDAD_PRODUCTO:
        return op.estado in ESTADOS_INSPECCION or op.unidad_actual == TERCERO
    return True


def _registrar(db: Session, op: OrdenProduccion, destino: str, id_usuario: str, rol: Optional[str], observacion: Optional[str]) -> TrasladoUnidadOP:
    traslado = TrasladoUnidadOP(
        id_op=op.id_op,
        unidad_origen=op.unidad_actual or SIN_ASIGNAR,
        unidad_destino=destino,
        # Desde la migración 34 se guarda el id_usuario de quien traslada
        usuario_email=id_usuario,
        rol=rol,
        observacion=observacion,
    )
    op.unidad_actual = destino
    db.add(traslado)
    return traslado


def trasladar(db: Session, op: OrdenProduccion, destino: Optional[str], id_usuario: str, rol: Optional[str],
              observacion: Optional[str] = None) -> TrasladoUnidadOP:
    """Traslado obligatorio: sin unidad destino no se confirma. No hace commit."""
    if rol not in roles.ROLES_CAMBIAR_UNIDAD_OP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Su rol no puede cambiar la unidad de la OP.")
    unidad_lider = unidad_del_lider(rol)
    if unidad_lider and op.unidad_actual != unidad_lider:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Solo puede trasladar OP que están en {ETIQUETAS[unidad_lider]}.")
    destino = (destino or "").strip().upper()
    if not destino:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=MENSAJE_SIN_DESTINO)
    if destino not in UNIDADES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Unidad destino no válida. Use una de: {', '.join(ETIQUETAS[u] for u in UNIDADES)}.")
    if destino == op.unidad_actual:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"La OP ya está en {ETIQUETAS[destino]}.")
    return _registrar(db, op, destino, id_usuario, rol, (observacion or "").strip() or None)


def asignar_unidad_inicial(db: Session, op: OrdenProduccion, planos: Iterable[Plano], id_usuario: str, rol: Optional[str]) -> None:
    """Al liberar, la OP sin unidad llega a la unidad de sus planos vigentes. Si los planos no
    dicen una sola unidad, queda SIN_ASIGNAR. No hace commit."""
    if (op.unidad_actual or SIN_ASIGNAR) != SIN_ASIGNAR:
        return
    destino = unidad_de_planos(planos)
    if destino:
        _registrar(db, op, destino, id_usuario, rol, "Asignación inicial al liberar la OP")
