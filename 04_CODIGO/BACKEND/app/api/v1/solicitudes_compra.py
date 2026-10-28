from typing import List, Optional, Union
from uuid import UUID, uuid4
from datetime import date, datetime
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import get_db
from app.db.models import (
    ArticuloInventario,
    BOMListaMateriales,
    EjecucionMRP,
    EstadoOPEnum,
    LoteMaterial,
    MovimientoInventario,
    OrdenProduccion,
    Plano,
    Proyecto,
    RequisicionMRP,
    RetalSobrante,
    SolicitudCompra as SolicitudCompraORM,
    TrazabilidadRequisicionMRP,
)

router = APIRouter()

# =============================================================================
# BLOQUE 1: SCHEMAS PYDANTIC ADAPTABLES
# =============================================================================

class EstadoMaterialBOMEnum(str, Enum):
    SIN_SOLICITAR = "SIN_SOLICITAR"
    SOLICITADO = "SOLICITADO"
    EN_COMPRA = "EN_COMPRA"
    EN_ALMACEN = "EN_ALMACEN"
    ENTREGADO = "ENTREGADO"

class SolicitudItemCreate(BaseModel):
    codigo_articulo: Optional[str] = "TEXTO_LIBRE"
    descripcion_material: Optional[str] = None
    descripcion: Optional[str] = None  # Soporte para alias de frontend
    cantidad: float = Field(1.0, ge=0.01)
    unidad_medida: Optional[str] = "UND"
    unidad: Optional[str] = None  # Soporte para alias de frontend
    codigo_plano: Optional[str] = None

    @validator('descripcion_material', always=True)
    def consolidar_descripcion(cls, v, values):
        return v or values.get('descripcion') or "Materia Prima / Insumo General"

    @validator('unidad_medida', always=True)
    def consolidar_unidad(cls, v, values):
        return v or values.get('unidad') or "UND"

class SolicitudCompraCreate(BaseModel):
    numero_solicitud: Optional[str] = None
    solicitante_nombre: Optional[str] = "Ing. Carlos Ruiz"
    solicitante: Optional[str] = None
    departamento_area: Optional[str] = "Diseño e Ingeniería"
    departamento: Optional[str] = None
    id_proyecto: Optional[Union[UUID, str]] = None
    numero_pedido: Optional[str] = None
    codigo_op: Optional[str] = None
    codigo_plano: Optional[str] = None
    fecha_necesaria: Optional[date] = None
    comentarios: Optional[str] = None
    items: Optional[List[SolicitudItemCreate]] = None
    insumos: Optional[List[SolicitudItemCreate]] = None  # Soporte para alias de frontend

    @validator('id_proyecto', pre=True)
    def sanitizar_uuid(cls, v):
        if not v or isinstance(v, str) and not len(v) == 36:
            return None
        return v

    @validator('fecha_necesaria', pre=True)
    def parse_fechas(cls, v):
        if v == "" or v is None:
            return None
        return v

class SolicitudCompraUpdate(BaseModel):
    estado: Optional[str] = None
    estado_bom: Optional[EstadoMaterialBOMEnum] = None
    comentarios: Optional[str] = None

class SolicitudCompraResponse(BaseModel):
    id_solicitud: UUID
    numero_solicitud: str
    solicitante_nombre: str
    departamento_area: str
    id_proyecto: Optional[UUID] = None
    numero_pedido: Optional[str] = "S/P"
    codigo_op: Optional[str] = "GENERAL"
    codigo_plano: Optional[str] = "N/A"
    codigo_sku: Optional[str] = None
    descripcion_resumen: str
    cantidad_piezas: float
    cantidad_recibida: float = 0
    cantidad_pendiente: Optional[float] = None
    unidad_medida: str
    estado: str
    estado_bom: EstadoMaterialBOMEnum
    fecha_solicitud: date
    fecha_necesaria: Optional[date] = None
    comentarios: Optional[str] = None
    creado_en: datetime

    class Config:
        from_attributes = True


class RetalMRPCreate(BaseModel):
    codigo_retal: str
    codigo_material: str
    descripcion: Optional[str] = None
    dimensiones: Optional[str] = None
    unidad_medida: str = "UND"
    cantidad_disponible: float = Field(..., gt=0)


class EstadoRequisicionMRPUpdate(BaseModel):
    estado_bom: EstadoMaterialBOMEnum


def _respuesta_requisicion_mrp(requisicion: RequisicionMRP) -> dict:
    return {
        "id_requisicion": str(requisicion.id_requisicion),
        "numero_solicitud": requisicion.numero_solicitud,
        "codigo_material": requisicion.codigo_material,
        "especificacion": requisicion.especificacion,
        "unidad_medida": requisicion.unidad_medida,
        "demanda_bruta": requisicion.demanda_bruta,
        "stock_libre": requisicion.stock_libre,
        "retales_disponibles": requisicion.retales_disponibles,
        "compras_en_transito": requisicion.compras_en_transito,
        "stock_reservado": requisicion.stock_reservado,
        "requerimiento_neto": requisicion.requerimiento_neto,
        "estado_bom": requisicion.estado,
        "trazabilidad": [
            {
                "codigo_op": detalle.codigo_op,
                "codigo_plano": detalle.codigo_plano,
                "cantidad_demanda": detalle.cantidad_demanda,
            }
            for detalle in requisicion.trazabilidad
        ],
    }


@router.post("/mrp/retales", status_code=status.HTTP_201_CREATED)
def registrar_retal_mrp(retal_in: RetalMRPCreate, db: Session = Depends(get_db)):
    codigo_retal = retal_in.codigo_retal.strip()
    if db.query(RetalSobrante).filter(RetalSobrante.codigo_retal == codigo_retal).first():
        raise HTTPException(status_code=400, detail="El código de retal ya está registrado.")

    retal = RetalSobrante(
        codigo_retal=codigo_retal,
        codigo_material=retal_in.codigo_material.strip(),
        descripcion=retal_in.descripcion,
        dimensiones=retal_in.dimensiones,
        unidad_medida=retal_in.unidad_medida,
        cantidad_disponible=retal_in.cantidad_disponible,
        reutilizable=True,
    )
    try:
        db.add(retal)
        db.commit()
        db.refresh(retal)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar el retal reutilizable.") from error
    return retal


@router.post("/mrp/ejecutar", status_code=status.HTTP_201_CREATED)
def ejecutar_mrp(db: Session = Depends(get_db)):
    """Explota el BOM de OP confirmadas y consolida una PR por especificación material."""
    estados_confirmados = [
        EstadoOPEnum.APROBADA,
        EstadoOPEnum.PENDIENTE_MATERIAL,
        EstadoOPEnum.LIBERADA_PRODUCCION,
        EstadoOPEnum.EN_PRODUCCION,
        EstadoOPEnum.EN_PROCESO_CNC,
        EstadoOPEnum.EN_SETUP,
        EstadoOPEnum.MECANIZADO,
        EstadoOPEnum.EN_INSPECCION,
        EstadoOPEnum.LISTA_PARA_LIBERAR,
        EstadoOPEnum.LIBERADA,
    ]
    ordenes = db.query(OrdenProduccion).options(
        joinedload(OrdenProduccion.proyecto),
        joinedload(OrdenProduccion.plano),
    ).filter(OrdenProduccion.estado.in_(estados_confirmados)).all()

    necesidades = {}
    for orden in ordenes:
        proyecto = orden.proyecto
        plano = orden.plano or db.query(Plano).filter(
            Plano.id_proyecto == orden.id_proyecto
        ).first()
        if not proyecto or not plano:
            continue

        bom_items = db.query(BOMListaMateriales).filter(
            BOMListaMateriales.plano_id == plano.id_plano
        ).all()
        for item in bom_items:
            codigo = item.codigo_material.strip()
            descripcion = item.descripcion.strip()
            unidad = item.unidad_medida.strip()
            clave = (codigo.casefold(), descripcion.casefold(), unidad.casefold())
            grupo = necesidades.setdefault(clave, {
                "codigo_material": codigo,
                "especificacion": descripcion,
                "unidad_medida": unidad,
                "demanda_bruta": 0.0,
                "trazabilidad": {},
                "bom_items": [],
            })
            cantidad = float(item.cantidad_requerida or 0) * float(orden.cantidad_fabricar or 0)
            grupo["demanda_bruta"] += cantidad
            clave_op_plano = (orden.codigo_op, plano.codigo_plano)
            grupo["trazabilidad"][clave_op_plano] = (
                grupo["trazabilidad"].get(clave_op_plano, 0.0) + cantidad
            )
            grupo["bom_items"].append(item)

    ejecucion = EjecucionMRP(ejecutado_por="MRP")
    requisiciones_creadas = []
    try:
        db.add(ejecucion)
        db.flush()

        for indice, grupo in enumerate(necesidades.values(), start=1):
            codigo_material = grupo["codigo_material"]
            articulo = db.query(ArticuloInventario).filter(
                ArticuloInventario.codigo_sku == codigo_material
            ).with_for_update().first()
            lotes_stock = db.query(LoteMaterial).filter(
                LoteMaterial.codigo_material == codigo_material,
                (
                    (LoteMaterial.estado_calidad == "LIBERADO")
                    | (
                        LoteMaterial.estado_calidad.is_(None)
                        & LoteMaterial.inspeccionado_calidad.is_(True)
                    )
                ),
            ).with_for_update().all()
            stock_lotes = sum(max(float(lote.stock_disponible or 0), 0.0) for lote in lotes_stock)
            stock = min(stock_lotes, max(float(articulo.stock_actual or 0), 0.0)) if articulo else stock_lotes
            reservado_lotes = sum(
                min(
                    max(float(lote.stock_reservado or 0), 0.0),
                    max(float(lote.stock_disponible or 0), 0.0),
                )
                for lote in lotes_stock
            )
            reservado_articulo = float(articulo.stock_reservado or 0) if articulo else 0.0
            reservado = min(max(reservado_articulo, reservado_lotes), stock)

            retales = db.query(RetalSobrante).filter(
                RetalSobrante.codigo_material == codigo_material,
                RetalSobrante.reutilizable.is_(True),
            ).all()
            cantidad_retales = sum(
                max(float(retal.cantidad_disponible or 0) - float(retal.cantidad_reservada or 0), 0.0)
                for retal in retales
            )
            compras = db.query(SolicitudCompraORM).filter(
                SolicitudCompraORM.codigo_sku == codigo_material,
                SolicitudCompraORM.estado.in_([
                    "PENDIENTE", "RADICADA", "APROBADA", "EN_COMPRA", "EN_TRANSITO", "ORDEN_COMPRA",
                ]),
            ).all()
            cantidad_transito = sum(max(float(compra.cantidad_solicitada or 0), 0.0) for compra in compras)
            disponible_neto = max(stock + cantidad_retales + cantidad_transito - reservado, 0.0)
            requerimiento_neto = max(grupo["demanda_bruta"] - disponible_neto, 0.0)

            cantidad_reservar_stock = min(max(stock - reservado, 0.0), grupo["demanda_bruta"])
            restante_reserva = max(grupo["demanda_bruta"] - cantidad_reservar_stock, 0.0)
            if articulo and cantidad_reservar_stock:
                articulo.stock_reservado = reservado + cantidad_reservar_stock
            if cantidad_reservar_stock:
                restante_lote = cantidad_reservar_stock
                for lote in sorted(lotes_stock, key=lambda item: item.codigo_lote):
                    disponible_lote = max(
                        float(lote.stock_disponible or 0) - float(lote.stock_reservado or 0),
                        0.0,
                    )
                    cantidad_lote = min(disponible_lote, restante_lote)
                    lote.stock_reservado = float(lote.stock_reservado or 0) + cantidad_lote
                    restante_lote -= cantidad_lote
                    if restante_lote <= 0:
                        break

            cantidad_reservar_retales = min(cantidad_retales, restante_reserva)
            restante_reserva = cantidad_reservar_retales
            for retal in sorted(retales, key=lambda item: item.codigo_retal):
                disponible_retal = max(
                    float(retal.cantidad_disponible or 0) - float(retal.cantidad_reservada or 0),
                    0.0,
                )
                cantidad_retal = min(disponible_retal, restante_reserva)
                retal.cantidad_reservada = float(retal.cantidad_reservada or 0) + cantidad_retal
                restante_reserva -= cantidad_retal
                if restante_reserva <= 0:
                    break

            numero_solicitud = None
            solicitud_db = None
            if requerimiento_neto > 0:
                numero_solicitud = f"PR-MRP-{ejecucion.id_ejecucion.hex[:8].upper()}-{indice:03d}"
                primer_codigo_op, primer_codigo_plano = next(iter(grupo["trazabilidad"]))
                plano_pr = db.query(Plano).filter(
                    Plano.codigo_op == primer_codigo_op,
                    Plano.codigo_plano == primer_codigo_plano,
                ).first()
                solicitud_db = SolicitudCompraORM(
                    numero_solicitud=numero_solicitud,
                    codigo_op=primer_codigo_op,
                    codigo_plano=primer_codigo_plano,
                    numero_pedido=plano_pr.proyecto.numero_pedido if plano_pr and plano_pr.proyecto else None,
                    nombre_item=grupo["especificacion"],
                    codigo_sku=codigo_material,
                    categoria="MATERIA_PRIMA",
                    cantidad_solicitada=requerimiento_neto,
                    unidad_medida=grupo["unidad_medida"],
                    estado="RADICADA",
                    estado_bom="SOLICITADO",
                    id_proyecto=plano_pr.id_proyecto if plano_pr else None,
                    id_plano=plano_pr.id_plano if plano_pr else None,
                    observaciones="Generada por ejecución MRP; revisar trazabilidad de OP/plano.",
                )
                db.add(solicitud_db)
                for item in grupo["bom_items"]:
                    item.estado_abastecimiento = "SOLICITADO"
            else:
                estado_cubierto = (
                    "EN_ALMACEN"
                    if max(stock + cantidad_retales - reservado, 0.0) >= grupo["demanda_bruta"]
                    else "EN_COMPRA"
                )
                for item in grupo["bom_items"]:
                    item.estado_abastecimiento = estado_cubierto

            requisicion = RequisicionMRP(
                id_ejecucion=ejecucion.id_ejecucion,
                codigo_material=codigo_material,
                especificacion=grupo["especificacion"],
                unidad_medida=grupo["unidad_medida"],
                demanda_bruta=grupo["demanda_bruta"],
                stock_libre=stock,
                retales_disponibles=cantidad_retales,
                compras_en_transito=cantidad_transito,
                stock_reservado=reservado,
                requerimiento_neto=requerimiento_neto,
                numero_solicitud=numero_solicitud,
                estado="SOLICITADO" if requerimiento_neto else "CUBIERTO",
                solicitud_id=solicitud_db.id_solicitud if solicitud_db else None,
            )
            db.add(requisicion)
            db.flush()
            for (codigo_op, codigo_plano), cantidad_demanda in grupo["trazabilidad"].items():
                db.add(TrazabilidadRequisicionMRP(
                    requisicion_id=requisicion.id_requisicion,
                    codigo_op=codigo_op,
                    codigo_plano=codigo_plano,
                    cantidad_demanda=cantidad_demanda,
                ))
            requisiciones_creadas.append(requisicion)

        db.commit()
        return {
            "id_ejecucion": str(ejecucion.id_ejecucion),
            "ejecutado_en": ejecucion.ejecutado_en,
            "requisiciones": [_respuesta_requisicion_mrp(item) for item in requisiciones_creadas],
        }
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="Falló la ejecución MRP; no se guardaron requisiciones.") from error


@router.get("/mrp/requisiciones")
def listar_requisiciones_mrp(db: Session = Depends(get_db)):
    ejecucion = db.query(EjecucionMRP).order_by(EjecucionMRP.ejecutado_en.desc()).first()
    if not ejecucion:
        return []
    requisiciones = db.query(RequisicionMRP).options(
        joinedload(RequisicionMRP.trazabilidad)
    ).filter(
        RequisicionMRP.id_ejecucion == ejecucion.id_ejecucion
    ).order_by(RequisicionMRP.codigo_material.asc()).all()
    return [_respuesta_requisicion_mrp(item) for item in requisiciones]


@router.patch("/mrp/requisiciones/{id_requisicion}")
def actualizar_estado_requisicion_mrp(
    id_requisicion: UUID,
    actualizacion: EstadoRequisicionMRPUpdate,
    db: Session = Depends(get_db),
):
    requisicion = db.query(RequisicionMRP).options(
        joinedload(RequisicionMRP.trazabilidad)
    ).filter(RequisicionMRP.id_requisicion == id_requisicion).first()
    if not requisicion:
        raise HTTPException(status_code=404, detail="Requisición MRP no encontrada.")
    if not requisicion.solicitud_id:
        raise HTTPException(status_code=400, detail="La requisición está cubierta por inventario y no tiene PR pendiente.")

    solicitud = db.query(SolicitudCompraORM).filter(
        SolicitudCompraORM.id_solicitud == requisicion.solicitud_id
    ).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="La PR asociada ya no existe.")

    estado_bom = actualizacion.estado_bom.value
    solicitud.estado_bom = estado_bom
    solicitud.estado = "EN_ALMACEN" if estado_bom == "EN_ALMACEN" else estado_bom
    requisicion.estado = estado_bom
    try:
        for detalle in requisicion.trazabilidad:
            plano = db.query(Plano).filter(
                Plano.codigo_op == detalle.codigo_op,
                Plano.codigo_plano == detalle.codigo_plano,
            ).first()
            if plano:
                db.query(BOMListaMateriales).filter(
                    BOMListaMateriales.plano_id == plano.id_plano,
                    BOMListaMateriales.codigo_material == requisicion.codigo_material,
                ).update(
                    {"estado_abastecimiento": estado_bom},
                    synchronize_session=False,
                )
        db.commit()
        db.refresh(requisicion)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo actualizar el estado de abastecimiento BOM.") from error
    return _respuesta_requisicion_mrp(requisicion)

# PERSISTENCIA TEMPORAL EN MEMORIA
SOLICITUDES_DB = [
    SolicitudCompraResponse(
        id_solicitud=uuid4(),
        numero_solicitud="PR-2690",
        solicitante_nombre="Ing. Carlos Ruiz",
        departamento_area="Diseño e Ingeniería",
        id_proyecto=None,
        numero_pedido="11001",
        codigo_op="4001234",
        codigo_plano="PLN-11001-A",
        descripcion_resumen="Acero 4140 Ø1\"X 110mm (24.0 UND)",
        cantidad_piezas=24.0,
        unidad_medida="UND",
        estado="APROBADA",
        estado_bom=EstadoMaterialBOMEnum.EN_COMPRA,
        fecha_solicitud=date.today(),
        fecha_necesaria=date.today(),
        comentarios="Materia prima autorizada para mecanizado",
        creado_en=datetime.now()
    )
]

# =============================================================================
# BLOQUE 2: ENDPOINTS API
# =============================================================================

@router.get("/", response_model=List[SolicitudCompraResponse])
def listar_solicitudes_compra(
    estado_bom: Optional[EstadoMaterialBOMEnum] = None,
    db: Session = Depends(get_db),
):
    consulta = db.query(SolicitudCompraORM)
    if estado_bom:
        consulta = consulta.filter(SolicitudCompraORM.estado_bom == estado_bom.value)
    persistidas = consulta.order_by(SolicitudCompraORM.fecha_solicitud.desc()).all()
    recibidas_por_solicitud = dict(
        db.query(
            MovimientoInventario.referencia_id,
            func.sum(MovimientoInventario.cantidad),
        ).filter(
            MovimientoInventario.referencia_tipo == "PR",
            MovimientoInventario.tipo_movimiento == "101",
        ).group_by(MovimientoInventario.referencia_id).all()
    )
    resultado = [
        SolicitudCompraResponse(
            id_solicitud=solicitud.id_solicitud,
            numero_solicitud=solicitud.numero_solicitud,
            solicitante_nombre="Compras / MRP",
            departamento_area="Compras",
            id_proyecto=solicitud.id_proyecto,
            numero_pedido=solicitud.numero_pedido or "S/P",
            codigo_op=solicitud.codigo_op or "GENERAL",
            codigo_plano=solicitud.codigo_plano or "N/A",
            codigo_sku=solicitud.codigo_sku,
            descripcion_resumen=solicitud.nombre_item,
            cantidad_piezas=solicitud.cantidad_solicitada or 0,
            cantidad_recibida=float(recibidas_por_solicitud.get(str(solicitud.id_solicitud), 0) or 0),
            cantidad_pendiente=max(
                float(solicitud.cantidad_solicitada or 0)
                - float(recibidas_por_solicitud.get(str(solicitud.id_solicitud), 0) or 0),
                0.0,
            ),
            unidad_medida=solicitud.unidad_medida or "UND",
            estado=solicitud.estado or "PENDIENTE",
            estado_bom=EstadoMaterialBOMEnum(solicitud.estado_bom or "SOLICITADO"),
            fecha_solicitud=solicitud.fecha_solicitud.date(),
            comentarios=solicitud.observaciones,
            creado_en=solicitud.fecha_solicitud,
        )
        for solicitud in persistidas
    ]
    ids_persistidas = {solicitud.id_solicitud for solicitud in persistidas}
    temporales = [] if estado_bom else [
        solicitud for solicitud in SOLICITUDES_DB
        if solicitud.id_solicitud not in ids_persistidas
    ]
    return resultado + temporales

@router.get("/verificar-pieza/{codigo_op}/{codigo_plano}")
def verificar_solicitud_pieza(codigo_op: str, codigo_plano: str):
    sol = next((s for s in SOLICITUDES_DB if s.codigo_op == codigo_op and s.codigo_plano == codigo_plano), None)
    if sol:
        return {
            "existe": True,
            "numero_solicitud": sol.numero_solicitud,
            "estado_bom": sol.estado_bom,
            "material": sol.descripcion_resumen
        }
    return {"existe": False, "estado_bom": EstadoMaterialBOMEnum.SIN_SOLICITAR}

@router.post("/", response_model=SolicitudCompraResponse, status_code=status.HTTP_201_CREATED)
def crear_solicitud_compra(sol_in: SolicitudCompraCreate, db: Session = Depends(get_db)):
    # 1. Consolidar lista de items/insumos
    lista_items = sol_in.items or sol_in.insumos or []
    if not lista_items:
        raise HTTPException(status_code=400, detail="Debe ingresar al menos un insumo/material en la solicitud.")

    # 2. Resumen de materiales
    resumen_insumos = ", ".join([f"{item.descripcion_material} ({item.cantidad} {item.unidad_medida})" for item in lista_items])
    primer_item = lista_items[0]

    # 3. Datos sanitizados de cabecera
    num_sol = sol_in.numero_solicitud or f"PR-{uuid4().hex[:4].upper()}"
    solicitante = sol_in.solicitante_nombre or sol_in.solicitante or "Carlos Ruiz (Diseño)"
    depto = sol_in.departamento_area or sol_in.departamento or "Diseño e Ingeniería"

    # 4. Vinculación automática con Ingeniería (Plano / OT)
    plano_db = None
    if sol_in.codigo_op and sol_in.codigo_plano:
        plano_db = db.query(Plano).filter(
            Plano.codigo_op == sol_in.codigo_op,
            Plano.codigo_plano == sol_in.codigo_plano
        ).first()

        if plano_db:
            plano_db.material_requerido = f"{resumen_insumos} ({num_sol})"
    codigo_material = primer_item.codigo_articulo
    if not codigo_material or codigo_material == "TEXTO_LIBRE":
        codigo_material = primer_item.descripcion_material[:50]
    solicitud_db = SolicitudCompraORM(
        numero_solicitud=num_sol,
        codigo_op=sol_in.codigo_op,
        codigo_plano=sol_in.codigo_plano,
        numero_pedido=sol_in.numero_pedido,
        nombre_item=resumen_insumos,
        codigo_sku=codigo_material,
        categoria="MATERIA_PRIMA",
        cantidad_solicitada=sum(item.cantidad for item in lista_items),
        unidad_medida=primer_item.unidad_medida,
        estado="RADICADA",
        estado_bom=EstadoMaterialBOMEnum.SOLICITADO.value,
        observaciones=sol_in.comentarios,
        id_proyecto=sol_in.id_proyecto if isinstance(sol_in.id_proyecto, UUID) else None,
        id_plano=plano_db.id_plano if plano_db else None,
    )
    try:
        db.add(solicitud_db)
        if plano_db:
            db.query(BOMListaMateriales).filter(
                BOMListaMateriales.plano_id == plano_db.id_plano,
                BOMListaMateriales.codigo_material == codigo_material,
            ).update(
                {"estado_abastecimiento": EstadoMaterialBOMEnum.SOLICITADO.value},
                synchronize_session=False,
            )
        db.commit()
        db.refresh(solicitud_db)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar la solicitud de compra.") from error

    return SolicitudCompraResponse(
        id_solicitud=solicitud_db.id_solicitud,
        numero_solicitud=solicitud_db.numero_solicitud,
        solicitante_nombre=solicitante,
        departamento_area=depto,
        id_proyecto=solicitud_db.id_proyecto,
        numero_pedido=solicitud_db.numero_pedido or "S/P",
        codigo_op=solicitud_db.codigo_op or "GENERAL",
        codigo_plano=solicitud_db.codigo_plano or "N/A",
        codigo_sku=solicitud_db.codigo_sku,
        descripcion_resumen=solicitud_db.nombre_item,
        cantidad_piezas=solicitud_db.cantidad_solicitada or 0,
        unidad_medida=solicitud_db.unidad_medida or "UND",
        fecha_solicitud=solicitud_db.fecha_solicitud.date(),
        fecha_necesaria=sol_in.fecha_necesaria,
        estado=solicitud_db.estado,
        estado_bom=EstadoMaterialBOMEnum(solicitud_db.estado_bom),
        comentarios=solicitud_db.observaciones,
        creado_en=solicitud_db.fecha_solicitud,
    )

@router.patch("/{id_solicitud}", response_model=SolicitudCompraResponse)
def actualizar_estado_solicitud(
    id_solicitud: UUID,
    sol_up: SolicitudCompraUpdate,
    db: Session = Depends(get_db),
):
    solicitud_db = db.query(SolicitudCompraORM).filter(
        SolicitudCompraORM.id_solicitud == id_solicitud
    ).first()
    if solicitud_db:
        if sol_up.estado:
            solicitud_db.estado = sol_up.estado
        if sol_up.estado_bom:
            solicitud_db.estado_bom = sol_up.estado_bom.value
            requisiciones_mrp = db.query(RequisicionMRP).options(
                joinedload(RequisicionMRP.trazabilidad)
            ).filter(
                RequisicionMRP.solicitud_id == solicitud_db.id_solicitud
            ).all()
            if requisiciones_mrp:
                for requisicion in requisiciones_mrp:
                    for detalle in requisicion.trazabilidad:
                        plano = db.query(Plano).filter(
                            Plano.codigo_op == detalle.codigo_op,
                            Plano.codigo_plano == detalle.codigo_plano,
                        ).first()
                        if plano:
                            db.query(BOMListaMateriales).filter(
                                BOMListaMateriales.plano_id == plano.id_plano,
                                BOMListaMateriales.codigo_material == requisicion.codigo_material,
                            ).update(
                                {"estado_abastecimiento": sol_up.estado_bom.value},
                                synchronize_session=False,
                            )
            elif solicitud_db.id_plano and solicitud_db.codigo_sku:
                db.query(BOMListaMateriales).filter(
                    BOMListaMateriales.plano_id == solicitud_db.id_plano,
                    BOMListaMateriales.codigo_material == solicitud_db.codigo_sku,
                ).update(
                    {"estado_abastecimiento": sol_up.estado_bom.value},
                    synchronize_session=False,
                )
            for requisicion in requisiciones_mrp:
                requisicion.estado = sol_up.estado_bom.value
        if sol_up.comentarios is not None:
            solicitud_db.observaciones = sol_up.comentarios
        try:
            db.commit()
            db.refresh(solicitud_db)
        except SQLAlchemyError as error:
            db.rollback()
            raise HTTPException(status_code=500, detail="No se pudo actualizar la solicitud de compra.") from error
        return SolicitudCompraResponse(
            id_solicitud=solicitud_db.id_solicitud,
            numero_solicitud=solicitud_db.numero_solicitud,
            solicitante_nombre="Compras / MRP",
            departamento_area="Compras",
            id_proyecto=solicitud_db.id_proyecto,
            numero_pedido=solicitud_db.numero_pedido or "S/P",
            codigo_op=solicitud_db.codigo_op or "GENERAL",
            codigo_plano=solicitud_db.codigo_plano or "N/A",
            codigo_sku=solicitud_db.codigo_sku,
            descripcion_resumen=solicitud_db.nombre_item,
            cantidad_piezas=solicitud_db.cantidad_solicitada or 0,
            unidad_medida=solicitud_db.unidad_medida or "UND",
            estado=solicitud_db.estado or "PENDIENTE",
            estado_bom=EstadoMaterialBOMEnum(solicitud_db.estado_bom or "SOLICITADO"),
            fecha_solicitud=solicitud_db.fecha_solicitud.date(),
            comentarios=solicitud_db.observaciones,
            creado_en=solicitud_db.fecha_solicitud,
        )

    for i, sol in enumerate(SOLICITUDES_DB):
        if sol.id_solicitud == id_solicitud:
            if sol_up.estado:
                SOLICITUDES_DB[i].estado = sol_up.estado
            if sol_up.estado_bom:
                SOLICITUDES_DB[i].estado_bom = sol_up.estado_bom
            if sol_up.comentarios:
                SOLICITUDES_DB[i].comentarios = sol_up.comentarios
            return SOLICITUDES_DB[i]
    raise HTTPException(status_code=404, detail="Solicitud de Compra no encontrada.")