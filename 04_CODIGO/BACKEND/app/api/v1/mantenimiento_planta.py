from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    CentroTrabajo,
    EquipoPlanta,
    OrdenMantenimiento,
    SolicitudCompra,
)
from app.db.models_produccion import RegistroTiempoOperario

router = APIRouter()


class EquipoCreate(BaseModel):
    codigo_maquina: str = Field(..., min_length=1, max_length=50)
    nombre: str = Field(..., min_length=1, max_length=150)
    centro_trabajo_asociado: Optional[str] = None
    estado_maquina: str = "OPERATIVA"

    @validator("estado_maquina")
    def validar_estado(cls, value):
        if value not in {"OPERATIVA", "EN_MANTENIMIENTO", "FUERA_DE_SERVICIO"}:
            raise ValueError("Estado de máquina no válido.")
        return value


class OrdenMantenimientoCreate(BaseModel):
    id_equipo: UUID
    tipo: str
    descripcion_falla: str = Field(..., min_length=1)
    repuestos_solicitados_almacen: List[dict] = Field(default_factory=list)
    fecha_programada: Optional[date] = None

    @validator("tipo")
    def validar_tipo(cls, value):
        if value not in {"PREVENTIVO", "CORRECTIVO", "OVERHAUL"}:
            raise ValueError("El tipo debe ser PREVENTIVO, CORRECTIVO u OVERHAUL.")
        return value


class EstadoMantenimientoUpdate(BaseModel):
    estado: str

    @validator("estado")
    def validar_estado(cls, value):
        if value not in {"ABIERTA", "EN_PROCESO", "CERRADA"}:
            raise ValueError("Estado de orden de mantenimiento no válido.")
        return value


def _registrar_repuestos(db: Session, orden: OrdenMantenimiento, equipo: EquipoPlanta) -> None:
    repuestos_actualizados = []
    for index, repuesto in enumerate(orden.repuestos_solicitados_almacen, start=1):
        nombre = str(repuesto.get("nombre_item", repuesto.get("descripcion", ""))).strip()
        cantidad = repuesto.get("cantidad", 1)
        if not nombre or not isinstance(cantidad, (int, float)) or cantidad <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cada repuesto requiere nombre y cantidad positiva.",
            )
        id_solicitud = repuesto.get("id_solicitud")
        try:
            id_solicitud_uuid = UUID(str(id_solicitud)) if id_solicitud else None
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El identificador de requisición asociado al repuesto no es válido.",
            ) from error
        solicitud_existente = (
            db.query(SolicitudCompra)
            .filter(SolicitudCompra.id_solicitud == id_solicitud_uuid)
            .first()
            if id_solicitud_uuid else None
        )
        numero_solicitud = f"{orden.codigo_otm}-{index:03d}"
        if not solicitud_existente:
            solicitud_existente = db.query(SolicitudCompra).filter(
                SolicitudCompra.numero_solicitud.in_([
                    numero_solicitud,
                    f"{orden.codigo_otm}-PR-{index:02d}",
                ])
            ).first()
        if solicitud_existente:
            repuestos_actualizados.append({
                **repuesto,
                "id_solicitud": str(solicitud_existente.id_solicitud),
            })
            continue
        solicitud = SolicitudCompra(
            numero_solicitud=numero_solicitud,
            nombre_item=nombre,
            codigo_sku=repuesto.get("codigo_sku"),
            categoria="REPUESTO_MANTENIMIENTO",
            cantidad_solicitada=float(cantidad),
            unidad_medida=repuesto.get("unidad_medida", "UND"),
            estado="PENDIENTE",
            estado_bom="SOLICITADO",
            observaciones=f"Solicitud de repuesto para la orden {orden.codigo_otm} / {equipo.codigo_maquina}.",
        )
        db.add(solicitud)
        repuestos_actualizados.append({"repuesto": repuesto, "solicitud": solicitud})
    db.flush()
    orden.repuestos_solicitados_almacen = [
        {
            **item["repuesto"],
            "id_solicitud": str(item["solicitud"].id_solicitud),
        } if "solicitud" in item else item
        for item in repuestos_actualizados
    ]


@router.get("/planta/equipos")
def listar_equipos_planta(db: Session = Depends(get_db)):
    equipos = db.query(EquipoPlanta).order_by(EquipoPlanta.codigo_maquina).all()
    ahora = datetime.now(timezone.utc)
    horas_activas = {}
    for registro in db.query(RegistroTiempoOperario).filter(
        RegistroTiempoOperario.fase_activa.isnot(None),
        RegistroTiempoOperario.fecha_fin_operacion.is_(None),
    ).all():
        inicio = registro.fecha_apertura_setup if registro.fase_activa == "SETUP" else registro.fecha_inicio_produccion
        if inicio is None or not registro.maquina_codigo:
            continue
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        segundos = max((ahora - inicio).total_seconds(), 0)
        horas_activas[registro.maquina_codigo] = horas_activas.get(registro.maquina_codigo, 0) + segundos / 3600
    return [
        {
            "id_equipo": str(equipo.id_equipo),
            "codigo_maquina": equipo.codigo_maquina,
            "nombre": equipo.nombre,
            "centro_trabajo_asociado": equipo.centro_trabajo_asociado,
            "horas_uso_acumuladas": round(
                float(equipo.horas_uso_acumuladas or 0) + horas_activas.get(equipo.codigo_maquina, 0),
                2,
            ),
            "cronometro_activo": equipo.codigo_maquina in horas_activas,
            "estado_maquina": equipo.estado_maquina,
        }
        for equipo in equipos
    ]


@router.post("/planta/equipos", status_code=status.HTTP_201_CREATED)
def crear_equipo_planta(equipo_in: EquipoCreate, db: Session = Depends(get_db)):
    codigo = equipo_in.codigo_maquina.strip().upper()
    if db.query(EquipoPlanta).filter(EquipoPlanta.codigo_maquina == codigo).first():
        raise HTTPException(status_code=409, detail="Ya existe un equipo con ese código.")
    centro_codigo = (equipo_in.centro_trabajo_asociado or "").strip() or None
    if centro_codigo and not db.query(CentroTrabajo).filter(CentroTrabajo.codigo_centro == centro_codigo).first():
        raise HTTPException(status_code=422, detail="El centro de trabajo indicado no está registrado.")
    equipo = EquipoPlanta(
        codigo_maquina=codigo,
        nombre=equipo_in.nombre.strip(),
        centro_trabajo_asociado=centro_codigo,
        estado_maquina=equipo_in.estado_maquina,
    )
    try:
        db.add(equipo)
        db.commit()
        db.refresh(equipo)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo crear el equipo de planta.") from error
    return {"id_equipo": str(equipo.id_equipo), "codigo_maquina": equipo.codigo_maquina}


@router.patch("/planta/equipos/{id_equipo}")
def actualizar_equipo_planta(id_equipo: UUID, equipo_in: EquipoCreate, db: Session = Depends(get_db)):
    equipo = db.query(EquipoPlanta).filter(EquipoPlanta.id_equipo == id_equipo).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="No existe el equipo de planta.")
    nuevo_codigo = equipo_in.codigo_maquina.strip().upper()
    duplicado = db.query(EquipoPlanta).filter(
        EquipoPlanta.codigo_maquina == nuevo_codigo,
        EquipoPlanta.id_equipo != id_equipo,
    ).first()
    if duplicado:
        raise HTTPException(status_code=409, detail="Ya existe un equipo con ese código.")
    equipo.codigo_maquina = nuevo_codigo
    equipo.nombre = equipo_in.nombre.strip()
    centro_codigo = (equipo_in.centro_trabajo_asociado or "").strip() or None
    if centro_codigo and not db.query(CentroTrabajo).filter(CentroTrabajo.codigo_centro == centro_codigo).first():
        raise HTTPException(status_code=422, detail="El centro de trabajo indicado no está registrado.")
    equipo.centro_trabajo_asociado = centro_codigo
    equipo.estado_maquina = equipo_in.estado_maquina
    try:
        db.commit()
        db.refresh(equipo)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo actualizar el equipo.") from error
    return {"id_equipo": str(equipo.id_equipo), "codigo_maquina": equipo.codigo_maquina}


@router.get("/planta/ordenes")
def listar_ordenes_mantenimiento(db: Session = Depends(get_db)):
    return [
        {
            "id_otm": str(orden.id_otm),
            "codigo_otm": orden.codigo_otm,
            "id_equipo": str(orden.id_equipo),
            "codigo_maquina": equipo.codigo_maquina,
            "nombre_equipo": equipo.nombre,
            "tipo": orden.tipo,
            "descripcion_falla": orden.descripcion_falla,
            "repuestos_solicitados_almacen": orden.repuestos_solicitados_almacen,
            "fecha_programada": orden.fecha_programada.isoformat() if orden.fecha_programada else None,
            "estado": orden.estado,
        }
        for orden, equipo in db.query(OrdenMantenimiento, EquipoPlanta)
        .join(EquipoPlanta, OrdenMantenimiento.id_equipo == EquipoPlanta.id_equipo)
        .order_by(OrdenMantenimiento.creada_en.desc())
        .all()
    ]


@router.post("/planta/ordenes", status_code=status.HTTP_201_CREATED)
def crear_orden_mantenimiento(orden_in: OrdenMantenimientoCreate, db: Session = Depends(get_db)):
    equipo = db.query(EquipoPlanta).filter(EquipoPlanta.id_equipo == orden_in.id_equipo).with_for_update().first()
    if not equipo:
        raise HTTPException(status_code=404, detail="No existe el equipo de planta.")
    fecha_codigo = datetime.now(timezone.utc).strftime("%Y%m%d")
    codigo = f"OTM-{fecha_codigo}-{datetime.now(timezone.utc).strftime('%H%M%S%f')}"
    orden = OrdenMantenimiento(
        codigo_otm=codigo,
        id_equipo=equipo.id_equipo,
        tipo=orden_in.tipo,
        descripcion_falla=orden_in.descripcion_falla.strip(),
        repuestos_solicitados_almacen=orden_in.repuestos_solicitados_almacen,
        fecha_programada=orden_in.fecha_programada,
    )
    try:
        db.add(orden)
        db.flush()
        _registrar_repuestos(db, orden, equipo)
        db.commit()
        db.refresh(orden)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo crear la orden de mantenimiento.") from error
    return {"id_otm": str(orden.id_otm), "codigo_otm": orden.codigo_otm}


@router.post("/planta/ordenes/{id_otm}/repuestos")
def solicitar_repuestos_orden_mantenimiento(id_otm: UUID, db: Session = Depends(get_db)):
    orden = db.query(OrdenMantenimiento).filter(
        OrdenMantenimiento.id_otm == id_otm
    ).with_for_update().first()
    if not orden:
        raise HTTPException(status_code=404, detail="No existe la orden de mantenimiento.")
    equipo = db.query(EquipoPlanta).filter(
        EquipoPlanta.id_equipo == orden.id_equipo
    ).first()
    if not equipo:
        raise HTTPException(status_code=404, detail="El equipo asociado a la orden ya no existe.")
    if not orden.repuestos_solicitados_almacen:
        raise HTTPException(status_code=409, detail="La orden no tiene repuestos requeridos.")

    try:
        _registrar_repuestos(db, orden, equipo)
        db.commit()
        db.refresh(orden)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudieron solicitar los repuestos a Almacén.") from error

    return {
        "id_otm": str(orden.id_otm),
        "requisiciones": orden.repuestos_solicitados_almacen,
        "mensaje": "Las requisiciones de repuestos están registradas en Compras y Almacén.",
    }


@router.patch("/planta/ordenes/{id_otm}/estado")
def actualizar_estado_orden_mantenimiento(
    id_otm: UUID,
    estado_in: EstadoMantenimientoUpdate,
    db: Session = Depends(get_db),
):
    orden = db.query(OrdenMantenimiento).filter(OrdenMantenimiento.id_otm == id_otm).with_for_update().first()
    if not orden:
        raise HTTPException(status_code=404, detail="No existe la orden de mantenimiento.")
    equipo = db.query(EquipoPlanta).filter(EquipoPlanta.id_equipo == orden.id_equipo).with_for_update().first()
    if orden.estado == "CERRADA" and estado_in.estado != "CERRADA":
        raise HTTPException(status_code=409, detail="Una orden cerrada no se puede reabrir.")
    orden.estado = estado_in.estado
    if estado_in.estado == "EN_PROCESO":
        equipo.estado_maquina = "EN_MANTENIMIENTO"
    elif estado_in.estado == "CERRADA":
        orden.cerrada_en = datetime.now(timezone.utc)
        equipo.estado_maquina = "OPERATIVA"
    try:
        db.commit()
        db.refresh(orden)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo actualizar el estado de la orden.") from error
    return {"id_otm": str(orden.id_otm), "estado": orden.estado}
