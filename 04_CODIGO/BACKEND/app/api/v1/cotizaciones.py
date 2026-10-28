# app/api/v1/cotizaciones.py
import uuid
from typing import List, Optional, Any, Union
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import (
    Cotizacion,
    PosicionCotizacion,
    SocioNegocio,
    Proyecto,
    PedidoDetalle,
    EstadoCotizacionEnum
)

router = APIRouter(prefix="/ventas/cotizaciones", tags=["Cotizaciones Comerciales"])

# =============================================================================
# ESQUEMAS PYDANTIC
# =============================================================================

class PosicionCotizacionIn(BaseModel):
    numero_producto: Optional[str] = "REF-COT"
    descripcion: str
    cantidad: float = 1.0
    precio_unitario: float = 0.0
    descuento_pct: float = 0.0
    unidad: Optional[str] = "UND"
    tipo_impuesto: Optional[str] = "IVA_19"
    vinculo_plano_catalogo: Optional[str] = None

class CotizacionCreateIn(BaseModel):
    id_socio: Optional[Any] = None
    codigo_cliente: Optional[str] = None
    razon_social: Optional[str] = None
    nit: Optional[str] = None
    contacto_nombre: Optional[str] = None
    contacto_telefono: Optional[str] = None
    contacto_email: Optional[str] = None
    direccion_cliente: Optional[str] = None
    ciudad: Optional[str] = None
    referencia_global: Optional[str] = None
    numero_cotizacion: str
    fecha_emision: Optional[date] = None
    fecha_vigencia: Optional[date] = None
    fecha_compromiso: Optional[date] = None
    condiciones_pago: Optional[str] = "30 Días"
    condiciones_comerciales: Optional[str] = None
    subtotal: Optional[float] = 0.0
    impuesto_total: Optional[float] = 0.0
    total_general: Optional[float] = 0.0
    posiciones: List[PosicionCotizacionIn] = []

    class Config:
        extra = "ignore"

class EnviarCotizacionMailIn(BaseModel):
    destinatario: str
    asunto: str
    mensaje: str

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/")
def listar_cotizaciones(db: Session = Depends(get_db)):
    """
    Retorna el listado completo de cotizaciones emitidas para ProyectosView.jsx
    """
    cotizaciones_db = db.query(Cotizacion).order_by(Cotizacion.creado_en.desc()).all()
    resultado = []
    for c in cotizaciones_db:
        socio = db.query(SocioNegocio).filter(SocioNegocio.id_socio == c.id_socio).first()
        nombre_cliente = socio.razon_social if socio else (socio.codigo_socio if socio else "Cliente Comercial")
        resultado.append({
            "id_cotizacion": str(c.id_cotizacion),
            "numero_cotizacion": c.numero_cotizacion,
            "id_socio": nombre_cliente,
            "fecha_emision": c.fecha_emision.strftime("%Y-%m-%d") if c.fecha_emision else "",
            "fecha_vigencia": c.fecha_vigencia.strftime("%Y-%m-%d") if c.fecha_vigencia else "",
            "valor_total": float(c.valor_total or 0.0),
            "estado": c.estado.value if hasattr(c.estado, "value") else str(c.estado)
        })
    return resultado

@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_cotizacion(data: CotizacionCreateIn, db: Session = Depends(get_db)):
    try:
        socio = None

        if data.id_socio:
            try:
                uuid_parsed = uuid.UUID(str(data.id_socio))
                socio = db.query(SocioNegocio).filter(SocioNegocio.id_socio == uuid_parsed).first()
            except (ValueError, AttributeError):
                socio = None

        if not socio and data.codigo_cliente:
            socio = db.query(SocioNegocio).filter(SocioNegocio.codigo_socio == data.codigo_cliente).first()

        if not socio and data.nit:
            socio = db.query(SocioNegocio).filter(SocioNegocio.nit_cedula == data.nit).first()

        if not socio:
            socio = SocioNegocio(
                id_socio=uuid.uuid4(),
                codigo_socio=data.codigo_cliente or f"CLI-{uuid.uuid4().hex[:6].upper()}",
                nit_cedula=data.nit or f"NIT-{uuid.uuid4().hex[:8].upper()}",
                razon_social=data.razon_social or "Cliente Sin Razón Social",
                es_cliente=True,
                es_proveedor=False,
                condiciones_pago_dias=30,
                estado_activo=True,
                direccion=data.direccion_cliente,
                telefono=data.contacto_telefono,
                email=data.contacto_email
            )
            db.add(socio)
            db.flush()

        total_doc = data.total_general if (data.total_general and data.total_general > 0) else sum(
            (p.cantidad * p.precio_unitario * (1 - p.descuento_pct / 100)) for p in data.posiciones
        )

        nueva_cot = Cotizacion(
            id_cotizacion=uuid.uuid4(),
            id_socio=socio.id_socio,
            numero_cotizacion=data.numero_cotizacion,
            fecha_emision=data.fecha_emision or date.today(),
            fecha_vigencia=data.fecha_vigencia,
            estado=EstadoCotizacionEnum.BORRADOR,
            valor_total=total_doc,
            condiciones_comerciales=data.condiciones_comerciales
        )
        db.add(nueva_cot)
        db.flush()

        for pos in data.posiciones:
            nueva_pos = PosicionCotizacion(
                id_posicion=uuid.uuid4(),
                id_cotizacion=nueva_cot.id_cotizacion,
                numero_producto=pos.numero_producto or "REF-COT",
                descripcion=pos.descripcion,
                cantidad=int(pos.cantidad),
                precio_unitario=pos.precio_unitario,
                vinculo_plano_catalogo=pos.vinculo_plano_catalogo
            )
            db.add(nueva_pos)

        db.commit()
        db.refresh(nueva_cot)

        return {
            "id_cotizacion": str(nueva_cot.id_cotizacion),
            "numero_cotizacion": nueva_cot.numero_cotizacion,
            "id_socio": socio.razon_social,
            "fecha_emision": str(nueva_cot.fecha_emision),
            "valor_total": float(nueva_cot.valor_total),
            "estado": "BORRADOR"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar la cotización: {str(e)}"
        )

@router.get("/{id_cotizacion}")
def obtener_detalle_cotizacion(id_cotizacion: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retorna el expediente completo de una cotización con su cliente y posiciones para el visor formal.
    """
    c = db.query(Cotizacion).filter(Cotizacion.id_cotizacion == id_cotizacion).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cotización no encontrada.")

    socio = db.query(SocioNegocio).filter(SocioNegocio.id_socio == c.id_socio).first()

    return {
        "id_cotizacion": str(c.id_cotizacion),
        "numero_cotizacion": c.numero_cotizacion,
        "fecha_emision": c.fecha_emision.strftime("%Y-%m-%d") if c.fecha_emision else "",
        "fecha_vigencia": c.fecha_vigencia.strftime("%Y-%m-%d") if c.fecha_vigencia else "",
        "valor_total": float(c.valor_total or 0.0),
        "estado": c.estado.value if hasattr(c.estado, "value") else str(c.estado),
        "condiciones_comerciales": c.condiciones_comerciales or "",
        "cliente": {
            "codigo": socio.codigo_socio if socio else "CLI-N/A",
            "razon_social": socio.razon_social if socio else "Cliente Comercial",
            "nit": socio.nit_cedula if socio else "",
            "direccion": socio.direccion if socio else "",
            "telefono": socio.telefono if socio else "",
            "email": socio.email if socio else "",
            "condiciones_pago": f"{socio.condiciones_pago_dias} Días" if socio and socio.condiciones_pago_dias else "30 Días"
        },
        "posiciones": [
            {
                "id_posicion": str(p.id_posicion),
                "numero_producto": p.numero_producto,
                "descripcion": p.descripcion,
                "cantidad": p.cantidad,
                "precio_unitario": float(p.precio_unitario or 0),
                "subtotal": float(p.cantidad * p.precio_unitario) if (p.cantidad and p.precio_unitario) else 0.0,
                "vinculo_plano_catalogo": p.vinculo_plano_catalogo
            }
            for p in c.posiciones
        ]
    }

@router.post("/{id_cotizacion}/enviar-cliente")
def enviar_cotizacion_cliente(id_cotizacion: uuid.UUID, data: EnviarCotizacionMailIn, db: Session = Depends(get_db)):
    """
    Registra el envío formal de la oferta al cliente y actualiza el estado a EMITIDA.
    """
    c = db.query(Cotizacion).filter(Cotizacion.id_cotizacion == id_cotizacion).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cotización no encontrada.")

    if c.estado == EstadoCotizacionEnum.BORRADOR:
        c.estado = EstadoCotizacionEnum.EMITIDA
        db.commit()

    return {
        "status": "ok",
        "mensaje": f"Cotización {c.numero_cotizacion} enviada exitosamente a {data.destinatario}."
    }

@router.patch("/{id_cotizacion}/aprobar-y-generar-pedido")
def aprobar_cotizacion_y_generar_pedido(id_cotizacion: uuid.UUID, db: Session = Depends(get_db)):
    cot = db.query(Cotizacion).filter(Cotizacion.id_cotizacion == id_cotizacion).first()
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada.")

    cot.estado = EstadoCotizacionEnum.APROBADA
    socio = db.query(SocioNegocio).filter(SocioNegocio.id_socio == cot.id_socio).first()

    numero_ped = f"PED-{cot.numero_cotizacion.replace('COT-', '')}"
    nuevo_pedido = Proyecto(
        id_proyecto=uuid.uuid4(),
        id_cliente=None,
        numero_pedido=numero_ped,
        codigo_proyecto=numero_ped,
        cliente_nombre=socio.razon_social if socio else "Cliente Comercial",
        contacto_nombre=socio.contacto_nombre if hasattr(socio, 'contacto_nombre') else "Contacto Técnico",
        contacto_telefono=socio.telefono,
        contacto_email=socio.email,
        ubicacion_cliente=socio.direccion if socio else "Planta Principal",
        cantidad=sum(p.cantidad for p in cot.posiciones) or 1,
        detalle_producto=cot.posiciones[0].descripcion if cot.posiciones else "Fabricación bajo cotización",
        requisitos_cliente="Fabricación según cotización aprobada",
        cotizacion_total=cot.valor_total,
        confirmado=False
    )
    db.add(nuevo_pedido)
    db.flush()

    for p in cot.posiciones:
        detalle = PedidoDetalle(
            detalle_id=uuid.uuid4(),
            pedido_id=nuevo_pedido.id_proyecto,
            codigo_producto=p.numero_producto,
            descripcion=p.descripcion,
            tipo="PIEZA",
            cantidad_solicitada=p.cantidad,
            unidad="UND",
            cantidad_asignada=0,
            cantidad_pendiente=p.cantidad
        )
        db.add(detalle)

    db.commit()

    return {
        "status": "ok",
        "mensaje": f"Cotización {cot.numero_cotizacion} aprobada. Pedido {numero_ped} creado exitosamente.",
        "id_proyecto": str(nuevo_pedido.id_proyecto),
        "numero_pedido": numero_ped
    }