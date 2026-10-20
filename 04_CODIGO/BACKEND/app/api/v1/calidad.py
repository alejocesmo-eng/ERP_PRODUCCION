# app/api/v1/calidad.py
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.db.database import get_db
from app.db.models import NoConformidad, OrdenProduccion, EstadoNCEnum
from app.db.models_calidad import InspeccionCalidad

router = APIRouter()

# =============================================================================
# SCHEMAS PYDANTIC - INSPECCIÓN DE CALIDAD
# =============================================================================

class InspeccionCalidadCreate(BaseModel):
    codigo_op: str = Field(..., example="4007256")
    codigo_plano: str = Field(..., example="PLN-PED-092-A")
    inspector_nombre: str = Field(..., example="Juan Pérez")
    resultado_inspeccion: str = Field(..., example="APROBADO_DESPACHO") # APROBADO_DESPACHO | APROBADO_TRATAMIENTO | RECHAZADO
    requiere_tratamiento: bool = False
    descripcion_tratamiento: Optional[str] = None
    piezas_enviadas_tratamiento: Optional[int] = 0
    proveedor_tratamiento_email: Optional[str] = None
    registros_fotograficos: List[str] = []  # Cadenas en Base64 o URLs
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
    registros_fotograficos: List[str]
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
    descripcion: str
    origen: Optional[str] = "INSPECCION_PROCESO"
    gravedad: Optional[str] = "MENOR"
    accion_correctiva: Optional[str] = None
    analisis_causa_5porques: Optional[str] = None

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
    eficacia_verificada: bool
    creado_en: datetime

    class Config:
        from_attributes = True


# =============================================================================
# FUNCIONES AUXILIARES (PLACEHOLDERS)
# =============================================================================

def _simular_generacion_pdf_informe(inspeccion: InspeccionCalidadCreate) -> str:
    """Placeholder: Simula la creación del reporte PDF para tratamiento térmico."""
    return f"/static/reportes/informe_tratamiento_{inspeccion.codigo_op}.pdf"

def _simular_envio_correo_proveedor(email: str, pdf_url: str) -> bool:
    """Placeholder: Simula el envío por correo electrónico al proveedor."""
    print(f"[CORREO SIMULADO] Enviando informe {pdf_url} a {email}...")
    return True

def _simular_notificacion_jefe_produccion(codigo_op: str) -> bool:
    """Placeholder: Simula notificación al jefe de producción para cierre de la OP."""
    print(f"[NOTIFICACIÓN SIMULADA] Orden de producción {codigo_op} lista para cierre por despacho.")
    return True


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
    estados_finales = ("CERRADA", "CANCELADA")
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
        OrdenProduccion.estado.in_(["EN_PRODUCCION", "LIBERADA_PRODUCCION", "EN_INSPECCION", "CERRADA"])
    ).all()

    if ops_db:
        resultado = []
        for op in ops_db:
            resultado.append({
                "codigo_op": op.codigo_op,
                "codigo_plano": op.plano.codigo_plano if op.plano else "PLN-GEN",
                "producto": op.proyecto.detalle_producto if op.proyecto else "Pieza Industrial",
                "cantidad_terminada": op.cantidad_fabricar or 1,
                "estado_op": op.estado.value if hasattr(op.estado, 'value') else str(op.estado),
                "url_plano_pdf": op.plano.archivo_url if op.plano else "/static/planos/PLN-PED-088-A.pdf"
            })
        return resultado

    # Fallback inicial si no hay OPs creadas
    return [
        {
            "codigo_op": "4007256",
            "codigo_plano": "PLN-PED-092-A",
            "producto": "Eje Calibrado Inox 316",
            "cantidad_terminada": 12,
            "estado_op": "TERMINADA",
            "url_plano_pdf": "/static/planos/PLN-PED-088-A.pdf"
        },
        {
            "codigo_op": "4007280",
            "codigo_plano": "PLN-MANT-008-P01",
            "producto": "Buje de Bronce SAE 65",
            "cantidad_terminada": 4,
            "estado_op": "TERMINADA",
            "url_plano_pdf": "/static/planos/PLN-PED-088-A.pdf"
        }
    ]


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

    notificado = False

    if inspeccion_in.resultado_inspeccion == 'APROBADO_TRATAMIENTO':
        if not inspeccion_in.descripcion_tratamiento or not inspeccion_in.proveedor_tratamiento_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe incluir la descripción del tratamiento y el correo del proveedor."
            )
        pdf_path = _simular_generacion_pdf_informe(inspeccion_in)
        _simular_envio_correo_proveedor(inspeccion_in.proveedor_tratamiento_email, pdf_path)

    elif inspeccion_in.resultado_inspeccion == 'APROBADO_DESPACHO':
        notificado = _simular_notificacion_jefe_produccion(inspeccion_in.codigo_op)

    nueva_inspeccion = InspeccionCalidad(
        codigo_op=inspeccion_in.codigo_op,
        codigo_plano=inspeccion_in.codigo_plano,
        inspector_id=uuid4(),
        inspector_nombre=inspeccion_in.inspector_nombre,
        resultado_inspeccion=inspeccion_in.resultado_inspeccion,
        requiere_tratamiento=inspeccion_in.requiere_tratamiento,
        descripcion_tratamiento=inspeccion_in.descripcion_tratamiento,
        piezas_enviadas_tratamiento=inspeccion_in.piezas_enviadas_tratamiento or 0,
        proveedor_tratamiento_email=inspeccion_in.proveedor_tratamiento_email,
        registros_fotograficos=inspeccion_in.registros_fotograficos,
        observaciones_inspector=inspeccion_in.observaciones_inspector,
        notificado_jefe_produccion=notificado
    )

    try:
        db.add(nueva_inspeccion)
        db.commit()
        db.refresh(nueva_inspeccion)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar inspección: {str(e)}")

    return nueva_inspeccion


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

    nueva_nc = NoConformidad(
        codigo_nc=nc_in.codigo_nc,
        id_op=nc_in.id_op,
        descripcion=nc_in.descripcion,
        origen=nc_in.origen or "INSPECCION_PROCESO",
        gravedad=nc_in.gravedad or "MENOR",
        estado=EstadoNCEnum.REGISTRADA,
        accion_correctiva=nc_in.accion_correctiva,
        analisis_causa_5porques=nc_in.analisis_causa_5porques,
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
        eficacia_verificada=nueva_nc.eficacia_verificada,
        creado_en=nueva_nc.creado_en
    )