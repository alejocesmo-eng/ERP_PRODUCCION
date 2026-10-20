# app/db/models_calidad.py
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base

class InspeccionCalidad(Base):
    """
    Modelo SQLAlchemy para Inspección de Calidad de Producto y Tratamientos Térmicos (ISO 9001:2026).
    """
    __tablename__ = "inspecciones_calidad"

    id_inspeccion = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_op = Column(String(50), nullable=False, index=True)
    codigo_plano = Column(String(50), nullable=False, index=True)
    inspector_id = Column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    inspector_nombre = Column(String(150), nullable=False)
    resultado_inspeccion = Column(String(30), nullable=False)  # 'APROBADO_DESPACHO', 'APROBADO_TRATAMIENTO', 'RECHAZADO'
    
    # Tratamiento Térmico (si aplica)
    requiere_tratamiento = Column(Boolean, default=False)
    descripcion_tratamiento = Column(Text, nullable=True)
    piezas_enviadas_tratamiento = Column(Integer, default=0)
    proveedor_tratamiento_email = Column(String(150), nullable=True)
    
    # Fotos (almacena array JSON de cadenas Base64 o URLs)
    registros_fotograficos = Column(JSON, default=list)
    
    observaciones_inspector = Column(Text, nullable=True)
    notificado_jefe_produccion = Column(Boolean, default=False)
    fecha_inspeccion = Column(DateTime(timezone=True), default=datetime.utcnow)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)