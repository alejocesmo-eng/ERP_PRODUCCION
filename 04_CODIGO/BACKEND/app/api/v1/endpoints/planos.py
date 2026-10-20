# app/api/v1/endpoints/planos.py
import os
import shutil
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from jose import jwt, JWTError, ExpiredSignatureError

from app.core.config import settings
from app.db.database import get_db
from app.db.models import Plano, OTDetalle, OrdenProduccion, EstadoOPEnum

router = APIRouter()

DIRECTORIO_STATIC_PLANOS = "static/planos"
os.makedirs(DIRECTORIO_STATIC_PLANOS, exist_ok=True)


# =============================================================================
# SCHEMAS PYDANTIC
# =============================================================================

class PiezaPlanoItem(BaseModel):
    id: Optional[int] = None
    detalle_id: Optional[UUID] = None
    codigo_op: str = Field(..., description="Orden de trabajo / Código OT individual de la pieza")
    codigo_plano: str = Field(..., description="Código del plano técnico")
    unidad_planta: Optional[str] = "Mecanizados"
    revision: Optional[str] = "REV-01"
    detalle_pieza: str = Field(..., description="Nombre / Detalle de la pieza")
    cantidad: int = Field(1, ge=0)
    dibujante_asignado: Optional[str] = "Ing. Carlos Ruiz"
    tiempo_estimado_valor: int = Field(4, ge=1, description="Tiempo estimado de trabajo por ítem")
    tiempo_estimado_unidad: str = Field("HORAS", description="HORAS o DIAS")
    fecha_compromiso: Optional[date] = Field(None, description="Fecha de entrega parcial por ítem")
    causa_espera: Optional[str] = None
    estado_item: Optional[str] = "EN_COLA"
    material_requerido: Optional[str] = None
    archivo_url: Optional[str] = Field(None, description="URL/Ruta del plano PDF")

    @validator('fecha_compromiso', pre=True)
    def parse_fecha_vacia(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v, "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    class Config:
        extra = "ignore"


class PlanoCreate(BaseModel):
    id_proyecto: Optional[UUID] = None
    numero_pedido: Optional[str] = None
    codigo_op: Optional[str] = "4007256"
    unidad_planta: Optional[str] = "Mecanizados"
    estado_diseno: Optional[str] = "PLANIFICADA"
    fecha_inicio_programada: Optional[date] = None
    fecha_entrega_cliente: Optional[date] = None
    fecha_entrega_produccion: Optional[date] = None
    piezas: List[PiezaPlanoItem] = Field(..., min_items=1, description="Listado de ítems desglosados")

    @validator('fecha_entrega_cliente', 'fecha_entrega_produccion', 'fecha_inicio_programada', pre=True)
    def parse_fechas_vacias(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v, "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    class Config:
        extra = "ignore"


class PlanoUpdate(BaseModel):
    codigo_op: Optional[str] = None
    codigo_plano: Optional[str] = None
    revision: Optional[str] = None
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = None
    estado_diseno: Optional[str] = None
    causa_espera: Optional[str] = None
    material_requerido: Optional[str] = None
    tiempo_estimado_valor: Optional[int] = None
    tiempo_estimado_unidad: Optional[str] = None
    fecha_inicio_programada: Optional[date] = None
    fecha_entrega_cliente: Optional[date] = None
    fecha_entrega_produccion: Optional[date] = None
    archivo_url: Optional[str] = None
    piezas: Optional[List[PiezaPlanoItem]] = None

    @validator('fecha_entrega_cliente', 'fecha_entrega_produccion', 'fecha_inicio_programada', pre=True)
    def parse_fechas_vacias(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v, "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    @validator('causa_espera', pre=True)
    def parse_causa_vacia(cls, v):
        if v == "" or v == "Sin demoras / Restricción resuelta" or v == "RESUELTA":
            return None
        return v

    class Config:
        extra = "ignore"


class PlanoResponse(BaseModel):
    id_plano: UUID
    id_proyecto: Optional[UUID] = None
    numero_pedido: Optional[str] = None
    codigo_op: Optional[str] = "4007256"
    codigo_plano: str
    revision: str
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = None
    estado_diseno: str
    causa_espera: Optional[str] = None
    material_requerido: Optional[str] = None
    tiempo_estimado_valor: Optional[int] = 4
    tiempo_estimado_unidad: Optional[str] = "HORAS"
    fecha_inicio_programada: Optional[date] = None
    fecha_entrega_produccion: Optional[date] = None
    archivo_url: Optional[str] = None
    creado_en: datetime

    class Config:
        from_attributes = True


class TokenPlanoResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_in_minutes: int = 15
    orden_id: str
    id_plano: Optional[UUID] = None
    codigo_plano: Optional[str] = None
    url_visor: str
    archivo_url: Optional[str] = None


# =============================================================================
# ENDPOINTS API - PLANOS Y DOCUMENTACIÓN TÉCNICA
# =============================================================================

@router.get("/", response_model=List[PlanoResponse])
def listar_planos(db: Session = Depends(get_db)):
    """Retorna las órdenes e ítems desglosados individualmente."""
    planos_db = db.query(Plano).order_by(Plano.creado_en.desc()).all()
    for p in planos_db:
        if not getattr(p, 'estado_diseno', None):
            p.estado_diseno = getattr(p, 'estado', 'PLANIFICADA') or 'PLANIFICADA'
    return planos_db


@router.post("/", response_model=PlanoResponse, status_code=status.HTTP_201_CREATED)
def crear_plano(plano_in: PlanoCreate, db: Session = Depends(get_db)):
    piezas_validas = [p for p in plano_in.piezas if p.cantidad > 0]
    if not piezas_validas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe incluir al menos un ítem con cantidad mayor a 0 para generar la Orden."
        )

    # REGLA BLOQUEANTE ISO 9001 (Paso 6: Liberación a Producción)
    if plano_in.estado_diseno == "LIBERADA":
        for p in piezas_validas:
            sin_pdf = not p.archivo_url or not p.archivo_url.strip()
            sin_bom = not p.material_requerido or not p.material_requerido.strip()
            if sin_pdf or sin_bom:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"❌ Bloqueo ISO 9001 (Paso 6): No se puede LIBERAR la pieza [{p.detalle_pieza}] sin adjuntar el plano PDF y especificar la materia prima/BOM."
                )

    total_horas = 0
    for p in piezas_validas:
        val = p.tiempo_estimado_valor or 1
        if p.tiempo_estimado_unidad == "DIAS":
            total_horas += val * 8
        else:
            total_horas += val

    primer_pieza = piezas_validas[0]
    codigo_op_individual = primer_pieza.codigo_op or plano_in.codigo_op or "4007256"
    unidad_planta_ind = primer_pieza.unidad_planta or plano_in.unidad_planta or "Mecanizados"
    codigo_plano_ind = primer_pieza.codigo_plano or codigo_op_individual
    materia_prima_ind = primer_pieza.material_requerido or "Materiales estándar"
    dibujante_ind = primer_pieza.dibujante_asignado or "Ing. Carlos Ruiz"
    causa_ind = primer_pieza.causa_espera if primer_pieza.causa_espera and primer_pieza.causa_espera.strip() else None
    primer_pdf = primer_pieza.archivo_url if primer_pieza.archivo_url and primer_pieza.archivo_url.strip() else None
    fecha_limite_ind = primer_pieza.fecha_compromiso or plano_in.fecha_entrega_produccion

    datos_plano = plano_in.dict(exclude={"piezas"}, exclude_none=True)
    datos_plano["codigo_op"] = codigo_op_individual
    datos_plano["unidad_planta"] = unidad_planta_ind
    datos_plano["codigo_plano"] = codigo_plano_ind
    datos_plano["material_requerido"] = materia_prima_ind
    datos_plano["dibujante_asignado"] = dibujante_ind
    datos_plano["causa_espera"] = causa_ind
    datos_plano["tiempo_estimado_valor"] = total_horas
    datos_plano["tiempo_estimado_unidad"] = "HORAS"
    datos_plano["fecha_entrega_produccion"] = fecha_limite_ind
    if primer_pdf:
        datos_plano["archivo_url"] = primer_pdf

    columnas_validas = {c.name for c in Plano.__table__.columns}
    datos_filtrados = {k: v for k, v in datos_plano.items() if k in columnas_validas}

    nuevo_plano = Plano(**datos_filtrados)
    db.add(nuevo_plano)
    db.flush()

    for p in piezas_validas:
        if p.detalle_id:
            relacion = OTDetalle(
                detalle_pedido_id=p.detalle_id,
                ot_id=nuevo_plano.id_plano,
                cantidad_asignada=p.cantidad
            )
            db.add(relacion)

    db.commit()
    db.refresh(nuevo_plano)
    return nuevo_plano


@router.patch("/{id_plano}", response_model=PlanoResponse)
def actualizar_plano(id_plano: UUID, plano_up: PlanoUpdate, db: Session = Depends(get_db)):
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada.")

    datos_update = plano_up.dict(exclude_unset=True, exclude={"piezas"})

    if datos_update.get("estado_diseno") == "LIBERADA":
        url_eval = datos_update.get("archivo_url") or plano.archivo_url
        mat_eval = datos_update.get("material_requerido") or plano.material_requerido
        
        sin_plano = not url_eval or not url_eval.strip()
        sin_material = not mat_eval or not mat_eval.strip()

        if sin_plano or sin_material:
            razones = []
            if sin_plano: razones.append("Archivo PDF del plano técnico no cargado")
            if sin_material: razones.append("Materia prima / BOM no especificado")
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"❌ Bloqueo de Calidad ISO 9001 (Paso 6): No se puede LIBERAR la orden a Producción. Faltan requerimientos: {', '.join(razones)}."
            )

    if datos_update.get("estado_diseno") in ["EN_DISENO", "LIBERADA"]:
        datos_update["causa_espera"] = None

    for campo, valor in datos_update.items():
        if hasattr(plano, campo):
            setattr(plano, campo, valor)

    db.commit()
    db.refresh(plano)
    return plano


@router.post("/upload-pdf/{id_plano}", response_model=PlanoResponse)
def subir_pdf_plano(
    id_plano: UUID, 
    archivo: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """Carga y almacena un plano PDF en /static/planos/ guardando la ruta relativa."""
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Orden de trabajo / plano no encontrado.")

    if not archivo.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos con extensión .pdf")

    nombre_archivo = f"{plano.codigo_op}_{plano.codigo_plano}_{plano.revision}.pdf".replace("/", "_")
    ruta_fisica = os.path.join(DIRECTORIO_STATIC_PLANOS, nombre_archivo)

    with open(ruta_fisica, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    ruta_relativa = f"/static/planos/{nombre_archivo}"
    plano.archivo_url = ruta_relativa
    
    db.commit()
    db.refresh(plano)
    return plano


# =============================================================================
# BLOQUE 2: SERVIDO SEGURO DE PLANOS MEDIANTE TOKENS TEMPORALES (TTL / TC-02)
# =============================================================================

@router.get("/token/{orden_id}", response_model=TokenPlanoResponse)
def generar_token_plano(orden_id: str, db: Session = Depends(get_db)):
    """
    TC-02 / Seguridad: Genera un token JWT temporal (TTL expirable de 15 minutos)
    para visualizar el plano PDF de la OP activa en el puesto de trabajo.
    """
    # 1. Buscar la Orden de Producción
    op = None
    try:
        val_uuid = UUID(orden_id)
        op = db.query(OrdenProduccion).filter(OrdenProduccion.id_op == val_uuid).first()
    except (ValueError, AttributeError):
        pass

    if not op and hasattr(OrdenProduccion, 'id') and orden_id.isdigit():
        op = db.query(OrdenProduccion).filter(OrdenProduccion.id == int(orden_id)).first()

    if not op:
        op = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == str(orden_id)).first()

    # 2. Si no se halló OP directa, buscar por Plano
    plano = None
    if op:
        # Validar estado activo de la OP
        estado_str = op.estado.value if hasattr(op.estado, 'value') else str(op.estado)
        if estado_str in ["CERRADA", "CANCELADA", "RECHAZADA"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"La orden de producción '{op.codigo_op}' está {estado_str} y ya no tiene acceso al visor de planos."
            )
        
        if op.id_plano:
            plano = db.query(Plano).filter(Plano.id_plano == op.id_plano).first()
        if not plano:
            plano = db.query(Plano).filter(Plano.id_proyecto == op.id_proyecto).first()
    else:
        # Búsqueda directa por ID de Plano
        try:
            val_uuid_plano = UUID(orden_id)
            plano = db.query(Plano).filter(Plano.id_plano == val_uuid_plano).first()
        except (ValueError, AttributeError):
            plano = db.query(Plano).filter(Plano.codigo_op == str(orden_id)).first()

    if not plano and not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró orden de producción ni plano para el identificador '{orden_id}'."
        )

    # 3. Generar token JWT con TTL expirable
    minutos_ttl = 15
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=minutos_ttl)

    payload_jwt = {
        "sub": str(op.id_op) if op else str(plano.id_plano),
        "orden_id": str(orden_id),
        "id_plano": str(plano.id_plano) if plano else None,
        "codigo_op": op.codigo_op if op else (plano.codigo_op if plano else ""),
        "codigo_plano": plano.codigo_plano if plano else None,
        "archivo_url": plano.archivo_url if plano else None,
        "scope": "plano_read",
        "exp": expiracion
    }

    token_seguro = jwt.encode(payload_jwt, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return TokenPlanoResponse(
        token=token_seguro,
        token_type="bearer",
        expires_in_minutes=minutos_ttl,
        orden_id=str(orden_id),
        id_plano=plano.id_plano if plano else None,
        codigo_plano=plano.codigo_plano if plano else None,
        url_visor=f"/api/v1/planos/visor/{token_seguro}",
        archivo_url=plano.archivo_url if plano else None
    )


@router.get("/visor/{token}")
def visualizar_plano_seguro(token: str, db: Session = Depends(get_db)):
    """
    TC-02: Valida el token JWT expirable y verifica que la OP siga activa en el puesto de trabajo.
    Si la OP ya fue finalizada o el token expiró, responde 403 Forbidden.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El token de visualización del plano ha expirado. Solicite un nuevo token en el puesto activo."
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de acceso a planos inválido o corrupto."
        )

    # Verificar vigencia de la OP asociada
    orden_id = payload.get("orden_id") or payload.get("sub")
    if orden_id:
        op = None
        try:
            val_uuid = UUID(orden_id)
            op = db.query(OrdenProduccion).filter(OrdenProduccion.id_op == val_uuid).first()
        except (ValueError, AttributeError):
            op = db.query(OrdenProduccion).filter(OrdenProduccion.codigo_op == str(orden_id)).first()

        if op:
            estado_str = op.estado.value if hasattr(op.estado, 'value') else str(op.estado)
            if estado_str in ["CERRADA", "CANCELADA", "FINALIZADO"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="La orden de producción ya finalizó en planta. El acceso al plano está bloqueado."
                )

    archivo_url = payload.get("archivo_url")
    if not archivo_url:
        return {
            "status": "ok",
            "mensaje": "Acceso autorizado al plano técnico.",
            "codigo_op": payload.get("codigo_op"),
            "codigo_plano": payload.get("codigo_plano"),
            "archivo_url": None
        }

    # Si el archivo existe físicamente en el servidor, servirlo
    ruta_limpia = archivo_url.lstrip("/")
    if os.path.exists(ruta_limpia):
        return FileResponse(
            path=ruta_limpia,
            media_type="application/pdf",
            filename=os.path.basename(ruta_limpia)
        )

    return {
        "status": "ok",
        "mensaje": "Acceso autorizado al plano técnico.",
        "codigo_op": payload.get("codigo_op"),
        "codigo_plano": payload.get("codigo_plano"),
        "archivo_url": archivo_url
    }

