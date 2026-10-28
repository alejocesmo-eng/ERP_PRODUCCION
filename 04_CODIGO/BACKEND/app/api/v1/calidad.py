# app/api/v1/calidad.py
import base64
import binascii
from io import BytesIO
from typing import List, Optional
from decimal import Decimal
from html import escape
from uuid import UUID, uuid4
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, ProgrammingError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db.database import get_db
from app.db.models import (
    AccionCAPA,
    EstadoNCEnum,
    EstadoOPEnum,
    NoConformidad,
    OrdenProduccion,
    ServicioTerceroOP,
)
from app.db.models_calidad import InspeccionCalidad
from app.db.models_produccion import (
    NotificacionLider,
    TipoNotificacionEnum,
    TipoUnidadPlantaEnum,
)

router = APIRouter()

# =============================================================================
# SCHEMAS PYDANTIC - INSPECCIÓN DE CALIDAD
# =============================================================================

class MedicionDimensional(BaseModel):
    caracteristica: str = Field(..., min_length=1, max_length=100)
    nominal: float
    tolerancia_min: float
    tolerancia_max: float
    valor_medido: float


class InspeccionCalidadCreate(BaseModel):
    codigo_op: str = Field(..., example="4007256")
    codigo_plano: str = Field(..., example="PLN-PED-092-A")
    inspector_nombre: str = Field(..., example="Juan Pérez")
    resultado_inspeccion: str = Field(..., example="APROBADO_DESPACHO") # APROBADO_DESPACHO | APROBADO_TRATAMIENTO | RECHAZADO
    requiere_tratamiento: bool = False
    descripcion_tratamiento: Optional[str] = None
    piezas_enviadas_tratamiento: Optional[int] = 0
    proveedor_tratamiento_email: Optional[str] = None
    proveedor_tratamiento: Optional[str] = None
    costo_tratamiento: Decimal = Field(Decimal("0"), ge=0)
    mediciones_dimensionales: List[MedicionDimensional] = Field(default_factory=list)
    registros_fotograficos: List[str] = Field(default_factory=list)
    observaciones_inspector: Optional[str] = None

class InspeccionCalidadResponse(BaseModel):
    id_inspeccion: UUID
    codigo_op: str
    codigo_plano: str
    inspector_nombre: str
    resultado_inspeccion: str
    requiere_tratamiento: bool
    descripcion_tratamiento: Optional[str] = None
    piezas_enviadas_tratamiento: int
    proveedor_tratamiento_email: Optional[str] = None
    proveedor_tratamiento: Optional[str] = None
    costo_tratamiento: Decimal
    mediciones_dimensionales: List[dict]
    registros_fotograficos: List[str]
    informe_tratamiento_html: Optional[str] = None
    informe_tratamiento_pdf_base64: Optional[str] = None
    observaciones_inspector: Optional[str] = None
    notificado_jefe_produccion: bool
    fecha_inspeccion: datetime

    class Config:
        from_attributes = True


# =============================================================================
# SCHEMAS PYDANTIC - NO CONFORMIDADES (ISO 9001:2026 - ISO 8.7)
# =============================================================================

class NoConformidadCreate(BaseModel):
    codigo_nc: str = Field(..., example="NC-2026-0001")
    id_op: Optional[UUID] = None
    codigo_op: Optional[str] = None
    descripcion: str
    origen: Optional[str] = "INSPECCION_PROCESO"
    gravedad: Optional[str] = "MENOR"
    accion_correctiva: Optional[str] = None
    analisis_causa_5porques: Optional[str] = None
    proceso_origen: Optional[str] = None
    causa_raiz: Optional[str] = None
    piezas_scrap: int = Field(0, ge=0)
    disposicion: Optional[str] = None

class NoConformidadResponse(BaseModel):
    id_nc: UUID
    codigo_nc: str
    id_op: Optional[UUID] = None
    descripcion: str
    origen: str
    gravedad: str
    estado: str
    accion_correctiva: Optional[str] = None
    analisis_causa_5porques: Optional[str] = None
    proceso_origen: Optional[str] = None
    causa_raiz: Optional[str] = None
    piezas_scrap: int = 0
    disposicion: Optional[str] = None
    eficacia_verificada: bool
    creado_en: datetime

    class Config:
        from_attributes = True


class AccionCAPACreate(BaseModel):
    accion_correctiva: str = Field(..., min_length=3)
    responsable_id: Optional[UUID] = None
    fecha_compromiso: date


class AccionCAPACierre(BaseModel):
    evidencia_cierre: str = Field(..., min_length=3)


def _respuesta_no_conformidad(nc: NoConformidad) -> NoConformidadResponse:
    return NoConformidadResponse(
        id_nc=nc.id_nc,
        codigo_nc=nc.codigo_nc,
        id_op=nc.id_op,
        descripcion=nc.descripcion,
        origen=nc.origen or "INSPECCION_PROCESO",
        gravedad=nc.gravedad or "MENOR",
        estado=nc.estado.value if hasattr(nc.estado, "value") else str(nc.estado),
        accion_correctiva=nc.accion_correctiva,
        analisis_causa_5porques=nc.analisis_causa_5porques,
        proceso_origen=nc.origen,
        causa_raiz=nc.causa_raiz,
        piezas_scrap=nc.piezas_scrap or 0,
        disposicion=nc.disposicion,
        eficacia_verificada=nc.eficacia_verificada or False,
        creado_en=nc.creado_en,
    )


# =============================================================================
# FUNCIONES AUXILIARES (PLACEHOLDERS)
# =============================================================================

def _generar_informe_tratamiento_html(inspeccion: InspeccionCalidadCreate) -> str:
    mediciones = "".join(
        "<tr>"
        f"<td>{escape(medicion.caracteristica)}</td>"
        f"<td>{medicion.nominal:g}</td>"
        f"<td>{medicion.tolerancia_min:g} – {medicion.tolerancia_max:g}</td>"
        f"<td>{medicion.valor_medido:g}</td>"
        f"<td>{'Conforme' if medicion.tolerancia_min <= medicion.valor_medido <= medicion.tolerancia_max else 'Fuera de tolerancia'}</td>"
        "</tr>"
        for medicion in inspeccion.mediciones_dimensionales
    )
    filas_medicion = mediciones or "<tr><td colspan='5'>Sin mediciones consignadas</td></tr>"
    return (
        "<!doctype html><html lang='es'><meta charset='utf-8'>"
        "<title>Informe de servicio térmico</title>"
        "<style>body{font:14px Arial;color:#1e293b;margin:32px}h1{color:#334155}"
        "table{border-collapse:collapse;width:100%;margin-top:20px}th,td{border:1px solid #cbd5e1;padding:8px;text-align:left}"
        "th{background:#f1f5f9}</style><body>"
        "<h1>Informe técnico de tratamiento térmico</h1>"
        f"<p><b>Orden de producción:</b> {escape(inspeccion.codigo_op)}</p>"
        f"<p><b>Plano:</b> {escape(inspeccion.codigo_plano)}</p>"
        f"<p><b>Proveedor:</b> {escape(inspeccion.proveedor_tratamiento or '')}</p>"
        f"<p><b>Proceso solicitado:</b> {escape(inspeccion.descripcion_tratamiento or '')}</p>"
        f"<p><b>Piezas:</b> {inspeccion.piezas_enviadas_tratamiento or 0}</p>"
        "<h2>Verificación dimensional previa</h2>"
        "<table><thead><tr><th>Característica</th><th>Nominal</th><th>Límites</th><th>Medido</th><th>Dictamen</th></tr></thead>"
        f"<tbody>{filas_medicion}</tbody></table>"
        f"<p><b>Observaciones:</b> {escape(inspeccion.observaciones_inspector or '')}</p>"
        "</body></html>"
    )


def _generar_informe_tratamiento_pdf(inspeccion: InspeccionCalidadCreate) -> str:
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Informe técnico de tratamiento térmico · OP {inspeccion.codigo_op}",
    )
    estilos = getSampleStyleSheet()
    contenido = [
        Paragraph("Informe técnico de tratamiento térmico", estilos["Title"]),
        Spacer(1, 5 * mm),
        Paragraph(f"<b>Orden de producción:</b> {escape(inspeccion.codigo_op)}", estilos["BodyText"]),
        Paragraph(f"<b>Plano:</b> {escape(inspeccion.codigo_plano)}", estilos["BodyText"]),
        Paragraph(f"<b>Proveedor:</b> {escape(inspeccion.proveedor_tratamiento or '')}", estilos["BodyText"]),
        Paragraph(f"<b>Proceso solicitado:</b> {escape(inspeccion.descripcion_tratamiento or '')}", estilos["BodyText"]),
        Paragraph(f"<b>Piezas:</b> {inspeccion.piezas_enviadas_tratamiento or 0}", estilos["BodyText"]),
        Spacer(1, 5 * mm),
        Paragraph("Verificación dimensional previa", estilos["Heading2"]),
    ]
    filas = [["Característica", "Nominal", "Límites", "Medido", "Dictamen"]]
    for medicion in inspeccion.mediciones_dimensionales:
        dictamen = (
            "Conforme"
            if medicion.tolerancia_min <= medicion.valor_medido <= medicion.tolerancia_max
            else "Fuera de tolerancia"
        )
        filas.append([
            Paragraph(escape(medicion.caracteristica), estilos["BodyText"]),
            f"{medicion.nominal:g}",
            f"{medicion.tolerancia_min:g} – {medicion.tolerancia_max:g}",
            f"{medicion.valor_medido:g}",
            dictamen,
        ])
    tabla = Table(filas, repeatRows=1, colWidths=[48 * mm, 22 * mm, 34 * mm, 22 * mm, 40 * mm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    contenido.extend([tabla, Spacer(1, 5 * mm)])
    contenido.append(Paragraph(
        f"<b>Observaciones:</b> {escape(inspeccion.observaciones_inspector or '')}",
        estilos["BodyText"],
    ))
    documento.build(contenido)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _simular_envio_correo_proveedor(email: str, codigo_op: str) -> None:
    print(f"[CORREO SIMULADO] Informe de tratamiento de OP {codigo_op} preparado para {email}.")


def _es_tabla_inspeccion_ausente(error: Exception) -> bool:
    causa = getattr(error, "orig", None)
    codigo_sql = getattr(causa, "pgcode", None) or getattr(causa, "sqlstate", None)
    if codigo_sql == "42P01":
        return True

    return "no such table: inspecciones_calidad" in str(causa or error).lower()


# =============================================================================
# ENDPOINTS API (CALIDAD DE PRODUCTO E INSPECCIÓN)
# =============================================================================

@router.get("/ordenes-abiertas", response_model=List[dict])
def listar_ordenes_abiertas(db: Session = Depends(get_db)):
    """Lista todas las órdenes de producción que todavía no están cerradas o canceladas."""
    estados_finales = (
        EstadoOPEnum.CERRADA,
        EstadoOPEnum.CANCELADA,
        EstadoOPEnum.TERMINADA,
        EstadoOPEnum.INSPECCION_CALIDAD,
        EstadoOPEnum.EN_INSPECCION,
    )
    ordenes = db.query(OrdenProduccion).filter(
        ~OrdenProduccion.estado.in_(estados_finales)
    ).all()

    resultado = []
    for op in ordenes:
        proyecto = op.proyecto
        plano = op.plano or (
            proyecto.planos[0] if proyecto and proyecto.planos else None
        )
        estado = op.estado.value if hasattr(op.estado, "value") else str(op.estado)
        resultado.append({
            "id_proyecto": proyecto.id_proyecto if proyecto else op.id_proyecto,
            "codigo_op": op.codigo_op,
            "numero_pedido": proyecto.numero_pedido if proyecto else None,
            "cliente_nombre": proyecto.cliente_nombre if proyecto else None,
            "ubicacion_cliente": proyecto.ubicacion_cliente if proyecto else None,
            "detalle_producto": proyecto.detalle_producto if proyecto else None,
            "cantidad": op.cantidad_fabricar,
            "requisitos_cliente": proyecto.requisitos_cliente if proyecto else None,
            "id_plano": plano.id_plano if plano else None,
            "codigo_plano": plano.codigo_plano if plano else None,
            "revision": plano.revision if plano else None,
            "dibujante_asignado": plano.dibujante_asignado if plano else None,
            "unidad_planta": plano.unidad_planta if plano else None,
            "material_requerido": plano.material_requerido if plano else None,
            "archivo_url": plano.archivo_url if plano else None,
            "estado_diseno": plano.estado_diseno if plano else None,
            "fecha_entrega_produccion": (
                str(plano.fecha_entrega_produccion)
                if plano and plano.fecha_entrega_produccion else None
            ),
            "fecha_compromiso": (
                str(proyecto.fecha_compromiso)
                if proyecto and proyecto.fecha_compromiso else None
            ),
            "porcentaje_avance": op.porcentaje_avance or 0.0,
            "estado_produccion": estado,
            "observaciones": op.observaciones,
            "creado_en": op.creado_en,
            "productos_componentes": []
        })

    return resultado


@router.get("/inspeccion", response_model=List[InspeccionCalidadResponse])
def listar_inspecciones_calidad(db: Session = Depends(get_db)):
    """Lista inspecciones registradas; responde vacío si la tabla aún no fue creada."""
    try:
        return db.query(InspeccionCalidad).order_by(
            InspeccionCalidad.fecha_inspeccion.desc()
        ).all()
    except (OperationalError, ProgrammingError) as error:
        db.rollback()
        if _es_tabla_inspeccion_ausente(error):
            return []
        raise


@router.get("/ordenes-terminadas", response_model=List[dict])
def listar_ordenes_terminadas(db: Session = Depends(get_db)):
    """
    Lista las órdenes de producción marcadas como terminadas desde el módulo de producción,
    listas para la inspección de calidad.
    """
    # Consulta a BD real
    ops_db = db.query(OrdenProduccion).filter(
        OrdenProduccion.estado.in_([
            EstadoOPEnum.TERMINADA,
            EstadoOPEnum.INSPECCION_CALIDAD,
            EstadoOPEnum.EN_INSPECCION,
        ])
    ).all()

    if ops_db:
        resultado = []
        for op in ops_db:
            resultado.append({
                "codigo_op": op.codigo_op,
                "codigo_plano": op.plano.codigo_plano if op.plano else None,
                "producto": op.proyecto.detalle_producto if op.proyecto else "Pieza Industrial",
                "cantidad_terminada": op.cantidad_fabricar or 1,
                "estado_op": op.estado.value if hasattr(op.estado, 'value') else str(op.estado),
                "url_plano_pdf": op.plano.archivo_url if op.plano else None
            })
        return resultado

    return []


@router.post("/inspeccionar", response_model=InspeccionCalidadResponse, status_code=status.HTTP_201_CREATED)
def registrar_inspeccion_calidad(
    inspeccion_in: InspeccionCalidadCreate, 
    db: Session = Depends(get_db)
):
    """
    Registra el resultado de inspección, emite informes de tratamiento térmico si aplica,
    o notifica al jefe de producción si la orden se aprueba para despacho.
    """
    if inspeccion_in.resultado_inspeccion not in ['APROBADO_DESPACHO', 'APROBADO_TRATAMIENTO', 'RECHAZADO']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Resultado de inspección no válido."
        )
    if not inspeccion_in.registros_fotograficos:
        raise HTTPException(status_code=422, detail="Debe adjuntar al menos una fotografía JPG o PNG.")
    if len(inspeccion_in.registros_fotograficos) > 10:
        raise HTTPException(status_code=422, detail="Se permiten máximo 10 fotografías por inspección.")
    for foto in inspeccion_in.registros_fotograficos:
        prefijo, separador, contenido = foto.partition(",")
        if (
            not separador
            or prefijo not in ("data:image/jpeg;base64", "data:image/png;base64")
            or len(foto) > 7_000_000
        ):
            raise HTTPException(status_code=422, detail="Cada evidencia debe ser una imagen JPG o PNG de máximo 5 MB.")
        try:
            imagen = base64.b64decode(contenido, validate=True)
        except (binascii.Error, ValueError) as error:
            raise HTTPException(status_code=422, detail="Una de las fotografías no tiene una codificación válida.") from error
        firma_valida = (
            prefijo == "data:image/png;base64" and imagen.startswith(b"\x89PNG\r\n\x1a\n")
        ) or (
            prefijo == "data:image/jpeg;base64" and imagen.startswith(b"\xff\xd8\xff")
        )
        if not firma_valida:
            raise HTTPException(status_code=422, detail="El formato real de una fotografía no coincide con su extensión.")
    if not inspeccion_in.mediciones_dimensionales:
        raise HTTPException(status_code=422, detail="Registre al menos una medición dimensional antes de emitir el dictamen.")
    if any(
        medicion.tolerancia_min > medicion.tolerancia_max
        for medicion in inspeccion_in.mediciones_dimensionales
    ):
        raise HTTPException(status_code=422, detail="El límite mínimo no puede superar el límite máximo de tolerancia.")

    notificado = False
    informe_html = None
    informe_pdf_base64 = None
    orden = db.query(OrdenProduccion).filter(
        OrdenProduccion.codigo_op == inspeccion_in.codigo_op
    ).with_for_update().first()
    if not orden:
        raise HTTPException(status_code=404, detail="No existe la orden de producción indicada.")
    estados_inspeccionables = {
        EstadoOPEnum.TERMINADA,
        EstadoOPEnum.INSPECCION_CALIDAD,
        EstadoOPEnum.EN_INSPECCION,
    }
    if orden.estado not in estados_inspeccionables:
        raise HTTPException(
            status_code=409,
            detail="La orden debe estar terminada o en inspección de calidad para registrar el dictamen.",
        )

    if inspeccion_in.resultado_inspeccion == 'APROBADO_TRATAMIENTO':
        if (
            not inspeccion_in.descripcion_tratamiento
            or not inspeccion_in.proveedor_tratamiento_email
            or not inspeccion_in.proveedor_tratamiento
            or not inspeccion_in.piezas_enviadas_tratamiento
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Indique proveedor, correo, proceso y cantidad para el tratamiento."
            )
        if inspeccion_in.piezas_enviadas_tratamiento > (orden.cantidad_fabricar or 0):
            raise HTTPException(status_code=422, detail="La cantidad enviada supera las piezas de la orden.")
        informe_html = _generar_informe_tratamiento_html(inspeccion_in)
        informe_pdf_base64 = _generar_informe_tratamiento_pdf(inspeccion_in)

    elif inspeccion_in.resultado_inspeccion == 'APROBADO_DESPACHO':
        orden.estado = EstadoOPEnum.LISTA_PARA_LIBERAR
        unidad_planta = getattr(orden.plano, "unidad_planta", None)
        if hasattr(unidad_planta, "value"):
            unidad_planta = unidad_planta.value
        try:
            unidad_planta = TipoUnidadPlantaEnum(unidad_planta)
        except (TypeError, ValueError):
            unidad_planta = TipoUnidadPlantaEnum.SERVICIOS
        db.add(NotificacionLider(
            unidad_planta=unidad_planta,
            tipo_notificacion=TipoNotificacionEnum.CALIDAD_APROBADA_DESPACHO,
            titulo=f"Producto aprobado para despacho · Orden {inspeccion_in.codigo_op}",
            mensaje=f"La inspección de calidad aprobó la orden {inspeccion_in.codigo_op}; queda pendiente el cierre por Producción.",
            codigo_op=inspeccion_in.codigo_op,
            codigo_plano=inspeccion_in.codigo_plano,
            operario_nombre=inspeccion_in.inspector_nombre,
            maquina_codigo="CONTROL_CALIDAD",
            piezas_reportadas=orden.cantidad_fabricar or 0,
        ))
        notificado = True

    nueva_inspeccion = InspeccionCalidad(
        codigo_op=inspeccion_in.codigo_op,
        codigo_plano=inspeccion_in.codigo_plano,
        inspector_id=uuid4(),
        inspector_nombre=inspeccion_in.inspector_nombre,
        resultado_inspeccion=inspeccion_in.resultado_inspeccion,
        requiere_tratamiento=inspeccion_in.resultado_inspeccion == "APROBADO_TRATAMIENTO",
        descripcion_tratamiento=inspeccion_in.descripcion_tratamiento,
        piezas_enviadas_tratamiento=inspeccion_in.piezas_enviadas_tratamiento or 0,
        proveedor_tratamiento_email=inspeccion_in.proveedor_tratamiento_email,
        proveedor_tratamiento=inspeccion_in.proveedor_tratamiento,
        costo_tratamiento=inspeccion_in.costo_tratamiento,
        mediciones_dimensionales=[
            {
                **medicion.model_dump(),
                "conforme": medicion.tolerancia_min <= medicion.valor_medido <= medicion.tolerancia_max,
            }
            for medicion in inspeccion_in.mediciones_dimensionales
        ],
        informe_tratamiento_html=informe_html,
        registros_fotograficos=inspeccion_in.registros_fotograficos,
        observaciones_inspector=inspeccion_in.observaciones_inspector,
        notificado_jefe_produccion=notificado
    )

    try:
        db.add(nueva_inspeccion)
        if inspeccion_in.resultado_inspeccion == "APROBADO_TRATAMIENTO":
            db.add(ServicioTerceroOP(
                op_id=orden.id_op,
                proveedor=inspeccion_in.proveedor_tratamiento,
                descripcion=inspeccion_in.descripcion_tratamiento,
                numero_factura=f"TRAT-{inspeccion_in.codigo_op}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
                costo=inspeccion_in.costo_tratamiento,
            ))
        db.commit()
        db.refresh(nueva_inspeccion)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo guardar la inspección y su registro de servicio.") from e

    if inspeccion_in.resultado_inspeccion == "APROBADO_TRATAMIENTO":
        _simular_envio_correo_proveedor(
            inspeccion_in.proveedor_tratamiento_email,
            inspeccion_in.codigo_op,
        )
    respuesta = InspeccionCalidadResponse.model_validate(nueva_inspeccion)
    return respuesta.model_copy(update={
        "informe_tratamiento_pdf_base64": informe_pdf_base64,
    })


# =============================================================================
# ENDPOINTS API (NO CONFORMIDADES - PERSISTENCIA REAL POSTGRESQL)
# =============================================================================

@router.get("/no-conformidades", response_model=List[NoConformidadResponse])
def listar_no_conformidades(db: Session = Depends(get_db)):
    """Consulta la lista persistida de No Conformidades en PostgreSQL."""
    ncs = db.query(NoConformidad).order_by(NoConformidad.creado_en.desc()).all()
    resultado = []
    for nc in ncs:
        resultado.append(NoConformidadResponse(
            id_nc=nc.id_nc,
            codigo_nc=nc.codigo_nc,
            id_op=nc.id_op,
            descripcion=nc.descripcion,
            origen=nc.origen or "INSPECCION_PROCESO",
            gravedad=nc.gravedad or "MENOR",
            estado=nc.estado.value if hasattr(nc.estado, 'value') else str(nc.estado),
            accion_correctiva=nc.accion_correctiva,
            analisis_causa_5porques=nc.analisis_causa_5porques,
            proceso_origen=nc.origen,
            causa_raiz=nc.causa_raiz,
            piezas_scrap=nc.piezas_scrap or 0,
            disposicion=nc.disposicion,
            eficacia_verificada=nc.eficacia_verificada or False,
            creado_en=nc.creado_en
        ))
    return resultado


@router.post("/no-conformidades", response_model=NoConformidadResponse, status_code=status.HTTP_201_CREATED)
def registrar_no_conformidad(
    nc_in: NoConformidadCreate,
    db: Session = Depends(get_db)
):
    """Registra una No Conformidad persistente en PostgreSQL (ISO 9001:2026)."""
    existente = db.query(NoConformidad).filter(NoConformidad.codigo_nc == nc_in.codigo_nc).first()
    if existente:
        raise HTTPException(status_code=400, detail=f"Ya existe una No Conformidad con código '{nc_in.codigo_nc}'.")
    orden = None
    if nc_in.codigo_op:
        orden = db.query(OrdenProduccion).filter(
            OrdenProduccion.codigo_op == nc_in.codigo_op.strip()
        ).first()
        if not orden:
            raise HTTPException(status_code=404, detail=f"No existe la OP {nc_in.codigo_op}.")
        if nc_in.id_op and nc_in.id_op != orden.id_op:
            raise HTTPException(status_code=422, detail="El identificador y el código de OP no corresponden.")
    elif nc_in.id_op:
        orden = db.query(OrdenProduccion).filter(OrdenProduccion.id_op == nc_in.id_op).first()
        if not orden:
            raise HTTPException(status_code=404, detail="No existe la OP indicada.")

    nueva_nc = NoConformidad(
        codigo_nc=nc_in.codigo_nc,
        id_op=orden.id_op if orden else None,
        descripcion=nc_in.descripcion,
        origen=nc_in.proceso_origen or nc_in.origen or "INSPECCION_PROCESO",
        gravedad=nc_in.gravedad or "MENOR",
        estado=EstadoNCEnum.REGISTRADA,
        accion_correctiva=nc_in.accion_correctiva,
        analisis_causa_5porques=nc_in.analisis_causa_5porques,
        causa_raiz=nc_in.causa_raiz,
        piezas_scrap=nc_in.piezas_scrap,
        disposicion=nc_in.disposicion,
        eficacia_verificada=False
    )

    try:
        db.add(nueva_nc)
        db.commit()
        db.refresh(nueva_nc)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al registrar No Conformidad: {str(e)}")

    return NoConformidadResponse(
        id_nc=nueva_nc.id_nc,
        codigo_nc=nueva_nc.codigo_nc,
        id_op=nueva_nc.id_op,
        descripcion=nueva_nc.descripcion,
        origen=nueva_nc.origen,
        gravedad=nueva_nc.gravedad,
        estado=nueva_nc.estado.value if hasattr(nueva_nc.estado, 'value') else str(nueva_nc.estado),
        accion_correctiva=nueva_nc.accion_correctiva,
        analisis_causa_5porques=nueva_nc.analisis_causa_5porques,
        proceso_origen=nueva_nc.origen,
        causa_raiz=nueva_nc.causa_raiz,
        piezas_scrap=nueva_nc.piezas_scrap or 0,
        disposicion=nueva_nc.disposicion,
        eficacia_verificada=nueva_nc.eficacia_verificada,
        creado_en=nueva_nc.creado_en
    )


@router.get("/rnc")
def listar_rnc(
    cliente: Optional[str] = None,
    codigo_op: Optional[str] = None,
    causa_raiz: Optional[str] = None,
    db: Session = Depends(get_db),
):
    consulta = db.query(NoConformidad, OrdenProduccion).outerjoin(
        OrdenProduccion, NoConformidad.id_op == OrdenProduccion.id_op
    )
    if codigo_op:
        consulta = consulta.filter(OrdenProduccion.codigo_op.ilike(f"%{codigo_op.strip()}%"))
    if causa_raiz:
        consulta = consulta.filter(NoConformidad.causa_raiz == causa_raiz)
    registros = consulta.order_by(NoConformidad.creado_en.desc()).all()
    resultados = []
    for nc, orden in registros:
        proyecto = orden.proyecto if orden else None
        cliente_nombre = proyecto.cliente_nombre if proyecto else None
        if cliente and (not cliente_nombre or cliente.strip().lower() not in cliente_nombre.lower()):
            continue
        resultados.append({
            **_respuesta_no_conformidad(nc).dict(),
            "codigo_op": orden.codigo_op if orden else None,
            "cliente": cliente_nombre,
            "acciones_capa": [
                {
                    "id_capa": str(accion.id_capa),
                    "accion_correctiva": accion.accion_correctiva,
                    "responsable_id": str(accion.responsable_id) if accion.responsable_id else None,
                    "fecha_compromiso": accion.fecha_compromiso.isoformat(),
                    "estado_cierre": accion.estado_cierre,
                    "evidencia_cierre": accion.evidencia_cierre,
                }
                for accion in nc.acciones_capa
            ],
        })
    return resultados


@router.post("/rnc/{id_rnc}/acciones-capa", status_code=status.HTTP_201_CREATED)
def crear_accion_capa(
    id_rnc: UUID,
    accion_in: AccionCAPACreate,
    db: Session = Depends(get_db),
):
    nc = db.query(NoConformidad).filter(NoConformidad.id_nc == id_rnc).with_for_update().first()
    if nc is None:
        raise HTTPException(status_code=404, detail="No existe el reporte de no conformidad.")
    accion = AccionCAPA(
        id_rnc=nc.id_nc,
        accion_correctiva=accion_in.accion_correctiva.strip(),
        responsable_id=accion_in.responsable_id,
        fecha_compromiso=accion_in.fecha_compromiso,
        estado_cierre="ABIERTA",
    )
    nc.estado = EstadoNCEnum.ACCION_CORRECTIVA
    try:
        db.add(accion)
        db.commit()
        db.refresh(accion)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo crear la acción correctiva.") from error
    return {
        "id_capa": str(accion.id_capa),
        "id_rnc": str(accion.id_rnc),
        "estado_cierre": accion.estado_cierre,
    }


@router.patch("/acciones-capa/{id_capa}/cerrar")
def cerrar_accion_capa(
    id_capa: UUID,
    cierre: AccionCAPACierre,
    db: Session = Depends(get_db),
):
    accion = db.query(AccionCAPA).filter(AccionCAPA.id_capa == id_capa).with_for_update().first()
    if accion is None:
        raise HTTPException(status_code=404, detail="No existe la acción CAPA.")
    if accion.estado_cierre == "CERRADA":
        raise HTTPException(status_code=409, detail="La acción CAPA ya está cerrada.")
    accion.estado_cierre = "CERRADA"
    accion.evidencia_cierre = cierre.evidencia_cierre.strip()
    accion.cerrada_en = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(accion)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo cerrar la acción CAPA.") from error
    return {
        "id_capa": str(accion.id_capa),
        "estado_cierre": accion.estado_cierre,
        "cerrada_en": accion.cerrada_en,
    }