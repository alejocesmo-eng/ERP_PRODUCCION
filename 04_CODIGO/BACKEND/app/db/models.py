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
    Float,
    Numeric,
    JSON,
    CheckConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
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


class EstadoCotizacionEnum(str, enum.Enum):
    BORRADOR = "BORRADOR"
    ENVIADA = "ENVIADA"
    APROBADA = "APROBADA"
    RECHAZADA = "RECHAZADA"


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
    TERMINADA = "TERMINADA"
    INSPECCION_CALIDAD = "INSPECCION_CALIDAD"
    EN_INSPECCION = "EN_INSPECCION"
    LISTA_PARA_LIBERAR = "LISTA_PARA_LIBERAR"
    LIBERADA = "LIBERADA"
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


class AreaTrabajadorEnum(str, enum.Enum):
    VENTAS = "VENTAS"
    DISENO = "DISENO"
    ALMACEN = "ALMACEN"
    PRODUCCION = "PRODUCCION"
    CALIDAD = "CALIDAD"
    ADMINISTRACION = "ADMINISTRACION"


class TipoEstructuraFinancieraEnum(str, enum.Enum):
    CUENTA_CONTABLE = "CUENTA_CONTABLE"
    CENTRO_COSTO = "CENTRO_COSTO"
    UNIDAD_NEGOCIO = "UNIDAD_NEGOCIO"


class SocioNegocio(Base):
    __tablename__ = "socios_negocio"
    __table_args__ = (
        CheckConstraint(
            "es_cliente OR es_proveedor",
            name="ck_socios_negocio_tipo",
        ),
        CheckConstraint(
            "condiciones_pago_dias BETWEEN 0 AND 365",
            name="ck_socios_negocio_condiciones_pago",
        ),
    )

    id_socio = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_socio = Column(String(50), unique=True, nullable=False, index=True)
    nit_cedula = Column(String(30), unique=True, nullable=False, index=True)
    razon_social = Column(String(200), nullable=False)
    es_cliente = Column(Boolean, nullable=False, default=False)
    es_proveedor = Column(Boolean, nullable=False, default=False)
    direccion = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    email = Column(String(150), nullable=True)
    condiciones_pago_dias = Column(Integer, nullable=False, default=30)
    cuenta_contable_por_cobrar = Column(String(100), nullable=True)
    cuenta_contable_por_pagar = Column(String(100), nullable=True)
    estado_activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())
    actualizado_en = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())


class Cotizacion(Base):
    """
    Entidad de Cotización Comercial previa al Pedido.
    """
    __tablename__ = "cotizaciones"

    id_cotizacion = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_socio = Column(UUID(as_uuid=True), ForeignKey("socios_negocio.id_socio"), nullable=False)
    numero_cotizacion = Column(String(50), unique=True, nullable=False)
    fecha_emision = Column(Date, nullable=False, default=date.today)
    fecha_vigencia = Column(Date, nullable=True)
    estado = Column(Enum(EstadoCotizacionEnum), default=EstadoCotizacionEnum.BORRADOR)
    valor_total = Column(Numeric(14, 2), default=0)
    condiciones_comerciales = Column(Text, nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    id = synonym("id_cotizacion")
    posiciones = relationship("PosicionCotizacion", back_populates="cotizacion", cascade="all, delete-orphan")


class PosicionCotizacion(Base):
    """
    Detalle de ítem cotizado.
    """
    __tablename__ = "posiciones_cotizacion"

    id_posicion = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_cotizacion = Column(UUID(as_uuid=True), ForeignKey("cotizaciones.id_cotizacion", ondelete="CASCADE"), nullable=False)
    numero_producto = Column(String(50), nullable=True)  # SKU
    descripcion = Column(String(255), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    precio_unitario = Column(Numeric(14, 4), nullable=False, default=0)
    vinculo_plano_catalogo = Column(String(50), nullable=True)  # Referencia al código de plano vigente

    id = synonym("id_posicion")
    cotizacion = relationship("Cotizacion", back_populates="posiciones")


class TrabajadorUsuario(Base):
    __tablename__ = "trabajadores_usuarios"
    __table_args__ = (
        CheckConstraint(
            "tarifa_hora_mano_obra >= 0",
            name="ck_trabajadores_usuarios_tarifa",
        ),
    )

    id_trabajador = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cedula = Column(String(30), unique=True, nullable=False, index=True)
    nombre_completo = Column(String(150), nullable=False)
    area = Column(
        SAEnum(
            AreaTrabajadorEnum,
            native_enum=False,
            create_constraint=True,
            name="area_trabajador_enum",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    cargo = Column(String(100), nullable=False)
    tarifa_hora_mano_obra = Column(Numeric(14, 4), nullable=False, default=0)
    id_usuario_sistema = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id_usuario", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )


class EstructuraFinanciera(Base):
    """
    Estructura Financiera y Organizativa del ERP (Cuentas Contables, Centros de Costo, Unidades de Negocio).
    Se agrega unique=True a la columna 'codigo' para resolver la restricción de clave foránea en 'cuenta_padre'.
    """
    __tablename__ = "estructura_financiera"

    id_elemento = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo = Column(
        SAEnum(
            TipoEstructuraFinancieraEnum,
            native_enum=False,
            create_constraint=True,
            name="tipo_estructura_financiera",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    cuenta_padre = Column(String(50), ForeignKey("estructura_financiera.codigo"), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)


class UnidadMedida(Base):
    __tablename__ = "unidades_medida"

    id_unidad = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(100), nullable=False)
    simbolo = Column(String(20), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())


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
    cotizacion_total = Column(Numeric(14, 2), nullable=True)
    presupuestos_componentes = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
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
    version = Column(String(10), nullable=False, default="V-01")
    dibujante_asignado = Column(String(150), default="Carlos Ruiz")
    unidad_planta = Column(String(100), default="Mecanizados")
    estado_diseno = Column(String(50), default="PLANIFICADA")
    causa_espera = Column(Text, nullable=True)
    material_requerido = Column(Text, nullable=True)
    insumos_opcionales = Column(Text, nullable=True)

    tiempo_estimado_valor = Column(Integer, default=4)
    tiempo_estimado_unidad = Column(String(20), default="HORAS")
    tiempo_estimado_setup_minutos = Column(Float, nullable=False, default=20)
    tiempo_estimado_mecanizado_horas = Column(Float, nullable=True)
    dias_estimados_diseno = Column(Integer, default=2)
    dias_espera_planificacion = Column(Integer, default=0)
    fecha_inicio_programada = Column(Date, nullable=True)
    fecha_entrega_cliente = Column(Date, nullable=True)
    fecha_entrega_produccion = Column(Date, nullable=True)

    # Trazabilidad de Tiempos de Diseño (MES Estilo Planta)
    fecha_inicio_diseno = Column(DateTime(timezone=True), nullable=True)
    fecha_fin_diseno = Column(DateTime(timezone=True), nullable=True)
    tiempo_total_diseno_minutos = Column(Integer, nullable=True)

    archivo_pdf_url = Column(String(255), nullable=True)
    archivo_step_url = Column(String(255), nullable=True)
    archivo_dxf_url = Column(String(255), nullable=True)
    archivo_url = synonym("archivo_pdf_url")
    revision = synonym("version")

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
    estado_abastecimiento = Column(String(30), nullable=False, default="SIN_SOLICITAR")

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
    causa_raiz = Column(String(50), nullable=True)
    piezas_scrap = Column(Integer, nullable=False, default=0)
    disposicion = Column(String(50), nullable=True)
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
    acciones_capa = relationship(
        "AccionCAPA",
        back_populates="reporte",
        cascade="all, delete-orphan",
    )


class AccionCAPA(Base):
    __tablename__ = "acciones_capa"

    id_capa = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_rnc = Column(
        UUID(as_uuid=True),
        ForeignKey("no_conformidades.id_nc", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    accion_correctiva = Column(Text, nullable=False)
    responsable_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=True)
    fecha_compromiso = Column(Date, nullable=False)
    estado_cierre = Column(String(30), nullable=False, default="ABIERTA")
    evidencia_cierre = Column(Text, nullable=True)
    cerrada_en = Column(DateTime(timezone=True), nullable=True)
    creada_en = Column(DateTime(timezone=True), nullable=False, default=func.now())

    reporte = relationship("NoConformidad", back_populates="acciones_capa")


# =============================================================================
# MÓDULO ALMACÉN, INVENTARIOS Y CATEGORÍAS DINÁMICAS
# =============================================================================

class CategoriaInventario(Base):
    """
    PM-04: Categorías Dinámicas de Inventario (Materia Prima, Herramientas, Consumibles, EPPs).
    """
    __tablename__ = "categorias_inventario"

    id_categoria = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(50), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    icono = Column(String(10), nullable=True, default="📦")
    descripcion = Column(Text, nullable=True)
    es_personalizada = Column(Boolean, default=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    id = synonym("id_categoria")


class TipoMaterialSAP(str, enum.Enum):
    ROH = "ROH"
    HALB = "HALB"
    FERT = "FERT"
    VERB = "VERB"
    ERSA = "ERSA"


class MetodoValoracionSAP(str, enum.Enum):
    CPP = "CPP"
    FIFO = "FIFO"
    PRECIO_ESTANDAR = "PRECIO_ESTANDAR"


class ClaseMovimientoSAP(str, enum.Enum):
    ENTRADA_COMPRA_101 = "101"
    SALIDA_CENTRO_COSTO_201 = "201"
    CONSUMO_OP_261 = "261"
    TRASLADO_311 = "311"
    SCRAP_551 = "551"


class CentroAlmacen(Base):
    __tablename__ = "centros_almacen"

    id_centro = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_centro = Column(String(50), unique=True, nullable=False)
    nombre_centro = Column(String(150), nullable=False)
    almacenes = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())


class CatalogoMaterialSAP(Base):
    __tablename__ = "catalogo_materiales_sap"
    __table_args__ = (
        CheckConstraint(
            "precio_unitario_valorado >= 0 AND stock_seguridad >= 0 AND punto_reorden >= 0",
            name="ck_catalogo_material_sap_valores_no_negativos",
        ),
    )

    id_material = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_articulo = Column(
        UUID(as_uuid=True),
        ForeignKey("articulos_inventario.id_articulo", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    sku_codigo = Column(
        String(50),
        ForeignKey("articulos_inventario.codigo_sku", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    descripcion_tecnica = Column(String(255), nullable=False)
    tipo_material_sap = Column(
        SAEnum(TipoMaterialSAP, native_enum=False, create_constraint=True, name="tipo_material_sap"),
        nullable=False,
        default=TipoMaterialSAP.ROH,
    )
    unidad_medida = Column(String(20), nullable=False, default="UND")
    clase_valoracion = Column(String(50), nullable=False, default="3000-MP")
    cuenta_contable_activo = Column(String(100), nullable=False, default="143505 - Inventario Materia Prima")
    cuenta_contable_gasto = Column(String(100), nullable=False, default="510506 - Consumo de Insumos")
    cuenta_contable_transitoria = Column(
        String(100),
        nullable=False,
        default="220505 - Recepción de facturas por conciliar",
    )
    centro_costo_defecto = Column(String(50), nullable=False, default="CC-100-PLANTA")
    metodo_valoracion = Column(
        SAEnum(MetodoValoracionSAP, native_enum=False, create_constraint=True, name="metodo_valoracion_sap"),
        nullable=False,
        default=MetodoValoracionSAP.CPP,
    )
    precio_unitario_valorado = Column(Numeric(16, 4), nullable=False, default=0)
    stock_seguridad = Column(Numeric(16, 4), nullable=False, default=0)
    punto_reorden = Column(Numeric(16, 4), nullable=False, default=0)
    codigo_centro = Column(
        String(50),
        ForeignKey("centros_almacen.codigo_centro"),
        nullable=False,
    )
    almacen_fisico = Column(String(50), nullable=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())
    actualizado_en = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    articulo = relationship(
        "ArticuloInventario",
        back_populates="catalogo_sap",
        foreign_keys=[id_articulo],
    )


class ArticuloInventario(Base):
    __tablename__ = "articulos_inventario"

    id_articulo = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_sku = Column(String(50), unique=True, nullable=False)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    categoria = Column(String(50), nullable=True)
    tipo_inventario = Column(String(50), nullable=False, default="GENERAL")
    unidad_medida = Column(String(20), default="UND")
    stock_actual = Column(Float, default=0.0)
    stock_reservado = Column(Float, nullable=False, default=0.0)
    costo_unitario = Column(Numeric(14, 4), nullable=False, default=0)
    metodo_valoracion = Column(String(20), nullable=False, default="PROMEDIO")
    stock_minimo = Column(Float, default=0.0)
    ubicacion = Column(String(100), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())

    id = synonym("id_articulo")
    catalogo_sap = relationship(
        "CatalogoMaterialSAP",
        back_populates="articulo",
        foreign_keys="CatalogoMaterialSAP.id_articulo",
        uselist=False,
        cascade="all, delete-orphan",
    )


class LoteMaterial(Base):
    """
    PM-04: Lotes de Material y Trazabilidad de Stock (01_ESQUEMA_SGI.sql).
    """
    __tablename__ = "lotes_material"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_lote = Column(String(50), unique=True, nullable=False)
    codigo_material = Column(String(50), nullable=False)
    codigo_centro = Column(String(50), nullable=True)
    almacen_fisico = Column(String(50), nullable=True)
    numero_colada = Column(String(50), nullable=True)
    stock_disponible = Column(Float, nullable=False, default=0.0)
    stock_reservado = Column(Float, nullable=False, default=0.0)
    costo_unitario = Column(Numeric(14, 4), nullable=False, default=0)
    inspeccionado_calidad = Column(Boolean, default=False)
    estado_calidad = Column(String(20), nullable=False, default="CUARENTENA")
    certificado_calidad_url = Column(String(255), nullable=True)
    fecha_ingreso = Column(DateTime(timezone=True), default=func.now())


class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"

    id_movimiento = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_articulo = Column(
        UUID(as_uuid=True),
        ForeignKey("articulos_inventario.id_articulo"),
        nullable=False,
        index=True,
    )
    id_lote = Column(Integer, ForeignKey("lotes_material.id"), nullable=False, index=True)
    tipo_movimiento = Column(String(3), nullable=False)
    cantidad = Column(Float, nullable=False)
    costo_unitario = Column(Numeric(14, 4), nullable=False)
    valor_total = Column(Numeric(14, 4), nullable=False)
    saldo_cantidad = Column(Float, nullable=False)
    referencia_tipo = Column(String(30), nullable=False)
    referencia_id = Column(String(100), nullable=False)
    documento_externo = Column(String(100), nullable=True)
    documento_url = Column(String(255), nullable=True)
    proveedor = Column(String(150), nullable=True)
    codigo_op = Column(String(50), nullable=True)
    destino = Column(String(100), nullable=True)
    registrado_por = Column(String(150), nullable=False)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)


class MovimientoKardexSAP(Base):
    __tablename__ = "movimientos_kardex_sap"
    __table_args__ = (
        CheckConstraint(
            "cantidad > 0 AND costo_unitario >= 0 AND costo_total_movimiento >= 0",
            name="ck_movimiento_kardex_sap_valores",
        ),
    )

    id_movimiento = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    numero_documento_material = Column(String(50), unique=True, nullable=False, index=True)
    clase_movimiento = Column(
        SAEnum(
            ClaseMovimientoSAP,
            native_enum=False,
            create_constraint=True,
            name="clase_movimiento_sap",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    sku_codigo = Column(String(50), ForeignKey("catalogo_materiales_sap.sku_codigo"), nullable=False, index=True)
    codigo_centro = Column(
        String(50),
        ForeignKey("centros_almacen.codigo_centro"),
        nullable=False,
    )
    almacen_origen = Column(String(50), nullable=True)
    almacen_destino = Column(String(50), nullable=True)
    cantidad = Column(Numeric(16, 4), nullable=False)
    costo_unitario = Column(Numeric(16, 4), nullable=False)
    costo_total_movimiento = Column(Numeric(18, 4), nullable=False)
    cuenta_debito = Column(String(100), nullable=False)
    cuenta_credito = Column(String(100), nullable=False)
    centro_costo_imputado = Column(String(50), nullable=True)
    referencia_op = Column(String(50), nullable=True)
    referencia_externa = Column(String(100), nullable=True)
    registrado_por = Column(String(150), nullable=False)
    fecha_hora = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)


class RegistroCalidadLote(Base):
    __tablename__ = "auditoria_calidad_lotes"

    id_registro = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_lote = Column(Integer, ForeignKey("lotes_material.id"), nullable=False, index=True)
    estado_anterior = Column(String(20), nullable=True)
    estado_nuevo = Column(String(20), nullable=False)
    motivo = Column(Text, nullable=False)
    registrado_por = Column(String(150), nullable=False)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())


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


class SolicitudCambioTecnico(Base):
    """
    ECR (Engineering Change Request): Trazabilidad de modificaciones sobre planos.
    Se genera desde la herramienta de anotación del visor de planos.
    """
    __tablename__ = "solicitudes_cambio_tecnico"

    id_solicitud = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_plano = Column(UUID(as_uuid=True), ForeignKey("planos.id_plano", ondelete="CASCADE"), nullable=False)
    version_origen = Column(String(10), nullable=False)
    descripcion_cambio = Column(Text, nullable=False)
    cota_afectada = Column(String(100), nullable=True)
    tipo_cambio = Column(String(50), default="CORRECCION")  # CORRECCION, MEJORA, REQUISITO_CLIENTE
    prioridad = Column(String(20), default="MEDIA")
    solicitado_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id_usuario"), nullable=False)
    estado_solicitud = Column(String(30), default="PENDIENTE")  # PENDIENTE, APROBADO, RECHAZADO, IMPLEMENTADO
    imagen_anotacion_url = Column(String(255), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())
    actualizado_en = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    plano = relationship("Plano")


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
    estado_bom = Column(String(30), nullable=False, default="SOLICITADO")
    fecha_solicitud = Column(DateTime(timezone=True), default=func.now())
    proveedor_sugerido = Column(String(150), nullable=True)
    observaciones = Column(Text, nullable=True)
    id_proyecto = Column(UUID(as_uuid=True), ForeignKey("proyectos.id_proyecto", ondelete="SET NULL"), nullable=True)
    id_plano = Column(UUID(as_uuid=True), ForeignKey("planos.id_plano", ondelete="SET NULL"), nullable=True)

    id = synonym("id_solicitud")


class RetalSobrante(Base):
    __tablename__ = "retales_sobrantes"

    id_retal = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_retal = Column(String(50), unique=True, nullable=False)
    codigo_material = Column(String(50), nullable=False, index=True)
    descripcion = Column(String(200), nullable=True)
    dimensiones = Column(String(200), nullable=True)
    unidad_medida = Column(String(20), nullable=False, default="UND")
    cantidad_disponible = Column(Float, nullable=False, default=0.0)
    cantidad_reservada = Column(Float, nullable=False, default=0.0)
    reutilizable = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), default=func.now())


class EjecucionMRP(Base):
    __tablename__ = "ejecuciones_mrp"

    id_ejecucion = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ejecutado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())
    ejecutado_por = Column(String(100), nullable=True)
    estado = Column(String(30), nullable=False, default="COMPLETADA")


class RequisicionMRP(Base):
    __tablename__ = "requisiciones_mrp"

    id_requisicion = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_ejecucion = Column(UUID(as_uuid=True), ForeignKey("ejecuciones_mrp.id_ejecucion", ondelete="CASCADE"), nullable=False)
    codigo_material = Column(String(50), nullable=False)
    especificacion = Column(String(200), nullable=False)
    unidad_medida = Column(String(20), nullable=False)
    demanda_bruta = Column(Float, nullable=False)
    stock_libre = Column(Float, nullable=False)
    retales_disponibles = Column(Float, nullable=False)
    compras_en_transito = Column(Float, nullable=False)
    stock_reservado = Column(Float, nullable=False)
    requerimiento_neto = Column(Float, nullable=False)
    numero_solicitud = Column(String(50), nullable=True)
    estado = Column(String(30), nullable=False, default="SOLICITADO")
    solicitud_id = Column(UUID(as_uuid=True), ForeignKey("solicitudes_compra.id_solicitud", ondelete="SET NULL"), nullable=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())

    ejecucion = relationship("EjecucionMRP")
    trazabilidad = relationship("TrazabilidadRequisicionMRP", back_populates="requisicion", cascade="all, delete-orphan")


class TrazabilidadRequisicionMRP(Base):
    __tablename__ = "trazabilidad_requisicion_mrp"

    id = Column(Integer, primary_key=True, autoincrement=True)
    requisicion_id = Column(UUID(as_uuid=True), ForeignKey("requisiciones_mrp.id_requisicion", ondelete="CASCADE"), nullable=False)
    codigo_op = Column(String(50), nullable=False)
    codigo_plano = Column(String(50), nullable=False)
    cantidad_demanda = Column(Float, nullable=False)

    requisicion = relationship("RequisicionMRP", back_populates="trazabilidad")


class CentroTrabajo(Base):
    __tablename__ = "centros_trabajo"

    id_centro = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_centro = Column(String(50), unique=True, nullable=False)
    tarifa_hora_mecanizado = Column(Numeric(14, 4), nullable=False, default=0)
    tarifa_hora_setup = Column(Numeric(14, 4), nullable=False, default=0)
    horas_capacidad_turno = Column(Numeric(5, 2), nullable=False, default=8)
    equivalencia = Column(String(50), nullable=False, default="GENERAL")
    activo = Column(Boolean, nullable=False, default=True)


class ConsumoMaterialOP(Base):
    __tablename__ = "consumos_material_op"

    id_consumo = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    op_id = Column(UUID(as_uuid=True), ForeignKey("ordenes_produccion.id_op", ondelete="CASCADE"), nullable=False, index=True)
    codigo_material = Column(String(50), nullable=False)
    descripcion_material = Column(String(200), nullable=False)
    cantidad = Column(Float, nullable=False)
    unidad_medida = Column(String(20), nullable=False)
    costo_unitario = Column(Numeric(14, 4), nullable=False)
    fuente = Column(String(30), nullable=False, default="KARDEX")
    registrado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())


class ServicioTerceroOP(Base):
    __tablename__ = "servicios_terceros_op"

    id_servicio = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    op_id = Column(UUID(as_uuid=True), ForeignKey("ordenes_produccion.id_op", ondelete="CASCADE"), nullable=False, index=True)
    proveedor = Column(String(150), nullable=False)
    descripcion = Column(String(200), nullable=False)
    numero_factura = Column(String(100), nullable=False)
    costo = Column(Numeric(14, 2), nullable=False)
    registrado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())


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


class EquipoPlanta(Base):
    __tablename__ = "equipos_planta"

    id_equipo = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_maquina = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    centro_trabajo_asociado = Column(
        String(50),
        ForeignKey("centros_trabajo.codigo_centro", ondelete="SET NULL"),
        nullable=True,
    )
    horas_uso_acumuladas = Column(Numeric(14, 2), nullable=False, default=0)
    estado_maquina = Column(String(30), nullable=False, default="OPERATIVA")
    creado_en = Column(DateTime(timezone=True), nullable=False, default=func.now())


class OrdenMantenimiento(Base):
    __tablename__ = "ordenes_mantenimiento"

    id_otm = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_otm = Column(String(50), unique=True, nullable=False, index=True)
    id_equipo = Column(
        UUID(as_uuid=True),
        ForeignKey("equipos_planta.id_equipo", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tipo = Column(String(20), nullable=False)
    descripcion_falla = Column(Text, nullable=False)
    repuestos_solicitados_almacen = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    fecha_programada = Column(Date, nullable=True)
    estado = Column(String(20), nullable=False, default="ABIERTA")
    creada_en = Column(DateTime(timezone=True), nullable=False, default=func.now())
    cerrada_en = Column(DateTime(timezone=True), nullable=True)


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


# =============================================================================
# MÓDULO CONFIGURACIÓN GENERAL / EMPRESA EMISORA (DATOS MAESTROS)
# =============================================================================

class EmpresaEmisora(Base):
    """
    Entidad única que almacena la razón social, datos fiscales y membrete
    de la empresa emisora para cotizaciones, pedidos y documentos ISO.
    """
    __tablename__ = "empresa_emisora"

    id = Column(Integer, primary_key=True, index=True)
    codigo_empresa = Column(String(50), unique=True, default="HD-01")
    razon_social = Column(String(255), nullable=False, default="HD Precision and Technology S.A.S")
    nit = Column(String(50), nullable=False, default="901.456.789-0")
    actividad_principal = Column(String(255), default="Mecanizado de Precision / Fabricacion Industrial")
    direccion = Column(String(255), default="Zona Industrial")
    ciudad = Column(String(100), default="Funza / Medellin, Colombia")
    telefono = Column(String(50), default="(004) 300 0000")
    email = Column(String(100), default="ventas@hdprecision.com")
    sitio_web = Column(String(100), default="www.hdprecision.com")
    terminos_garantia = Column(Text, nullable=True)


# =============================================================================
# HISTORIAL, TRAZABILIDAD Y PROTECCIÓN DE INDICADORES (ISO 9001:2026)
# =============================================================================

class HistorialAccionesDocumento(Base):
    """
    Trazabilidad transversal de eventos y estados para Pedidos y Órdenes de Producción.
    Permite auditar cotizaciones, aperturas, liberaciones y registrar suspensiones
    con 'pausa_tiempo_productivo=True' para aislar las demoras comerciales del OEE y Lead Time.
    """
    __tablename__ = "historial_acciones_documento"

    id_historial = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_entidad = Column(String(30), nullable=False, index=True)  # 'PEDIDO' u 'ORDEN_PRODUCCION'
    identificador_documento = Column(String(50), nullable=False, index=True)  # Ej: 'PED-2026-088', '4007256'
    
    accion = Column(String(60), nullable=False)
    # Estados de ejemplo: 'COTIZACION_EMITIDA', 'COTIZACION_APROBADA', 'PEDIDO_CREADO',
    #                    'SUSPENDIDO_COMERCIAL', 'REACTIVADO', 'OP_APERTURA', 'OP_LIBERADA',
    #                    'INICIO_MECANIZADO_MES', 'PAUSA_EXTERNA_CLIENTE', 'FINALIZADO'
    
    estado_anterior = Column(String(50), nullable=True)
    estado_nuevo = Column(String(50), nullable=True)
    
    # Flag para proteger los indicadores de productividad de planta
    pausa_tiempo_productivo = Column(Boolean, default=False, nullable=False)
    
    motivo_observacion = Column(Text, nullable=True)
    usuario_responsable = Column(String(100), nullable=False, default="Sistema Comercial")
    area_origen = Column(String(50), nullable=False, default="VENTAS")  # VENTAS, DISENO, PRODUCCION, CALIDAD
    fecha_hora = Column(DateTime(timezone=True), default=func.now(), nullable=False)