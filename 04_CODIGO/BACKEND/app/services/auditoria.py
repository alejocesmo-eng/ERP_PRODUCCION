from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import HistorialAccionesDocumento


def agregar_evento_trazabilidad(
    db: Session,
    *,
    tipo_entidad: str,
    identificador: str,
    accion: str,
    usuario: str,
    area: str,
    estado_anterior: Optional[str] = None,
    estado_nuevo: Optional[str] = None,
    motivo: Optional[str] = None,
) -> HistorialAccionesDocumento:
    """Añade un evento a la transacción activa; el llamador confirma junto al cambio."""
    evento = HistorialAccionesDocumento(
        tipo_entidad=tipo_entidad.upper(),
        identificador_documento=str(identificador),
        accion=accion,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
        motivo_observacion=motivo,
        usuario_responsable=usuario,
        area_origen=area.upper(),
        fecha_hora=datetime.now(timezone.utc),
    )
    db.add(evento)
    return evento
