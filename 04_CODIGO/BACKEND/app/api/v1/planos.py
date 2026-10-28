import os
import shutil
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, date, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
import jwt

from app.db.database import get_db
from app.db.models import BOMListaMateriales, Plano, Proyecto
from app.api.v1.quality_gate import ESTADOS_BOM_LIBERABLES, validar_gate_calidad

router = APIRouter()

DIRECTORIO_STATIC_PLANOS = "static/planos"
os.makedirs(DIRECTORIO_STATIC_PLANOS, exist_ok=True)

SECRET_KEY_PLANOS = os.getenv("JWT_SECRET_KEY_PLANOS", "SGI_ERP_SECRET_KEY_TEMPORAL_PLANOS_2026")
ALGORITHM = "HS256"


# =============================================================================
# SCHEMAS PYDANTIC
# =============================================================================

class BOMItemResponse(BaseModel):
    codigo_material: str
    descripcion: str
    cantidad_requerida: float
    unidad_medida: str
    estado_abastecimiento: str

    class Config:
        from_attributes = True


class PlanoResponse(BaseModel):
    id_plano: UUID
    id_proyecto: UUID
    codigo_op: str
    codigo_plano: str
    version: str
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = "Mecanizados"
    estado_diseno: str
    material_requerido: Optional[str] = None
    archivo_pdf_url: Optional[str] = None
    archivo_step_url: Optional[str] = None
    archivo_dxf_url: Optional[str] = None
    creado_en: datetime
    bom_items: List["BOMItemResponse"] = Field(default_factory=list)

    class Config:
        from_attributes = True
class PiezaPlanoWrite(BaseModel):
    codigo_plano: Optional[str] = None
    version: Optional[str] = "V-01"
    detalle_pieza: Optional[str] = None
    cantidad: Optional[int] = 1
    material_requerido: Optional[str] = None
    codigo_material: Optional[str] = None
    cantidad_material: Optional[float] = None
    unidad_medida: Optional[str] = "UND"
    archivo_pdf_url: Optional[str] = None
    archivo_step_url: Optional[str] = None
    archivo_dxf_url: Optional[str] = None


class PlanoWriteRequest(BaseModel):
    id_proyecto: UUID
    codigo_op: str
    codigo_plano: Optional[str] = None
    version: Optional[str] = "V-01"
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = "Mecanizados"
    estado_diseno: Optional[str] = "PLANIFICADA"
    causa_espera: Optional[str] = None
    material_requerido: Optional[str] = None
    archivo_pdf_url: Optional[str] = None
    archivo_step_url: Optional[str] = None
    archivo_dxf_url: Optional[str] = None
    piezas: List[PiezaPlanoWrite] = Field(default_factory=list)


class PlanoUpdateRequest(BaseModel):
    estado_diseno: Optional[str] = None
    causa_espera: Optional[str] = None
    archivo_pdf_url: Optional[str] = None
    archivo_step_url: Optional[str] = None
    archivo_dxf_url: Optional[str] = None
    material_requerido: Optional[str] = None
    version: Optional[str] = None
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = None
    piezas: Optional[List[PiezaPlanoWrite]] = None


class TokenPlanoResponse(BaseModel):
    token_temporal: str
    url_acceso_temporal: str
    expira_en_minutos: int = 15


# =============================================================================
# HELPER TOKEN TEMPORAL TTL
# =============================================================================

def generar_token_plano_ttl(id_plano: UUID, ttl_minutos: int = 15) -> str:
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutos)
    payload = {
        "sub": str(id_plano),
        "exp": expiracion,
        "type": "plano_temp_access"
    }
    return jwt.encode(payload, SECRET_KEY_PLANOS, algorithm=ALGORITHM)


# =============================================================================
# ENDPOINTS GESTIÓN Y SERVIDO DE PLANOS CON TOKENS TTL
# =============================================================================

@router.get("/", response_model=List[PlanoResponse])
def listar_planos(db: Session = Depends(get_db)):
    return db.query(Plano).options(
        joinedload(Plano.bom_items)
    ).order_by(Plano.creado_en.desc()).all()


def _datos_pieza(plano_in: PlanoWriteRequest, pieza: PiezaPlanoWrite):
    codigo_material = (pieza.codigo_material or pieza.material_requerido or plano_in.material_requerido or "").strip()
    descripcion = (pieza.material_requerido or plano_in.material_requerido or codigo_material).strip()
    return {
        "codigo_material": codigo_material[:50],
        "descripcion": descripcion[:200],
        "cantidad_requerida": pieza.cantidad_material if pieza.cantidad_material is not None else 1.0,
        "unidad_medida": pieza.unidad_medida or "UND",
    }


@router.post("/", response_model=List[PlanoResponse], status_code=status.HTTP_201_CREATED)
def crear_planos(plano_in: PlanoWriteRequest, db: Session = Depends(get_db)):
    proyecto = db.query(Proyecto).filter(Proyecto.id_proyecto == plano_in.id_proyecto).first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="El proyecto asociado al plano no existe.")

    piezas = plano_in.piezas or [
        PiezaPlanoWrite(
            codigo_plano=plano_in.codigo_plano,
            revision=plano_in.revision,
            material_requerido=plano_in.material_requerido,
            archivo_url=plano_in.archivo_url,
        )
    ]
    planos_creados = []
    try:
        for pieza in piezas:
            plano = Plano(
                id_proyecto=proyecto.id_proyecto,
                codigo_op=plano_in.codigo_op,
                codigo_plano=pieza.codigo_plano or plano_in.codigo_plano or plano_in.codigo_op,
                version=pieza.version or plano_in.version or "V-01",
                dibujante_asignado=plano_in.dibujante_asignado,
                unidad_planta=plano_in.unidad_planta,
                estado_diseno=plano_in.estado_diseno or "PLANIFICADA",
                causa_espera=plano_in.causa_espera,
                material_requerido=pieza.material_requerido or plano_in.material_requerido,
                archivo_pdf_url=pieza.archivo_pdf_url or plano_in.archivo_pdf_url,
                archivo_step_url=pieza.archivo_step_url or plano_in.archivo_step_url,
                archivo_dxf_url=pieza.archivo_dxf_url or plano_in.archivo_dxf_url,
            )
            db.add(plano)
            db.flush()
            datos_bom = _datos_pieza(plano_in, pieza)
            if datos_bom["codigo_material"]:
                db.add(BOMListaMateriales(
                    plano_id=plano.id_plano,
                    estado_abastecimiento="SIN_SOLICITAR",
                    **datos_bom,
                ))
            if plano.estado_diseno == "LIBERADA":
                validar_gate_calidad(db, plano)
            planos_creados.append(plano)
        db.commit()
        for plano in planos_creados:
            db.refresh(plano)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudieron guardar los planos.") from error
    return planos_creados


@router.patch("/{id_plano}", response_model=PlanoResponse)
def actualizar_plano(
    id_plano: UUID,
    plano_in: PlanoUpdateRequest,
    db: Session = Depends(get_db),
):
    plano = db.query(Plano).options(joinedload(Plano.bom_items)).filter(
        Plano.id_plano == id_plano
    ).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Plano no encontrado.")

    campos_editables = {
        "estado_diseno",
        "causa_espera",
        "archivo_pdf_url",
        "archivo_step_url",
        "archivo_dxf_url",
        "material_requerido",
        "version",
        "dibujante_asignado",
        "unidad_planta",
    }
    datos_actualizacion = plano_in.dict(exclude_unset=True)
    for campo in campos_editables:
        if campo in datos_actualizacion:
            setattr(plano, campo, datos_actualizacion[campo])

    piezas = plano_in.piezas or []
    if piezas:
        pieza = piezas[0]
        datos_bom = {
            "codigo_material": str(pieza.codigo_material or pieza.material_requerido or plano.material_requerido or "").strip()[:50],
            "descripcion": str(pieza.material_requerido or plano.material_requerido or "").strip()[:200],
            "cantidad_requerida": pieza.cantidad_material or 1,
            "unidad_medida": pieza.unidad_medida or "UND",
        }
        if datos_bom["codigo_material"]:
            if plano.bom_items:
                item = plano.bom_items[0]
                if (
                    item.codigo_material != datos_bom["codigo_material"]
                    or item.descripcion != datos_bom["descripcion"]
                ):
                    item.estado_abastecimiento = "SIN_SOLICITAR"
                for campo, valor in datos_bom.items():
                    setattr(item, campo, valor)
            else:
                db.add(BOMListaMateriales(
                    plano_id=plano.id_plano,
                    estado_abastecimiento="SIN_SOLICITAR",
                    **datos_bom,
                ))
    try:
        db.flush()
        if plano.estado_diseno == "LIBERADA":
            validar_gate_calidad(db, plano)
        db.commit()
        db.refresh(plano)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo actualizar el plano.") from error
    return plano


@router.get("/token/{id_plano}", response_model=TokenPlanoResponse)
def obtener_token_temporal_plano(id_plano: UUID, db: Session = Depends(get_db)):
    """
    Genera un token de acceso temporal firmado con TTL de 15 minutos para visualizar el plano PDF.
    """
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano or not plano.archivo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plano no encontrado o no posee un archivo PDF cargado."
        )

    token = generar_token_plano_ttl(id_plano, ttl_minutos=15)
    url_acceso = f"/api/v1/planos/visor-seguro?token={token}"

    return TokenPlanoResponse(
        token_temporal=token,
        url_acceso_temporal=url_acceso,
        expira_en_minutos=15
    )


@router.get("/visor-seguro")
def servir_plano_pdf_seguro(token: str, db: Session = Depends(get_db)):
    """
    Valida la firma y vigencia TTL del token para servir el archivo PDF congelado.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY_PLANOS, algorithms=[ALGORITHM])
        id_plano_str = payload.get("sub")
        if not id_plano_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no válido.")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="❌ El token de acceso al plano ha expirado.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token alterado o no válido.")

    plano = db.query(Plano).filter(Plano.id_plano == UUID(id_plano_str)).first()
    if not plano or not plano.archivo_pdf_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo PDF no encontrado."
        )

    nombre_archivo = os.path.basename(plano.archivo_pdf_url)
    ruta_fisica = os.path.join(DIRECTORIO_STATIC_PLANOS, nombre_archivo)

    if not os.path.exists(ruta_fisica):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo físico PDF no existe en el almacenamiento.")

    return FileResponse(ruta_fisica, media_type="application/pdf", filename=nombre_archivo)


@router.post("/upload-pdf/{id_plano}", response_model=PlanoResponse)
def subir_pdf_plano(id_plano: UUID, archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano no encontrado.")

    if not archivo.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato inválido. Solo PDF.")

    nombre_archivo = f"{plano.codigo_op}_{plano.codigo_plano}_{plano.version}.pdf".replace("/", "_")
    ruta_fisica = os.path.join(DIRECTORIO_STATIC_PLANOS, nombre_archivo)

    with open(ruta_fisica, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    plano.archivo_pdf_url = f"/static/planos/{nombre_archivo}"
    db.commit()
    db.refresh(plano)

    return plano

@router.post("/upload-cad/{id_plano}", response_model=PlanoResponse)
def subir_cad_plano(id_plano: UUID, archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano no encontrado.")

    ext = archivo.filename.lower()
    if ext.endswith('.step') or ext.endswith('.stp'):
        campo = "archivo_step_url"
        ext_final = ".step"
    elif ext.endswith('.dxf'):
        campo = "archivo_dxf_url"
        ext_final = ".dxf"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formato inválido. Solo .step, .stp o .dxf.")

    nombre_archivo = f"{plano.codigo_op}_{plano.codigo_plano}_{plano.version}{ext_final}".replace("/", "_")
    ruta_fisica = os.path.join(DIRECTORIO_STATIC_PLANOS, nombre_archivo)

    with open(ruta_fisica, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    setattr(plano, campo, f"/static/planos/{nombre_archivo}")
    db.commit()
    db.refresh(plano)

    return plano

@router.get("/descargar-cad/{id_plano}/{tipo}")
def descargar_cad_plano(id_plano: UUID, tipo: str, db: Session = Depends(get_db)):
    """
    Descarga de archivos CAD (.step o .dxf).
    tipos: 'step', 'dxf'
    """
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Plano no encontrado.")

    campo = "archivo_step_url" if tipo == "step" else "archivo_dxf_url"
    url = getattr(plano, campo)

    if not url:
        raise HTTPException(status_code=404, detail=f"Archivo {tipo} no disponible.")

    nombre_archivo = os.path.basename(url)
    ruta_fisica = os.path.join(DIRECTORIO_STATIC_PLANOS, nombre_archivo)

    if not os.path.exists(ruta_fisica):
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado.")

    return FileResponse(ruta_fisica)
