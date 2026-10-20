import os
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models_produccion import OperacionOT, RegistroTiempoOperario

router = APIRouter()


# =============================================================================
# SCHEMAS PYDANTIC (PUESTO CNC Y TIEMPOS MES)
# =============================================================================

class IniciarSetupRequest(BaseModel):
    operacion_id: UUID
    operario_id: UUID
    maquina_id: Optional[str] = "CNC-01"


class ConmutarMecanizadoRequest(BaseModel):
    operacion_id: UUID
    operario_id: UUID
    justificacion_exceso: Optional[str] = Field(
        None, 
        description="Justificación obligatoria si el Setup excede >50% del tiempo estimado de Setup"
    )


class PausaTurnoRequest(BaseModel):
    operacion_id: UUID
    operario_id: UUID
    motivo: str = Field(..., description="Motivo de la pausa (ej. ALMUERZO, FIN_DE_TURNO, DESCANSO)")


class RegistroTiempoResponse(BaseModel):
    id: UUID
    operacion_id: UUID
    operario_id: UUID
    fase: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    tiempo_acumulado_segundos: int
    justificacion_exceso: Optional[str] = None
    motivo_pausa: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================================================
# ENDPOINTS OPERATIVOS MES - PUESTO DE TRABAJO OPERARIO CNC
# =============================================================================

@router.post("/setup/iniciar", response_model=RegistroTiempoResponse, status_code=status.HTTP_200_OK)
def iniciar_setup_cnc(payload: IniciarSetupRequest, db: Session = Depends(get_db)):
    """
    Inicia la fase de Setup (Alistamiento) para la operación asignada en el puesto CNC.
    Transiciona el estado de la operación a 'EN_SETUP'.
    """
    operacion = db.query(OperacionOT).filter(OperacionOT.id == payload.operacion_id).first()
    if not operacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="La operación especificada no existe."
        )

    # Verificar si hay una fase previa activa sin cerrar
    registro_activo = db.query(RegistroTiempoOperario).filter(
        RegistroTiempoOperario.operacion_id == payload.operacion_id,
        RegistroTiempoOperario.operario_id == payload.operario_id,
        RegistroTiempoOperario.fecha_fin.is_(None)
    ).first()

    if registro_activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un registro de tiempo activo en fase '{registro_activo.fase}'. Debe cerrar la fase actual antes de iniciar Setup."
        )

    ahora = datetime.now(timezone.utc)
    
    # Crear nuevo registro de tiempo para SETUP
    nuevo_registro = RegistroTiempoOperario(
        id=uuid4(),
        operacion_id=payload.operacion_id,
        operario_id=payload.operario_id,
        fase="SETUP",
        fecha_inicio=ahora,
        tiempo_acumulado_segundos=0
    )
    
    operacion.estado = "EN_SETUP"
    
    db.add(nuevo_registro)
    db.commit()
    db.refresh(nuevo_registro)
    
    return nuevo_registro


@router.post("/mecanizado/conmutar", response_model=RegistroTiempoResponse, status_code=status.HTTP_200_OK)
def conmutar_a_mecanizado(payload: ConmutarMecanizadoRequest, db: Session = Depends(get_db)):
    """
    Cierra la fase de Setup y conmuta a la fase de Mecanizado.
    Validación ADR-001 / REQ-PROD-001: Si el tiempo de Setup excede más del 50% el tiempo estimado
    de Setup de la operación, exige de forma obligatoria una justificación técnica.
    """
    operacion = db.query(OperacionOT).filter(OperacionOT.id == payload.operacion_id).first()
    if not operacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="La operación especificada no existe."
        )

    # Buscar el registro activo de Setup
    registro_setup = db.query(RegistroTiempoOperario).filter(
        RegistroTiempoOperario.operacion_id == payload.operacion_id,
        RegistroTiempoOperario.operario_id == payload.operario_id,
        RegistroTiempoOperario.fase == "SETUP",
        RegistroTiempoOperario.fecha_fin.is_(None)
    ).first()

    if not registro_setup:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontró un proceso de Setup activo para conmutar a Mecanizado."
        )

    ahora = datetime.now(timezone.utc)
    duracion_setup_seg = int((ahora - registro_setup.fecha_inicio.replace(tzinfo=timezone.utc)).total_seconds())
    
    # Validación de exceso >50% respecto al tiempo estimado de Setup (en segundos)
    tiempo_estimado_setup_seg = getattr(operacion, "tiempo_estimado_setup_segundos", 1800) or 1800
    limite_tolerancia_seg = tiempo_estimado_setup_seg * 1.5

    if duracion_setup_seg > limite_tolerancia_seg:
        if not payload.justificacion_exceso or not payload.justificacion_exceso.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"❌ Excepción Setup (>50% exceso): El Setup duró {duracion_setup_seg}s (Límite tolerado: {limite_tolerancia_seg}s). Debe ingresar una justificación técnica obligatoria."
            )
        registro_setup.justificacion_exceso = payload.justificacion_exceso.strip()

    # Cerrar Setup
    registro_setup.fecha_fin = ahora
    registro_setup.tiempo_acumulado_segundos = duracion_setup_seg

    # Crear nuevo registro para MECANIZADO
    nuevo_mecanizado = RegistroTiempoOperario(
        id=uuid4(),
        operacion_id=payload.operacion_id,
        operario_id=payload.operario_id,
        fase="MECANIZADO",
        fecha_inicio=ahora,
        tiempo_acumulado_segundos=0
    )

    operacion.estado = "EN_MECANIZADO"

    db.add(nuevo_mecanizado)
    db.commit()
    db.refresh(nuevo_mecanizado)

    return nuevo_mecanizado


@router.post("/pausa/turno", response_model=RegistroTiempoResponse, status_code=status.HTTP_200_OK)
def pausas_por_turno(payload: PausaTurnoRequest, db: Session = Depends(get_db)):
    """
    Pausa temporalmente la fase activa (Setup o Mecanizado) por cambio/interrupción de turno o descanso.
    """
    registro_activo = db.query(RegistroTiempoOperario).filter(
        RegistroTiempoOperario.operacion_id == payload.operacion_id,
        RegistroTiempoOperario.operario_id == payload.operario_id,
        RegistroTiempoOperario.fecha_fin.is_(None)
    ).first()

    if not registro_activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay ninguna fase activa corriendo para pausar."
        )

    ahora = datetime.now(timezone.utc)
    duracion_fase_seg = int((ahora - registro_activo.fecha_inicio.replace(tzinfo=timezone.utc)).total_seconds())

    registro_activo.fecha_fin = ahora
    registro_activo.tiempo_acumulado_segundos = duracion_fase_seg
    registro_activo.motivo_pausa = payload.motivo

    operacion = db.query(OperacionOT).filter(OperacionOT.id == payload.operacion_id).first()
    if operacion:
        operacion.estado = "PAUSADO"

    db.commit()
    db.refresh(registro_activo)

    return registro_activo