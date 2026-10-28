from datetime import date
from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.db.database import get_db
from app.db.models import CentroTrabajo, EquipoPlanta, OrdenProduccion
from app.db.models_produccion import OperacionOT, RegistroTiempoOperario, SubLoteOperacion

router = APIRouter()


class ReasignarSublote(BaseModel):
    maquina_codigo: str = Field(..., min_length=1, max_length=50)


@router.get("/carga-maquinas")
def obtener_carga_maquinas(db: Session = Depends(get_db)):
    operaciones = (
        db.query(OperacionOT)
        .options(
            joinedload(OperacionOT.sublotes),
        )
        .all()
    )
    ordenes_abiertas = {
        orden.codigo_op: orden
        for orden in db.query(OrdenProduccion).filter(
            OrdenProduccion.estado.notin_(["CERRADA", "CANCELADA"])
        ).all()
    }
    planos = {
        orden.id_plano: orden.plano
        for orden in ordenes_abiertas.values()
        if orden.plano is not None
    }
    equipos = {
        equipo.codigo_maquina: equipo
        for equipo in db.query(EquipoPlanta).all()
    }
    centros = {
        centro.codigo_centro: centro
        for centro in db.query(CentroTrabajo).filter(CentroTrabajo.activo.is_(True)).all()
    }

    por_centro = {}
    ordenes_programadas = set()
    for operacion in operaciones:
        orden = ordenes_abiertas.get(operacion.codigo_op)
        if orden is None:
            continue
        plano = planos.get(orden.id_plano)
        setup_min = max(float(plano.tiempo_estimado_setup_minutos or 0), 0) if plano else 20.0
        estimado_horas = (
            float(plano.tiempo_estimado_mecanizado_horas)
            if plano and plano.tiempo_estimado_mecanizado_horas is not None
            else max(float(plano.tiempo_estimado_valor or 0), 0)
            if plano and str(plano.tiempo_estimado_unidad).upper() in {"HORA", "HORAS", "H"}
            else max(float(plano.tiempo_estimado_valor or 0), 0) / 60
            if plano
            else 0
        )
        sublotes = operacion.sublotes or []
        if sublotes:
            ordenes_programadas.add(orden.codigo_op)
        piezas_totales = sum(max(sublote.cantidad_asignada or 0, 0) for sublote in sublotes) or 1
        for sublote in sublotes:
            equipo = equipos.get(sublote.maquina_codigo or "")
            centro_codigo = equipo.centro_trabajo_asociado if equipo else sublote.maquina_codigo or "PENDIENTE_ASIGNACION"
            porcion = max(sublote.cantidad_asignada or 0, 0) / piezas_totales
            horas_setup = setup_min / 60 * porcion
            horas_mecanizado = estimado_horas * porcion
            grupo = por_centro.setdefault(
                centro_codigo,
                {
                    "centro_trabajo": centro_codigo,
                    "capacidad_turno_horas": float(centros[centro_codigo].horas_capacidad_turno)
                    if centro_codigo in centros
                    else 8.0,
                    "horas_ocupadas": 0.0,
                    "ordenes": [],
                },
            )
            grupo["horas_ocupadas"] += horas_setup + horas_mecanizado
            grupo["ordenes"].append(
                {
                    "id_sublote": str(sublote.id_sublote),
                    "codigo_op": orden.codigo_op,
                    "codigo_plano": operacion.codigo_plano,
                    "proceso": operacion.nombre_proceso,
                    "maquina_codigo": sublote.maquina_codigo,
                    "cantidad_asignada": sublote.cantidad_asignada,
                    "horas_setup_estimadas": round(horas_setup, 2),
                    "horas_mecanizado_estimadas": round(horas_mecanizado, 2),
                    "fecha_entrega": plano.fecha_entrega_cliente.isoformat()
                    if plano and plano.fecha_entrega_cliente
                    else None,
                    "estado": str(getattr(sublote.estado_sublote, "value", sublote.estado_sublote)),
                }
            )
    for orden in ordenes_abiertas.values():
        if orden.codigo_op in ordenes_programadas:
            continue
        plano = orden.plano
        setup_min = max(float(plano.tiempo_estimado_setup_minutos or 0), 0) if plano else 20.0
        mecanizado_horas = (
            float(plano.tiempo_estimado_mecanizado_horas)
            if plano and plano.tiempo_estimado_mecanizado_horas is not None
            else max(float(plano.tiempo_estimado_valor or 0), 0)
            if plano and str(plano.tiempo_estimado_unidad).upper() in {"HORA", "HORAS", "H"}
            else max(float(plano.tiempo_estimado_valor or 0), 0) / 60
            if plano
            else 0
        )
        centro_codigo = "PENDIENTE_ASIGNACION"
        grupo = por_centro.setdefault(
            centro_codigo,
            {
                "centro_trabajo": centro_codigo,
                "capacidad_turno_horas": 8.0,
                "horas_ocupadas": 0.0,
                "ordenes": [],
            },
        )
        grupo["horas_ocupadas"] += setup_min / 60 + mecanizado_horas
        grupo["ordenes"].append(
            {
                "id_sublote": None,
                "codigo_op": orden.codigo_op,
                "codigo_plano": plano.codigo_plano if plano else "SIN_PLANO",
                "proceso": "Pendiente de asignación",
                "maquina_codigo": None,
                "cantidad_asignada": orden.cantidad_fabricar,
                "horas_setup_estimadas": round(setup_min / 60, 2),
                "horas_mecanizado_estimadas": round(mecanizado_horas, 2),
                "fecha_entrega": plano.fecha_entrega_cliente.isoformat()
                if plano and plano.fecha_entrega_cliente
                else None,
                "estado": "PENDIENTE_ASIGNACION",
            }
        )
    grupos_salida = []
    for grupo in sorted(por_centro.values(), key=lambda item: item["centro_trabajo"]):
        por_fecha = defaultdict(float)
        for orden in grupo["ordenes"]:
            fecha = orden["fecha_entrega"] or "SIN_FECHA"
            por_fecha[fecha] += orden["horas_setup_estimadas"] + orden["horas_mecanizado_estimadas"]
        grupos_salida.append(
            {
                **grupo,
                "horas_ocupadas": round(grupo["horas_ocupadas"], 2),
                "porcentaje_carga": round(
                    grupo["horas_ocupadas"] / grupo["capacidad_turno_horas"] * 100,
                    1,
                )
                if grupo["capacidad_turno_horas"] > 0
                else 0,
                "carga_por_fecha": [
                    {
                        "fecha": fecha,
                        "horas_ocupadas": round(horas, 2),
                        "capacidad_turno_horas": grupo["capacidad_turno_horas"],
                        "porcentaje_carga": round(
                            horas / grupo["capacidad_turno_horas"] * 100,
                            1,
                        )
                        if grupo["capacidad_turno_horas"] > 0
                        else 0,
                    }
                    for fecha, horas in sorted(por_fecha.items())
                ],
            }
        )
    return {
        "centros": grupos_salida,
        "maquinas_disponibles": [
            {
                "codigo_maquina": equipo.codigo_maquina,
                "centro_trabajo": equipo.centro_trabajo_asociado,
                "estado": equipo.estado_maquina,
            }
            for equipo in equipos.values()
            if equipo.estado_maquina == "OPERATIVA"
        ],
        "actualizado_en": date.today().isoformat(),
    }


@router.patch("/carga-maquinas/sublotes/{id_sublote}/maquina")
def reasignar_sublote(
    id_sublote: UUID,
    asignacion: ReasignarSublote,
    db: Session = Depends(get_db),
):
    sublote = (
        db.query(SubLoteOperacion)
        .filter(SubLoteOperacion.id_sublote == id_sublote)
        .with_for_update()
        .first()
    )
    if sublote is None:
        raise HTTPException(status_code=404, detail="No existe el sublote solicitado.")
    if str(getattr(sublote.estado_sublote, "value", sublote.estado_sublote)) in {
        "COMPLETADA",
        "PARCIALMENTE_COMPLETADA",
    }:
        raise HTTPException(status_code=409, detail="No se puede reasignar un sublote ya ejecutado.")
    if db.query(RegistroTiempoOperario).filter(
        RegistroTiempoOperario.id_sublote == sublote.id_sublote,
        RegistroTiempoOperario.fase_activa.isnot(None),
        RegistroTiempoOperario.fecha_fin_operacion.is_(None),
    ).first():
        raise HTTPException(status_code=409, detail="No se puede reasignar una operación con cronómetro activo.")

    destino = db.query(EquipoPlanta).filter(
        EquipoPlanta.codigo_maquina == asignacion.maquina_codigo.strip().upper()
    ).with_for_update().first()
    if destino is None:
        raise HTTPException(status_code=404, detail="La máquina destino no está registrada.")
    if destino.estado_maquina != "OPERATIVA":
        raise HTTPException(status_code=409, detail="La máquina destino no está operativa.")
    actual = (
        db.query(EquipoPlanta)
        .filter(EquipoPlanta.codigo_maquina == sublote.maquina_codigo)
        .first()
        if sublote.maquina_codigo
        else None
    )
    if actual and actual.codigo_maquina != destino.codigo_maquina:
        centro_actual = actual.centro_trabajo_asociado
        centro_destino = destino.centro_trabajo_asociado
        equivalentes = bool(centro_actual and centro_destino and centro_actual == centro_destino)
        if centro_actual and centro_destino and centro_actual != centro_destino:
            grupo_actual = db.query(CentroTrabajo).filter(
                CentroTrabajo.codigo_centro == centro_actual
            ).first()
            grupo_destino = db.query(CentroTrabajo).filter(
                CentroTrabajo.codigo_centro == centro_destino
            ).first()
            equivalentes = bool(
                grupo_actual and grupo_destino
                and grupo_actual.equivalencia == grupo_destino.equivalencia
            )
        if not equivalentes:
            raise HTTPException(status_code=422, detail="La máquina destino no es equivalente al centro de trabajo actual.")
    sublote.maquina_codigo = destino.codigo_maquina
    try:
        db.commit()
        db.refresh(sublote)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo reasignar el sublote.") from error
    return {
        "id_sublote": str(sublote.id_sublote),
        "maquina_codigo": sublote.maquina_codigo,
        "centro_trabajo": destino.centro_trabajo_asociado,
    }
