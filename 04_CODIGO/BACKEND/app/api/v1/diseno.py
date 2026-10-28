import os
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db
from app.db.models import Plano, SolicitudCambioTecnico

router = APIRouter()

@router.post("/op/{id_plano}/iniciar-trabajo")
def iniciar_trabajo_diseno(id_plano: UUID, db: Session = Depends(get_db)):
    """
    Marca el inicio del trabajo de diseño para una OP.
    Cambia el estado a 'EN_DISENO' y registra el timestamp de inicio.
    """
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=404, detail="La Orden de Producción no fue encontrada.")

    if plano.estado_diseno == "LIBERADA":
        raise HTTPException(status_code=400, detail="La orden ya ha sido liberada a producción.")

    plano.estado_diseno = "EN_DISENO"
    plano.fecha_inicio_diseno = datetime.now(timezone.utc)

    db.commit()
    db.refresh(plano)
    return {"mensaje": "Trabajo de diseño iniciado", "inicio": plano.fecha_inicio_diseno}

@router.post("/op/{id_plano}/liberar")
def liberar_diseno_produccion(id_plano: UUID, db: Session = Depends(get_db)):
    """
    Libera el diseño para producción tras validar requisitos bloqueantes:
    1. Presencia de los 3 archivos técnicos (.pdf, .step, .dxf).
    2. Ausencia de Solicitudes de Cambio Técnico (ECR) pendientes.
    """
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=404, detail="La Orden de Producción no fue encontrada.")

    # 1. Validación de Archivos Técnicos
    faltantes = []
    if not plano.archivo_pdf_url: faltantes.append("PDF (Plano)")
    if not plano.archivo_step_url: faltantes.append("STEP (Modelo 3D)")
    if not plano.archivo_dxf_url: faltantes.append("DXF (Corte/CNC)")

    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede liberar el diseño. Faltan archivos obligatorios: {', '.join(faltantes)}."
        )

    # 2. Validación de ECRs Pendientes
    ecrs_pendientes = db.query(SolicitudCambioTecnico).filter(
        SolicitudCambioTecnico.id_plano == id_plano,
        SolicitudCambioTecnico.estado_solicitud == "PENDIENTE"
    ).count()

    if ecrs_pendientes > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede liberar el diseño. Existen {ecrs_pendientes} Solicitudes de Cambio Técnico (ECR) pendientes de resolución."
        )

    # Cálculo de tiempo neto de diseño
    ahora = datetime.now(timezone.utc)
    if plano.fecha_inicio_diseno:
        delta = ahora - plano.fecha_inicio_diseno
        plano.tiempo_total_diseno_minutos = int(delta.total_seconds() / 60)

    plano.fecha_fin_diseno = ahora
    plano.estado_diseno = "LIBERADA"

    db.commit()
    db.refresh(plano)
    return {"mensaje": "Diseño liberado exitosamente a producción", "tiempo_total_minutos": plano.tiempo_total_diseno_minutos}

@router.patch("/ecr/{id_solicitud}/resolver")
def resolver_ecr(id_solicitud: UUID, db: Session = Depends(get_db)):
    """
    Permite al dibujante marcar una observación técnica como resuelta.
    """
    ecr = db.query(SolicitudCambioTecnico).filter(SolicitudCambioTecnico.id_solicitud == id_solicitud).first()
    if not ecr:
        raise HTTPException(status_code=404, detail="La solicitud de cambio no fue encontrada.")

    ecr.estado_solicitud = "RESUELTA"
    db.commit()
    return {"mensaje": "Observación técnica marcada como resuelta"}
