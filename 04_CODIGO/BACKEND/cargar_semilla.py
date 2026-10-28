import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Tuple, Type

from sqlalchemy import and_, inspect
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.database import Base, SessionLocal, engine
from app.db.models import (
    AccionCAPA,
    ArticuloInventario,
    CategoriaInventario,
    CatalogoMaterialSAP,
    CentroAlmacen,
    CentroTrabajo,
    ClaseMovimientoSAP,
    Cliente,
    ConsumoMaterialOP,
    EntregaMaterialOP,
    Empleado,
    EquipoPlanta,
    EstadoNCEnum,
    EstadoOPEnum,
    EstadoPlanoEnum,
    EstadoCotizacionEnum,
    EstructuraFinanciera,
    InstrumentoMedicion,
    LoteMaterial,
    Maquina,
    MovimientoInventario,
    NoConformidad,
    OrdenMantenimiento,
    OrdenProduccion,
    OTDetalle,
    PedidoDetalle,
    Plano,
    Proyecto,
    RegistroCalidadLote,
    RetalSobrante,
    Rol,
    ServicioTerceroOP,
    SocioNegocio,
    SolicitudCompra,
    SolicitudCambioTecnico,
    TrabajadorUsuario,
    UnidadMedida,
    Usuario,
    MetodoValoracionSAP,
    MovimientoKardexSAP,
    TipoEstructuraFinancieraEnum,
    TipoMaterialSAP,
    Cotizacion,
    PosicionCotizacion,
)
from app.db.models_calidad import InspeccionCalidad
from app.db.models_produccion import (
    EstadoOperacionEnum,
    NotificacionLider,
    OperacionOT,
    RegistroTiempoOperario,
    SubLoteOperacion,
    TipoNotificacionEnum,
    TipoUnidadPlantaEnum,
)


def crear_instancia_segura(modelo: Type[Any], **kwargs: Any) -> Any:
    """Crea una instancia usando solo atributos columna declarados por el modelo."""
    columnas = set(modelo.__mapper__.column_attrs.keys())
    datos_validos = {nombre: valor for nombre, valor in kwargs.items() if nombre in columnas}
    return modelo(**datos_validos)


def _upsert(
    db: Session,
    modelo: Type[Any],
    claves: Tuple[str, ...],
    valores: Dict[str, Any],
) -> Any:
    columnas = set(modelo.__mapper__.column_attrs.keys())
    desconocidas = set(claves) - columnas
    if desconocidas:
        raise ValueError(
            f"Claves de búsqueda inexistentes en {modelo.__name__}: {', '.join(sorted(desconocidas))}"
        )

    valores_validos = {nombre: valor for nombre, valor in valores.items() if nombre in columnas}
    filtros = [getattr(modelo, nombre) == valores_validos[nombre] for nombre in claves]
    instancia = db.query(modelo).filter(and_(*filtros)).first()
    if instancia is None:
        instancia = crear_instancia_segura(modelo, **valores_validos)
        db.add(instancia)
    else:
        for nombre, valor in valores_validos.items():
            if nombre not in claves:
                setattr(instancia, nombre, valor)
    db.flush()
    return instancia


def _insertar_movimiento_si_no_existe(
    db: Session,
    modelo: Type[Any],
    claves: Tuple[str, ...],
    valores: Dict[str, Any],
) -> Any:
    columnas = set(modelo.__mapper__.column_attrs.keys())
    desconocidas = set(claves) - columnas
    if desconocidas:
        raise ValueError(
            f"Claves de búsqueda inexistentes en {modelo.__name__}: {', '.join(sorted(desconocidas))}"
        )
    filtros = [getattr(modelo, nombre) == valores[nombre] for nombre in claves]
    existente = db.query(modelo).filter(and_(*filtros)).first()
    if existente is not None:
        return existente
    movimiento = crear_instancia_segura(modelo, **valores)
    db.add(movimiento)
    db.flush()
    return movimiento


def _registrar_movimiento_kardex(
    db: Session,
    numero_documento: str,
    clase: ClaseMovimientoSAP,
    catalogo: CatalogoMaterialSAP,
    cantidad: Decimal,
    almacen_origen: str | None,
    almacen_destino: str | None,
    cuenta_debito: str,
    cuenta_credito: str,
    referencia_externa: str,
    fecha_hora: datetime,
    referencia_op: str | None = None,
) -> MovimientoKardexSAP:
    return _insertar_movimiento_si_no_existe(
        db,
        MovimientoKardexSAP,
        ("numero_documento_material",),
        {
            "numero_documento_material": numero_documento,
            "clase_movimiento": clase,
            "sku_codigo": catalogo.sku_codigo,
            "codigo_centro": catalogo.codigo_centro,
            "almacen_origen": almacen_origen,
            "almacen_destino": almacen_destino,
            "cantidad": cantidad,
            "costo_unitario": catalogo.precio_unitario_valorado,
            "costo_total_movimiento": cantidad * catalogo.precio_unitario_valorado,
            "cuenta_debito": cuenta_debito,
            "cuenta_credito": cuenta_credito,
            "centro_costo_imputado": catalogo.centro_costo_defecto,
            "referencia_op": referencia_op,
            "referencia_externa": referencia_externa,
            "registrado_por": "semilla@sgi.local",
            "fecha_hora": fecha_hora,
        },
    )


def _verificar_migracion_requerida() -> None:
    columnas_requeridas = {
        "centros_trabajo": {"horas_capacidad_turno", "equivalencia"},
        "planos": {"tiempo_estimado_setup_minutos", "tiempo_estimado_mecanizado_horas"},
        "no_conformidades": {"causa_raiz", "piezas_scrap", "disposicion"},
        "proyectos": {"presupuestos_componentes"},
    }
    inspector = inspect(engine)
    faltantes = []
    for tabla, requeridas in columnas_requeridas.items():
        existentes = {columna["name"] for columna in inspector.get_columns(tabla)}
        faltantes.extend(
            f"{tabla}.{nombre}"
            for nombre in sorted(requeridas - existentes)
        )
    if faltantes:
        raise RuntimeError(
            "El esquema de la base de datos está desactualizado. "
            "Aplique las migraciones pendientes en 05_BASE_DATOS antes de cargar "
            "la semilla. Columnas faltantes: "
            + ", ".join(faltantes)
        )


def _crear_maestros(db: Session) -> Dict[str, Any]:
    roles_data = (
        ("ADMIN", "Administrador General", "Administración integral del SGI-ERP."),
        ("JEFE_ING", "Jefe de Ingeniería", "Supervisión de diseño, asignación de OPs y liberación técnica."),
        ("VENTAS", "Ventas", "Gestión de clientes y pedidos comerciales."),
        ("DISENO", "Dibujante", "Planos, especificaciones y ejecución de diseño técnico."),
        ("ALMACEN", "Almacén y Compras", "Recepción, inventarios, requisiciones y despachos."),
        ("PRODUCCION", "Líder de Producción", "Programación de planta y ejecución MES."),
        ("CALIDAD", "Calidad", "Inspección, metrología y acciones correctivas."),
        ("MANTENIMIENTO", "Mantenimiento de Planta", "Gestión de equipos y órdenes de mantenimiento."),
        ("OPERARIO", "Operario CNC", "Ejecución de mecanizados y reporte de tiempos."),
    )
    roles = {
        codigo: _upsert(
            db,
            Rol,
            ("id_rol",),
            {"id_rol": codigo, "nombre_rol": nombre, "descripcion": descripcion},
        )
        for codigo, nombre, descripcion in roles_data
    }

    password = "123456"
    usuarios_data = (
        ("admin@sgi.com", "Administrador SGI", "ADMIN"),
        ("jefe_diseno@sgi.local", "Roberto Méndez - Jefe Diseño", "JEFE_ING"),
        ("dibujante_1@sgi.local", "Carlos Ruiz - Dibujante 1", "DISENO"),
        ("dibujante_2@sgi.local", "Ana María Silva - Dibujante 2", "DISENO"),
        ("lider_produccion@sgi.local", "Jorge Méndez - Líder Prod", "PRODUCCION"),
        ("operario_1@sgi.local", "Luis Pérez - Operario 1", "OPERARIO"),
        ("ventas@sgi.local", "Laura Gómez - Ventas", "VENTAS"),
        ("almacen@sgi.local", "Andrés Torres - Almacén", "ALMACEN"),
        ("calidad@sgi.local", "Paula Rojas - Calidad", "CALIDAD"),
        ("mantenimiento@sgi.local", "Diego Castro - Mantenimiento", "MANTENIMIENTO"),
    )
    usuarios = {}
    for email, nombre, rol in usuarios_data:
        usuario = _upsert(
            db,
            Usuario,
            ("email",),
            {
                "email": email,
                "password_hash": get_password_hash(password),
                "nombre_completo": nombre,
                "id_rol": roles[rol].id_rol,
                "activo": True,
            },
        )
        usuarios[email] = usuario


    # Mapeo auxiliar para acceso rápido por rol en el resto del script
    rol_user_map = {
        "ADMIN": usuarios["admin@sgi.com"],
        "JEFE_ING": usuarios["jefe_diseno@sgi.local"],
        "DIBUJANTE1": usuarios["dibujante_1@sgi.local"],
        "DIBUJANTE2": usuarios["dibujante_2@sgi.local"],
        "PRODUCCION": usuarios["lider_produccion@sgi.local"],
        "OPERARIO": usuarios["operario_1@sgi.local"],
        "VENTAS": usuarios["ventas@sgi.local"],
        "ALMACEN": usuarios["almacen@sgi.local"],
        "CALIDAD": usuarios["calidad@sgi.local"],
        "MANTENIMIENTO": usuarios["mantenimiento@sgi.local"],
    }


    personal_data = (
        ("10000001", "Laura Gómez", "Ejecutiva comercial", "VENTAS", "VENTAS", Decimal("42000")),
        ("10000002", "Carlos Ruiz", "Dibujante Mecánico 1", "DISENO", "DISENO", Decimal("52000")),
        ("10000003", "Andrés Torres", "Coordinador de almacén", "ALMACEN", "ALMACEN", Decimal("36000")),
        ("10000004", "Jorge Méndez", "Líder de producción", "PRODUCCION", "PRODUCCION", Decimal("48000")),
        ("10000005", "Paula Rojas", "Inspectora de calidad", "CALIDAD", "CALIDAD", Decimal("45000")),
        ("10000006", "Diego Castro", "Técnico de mantenimiento", "ADMINISTRACION", "MANTENIMIENTO", Decimal("40000")),
        ("10000007", "Ana María Silva", "Dibujante Mecánico 2", "DISENO", "DISENO", Decimal("51000")),
        ("10000008", "Roberto Méndez", "Jefe de Ingeniería", "DISENO", "JEFE_ING", Decimal("65000")),
    )
    for cedula, nombre, cargo, area, rol, tarifa in personal_data:
        trabajador = _upsert(
            db,
            TrabajadorUsuario,
            ("cedula",),
            {
                "cedula": cedula,
                "nombre_completo": nombre,
                "cargo": cargo,
                "area": area,
                "tarifa_hora_mano_obra": tarifa,
                "id_usuario_sistema": rol_user_map[rol].id_usuario if rol in rol_user_map else None,
            },
        )
        _upsert(
            db,
            Empleado,
            ("id_empleado",),
            {
                "id_empleado": cedula,
                "nombre_completo": nombre,
                "cargo": cargo,
                "area": area,
            },
        )

    estructura_data = (
        (TipoEstructuraFinancieraEnum.CUENTA_CONTABLE, "1", "Activos", "Clase de cuentas de activo.", None),
        (TipoEstructuraFinancieraEnum.CUENTA_CONTABLE, "14", "Inventarios", "Inventarios de materias primas e insumos.", "1"),
        (TipoEstructuraFinancieraEnum.CUENTA_CONTABLE, "143505", "Inventario de materia prima", "Aceros, bronces y materiales directos.", "14"),
        (TipoEstructuraFinancieraEnum.CUENTA_CONTABLE, "143510", "Inventario de herramientas", "Herramientas y consumibles de planta.", "14"),
        (TipoEstructuraFinancieraEnum.CUENTA_CONTABLE, "220505", "Proveedores nacionales", "Obligaciones por pagar a proveedores.", None),
        (TipoEstructuraFinancieraEnum.CUENTA_CONTABLE, "510506", "Consumo de insumos", "Costo de materiales e insumos consumidos.", None),
        (TipoEstructuraFinancieraEnum.CENTRO_COSTO, "CC-100-MECANIZADO", "Mecanizado", "Tornos, fresadoras y centros CNC.", None),
        (TipoEstructuraFinancieraEnum.CENTRO_COSTO, "CC-200-METALISTERIA", "Metalistería", "Corte, armado, soldadura y acabado.", None),
        (TipoEstructuraFinancieraEnum.CENTRO_COSTO, "CC-300-SERVICIOS", "Servicios de planta", "Servicios internos y tratamientos externos.", None),
        (TipoEstructuraFinancieraEnum.UNIDAD_NEGOCIO, "UN-PLANTA", "Planta de producción", "Unidad de negocio de fabricación.", None),
    )
    for tipo, codigo, nombre, descripcion, padre in estructura_data:
        _upsert(
            db,
            EstructuraFinanciera,
            ("codigo",),
            {
                "tipo": tipo,
                "codigo": codigo,
                "nombre": nombre,
                "descripcion": descripcion,
                "cuenta_padre": padre,
                "activo": True,
            },
        )

    unidades = (
        ("KG", "Kilogramo", "kg"),
        ("M", "Metro", "m"),
        ("MM", "Milímetro", "mm"),
        ("UND", "Unidad", "und"),
    )
    for codigo, nombre, simbolo in unidades:
        _upsert(
            db,
            UnidadMedida,
            ("codigo",),
            {"codigo": codigo, "nombre": nombre, "simbolo": simbolo, "activo": True},
        )

    categorias = (
        ("MATERIA_PRIMA", "Materia prima", "🧱"),
        ("SEMIELABORADOS", "Semielaborados", "🧩"),
        ("PRODUCTO_TERMINADO", "Producto terminado", "📦"),
        ("HERRAMIENTAS_CNC", "Herramientas CNC", "⚙"),
        ("CONSUMIBLES", "Consumibles", "🧰"),
        ("EPP", "Elementos de protección personal", "🦺"),
        ("REPUESTOS", "Repuestos de máquina", "🔩"),
    )
    for codigo, nombre, icono in categorias:
        _upsert(
            db,
            CategoriaInventario,
            ("codigo",),
            {
                "codigo": codigo,
                "nombre": nombre,
                "icono": icono,
                "descripcion": f"Catálogo base de {nombre.lower()}.",
                "es_personalizada": False,
            },
        )

    socios_data = (
        {
            "nit_cedula": "800123456-1",
            "razon_social": "Ecopetrol S.A.",
            "es_cliente": True,
            "es_proveedor": False,
            "email": "compras@ecopetrol.example",
            "condiciones_pago_dias": 30,
            "cuenta_contable_por_cobrar": "130505 - Clientes nacionales",
        },
        {
            "nit_cedula": "900987654-3",
            "razon_social": "Aceros e Importaciones del Llano S.A.S.",
            "es_cliente": False,
            "es_proveedor": True,
            "email": "ventas@acerosllano.example",
            "condiciones_pago_dias": 60,
            "cuenta_contable_por_pagar": "220505 - Proveedores nacionales",
        },
        {
            "nit_cedula": "901555777-2",
            "razon_social": "Tratamientos Térmicos Andinos S.A.S.",
            "es_cliente": False,
            "es_proveedor": True,
            "email": "servicio@tratamientosandinos.example",
            "condiciones_pago_dias": 30,
            "cuenta_contable_por_pagar": "220505 - Proveedores nacionales",
        },
        {
            "nit_cedula": "901111222-3",
            "razon_social": "Integración Industrial del Centro S.A.S.",
            "es_cliente": True,
            "es_proveedor": True,
            "email": "contacto@integracioncentro.example",
            "condiciones_pago_dias": 45,
            "cuenta_contable_por_cobrar": "130505 - Clientes nacionales",
            "cuenta_contable_por_pagar": "220505 - Proveedores nacionales",
        },
    )
    socios = {}
    for socio_data in socios_data:
        socios[socio_data["nit_cedula"]] = _upsert(
            db,
            SocioNegocio,
            ("nit_cedula",),
            {
                "direccion": "Zona Industrial, Colombia",
                "telefono": "+57 601 555 0101",
                "estado_activo": True,
                **socio_data,
            },
        )

    clientes_data = (
        ("800123456-1", "Ecopetrol S.A.", "Juan Pérez", "juan.perez@ecopetrol.example"),
        ("901111222-3", "Integración Industrial del Centro S.A.S.", "María López", "maria.lopez@integracioncentro.example"),
    )
    clientes = {}
    for nit, nombre, contacto, email in clientes_data:
        clientes[nit] = _upsert(
            db,
            Cliente,
            ("nit_rut",),
            {
                "nit_rut": nit,
                "razon_social": nombre,
                "contacto": contacto,
                "email_contacto": email,
                "telefono": "+57 310 555 0101",
            },
        )

    return {"roles": roles, "usuarios": usuarios, "socios": socios, "clientes": clientes}


def _crear_planta(db: Session) -> Dict[str, Any]:
    centros = {}
    centros_data = (
        ("CC-100-MECANIZADO", Decimal("72000"), Decimal("54000"), Decimal("8"), "MECANIZADO"),
        ("CC-200-METALISTERIA", Decimal("58000"), Decimal("44000"), Decimal("8"), "METALISTERIA"),
        ("CC-300-SERVICIOS", Decimal("50000"), Decimal("40000"), Decimal("8"), "SERVICIOS"),
    )
    for codigo, tarifa, setup, capacidad, equivalencia in centros_data:
        centros[codigo] = _upsert(
            db,
            CentroTrabajo,
            ("codigo_centro",),
            {
                "codigo_centro": codigo,
                "tarifa_hora_mecanizado": tarifa,
                "tarifa_hora_setup": setup,
                "horas_capacidad_turno": capacidad,
                "equivalencia": equivalencia,
                "activo": True,
            },
        )

    centro_almacen = _upsert(
        db,
        CentroAlmacen,
        ("codigo_centro",),
        {
            "codigo_centro": "CENTRO-01-FUNZA",
            "nombre_centro": "Planta Funza",
            "almacenes": [
                "BOD-MP-01",
                "BOD-MP-02",
                "BOD-HERR-02",
                "BOD-CUARENTENA-QM",
                "BOD-RETALES",
            ],
            "activo": True,
        },
    )
    equipos_data = (
        ("TORN-CNC-01", "Torno CNC Doosan Puma 3100", "CC-100-MECANIZADO", Decimal("1280.5"), "OPERATIVA"),
        ("FRES-CNC-02", "Centro de mecanizado Haas VF-4", "CC-100-MECANIZADO", Decimal("964.0"), "OPERATIVA"),
        ("SOLD-MIG-01", "Estación de soldadura MIG", "CC-200-METALISTERIA", Decimal("612.0"), "OPERATIVA"),
        ("SERV-HT-01", "Control de tratamientos térmicos", "CC-300-SERVICIOS", Decimal("220.0"), "OPERATIVA"),
    )
    equipos = {}
    for codigo, nombre, centro, horas, estado in equipos_data:
        equipos[codigo] = _upsert(
            db,
            EquipoPlanta,
            ("codigo_maquina",),
            {
                "codigo_maquina": codigo,
                "nombre": nombre,
                "centro_trabajo_asociado": centro,
                "horas_uso_acumuladas": horas,
                "estado_maquina": estado,
            },
        )
        _upsert(
            db,
            Maquina,
            ("id_maquina",),
            {
                "id_maquina": codigo,
                "nombre_maquina": nombre,
                "tipo_maquina": centro,
                "estado": estado,
            },
        )

    return {
        "centros_trabajo": centros,
        "centro_almacen": centro_almacen,
        "equipos": equipos,
    }


def _crear_inventario(db: Session, centro_almacen: CentroAlmacen) -> Dict[str, Any]:
    articulos_data = (
        {
            "sku": "MP-A105-014",
            "nombre": "Barra de acero ASTM A105 Ø14",
            "descripcion": "Acero al carbono para bridas de proceso.",
            "categoria": "MATERIA_PRIMA",
            "sap_tipo": TipoMaterialSAP.ROH,
            "unidad": "KG",
            "costo": Decimal("18500"),
            "stock": 320.0,
            "minimo": 80.0,
            "almacen": "BOD-MP-01",
            "lote": "LOT-A105-2026-001",
            "colada": "HEAT-A105-77821",
            "calidad": "LIBERADO",
        },
        {
            "sku": "MP-316L-020",
            "nombre": "Platina acero inoxidable 316L",
            "descripcion": "Platina inoxidable para fabricación industrial.",
            "categoria": "MATERIA_PRIMA",
            "sap_tipo": TipoMaterialSAP.ROH,
            "unidad": "KG",
            "costo": Decimal("32700"),
            "stock": 145.0,
            "minimo": 60.0,
            "almacen": "BOD-CUARENTENA-QM",
            "lote": "LOT-316L-2026-002",
            "colada": "HEAT-316L-11990",
            "calidad": "CUARENTENA",
        },
        {
            "sku": "HERR-INS-008",
            "nombre": "Inserto de torneado CNMG",
            "descripcion": "Inserto de carburo para operaciones de torneado.",
            "categoria": "HERRAMIENTAS_CNC",
            "sap_tipo": TipoMaterialSAP.ERSA,
            "unidad": "UND",
            "costo": Decimal("28500"),
            "stock": 24.0,
            "minimo": 10.0,
            "almacen": "BOD-HERR-02",
            "lote": "LOT-CNMG-2026-003",
            "colada": None,
            "calidad": "LIBERADO",
        },
        {
            "sku": "CON-SOLD-001",
            "nombre": "Alambre de soldadura ER70S-6",
            "descripcion": "Alambre sólido para soldadura de acero al carbono.",
            "categoria": "CONSUMIBLES",
            "sap_tipo": TipoMaterialSAP.VERB,
            "unidad": "KG",
            "costo": Decimal("12500"),
            "stock": 78.0,
            "minimo": 25.0,
            "almacen": "BOD-MP-01",
            "lote": "LOT-ER70-2026-004",
            "colada": None,
            "calidad": "LIBERADO",
        },
        {
            "sku": "REP-ROD-030",
            "nombre": "Rodamiento de husillo 6308",
            "descripcion": "Repuesto para mantenimiento de equipo de planta.",
            "categoria": "REPUESTOS",
            "sap_tipo": TipoMaterialSAP.ERSA,
            "unidad": "UND",
            "costo": Decimal("96500"),
            "stock": 2.0,
            "minimo": 3.0,
            "almacen": "BOD-HERR-02",
            "lote": "LOT-6308-2026-005",
            "colada": None,
            "calidad": "LIBERADO",
        },
        {
            "sku": "PROD-BR-12",
            "nombre": "Brida forjada 12 ANSI 600",
            "descripcion": "Producto terminado según plano PLN-PED-088-A.",
            "categoria": "PRODUCTO_TERMINADO",
            "sap_tipo": TipoMaterialSAP.FERT,
            "unidad": "UND",
            "costo": Decimal("245000"),
            "stock": 2.0,
            "minimo": 0.0,
            "almacen": "BOD-MP-01",
            "lote": "LOT-BR12-2026-006",
            "colada": "HEAT-A105-77821",
            "calidad": "LIBERADO",
        },
        {
            "sku": "SEM-BR-12-01",
            "nombre": "Brida mecanizada en proceso",
            "descripcion": "Semielaborado pendiente de inspección final.",
            "categoria": "SEMIELABORADOS",
            "sap_tipo": TipoMaterialSAP.HALB,
            "unidad": "UND",
            "costo": Decimal("198000"),
            "stock": 3.0,
            "minimo": 1.0,
            "almacen": "BOD-MP-01",
            "lote": "LOT-HALB-2026-007",
            "colada": "HEAT-A105-77821",
            "calidad": "LIBERADO",
        },
        {
            "sku": "EPP-GAFAS-001",
            "nombre": "Gafas de seguridad industrial",
            "descripcion": "Elemento de protección ocular para personal de planta.",
            "categoria": "EPP",
            "sap_tipo": TipoMaterialSAP.VERB,
            "unidad": "UND",
            "costo": Decimal("18500"),
            "stock": 18.0,
            "minimo": 6.0,
            "almacen": "BOD-HERR-02",
            "lote": "LOT-EPP-2026-008",
            "colada": None,
            "calidad": "LIBERADO",
        },
        {
            "sku": "MP-316L-RECHAZADO",
            "nombre": "Recorte de platina 316L no conforme",
            "descripcion": "Material retenido y dado de baja tras inspección de recepción.",
            "categoria": "MATERIA_PRIMA",
            "sap_tipo": TipoMaterialSAP.ROH,
            "unidad": "KG",
            "costo": Decimal("32700"),
            "stock": 1.0,
            "minimo": 0.0,
            "almacen": "BOD-CUARENTENA-QM",
            "lote": "LOT-316L-RECHAZADO-009",
            "colada": "HEAT-316L-RECHAZADO-009",
            "calidad": "RECHAZADO",
        },
    )
    catalogos = {}
    lotes = {}
    articulos = {}
    for item in articulos_data:
        articulo = _upsert(
            db,
            ArticuloInventario,
            ("codigo_sku",),
            {
                "codigo_sku": item["sku"],
                "nombre": item["nombre"],
                "descripcion": item["descripcion"],
                "categoria": item["categoria"],
                "tipo_inventario": item["sap_tipo"].value,
                "unidad_medida": item["unidad"],
                "stock_actual": item["stock"],
                "stock_reservado": 0.0,
                "costo_unitario": item["costo"],
                "metodo_valoracion": "PROMEDIO",
                "stock_minimo": item["minimo"],
                "ubicacion": item["almacen"],
            },
        )
        articulos[item["sku"]] = articulo
        catalogo = _upsert(
            db,
            CatalogoMaterialSAP,
            ("sku_codigo",),
            {
                "id_articulo": articulo.id_articulo,
                "sku_codigo": item["sku"],
                "descripcion_tecnica": item["descripcion"],
                "tipo_material_sap": item["sap_tipo"],
                "unidad_medida": item["unidad"],
                "clase_valoracion": "3000-MP" if item["sap_tipo"] == TipoMaterialSAP.ROH else "4000-CONSUMIBLES",
                "cuenta_contable_activo": "143505 - Inventario materia prima",
                "cuenta_contable_gasto": "510506 - Consumo de insumos",
                "cuenta_contable_transitoria": "220505 - Recepción de facturas por conciliar",
                "centro_costo_defecto": (
                    "CC-200-METALISTERIA"
                    if item["sap_tipo"] == TipoMaterialSAP.VERB
                    else "CC-100-MECANIZADO"
                ),
                "metodo_valoracion": MetodoValoracionSAP.CPP,
                "precio_unitario_valorado": item["costo"],
                "stock_seguridad": item["minimo"],
                "punto_reorden": item["minimo"],
                "codigo_centro": centro_almacen.codigo_centro,
                "almacen_fisico": item["almacen"],
            },
        )
        catalogos[item["sku"]] = catalogo

        lote = _upsert(
            db,
            LoteMaterial,
            ("codigo_lote",),
            {
                "codigo_lote": item["lote"],
                "codigo_material": item["sku"],
                "codigo_centro": centro_almacen.codigo_centro,
                "almacen_fisico": item["almacen"],
                "numero_colada": item["colada"],
                "stock_disponible": item["stock"],
                "stock_reservado": 0.0,
                "costo_unitario": item["costo"],
                "inspeccionado_calidad": item["calidad"] == "LIBERADO",
                "estado_calidad": item["calidad"],
                "certificado_calidad_url": (
                    f"/static/certificados/{item['lote']}.pdf"
                    if item["colada"]
                    else None
                ),
            },
        )
        lotes[item["sku"]] = lote
        _insertar_movimiento_si_no_existe(
            db,
            MovimientoInventario,
            ("referencia_tipo", "referencia_id"),
            {
                "id_articulo": articulo.id_articulo,
                "id_lote": lote.id,
                "tipo_movimiento": "101",
                "cantidad": item["stock"],
                "costo_unitario": item["costo"],
                "valor_total": Decimal(str(item["stock"])) * item["costo"],
                "saldo_cantidad": item["stock"],
                "referencia_tipo": "SEMILLA_RECEPCION",
                "referencia_id": item["lote"],
                "documento_externo": f"OC-SEED-{item['lote']}",
                "proveedor": "Aceros e Importaciones del Llano S.A.S.",
                "registrado_por": "semilla@sgi.local",
                "creado_en": datetime(2026, 10, 1, 9, 0),
            },
        )
        _registrar_movimiento_kardex(
            db,
            f"SEED-101-{item['lote']}",
            ClaseMovimientoSAP.ENTRADA_COMPRA_101,
            catalogo,
            Decimal(str(item["stock"])),
            None,
            item["almacen"],
            catalogo.cuenta_contable_activo,
            "220505 - Recepción de facturas por conciliar",
            f"OC-SEED-{item['lote']}",
            datetime(2026, 10, 1, 9, 0),
        )
        if item["calidad"] == "RECHAZADO":
            articulo.stock_actual = 0
            lote.stock_disponible = 0
            _insertar_movimiento_si_no_existe(
                db,
                MovimientoInventario,
                ("referencia_tipo", "referencia_id"),
                {
                    "id_articulo": articulo.id_articulo,
                    "id_lote": lote.id,
                    "tipo_movimiento": "551",
                    "cantidad": item["stock"],
                    "costo_unitario": item["costo"],
                    "valor_total": Decimal(str(item["stock"])) * item["costo"],
                    "saldo_cantidad": 0,
                    "referencia_tipo": "SEMILLA_RECHAZO_QM",
                    "referencia_id": item["lote"],
                    "destino": "BAJA_CALIDAD",
                    "registrado_por": "calidad@sgi.local",
                    "creado_en": datetime(2026, 10, 2, 11, 0),
                },
            )
            _registrar_movimiento_kardex(
                db,
                f"SEED-551-{item['lote']}",
                ClaseMovimientoSAP.SCRAP_551,
                catalogo,
                Decimal(str(item["stock"])),
                item["almacen"],
                None,
                "519595 - Pérdida por material rechazado",
                catalogo.cuenta_contable_activo,
                f"INSPECCION-SEED-{item['lote']}",
                datetime(2026, 10, 2, 11, 0),
            )
        if item["colada"]:
            _upsert(
                db,
                RegistroCalidadLote,
                ("id_lote",),
                {
                    "id_lote": lote.id,
                    "estado_anterior": None,
                    "estado_nuevo": item["calidad"],
                    "motivo": (
                        "Ingreso de muestra con trazabilidad de certificado de colada."
                        if item["calidad"] == "LIBERADO"
                        else "Pendiente de revisión del certificado y ensayos de recepción."
                    ),
                    "registrado_por": "calidad@sgi.local",
                },
            )

    retales_data = (
        ("RET-A105-001", "MP-A105-014", "Remanente de barra ASTM A105", "Ø14 mm x 680 mm", "KG", 7.5),
        ("RET-316L-002", "MP-316L-020", "Sobrante de platina 316L", "12 mm x 90 mm x 420 mm", "UND", 1.0),
    )
    for codigo, material, descripcion, dimensiones, unidad, cantidad in retales_data:
        _upsert(
            db,
            RetalSobrante,
            ("codigo_retal",),
            {
                "codigo_retal": codigo,
                "codigo_material": material,
                "descripcion": descripcion,
                "dimensiones": dimensiones,
                "unidad_medida": unidad,
                "cantidad_disponible": cantidad,
                "cantidad_reservada": 0.0,
                "reutilizable": True,
            },
        )
    return {"articulos": articulos, "catalogos": catalogos, "lotes": lotes}


def _crear_proyectos_y_produccion(
    db: Session,
    maestros: Dict[str, Any],
) -> Dict[str, Any]:
    pedidos_data = (
        {
            "numero_pedido": "PED-2026-088",
            "codigo_proyecto": "PED-2026-088",
            "nit_cliente": "800123456-1",
            "contacto": "Juan Pérez",
            "contacto_email": "juan.perez@ecopetrol.example",
            "descripcion": "Bridas forjadas 12 pulgadas ANSI 600",
            "tipo": "MECANIZADOS",
            "codigo_op": "4007256",
            "codigo_plano": "PLN-PED-088-A",
            "codigo_producto": "PROD-BR-12",
            "nombre_proceso": "Torneado y refrentado",
            "unidad_planta": TipoUnidadPlantaEnum.MECANIZADOS,
            "centro_trabajo": "CC-100-MECANIZADO",
            "maquina": "TORN-CNC-01",
            "cantidad": 10,
            "precio": Decimal("5200000"),
            "fecha": date(2026, 11, 15),
        },
        {
            "numero_pedido": "PED-2026-091",
            "codigo_proyecto": "PED-2026-091",
            "nit_cliente": "901111222-3",
            "contacto": "María López",
            "contacto_email": "maria.lopez@integracioncentro.example",
            "descripcion": "Bastidor industrial soldado",
            "tipo": "METALISTERIA",
            "codigo_op": "1007257",
            "codigo_plano": "PLN-PED-091-M",
            "codigo_producto": "BAST-IND-01",
            "nombre_proceso": "Corte, armado y soldadura MIG",
            "unidad_planta": TipoUnidadPlantaEnum.METALISTERIA,
            "centro_trabajo": "CC-200-METALISTERIA",
            "maquina": "SOLD-MIG-01",
            "cantidad": 4,
            "precio": Decimal("3600000"),
            "fecha": date(2026, 11, 20),
        },
        {
            "numero_pedido": "PED-2026-095",
            "codigo_proyecto": "PED-2026-095",
            "nit_cliente": "800123456-1",
            "contacto": "Juan Pérez",
            "contacto_email": "juan.perez@ecopetrol.example",
            "descripcion": "Tratamiento térmico y ensayo de dureza",
            "tipo": "SERVICIOS",
            "codigo_op": "3007258",
            "codigo_plano": "PLN-PED-095-S",
            "codigo_producto": "SERV-HT-01",
            "nombre_proceso": "Tratamiento térmico y verificación",
            "unidad_planta": TipoUnidadPlantaEnum.SERVICIOS,
            "centro_trabajo": "CC-300-SERVICIOS",
            "maquina": "SERV-HT-01",
            "cantidad": 2,
            "precio": Decimal("950000"),
            "fecha": date(2026, 11, 25),
        },
        {
            "numero_pedido": "PED-2026-099",
            "codigo_proyecto": "PED-2026-099",
            "nit_cliente": "901111222-3",
            "contacto": "María López",
            "contacto_email": "maria.lopez@integracioncentro.example",
            "descripcion": "Eje de transmisión para equipo industrial",
            "tipo": "MECANIZADOS",
            "codigo_op": "4007259",
            "codigo_plano": "PLN-PED-099-A",
            "codigo_producto": "EJE-TR-099",
            "nombre_proceso": "Torneado de precisión",
            "unidad_planta": TipoUnidadPlantaEnum.MECANIZADOS,
            "centro_trabajo": "CC-100-MECANIZADO",
            "maquina": "TORN-CNC-01",
            "cantidad": 6,
            "precio": Decimal("2850000"),
            "fecha": date(2026, 11, 30),
        },
    )
    pedidos_data = pedidos_data + (
        {
            "numero_pedido": "PED-2026-101",
            "codigo_proyecto": "PED-2026-101",
            "nit_cliente": "800123456-1",
            "contacto": "Juan Pérez",
            "contacto_email": "juan.perez@ecopetrol.example",
            "descripcion": "Eje de transmisión mecanizado y liberado",
            "tipo": "MECANIZADOS",
            "codigo_op": "4007260",
            "codigo_plano": "PLN-PED-101-A",
            "codigo_producto": "EJE-TR-101",
            "nombre_proceso": "Torneado de acabado y control dimensional",
            "unidad_planta": TipoUnidadPlantaEnum.MECANIZADOS,
            "centro_trabajo": "CC-100-MECANIZADO",
            "maquina": "TORN-CNC-01",
            "cantidad": 3,
            "precio": Decimal("1450000"),
            "fecha": date(2026, 11, 30),
        },
    ) + tuple(
        {
            "numero_pedido": f"PED-2026-DEMO-{indice:04d}",
            "codigo_proyecto": f"PED-2026-DEMO-{indice:04d}",
            "nit_cliente": "800123456-1" if indice % 2 else "901111222-3",
            "contacto": "Juan Pérez" if indice % 2 else "María López",
            "contacto_email": (
                "juan.perez@ecopetrol.example"
                if indice % 2
                else "maria.lopez@integracioncentro.example"
            ),
            "descripcion": f"Componente industrial de fabricación programada {indice:04d}",
            "tipo": "MECANIZADOS" if indice % 3 else "METALISTERIA",
            "codigo_op": f"410{indice:04d}",
            "codigo_plano": f"PLN-DEMO-{indice:04d}",
            "codigo_producto": f"COMP-DEMO-{indice:04d}",
            "nombre_proceso": (
                "Torneado CNC de componente"
                if indice % 3
                else "Corte y soldadura de componente"
            ),
            "unidad_planta": (
                TipoUnidadPlantaEnum.MECANIZADOS
                if indice % 3
                else TipoUnidadPlantaEnum.METALISTERIA
            ),
            "centro_trabajo": (
                "CC-100-MECANIZADO"
                if indice % 3
                else "CC-200-METALISTERIA"
            ),
            "maquina": "TORN-CNC-01" if indice % 3 else "SOLD-MIG-01",
            "cantidad": 2 + indice % 9,
            "precio": Decimal(str(1_200_000 + indice * 1_000)),
            "fecha": date(2026, 11, 1 + indice % 28),
            "estado_sublote": EstadoOperacionEnum.EN_COLA,
            "registrar_tiempo_mes": False,
        }
        for indice in range(1, 401)
    )
    proyectos = {}
    planos = {}
    ordenes = {}
    operaciones = {}
    sublotes = {}
    for item in pedidos_data:
        cliente = maestros["clientes"][item["nit_cliente"]]
        proyecto = _upsert(
            db,
            Proyecto,
            ("numero_pedido",),
            {
                "id_cliente": cliente.id_cliente,
                "numero_pedido": item["numero_pedido"],
                "codigo_proyecto": item["codigo_proyecto"],
                "cliente_nombre": cliente.razon_social,
                "contacto_nombre": item["contacto"],
                "contacto_telefono": "+57 310 555 0101",
                "contacto_email": item["contacto_email"],
                "ubicacion_cliente": "Colombia",
                "cantidad": item["cantidad"],
                "detalle_producto": item["descripcion"],
                "requisitos_cliente": (
                    "Trazabilidad dimensional, inspección final y documentación de calidad."
                ),
                "fecha_compromiso": item["fecha"],
                "cotizacion_total": item["precio"],
                "presupuestos_componentes": (
                    [
                        {
                            "categoria": "MATERIA_PRIMA",
                            "referencia": "MP-A105-014",
                            "monto_presupuestado": 30000,
                        },
                        {
                            "categoria": "HORAS_MES",
                            "referencia": "CC-100-MECANIZADO|SETUP",
                            "monto_presupuestado": 25000,
                        },
                        {
                            "categoria": "HORAS_MES",
                            "referencia": "CC-100-MECANIZADO|MECANIZADO",
                            "monto_presupuestado": 150000,
                        },
                        {
                            "categoria": "SERVICIO_EXTERNO",
                            "referencia": (
                                "Metrología y Ensayos Industriales S.A.S.|"
                                "Ensayo no destructivo y certificado dimensional"
                            ),
                            "monto_presupuestado": 175000,
                        },
                    ]
                    if item["codigo_op"] == "4007260"
                    else []
                ),
                "confirmado": True,
            },
        )
        proyectos[item["codigo_op"]] = proyecto
        detalle = _upsert(
            db,
            PedidoDetalle,
            ("pedido_id", "codigo_producto"),
            {
                "pedido_id": proyecto.id_proyecto,
                "codigo_producto": item["codigo_producto"],
                "descripcion": item["descripcion"],
                "tipo": "SERVICIO" if item["tipo"] == "SERVICIOS" else "PIEZA",
                "cantidad_solicitada": item["cantidad"],
                "unidad": "UND",
                "cantidad_asignada": item["cantidad"],
                "cantidad_pendiente": 0,
                "fecha_requerida": item["fecha"],
                "prioridad": "ALTA",
            },
        )

        plano = _upsert(
            db,
            Plano,
            ("codigo_plano",),
            {
                "id_proyecto": proyecto.id_proyecto,
                "codigo_op": item["codigo_op"],
                "codigo_plano": item["codigo_plano"],
                "version": "V-01",
                "dibujante_asignado": "Carlos Ruiz",
                "unidad_planta": item["unidad_planta"].value,
                "estado_diseno": "LIBERADA",
                "material_requerido": item["codigo_producto"],
                "tiempo_estimado_valor": 8 if item["tipo"] != "MECANIZADOS" else 16,
                "tiempo_estimado_unidad": "HORAS",
                "tiempo_estimado_setup_minutos": 30,
                "tiempo_estimado_mecanizado_horas": 6 if item["tipo"] == "MECANIZADOS" else 4,
                "dias_estimados_diseno": 2,
                "fecha_inicio_programada": date(2026, 10, 19),
                "fecha_entrega_cliente": item["fecha"],
                "fecha_entrega_produccion": item["fecha"],
                "archivo_pdf_url": f"/static/planos/{item['codigo_plano']}.pdf",
                "estado": EstadoPlanoEnum.APROBADO,
                "aprobado_por": maestros["usuarios"]["jefe.ing@sgi.local"].nombre_completo,
                "fecha_aprobacion": datetime(2026, 10, 15, 12, 0),
                "creado_por": maestros["usuarios"]["jefe.ing@sgi.local"].id_usuario,
            },
        )


        planos[item["codigo_op"]] = plano
        _upsert(
            db,
            OTDetalle,
            ("detalle_pedido_id", "ot_id"),
            {
                "detalle_pedido_id": detalle.detalle_id,
                "ot_id": plano.id_plano,
                "cantidad_asignada": item["cantidad"],
            },
        )

        orden = _upsert(
            db,
            OrdenProduccion,
            ("codigo_op",),
            {
                "id_proyecto": proyecto.id_proyecto,
                "id_plano": plano.id_plano,
                "codigo_op": item["codigo_op"],
                "cantidad_fabricar": item["cantidad"],
                "estado": (
                    EstadoOPEnum.TERMINADA
                    if item["codigo_op"] == "4007260"
                    else
                    EstadoOPEnum.LISTA_PARA_LIBERAR
                    if item["codigo_op"] == "4007256"
                    else EstadoOPEnum.EN_INSPECCION
                    if item["codigo_op"] == "4007259"
                    else EstadoOPEnum.EN_PRODUCCION
                ),
                "reserva_stock_100": False,
                "porcentaje_avance": 100 if item["codigo_op"] == "4007260" else 20,
                "tiempo_setup_estandar_minutos": 30,
                "observaciones": f"Orden autónoma de planta: {item['tipo']}.",
            },
        )
        ordenes[item["codigo_op"]] = orden

        operacion = _upsert(
            db,
            OperacionOT,
            ("codigo_op", "secuencia_paso"),
            {
                "id_plano": plano.id_plano,
                "codigo_op": item["codigo_op"],
                "codigo_plano": item["codigo_plano"],
                "secuencia_paso": 10,
                "unidad_planta": item["unidad_planta"],
                "nombre_proceso": item["nombre_proceso"],
                "cantidad_total_orden": item["cantidad"],
                "cantidad_acumulada_ok": (
                    item["cantidad"]
                    if item["codigo_op"] == "4007260"
                    else 1 if item["tipo"] == "MECANIZADOS" else 0
                ),
                "estado_operacion": (
                    EstadoOperacionEnum.COMPLETADA
                    if item["codigo_op"] == "4007260"
                    else EstadoOperacionEnum.EN_COLA
                    if item.get("estado_sublote") == EstadoOperacionEnum.EN_COLA
                    else EstadoOperacionEnum.EN_PRODUCCION
                ),
            },
        )
        operaciones[item["codigo_op"]] = operacion
        sublote = _upsert(
            db,
            SubLoteOperacion,
            ("id_operacion", "numero_sublote"),
            {
                "id_operacion": operacion.id_operacion,
                "numero_sublote": "SUB-01",
                "cantidad_asignada": item["cantidad"],
                "operario_id": str(maestros["usuarios"]["PRODUCCION"].id_usuario),
                "operario_nombre": maestros["usuarios"]["PRODUCCION"].nombre_completo,
                "maquina_codigo": item["maquina"],
                "prioridad_cola": 1,
                "estado_sublote": (
                    item.get("estado_sublote")
                    or (
                        EstadoOperacionEnum.COMPLETADA
                        if item["codigo_op"] == "4007260"
                        else EstadoOperacionEnum.EN_PRODUCCION
                    )
                ),
            },
        )
        sublotes[item["codigo_op"]] = sublote
        if item.get("registrar_tiempo_mes", True):
            orden_completada = item["codigo_op"] == "4007260"
            _upsert(
                db,
                RegistroTiempoOperario,
                ("id_sublote", "operario_id"),
                {
                    "id_sublote": sublote.id_sublote,
                    "operario_id": str(maestros["usuarios"]["PRODUCCION"].id_usuario),
                    "maquina_codigo": item["maquina"],
                    "fecha_apertura_setup": datetime(2026, 10, 21, 8, 0),
                    "fecha_inicio_produccion": datetime(2026, 10, 21, 8, 30),
                    "fecha_fin_operacion": datetime(2026, 10, 21, 10, 30),
                    "tiempo_setup_segundos": 1800,
                    "tiempo_produccion_segundos": 7200,
                    "piezas_conformes_ok": item["cantidad"] if orden_completada else 1,
                    "piezas_defectuosas_scrap": 0,
                    "es_entrega_parcial": not orden_completada,
                    "comentarios_operario": (
                        "Orden terminada; tiempos consolidados para liquidación."
                        if orden_completada
                        else "Registro de prueba; el sublote sigue activo."
                    ),
                    "creado_en": datetime(2026, 10, 21, 10, 30),
                },
            )

    notificaciones = (
        ("4007256", "Entrega parcial en torno", "Se reportaron piezas conformes y la operación continúa."),
        ("1007257", "Inicio de fabricación de bastidor", "Sub-lote asignado a la estación de soldadura MIG."),
        ("3007258", "Servicio en ejecución", "Lote enviado a tratamiento térmico y control de dureza."),
    )
    for codigo_op, titulo, mensaje in notificaciones:
        item = next(row for row in pedidos_data if row["codigo_op"] == codigo_op)
        sublote = sublotes[codigo_op]
        _upsert(
            db,
            NotificacionLider,
            ("id_sublote", "titulo"),
            {
                "id_sublote": sublote.id_sublote,
                "unidad_planta": item["unidad_planta"],
                "tipo_notificacion": TipoNotificacionEnum.ENTREGA_PARCIAL,
                "titulo": titulo,
                "mensaje": mensaje,
                "codigo_op": codigo_op,
                "codigo_plano": item["codigo_plano"],
                "operario_nombre": maestros["usuarios"]["PRODUCCION"].nombre_completo,
                "maquina_codigo": item["maquina"],
                "piezas_reportadas": 1,
                "leida": 0,
                "atendida": 0,
            },
        )
    return {
        "proyectos": proyectos,
        "planos": planos,
        "ordenes": ordenes,
        "operaciones": operaciones,
        "sublotes": sublotes,
    }


def _crear_compras_almacen(
    db: Session,
    maestros: Dict[str, Any],
    inventario: Dict[str, Any],
    produccion: Dict[str, Any],
) -> None:
    solicitudes = (
        {
            "numero": "PR-2026-001",
            "codigo_op": "4007256",
            "sku": "MP-A105-014",
            "nombre": "Barra de acero ASTM A105 Ø14",
            "cantidad": 120.0,
            "unidad": "KG",
            "estado": "EN_COMPRA",
            "estado_bom": "EN_COMPRA",
        },
        {
            "numero": "PR-2026-002",
            "codigo_op": "1007257",
            "sku": "CON-SOLD-001",
            "nombre": "Alambre de soldadura ER70S-6",
            "cantidad": 30.0,
            "unidad": "KG",
            "estado": "PENDIENTE",
            "estado_bom": "SOLICITADO",
        },
        {
            "numero": "PR-2026-003",
            "codigo_op": "3007258",
            "sku": "REP-ROD-030",
            "nombre": "Rodamiento de husillo 6308",
            "cantidad": 2.0,
            "unidad": "UND",
            "estado": "EN_COMPRA",
            "estado_bom": "EN_COMPRA",
        },
        {
            "numero": "PR-2026-004",
            "codigo_op": "4007260",
            "sku": "MP-A105-014",
            "nombre": "Barra de acero ASTM A105 Ø14",
            "cantidad": 2.0,
            "unidad": "KG",
            "estado": "ENTREGADA",
            "estado_bom": "ENTREGADO",
        },
    )
    for item in solicitudes:
        orden = produccion["ordenes"][item["codigo_op"]]
        plano = produccion["planos"][item["codigo_op"]]
        _upsert(
            db,
            SolicitudCompra,
            ("numero_solicitud", "codigo_sku"),
            {
                "numero_solicitud": item["numero"],
                "codigo_op": item["codigo_op"],
                "codigo_plano": plano.codigo_plano,
                "numero_pedido": orden.proyecto.numero_pedido,
                "nombre_item": item["nombre"],
                "codigo_sku": item["sku"],
                "categoria": "MATERIA_PRIMA" if item["unidad"] == "KG" else "REPUESTOS",
                "cantidad_solicitada": item["cantidad"],
                "unidad_medida": item["unidad"],
                "estado": item["estado"],
                "estado_bom": item["estado_bom"],
                "proveedor_sugerido": "Aceros e Importaciones del Llano S.A.S.",
                "observaciones": "Solicitud de prueba vinculada a la orden de producción.",
                "id_proyecto": orden.id_proyecto,
                "id_plano": plano.id_plano,
            },
        )

    db.flush()
    despachos_programados = {"4007256": 5.0, "1007257": 3.0, "4007260": 2.0}
    for index, solicitud_data in enumerate(solicitudes, start=1):
        sku = solicitud_data["sku"]
        codigo_op = solicitud_data["codigo_op"]
        cantidad_despachada = despachos_programados.get(codigo_op, 0.0)
        lote = inventario["lotes"][sku]
        articulo = inventario["articulos"][sku]
        if cantidad_despachada <= 0:
            continue
        entrega_existente = db.query(EntregaMaterialOP).filter(
            EntregaMaterialOP.op_id == produccion["ordenes"][codigo_op].id_op,
            EntregaMaterialOP.lote_id == lote.id,
        ).first()
        saldo = max(float(lote.stock_disponible or 0) - cantidad_despachada, 0)
        if cantidad_despachada > float(lote.stock_disponible or 0):
            raise ValueError(f"Stock insuficiente en el lote {lote.codigo_lote} para el despacho de prueba.")
        articulo.stock_actual = max(float(articulo.stock_actual or 0) - cantidad_despachada, 0)
        lote.stock_disponible = saldo
        _upsert(
            db,
            EntregaMaterialOP,
            ("op_id", "lote_id"),
            {
                "op_id": produccion["ordenes"][codigo_op].id_op,
                "lote_id": lote.id,
                "cantidad_entregada": cantidad_despachada,
                "entregado_por": maestros["usuarios"]["ALMACEN"].id_usuario,
                "recibido_por_produccion": maestros["usuarios"]["PRODUCCION"].id_usuario,
                "fecha_entrega": datetime(2026, 10, 20, 10, index),
            },
        )
        if entrega_existente is not None:
            continue
        _insertar_movimiento_si_no_existe(
            db,
            MovimientoInventario,
            ("referencia_tipo", "referencia_id"),
            {
                "id_articulo": articulo.id_articulo,
                "id_lote": lote.id,
                "tipo_movimiento": "261",
                "cantidad": cantidad_despachada,
                "costo_unitario": articulo.costo_unitario,
                "valor_total": Decimal(str(cantidad_despachada)) * articulo.costo_unitario,
                "saldo_cantidad": saldo,
                "referencia_tipo": "SEMILLA_DESPACHO_OP",
                "referencia_id": f"{codigo_op}:{sku}",
                "codigo_op": codigo_op,
                "destino": "PLANTA",
                "registrado_por": maestros["usuarios"]["ALMACEN"].email,
                "creado_en": datetime(2026, 10, 20, 10, index),
            },
        )
        catalogo = inventario["catalogos"][sku]
        _registrar_movimiento_kardex(
            db,
            f"SEED-261-{codigo_op}-{sku}",
            ClaseMovimientoSAP.CONSUMO_OP_261,
            catalogo,
            Decimal(str(cantidad_despachada)),
            "BOD-MP-01",
            None,
            catalogo.cuenta_contable_gasto,
            catalogo.cuenta_contable_activo,
            f"DESPACHO-OP-{codigo_op}",
            datetime(2026, 10, 20, 10, index),
            codigo_op,
        )
        _upsert(
            db,
            ConsumoMaterialOP,
            ("op_id", "codigo_material", "fuente"),
            {
                "op_id": produccion["ordenes"][codigo_op].id_op,
                "codigo_material": sku,
                "descripcion_material": solicitud_data["nombre"],
                "cantidad": cantidad_despachada,
                "unidad_medida": solicitud_data["unidad"],
                "costo_unitario": articulo.costo_unitario,
                "fuente": "KARDEX",
            },
        )

    sku_traslado = "MP-A105-014"
    articulo_traslado = inventario["articulos"][sku_traslado]
    lote_traslado = inventario["lotes"][sku_traslado]
    catalogo_traslado = inventario["catalogos"][sku_traslado]
    _insertar_movimiento_si_no_existe(
        db,
        MovimientoInventario,
        ("referencia_tipo", "referencia_id"),
        {
            "id_articulo": articulo_traslado.id_articulo,
            "id_lote": lote_traslado.id,
            "tipo_movimiento": "311",
            "cantidad": 1.0,
            "costo_unitario": articulo_traslado.costo_unitario,
            "valor_total": articulo_traslado.costo_unitario,
            "saldo_cantidad": lote_traslado.stock_disponible,
            "referencia_tipo": "SEMILLA_TRASLADO",
            "referencia_id": f"{sku_traslado}:BOD-MP-02",
            "destino": "BOD-MP-02",
            "registrado_por": maestros["usuarios"]["ALMACEN"].email,
            "creado_en": datetime(2026, 10, 21, 9, 0),
        },
    )
    _registrar_movimiento_kardex(
        db,
        f"SEED-311-{sku_traslado}",
        ClaseMovimientoSAP.TRASLADO_311,
        catalogo_traslado,
        Decimal("1"),
        "BOD-MP-01",
        "BOD-MP-02",
        catalogo_traslado.cuenta_contable_activo,
        catalogo_traslado.cuenta_contable_activo,
        f"TRASLADO-SEED-{sku_traslado}",
        datetime(2026, 10, 21, 9, 0),
    )

    _upsert(
        db,
        ServicioTerceroOP,
        ("op_id", "numero_factura"),
        {
            "op_id": produccion["ordenes"]["3007258"].id_op,
            "proveedor": "Tratamientos Térmicos Andinos S.A.S.",
            "descripcion": "Tratamiento térmico y ensayo de dureza",
            "numero_factura": "FAC-SEED-2026-003",
            "costo": Decimal("425000"),
        },
    )
    _upsert(
        db,
        ServicioTerceroOP,
        ("op_id", "numero_factura"),
        {
            "op_id": produccion["ordenes"]["4007260"].id_op,
            "proveedor": "Metrología y Ensayos Industriales S.A.S.",
            "descripcion": "Ensayo no destructivo y certificado dimensional",
            "numero_factura": "FAC-SEED-2026-004",
            "costo": Decimal("185000"),
        },
    )


def _crear_calidad_y_mantenimiento(
    db: Session,
    maestros: Dict[str, Any],
    planta: Dict[str, Any],
    produccion: Dict[str, Any],
) -> None:
    for codigo_op, item in (
        ("4007256", ("APROBADO_DESPACHO", "Inspección dimensional inicial conforme.")),
        ("1007257", ("APROBADO_TRATAMIENTO", "Inspección de soldadura previa a acabado.")),
        ("3007258", ("APROBADO_DESPACHO", "Verificación de dureza y certificado del proveedor.")),
    ):
        plano = produccion["planos"][codigo_op]
        _upsert(
            db,
            InspeccionCalidad,
            ("codigo_op", "resultado_inspeccion"),
            {
                "codigo_op": codigo_op,
                "codigo_plano": plano.codigo_plano,
                "inspector_id": maestros["usuarios"]["CALIDAD"].id_usuario,
                "inspector_nombre": maestros["usuarios"]["CALIDAD"].nombre_completo,
                "resultado_inspeccion": item[0],
                "requiere_tratamiento": item[0] == "APROBADO_TRATAMIENTO",
                "descripcion_tratamiento": "Tratamiento térmico de alivio de esfuerzos" if item[0] == "APROBADO_TRATAMIENTO" else None,
                "piezas_enviadas_tratamiento": 1 if item[0] == "APROBADO_TRATAMIENTO" else 0,
                "proveedor_tratamiento_email": "servicio@tratamientosandinos.example" if item[0] == "APROBADO_TRATAMIENTO" else None,
                "proveedor_tratamiento": "Tratamientos Térmicos Andinos S.A.S." if item[0] == "APROBADO_TRATAMIENTO" else None,
                "costo_tratamiento": Decimal("425000") if item[0] == "APROBADO_TRATAMIENTO" else Decimal("0"),
                "mediciones_dimensionales": [
                    {
                        "caracteristica": "Diámetro exterior de control",
                        "nominal": 25.0,
                        "tolerancia_min": 24.98,
                        "tolerancia_max": 25.02,
                        "valor_medido": 25.0,
                        "conforme": True,
                    }
                ],
                "informe_tratamiento_html": (
                    "<!doctype html><html lang='es'><meta charset='utf-8'><title>Informe técnico de tratamiento térmico</title>"
                    "<h1>Informe de servicio térmico</h1><p>Orden: 1007257</p>"
                    "<p>Proceso: Tratamiento térmico de alivio de esfuerzos</p>"
                    "<p>Proveedor: Tratamientos Térmicos Andinos S.A.S.</p></html>"
                ) if item[0] == "APROBADO_TRATAMIENTO" else None,
                "registros_fotograficos": [
                    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/T2sAAAAASUVORK5CYII="
                ],
                "observaciones_inspector": item[1],
                "notificado_jefe_produccion": True,
                "fecha_inspeccion": datetime(2026, 10, 21, 14, 0),
            },
        )

    nc = _upsert(
        db,
        NoConformidad,
        ("codigo_nc",),
        {
            "codigo_nc": "RNC-SEED-2026-001",
            "id_op": produccion["ordenes"]["4007256"].id_op,
            "descripcion": "Certificado de colada recibido pendiente de validación documental.",
            "origen": "RECEPCION_COMPRAS",
            "gravedad": "MENOR",
            "estado": EstadoNCEnum.ACCION_CORRECTIVA,
            "accion_correctiva": "Solicitar y validar el certificado original del proveedor.",
            "analisis_causa_5porques": "La recepción documental se separó de la recepción física.",
            "causa_raiz": "MATERIAL_DEFECTUOSO",
            "piezas_scrap": 0,
            "disposicion": "CUARENTENA",
            "eficacia_verificada": False,
            "reportado_por": maestros["usuarios"]["CALIDAD"].id_usuario,
        },
    )
    _upsert(
        db,
        AccionCAPA,
        ("id_rnc", "accion_correctiva"),
        {
            "id_rnc": nc.id_nc,
            "accion_correctiva": "Implementar lista de verificación de certificados 3.1 en recepción.",
            "responsable_id": maestros["usuarios"]["ALMACEN"].id_usuario,
            "fecha_compromiso": date(2026, 11, 5),
            "estado_cierre": "ABIERTA",
            "evidencia_cierre": None,
        },
    )

    instrumento = _upsert(
        db,
        InstrumentoMedicion,
        ("codigo_equipo",),
        {
            "codigo_equipo": "CAL-MIC-001",
            "nombre": "Micrómetro exterior 0-25 mm",
            "fecha_ultima_calibracion": date(2026, 4, 15),
            "fecha_vencimiento_calibracion": date(2027, 4, 15),
            "estado_disponible": True,
        },
    )
    orden_mecanizado = produccion["ordenes"]["4007256"]
    existe_ficha = db.query(FichaMetrologia).filter(
        FichaMetrologia.op_id == orden_mecanizado.id_op,
        FichaMetrologia.instrumento_id == instrumento.id,
        FichaMetrologia.cota_medida == 25.0,
    ).first()
    if existe_ficha is None:
        db.add(
            crear_instancia_segura(
                FichaMetrologia,
                op_id=orden_mecanizado.id_op,
                instrumento_id=instrumento.id,
                cota_medida=25.0,
                tolerancia_min=24.98,
                tolerancia_max=25.02,
                resultado_conforme=True,
                inspector_id=maestros["usuarios"]["CALIDAD"].id_usuario,
                fecha_inspeccion=datetime(2026, 10, 21, 14, 15),
            )
        )
        db.flush()

    # No need to call _upsert for FichaMetrologia since it was removed from models.py
    for codigo, tipo, descripcion, repuestos, fecha, estado in (
        (
            "OTM-2026-TORNO-001",
            "PREVENTIVO",
            "Inspección de husillo y lubricación programada.",
            [{"codigo_sku": "REP-ROD-030", "nombre_item": "Rodamiento de husillo 6308", "cantidad": 1, "unidad_medida": "UND"}],
            date(2026, 11, 2),
            "ABIERTA",
        ),
        (
            "OTM-2026-FRESA-001",
            "CORRECTIVO",
            "Revisión de presión y sistema de refrigeración.",
            [],
            date(2026, 10, 28),
            "EN_PROCESO",
        ),
    ):
        equipo = planta["equipos"]["TORN-CNC-01" if "TORNO" in codigo else "FRES-CNC-02"]
        orden_mantenimiento = _upsert(
            db,
            OrdenMantenimiento,
            ("codigo_otm",),
            {
                "codigo_otm": codigo,
                "id_equipo": equipo.id_equipo,
                "tipo": tipo,
                "descripcion_falla": descripcion,
                "repuestos_solicitados_almacen": repuestos,
                "fecha_programada": fecha,
                "estado": estado,
            },
        )
        if estado == "EN_PROCESO":
            equipo.estado_maquina = "EN_MANTENIMIENTO"
        for index, repuesto in enumerate(repuestos, start=1):
            _upsert(
                db,
                SolicitudCompra,
                ("numero_solicitud", "codigo_sku"),
                {
                    "numero_solicitud": f"{codigo}-PR-{index:02d}",
                    "nombre_item": repuesto["nombre_item"],
                    "codigo_sku": repuesto["codigo_sku"],
                    "categoria": "REPUESTOS",
                    "cantidad_solicitada": repuesto["cantidad"],
                    "unidad_medida": repuesto["unidad_medida"],
                    "estado": "PENDIENTE",
                    "estado_bom": "SOLICITADO",
                    "observaciones": f"Repuesto vinculado con la orden de mantenimiento {orden_mantenimiento.codigo_otm}.",
                },
            )


def cargar_semilla_db() -> None:
    print("Iniciando carga idempotente de datos de prueba SGI-ERP...")
    Base.metadata.create_all(bind=engine)
    _verificar_migracion_requerida()
    db = SessionLocal()
    try:
        maestros = _crear_maestros(db)
        planta = _crear_planta(db)
        inventario = _crear_inventario(db, planta["centro_almacen"])
        produccion = _crear_proyectos_y_produccion(db, maestros)
        _crear_compras_almacen(db, maestros, inventario, produccion)
        _crear_calidad_y_mantenimiento(db, maestros, planta, produccion)

        # Escenarios de prueba para Diseño MES
        _cargar_escenarios_diseno(db, maestros)

        db.commit()
        print("Semilla SGI-ERP cargada correctamente para todas las áreas.")
        print("Usuarios de prueba: admin@sgi.com, jefe.ing@sgi.local, dibujante1@sgi.local, dibujante2@sgi.local,")
        print("ventas@sgi.local, almacen@sgi.local, produccion@sgi.local, calidad@sgi.local, mantenimiento@sgi.local")
        if os.environ.get("SGI_SEED_PASSWORD"):
            print("Contraseña configurada mediante la variable de entorno SGI_SEED_PASSWORD.")
        else:
            print("Contraseña predeterminada de pruebas: admin123.")
    except Exception as error:
        db.rollback()
        raise RuntimeError(f"No se pudo cargar la semilla SGI-ERP: {error}") from error
    finally:
        db.close()

def _cargar_escenarios_diseno(db: Session, maestros: Dict[str, Any]) -> None:
    from uuid import uuid4
    # Re-mapeo de usuarios para los escenarios
    rol_user_map = {
        "ADMIN": maestros["usuarios"]["admin@sgi.com"],
        "JEFE_ING": maestros["usuarios"]["jefe.ing@sgi.local"],
        "DIBUJANTE1": maestros["usuarios"]["dibujante1@sgi.local"],
        "DIBUJANTE2": maestros["usuarios"]["dibujante2@sgi.local"],
    }

    # 1. OP ASIGNADA: Lista para iniciar trabajo
    op_asignada_cod = "4009001"
    proyecto_asignada = _upsert(Proyecto, ("numero_pedido",), {
        "numero_pedido": "PED-TEST-01", "codigo_proyecto": "PED-TEST-01", "nit_cliente": "800123456-1",
        "cliente_nombre": "Ecopetrol S.A.", "contacto_nombre": "Juan Pérez", "contacto_email": "juan.perez@ecopetrol.example",
        "ubicacion_cliente": "Colombia", "cantidad": 1, "detalle_producto": "Pieza Prueba Asignada",
        "requisitos_cliente": "Prueba de flujo de inicio de trabajo", "fecha_compromiso": date(2026, 12, 1), "confirmado": True
    })
    plano_asignada = _upsert(Plano, ("codigo_plano",), {
        "id_proyecto": proyecto_asignada.id_proyecto, "codigo_op": op_asignada_cod, "codigo_plano": "PLN-TEST-01",
        "version": "V-01", "dibujante_asignado": "Carlos Ruiz", "unidad_planta": "Mecanizados",
        "estado_diseno": "ASIGNADA", "material_requerido": "Acero A105", "fecha_entrega_produccion": date(2026, 12, 1)
    })
    _upsert(OrdenProduccion, ("codigo_op",), {
        "id_proyecto": proyecto_asignada.id_proyecto, "id_plano": plano_asignada.id_plano,
        "codigo_op": op_asignada_cod, "cantidad_fabricar": 1, "estado": EstadoOPEnum.BORRADOR
    })

    # 2. OP EN DISEÑO: Con cronómetro corriendo
    op_en_diseno_cod = "4009002"
    proyecto_diseno = _upsert(Proyecto, ("numero_pedido",), {
        "numero_pedido": "PED-TEST-02", "codigo_proyecto": "PED-TEST-02", "nit_cliente": "800123456-1",
        "cliente_nombre": "Ecopetrol S.A.", "contacto_nombre": "Juan Pérez", "contacto_email": "juan.perez@ecopetrol.example",
        "ubicacion_cliente": "Colombia", "cantidad": 1, "detalle_producto": "Pieza Prueba En Diseño",
        "requisitos_cliente": "Prueba de cronómetro y carga de archivos", "fecha_compromiso": date(2026, 12, 5), "confirmado": True
    })
    plano_diseno = _upsert(Plano, ("codigo_plano",), {
        "id_proyecto": proyecto_diseno.id_proyecto, "codigo_op": op_en_diseno_cod, "codigo_plano": "PLN-TEST-02",
        "version": "V-01", "dibujante_asignado": "Ana María Silva", "unidad_planta": "Mecanizados",
        "estado_diseno": "EN_DISENO", "material_requerido": "Acero 316L", "fecha_inicio_diseno": datetime(2026, 10, 25, 8, 0),
        "fecha_entrega_produccion": date(2026, 12, 5)
    })
    _upsert(OrdenProduccion, ("codigo_op",), {
        "id_proyecto": proyecto_diseno.id_proyecto, "id_plano": plano_diseno.id_plano,
        "codigo_op": op_en_diseno_cod, "cantidad_fabricar": 1, "estado": EstadoOPEnum.BORRADOR
    })

    # 3. OP CON ECR PENDIENTE: Bloqueo de liberación
    op_ecr_cod = "4009003"
    proyecto_ecr = _upsert(Proyecto, ("numero_pedido",), {
        "numero_pedido": "PED-TEST-03", "codigo_proyecto": "PED-TEST-03", "nit_cliente": "800123456-1",
        "cliente_nombre": "Ecopetrol S.A.", "contacto_nombre": "Juan Pérez", "contacto_email": "juan.perez@ecopetrol.example",
        "ubicacion_cliente": "Colombia", "cantidad": 1, "detalle_producto": "Pieza Prueba ECR",
        "requisitos_cliente": "Prueba de bloqueo por ECR", "fecha_compromiso": date(2026, 12, 10), "confirmado": True
    })
    plano_ecr = _upsert(Plano, ("codigo_plano",), {
        "id_proyecto": proyecto_ecr.id_proyecto, "codigo_op": op_ecr_cod, "codigo_plano": "PLN-TEST-03",
        "version": "V-01", "dibujante_asignado": "Carlos Ruiz", "unidad_planta": "Mecanizados",
        "estado_diseno": "EN_DISENO", "material_requerido": "Acero A105", "fecha_inicio_diseno": datetime(2026, 10, 20, 9, 0),
        "fecha_entrega_produccion": date(2026, 12, 10),
        "archivo_pdf_url": "/static/planos/PLN-TEST-03.pdf", "archivo_step_url": "/static/planos/PLN-TEST-03.step", "archivo_dxf_url": "/static/planos/PLN-TEST-03.dxf"
    })
    _upsert(OrdenProduccion, ("codigo_op",), {
        "id_proyecto": proyecto_ecr.id_proyecto, "id_plano": plano_ecr.id_plano,
        "codigo_op": op_ecr_cod, "cantidad_fabricar": 1, "estado": EstadoOPEnum.BORRADOR
    })
    _upsert(SolicitudCambioTecnico, ("id_solicitud",), {
        "id_solicitud": uuid4(), "id_plano": plano_ecr.id_plano, "version_origen": "V-01",
        "descripcion_cambio": "Corregir cota de diámetro en cara A", "cota_afectada": "Ø25.0",
        "tipo_cambio": "CORRECCION", "prioridad": "ALTA", "solicitado_por": rol_user_map["JEFE_ING"].id_usuario,
        "estado_solicitud": "PENDIENTE"
    })

    # 4. OP LISTA PARA LIBERAR: Todos los archivos cargados
    op_lista_cod = "4009004"
    proyecto_lista = _upsert(Proyecto, ("numero_pedido",), {
        "numero_pedido": "PED-TEST-04", "codigo_proyecto": "PED-TEST-04", "nit_cliente": "800123456-1",
        "cliente_nombre": "Ecopetrol S.A.", "contacto_nombre": "Juan Pérez", "contacto_email": "juan.perez@ecopetrol.example",
        "ubicacion_cliente": "Colombia", "cantidad": 1, "detalle_producto": "Pieza Lista Liberar",
        "requisitos_cliente": "Prueba de liberación exitosa", "fecha_compromiso": date(2026, 12, 15), "confirmado": True
    })
    plano_lista = _upsert(Plano, ("codigo_plano",), {
        "id_proyecto": proyecto_lista.id_proyecto, "codigo_op": op_lista_cod, "codigo_plano": "PLN-TEST-04",
        "version": "V-01", "dibujante_asignado": "Ana María Silva", "unidad_planta": "Mecanizados",
        "estado_diseno": "EN_DISENO", "material_requerido": "Acero 316L", "fecha_inicio_diseno": datetime(2026, 10, 24, 10, 0),
        "fecha_entrega_produccion": date(2026, 12, 15),
        "archivo_pdf_url": "/static/planos/PLN-TEST-04.pdf", "archivo_step_url": "/static/planos/PLN-TEST-04.step", "archivo_dxf_url": "/static/planos/PLN-TEST-04.dxf"
    })
    _upsert(OrdenProduccion, ("codigo_op",), {
        "id_proyecto": proyecto_lista.id_proyecto, "id_plano": plano_lista.id_plano,
        "codigo_op": op_lista_cod, "cantidad_fabricar": 1, "estado": EstadoOPEnum.BORRADOR
    })



if __name__ == "__main__":
    cargar_semilla_db()
