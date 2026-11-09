from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Plano, PlanoHistorial

LONGITUD_MINIMA_JUSTIFICACION = 10
MENSAJE_JUSTIFICACION = (
    f"La justificación del cambio de archivo o versión debe tener al menos "
    f"{LONGITUD_MINIMA_JUSTIFICACION} caracteres."
)


def exigir_justificacion(justificacion: Optional[str]) -> str:
    """Cambio de versión, cambio de archivo y revisión: 422 si la justificación no llega
    a 10 caracteres sin contar espacios. Se llama antes de escribir nada."""
    texto = justificacion.strip() if isinstance(justificacion, str) else ""
    if len(texto) < LONGITUD_MINIMA_JUSTIFICACION:
        raise HTTPException(status_code=422, detail=MENSAJE_JUSTIFICACION)
    return texto


def justificacion_opcional(justificacion: Optional[str]) -> Optional[str]:
    texto = justificacion.strip() if isinstance(justificacion, str) else ""
    return texto or None


def registrar_evento_plano(
    db: Session,
    plano: Plano,
    tipo_evento: str,
    usuario: str,
    *,
    version_anterior: Optional[str] = None,
    tipo_archivo: Optional[str] = None,
    sha256: Optional[str] = None,
    justificacion: Optional[str] = None,
) -> PlanoHistorial:
    """Añade un evento append-only a la transacción activa; el llamador confirma junto al cambio."""
    evento = PlanoHistorial(
        id_plano=plano.id_plano,
        tipo_evento=tipo_evento,
        version=plano.version,
        version_anterior=version_anterior,
        estado=plano.estado_diseno,
        tipo_archivo=tipo_archivo,
        sha256=sha256,
        usuario=usuario,
        justificacion=justificacion,
    )
    db.add(evento)
    return evento
