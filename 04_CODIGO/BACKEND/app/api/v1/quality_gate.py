from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import BOMListaMateriales, EstadoPlanoEnum, Plano


ESTADOS_BOM_LIBERABLES = {"EN_ALMACEN", "ENTREGADO"}


def validar_gate_calidad(db: Session, plano: Plano | None) -> None:
    if not plano:
        raise HTTPException(status_code=400, detail="La OP no tiene un plano asociado.")
    if not plano.archivo_url or not plano.archivo_url.strip():
        raise HTTPException(status_code=400, detail="RN-OP-004: debe adjuntar el plano PDF antes de liberar la OP.")

    materiales = db.query(BOMListaMateriales).filter(
        BOMListaMateriales.plano_id == plano.id_plano
    ).all()
    if not materiales:
        raise HTTPException(status_code=400, detail="RN-OP-004: la OP requiere al menos una línea BOM abastecida.")

    pendientes = [
        item.codigo_material
        for item in materiales
        if item.estado_abastecimiento not in ESTADOS_BOM_LIBERABLES
    ]
    if pendientes:
        raise HTTPException(
            status_code=400,
            detail=f"RN-OP-004: materiales BOM pendientes de almacén/entrega: {', '.join(pendientes)}.",
        )


def planos_de_op(db: Session, id_proyecto: UUID, codigo_op: str, id_plano: UUID | None = None) -> list[Plano]:
    """Planos de la OP: el plano principal y los del mismo proyecto con el mismo codigo_op.
    Sin coincidencias, todos los planos del proyecto."""
    planos = db.query(Plano).filter(Plano.id_proyecto == id_proyecto, Plano.codigo_op == codigo_op).all()
    if id_plano and all(plano.id_plano != id_plano for plano in planos):
        principal = db.query(Plano).filter(Plano.id_plano == id_plano).first()
        if principal:
            planos.insert(0, principal)
    if not planos:
        planos = db.query(Plano).filter(Plano.id_proyecto == id_proyecto).all()
    return planos


def validar_regla_liberacion(db: Session, planos: list[Plano]) -> None:
    """Una OP pasa a LIBERADA solo si cada plano tiene PDF, BOM abastecida y aprobación de Diseño."""
    if not planos:
        raise HTTPException(status_code=400, detail="La OP no tiene un plano asociado.")
    for plano in planos:
        validar_gate_calidad(db, plano)
        estado = plano.estado.value if hasattr(plano.estado, "value") else plano.estado
        if estado != EstadoPlanoEnum.APROBADO.value or not plano.aprobado_por or not plano.fecha_aprobacion:
            raise HTTPException(
                status_code=400,
                detail=f"El plano {plano.codigo_plano} debe estar APROBADO por Diseño (aprobado_por y fecha_aprobacion) antes de liberar la OP.",
            )


def _como_utc(valor: datetime) -> datetime:
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


def planos_por_revisar(planos: list[Plano]) -> list[str]:
    """Marca "revisar": planos con una revisión posterior a su aprobación. Solo es un aviso."""
    return [
        plano.codigo_plano
        for plano in planos
        if plano.fecha_ultima_revision
        and plano.fecha_aprobacion
        and _como_utc(plano.fecha_ultima_revision) > _como_utc(plano.fecha_aprobacion)
    ]
