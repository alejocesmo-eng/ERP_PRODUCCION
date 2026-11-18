"""
Cierre seguro de OP y cierre manual del pedido (reglas/cierre-op-seguro.md y Regla 6 de
reglas/pedido-cotizacion-cambios.md; 36_MIGRACION_PEDIDO_CERRADO.sql).

Cierre de OP, todo validado aquí con el rol de la base:
1. Solo si CALIDAD_PRODUCTO aprobó todas las piezas de la OP (cantidad_aprobada, migración 35) y
   cada proceso de su ruta tiene tiempo cargado (carga manual o puesto CNC). Si no, se rechaza
   aunque la interfaz muestre el botón.
2. La persona confirma escribiendo el número de la OP; el resumen lo da resumen_cierre.
3. Un líder de respaldo da un motivo de al menos 15 caracteres; el Jefe de Producción no.
4. Cada cierre queda en el historial (quién, cuándo, estado previo y motivo); si cierra un líder
   de respaldo, el Jefe de Producción recibe un aviso.

Quién cierra: JEFE_PRODUCCION cualquier OP; LIDER_MECANIZADOS cualquiera como respaldo;
LIDER_SERVICIOS solo las de su área. Solo JEFE_PRODUCCION reabre, con motivo, y nunca si el
pedido ya está CERRADO.

Pedido: solo JEFE_PRODUCCION lo cierra, a mano, cuando todas sus OP están cerradas (o canceladas,
con al menos una cerrada). Confirma escribiendo el número del pedido. Queda CERRADO, sin edición.
"""
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import roles
from app.db.models import EstadoOPEnum, EstadoProyectoEnum, OrdenProduccion, Proyecto, RegistroTiemposProduccion
from app.db.models_produccion import (
    NotificacionLider,
    OperacionOT,
    RegistroTiempoOperario,
    SubLoteOperacion,
    TipoNotificacionEnum,
    TipoUnidadPlantaEnum,
)
from app.services import unidad_op
from app.services.auditoria import agregar_evento_trazabilidad
from app.services.piezas_aprobadas import piezas_aprobadas

LONGITUD_MINIMA_MOTIVO = 15
# Estados de OP con los que el pedido se puede cerrar
ESTADOS_OP_FINALES = {EstadoOPEnum.CERRADA, EstadoOPEnum.CANCELADA}
# Al reabrir, la OP vuelve a terminada (Calidad ya aprobó sus piezas)
ESTADO_OP_REABIERTA = EstadoOPEnum.TERMINADA
UNIDAD_NOTIFICACION = {
    "MECANIZADOS": TipoUnidadPlantaEnum.MECANIZADOS,
    "METALISTERIA": TipoUnidadPlantaEnum.METALISTERIA,
    "SERVICIOS": TipoUnidadPlantaEnum.SERVICIOS,
}


def _valor(estado) -> Optional[str]:
    return estado.value if hasattr(estado, "value") else estado


def _motivo(motivo: Optional[str]) -> str:
    return (motivo or "").strip()


def pedido_cerrado(pedido: Optional[Proyecto]) -> bool:
    return pedido is not None and pedido.estado == EstadoProyectoEnum.CERRADO


def segundos_por_operacion(db: Session, op: OrdenProduccion) -> tuple[list, dict]:
    """(procesos de la ruta en orden, {id_operacion: segundos de operación + setup}), con la carga
    manual (migración 33) y los registros del puesto CNC, igual que el mapa de procesos."""
    procesos = (
        db.query(OperacionOT).filter(OperacionOT.codigo_op == op.codigo_op)
        .order_by(OperacionOT.secuencia_paso, OperacionOT.nombre_proceso).all()
    )
    ids = [proceso.id_operacion for proceso in procesos]
    segundos = {id_operacion: 0 for id_operacion in ids}
    if ids:
        for registro in db.query(RegistroTiemposProduccion).filter(RegistroTiemposProduccion.id_operacion.in_(ids)).all():
            segundos[registro.id_operacion] += (registro.segundos_ejecutados or 0) + (registro.segundos_setup or 0)
        for sublote, registro in (
            db.query(SubLoteOperacion, RegistroTiempoOperario)
            .join(RegistroTiempoOperario, RegistroTiempoOperario.id_sublote == SubLoteOperacion.id_sublote)
            .filter(SubLoteOperacion.id_operacion.in_(ids)).all()
        ):
            segundos[sublote.id_operacion] += (registro.tiempo_produccion_segundos or 0) + (registro.tiempo_setup_segundos or 0)
    return procesos, segundos


def resumen_cierre(db: Session, op: OrdenProduccion, rol: Optional[str]) -> dict:
    """Lo que muestra la confirmación y lo que valida el cierre."""
    pedido = op.proyecto
    cantidad = op.cantidad_fabricar or 0
    aprobadas = piezas_aprobadas(db, op.codigo_op)
    procesos, segundos = segundos_por_operacion(db, op)
    sin_tiempo = [proceso.nombre_proceso for proceso in procesos if segundos[proceso.id_operacion] <= 0]
    aprobada_calidad = cantidad > 0 and aprobadas >= cantidad

    faltantes = []
    if not aprobada_calidad:
        faltantes.append(f"Calidad de producto no ha aprobado todas las piezas ({aprobadas} de {cantidad}).")
    if not procesos:
        faltantes.append("La OP no tiene procesos en su ruta: no hay tiempos que verificar.")
    elif sin_tiempo:
        faltantes.append(f"Procesos sin tiempo cargado: {', '.join(sin_tiempo)}.")
    if op.estado == EstadoOPEnum.CERRADA:
        faltantes.append("La OP ya está cerrada.")
    elif op.estado == EstadoOPEnum.CANCELADA:
        faltantes.append("La OP está cancelada.")
    if pedido_cerrado(pedido):
        faltantes.append("El pedido está cerrado.")

    return {
        "codigo_op": op.codigo_op,
        "estado": _valor(op.estado),
        "numero_pedido": pedido.numero_pedido if pedido else None,
        "cliente": pedido.cliente_nombre if pedido else None,
        "cantidad": cantidad,
        "piezas_aprobadas": aprobadas,
        "aprobada_calidad": aprobada_calidad,
        "minutos_tiempos": round(sum(segundos.values()) / 60, 2),
        "procesos": len(procesos),
        "procesos_sin_tiempo": sin_tiempo,
        "tiempos_completos": bool(procesos) and not sin_tiempo,
        "requiere_motivo": rol not in roles.ROLES_CIERRE_SIN_MOTIVO,
        "longitud_minima_motivo": LONGITUD_MINIMA_MOTIVO,
        "puede_cerrar": not faltantes,
        "faltantes": faltantes,
    }


def validar_rol_cierre(db: Session, rol: Optional[str], op: OrdenProduccion) -> None:
    if rol not in roles.ROLES_CERRAR_OP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Su rol no cierra OP.")
    if rol in roles.ROLES_CIERRE_SOLO_SU_UNIDAD and not unidad_op.puede_ver_op(rol, op, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo puede cerrar OP de su área.")


def _aviso_al_jefe(db: Session, op: OrdenProduccion, rol: str, usuario: str, motivo: str) -> None:
    unidad = UNIDAD_NOTIFICACION.get(op.unidad_actual)
    if unidad is None:
        try:
            unidad = TipoUnidadPlantaEnum(_valor(getattr(op.plano, "unidad_planta", None)))
        except (TypeError, ValueError):
            unidad = TipoUnidadPlantaEnum.MECANIZADOS
    db.add(NotificacionLider(
        unidad_planta=unidad,
        tipo_notificacion=TipoNotificacionEnum.OP_CERRADA_RESPALDO,
        titulo=f"OP cerrada por respaldo · Orden {op.codigo_op}",
        mensaje=f"{rol} cerró la orden {op.codigo_op} como respaldo del Jefe de Producción. Motivo: {motivo}",
        codigo_op=op.codigo_op,
        codigo_plano=getattr(op.plano, "codigo_plano", None) or "SIN_PLANO",
        operario_nombre=usuario,
        maquina_codigo="CIERRE_OP",
        piezas_reportadas=op.cantidad_fabricar or 0,
    ))


def cerrar_op(db: Session, op: OrdenProduccion, rol: str, usuario: str, confirmacion: Optional[str],
              motivo: Optional[str]) -> dict:
    """Valida las cuatro condiciones y deja la OP CERRADA en la transacción activa."""
    validar_rol_cierre(db, rol, op)
    if (confirmacion or "").strip() != op.codigo_op:
        raise HTTPException(status_code=422, detail="Escriba el número de la OP para confirmar el cierre.")
    motivo = _motivo(motivo)
    respaldo = rol not in roles.ROLES_CIERRE_SIN_MOTIVO
    if respaldo and len(motivo) < LONGITUD_MINIMA_MOTIVO:
        raise HTTPException(
            status_code=422,
            detail=f"Como respaldo del Jefe de Producción, indique el motivo (mínimo {LONGITUD_MINIMA_MOTIVO} caracteres).",
        )
    resumen = resumen_cierre(db, op, rol)
    if not resumen["puede_cerrar"]:
        raise HTTPException(status_code=409, detail=" ".join(resumen["faltantes"]))

    estado_anterior = _valor(op.estado)
    op.estado = EstadoOPEnum.CERRADA
    agregar_evento_trazabilidad(
        db,
        tipo_entidad="ORDEN_PRODUCCION",
        identificador=op.codigo_op,
        accion="OP_CERRADA",
        usuario=usuario,
        area=rol,
        estado_anterior=estado_anterior,
        estado_nuevo=EstadoOPEnum.CERRADA.value,
        motivo=motivo or None,
    )
    if respaldo:
        _aviso_al_jefe(db, op, rol, usuario, motivo)
    return {"estado_anterior": estado_anterior, "aviso_jefe": respaldo}


def reabrir_op(db: Session, op: OrdenProduccion, rol: str, usuario: str, motivo: Optional[str]) -> str:
    if rol not in roles.ROLES_REABRIR_OP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el Jefe de Producción reabre una OP.")
    motivo = _motivo(motivo)
    if len(motivo) < LONGITUD_MINIMA_MOTIVO:
        raise HTTPException(status_code=422, detail=f"Indique el motivo de la reapertura (mínimo {LONGITUD_MINIMA_MOTIVO} caracteres).")
    if op.estado != EstadoOPEnum.CERRADA:
        raise HTTPException(status_code=409, detail="Solo se reabre una OP cerrada.")
    if pedido_cerrado(op.proyecto):
        raise HTTPException(status_code=409, detail="El pedido está cerrado: sus OP no se reabren.")
    estado_anterior = _valor(op.estado)
    op.estado = ESTADO_OP_REABIERTA
    agregar_evento_trazabilidad(
        db,
        tipo_entidad="ORDEN_PRODUCCION",
        identificador=op.codigo_op,
        accion="OP_REABIERTA",
        usuario=usuario,
        area=rol,
        estado_anterior=estado_anterior,
        estado_nuevo=ESTADO_OP_REABIERTA.value,
        motivo=motivo,
    )
    return estado_anterior


def pendientes_para_cerrar_pedido(db: Session, pedido: Proyecto) -> list[str]:
    """Por qué el pedido aún no se puede cerrar; vacío si ya se puede."""
    if pedido_cerrado(pedido):
        return ["El pedido ya está cerrado."]
    if not pedido.confirmado:
        return ["El pedido no está confirmado."]
    ops = db.query(OrdenProduccion).filter(OrdenProduccion.id_proyecto == pedido.id_proyecto).all()
    if not ops:
        return ["El pedido no tiene OP."]
    abiertas = sorted(op.codigo_op for op in ops if op.estado not in ESTADOS_OP_FINALES)
    if abiertas:
        return [f"OP sin cerrar: {', '.join(abiertas)}."]
    if not any(op.estado == EstadoOPEnum.CERRADA for op in ops):
        return ["Todas las OP del pedido están canceladas: no hay OP cerradas."]
    return []


def cerrar_pedido(db: Session, pedido: Proyecto, rol: str, usuario: str, confirmacion: Optional[str]) -> str:
    if rol not in roles.ROLES_CERRAR_PEDIDO:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el Jefe de Producción cierra el pedido.")
    if (confirmacion or "").strip() != pedido.numero_pedido:
        raise HTTPException(status_code=422, detail="Escriba el número del pedido para confirmar el cierre.")
    pendientes = pendientes_para_cerrar_pedido(db, pedido)
    if pendientes:
        raise HTTPException(status_code=409, detail=" ".join(pendientes))
    estado_anterior = _valor(pedido.estado)
    pedido.estado = EstadoProyectoEnum.CERRADO
    agregar_evento_trazabilidad(
        db,
        tipo_entidad="PEDIDO",
        identificador=pedido.numero_pedido,
        accion="PEDIDO_CERRADO",
        usuario=usuario,
        area=rol,
        estado_anterior=estado_anterior,
        estado_nuevo=EstadoProyectoEnum.CERRADO.value,
    )
    return estado_anterior
