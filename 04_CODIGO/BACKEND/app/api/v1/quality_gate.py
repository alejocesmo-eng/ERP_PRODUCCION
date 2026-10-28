from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import BOMListaMateriales, Plano


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
