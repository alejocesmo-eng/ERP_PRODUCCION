# app/api/v1/historial.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from app.api.deps import requerir_roles
from app.db.database import get_db
from app.db.models import HistorialAccionesDocumento

router = APIRouter(prefix="/historial", tags=["Historial & Trazabilidad"])

# Función auxiliar para registrar hitos desde cualquier controlador
def registrar_evento_historial(
    db: Session,
    tipo_entidad: str,
    identificador: str,
    accion: str,
    usuario: str = "Sistema",
    area: str = "VENTAS",
    estado_ant: Optional[str] = None,
    estado_nuev: Optional[str] = None,
    motivo: Optional[str] = None,
    pausa: bool = False
):
    nuevo_registro = HistorialAccionesDocumento(
        id_historial=uuid.uuid4(),
        tipo_entidad=tipo_entidad.upper(),
        identificador_documento=str(identificador),
        accion=accion,
        estado_anterior=estado_ant,
        estado_nuevo=estado_nuev,
        pausa_tiempo_productivo=pausa,
        motivo_observacion=motivo,
        usuario_responsable=usuario,
        area_origen=area.upper(),
        fecha_hora=datetime.now().astimezone()
    )
    db.add(nuevo_registro)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

# Esquemas Pydantic
class SuspensionRequest(BaseModel):
    tipo_entidad: str
    identificador: str
    motivo: str

class ReactivacionRequest(BaseModel):
    tipo_entidad: str
    identificador: str
    motivo: Optional[str] = "Reanudación regular de actividades"

# 1. Consulta cronológica de la línea de tiempo
@router.get("/{tipo_entidad}/{identificador}")
def obtener_historial_documento(
    tipo_entidad: str,
    identificador: str,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD", "MANTENIMIENTO"])),
):
    registros = db.query(HistorialAccionesDocumento).filter(
        HistorialAccionesDocumento.tipo_entidad == tipo_entidad.upper(),
        HistorialAccionesDocumento.identificador_documento == str(identificador)
    ).order_by(HistorialAccionesDocumento.fecha_hora.asc()).all()

    return [
        {
            "id": str(r.id_historial),
            "accion": r.accion,
            "estado_anterior": r.estado_anterior,
            "estado_nuevo": r.estado_nuevo,
            "pausa_productiva": r.pausa_tiempo_productivo,
            "motivo": r.motivo_observacion,
            "usuario": r.usuario_responsable,
            "area": r.area_origen,
            "fecha_hora": r.fecha_hora.isoformat() if r.fecha_hora else ""
        }
        for r in registros
    ]

# 2. Registrar suspensión (congelamiento de reloj de productividad)
@router.post("/suspender", status_code=status.HTTP_201_CREATED)
def suspender_documento(
    req: SuspensionRequest,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "VENTAS", "DISENO", "PRODUCCION", "CALIDAD", "MANTENIMIENTO"])),
):
    if not req.motivo or not req.motivo.strip():
        raise HTTPException(status_code=400, detail="El motivo de la suspensión es obligatorio.")

    registrar_evento_historial(
        db=db,
        tipo_entidad=req.tipo_entidad,
        identificador=req.identificador,
        accion="SUSPENDIDO_COMERCIAL",
        usuario=usuario["email"],
        area=usuario["rol"],
        estado_ant="ACTIVO",
        estado_nuev="SUSPENDIDO",
        motivo=req.motivo,
        pausa=True
    )
    return {
        "status": "ok",
        "mensaje": f"{req.tipo_entidad} {req.identificador} suspendido preventivamente."
    }

# 3. Registrar reactivación del flujo regular
@router.post("/reactivar", status_code=status.HTTP_201_CREATED)
def reactivar_documento(
    req: ReactivacionRequest,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "VENTAS", "DISENO", "PRODUCCION", "CALIDAD", "MANTENIMIENTO"])),
):
    registrar_evento_historial(
        db=db,
        tipo_entidad=req.tipo_entidad,
        identificador=req.identificador,
        accion="REACTIVADO",
        usuario=usuario["email"],
        area=usuario["rol"],
        estado_ant="SUSPENDIDO",
        estado_nuev="ACTIVO",
        motivo=req.motivo,
        pausa=False
    )
    return {
        "status": "ok",
        "mensaje": f"{req.tipo_entidad} {req.identificador} reactivado formalmente."
    }
