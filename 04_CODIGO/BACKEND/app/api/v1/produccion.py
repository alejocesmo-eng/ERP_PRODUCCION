from decimal import Decimal
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import EquipoPlanta, Plano
from app.db.models_produccion import (
    EstadoOperacionEnum,
    OperacionOT,
    RegistroTiempoOperario,
    SubLoteOperacion,
)

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
    operario_id: str
    fase: str
    fecha_inicio: datetime
    fecha_fin: Optional[datetime] = None
    tiempo_acumulado_segundos: int
    justificacion_exceso: Optional[str] = None
    motivo_pausa: Optional[str] = None

    class Config:
        from_attributes = True


def _respuesta_tiempo(registro: RegistroTiempoOperario, operacion_id: UUID, fase: str, inicio: datetime):
    total = registro.tiempo_setup_segundos or 0
    if fase == "MECANIZADO":
        total = registro.tiempo_produccion_segundos or 0
    return {
        "id": registro.id_registro,
        "operacion_id": operacion_id,
        "operario_id": registro.operario_id,
        "fase": fase,
        "fecha_inicio": inicio,
        "fecha_fin": registro.fecha_fin_operacion,
        "tiempo_acumulado_segundos": total,
        "justificacion_exceso": registro.justificacion_exceso,
        "motivo_pausa": registro.motivo_pausa,
    }


def _segundos_transcurridos(inicio: datetime, fin: datetime) -> int:
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=timezone.utc)
    return max(int((fin - inicio).total_seconds()), 0)


def _obtener_sublote(
    db: Session,
    operacion_id: UUID,
    operario_id: UUID,
    maquina_id: Optional[str] = None,
) -> SubLoteOperacion:
    consulta = db.query(SubLoteOperacion).filter(
        SubLoteOperacion.id_operacion == operacion_id,
        SubLoteOperacion.operario_id == str(operario_id),
    )
    sublote = consulta.with_for_update().first()
    if not sublote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El operario no tiene un sublote asignado a esta operación.",
        )
    if maquina_id and sublote.maquina_codigo and sublote.maquina_codigo != maquina_id:
        raise HTTPException(status_code=409, detail="La máquina no coincide con la asignación del sublote.")
    if not sublote.maquina_codigo and maquina_id:
        sublote.maquina_codigo = maquina_id
    return sublote


def _actualizar_horas_equipo(db: Session, maquina_codigo: str, segundos: int) -> None:
    equipo = db.query(EquipoPlanta).filter(
        EquipoPlanta.codigo_maquina == maquina_codigo
    ).with_for_update().first()
    if equipo:
        equipo.horas_uso_acumuladas = (
            equipo.horas_uso_acumuladas or Decimal("0")
        ) + Decimal(segundos) / Decimal("3600")


# =============================================================================
# ENDPOINTS OPERATIVOS MES - PUESTO DE TRABAJO OPERARIO CNC
# =============================================================================

@router.post("/setup/iniciar", response_model=RegistroTiempoResponse, status_code=status.HTTP_200_OK)
def iniciar_setup_cnc(payload: IniciarSetupRequest, db: Session = Depends(get_db)):
    """
    Inicia la fase de Setup (Alistamiento) para la operación asignada en el puesto CNC.
    Transiciona el estado de la operación a 'EN_SETUP'.
    """
    operacion = db.query(OperacionOT).filter(OperacionOT.id_operacion == payload.operacion_id).first()
    if not operacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="La operación especificada no existe."
        )

    sublote = _obtener_sublote(db, payload.operacion_id, payload.operario_id, payload.maquina_id)
    equipo = db.query(EquipoPlanta).filter(
        EquipoPlanta.codigo_maquina == sublote.maquina_codigo
    ).with_for_update().first()
    if not equipo:
        raise HTTPException(status_code=422, detail="La máquina asignada debe estar registrada en Mantenimiento de Planta.")
    if equipo.estado_maquina != "OPERATIVA":
        raise HTTPException(status_code=409, detail="La máquina asignada no está operativa.")
    registro_activo = db.query(RegistroTiempoOperario).filter(
        RegistroTiempoOperario.id_sublote == sublote.id_sublote,
        RegistroTiempoOperario.fase_activa.isnot(None),
        RegistroTiempoOperario.fecha_fin_operacion.is_(None),
    ).first()

    if registro_activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un registro de tiempo activo en fase '{registro_activo.fase}'. Debe cerrar la fase actual antes de iniciar Setup."
        )

    ahora = datetime.now(timezone.utc)
    nuevo_registro = RegistroTiempoOperario(
        id_sublote=sublote.id_sublote,
        operario_id=str(payload.operario_id),
        maquina_codigo=sublote.maquina_codigo,
        fecha_apertura_setup=ahora,
        tiempo_setup_segundos=0,
        tiempo_produccion_segundos=0,
        fase_activa="SETUP",
    )
    operacion.estado_operacion = EstadoOperacionEnum.EN_SETUP
    sublote.estado_sublote = EstadoOperacionEnum.EN_SETUP
    try:
        db.add(nuevo_registro)
        db.commit()
        db.refresh(nuevo_registro)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo iniciar el cronómetro de preparación.") from error
    return _respuesta_tiempo(nuevo_registro, payload.operacion_id, "SETUP", ahora)


@router.post("/mecanizado/conmutar", response_model=RegistroTiempoResponse, status_code=status.HTTP_200_OK)
def conmutar_a_mecanizado(payload: ConmutarMecanizadoRequest, db: Session = Depends(get_db)):
    """
    Cierra la fase de Setup y conmuta a la fase de Mecanizado.
    Validación ADR-001 / REQ-PROD-001: Si el tiempo de Setup excede más del 50% el tiempo estimado
    de Setup de la operación, exige de forma obligatoria una justificación técnica.
    """
    operacion = db.query(OperacionOT).filter(OperacionOT.id_operacion == payload.operacion_id).first()
    if not operacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="La operación especificada no existe."
        )

    sublote = _obtener_sublote(db, payload.operacion_id, payload.operario_id)
    registro_setup = db.query(RegistroTiempoOperario).filter(
        RegistroTiempoOperario.id_sublote == sublote.id_sublote,
        RegistroTiempoOperario.operario_id == str(payload.operario_id),
        RegistroTiempoOperario.fase_activa == "SETUP",
        RegistroTiempoOperario.fecha_fin_operacion.is_(None),
    ).with_for_update().first()

    if not registro_setup:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se encontró un proceso de Setup activo para conmutar a Mecanizado."
        )

    ahora = datetime.now(timezone.utc)
    duracion_setup_seg = _segundos_transcurridos(registro_setup.fecha_apertura_setup, ahora)
    plano = db.query(Plano).filter(Plano.id_plano == operacion.id_plano).first()
    tiempo_estimado_setup_seg = (
        max(float(plano.tiempo_estimado_setup_minutos or 0), 0) * 60
        if plano
        else 1800
    )
    limite_tolerancia_seg = tiempo_estimado_setup_seg * 1.5

    if duracion_setup_seg > limite_tolerancia_seg:
        if not payload.justificacion_exceso or not payload.justificacion_exceso.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"❌ Excepción Setup (>50% exceso): El Setup duró {duracion_setup_seg}s (Límite tolerado: {limite_tolerancia_seg}s). Debe ingresar una justificación técnica obligatoria."
            )
        registro_setup.justificacion_exceso = payload.justificacion_exceso.strip()

    registro_setup.tiempo_setup_segundos = duracion_setup_seg
    registro_setup.fecha_inicio_produccion = ahora
    registro_setup.fase_activa = "MECANIZADO"
    operacion.estado_operacion = EstadoOperacionEnum.EN_PRODUCCION
    sublote.estado_sublote = EstadoOperacionEnum.EN_PRODUCCION
    _actualizar_horas_equipo(db, registro_setup.maquina_codigo, duracion_setup_seg)
    try:
        db.commit()
        db.refresh(registro_setup)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo conmutar el cronómetro a mecanizado.") from error
    return _respuesta_tiempo(registro_setup, payload.operacion_id, "MECANIZADO", ahora)


@router.post("/pausa/turno", response_model=RegistroTiempoResponse, status_code=status.HTTP_200_OK)
def pausas_por_turno(payload: PausaTurnoRequest, db: Session = Depends(get_db)):
    """
    Pausa temporalmente la fase activa (Setup o Mecanizado) por cambio/interrupción de turno o descanso.
    """
    sublote = _obtener_sublote(db, payload.operacion_id, payload.operario_id)
    registro_activo = db.query(RegistroTiempoOperario).filter(
        RegistroTiempoOperario.id_sublote == sublote.id_sublote,
        RegistroTiempoOperario.operario_id == str(payload.operario_id),
        RegistroTiempoOperario.fase_activa.isnot(None),
        RegistroTiempoOperario.fecha_fin_operacion.is_(None),
    ).with_for_update().first()

    if not registro_activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay ninguna fase activa corriendo para pausar."
        )

    ahora = datetime.now(timezone.utc)
    fase = registro_activo.fase_activa
    inicio = registro_activo.fecha_apertura_setup if fase == "SETUP" else registro_activo.fecha_inicio_produccion
    duracion_fase_seg = _segundos_transcurridos(inicio or ahora, ahora)
    if fase == "SETUP":
        registro_activo.tiempo_setup_segundos = duracion_fase_seg
    else:
        registro_activo.tiempo_produccion_segundos = duracion_fase_seg
    registro_activo.fecha_fin_operacion = ahora
    registro_activo.fase_activa = None
    registro_activo.motivo_pausa = payload.motivo

    operacion = db.query(OperacionOT).filter(OperacionOT.id_operacion == payload.operacion_id).first()
    if operacion:
        operacion.estado_operacion = EstadoOperacionEnum.PAUSADA
        sublote.estado_sublote = EstadoOperacionEnum.PAUSADA
    _actualizar_horas_equipo(db, registro_activo.maquina_codigo, duracion_fase_seg)
    try:
        db.commit()
        db.refresh(registro_activo)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo pausar el cronómetro.") from error

    return _respuesta_tiempo(registro_activo, payload.operacion_id, fase, inicio or ahora)