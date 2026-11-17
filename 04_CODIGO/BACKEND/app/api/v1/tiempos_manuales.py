# app/api/v1/tiempos_manuales.py
"""
Carga manual de tiempos desde la orden de fabricación (reglas/carga-tiempos-manual.md del proyecto
PRISMA; 33_MIGRACION_CARGA_TIEMPOS_MANUAL.sql).

- Cada fila: proceso de la ruta de la OP, máquina del catálogo, operario asignado a esa máquina en
  Configuración, tiempo de operación en minutos, setup en minutos (opcional) y fecha (hoy si no se
  indica). Se guarda en registro_tiempos_produccion con origen MANUAL, tipo MECANIZADO.
- Registra quien tiene PERM_TIEMPOS_REGISTRAR, salvo OPERARIO; los líderes de unidad, solo en las
  OP que ven (unidad_op.puede_ver_op). El rol se lee de la base en cada consulta.
- Las filas se agregan y se corrigen mientras la OP no esté CERRADA. No se borran: cada corrección
  pide motivo y queda en tiempos_manuales_correcciones con los valores anteriores y los nuevos.
- No se validan solapamientos entre registros.
- Los costos de los tiempos solo salen para COSTOS y JEFE_PRODUCCION (roles.ROLES_COSTOS_TIEMPOS).
- Sin parámetros en la ruta: CAPTURISTA_TIEMPOS solo pasa a rutas fijas (acceso_bd.RUTAS_CAPTURISTA).
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual
from app.core import roles
from app.db.database import get_db
from app.db.models import (
    CentroTrabajo, CorreccionTiempoManual, EquipoPlanta, EstadoOPEnum, MaquinaOperario, OrdenProduccion,
    RegistroTiemposProduccion, Usuario,
)
from app.db.models_produccion import OperacionOT
from app.services import unidad_op
from app.services.acceso_bd import PERMISO_TIEMPOS, puede, rol_en_bd

router = APIRouter()

ORIGEN_MANUAL = "MANUAL"
MENSAJE_SIN_MOTIVO = "Indique el motivo de la corrección."
MENSAJE_OP_CERRADA = "La OP está cerrada: no se agregan ni corrigen tiempos."
MENSAJE_SIN_ACCESO = "Su rol no carga tiempos manuales."


class TiempoManual(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_operacion: UUID
    codigo_maquina: str = Field(..., min_length=1)
    operario_email: str = Field(..., min_length=1)
    minutos_operacion: float = Field(..., gt=0)
    minutos_setup: Optional[float] = Field(None, ge=0)
    fecha: Optional[date] = None


class TiempoManualCrear(TiempoManual):
    codigo_op: str = Field(..., min_length=1)


class TiempoManualCorregir(TiempoManual):
    id_registro: int
    motivo: str = ""


def _carga(db: Session, usuario: dict) -> tuple[Optional[str], bool, bool]:
    """(rol de la base, puede registrar, ve costos)."""
    rol = rol_en_bd(db, usuario["email"])
    registra = rol not in roles.ROLES_SIN_CARGA_MANUAL_TIEMPOS and puede(db, rol, PERMISO_TIEMPOS)
    return rol, registra, rol in roles.ROLES_COSTOS_TIEMPOS


def _op(db: Session, codigo_op: str, rol: Optional[str]) -> OrdenProduccion:
    op = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == codigo_op).first()
    # Una OP fuera del alcance del rol se responde igual que una inexistente
    if not op or not unidad_op.puede_ver_op(rol, op, db):
        raise HTTPException(status_code=404, detail="No se encontró la Orden de Producción indicada.")
    return op


def _abierta(op: OrdenProduccion) -> None:
    if op.estado == EstadoOPEnum.CERRADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=MENSAJE_OP_CERRADA)


def _segundos(minutos: Optional[float]) -> Optional[int]:
    return None if minutos is None else int(round(minutos * 60))


def _minutos(segundos: Optional[int]) -> Optional[float]:
    return None if segundos is None else round(segundos / 60, 2)


def _validar(db: Session, op: OrdenProduccion, datos: TiempoManual) -> tuple[OperacionOT, EquipoPlanta, Usuario]:
    proceso = db.query(OperacionOT).filter(
        OperacionOT.id_operacion == datos.id_operacion, OperacionOT.codigo_op == op.codigo_op,
    ).first()
    if not proceso:
        raise HTTPException(status_code=422, detail="El proceso no pertenece a la ruta de la OP.")
    maquina = db.query(EquipoPlanta).filter(EquipoPlanta.codigo_maquina == datos.codigo_maquina.strip()).first()
    if not maquina:
        raise HTTPException(status_code=422, detail="La estación no está en el catálogo de máquinas.")
    operario = (
        db.query(Usuario)
        .join(MaquinaOperario, MaquinaOperario.id_usuario == Usuario.id_usuario)
        .filter(MaquinaOperario.id_equipo == maquina.id_equipo, Usuario.email == datos.operario_email.strip())
        .first()
    )
    if not operario:
        raise HTTPException(status_code=422, detail="El operario no está asignado a esa máquina en Configuración.")
    return proceso, maquina, operario


def _aplicar(registro: RegistroTiemposProduccion, datos: TiempoManual, maquina: EquipoPlanta, operario: Usuario) -> None:
    fecha = datos.fecha or date.today()
    registro.id_operacion = datos.id_operacion
    registro.estacion_id = maquina.codigo_maquina
    registro.operario_id = operario.email
    registro.segundos_ejecutados = _segundos(datos.minutos_operacion)
    registro.segundos_setup = _segundos(datos.minutos_setup)
    registro.fecha_trabajo = fecha
    # La captura solo trae fecha: inicio a las 00:00 y fin = inicio + tiempo de operación. Los costos
    # usan los segundos, no estas horas
    registro.fecha_hora_inicio = datetime.combine(fecha, time.min, tzinfo=timezone.utc)
    registro.fecha_hora_fin = registro.fecha_hora_inicio + timedelta(seconds=registro.segundos_ejecutados)


def _valores(registro: RegistroTiemposProduccion) -> dict:
    return {
        "id_operacion": str(registro.id_operacion) if registro.id_operacion else None,
        "codigo_maquina": registro.estacion_id,
        "operario_email": registro.operario_id,
        "minutos_operacion": _minutos(registro.segundos_ejecutados),
        "minutos_setup": _minutos(registro.segundos_setup),
        "fecha": registro.fecha_trabajo.isoformat() if registro.fecha_trabajo else None,
    }


def _costo(registro: RegistroTiemposProduccion, maquinas: dict, centros: dict) -> Optional[float]:
    maquina = maquinas.get(registro.estacion_id)
    centro = centros.get(maquina.centro_trabajo_asociado) if maquina else None
    if not centro:
        return None
    costo = (
        Decimal(registro.segundos_ejecutados or 0) * Decimal(centro.tarifa_hora_mecanizado or 0)
        + Decimal(registro.segundos_setup or 0) * Decimal(centro.tarifa_hora_setup or 0)
    ) / Decimal(3600)
    return float(round(costo, 2))


def _fecha(valor):
    return valor.isoformat() if valor else None


def _confirmar(db: Session, mensaje: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=mensaje) from error


@router.get("")
def listar_tiempos(
    codigo_op: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    rol, registra, ve_costos = _carga(db, usuario)
    if not registra and not ve_costos:
        raise HTTPException(status_code=403, detail=MENSAJE_SIN_ACCESO)
    op = _op(db, codigo_op, rol)

    procesos = (
        db.query(OperacionOT).filter(OperacionOT.codigo_op == op.codigo_op)
        .order_by(OperacionOT.secuencia_paso, OperacionOT.nombre_proceso).all()
    )
    nombre_proceso = {proceso.id_operacion: proceso.nombre_proceso for proceso in procesos}
    maquinas = db.query(EquipoPlanta).order_by(EquipoPlanta.codigo_maquina).all()
    asignados = {}
    for id_equipo, email, nombre in (
        db.query(MaquinaOperario.id_equipo, Usuario.email, Usuario.nombre_completo)
        .join(Usuario, Usuario.id_usuario == MaquinaOperario.id_usuario)
        .filter(Usuario.activo.isnot(False)).order_by(Usuario.nombre_completo).all()
    ):
        asignados.setdefault(id_equipo, []).append({"email": email, "nombre": nombre})
    nombres = dict(db.query(Usuario.email, Usuario.nombre_completo).all())

    registros = (
        db.query(RegistroTiemposProduccion)
        .filter(RegistroTiemposProduccion.orden_produccion_id == op.id_op, RegistroTiemposProduccion.origen == ORIGEN_MANUAL)
        .order_by(RegistroTiemposProduccion.fecha_trabajo, RegistroTiemposProduccion.id).all()
    )
    correcciones = {}
    if registros:
        for correccion in (
            db.query(CorreccionTiempoManual)
            .filter(CorreccionTiempoManual.id_registro.in_([registro.id for registro in registros]))
            .order_by(CorreccionTiempoManual.corregido_en, CorreccionTiempoManual.id_correccion).all()
        ):
            correcciones.setdefault(correccion.id_registro, []).append({
                "motivo": correccion.motivo,
                "corregido_por": correccion.corregido_por,
                "corregido_en": _fecha(correccion.corregido_en),
                "valores_anteriores": correccion.valores_anteriores,
            })
    maquina_por_codigo = {maquina.codigo_maquina: maquina for maquina in maquinas}
    centros = {centro.codigo_centro: centro for centro in db.query(CentroTrabajo).all()} if ve_costos else {}

    filas = []
    for registro in registros:
        fila = {
            "id_registro": registro.id,
            **_valores(registro),
            "proceso": nombre_proceso.get(registro.id_operacion),
            "operario_nombre": nombres.get(registro.operario_id),
            "registrado_por": registro.registrado_por,
            "correcciones": correcciones.get(registro.id, []),
        }
        if ve_costos:
            fila["costo"] = _costo(registro, maquina_por_codigo, centros)
        filas.append(fila)

    return {
        "codigo_op": op.codigo_op,
        "op_cerrada": op.estado == EstadoOPEnum.CERRADA,
        "puede_registrar": registra,
        "ve_costos": ve_costos,
        "procesos": [{
            "id_operacion": str(proceso.id_operacion),
            "secuencia": proceso.secuencia_paso,
            "nombre_proceso": proceso.nombre_proceso,
        } for proceso in procesos],
        "maquinas": [{
            "codigo_maquina": maquina.codigo_maquina,
            "nombre": maquina.nombre,
            "operarios": asignados.get(maquina.id_equipo, []),
        } for maquina in maquinas],
        "registros": filas,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def agregar_tiempo(
    datos: TiempoManualCrear,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    rol, registra, _ = _carga(db, usuario)
    if not registra:
        raise HTTPException(status_code=403, detail=MENSAJE_SIN_ACCESO)
    op = _op(db, datos.codigo_op.strip(), rol)
    _abierta(op)
    _, maquina, operario = _validar(db, op, datos)

    registro = RegistroTiemposProduccion(
        orden_produccion_id=op.id_op,
        tipo_tiempo="MECANIZADO",
        origen=ORIGEN_MANUAL,
        registrado_por=usuario["email"],
    )
    _aplicar(registro, datos, maquina, operario)
    db.add(registro)
    _confirmar(db, "No se pudo registrar el tiempo.")
    db.refresh(registro)
    return {"id_registro": registro.id, **_valores(registro)}


@router.post("/corregir")
def corregir_tiempo(
    datos: TiempoManualCorregir,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    rol, registra, _ = _carga(db, usuario)
    if not registra:
        raise HTTPException(status_code=403, detail=MENSAJE_SIN_ACCESO)
    motivo = datos.motivo.strip()
    if not motivo:
        raise HTTPException(status_code=422, detail=MENSAJE_SIN_MOTIVO)
    registro = db.query(RegistroTiemposProduccion).filter(
        RegistroTiemposProduccion.id == datos.id_registro, RegistroTiemposProduccion.origen == ORIGEN_MANUAL,
    ).with_for_update().first()
    op = db.query(OrdenProduccion).filter(OrdenProduccion.id_op == registro.orden_produccion_id).first() if registro else None
    if not op or not unidad_op.puede_ver_op(rol, op, db):
        raise HTTPException(status_code=404, detail="No se encontró el registro de tiempo indicado.")
    _abierta(op)
    _, maquina, operario = _validar(db, op, datos)

    anteriores = _valores(registro)
    _aplicar(registro, datos, maquina, operario)
    nuevos = _valores(registro)
    if nuevos == anteriores:
        db.rollback()
        raise HTTPException(status_code=422, detail="La corrección no cambia ningún dato.")
    db.add(CorreccionTiempoManual(
        id_registro=registro.id,
        valores_anteriores=anteriores,
        valores_nuevos=nuevos,
        motivo=motivo,
        corregido_por=usuario["email"],
    ))
    _confirmar(db, "No se pudo registrar la corrección.")
    return {"id_registro": registro.id, **nuevos}
