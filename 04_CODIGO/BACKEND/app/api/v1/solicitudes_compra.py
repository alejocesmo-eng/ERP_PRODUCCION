from typing import List, Optional, Union
from uuid import UUID, uuid4
from datetime import date, datetime
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Proyecto, Plano

router = APIRouter()

# =============================================================================
# BLOQUE 1: SCHEMAS PYDANTIC ADAPTABLES
# =============================================================================

class EstadoMaterialBOMEnum(str, Enum):
    SIN_SOLICITAR = "SIN_SOLICITAR"
    SOLICITADO = "SOLICITADO"
    EN_COMPRA = "EN_COMPRA"
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
    descripcion_resumen: str
    cantidad_piezas: float
    unidad_medida: str
    estado: str
    estado_bom: EstadoMaterialBOMEnum
    fecha_solicitud: date
    fecha_necesaria: Optional[date] = None
    comentarios: Optional[str] = None
    creado_en: datetime

    class Config:
        from_attributes = True

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
def listar_solicitudes_compra():
    return SOLICITUDES_DB

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
    if sol_in.codigo_op and sol_in.codigo_plano:
        plano_db = db.query(Plano).filter(
            Plano.codigo_op == sol_in.codigo_op,
            Plano.codigo_plano == sol_in.codigo_plano
        ).first()

        if plano_db:
            plano_db.material_requerido = f"{resumen_insumos} ({num_sol})"
            db.commit()

    nueva_sol = SolicitudCompraResponse(
        id_solicitud=uuid4(),
        numero_solicitud=num_sol,
        solicitante_nombre=solicitante,
        departamento_area=depto,
        id_proyecto=sol_in.id_proyecto if isinstance(sol_in.id_proyecto, UUID) else None,
        numero_pedido=sol_in.numero_pedido or "S/P",
        codigo_op=sol_in.codigo_op or "GENERAL",
        codigo_plano=sol_in.codigo_plano or "N/A",
        descripcion_resumen=resumen_insumos,
        cantidad_piezas=primer_item.cantidad,
        unidad_medida=primer_item.unidad_medida,
        fecha_solicitud=date.today(),
        fecha_necesaria=sol_in.fecha_necesaria,
        estado="RADICADA",
        estado_bom=EstadoMaterialBOMEnum.SOLICITADO,
        comentarios=sol_in.comentarios,
        creado_en=datetime.now()
    )

    SOLICITUDES_DB.insert(0, nueva_sol)
    return nueva_sol

@router.patch("/{id_solicitud}", response_model=SolicitudCompraResponse)
def actualizar_estado_solicitud(id_solicitud: UUID, sol_up: SolicitudCompraUpdate):
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