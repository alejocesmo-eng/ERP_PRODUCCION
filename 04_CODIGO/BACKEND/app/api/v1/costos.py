from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    CentroTrabajo,
    ConsumoMaterialOP,
    EntregaMaterialOP,
    EquipoPlanta,
    LoteMaterial,
    OrdenProduccion,
    Proyecto,
    RegistroTiemposProduccion,
    ServicioTerceroOP,
)
from app.db.models_produccion import OperacionOT, RegistroTiempoOperario, SubLoteOperacion

router = APIRouter()


def _normalizar_referencia_presupuestal(valor: str) -> str:
    return str(valor or "").strip().casefold()


def _crear_indice_presupuestos(proyecto: Optional[Proyecto]) -> dict:
    indice = {}
    if not proyecto:
        return indice
    for presupuesto in proyecto.presupuestos_componentes or []:
        categoria = str(presupuesto.get("categoria") or "").strip().upper()
        referencia = _normalizar_referencia_presupuestal(
            presupuesto.get("referencia")
        )
        if categoria and referencia:
            indice[(categoria, referencia)] = float(
                presupuesto.get("monto_presupuestado", 0)
            )
    return indice


def _anexar_presupuesto(
    detalle: dict,
    indice_presupuestos: dict,
    categoria: str,
    referencia: str,
    costo_real: float,
) -> None:
    presupuesto = indice_presupuestos.get(
        (categoria, _normalizar_referencia_presupuestal(referencia))
    )
    detalle["presupuesto"] = presupuesto
    detalle["variacion_presupuestal"] = (
        costo_real - presupuesto if presupuesto is not None else None
    )
    detalle["desviacion_presupuestal"] = (
        costo_real > presupuesto if presupuesto is not None else False
    )


@router.get("/liquidar/{codigo_op}")
def liquidar_op(codigo_op: str, db: Session = Depends(get_db)):
    resumen = obtener_costos_op(codigo_op, db)
    cotizacion = resumen["cotizacion_comercial"]
    real = resumen["costos"]["real_total"]
    return {
        **resumen,
        "desviacion_costo": real,
        "margen_real_valor": cotizacion - real if cotizacion is not None else None,
        "margen_real_porcentaje": ((cotizacion - real) / cotizacion * 100) if cotizacion else None,
        "criterio_costeo": "Materiales consumidos + tiempos MES por tarifa del centro + servicios de terceros.",
    }


@router.get("/oee")
def obtener_oee(db: Session = Depends(get_db)):
    desde = datetime.utcnow() - timedelta(days=7)
    registros = (
        db.query(RegistroTiempoOperario, SubLoteOperacion, OperacionOT)
        .join(SubLoteOperacion, RegistroTiempoOperario.id_sublote == SubLoteOperacion.id_sublote)
        .join(OperacionOT, SubLoteOperacion.id_operacion == OperacionOT.id_operacion)
        .filter(RegistroTiempoOperario.creado_en >= desde)
        .all()
    )
    codigos = {operacion.codigo_op for _, _, operacion in registros}
    ordenes = {
        orden.codigo_op: orden
        for orden in db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op.in_(codigos)).all()
    } if codigos else {}

    tiempo_setup = 0
    tiempo_produccion = 0
    tiempo_ideal = 0.0
    piezas_ok = 0
    piezas_scrap = 0
    for registro, sublote, operacion in registros:
        setup = max(registro.tiempo_setup_segundos or 0, 0)
        produccion = max(registro.tiempo_produccion_segundos or 0, 0)
        tiempo_setup += setup
        tiempo_produccion += produccion
        piezas_ok += max(registro.piezas_conformes_ok or 0, 0)
        piezas_scrap += max(registro.piezas_defectuosas_scrap or 0, 0)
        orden = ordenes.get(operacion.codigo_op)
        plano = orden.plano if orden else None
        total_op = max(orden.cantidad_fabricar or 0, 1) if orden else 1
        horas_estimadas = (
            float(plano.tiempo_estimado_mecanizado_horas)
            if plano and plano.tiempo_estimado_mecanizado_horas is not None
            else max(float(plano.tiempo_estimado_valor or 0), 0)
            if plano and str(plano.tiempo_estimado_unidad).upper() in {"HORA", "HORAS", "H"}
            else max(float(plano.tiempo_estimado_valor or 0), 0) / 60
            if plano
            else 0
        )
        tiempo_ideal += horas_estimadas * 3600 * min(
            max(registro.piezas_conformes_ok or 0, 0) / total_op,
            1,
        )

    disponibilidad = tiempo_produccion / (tiempo_produccion + tiempo_setup) if tiempo_produccion + tiempo_setup else 0
    rendimiento = min(tiempo_ideal / tiempo_produccion, 1) if tiempo_produccion else 0
    calidad = piezas_ok / (piezas_ok + piezas_scrap) if piezas_ok + piezas_scrap else 0
    return {
        "periodo_dias": 7,
        "disponibilidad": round(disponibilidad, 4),
        "rendimiento": round(rendimiento, 4),
        "calidad": round(calidad, 4),
        "oee": round(disponibilidad * rendimiento * calidad, 4),
        "tiempo_setup_horas": round(tiempo_setup / 3600, 2),
        "tiempo_produccion_horas": round(tiempo_produccion / 3600, 2),
        "piezas_conformes": piezas_ok,
        "piezas_scrap": piezas_scrap,
        "criterio": "Disponibilidad = producción/(producción + setup); rendimiento compara tiempo ideal estimado y real; calidad usa piezas conformes sobre procesadas.",
    }


class ConsumoMaterialCreate(BaseModel):
    codigo_material: str
    descripcion_material: str
    cantidad: float = Field(..., gt=0)
    unidad_medida: str
    costo_unitario: Decimal = Field(..., ge=0)
    fuente: str = "KARDEX"


class ServicioTerceroCreate(BaseModel):
    proveedor: str
    descripcion: str
    numero_factura: str
    costo: Decimal = Field(..., ge=0)


class CentroTrabajoCreate(BaseModel):
    codigo_centro: str
    tarifa_hora_mecanizado: Decimal = Field(..., ge=0)
    tarifa_hora_setup: Decimal = Field(..., ge=0)
    activo: bool = True


def _obtener_op(db: Session, codigo_op: str) -> OrdenProduccion:
    orden = db.query(OrdenProduccion).filter(
        OrdenProduccion.codigo_op == codigo_op
    ).first()
    if not orden:
        raise HTTPException(status_code=404, detail=f"No existe la OP {codigo_op}.")
    return orden


@router.get("/op/{codigo_op}")
def obtener_costos_op(codigo_op: str, db: Session = Depends(get_db)):
    orden = _obtener_op(db, codigo_op)
    proyecto = db.query(Proyecto).filter(
        Proyecto.id_proyecto == orden.id_proyecto
    ).first()
    indice_presupuestos = _crear_indice_presupuestos(proyecto)

    entregas = db.query(EntregaMaterialOP, LoteMaterial).join(
        LoteMaterial, EntregaMaterialOP.lote_id == LoteMaterial.id
    ).filter(EntregaMaterialOP.op_id == orden.id_op).all()
    consumos = db.query(ConsumoMaterialOP).filter(
        ConsumoMaterialOP.op_id == orden.id_op
    ).all()
    if entregas:
        detalle_materiales = [
            {
                "codigo_material": lote.codigo_material,
                "descripcion": lote.codigo_material,
                "cantidad": entrega.cantidad_entregada,
                "unidad_medida": None,
                "costo_unitario": float(lote.costo_unitario),
                "costo_total": float(lote.costo_unitario) * entrega.cantidad_entregada,
                "fuente": "KARDEX",
                "lote_codigo": lote.codigo_lote,
                "numero_colada": lote.numero_colada,
            }
            for entrega, lote in entregas
        ]
    elif consumos:
        detalle_materiales = [
            {
                "codigo_material": item.codigo_material,
                "descripcion": item.descripcion_material,
                "cantidad": item.cantidad,
                "unidad_medida": item.unidad_medida,
                "costo_unitario": float(item.costo_unitario),
                "costo_total": float(item.costo_unitario) * item.cantidad,
                "fuente": item.fuente,
                "lote_codigo": None,
                "numero_colada": None,
            }
            for item in consumos
        ]
    else:
        detalle_materiales = []
    for item in detalle_materiales:
        _anexar_presupuesto(
            item,
            indice_presupuestos,
            "MATERIA_PRIMA",
            item["codigo_material"],
            item["costo_total"],
        )
    costo_materiales = sum(item["costo_total"] for item in detalle_materiales)

    registros_tiempo = db.query(RegistroTiemposProduccion).filter(
        RegistroTiemposProduccion.orden_produccion_id == orden.id_op
    ).all()
    centros = {
        centro.codigo_centro: centro
        for centro in db.query(CentroTrabajo).filter(CentroTrabajo.activo.is_(True)).all()
    }
    horas_por_centro = {}
    if registros_tiempo:
        for registro in registros_tiempo:
            tipo = registro.tipo_tiempo.upper()
            if tipo not in {"SETUP", "MECANIZADO"}:
                continue
            centro_codigo = registro.estacion_id or "SIN_CENTRO"
            grupo = horas_por_centro.setdefault(
                (centro_codigo, tipo),
                {"horas": 0.0, "tarifa_hora": 0.0, "costo_total": 0.0},
            )
            grupo["horas"] += max(registro.segundos_ejecutados or 0, 0) / 3600
            centro = centros.get(centro_codigo)
            if centro:
                tarifa = centro.tarifa_hora_setup if tipo == "SETUP" else centro.tarifa_hora_mecanizado
                grupo["tarifa_hora"] = float(tarifa)
                grupo["costo_total"] = grupo["horas"] * grupo["tarifa_hora"]
    else:
        registros_mes = (
            db.query(RegistroTiempoOperario, SubLoteOperacion, OperacionOT)
            .join(SubLoteOperacion, RegistroTiempoOperario.id_sublote == SubLoteOperacion.id_sublote)
            .join(OperacionOT, SubLoteOperacion.id_operacion == OperacionOT.id_operacion)
            .filter(OperacionOT.codigo_op == orden.codigo_op)
            .all()
        )
        equipos = {
            equipo.codigo_maquina: equipo
            for equipo in db.query(EquipoPlanta).all()
        }
        ahora = datetime.now(timezone.utc)
        for registro, sublote, _operacion in registros_mes:
            equipo = equipos.get(registro.maquina_codigo or sublote.maquina_codigo or "")
            centro_codigo = (
                equipo.centro_trabajo_asociado
                if equipo and equipo.centro_trabajo_asociado
                else registro.maquina_codigo or sublote.maquina_codigo or "SIN_CENTRO"
            )
            for tipo, segundos in (
                ("SETUP", max(registro.tiempo_setup_segundos or 0, 0)),
                ("MECANIZADO", max(registro.tiempo_produccion_segundos or 0, 0)),
            ):
                if registro.fase_activa == tipo:
                    inicio = (
                        registro.fecha_apertura_setup
                        if tipo == "SETUP"
                        else registro.fecha_inicio_produccion
                    )
                    if inicio:
                        if inicio.tzinfo is None:
                            inicio = inicio.replace(tzinfo=timezone.utc)
                        segundos += max(int((ahora - inicio).total_seconds()), 0)
                if not segundos:
                    continue
                grupo = horas_por_centro.setdefault(
                    (centro_codigo, tipo),
                    {"horas": 0.0, "tarifa_hora": 0.0, "costo_total": 0.0},
                )
                grupo["horas"] += segundos / 3600
                centro = centros.get(centro_codigo)
                if centro:
                    tarifa = centro.tarifa_hora_setup if tipo == "SETUP" else centro.tarifa_hora_mecanizado
                    grupo["tarifa_hora"] = float(tarifa)
                    grupo["costo_total"] = grupo["horas"] * grupo["tarifa_hora"]

    detalle_tiempos = [
        {
            "centro_trabajo": centro,
            "tipo": tipo,
            "horas": datos["horas"],
            "tarifa_hora": datos["tarifa_hora"],
            "costo_total": datos["costo_total"],
            "tarifa_configurada": datos["tarifa_hora"] > 0,
        }
        for (centro, tipo), datos in horas_por_centro.items()
    ]
    for item in detalle_tiempos:
        _anexar_presupuesto(
            item,
            indice_presupuestos,
            "HORAS_MES",
            f"{item['centro_trabajo']}|{item['tipo']}",
            item["costo_total"],
        )
    costo_mano_obra = sum(item["costo_total"] for item in detalle_tiempos)

    servicios = db.query(ServicioTerceroOP).filter(
        ServicioTerceroOP.op_id == orden.id_op
    ).all()
    detalle_servicios = [
        {
            "proveedor": item.proveedor,
            "descripcion": item.descripcion,
            "numero_factura": item.numero_factura,
            "costo": float(item.costo),
        }
        for item in servicios
    ]
    for item in detalle_servicios:
        _anexar_presupuesto(
            item,
            indice_presupuestos,
            "SERVICIO_EXTERNO",
            f"{item['proveedor']}|{item['descripcion']}",
            item["costo"],
        )
    costo_terceros = sum(item["costo"] for item in detalle_servicios)
    costo_real = costo_materiales + costo_mano_obra + costo_terceros
    cotizacion = float(proyecto.cotizacion_total) if proyecto and proyecto.cotizacion_total is not None else None

    return {
        "codigo_op": orden.codigo_op,
        "estado_op": orden.estado.value if hasattr(orden.estado, "value") else orden.estado,
        "cotizacion_comercial": cotizacion,
        "costos": {
            "materiales": costo_materiales,
            "mano_obra": costo_mano_obra,
            "servicios_terceros": costo_terceros,
            "real_total": costo_real,
        },
        "margen_real": {
            "valor": cotizacion - costo_real if cotizacion is not None else None,
            "porcentaje": ((cotizacion - costo_real) / cotizacion * 100)
            if cotizacion else None,
        },
        "detalle_materiales": detalle_materiales,
        "detalle_tiempos": detalle_tiempos,
        "detalle_servicios_terceros": detalle_servicios,
        "alertas": [
            f"Tarifa no configurada para {item['centro_trabajo']} ({item['tipo']})."
            for item in detalle_tiempos
            if not item["tarifa_configurada"]
        ],
    }


@router.post("/op/{codigo_op}/consumos", status_code=status.HTTP_201_CREATED)
def registrar_consumo_material_op(
    codigo_op: str,
    consumo: ConsumoMaterialCreate,
    db: Session = Depends(get_db),
):
    orden = _obtener_op(db, codigo_op)
    registro = ConsumoMaterialOP(
        op_id=orden.id_op,
        codigo_material=consumo.codigo_material,
        descripcion_material=consumo.descripcion_material,
        cantidad=consumo.cantidad,
        unidad_medida=consumo.unidad_medida,
        costo_unitario=consumo.costo_unitario,
        fuente=consumo.fuente,
    )
    try:
        db.add(registro)
        db.commit()
        db.refresh(registro)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar el consumo de material.") from error
    return {"id_consumo": str(registro.id_consumo), "codigo_op": codigo_op}


@router.post("/op/{codigo_op}/servicios-terceros", status_code=status.HTTP_201_CREATED)
def registrar_servicio_tercero_op(
    codigo_op: str,
    servicio: ServicioTerceroCreate,
    db: Session = Depends(get_db),
):
    orden = _obtener_op(db, codigo_op)
    registro = ServicioTerceroOP(op_id=orden.id_op, **servicio.dict())
    try:
        db.add(registro)
        db.commit()
        db.refresh(registro)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar el servicio de tercero.") from error
    return {"id_servicio": str(registro.id_servicio), "codigo_op": codigo_op}


def _guardar_centro_trabajo(
    centro_in: CentroTrabajoCreate,
    db: Session,
    actualizar: bool,
):
    codigo_centro = centro_in.codigo_centro.strip()
    existente = db.query(CentroTrabajo).filter(CentroTrabajo.codigo_centro == codigo_centro).first()
    if existente and not actualizar:
        raise HTTPException(status_code=400, detail="El centro de trabajo ya existe.")
    if actualizar and not existente:
        raise HTTPException(status_code=404, detail="El centro de trabajo no existe.")
    centro = existente or CentroTrabajo(codigo_centro=codigo_centro)
    for campo, valor in centro_in.dict(exclude={"codigo_centro"}).items():
        setattr(centro, campo, valor)
    try:
        db.add(centro)
        db.commit()
        db.refresh(centro)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo guardar la tarifa del centro de trabajo.") from error
    return {
        "codigo_centro": centro.codigo_centro,
        "tarifa_hora_setup": float(centro.tarifa_hora_setup),
        "tarifa_hora_mecanizado": float(centro.tarifa_hora_mecanizado),
    }


@router.post("/centros-trabajo", status_code=status.HTTP_201_CREATED)
def crear_centro_trabajo(centro_in: CentroTrabajoCreate, db: Session = Depends(get_db)):
    return _guardar_centro_trabajo(centro_in, db, actualizar=False)


@router.put("/centros-trabajo/{codigo_centro}")
def actualizar_centro_trabajo(
    codigo_centro: str,
    centro_in: CentroTrabajoCreate,
    db: Session = Depends(get_db),
):
    if codigo_centro.strip() != centro_in.codigo_centro.strip():
        raise HTTPException(status_code=400, detail="El código de centro debe coincidir con el recurso.")
    return _guardar_centro_trabajo(centro_in, db, actualizar=True)
