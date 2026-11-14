# app/api/v1/unidades_op.py
"""
Unidad actual de la OP y traslados (app/services/unidad_op.py). El rol se lee de la base en cada
consulta. El permiso se revisa en el cuerpo (no con requerir_roles): ADMIN no cambia la unidad.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual
from app.core import roles
from app.db.database import get_db
from app.db.models import OrdenProduccion, TrasladoUnidadOP
from app.services import unidad_op
from app.services.acceso_bd import rol_en_bd

router = APIRouter()


class TrasladoRequest(BaseModel):
    # Opcional en el esquema para responder con el mensaje propio cuando falta
    unidad_destino: Optional[str] = None
    observacion: Optional[str] = None


def _fecha(valor):
    return valor.isoformat() if valor else None


def _op_visible(db: Session, codigo_op: str, rol: Optional[str]) -> OrdenProduccion:
    op = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == codigo_op).first()
    # Una OP fuera del alcance del rol se responde igual que una inexistente
    if not op or not unidad_op.puede_ver_op(rol, op, db):
        raise HTTPException(status_code=404, detail="No se encontró la Orden de Producción indicada.")
    return op


@router.get("/unidades")
def listar_unidades():
    return [{"codigo": codigo, "nombre": unidad_op.ETIQUETAS[codigo]} for codigo in unidad_op.UNIDADES]


@router.post("/{codigo_op}/traslado")
def trasladar_op(
    codigo_op: str,
    datos: TrasladoRequest,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    rol = rol_en_bd(db, usuario["email"])
    if rol not in roles.ROLES_CAMBIAR_UNIDAD_OP:
        raise HTTPException(status_code=403, detail="Su rol no puede cambiar la unidad de la OP.")
    op = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == codigo_op).first()
    if not op:
        raise HTTPException(status_code=404, detail="No se encontró la Orden de Producción indicada.")
    traslado = unidad_op.trasladar(db, op, datos.unidad_destino, usuario["email"], rol, datos.observacion)
    try:
        db.commit()
        db.refresh(traslado)
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar el traslado de la OP.") from error
    return {
        "codigo_op": op.codigo_op,
        "unidad_origen": traslado.unidad_origen,
        "unidad_destino": traslado.unidad_destino,
        "trasladado_por": traslado.usuario_email,
        "trasladado_en": _fecha(traslado.registrado_en),
    }


@router.get("/{codigo_op}/traslados")
def listar_traslados(
    codigo_op: str,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    rol = rol_en_bd(db, usuario["email"])
    if rol not in roles.ROLES_EXPEDIENTE_OP and rol not in roles.ROLES_CAMBIAR_UNIDAD_OP:
        raise HTTPException(status_code=404, detail="No se encontró la Orden de Producción indicada.")
    op = _op_visible(db, codigo_op, rol)
    traslados = (
        db.query(TrasladoUnidadOP).filter(TrasladoUnidadOP.id_op == op.id_op)
        .order_by(TrasladoUnidadOP.registrado_en, TrasladoUnidadOP.id_traslado).all()
    )
    return {
        "codigo_op": op.codigo_op,
        "unidad_actual": op.unidad_actual,
        "traslados": [{
            "unidad_origen": t.unidad_origen,
            "unidad_destino": t.unidad_destino,
            "usuario": t.usuario_email,
            "rol": t.rol,
            "observacion": t.observacion,
            "registrado_en": _fecha(t.registrado_en),
        } for t in traslados],
    }
