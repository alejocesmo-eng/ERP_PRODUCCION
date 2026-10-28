# app/db/models_rea.py
import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, synonym
from app.db.database import Base

class EstadoEvaluacionReaEnum(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    EN_REVISION = "EN_REVISION"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    OBSERVADO = "OBSERVADO"

class EvaluacionRea(Base):
    """
    Módulo de Evaluación REA (Revisión de Especificaciones Técnicas y Acuerdos).
    Actúa como Quality Gate antes de la conversión de Cotización a Pedido/OP.
    """
    __tablename__ = "evaluaciones_rea"

    id_rea = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_cotizacion = Column(UUID(as_uuid=True), ForeignKey("cotizaciones.id_cotizacion"), nullable=False, unique=True)

    # Criterios de Evaluación
    viabilidad_tecnica = Column(Boolean, default=False)
    capacidad_maquinaria = Column(Boolean, default=False)
    disponibilidad_materiales = Column(Boolean, default=False)
    cumplimiento_normativo = Column(Boolean, default=False)
    riesgos_identificados = Column(Text, nullable=True)

    # Resultado Final
    estado = Column(Enum(EstadoEvaluacionReaEnum), default=EstadoEvaluacionReaEnum.PENDIENTE)
    observaciones_tecnicas = Column(Text, nullable=True)

    # Auditoría
    evaluador_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=True)
    fecha_evaluacion = Column(DateTime(timezone=True), default=datetime.now)

    id = synonym("id_rea")

    cotizacion = relationship("Cotizacion")
    evaluador = relationship("Usuario")
