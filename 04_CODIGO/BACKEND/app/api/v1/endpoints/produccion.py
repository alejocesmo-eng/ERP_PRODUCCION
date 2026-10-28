# app/api/v1/endpoints/produccion.py
from typing import List, Optional, Union
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import get_db
from app.db.models import (
    Plano, 
    OrdenProduccion, 
    RegistroTiemposProduccion, 
    EstadoOPEnum
)
from app.db.models_produccion import (
    OperacionOT, 
    SubLoteOperacion, 
    RegistroTiempoOperario, 
    NotificacionLider,
    EstadoOperacionEnum,
    TipoUnidadPlantaEnum,
    TipoNotificacionEnum
)

router = APIRouter()
cola_router = APIRouter()


# =============================================================================
# SCHEMAS PYDANTIC - PUESTO DE TRABAJO CNC Y CRONÓMETRO DUAL (ADR-001 / REQ-PROD-001)
# =============================================================================

class SetupIniciarRequest(BaseModel):
    orden_id: str = Field(..., description="UUID, ID entero o consecutivo_op de la Orden de Producción")
    operario_id: Optional[str] = Field(None, description="Identificador o nombre del operario CNC")
    estacion_id: Optional[str] = Field("CNC-01", description="Código de máquina o puesto de trabajo")
    tiempo_estandar_minutos: Optional[float] = Field(20.0, ge=0.1, description="Tiempo presupuestado de Setup en minutos")


class MecanizadoIniciarRequest(BaseModel):
    orden_id: str = Field(..., description="UUID, ID entero o consecutivo_op de la Orden de Producción")
    operario_id: Optional[str] = None
    estacion_id: Optional[str] = None
    tiempo_setup_segundos: Optional[int] = Field(None, ge=0, description="Segundos acumulados en Setup")
    tiempo_estandar_minutos: Optional[float] = Field(20.0, ge=0.1, description="Tiempo presupuestado de Setup en minutos")
    observacion_desviacion: Optional[str] = Field(None, description="Justificación obligatoria si Setup excede en >50% el estándar")


class PausarTurnoRequest(BaseModel):
    orden_id: str = Field(..., description="UUID, ID entero o consecutivo_op de la Orden de Producción")
    operario_id: Optional[str] = None
    segundos_adicionales: Optional[int] = Field(0, ge=0, description="Segundos ejecutados antes de la pausa")
    motivo: Optional[str] = Field("Fin de turno laboral", description="Motivo de la pausa de cronómetro")


class SubLoteCrearSchema(BaseModel):
    id_plano: UUID
    codigo_op: str
    codigo_plano: str
    secuencia_paso: int = 10
    nombre_proceso: str
    unidad_planta: TipoUnidadPlantaEnum
    cantidad_sublote: int = Field(..., ge=1)
    operario_nombre: str
    maquina_codigo: str
    instrucciones: Optional[str] = None


class ReordenarSublotesSchema(BaseModel):
    operario_nombre: str = Field(..., min_length=1)
    maquina_codigo: Optional[str] = None
    orden_ids: List[UUID] = Field(..., min_length=1)


class EstadoSubloteUpdateSchema(BaseModel):
    estado_sublote: EstadoOperacionEnum


class FinalizarSubloteSchema(BaseModel):
    id_sublote: UUID
    codigo_op: str
    operario: str = Field(..., min_length=1)
    maquina: str = Field(..., min_length=1)
    piezas_ok: int = Field(..., ge=0)
    piezas_scrap: int = Field(0, ge=0)
    segundos_setup: int = Field(0, ge=0)
    segundos_produccion: int = Field(0, ge=0)
    segundos_pausa: int = Field(0, ge=0)
    motivo_pausa: Optional[str] = None
    novedades: Optional[str] = None


class ReporteCierreOperarioSchema(BaseModel):
    id_sublote: UUID
    operario_id: str
    maquina_codigo: str
    duracion_setup_segundos: int
    duracion_produccion_segundos: int
    piezas_ok: int = Field(..., ge=0)
    piezas_scrap: int = Field(0, ge=0)
    comentarios_novedades: Optional[str] = None


class NotificacionResponseSchema(BaseModel):
    id_notificacion: UUID
    unidad_planta: TipoUnidadPlantaEnum
    tipo_notificacion: TipoNotificacionEnum
    codigo_op: str
    codigo_plano: str
    operario_nombre: str
    maquina_codigo: str
    piezas_reportadas: int
    mensaje: str
    leida: int
    creado_en: datetime

    class Config:
        from_attributes = True


# =============================================================================
# FUNCIONES AUXILIARES DE BÚSQUEDA
# =============================================================================

def _obtener_op_por_identificador(db: Session, orden_id: str) -> OrdenProduccion:
    """Busca la OP por UUID, ID entero o código/consecutivo."""
    # 1. Intentar por UUID directo
    try:
        val_uuid = UUID(orden_id)
        op = db.query(OrdenProduccion).filter(OrdenProduccion.id_op == val_uuid).first()
        if op:
            return op
    except (ValueError, AttributeError):
        pass

    # 2. Intentar por ID entero si la tabla tiene id
    if hasattr(OrdenProduccion, 'id') and orden_id.isdigit():
        op = db.query(OrdenProduccion).filter(OrdenProduccion.id == int(orden_id)).first()
        if op:
            return op

    # 3. Intentar por código / consecutivo de OP
    op = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == str(orden_id)).first()
    if op:
        return op

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Orden de Producción con identificador '{orden_id}' no encontrada."
    )


# =============================================================================
# BLOQUE 1: PUESTO DE TRABAJO CNC Y CONTROL DE TIEMPOS DUAL (ADR-001 / REQ-PROD-001)
# =============================================================================

@router.post("/setup/iniciar", status_code=status.HTTP_200_OK)
def iniciar_setup_op(data: SetupIniciarRequest, db: Session = Depends(get_db)):
    """
    TC-01: Inicia el cronómetro de alistamiento (tipo_tiempo = 'SETUP').
    Registra el timestamp inicial en PostgreSQL y actualiza el estado de la OP a 'EN_PROCESO_CNC'.
    """
    op = _obtener_op_por_identificador(db, data.orden_id)

    # 1. Transición de estado a 'EN_PROCESO_CNC'
    op.estado = EstadoOPEnum.EN_PROCESO_CNC
    if hasattr(op, 'tiempo_setup_estandar_minutos') and data.tiempo_estandar_minutos:
        op.tiempo_setup_estandar_minutos = data.tiempo_estandar_minutos

    # 2. Registrar apertura de Setup en la tabla registro_tiempos_produccion
    ahora = datetime.now(timezone.utc)
    registro = RegistroTiemposProduccion(
        orden_produccion_id=op.id_op,
        operario_id=data.operario_id or "operario1",
        estacion_id=data.estacion_id or "CNC-01",
        tipo_tiempo="SETUP",
        fecha_hora_inicio=ahora,
        segundos_ejecutados=0,
        pausado_por_turno=False
    )

    try:
        db.add(registro)
        db.commit()
        db.refresh(op)
        db.refresh(registro)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al iniciar Setup en base de datos: {str(e)}"
        )

    return {
        "status": "ok",
        "mensaje": "Inicio de alistamiento Setup registrado correctamente.",
        "orden_id": str(op.id_op),
        "codigo_op": op.codigo_op,
        "estado_op": op.estado.value if hasattr(op.estado, 'value') else str(op.estado),
        "tipo_tiempo": registro.tipo_tiempo,
        "fecha_hora_inicio": registro.fecha_hora_inicio,
        "registro_id": registro.id
    }


@router.post("/mecanizado/iniciar", status_code=status.HTTP_200_OK)
def iniciar_mecanizado_op(data: MecanizadoIniciarRequest, db: Session = Depends(get_db)):
    """
    TC-03 / ADR-001: Valida el tiempo acumulado en Setup.
    Si el tiempo excede el 50% del estándar (>150% del tiempo previsto):
    - Requiere obligatoriamente el campo 'observacion_desviacion'.
    - Si falta, retorna HTTP 400 Bad Request.
    - Si se incluye, guarda la justificación y conmuta a 'MECANIZADO'.
    """
    op = _obtener_op_por_identificador(db, data.orden_id)

    # 1. Obtener el registro de Setup activo o más reciente
    reg_setup = db.query(RegistroTiemposProduccion).filter(
        RegistroTiemposProduccion.orden_produccion_id == op.id_op,
        RegistroTiemposProduccion.tipo_tiempo == "SETUP"
    ).order_by(RegistroTiemposProduccion.fecha_hora_inicio.desc()).first()

    ahora = datetime.now(timezone.utc)

    # 2. Calcular los segundos acumulados en Setup
    if data.tiempo_setup_segundos is not None:
        segundos_acumulados = data.tiempo_setup_segundos
    elif reg_setup and reg_setup.fecha_hora_inicio:
        inicio = reg_setup.fecha_hora_inicio
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        elapsed = (ahora - inicio).total_seconds()
        segundos_acumulados = int((reg_setup.segundos_ejecutados or 0) + max(0, elapsed))
    else:
        segundos_acumulados = 0

    # 3. Calcular umbral de desviación (>50% sobre el estándar)
    estandar_minutos = data.tiempo_estandar_minutos or getattr(op, 'tiempo_setup_estandar_minutos', 20.0) or 20.0
    segundos_estandar = estandar_minutos * 60.0
    umbral_limite = segundos_estandar * 1.5  # 150% del estándar (exceso > 50%)

    # 4. Validar excepción de Setup
    if segundos_acumulados > umbral_limite:
        if not data.observacion_desviacion or not data.observacion_desviacion.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El tiempo de Setup acumulado ({segundos_acumulados}s) superó en más del 50% "
                    f"el estándar presupuestado ({int(segundos_estandar)}s). "
                    f"Se requiere obligatoriamente el campo 'observacion_desviacion' según ADR-001."
                )
            )

    # 5. Cerrar registro de Setup con los segundos ejecutados y la justificación
    if reg_setup:
        reg_setup.fecha_hora_fin = ahora
        reg_setup.segundos_ejecutados = segundos_acumulados
        if data.observacion_desviacion:
            reg_setup.observacion_desviacion = data.observacion_desviacion.strip()

    # 6. Abrir nuevo ciclo de tiempo 'MECANIZADO'
    nuevo_registro = RegistroTiemposProduccion(
        orden_produccion_id=op.id_op,
        operario_id=data.operario_id or (reg_setup.operario_id if reg_setup else "operario1"),
        estacion_id=data.estacion_id or (reg_setup.estacion_id if reg_setup else "CNC-01"),
        tipo_tiempo="MECANIZADO",
        fecha_hora_inicio=ahora,
        segundos_ejecutados=0,
        pausado_por_turno=False
    )

    try:
        db.add(nuevo_registro)
        db.commit()
        db.refresh(op)
        db.refresh(nuevo_registro)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al conmutar a Mecanizado: {str(e)}"
        )

    return {
        "status": "ok",
        "mensaje": "Conmutación a MECANIZADO registrada correctamente.",
        "orden_id": str(op.id_op),
        "codigo_op": op.codigo_op,
        "estado_op": op.estado.value if hasattr(op.estado, 'value') else str(op.estado),
        "tipo_tiempo": nuevo_registro.tipo_tiempo,
        "tiempo_setup_acumulado_segundos": segundos_acumulados,
        "desviacion_detectada": segundos_acumulados > umbral_limite,
        "observacion_desviacion": data.observacion_desviacion,
        "registro_id": nuevo_registro.id
    }


@router.post("/pausar-turno", status_code=status.HTTP_200_OK)
def pausar_turno_op(data: PausarTurnoRequest, db: Session = Depends(get_db)):
    """
    Registra la pausa de tiempo en el puesto CNC por fin de jornada o cambio de turno,
    conservando el acumulado de segundos para el siguiente turno.
    """
    op = _obtener_op_por_identificador(db, data.orden_id)

    # Buscar el registro de cronómetro activo más reciente
    registro = db.query(RegistroTiemposProduccion).filter(
        RegistroTiemposProduccion.orden_produccion_id == op.id_op,
        RegistroTiemposProduccion.fecha_hora_fin.is_(None)
    ).order_by(RegistroTiemposProduccion.fecha_hora_inicio.desc()).first()

    if not registro:
        # Fallback al último registro
        registro = db.query(RegistroTiemposProduccion).filter(
            RegistroTiemposProduccion.orden_produccion_id == op.id_op
        ).order_by(RegistroTiemposProduccion.fecha_hora_inicio.desc()).first()

    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró cronómetro activo para pausar en esta orden de producción."
        )

    ahora = datetime.now(timezone.utc)
    inicio = registro.fecha_hora_inicio
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    
    segundos_delta = int((ahora - inicio).total_seconds()) if not registro.pausado_por_turno else 0
    segundos_totales = (registro.segundos_ejecutados or 0) + max(0, segundos_delta) + (data.segundos_adicionales or 0)

    registro.segundos_ejecutados = segundos_totales
    registro.pausado_por_turno = True
    registro.fecha_hora_fin = ahora
    if data.motivo:
        if registro.observacion_desviacion:
            registro.observacion_desviacion += f" | Pausa: {data.motivo}"
        else:
            registro.observacion_desviacion = f"Pausa: {data.motivo}"

    try:
        db.commit()
        db.refresh(registro)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al pausar turno: {str(e)}"
        )

    return {
        "status": "ok",
        "mensaje": "Pausa de turno registrada correctamente. Contador de segundos preservado.",
        "orden_id": str(op.id_op),
        "tipo_tiempo": registro.tipo_tiempo,
        "segundos_conservados": registro.segundos_ejecutados,
        "pausado_por_turno": registro.pausado_por_turno
    }


# =============================================================================
# BLOQUE 2: OPERACIONES MES (SUB-LOTES Y NOTIFICACIONES DE PLANTA)
# =============================================================================

@cola_router.get("/sublotes", status_code=status.HTTP_200_OK)
def listar_sublotes(
    area: Optional[str] = Query(None),
    maquina: Optional[str] = Query(None),
    operario_nombre: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Consulta trabajos activos y pendientes ordenados por operario, estación y prioridad."""
    query = db.query(SubLoteOperacion).options(joinedload(SubLoteOperacion.operacion))
    query = query.filter(SubLoteOperacion.estado_sublote.in_([
        EstadoOperacionEnum.PENDIENTE,
        EstadoOperacionEnum.PENDIENTE_ASIGNACION,
        EstadoOperacionEnum.EN_COLA,
        EstadoOperacionEnum.EN_SETUP,
        EstadoOperacionEnum.EN_PRODUCCION,
        EstadoOperacionEnum.PAUSADA,
    ]))
    if maquina:
        query = query.filter(SubLoteOperacion.maquina_codigo == maquina)
    if operario_nombre:
        query = query.filter(SubLoteOperacion.operario_nombre == operario_nombre)
    if area:
        query = query.join(SubLoteOperacion.operacion).filter(
            OperacionOT.unidad_planta == area
        )
    sublotes = query.order_by(
        SubLoteOperacion.operario_nombre,
        SubLoteOperacion.prioridad_cola,
        SubLoteOperacion.id_sublote,
    ).all()
    respuesta = []
    for sublote in sublotes:
        operacion = sublote.operacion
        plano = db.query(Plano).filter(Plano.id_plano == operacion.id_plano).first()
        respuesta.append({
            "id_sublote": sublote.id_sublote,
            "id_operacion": operacion.id_operacion,
            "codigo_op": operacion.codigo_op,
            "codigo_plano": operacion.codigo_plano,
            "numero_pedido": None,
            "detalle_pieza": plano.material_requerido if plano else operacion.codigo_plano,
            "sublote_tag": sublote.numero_sublote,
            "cantidad_asignada": sublote.cantidad_asignada,
            "nombre_proceso": operacion.nombre_proceso,
            "secuencia_paso": operacion.secuencia_paso,
            "archivo_url": plano.archivo_url if plano else None,
            "instrucciones": plano.causa_espera if plano else None,
            "operario_id": sublote.operario_id,
            "operario_nombre": sublote.operario_nombre,
            "maquina_codigo": sublote.maquina_codigo,
            "estado_sublote": sublote.estado_sublote.value if hasattr(sublote.estado_sublote, "value") else sublote.estado_sublote,
            "prioridad_cola": sublote.prioridad_cola,
            "unidad_planta": operacion.unidad_planta.value if hasattr(operacion.unidad_planta, "value") else operacion.unidad_planta,
        })
    return respuesta


@cola_router.post("/sublotes/reordenar", status_code=status.HTTP_200_OK)
def reordenar_sublotes(payload: ReordenarSublotesSchema, db: Session = Depends(get_db)):
    """Guarda atómicamente la secuencia de espera de un operario en una estación."""
    consulta = db.query(SubLoteOperacion).filter(
        SubLoteOperacion.operario_nombre == payload.operario_nombre,
        SubLoteOperacion.estado_sublote.in_([
            EstadoOperacionEnum.PENDIENTE,
            EstadoOperacionEnum.PENDIENTE_ASIGNACION,
            EstadoOperacionEnum.EN_COLA,
        ]),
    )
    if payload.maquina_codigo:
        consulta = consulta.filter(SubLoteOperacion.maquina_codigo == payload.maquina_codigo)
    sublotes = consulta.with_for_update().all()
    ids_existentes = {sublote.id_sublote for sublote in sublotes}
    ids_solicitados = payload.orden_ids
    if len(ids_solicitados) != len(set(ids_solicitados)) or set(ids_solicitados) != ids_existentes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cola cambió. Actualice la vista y vuelva a ordenar los sublotes.",
        )
    por_id = {sublote.id_sublote: sublote for sublote in sublotes}
    try:
        for prioridad, id_sublote in enumerate(ids_solicitados, start=1):
            por_id[id_sublote].prioridad_cola = prioridad
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo guardar el orden de la cola.") from error
    return {
        "operario_nombre": payload.operario_nombre,
        "maquina_codigo": payload.maquina_codigo,
        "orden_ids": ids_solicitados,
        "mensaje": "La prioridad de los sublotes quedó guardada.",
    }


@cola_router.patch("/sublotes/{id_sublote}/estado", status_code=status.HTTP_200_OK)
def actualizar_estado_sublote(
    id_sublote: UUID,
    payload: EstadoSubloteUpdateSchema,
    db: Session = Depends(get_db),
):
    sublote = db.query(SubLoteOperacion).filter(
        SubLoteOperacion.id_sublote == id_sublote
    ).with_for_update().first()
    if not sublote:
        raise HTTPException(status_code=404, detail="No existe el sublote solicitado.")

    estado_actual = sublote.estado_sublote
    transiciones_permitidas = {
        EstadoOperacionEnum.PENDIENTE: {EstadoOperacionEnum.EN_SETUP},
        EstadoOperacionEnum.PENDIENTE_ASIGNACION: {EstadoOperacionEnum.EN_SETUP},
        EstadoOperacionEnum.EN_COLA: {EstadoOperacionEnum.EN_SETUP},
        EstadoOperacionEnum.EN_SETUP: {
            EstadoOperacionEnum.EN_PRODUCCION,
            EstadoOperacionEnum.PAUSADA,
        },
        EstadoOperacionEnum.EN_PRODUCCION: {EstadoOperacionEnum.PAUSADA},
        EstadoOperacionEnum.PAUSADA: {EstadoOperacionEnum.EN_PRODUCCION},
    }
    if payload.estado_sublote not in transiciones_permitidas.get(estado_actual, set()):
        raise HTTPException(
            status_code=409,
            detail="La transición de estado solicitada no está permitida para este sublote.",
        )

    sublote.estado_sublote = payload.estado_sublote
    try:
        db.commit()
        db.refresh(sublote)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo actualizar el estado del sublote.") from error
    return {
        "id_sublote": str(sublote.id_sublote),
        "estado_sublote": sublote.estado_sublote.value,
    }


@cola_router.post("/sublotes/crear", status_code=status.HTTP_201_CREATED)
def crear_sublote_programado(data: SubLoteCrearSchema, db: Session = Depends(get_db)):
    """Permite al Líder fraccionar una OT en sub-lotes asignados a máquinas/operarios."""
    operacion = db.query(OperacionOT).filter(
        OperacionOT.id_plano == data.id_plano,
        OperacionOT.secuencia_paso == data.secuencia_paso
    ).first()

    if not operacion:
        plano_db = db.query(Plano).filter(Plano.id_plano == data.id_plano).first()
        cant_total = plano_db.tiempo_estimado_valor if plano_db else data.cantidad_sublote

        operacion = OperacionOT(
            id_operacion=uuid4(),
            id_plano=data.id_plano,
            codigo_op=data.codigo_op,
            codigo_plano=data.codigo_plano,
            secuencia_paso=data.secuencia_paso,
            unidad_planta=data.unidad_planta,
            nombre_proceso=data.nombre_proceso,
            cantidad_total_orden=cant_total,
            estado_operacion=EstadoOperacionEnum.EN_COLA
        )
        db.add(operacion)
        db.flush()

    conteo = db.query(SubLoteOperacion).filter(SubLoteOperacion.id_operacion == operacion.id_operacion).count()
    prioridad = db.query(SubLoteOperacion.prioridad_cola).filter(
        SubLoteOperacion.operario_nombre == data.operario_nombre,
        SubLoteOperacion.maquina_codigo == data.maquina_codigo,
        SubLoteOperacion.estado_sublote.in_([
            EstadoOperacionEnum.PENDIENTE,
            EstadoOperacionEnum.PENDIENTE_ASIGNACION,
            EstadoOperacionEnum.EN_COLA,
        ]),
    ).order_by(SubLoteOperacion.prioridad_cola.desc()).with_for_update().first()
    
    nuevo_sublote = SubLoteOperacion(
        id_sublote=uuid4(),
        id_operacion=operacion.id_operacion,
        numero_sublote=f"SUB-0{conteo + 1}",
        cantidad_asignada=data.cantidad_sublote,
        operario_nombre=data.operario_nombre,
        operario_id=data.operario_nombre.lower().replace(" ", "_"),
        maquina_codigo=data.maquina_codigo,
        prioridad_cola=(prioridad[0] if prioridad else 0) + 1,
        estado_sublote=EstadoOperacionEnum.EN_COLA
    )
    
    db.add(nuevo_sublote)
    db.commit()
    
    return {
        "status": "ok",
        "mensaje": f"Sub-lote de {data.cantidad_sublote} UND enviado a la tablet de {data.operario_nombre} [{data.maquina_codigo}].",
        "id_sublote": nuevo_sublote.id_sublote
    }


@cola_router.post("/sublotes/finalizar", status_code=status.HTTP_200_OK)
def finalizar_sublote(payload: FinalizarSubloteSchema, db: Session = Depends(get_db)):
    sublote = db.query(SubLoteOperacion).filter(
        SubLoteOperacion.id_sublote == payload.id_sublote
    ).with_for_update().first()
    if not sublote:
        raise HTTPException(status_code=404, detail="No se encontró el sublote indicado.")
    if sublote.estado_sublote == EstadoOperacionEnum.COMPLETADA:
        raise HTTPException(status_code=409, detail="El sublote ya fue registrado como terminado.")
    if payload.piezas_ok + payload.piezas_scrap > sublote.cantidad_asignada:
        raise HTTPException(status_code=422, detail="Las piezas conformes y rechazadas superan la cantidad asignada.")
    operacion = db.query(OperacionOT).filter(
        OperacionOT.id_operacion == sublote.id_operacion
    ).with_for_update().first()
    if not operacion or operacion.codigo_op != payload.codigo_op:
        raise HTTPException(status_code=409, detail="El código de orden no corresponde al sublote.")
    ahora = datetime.now(timezone.utc)
    registro = RegistroTiempoOperario(
        id_sublote=sublote.id_sublote,
        operario_id=sublote.operario_id or payload.operario,
        maquina_codigo=sublote.maquina_codigo or payload.maquina,
        tiempo_setup_segundos=payload.segundos_setup,
        tiempo_produccion_segundos=payload.segundos_produccion,
        fecha_fin_operacion=ahora,
        piezas_conformes_ok=payload.piezas_ok,
        piezas_defectuosas_scrap=payload.piezas_scrap,
        es_entrega_parcial=int(payload.piezas_ok + payload.piezas_scrap < sublote.cantidad_asignada),
        comentarios_operario=payload.novedades,
        motivo_pausa=payload.motivo_pausa,
    )
    sublote.estado_sublote = (
        EstadoOperacionEnum.COMPLETADA
        if payload.piezas_ok + payload.piezas_scrap >= sublote.cantidad_asignada
        else EstadoOperacionEnum.PARCIALMENTE_COMPLETADA
    )
    operacion.cantidad_acumulada_ok = (operacion.cantidad_acumulada_ok or 0) + payload.piezas_ok
    if operacion.cantidad_acumulada_ok >= operacion.cantidad_total_orden:
        operacion.estado_operacion = EstadoOperacionEnum.COMPLETADA
    notificacion = NotificacionLider(
        id_sublote=sublote.id_sublote,
        unidad_planta=operacion.unidad_planta,
        tipo_notificacion=(
            TipoNotificacionEnum.PIEZAS_DEFECTUOSAS
            if payload.piezas_scrap
            else TipoNotificacionEnum.ENTREGA_PARCIAL
            if sublote.estado_sublote == EstadoOperacionEnum.PARCIALMENTE_COMPLETADA
            else TipoNotificacionEnum.SUBLOTE_COMPLETADO
        ),
        titulo=f"Reporte de planta · OP {operacion.codigo_op}",
        mensaje=f"{payload.operario} reportó {payload.piezas_ok} piezas conformes y {payload.piezas_scrap} rechazadas en {payload.maquina}.",
        codigo_op=operacion.codigo_op,
        codigo_plano=operacion.codigo_plano,
        operario_nombre=payload.operario,
        maquina_codigo=payload.maquina,
        piezas_reportadas=payload.piezas_ok,
    )
    try:
        db.add_all([registro, notificacion])
        db.commit()
        db.refresh(registro)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar el cierre del sublote.") from error
    return {"mensaje": "El reporte de producción quedó registrado.", "id_registro": registro.id_registro}


@router.post("/reportar-cierre", status_code=status.HTTP_200_OK)
def reportar_cierre_operario(reporte: ReporteCierreOperarioSchema, db: Session = Depends(get_db)):
    """Recibe el cierre de sub-lote con piezas conformes y scrap."""
    sublote = db.query(SubLoteOperacion).filter(SubLoteOperacion.id_sublote == reporte.id_sublote).first()
    if not sublote:
        raise HTTPException(status_code=404, detail="Sub-Lote no encontrado en el sistema MES.")

    registro_tiempo = RegistroTiempoOperario(
        id_registro=uuid4(),
        id_sublote=sublote.id_sublote,
        operario_id=reporte.operario_id,
        maquina_codigo=reporte.maquina_codigo,
        tiempo_setup_segundos=reporte.duracion_setup_segundos,
        tiempo_produccion_segundos=reporte.duracion_produccion_segundos,
        piezas_conformes_ok=reporte.piezas_ok,
        piezas_defectuosas_scrap=reporte.piezas_scrap,
        comentarios_operario=reporte.comentarios_novedades,
        fecha_fin_operacion=datetime.now(timezone.utc)
    )
    db.add(registro_tiempo)

    sublote.estado_sublote = EstadoOperacionEnum.COMPLETADA
    
    operacion = db.query(OperacionOT).filter(OperacionOT.id_operacion == sublote.id_operacion).first()
    if operacion:
        operacion.cantidad_acumulada_ok += reporte.piezas_ok
        if operacion.cantidad_acumulada_ok >= operacion.cantidad_total_orden:
            operacion.estado_operacion = EstadoOperacionEnum.COMPLETADA

    notificacion = NotificacionLider(
        id_notificacion=uuid4(),
        id_sublote=sublote.id_sublote,
        unidad_planta=operacion.unidad_planta if operacion else TipoUnidadPlantaEnum.MECANIZADOS,
        tipo_notificacion=TipoNotificacionEnum.SUBLOTE_COMPLETADO,
        titulo=f"Proceso Finalizado - OT-{operacion.codigo_op if operacion else 'N/A'}",
        mensaje=f"El operario {sublote.operario_nombre} completó {reporte.piezas_ok} piezas OK en {reporte.maquina_codigo}.",
        codigo_op=operacion.codigo_op if operacion else "N/A",
        codigo_plano=operacion.codigo_plano if operacion else "N/A",
        operario_nombre=sublote.operario_nombre,
        maquina_codigo=reporte.maquina_codigo,
        piezas_reportadas=reporte.piezas_ok
    )
    db.add(notificacion)
    db.commit()

    return {
        "status": "exito",
        "mensaje": "Reporte de producción registrado e informado al Líder de Planta."
    }


@router.get("/notificaciones/{area}", response_model=List[NotificacionResponseSchema])
def listar_notificaciones_area(area: TipoUnidadPlantaEnum, db: Session = Depends(get_db)):
    """Obtiene la lista de alertas emitidas desde las tablets para la unidad de planta."""
    return db.query(NotificacionLider).filter(
        NotificacionLider.unidad_planta == area
    ).order_by(NotificacionLider.creado_en.desc()).all()
