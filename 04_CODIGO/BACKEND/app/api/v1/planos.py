import os
import shutil
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, date, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import jwt

from app.db.database import get_db
from app.db.models import Plano

router = APIRouter()

DIRECTORIO_STATIC_PLANOS = "static/planos"
os.makedirs(DIRECTORIO_STATIC_PLANOS, exist_ok=True)

SECRET_KEY_PLANOS = os.getenv("JWT_SECRET_KEY_PLANOS", "SGI_ERP_SECRET_KEY_TEMPORAL_PLANOS_2026")
ALGORITHM = "HS256"


# =============================================================================
# SCHEMAS PYDANTIC
# =============================================================================

class PlanoResponse(BaseModel):
    id_plano: UUID
    codigo_op: str
    codigo_plano: str
    revision: str
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = "Mecanizados"
    estado_diseno: str
    material_requerido: Optional[str] = None
    archivo_url: Optional[str] = None
    creado_en: datetime

    class Config:
        from_attributes = True


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
    return db.query(Plano).order_by(Plano.creado_en.desc()).all()


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
    if not plano or not plano.archivo_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo PDF no encontrado.")

    nombre_archivo = os.path.basename(plano.archivo_url)
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

    nombre_archivo = f"{plano.codigo_op}_{plano.codigo_plano}_{plano.revision}.pdf".replace("/", "_")
    ruta_fisica = os.path.join(DIRECTORIO_STATIC_PLANOS, nombre_archivo)

    with open(ruta_fisica, "wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    plano.archivo_url = f"/static/planos/{nombre_archivo}"
    db.commit()
    db.refresh(plano)

    return plano