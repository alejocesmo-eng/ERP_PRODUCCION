import enum
from uuid import uuid4
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base

class EstadoOperacionEnum(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    PENDIENTE_ASIGNACION = "PENDIENTE_ASIGNACION"
    EN_COLA = "EN_COLA"
    EN_SETUP = "EN_SETUP"
    EN_PRODUCCION = "EN_PRODUCCION"
    PAUSADA = "PAUSADA"
    PARCIALMENTE_COMPLETADA = "PARCIALMENTE_COMPLETADA" # Cuando se termina solo una parte del lote
    COMPLETADA = "COMPLETADA"

class TipoUnidadPlantaEnum(str, enum.Enum):
    MECANIZADOS = "Mecanizados"
    METALISTERIA = "Metalistería"
    SERVICIOS = "Servicios"

# =============================================================================
# TABLA 1: OPERACIÓN TÉCNICA BASE (RUTA DE TRABAJO GLOBAL)
# =============================================================================

class OperacionOT(Base):
    """
    Define el paso o proceso global de la OT (ej. Operación 10: Torneado General).
    Contiene la cantidad total solicitada por el cliente.
    """
    __tablename__ = "operaciones_ot"

    id_operacion = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    id_plano = Column(UUID(as_uuid=True), ForeignKey("planos.id_plano"), nullable=False)
    codigo_op = Column(String(50), index=True, nullable=False)
    codigo_plano = Column(String(50), nullable=False)
    
    secuencia_paso = Column(Integer, default=1, nullable=False) # 10, 20, 30...
    unidad_planta = Column(Enum(TipoUnidadPlantaEnum), default=TipoUnidadPlantaEnum.MECANIZADOS)
    nombre_proceso = Column(String(100), nullable=False) # Ej. Torneado, Fresado, Taladrado
    
    # Saldos globales de la operación
    cantidad_total_orden = Column(Integer, nullable=False, default=1)
    cantidad_acumulada_ok = Column(Integer, default=0) # Suma de piezas terminadas de todos los sub-lotes
    
    estado_operacion = Column(Enum(EstadoOperacionEnum), default=EstadoOperacionEnum.PENDIENTE)
    creado_en = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    sublotes = relationship("SubLoteOperacion", back_populates="operacion", cascade="all, delete-orphan")


# =============================================================================
# TABLA 2: SUB-LOTES Y ASIGNACIÓN A MÁQUINA / OPERARIO (TRABAJO EN PARALELO)
# =============================================================================

class SubLoteOperacion(Base):
    """
    Permite dividir la Operación en varios envíos/maquinados independientes.
    Ejemplo:
    - Sub-Lote 1: Torno 01 - Operario A - 50 Piezas
    - Sub-Lote 2: Torno 02 - Operario B - 50 Piezas
    """
    __tablename__ = "sublotes_operacion"

    id_sublote = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    id_operacion = Column(UUID(as_uuid=True), ForeignKey("operaciones_ot.id_operacion"), nullable=False)
    
    numero_sublote = Column(String(20), default="LOTE-1") # Ej: "SUB-01", "SUB-02"
    cantidad_asignada = Column(Integer, nullable=False, default=1) # Cantidad de piezas asignadas a este grupo
    
    # Recursos específicos asignados por el Líder
    operario_id = Column(String(100), nullable=True)
    operario_nombre = Column(String(150), nullable=True)
    maquina_codigo = Column(String(50), nullable=True)
    prioridad_cola = Column(Integer, nullable=False, default=0)
    
    estado_sublote = Column(Enum(EstadoOperacionEnum), default=EstadoOperacionEnum.EN_COLA)
    
    # Relaciones
    operacion = relationship("OperacionOT", back_populates="sublotes")
    registros_tiempo = relationship("RegistroTiempoOperario", back_populates="sublote", cascade="all, delete-orphan")


# =============================================================================
# TABLA 3: CAPTURA DE TIEMPOS Y PRODUCCIÓN PARCIAL EN TABLET
# =============================================================================

class RegistroTiempoOperario(Base):
    """
    Almacena los tiempos reales y el reporte de entrega parcial del operario.
    """
    __tablename__ = "registros_tiempo_operario"

    id_registro = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    id_sublote = Column(UUID(as_uuid=True), ForeignKey("sublotes_operacion.id_sublote"), nullable=False)
    
    operario_id = Column(String(100), nullable=False)
    maquina_codigo = Column(String(50), nullable=False)
    
    fecha_apertura_setup = Column(DateTime, nullable=True)
    fecha_inicio_produccion = Column(DateTime, nullable=True)
    fecha_fin_operacion = Column(DateTime, nullable=True)
    
    tiempo_setup_segundos = Column(Integer, default=0)
    tiempo_produccion_segundos = Column(Integer, default=0)
    fase_activa = Column(String(20), nullable=True)
    justificacion_exceso = Column(Text, nullable=True)
    motivo_pausa = Column(String(150), nullable=True)
    
    # Piezas efectivamente reportadas en este turno/operación
    piezas_conformes_ok = Column(Integer, default=0, nullable=False)
    piezas_defectuosas_scrap = Column(Integer, default=0, nullable=False)
    es_entrega_parcial = Column(Integer, default=0) # 1 si terminó un turno pero no todas las piezas del sub-lote
    
    comentarios_operario = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    sublote = relationship("SubLoteOperacion", back_populates="registros_tiempo")


# =============================================================================
# TABLA 4: NOTIFICACIONES EN TIEMPO REAL PARA EL LÍDER DE ÁREA
# =============================================================================

class TipoNotificacionEnum(str, enum.Enum):
    SUBLOTE_COMPLETADO = "SUBLOTE_COMPLETADO"      # Operario terminó un sub-lote (OK)
    ENTREGA_PARCIAL = "ENTREGA_PARCIAL"            # Operario entregó piezas parciales
    ALERTA_PARO_MAQUINA = "ALERTA_PARO_MAQUINA"    # Falla técnica / Causa de espera
    PIEZAS_DEFECTUOSAS = "PIEZAS_DEFECTUOSAS"      # Alerta por alto porcentaje de Scrap
    CALIDAD_APROBADA_DESPACHO = "CALIDAD_APROBADA_DESPACHO"

class NotificacionLider(Base):
    """
    Registra las alertas generadas desde las Tablets de los operarios
    para notificar al Líder de Planta en tiempo real.
    """
    __tablename__ = "notificaciones_lider"

    id_notificacion = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    id_sublote = Column(UUID(as_uuid=True), ForeignKey("sublotes_operacion.id_sublote"), nullable=True)
    
    unidad_planta = Column(Enum(TipoUnidadPlantaEnum), nullable=False) # Mecanizados, Metalistería, Servicios
    tipo_notificacion = Column(Enum(TipoNotificacionEnum), nullable=False)
    
    titulo = Column(String(150), nullable=False)
    mensaje = Column(Text, nullable=False)
    
    # Datos de trazabilidad
    codigo_op = Column(String(50), nullable=False)
    codigo_plano = Column(String(50), nullable=False)
    operario_nombre = Column(String(150), nullable=False)
    maquina_codigo = Column(String(50), nullable=False)
    piezas_reportadas = Column(Integer, default=0)
    
    # Estado de lectura/atención por el Líder
    leida = Column(Integer, default=0)              # 0: Unread, 1: Read
    atendida = Column(Integer, default=0)          # 1 cuando el líder asigna el siguiente paso
    creado_en = Column(DateTime, default=datetime.utcnow)