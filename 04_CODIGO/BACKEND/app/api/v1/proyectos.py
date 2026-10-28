# app/api/v1/proyectos.py
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, Field, validator

from app.db.database import get_db
from app.db.models import (
    BOMListaMateriales,
    Cliente,
    MovimientoKardexSAP,
    OrdenProduccion,
    Proyecto,
    PedidoDetalle,
    OTDetalle,
    Plano,
    SocioNegocio,
)

router = APIRouter()

# =============================================================================
# SCHEMAS PYDANTIC (PM-01 VENTAS / PEDIDOS COMERCIALES)
# =============================================================================

class PresupuestoComponente(BaseModel):
    categoria: str
    referencia: str = Field(..., min_length=1, max_length=200)
    monto_presupuestado: float = Field(..., ge=0)

    @validator("categoria")
    def validar_categoria(cls, valor):
        categorias_validas = {"MATERIA_PRIMA", "HORAS_MES", "SERVICIO_EXTERNO"}
        categoria = valor.strip().upper()
        if categoria not in categorias_validas:
            raise ValueError("La categoría debe ser MATERIA_PRIMA, HORAS_MES o SERVICIO_EXTERNO.")
        return categoria

    @validator("referencia")
    def validar_referencia(cls, valor):
        referencia = valor.strip()
        if not referencia:
            raise ValueError("La referencia del componente no puede estar vacía.")
        return referencia

    class Config:
        extra = "ignore"


def validar_referencias_presupuestales(presupuestos):
    referencias = set()
    for presupuesto in presupuestos or []:
        clave = (presupuesto.categoria, presupuesto.referencia.casefold())
        if clave in referencias:
            raise ValueError("No se permiten referencias presupuestales duplicadas en la misma categoría.")
        referencias.add(clave)
    return presupuestos


class PedidoDetalleItem(BaseModel):
    detalle_id: Optional[UUID] = None
    codigo_producto: Optional[str] = None
    descripcion: str = Field(..., description="Nombre / Detalle de la pieza o servicio")
    tipo: Optional[str] = "pieza"
    cantidad_solicitada: int = Field(1, ge=1)
    unidad: Optional[str] = "UND"
    prioridad: Optional[str] = "MEDIA"
    fecha_compromiso: Optional[date] = None
    requisitos_especificos: Optional[str] = None
    observaciones: Optional[str] = None

    @validator('fecha_compromiso', pre=True)
    def parse_fechas_vacias(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    @validator('cantidad_solicitada', pre=True)
    def parse_cantidad(cls, v):
        if v == "" or v is None:
            return 1
        try:
            return int(v)
        except (ValueError, TypeError):
            return 1

    class Config:
        extra = "ignore"


class ProyectoCreate(BaseModel):
    numero_pedido: str = Field(..., description="N° Pedido Comercial Agrupador (ej. PED-2026-088)")
    codigo_proyecto: Optional[str] = None
    cliente_nombre: str = Field(..., description="Nombre o Razón Social del Cliente")
    contacto_nombre: Optional[str] = None
    contacto_telefono: Optional[str] = None
    contacto_email: Optional[str] = None
    ubicacion_cliente: Optional[str] = "Planta Principal"
    cantidad: Optional[int] = 1
    detalle_producto: Optional[str] = None
    requisitos_cliente: Optional[str] = Field(default="Sin especificación", description="Requisitos técnicos o normas aplicables")
    fecha_compromiso: Optional[date] = None
    detalles: Optional[List[PedidoDetalleItem]] = Field(default_factory=list)
    presupuestos_componentes: List[PresupuestoComponente] = Field(default_factory=list)

    _validar_referencias_presupuestales = validator(
        "presupuestos_componentes",
        allow_reuse=True,
    )(validar_referencias_presupuestales)

    @validator('fecha_compromiso', pre=True)
    def parse_fechas_vacias(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    @validator('cantidad', pre=True)
    def parse_cantidad(cls, v):
        if v == "" or v is None:
            return 1
        try:
            return int(v)
        except (ValueError, TypeError):
            return 1

    class Config:
        extra = "ignore"


class ProyectoUpdate(BaseModel):
    numero_pedido: Optional[str] = None
    cliente_nombre: Optional[str] = None
    contacto_nombre: Optional[str] = None
    contacto_telefono: Optional[str] = None
    contacto_email: Optional[str] = None
    ubicacion_cliente: Optional[str] = None
    requisitos_cliente: Optional[str] = None
    fecha_compromiso: Optional[date] = None
    detalles: Optional[List[PedidoDetalleItem]] = None
    presupuestos_componentes: Optional[List[PresupuestoComponente]] = None

    _validar_referencias_presupuestales = validator(
        "presupuestos_componentes",
        allow_reuse=True,
    )(validar_referencias_presupuestales)

    @validator('fecha_compromiso', pre=True)
    def parse_fechas_vacias(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    class Config:
        extra = "ignore"


class OTDetalleResponse(BaseModel):
    ot_detalle_id: UUID
    ot_id: UUID
    cantidad_asignada: int

    class Config:
        from_attributes = True


class PedidoDetalleResponse(BaseModel):
    detalle_id: UUID
    codigo_producto: Optional[str] = None
    descripcion: str
    tipo: str
    cantidad_solicitada: int
    unidad: str
    cantidad_asignada: int
    cantidad_pendiente: int
    estado_asignacion: Optional[str] = "SIN_ASIGNAR"
    prioridad: str
    fecha_compromiso: Optional[date] = None
    requisitos_especificos: Optional[str] = None
    observaciones: Optional[str] = None
    ot_detalles: List[OTDetalleResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class ProyectoResponse(BaseModel):
    id_proyecto: UUID
    numero_pedido: str
    codigo_proyecto: str
    cliente_nombre: str
    contacto_nombre: Optional[str] = None
    contacto_telefono: Optional[str] = None
    contacto_email: Optional[str] = None
    ubicacion_cliente: Optional[str] = None
    cantidad: Optional[int] = 1
    detalle_producto: Optional[str] = None
    requisitos_cliente: Optional[str] = None
    fecha_compromiso: Optional[date] = None
    confirmado: bool
    creado_en: datetime
    presupuestos_componentes: List[PresupuestoComponente] = Field(default_factory=list)
    detalles: List[PedidoDetalleResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


# =============================================================================
# ENDPOINTS API (PM-01)
# =============================================================================

@router.get("/", response_model=List[ProyectoResponse])
def listar_proyectos(db: Session = Depends(get_db)):
    proyectos_db = db.query(Proyecto).order_by(Proyecto.creado_en.desc()).all()
    
    for p in proyectos_db:
        num_ped = getattr(p, 'numero_pedido', None) or getattr(p, 'codigo_proyecto', 'S/P')
        p.numero_pedido = num_ped
        p.codigo_proyecto = getattr(p, 'codigo_proyecto', None) or f"PED-{num_ped}"
        
        for det in p.detalles:
            cant_sol = det.cantidad_solicitada or 0
            cant_asig = sum(rel.cantidad_asignada for rel in det.ot_detalles) if det.ot_detalles else 0
            cant_pend = cant_sol - cant_asig
            
            det.cantidad_asignada = cant_asig
            det.cantidad_pendiente = cant_pend if cant_pend >= 0 else 0
            
            if cant_asig == 0:
                det.estado_asignacion = "SIN_ASIGNAR"
            elif cant_asig < cant_sol:
                det.estado_asignacion = "PARCIALMENTE_ASIGNADA"
            else:
                det.estado_asignacion = "TOTALMENTE_ASIGNADA"
                
    return proyectos_db


@router.get("/{id_proyecto}/expediente")
def obtener_expediente_pedido(id_proyecto: UUID, db: Session = Depends(get_db)):
    proyecto = db.query(Proyecto).filter(Proyecto.id_proyecto == id_proyecto).first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="Pedido comercial no encontrado.")

    detalles = (
        db.query(PedidoDetalle)
        .filter(PedidoDetalle.pedido_id == id_proyecto)
        .order_by(PedidoDetalle.creado_en, PedidoDetalle.detalle_id)
        .all()
    )
    detalle_ids = [detalle.detalle_id for detalle in detalles]
    relaciones = (
        db.query(OTDetalle)
        .filter(OTDetalle.detalle_pedido_id.in_(detalle_ids))
        .all()
        if detalle_ids else []
    )

    planos_por_id = {}
    relaciones_por_detalle = {}
    for relacion in relaciones:
        plano = relacion.plano_ot
        if not plano:
            continue
        planos_por_id[plano.id_plano] = plano
        relaciones_por_detalle.setdefault(relacion.detalle_pedido_id, []).append(relacion)

    plano_ids = list(planos_por_id)
    ordenes = (
        db.query(OrdenProduccion)
        .filter(OrdenProduccion.id_plano.in_(plano_ids))
        .all()
        if plano_ids else []
    )
    ordenes_por_plano = {}
    for orden in ordenes:
        ordenes_por_plano.setdefault(orden.id_plano, []).append(orden)

    lineas_bom = (
        db.query(BOMListaMateriales)
        .filter(BOMListaMateriales.plano_id.in_(plano_ids))
        .all()
        if plano_ids else []
    )
    bom_por_plano = {}
    for linea in lineas_bom:
        bom_por_plano.setdefault(linea.plano_id, []).append(linea)

    codigos_op = {
        orden.codigo_op
        for orden in ordenes
        if orden.codigo_op
    }
    codigos_op.update(
        plano.codigo_op
        for plano in planos_por_id.values()
        if plano.codigo_op
    )
    cliente = proyecto.cliente or (
        db.query(Cliente)
        .filter(Cliente.razon_social == proyecto.cliente_nombre)
        .first()
    )
    nit_rut = cliente.nit_rut if cliente else None
    socio = (
        db.query(SocioNegocio)
        .filter(SocioNegocio.nit_cedula == nit_rut)
        .first()
        if nit_rut else None
    )

    def estado_insumo(plano_id):
        estados = [linea.estado_abastecimiento for linea in bom_por_plano.get(plano_id, [])]
        if not estados:
            return "SIN_REGISTRO"
        if all(estado == "ENTREGADO" for estado in estados):
            return "ENTREGADO"
        if all(estado in {"EN_ALMACEN", "ENTREGADO"} for estado in estados):
            return "EN_ALMACEN"
        if "EN_COMPRA" in estados:
            return "EN_COMPRA"
        if "SOLICITADO" in estados:
            return "SOLICITADO"
        return estados[0]

    def serializar_orden(orden, plano):
        return {
            "id_op": str(orden.id_op) if orden else None,
            "codigo_op": orden.codigo_op if orden else plano.codigo_op,
            "codigo_plano": plano.codigo_plano,
            "revision": plano.revision,
            "unidad_planta": plano.unidad_planta,
            "archivo_url": plano.archivo_url,
            "estado_pdf": "CARGA_OK" if plano.archivo_url and plano.archivo_url.strip() else "PENDIENTE",
            "estado_insumo": estado_insumo(plano.id_plano),
            "estado_produccion": (
                orden.estado.value if hasattr(orden.estado, "value") else orden.estado
            ) if orden else None,
            "porcentaje_avance": float(orden.porcentaje_avance or 0) if orden else 0,
            "centro_costo_imputado": None,
        }

    imputacion_por_op = {}
    if codigos_op:
        movimientos = (
            db.query(
                MovimientoKardexSAP.referencia_op,
                MovimientoKardexSAP.centro_costo_imputado,
            )
            .filter(
                MovimientoKardexSAP.referencia_op.in_(codigos_op),
                MovimientoKardexSAP.centro_costo_imputado.isnot(None),
            )
            .all()
        )
        for codigo_op, centro_costo in movimientos:
            if codigo_op and centro_costo:
                imputacion_por_op.setdefault(codigo_op, set()).add(centro_costo)
    centros_costo = sorted({
        centro
        for centros in imputacion_por_op.values()
        for centro in centros
    })

    ordenes_vinculadas = []
    for plano in planos_por_id.values():
        ordenes_plano = ordenes_por_plano.get(plano.id_plano, [])
        filas_ordenes = ordenes_plano or [None]
        for orden in filas_ordenes:
            fila = serializar_orden(orden, plano)
            centros = sorted(imputacion_por_op.get(fila["codigo_op"], set()))
            fila["centro_costo_imputado"] = ", ".join(centros) or None
            ordenes_vinculadas.append(fila)

    detalles_expediente = []
    for indice, detalle in enumerate(detalles, start=1):
        relaciones_detalle = relaciones_por_detalle.get(detalle.detalle_id, [])
        cantidad_asignada = sum(relacion.cantidad_asignada or 0 for relacion in relaciones_detalle)
        cantidad_solicitada = detalle.cantidad_solicitada or 0
        estado_cobertura = (
            "SIN_ASIGNAR" if cantidad_asignada <= 0
            else "PARCIAL" if cantidad_asignada < cantidad_solicitada
            else "ASIGNADO"
        )
        ordenes_detalle = []
        for relacion in relaciones_detalle:
            plano = planos_por_id.get(relacion.ot_id)
            if not plano:
                continue
            for orden in ordenes_por_plano.get(plano.id_plano, []) or [None]:
                fila_orden = serializar_orden(orden, plano)
                centros = sorted(imputacion_por_op.get(fila_orden["codigo_op"], set()))
                fila_orden["centro_costo_imputado"] = ", ".join(centros) or None
                ordenes_detalle.append({
                    "ot_detalle_id": str(relacion.ot_detalle_id),
                    "cantidad_asignada": relacion.cantidad_asignada,
                    "orden_produccion": fila_orden,
                })

        detalles_expediente.append({
            "detalle_id": str(detalle.detalle_id),
            "posicion": f"POS-{indice * 10}",
            "codigo_producto": detalle.codigo_producto,
            "descripcion": detalle.descripcion,
            "tipo": detalle.tipo,
            "cantidad_solicitada": cantidad_solicitada,
            "unidad": detalle.unidad,
            "cantidad_asignada": cantidad_asignada,
            "cantidad_pendiente": max(cantidad_solicitada - cantidad_asignada, 0),
            "estado_cobertura": estado_cobertura,
            "prioridad": detalle.prioridad,
            "fecha_compromiso": detalle.fecha_requerida.isoformat() if detalle.fecha_requerida else None,
            "observaciones": detalle.observaciones,
            "ot_detalles": ordenes_detalle,
        })

    return {
        "id_proyecto": str(proyecto.id_proyecto),
        "numero_pedido": proyecto.numero_pedido,
        "codigo_proyecto": proyecto.codigo_proyecto,
        "confirmado": bool(proyecto.confirmado),
        "cliente_nombre": proyecto.cliente_nombre,
        "nit_rut": nit_rut,
        "contacto_nombre": proyecto.contacto_nombre or (cliente.contacto if cliente else None),
        "contacto_telefono": proyecto.contacto_telefono or (cliente.telefono if cliente else None),
        "contacto_email": proyecto.contacto_email or (cliente.email_contacto if cliente else None),
        "ubicacion_cliente": proyecto.ubicacion_cliente,
        "fecha_compromiso": proyecto.fecha_compromiso.isoformat() if proyecto.fecha_compromiso else None,
        "condiciones_pago_dias": socio.condiciones_pago_dias if socio else None,
        "valor_total_cotizado": float(proyecto.cotizacion_total) if proyecto.cotizacion_total is not None else None,
        "centro_costo_imputado": ", ".join(centros_costo) or None,
        "presupuestos_componentes": proyecto.presupuestos_componentes or [],
        "detalles": detalles_expediente,
        "pedido_detalles": detalles_expediente,
        "ordenes_produccion": ordenes_vinculadas,
        "planos": ordenes_vinculadas,
    }


@router.post("/", response_model=ProyectoResponse, status_code=status.HTTP_201_CREATED)
def crear_proyecto(proyecto_in: ProyectoCreate, db: Session = Depends(get_db)):
    codigo_ref = proyecto_in.codigo_proyecto or proyecto_in.numero_pedido or "PED-001"

    nuevo_proyecto = Proyecto(
        codigo_proyecto=codigo_ref,
        numero_pedido=proyecto_in.numero_pedido,
        cliente_nombre=proyecto_in.cliente_nombre,
        contacto_nombre=proyecto_in.contacto_nombre,
        contacto_telefono=proyecto_in.contacto_telefono,
        contacto_email=proyecto_in.contacto_email,
        ubicacion_cliente=proyecto_in.ubicacion_cliente or "Planta Principal",
        cantidad=proyecto_in.cantidad or 1,
        detalle_producto=proyecto_in.detalle_producto or "Lote de Piezas Solicitadas",
        requisitos_cliente=proyecto_in.requisitos_cliente or "Sin especificación",
        fecha_compromiso=proyecto_in.fecha_compromiso,
        presupuestos_componentes=[
            presupuesto.dict()
            for presupuesto in proyecto_in.presupuestos_componentes
        ],
        confirmado=False
    )

    try:
        db.add(nuevo_proyecto)
        db.flush()

        if proyecto_in.detalles:
            for item in proyecto_in.detalles:
                detalle_db = PedidoDetalle(
                    pedido_id=nuevo_proyecto.id_proyecto,
                    codigo_producto=item.codigo_producto,
                    descripcion=item.descripcion,
                    tipo=item.tipo or "pieza",
                    cantidad_solicitada=item.cantidad_solicitada,
                    unidad=item.unidad or "UND",
                    cantidad_asignada=0,
                    cantidad_pendiente=item.cantidad_solicitada,
                    prioridad=item.prioridad or "MEDIA",
                    fecha_compromiso=item.fecha_compromiso or proyecto_in.fecha_compromiso,
                    requisitos_especificos=item.requisitos_especificos,
                    observaciones=item.observaciones
                )
                db.add(detalle_db)

        db.commit()
        db.refresh(nuevo_proyecto)
        return nuevo_proyecto
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al guardar pedido comercial en base de datos: {str(e)}"
        )


@router.patch("/{id_proyecto}", response_model=ProyectoResponse)
def actualizar_proyecto(id_proyecto: UUID, proyecto_up: ProyectoUpdate, db: Session = Depends(get_db)):
    proyecto = db.query(Proyecto).filter(Proyecto.id_proyecto == id_proyecto).first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="Pedido comercial no encontrado.")

    if proyecto.confirmado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="❌ Bloqueo ISO 9001: No se puede modificar un Pedido Comercial que ya ha sido CONFIRMADO."
        )

    datos_dict = proyecto_up.dict(exclude_unset=True, exclude={"detalles"})
    if proyecto_up.presupuestos_componentes is not None:
        datos_dict["presupuestos_componentes"] = [
            presupuesto.dict()
            for presupuesto in proyecto_up.presupuestos_componentes
        ]
    for campo, valor in datos_dict.items():
        if hasattr(proyecto, campo) and valor is not None:
            setattr(proyecto, campo, valor)

    try:
        if proyecto_up.detalles is not None:
            # Eliminación limpia con flush previa a la reinserción
            db.query(PedidoDetalle).filter(PedidoDetalle.pedido_id == id_proyecto).delete()
            db.flush()
            
            for item in proyecto_up.detalles:
                nuevo_det = PedidoDetalle(
                    pedido_id=id_proyecto,
                    codigo_producto=item.codigo_producto,
                    descripcion=item.descripcion,
                    tipo=item.tipo or "pieza",
                    cantidad_solicitada=item.cantidad_solicitada,
                    unidad=item.unidad or "UND",
                    cantidad_asignada=0,
                    cantidad_pendiente=item.cantidad_solicitada,
                    prioridad=item.prioridad or "MEDIA",
                    fecha_compromiso=item.fecha_compromiso or proyecto.fecha_compromiso,
                    requisitos_especificos=item.requisitos_especificos,
                    observaciones=item.observaciones
                )
                db.add(nuevo_det)

        if proyecto.detalles and len(proyecto.detalles) > 0:
            proyecto.detalle_producto = proyecto.detalles[0].descripcion

        db.commit()
        db.refresh(proyecto)
        return proyecto
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar pedido comercial: {str(e)}"
        )


@router.patch("/{id_proyecto}/confirmar", response_model=ProyectoResponse)
def confirmar_proyecto(id_proyecto: UUID, db: Session = Depends(get_db)):
    proyecto = db.query(Proyecto).filter(Proyecto.id_proyecto == id_proyecto).first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="Pedido comercial no encontrado.")

    try:
        proyecto.confirmado = True
        db.commit()
        db.refresh(proyecto)
        return proyecto
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al confirmar pedido: {str(e)}"
        )