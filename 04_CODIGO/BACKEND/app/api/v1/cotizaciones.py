# app/api/v1/cotizaciones.py
import re
import uuid
from typing import List, Literal, Optional, Any, Union
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.api.deps import obtener_usuario_actual, requerir_roles
from app.core.roles import ROLES_VENTAS
from app.services.auditoria import agregar_evento_trazabilidad
from app.db.models import (
    CondicionPago,
    Cotizacion,
    HistorialAccionesDocumento,
    Usuario,
    PosicionCotizacion,
    SocioNegocio,
    Proyecto,
    PedidoDetalle,
    EstadoCotizacionEnum,
    ArticuloInventario
)
from app.services.socios import codigo_socio_o_none, normalizar_nit
from app.services.stock_pt import CATEGORIA_PT, ORIGEN_STOCK_PT

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
    origen: Optional[str] = "PLANO"
    id_articulo: Optional[uuid.UUID] = None

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
    # Formato aprobado (migración 26)
    moneda: Literal["COP", "USD"] = "COP"
    validez_oferta_dias: Optional[int] = Field(default=None, gt=0)
    id_condicion_pago: Optional[int] = None
    termino_negociacion: Optional[str] = Field(default="Puesto en planta HD", max_length=100)
    observaciones: Optional[str] = None
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
def listar_cotizaciones(db: Session = Depends(get_db), usuario: dict = Depends(obtener_usuario_actual)):
    """
    Retorna el listado completo de cotizaciones emitidas para ProyectosView.jsx
    """
    cotizaciones_db = db.query(Cotizacion).order_by(Cotizacion.creado_en.desc()).all()
    con_pedido = {fila[0] for fila in db.query(Proyecto.codigo_proyecto).filter(Proyecto.cotizacion_total.isnot(None)).all()}
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
            "moneda": c.moneda or "COP",
            "estado": c.estado.value if hasattr(c.estado, "value") else str(c.estado),
            "numero_pedido": _numero_pedido(c) if _numero_pedido(c) in con_pedido else None,
        })
    return resultado


@router.get("/siguiente-consecutivo")
def siguiente_consecutivo(
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_VENTAS)),
):
    """Número sugerido para una cotización nueva, en el formato de la empresa HD-XXXXX-AA."""
    numeros = [fila[0] for fila in db.query(Cotizacion.numero_cotizacion).filter(Cotizacion.numero_cotizacion.like("HD-%")).all()]
    return {"siguiente_numero": siguiente_numero_hd(numeros, date.today())}

# Borrador (reglas/cotizacion-formato-y-borrador.md): una cotización nueva es BORRADOR, editable
# y eliminable sin dejar rastro en pedidos. Al emitirla pasa a EMITIDA y deja de ser editable.
# Solo una cotización EMITIDA se convierte en pedido.
MENSAJE_SOLO_BORRADOR = "Solo una cotización en BORRADOR se puede {accion}. Esta está en {estado}."


def _estado_de(cot: Cotizacion) -> str:
    return cot.estado.value if hasattr(cot.estado, "value") else str(cot.estado)


def _exigir_borrador(cot: Cotizacion, accion: str) -> None:
    estado = _estado_de(cot)
    if estado != EstadoCotizacionEnum.BORRADOR.value:
        raise HTTPException(status_code=409, detail=MENSAJE_SOLO_BORRADOR.format(accion=accion, estado=estado))


def _aplicar_formato(db: Session, cot: Cotizacion, data: "CotizacionCreateIn") -> None:
    """Moneda, validez, condición de pago (datos maestros activos), término, referencia y observaciones."""
    if data.id_condicion_pago is not None:
        condicion = db.query(CondicionPago).filter(
            CondicionPago.id_condicion_pago == data.id_condicion_pago, CondicionPago.activo.is_(True)
        ).first()
        if not condicion:
            raise HTTPException(status_code=400, detail="La condición de pago no existe o no está activa.")
    cot.moneda = data.moneda
    cot.validez_oferta_dias = data.validez_oferta_dias
    cot.id_condicion_pago = data.id_condicion_pago
    cot.termino_negociacion = (data.termino_negociacion or "").strip() or None
    cot.referencia = (data.referencia_global or "").strip()[:150] or None
    cot.observaciones = (data.observaciones or "").strip() or None


def _numero_pedido(cot: Cotizacion) -> str:
    return f"PED-{cot.numero_cotizacion.replace('COT-', '')}"


# Número de la empresa: HD-XXXXX-AA (consecutivo de 5 dígitos y año en 2 dígitos)
_NUMERO_HD = re.compile(r"^HD-(\d{5})-(\d{2})$")


def siguiente_numero_hd(numeros: List[str], hoy: date) -> str:
    """Siguiente HD-XXXXX-AA: el mayor consecutivo HD existente más uno (sin reiniciar por año)."""
    consecutivos = [int(m.group(1)) for m in (_NUMERO_HD.match(n or "") for n in numeros) if m]
    return f"HD-{(max(consecutivos) if consecutivos else 0) + 1:05d}-{hoy.year % 100:02d}"


def _elaborado_por(db: Session, cot: Cotizacion) -> dict:
    """Firma "Elaboró": el usuario que creó la cotización (evento COTIZACION_CREADA)."""
    evento = db.query(HistorialAccionesDocumento).filter(
        HistorialAccionesDocumento.tipo_entidad == "COTIZACION",
        HistorialAccionesDocumento.identificador_documento == cot.numero_cotizacion,
        HistorialAccionesDocumento.accion == "COTIZACION_CREADA",
    ).order_by(HistorialAccionesDocumento.fecha_hora).first()
    if not evento:
        return {"email": None, "nombre": None}
    usuario = db.query(Usuario).filter(Usuario.email == evento.usuario_responsable).first()
    return {"email": evento.usuario_responsable, "nombre": usuario.nombre_completo if usuario else evento.usuario_responsable}


def _resolver_socio(db: Session, data: "CotizacionCreateIn") -> SocioNegocio:
    """Socio de la cotización: por id, por código o por NIT; si no existe y hay NIT, se crea."""
    socio = None

    if data.id_socio:
        try:
            uuid_parsed = uuid.UUID(str(data.id_socio))
            socio = db.query(SocioNegocio).filter(SocioNegocio.id_socio == uuid_parsed).first()
        except (ValueError, AttributeError):
            socio = None

    # SCRUM-22: codigo_socio es el NIT solo con números; codigo_cliente y nit se comparan normalizados
    codigo_por_codigo = codigo_socio_o_none(data.codigo_cliente)
    codigo_por_nit = codigo_socio_o_none(data.nit)

    if not socio and codigo_por_codigo:
        socio = db.query(SocioNegocio).filter(SocioNegocio.codigo_socio == codigo_por_codigo).first()

    if not socio and codigo_por_nit:
        socio = db.query(SocioNegocio).filter(SocioNegocio.codigo_socio == codigo_por_nit).first()

    if not socio:
        # Cliente nuevo: sin NIT válido no se crea (antes se inventaban CLI-/NIT- aleatorios)
        nit_cliente = data.nit if codigo_por_nit else (data.codigo_cliente if codigo_por_codigo else None)
        if not nit_cliente:
            raise HTTPException(
                status_code=400,
                detail="No se puede crear un cliente sin NIT. Indique el NIT del cliente (solo números, "
                       "con dígito de verificación opcional tras un guion)."
            )
        socio = SocioNegocio(
            id_socio=uuid.uuid4(),
            codigo_socio=normalizar_nit(nit_cliente),
            nit_cedula=nit_cliente.strip().upper(),
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
    return socio


def _total_documento(data: "CotizacionCreateIn") -> float:
    return data.total_general if (data.total_general and data.total_general > 0) else sum(
        (p.cantidad * p.precio_unitario * (1 - p.descuento_pct / 100)) for p in data.posiciones
    )


def _agregar_posiciones(db: Session, cotizacion: Cotizacion, posiciones: List[PosicionCotizacionIn]) -> None:
    for pos in posiciones:
        origen_pos = (pos.origen or "PLANO").strip().upper()
        if origen_pos not in ("PLANO", ORIGEN_STOCK_PT):
            raise HTTPException(status_code=400, detail="El origen de la posición debe ser PLANO o STOCK_PT.")
        sku_pos = pos.numero_producto or "REF-COT"
        descripcion_pos = pos.descripcion
        id_articulo_pos = None
        if origen_pos == ORIGEN_STOCK_PT:
            # La cotización no es vinculante: solo valida el artículo PT y fija SKU/descripción.
            # No reserva ni modifica el saldo de inventario.
            art = (
                db.query(ArticuloInventario)
                .filter(ArticuloInventario.id_articulo == pos.id_articulo)
                .first()
                if pos.id_articulo else None
            )
            if art is None or art.categoria != CATEGORIA_PT:
                raise HTTPException(
                    status_code=400,
                    detail="La posición de stock PT requiere un artículo existente de categoría PRODUCTO_TERMINADO."
                )
            sku_pos = art.codigo_sku
            descripcion_pos = art.nombre
            id_articulo_pos = art.id_articulo
        db.add(PosicionCotizacion(
            id_posicion=uuid.uuid4(),
            id_cotizacion=cotizacion.id_cotizacion,
            numero_producto=sku_pos,
            descripcion=descripcion_pos,
            cantidad=int(pos.cantidad),
            precio_unitario=pos.precio_unitario,
            vinculo_plano_catalogo=pos.vinculo_plano_catalogo,
            origen=origen_pos,
            id_articulo=id_articulo_pos
        ))


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_cotizacion(
    data: CotizacionCreateIn,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_VENTAS)),
):
    try:
        socio = _resolver_socio(db, data)
        total_doc = _total_documento(data)

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
        _aplicar_formato(db, nueva_cot, data)
        db.add(nueva_cot)
        db.flush()

        _agregar_posiciones(db, nueva_cot, data.posiciones)

        agregar_evento_trazabilidad(
            db,
            tipo_entidad="COTIZACION",
            identificador=nueva_cot.numero_cotizacion,
            accion="COTIZACION_CREADA",
            usuario=usuario["email"],
            area="VENTAS",
            estado_nuevo="BORRADOR",
            motivo=f"id_cotizacion={nueva_cot.id_cotizacion}; id_socio={socio.id_socio}",
        )

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

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al guardar la cotización: {str(e)}"
        )

@router.get("/{id_cotizacion}")
def obtener_detalle_cotizacion(
    id_cotizacion: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
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
        "moneda": c.moneda or "COP",
        "validez_oferta_dias": c.validez_oferta_dias,
        "condicion_pago": (
            {"id_condicion_pago": c.condicion_pago.id_condicion_pago, "descripcion": c.condicion_pago.descripcion}
            if c.condicion_pago else None
        ),
        "termino_negociacion": c.termino_negociacion or "",
        "referencia": c.referencia or "",
        "observaciones": c.observaciones or "",
        "elaborado_por": _elaborado_por(db, c),
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
                "vinculo_plano_catalogo": p.vinculo_plano_catalogo,
                "origen": p.origen or "PLANO",
                "id_articulo": str(p.id_articulo) if p.id_articulo else None
            }
            for p in c.posiciones
        ]
    }

@router.put("/{id_cotizacion}")
def editar_cotizacion_borrador(
    id_cotizacion: uuid.UUID,
    data: CotizacionCreateIn,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_VENTAS)),
):
    """Reemplaza cliente, fechas, condiciones y posiciones de una cotización en BORRADOR.
    El número de la cotización no cambia."""
    cot = db.query(Cotizacion).filter(Cotizacion.id_cotizacion == id_cotizacion).with_for_update().first()
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada.")
    _exigir_borrador(cot, "editar")
    try:
        socio = _resolver_socio(db, data)
        cot.id_socio = socio.id_socio
        cot.fecha_emision = data.fecha_emision or cot.fecha_emision
        cot.fecha_vigencia = data.fecha_vigencia
        cot.valor_total = _total_documento(data)
        cot.condiciones_comerciales = data.condiciones_comerciales
        _aplicar_formato(db, cot, data)
        cot.posiciones.clear()
        db.flush()
        _agregar_posiciones(db, cot, data.posiciones)
        agregar_evento_trazabilidad(
            db,
            tipo_entidad="COTIZACION",
            identificador=cot.numero_cotizacion,
            accion="COTIZACION_EDITADA",
            usuario=usuario["email"],
            area="VENTAS",
            estado_anterior="BORRADOR",
            estado_nuevo="BORRADOR",
            motivo=f"id_cotizacion={cot.id_cotizacion}; posiciones={len(data.posiciones)}",
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al editar la cotización: {str(e)}")
    return {
        "id_cotizacion": str(cot.id_cotizacion),
        "numero_cotizacion": cot.numero_cotizacion,
        "id_socio": socio.razon_social,
        "fecha_emision": str(cot.fecha_emision),
        "valor_total": float(cot.valor_total),
        "estado": "BORRADOR"
    }


@router.delete("/{id_cotizacion}")
def eliminar_cotizacion_borrador(
    id_cotizacion: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_VENTAS)),
):
    """Elimina una cotización en BORRADOR con sus posiciones. Un borrador nunca generó pedido,
    así que no queda rastro en pedidos; la trazabilidad registra la eliminación."""
    cot = db.query(Cotizacion).filter(Cotizacion.id_cotizacion == id_cotizacion).with_for_update().first()
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada.")
    _exigir_borrador(cot, "eliminar")
    numero = cot.numero_cotizacion
    agregar_evento_trazabilidad(
        db,
        tipo_entidad="COTIZACION",
        identificador=numero,
        accion="COTIZACION_ELIMINADA",
        usuario=usuario["email"],
        area="VENTAS",
        estado_anterior="BORRADOR",
        motivo=f"id_cotizacion={cot.id_cotizacion}",
    )
    db.delete(cot)
    db.commit()
    return {"status": "ok", "mensaje": f"Cotización {numero} eliminada."}


@router.post("/{id_cotizacion}/emitir")
def emitir_cotizacion(
    id_cotizacion: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_VENTAS)),
):
    """BORRADOR → EMITIDA. Desde aquí la cotización no se edita: un cambio exige una cotización nueva."""
    cot = db.query(Cotizacion).filter(Cotizacion.id_cotizacion == id_cotizacion).with_for_update().first()
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada.")
    _exigir_borrador(cot, "emitir")
    if not cot.posiciones:
        raise HTTPException(status_code=400, detail="No se puede emitir una cotización sin posiciones.")
    cot.estado = EstadoCotizacionEnum.EMITIDA
    agregar_evento_trazabilidad(
        db,
        tipo_entidad="COTIZACION",
        identificador=cot.numero_cotizacion,
        accion="COTIZACION_EMITIDA",
        usuario=usuario["email"],
        area="VENTAS",
        estado_anterior="BORRADOR",
        estado_nuevo="EMITIDA",
        motivo=f"id_cotizacion={cot.id_cotizacion}",
    )
    db.commit()
    return {"status": "ok", "mensaje": f"Cotización {cot.numero_cotizacion} emitida.", "estado": "EMITIDA"}


@router.post("/{id_cotizacion}/enviar-cliente")
def enviar_cotizacion_cliente(
    id_cotizacion: uuid.UUID,
    data: EnviarCotizacionMailIn,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_VENTAS)),
):
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
def aprobar_cotizacion_y_generar_pedido(
    id_cotizacion: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(ROLES_VENTAS)),
):
    cot = (
        db.query(Cotizacion)
        .filter(Cotizacion.id_cotizacion == id_cotizacion)
        .with_for_update()
        .first()
    )
    if not cot:
        raise HTTPException(status_code=404, detail="Cotización no encontrada.")

    numero_ped = _numero_pedido(cot)
    estado_actual = cot.estado.value if hasattr(cot.estado, "value") else str(cot.estado)
    # EMITIDA reemplaza a APROBADA (reglas/cotizacion-formato-y-borrador.md): al convertirse en pedido
    # la cotización sigue EMITIDA; si ya tiene pedido se devuelve ese (APROBADA solo en datos antiguos).
    # El pedido nacido de una cotización es el único con cotizacion_total.
    pedido_existente = db.query(Proyecto).filter(Proyecto.codigo_proyecto == numero_ped).first()
    if pedido_existente and pedido_existente.cotizacion_total is None:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe el pedido {numero_ped} sin cotización de origen; no se puede reutilizar su número.",
        )
    if pedido_existente and estado_actual in (EstadoCotizacionEnum.EMITIDA.value, EstadoCotizacionEnum.APROBADA.value):
        db.rollback()
        return {
            "status": "ok",
            "mensaje": f"La cotización {cot.numero_cotizacion} ya tiene el pedido {numero_ped}.",
            "id_proyecto": str(pedido_existente.id_proyecto),
            "numero_pedido": numero_ped,
        }

    if estado_actual != EstadoCotizacionEnum.EMITIDA.value:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Solo una cotización EMITIDA se convierte en pedido. Esta está en {estado_actual}: emítala primero.",
        )

    socio = db.query(SocioNegocio).filter(SocioNegocio.id_socio == cot.id_socio).first()

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
        requisitos_cliente="Fabricación según cotización emitida",
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
            origen=p.origen or "PLANO",
            id_articulo=p.id_articulo,
            cantidad_solicitada=p.cantidad,
            unidad="UND",
            cantidad_asignada=0,
            cantidad_pendiente=p.cantidad
        )
        db.add(detalle)

    agregar_evento_trazabilidad(
        db,
        tipo_entidad="COTIZACION",
        identificador=cot.numero_cotizacion,
        accion="COTIZACION_CONVERTIDA_EN_PEDIDO",
        usuario=usuario["email"],
        area="VENTAS",
        estado_anterior=estado_actual,
        estado_nuevo=estado_actual,
        motivo=f"id_proyecto={nuevo_pedido.id_proyecto}; pedido={numero_ped}",
    )
    agregar_evento_trazabilidad(
        db,
        tipo_entidad="PEDIDO",
        identificador=numero_ped,
        accion="PEDIDO_CREADO_DESDE_COTIZACION",
        usuario=usuario["email"],
        area="VENTAS",
        estado_nuevo="BORRADOR",
        motivo=f"id_proyecto={nuevo_pedido.id_proyecto}; cotizacion={cot.numero_cotizacion}",
    )

    db.commit()

    return {
        "status": "ok",
        "mensaje": f"Cotización {cot.numero_cotizacion} convertida en el pedido {numero_ped}.",
        "id_proyecto": str(nuevo_pedido.id_proyecto),
        "numero_pedido": numero_ped
    }
