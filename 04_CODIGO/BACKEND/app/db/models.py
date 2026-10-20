# app/db/models.py
import uuid
import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, 
    String, 
    Boolean, 
    DateTime, 
    Integer, 
    Text, 
    ForeignKey, 
    Enum,
    Date,
    Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.sql import func
from app.db.database import Base
from app.db.models_produccion import OperacionOT, RegistroTiempoOperario

# =============================================================================
# ENUMS
# =============================================================================

class EstadoProyectoEnum(str, enum.Enum):
    BORRADOR = "BORRADOR"
    CONFIRMADO = "CONFIRMADO"
    EN_DISENO = "EN_DISENO"
    FINALIZADO = "FINALIZADO"
    CANCELADO = "CANCELADO"


class EstadoOPEnum(str, enum.Enum):
    BORRADOR = "BORRADOR"
    EN_REVISION_CALIDAD = "EN_REVISION_CALIDAD"
    APROBADA = "APROBADA"
    PENDIENTE_MATERIAL = "PENDIENTE_MATERIAL"
    LIBERADA_PRODUCCION = "LIBERADA_PRODUCCION"
    EN_PRODUCCION = "EN_PRODUCCION"
    EN_PROCESO_CNC = "EN_PROCESO_CNC"
    EN_SETUP = "EN_SETUP"
    MECANIZADO = "MECANIZADO"
    EN_INSPECCION = "EN_INSPECCION"
    CERRADA = "CERRADA"
    CANCELADA = "CANCELADA"


class EstadoPlanoEnum(str, enum.Enum):
    BORRADOR = "BORRADOR"
    EN_REVISION = "EN_REVISION"
    APROBADO = "APROBADO"
    OBSOLETO = "OBSOLETO"


class EstadoNCEnum(str, enum.Enum):
    ABIERTA = "ABIERTA"
    REGISTRADA = "REGISTRADA"
    EN_ANALISIS = "EN_ANALISIS"
    ACCION_CORRECTIVA = "ACCION_CORRECTIVA"
    ACCION_DEFINIDA = "ACCION_DEFINIDA"
    VERIFICANDO_EFICACIA = "VERIFICANDO_EFICACIA"
    CERRADA = "CERRADA"


# =============================================================================
# MODELOS BASE Y PERMISOS DEL SISTEMA
# =============================================================================

class Rol(Base):
    __tablename__ = "roles"

    id_rol = Column(String(50), primary_key=True)
    nombre_rol = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)

    usuarios = relationship("Usuario", back_populates="rol")


class Permiso(Base):
    __tablename__ = "permisos"

    id_permiso = Column(String(100), primary_key=True)
    modulo = Column(String(50), nullable=False)
    descripcion = Column(Text, nullable=True)


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nombre_completo = Column(String(150), nullable=False)
    id_rol = Column(String(50), ForeignKey("roles.id_rol"), nullable=True)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    # Homologación con DDL canónico (id <=> id_usuario)
    id = synonym("id_usuario")

    rol = relationship("Rol", back_populates="usuarios")


class Maquina(Base):
    __tablename__ = "maquinas"

    id_maquina = Column(String(50), primary_key=True)
    nombre_maquina = Column(String(100), nullable=False)
    tipo_maquina = Column(String(50), nullable=True)
    estado = Column(String(50), default="OPERATIVA")

    # Homologación con identificadores
    id = synonym("id_maquina")


class Empleado(Base):
    __tablename__ = "empleados"

    id_empleado = Column(String(50), primary_key=True)
    nombre_completo = Column(String(150), nullable=False)
    cargo = Column(String(100), nullable=True)
    area = Column(String(100), nullable=True)

    # Homologación con identificadores
    id = synonym("id_empleado")


class Cliente(Base):
    """
    PM-01: Catálogo Maestro de Clientes (Homologación DDL vs ORM).
    """
    __tablename__ = "clientes"

    id_cliente = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nit_rut = Column(String(50), unique=True, nullable=False)
    razon_social = Column(String(150), nullable=False)
    contacto = Column(String(100), nullable=True)
    email_contacto = Column(String(100), nullable=True)
    telefono = Column(String(50), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    # Homologación con DDL canónico (01_ESQUEMA_SGI.sql)
    id = synonym("id_cliente")
    nit = synonym("nit_rut")
    contacto_nombre = synonym("contacto")
    contacto_email = synonym("email_contacto")

    proyectos = relationship("Proyecto", back_populates="cliente")


# =============================================================================
# MÓDULOS OPERATIVOS (VENTAS, DISEÑO Y PRODUCCIÓN)
# =============================================================================

class Proyecto(Base):
    """
    PM-01: Cabecera Comercial del Pedido.
    """
    __tablename__ = "proyectos"

    id_proyecto = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_cliente = Column(UUID(as_uuid=True), ForeignKey("clientes.id_cliente"), nullable=True)
    numero_pedido = Column(String(50), nullable=False)
    codigo_proyecto = Column(String(50), nullable=False)
    cliente_nombre = Column(String(150), nullable=False)
    contacto_nombre = Column(String(150), nullable=True)
    contacto_telefono = Column(String(50), nullable=True)
    contacto_email = Column(String(100), nullable=True)
    ubicacion_cliente = Column(String(150), nullable=True)
    cantidad = Column(Integer, default=1)
    detalle_producto = Column(Text, nullable=True)
    requisitos_cliente = Column(Text, nullable=False)
    fecha_compromiso = Column(Date, nullable=True)
    fecha_entrega_real = Column(Date, nullable=True)
    confirmado = Column(Boolean, default=False)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    # Homologación de identificadores con DDL Canónico
    id = synonym("id_proyecto")
    cliente_id = synonym("id_cliente")
    nombre = synonym("detalle_producto")
    especificaciones_tecnicas = synonym("requisitos_cliente")

    cliente = relationship("Cliente", back_populates="proyectos")
    detalles = relationship("PedidoDetalle", back_populates="proyecto", cascade="all, delete-orphan")
    planos = relationship("Plano", back_populates="proyecto", cascade="all, delete-orphan")
    ordenes_produccion = relationship("OrdenProduccion", back_populates="proyecto", cascade="all, delete-orphan")


class PedidoDetalle(Base):
    """
    PEDIDO_DETALLE: Entidad intermedia para almacenar cada pieza, conjunto, 
    servicio, trabajo, producto o elemento solicitado.
    """
    __tablename__ = "pedido_detalles"

    detalle_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = Column(UUID(as_uuid=True), ForeignKey("proyectos.id_proyecto", ondelete="CASCADE"), nullable=False)
    codigo_producto = Column(String(50), nullable=True)
    descripcion = Column(String(255), nullable=False)
    tipo = Column(String(50), default="PIEZA")
    cantidad_solicitada = Column(Integer, nullable=False, default=1)
    unidad = Column(String(20), default="UND")
    cantidad_asignada = Column(Integer, default=0)
    cantidad_pendiente = Column(Integer, default=1)
    fecha_requerida = Column(Date, nullable=True)
    prioridad = Column(String(20), default="MEDIA")
    observaciones = Column(Text, nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    # Homologación con identificadores
    id = synonym("detalle_id")
    id_pedido = synonym("pedido_id")
    fecha_compromiso = synonym("fecha_requerida")

    proyecto = relationship("Proyecto", back_populates="detalles")
    ot_detalles = relationship("OTDetalle", back_populates="pedido_detalle", cascade="all, delete-orphan")


class OTDetalle(Base):
    """
    OT_DETALLE: Entidad intermedia que relaciona PEDIDO_DETALLE con ORDEN_TRABAJO (Plano)
    Permite asignar cantidades parciales a varias OTs.
    """
    __tablename__ = "ot_detalles"

    ot_detalle_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    detalle_pedido_id = Column(UUID(as_uuid=True), ForeignKey("pedido_detalles.detalle_id", ondelete="CASCADE"), nullable=False)
    ot_id = Column(UUID(as_uuid=True), ForeignKey("planos.id_plano", ondelete="CASCADE"), nullable=False)
    cantidad_asignada = Column(Integer, nullable=False, default=1)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    id = synonym("ot_detalle_id")

    pedido_detalle = relationship("PedidoDetalle", back_populates="ot_detalles")
    plano_ot = relationship("Plano", back_populates="ot_detalles")


class Plano(Base):
    """
    PM-02: Orden de Trabajo (OT / OP) / Paquete Técnico asignado en Planta.
    """
    __tablename__ = "planos"

    id_plano = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey("proyectos.id_proyecto", ondelete="CASCADE"), nullable=False)
    id_mantenimiento = Column(Integer, ForeignKey("mantenimientos_maquinas.id_mantenimiento", ondelete="SET NULL"), nullable=True)

    codigo_op = Column(String(50), nullable=False, default="4007256")
    codigo_plano = Column(String(50), nullable=False)
    revision = Column(String(10), nullable=False, default="REV-01")
    dibujante_asignado = Column(String(150), default="Carlos Ruiz")
    unidad_planta = Column(String(100), default="Mecanizados")
    estado_diseno = Column(String(50), default="PLANIFICADA")
    causa_espera = Column(Text, nullable=True)
    material_requerido = Column(Text, nullable=True)
    insumos_opcionales = Column(Text, nullable=True)
    
    tiempo_estimado_valor = Column(Integer, default=4)
    tiempo_estimado_unidad = Column(String(20), default="HORAS")
    dias_estimados_diseno = Column(Integer, default=2)
    dias_espera_planificacion = Column(Integer, default=0)
    fecha_inicio_programada = Column(Date, nullable=True)
    fecha_entrega_cliente = Column(Date, nullable=True)
    fecha_entrega_produccion = Column(Date, nullable=True)
    
    archivo_url = Column(String(255), nullable=True)
    estado = Column(Enum(EstadoPlanoEnum), default=EstadoPlanoEnum.BORRADOR)
    aprobado_por = Column(String(100), nullable=True)
    fecha_aprobacion = Column(DateTime(timezone=True), nullable=True)
    creado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())
    actualizado_en = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Homologación con DDL Canónico
    id = synonym("id_plano")
    proyecto_id = synonym("id_proyecto")

    proyecto = relationship("Proyecto", back_populates="planos")
    mantenimiento = relationship("MantenimientoMaquina", back_populates="planos_ot")
    ot_detalles = relationship("OTDetalle", back_populates="plano_ot", cascade="all, delete-orphan")
    bom_items = relationship("BOMListaMateriales", back_populates="plano", cascade="all, delete-orphan")
    ordenes_produccion = relationship("OrdenProduccion", back_populates="plano")


class BOMListaMateriales(Base):
    """
    PM-02 / BOM: Lista de materiales y despiece requerido por cada plano/OT.
    """
    __tablename__ = "bom_lista_materiales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plano_id = Column(UUID(as_uuid=True), ForeignKey("planos.id_plano", ondelete="CASCADE"), nullable=False)
    codigo_material = Column(String(50), nullable=False)
    descripcion = Column(String(200), nullable=False)
    cantidad_requerida = Column(Float, nullable=False, default=1.0)
    unidad_medida = Column(String(20), nullable=False, default="UND")

    plano = relationship("Plano", back_populates="bom_items")


class OrdenProduccion(Base):
    """
    PM-03: Orden de Producción en Planta y Control de Liberación (ISO 9001:2026).
    """
    __tablename__ = "ordenes_produccion"

    id_op = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey("proyectos.id_proyecto", ondelete="CASCADE"), nullable=False)
    id_plano = Column(UUID(as_uuid=True), ForeignKey("planos.id_plano"), nullable=True)
    id_mantenimiento = Column(Integer, ForeignKey("mantenimientos_maquinas.id_mantenimiento", ondelete="SET NULL"), nullable=True)
    codigo_op = Column(String(50), unique=True, nullable=False)
    cantidad_fabricar = Column(Integer, default=1, nullable=False)
    estado = Column(Enum(EstadoOPEnum), default=EstadoOPEnum.BORRADOR)
    reserva_stock_100 = Column(Boolean, default=False)
    aprobado_por_calidad_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=True)
    liberada_en = Column(DateTime(timezone=True), nullable=True)
    observaciones = Column(Text, nullable=True)
    porcentaje_avance = Column(Float, default=0.0)
    tiempo_setup_estandar_minutos = Column(Float, default=20.0)
    estado_calidad = Column(String(30), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())
    actualizado_en = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Homologación con DDL Canónico
    id = synonym("id_op")
    proyecto_id = synonym("id_proyecto")
    plano_id = synonym("id_plano")

    proyecto = relationship("Proyecto", back_populates="ordenes_produccion")
    plano = relationship("Plano", back_populates="ordenes_produccion")
    no_conformidades = relationship("NoConformidad", back_populates="orden_produccion")
    registros_tiempos = relationship("RegistroTiemposProduccion", back_populates="orden_produccion", cascade="all, delete-orphan")


class RegistroTiemposProduccion(Base):
    """
    PM-03 / ADR-001 / TC-PROD-001: Control de tiempos CNC (Setup y Mecanizado).
    """
    __tablename__ = "registro_tiempos_produccion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_registro = Column(UUID(as_uuid=True), default=uuid.uuid4, index=True)
    orden_produccion_id = Column(UUID(as_uuid=True), ForeignKey("ordenes_produccion.id_op", ondelete="CASCADE"), nullable=False, index=True)
    operario_id = Column(String(100), nullable=True)
    estacion_id = Column(String(50), nullable=True, default="CNC-01")
    tipo_tiempo = Column(String(20), nullable=False, default="SETUP")  # 'SETUP' o 'MECANIZADO'
    fecha_hora_inicio = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    fecha_hora_fin = Column(DateTime(timezone=True), nullable=True)
    segundos_ejecutados = Column(Integer, default=0, nullable=False)
    pausado_por_turno = Column(Boolean, default=False, nullable=False)
    observacion_desviacion = Column(Text, nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    # Homologación con DDL / Nomenclaturas
    id_op = synonym("orden_produccion_id")
    maquina_codigo = synonym("estacion_id")

    orden_produccion = relationship("OrdenProduccion", back_populates="registros_tiempos")



class NoConformidad(Base):
    """
    PC-03 / PC-04: Gestión de No Conformidades y Acciones Correctivas (ISO 8.7).
    """
    __tablename__ = "no_conformidades"

    id_nc = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_nc = Column(String(50), unique=True, nullable=False)
    id_op = Column(UUID(as_uuid=True), ForeignKey("ordenes_produccion.id_op"), nullable=True)
    descripcion = Column(Text, nullable=False)
    origen = Column(String(100), default="INSPECCION_PROCESO")
    gravedad = Column(String(50), default="MENOR")
    estado = Column(Enum(EstadoNCEnum), default=EstadoNCEnum.ABIERTA)
    accion_correctiva = Column(Text, nullable=True)
    analisis_causa_5porques = Column(Text, nullable=True)
    eficacia_verificada = Column(Boolean, default=False)
    cerrado_por_calidad = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=True)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    reportado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    # Homologación con DDL Canónico
    id = synonym("id_nc")
    op_id = synonym("id_op")
    descripcion_hallazgo = synonym("descripcion")
    origen_proceso = synonym("origen")

    orden_produccion = relationship("OrdenProduccion", back_populates="no_conformidades")


class ArticuloInventario(Base):
    __tablename__ = "articulos_inventario"

    id_articulo = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_sku = Column(String(50), unique=True, nullable=False)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    categoria = Column(String(50), nullable=True)
    unidad_medida = Column(String(20), default="UND")
    stock_actual = Column(Float, default=0.0)
    stock_minimo = Column(Float, default=0.0)
    ubicacion = Column(String(100), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    id = synonym("id_articulo")


class LoteMaterial(Base):
    """
    PM-04: Lotes de Material y Trazabilidad de Stock (01_ESQUEMA_SGI.sql).
    """
    __tablename__ = "lotes_material"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_lote = Column(String(50), unique=True, nullable=False)
    codigo_material = Column(String(50), nullable=False)
    stock_disponible = Column(Float, nullable=False, default=0.0)
    inspeccionado_calidad = Column(Boolean, default=False)
    certificado_calidad_url = Column(String(255), nullable=True)
    fecha_ingreso = Column(DateTime(timezone=True), default=func.now())


class EntregaMaterialOP(Base):
    """
    PM-04: Entregas de Lote de Material a Órdenes de Producción.
    """
    __tablename__ = "entregas_material_op"

    id = Column(Integer, primary_key=True, autoincrement=True)
    op_id = Column(UUID(as_uuid=True), ForeignKey("ordenes_produccion.id_op", ondelete="CASCADE"), nullable=False)
    lote_id = Column(Integer, ForeignKey("lotes_material.id"), nullable=False)
    cantidad_entregada = Column(Float, nullable=False)
    entregado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=False)
    recibido_por_produccion = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=False)
    fecha_entrega = Column(DateTime(timezone=True), default=func.now())


class InstrumentoMedicion(Base):
    """
    PM-06: Catálogo de Instrumentos y Equipos de Medición (ISO 9001:2026).
    """
    __tablename__ = "instrumentos_medicion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_equipo = Column(String(50), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    fecha_ultima_calibracion = Column(Date, nullable=False)
    fecha_vencimiento_calibracion = Column(Date, nullable=False)
    estado_disponible = Column(Boolean, default=True)


class FichaMetrologia(Base):
    """
    PM-06: Fichas de Inspección Metrológica por Cota y Tolerancias.
    """
    __tablename__ = "fichas_metrologia"

    id = Column(Integer, primary_key=True, autoincrement=True)
    op_id = Column(UUID(as_uuid=True), ForeignKey("ordenes_produccion.id_op", ondelete="CASCADE"), nullable=False)
    instrumento_id = Column(Integer, ForeignKey("instrumentos_medicion.id"), nullable=False)
    cota_medida = Column(Float, nullable=False)
    tolerancia_min = Column(Float, nullable=False)
    tolerancia_max = Column(Float, nullable=False)
    resultado_conforme = Column(Boolean, nullable=False)
    inspector_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=False)
    fecha_inspeccion = Column(DateTime(timezone=True), default=func.now())


class SolicitudCompra(Base):
    """
    PM-02 / PM-04: Persistencia formal de Solicitudes de Compra de Materia Prima / BOM.
    """
    __tablename__ = "solicitudes_compra"

    id_solicitud = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_solicitud = Column(String(50), nullable=False)
    codigo_op = Column(String(50), nullable=True)
    codigo_plano = Column(String(50), nullable=True)
    numero_pedido = Column(String(50), nullable=True)
    nombre_item = Column(String(150), nullable=False)
    codigo_sku = Column(String(50), nullable=True)
    categoria = Column(String(50), default="MATERIA_PRIMA")
    cantidad_solicitada = Column(Float, default=1.0)
    unidad_medida = Column(String(20), default="UND")
    estado = Column(String(50), default="PENDIENTE")
    fecha_solicitud = Column(DateTime(timezone=True), default=func.now())
    proveedor_sugerido = Column(String(150), nullable=True)
    observaciones = Column(Text, nullable=True)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey("proyectos.id_proyecto", ondelete="SET NULL"), nullable=True)
    id_plano = Column(UUID(as_uuid=True), ForeignKey("planos.id_plano", ondelete="SET NULL"), nullable=True)

    id = synonym("id_solicitud")


class EntradaMercancia(Base):
    __tablename__ = "entradas_mercancia"

    id_entrada = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_factura_remision = Column(String(100), nullable=False)
    proveedor = Column(String(150), nullable=False)
    fecha_recepcion = Column(DateTime(timezone=True), default=func.now())
    recibido_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=True)

    id = synonym("id_entrada")


class AjusteInventario(Base):
    __tablename__ = "ajustes_inventario"

    id_ajuste = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_articulo = Column(UUID(as_uuid=True), ForeignKey("articulos_inventario.id_articulo"), nullable=False)
    tipo_ajuste = Column(String(20), nullable=False)
    cantidad = Column(Float, nullable=False)
    motivo = Column(Text, nullable=False)
    fecha_ajuste = Column(DateTime(timezone=True), default=func.now())

    id = synonym("id_ajuste")


# =============================================================================
# MÓDULO MANTENIMIENTO & OVERHAUL
# =============================================================================

class MantenimientoMaquina(Base):
    """
    Mapeo de la tabla 'mantenimientos_maquinas' para registro de ingresos 
    y seguimiento del avance de overhaul.
    """
    __tablename__ = "mantenimientos_maquinas"

    id_mantenimiento = Column(Integer, primary_key=True, index=True)
    codigo_mantenimiento = Column(String(50), unique=True, nullable=False, index=True)
    cliente_nombre = Column(String(150), nullable=False)
    codigo_op = Column(String(50), nullable=False)
    nombre_maquina = Column(String(150), nullable=False)
    marca_modelo = Column(String(150), nullable=True)
    serie_maquina = Column(String(100), nullable=True)
    observaciones_ingreso = Column(Text, nullable=True)
    fase_mantenimiento = Column(String(50), default="LAVADO_DESARME", nullable=False)
    confirmado = Column(Boolean, default=False, nullable=False)
    total_piezas_autorizadas = Column(Integer, default=0)
    piezas_terminadas_ok = Column(Integer, default=0)
    porcentaje_kit_listo = Column(Float, default=0.0)
    creado_en = Column(DateTime(timezone=True), default=func.now())
    actualizado_en = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    id = synonym("id_mantenimiento")

    piezas_det = relationship("MantenimientoPiezaDet", back_populates="mantenimiento", cascade="all, delete-orphan")
    planos_ot = relationship("Plano", back_populates="mantenimiento")


class MantenimientoPiezaDet(Base):
    """
    Mapeo de la tabla 'mantenimientos_piezas_det' para el desglosado 
    del levantamiento técnico de piezas por máquina.
    """
    __tablename__ = "mantenimientos_piezas_det"

    id_pieza_det = Column(Integer, primary_key=True, index=True)
    id_mantenimiento = Column(Integer, ForeignKey("mantenimientos_maquinas.id_mantenimiento", ondelete="CASCADE"), nullable=False)
    codigo_item = Column(String(50), nullable=False)
    descripcion_pieza = Column(String(200), nullable=False)
    cantidad = Column(Integer, default=1)
    accion_tecnica = Column(String(50), nullable=False)
    estado_pieza = Column(String(50), default="DIAGNOSTICO")
    creado_en = Column(DateTime(timezone=True), default=func.now())

    id = synonym("id_pieza_det")

    mantenimiento = relationship("MantenimientoMaquina", back_populates="piezas_det")