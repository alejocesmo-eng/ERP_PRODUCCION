from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

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
    """Añade un evento append-only a la transacción activa; el llamador confirma junto al cambio.
    La fecha se toma aquí y no del servidor: en PostgreSQL now() es la hora de inicio de la
    transacción y los eventos de una misma petición quedarían empatados en la línea de tiempo."""
    evento = PlanoHistorial(
        id_plano=plano.id_plano,
        tipo_evento=tipo_evento,
        version=plano.version,
        version_anterior=version_anterior,
        estado=plano.estado_diseno,
        tipo_archivo=tipo_archivo,
        sha256=sha256,
        usuario=usuario,
        fecha=datetime.now(timezone.utc),
        justificacion=justificacion,
    )
    db.add(evento)
    return evento


def serializar_evento_plano(evento: PlanoHistorial) -> dict:
    return {
        "id_evento": str(evento.id_evento),
        "tipo_evento": evento.tipo_evento,
        "version": evento.version,
        "version_anterior": evento.version_anterior,
        "estado": evento.estado,
        "tipo_archivo": evento.tipo_archivo,
        "sha256": evento.sha256,
        "usuario": evento.usuario,
        "fecha": evento.fecha.isoformat() if evento.fecha else None,
        "justificacion": evento.justificacion,
    }


def historial_por_plano(db: Session, ids_plano: Iterable[UUID]) -> dict[UUID, list[dict]]:
    """Línea de tiempo de cada plano en orden cronológico, en una sola consulta."""
    ids = list(ids_plano)
    if not ids:
        return {}
    eventos = (
        db.query(PlanoHistorial)
        .filter(PlanoHistorial.id_plano.in_(ids))
        .order_by(PlanoHistorial.fecha, PlanoHistorial.id_evento)
        .all()
    )
    resultado: dict[UUID, list[dict]] = {}
    for evento in eventos:
        resultado.setdefault(evento.id_plano, []).append(serializar_evento_plano(evento))
    return resultado
