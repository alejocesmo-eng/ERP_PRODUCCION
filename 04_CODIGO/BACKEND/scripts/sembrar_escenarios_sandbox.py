"""
Semilla de escenarios de sgi_sandbox (SCRUM-33): los datos de reglas/datos-base-sandbox.md que
el modelo actual puede representar, para el recorrido de reglas/escenarios-prueba.md.

Bloques (en orden de dependencias):
    usuarios_demo          los 16 de usuarios-demo.md (los crea preparar_sandbox; aqui solo se exigen)
    clientes_y_proveedor   3 clientes demo (socios_negocio y su copia en clientes, mismo NIT) y 1 proveedor
    centro_trabajo         CT-DEMO-CNC con tarifas, para la liquidacion de costos (E14)
    materiales_y_stock     materias primas, CC-50 como producto terminado y sus lotes liberados
    productos              SM-100, BT-200, CC-50 y SM-110 (E6)
    planos_pdf_bom         planos aprobados de SM-100 y BT-200 y plano en borrador de SM-110
                           (Mecanizados), PDF con sha256 y BOM
    cotizaciones           COT-DEMO-001 a 006 y 008 emitidas; todas con pedido salvo COT-DEMO-006 (E20)
    pedidos                PED-DEMO-001 a 005 y 008 desde su cotizacion y PED-DEMO-006/007 sin cotizacion (E21)
    ordenes_produccion     OP-DEMO-001 (SM-100 liberada), 002 (BT-200 sin liberar), 003 (SM-110 sin
                           plano aprobado, E6) y 004 (terminada)
    compras_y_entregas     solicitudes de compra radicadas y entregas a la OP (BT-200 al 60 %)
    costos_op              consumos, tiempos y temple de OP-DEMO-001 (E14)
    picking                orden de picking de la linea de stock de PED-DEMO-003 (E16)

Pendiente (no se inventa; ver PENDIENTES): lo que depende de los pasos 3a, 3b, 4, 5 y 6 del
handoff y lo que el modelo no tiene (ordenes de compra, fecha prometida).

Supuestos aprobados por Alejo (2026-11-11), porque datos-base-sandbox.md no los define:
proveedor "Aceros Demo Proveedor S.A.S.", tarifas ficticias de CT-DEMO-CNC, temple como servicio
de tercero, COT-DEMO-006 de Industrias Demo Norte, OP-DEMO-004 de SM-100 y "Soporte SM-110" con
plano en borrador para E6 (con su cotizacion COT-DEMO-008 y pedido PED-DEMO-008).

Repetible: cada registro se busca por su clave natural (correo, NIT, SKU, codigo_lote,
codigo_rn, codigo_plano + revision, numero_cotizacion, numero_pedido, codigo_op,
numero_solicitud, codigo de factura); si existe se devuelve a los valores de la tabla, si no
se crea. Una segunda corrida no crea nada. Todo va en una transaccion: si un bloque falla, no
queda nada a medias.

Solo sgi_sandbox o copias sgi_test_* (_pg_pruebas.validar_nombre); sgi_db se rechaza antes de
conectar. Credenciales solo por variables de entorno (ADR-005): SGI_TEST_PG_ADMIN_URL (sin
clave) y PGPASSWORD. No imprime claves.

Los PDF se escriben en 04_CODIGO/BACKEND/static/planos, la carpeta que sirve el backend cuando
se arranca desde 04_CODIGO/BACKEND.

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.sembrar_escenarios_sandbox sgi_test_run   # primero en la copia de pruebas
    python -m scripts.sembrar_escenarios_sandbox sgi_sandbox
"""
import argparse
import enum
import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# app.db.database exige DATABASE_URL y SECRET_KEY al importarse. La semilla no usa ese engine
# (abre el suyo con url_base): si faltan, se fija una base inexistente y una clave sin uso,
# igual que tests/conftest.py. Nunca se lee el .env.
os.environ.setdefault("DATABASE_URL", "postgresql://sin-base-semilla.invalid/sgi_test_sin_definir")
os.environ.setdefault("SECRET_KEY", "sin-uso-en-la-semilla")

from app.db.models import (  # noqa: E402
    ArticuloInventario,
    BOMListaMateriales,
    CentroTrabajo,
    Cliente,
    ConsumoMaterialOP,
    Cotizacion,
    EntregaMaterialOP,
    EstadoCotizacionEnum,
    EstadoOPEnum,
    EstadoPlanoEnum,
    LoteMaterial,
    OrdenPicking,
    OrdenProduccion,
    PedidoDetalle,
    Plano,
    PlanoArchivo,
    PosicionCotizacion,
    Producto,
    Proyecto,
    RegistroTiemposProduccion,
    ServicioTerceroOP,
    SocioNegocio,
    SolicitudCompra,
    Usuario,
)
from app.services.stock_pt import crear_picking_para_pedido  # noqa: E402

DIRECTORIO_PLANOS = Path(__file__).resolve().parents[1] / "static" / "planos"
CATEGORIA_MP = "MATERIA_PRIMA"
CATEGORIA_PT = "PRODUCTO_TERMINADO"
UNIDAD_PLANTA = "Mecanizados"

# Cuentas de usuarios-demo.md que usan los registros (planos, entregas, aprobacion de calidad)
CORREOS = {
    "diseno": "liderdiseno@sgi.local",
    "dibujante": "dibujante@sgi.local",
    "almacen": "almacen@sgi.local",
    "lider_produccion": "liderprod@sgi.local",
    "calidad": "calidadprod@sgi.local",
    "operario": "operario@sgi.local",
    "ventas": "ventas@sgi.local",
}

CLIENTES = (
    # (NIT = codigo_socio, razon social, escenario)
    ("900000001", "Industrias Demo Norte S.A.", "E12 histórico de varios pedidos"),
    ("900000002", "Comercial Demo Sur Ltda.", "E12 sin trabajos registrados"),
    ("900000003", "Constructora Demo Centro S.A.S.", "E9-E11 pedido retenido (retención pendiente del paso 5)"),
)
# Supuesto: datos-base-sandbox.md no nombra al proveedor; hace falta para las compras del perfil
PROVEEDOR = ("900000004", "Aceros Demo Proveedor S.A.S.")

# Supuesto: tarifas ficticias para que la liquidación de costos de OP-DEMO-001 tenga valores (E14)
CENTRO = {"codigo_centro": "CT-DEMO-CNC", "tarifa_hora_mecanizado": Decimal("80000.00"),
          "tarifa_hora_setup": Decimal("60000.00"), "horas_capacidad_turno": Decimal("8.00"),
          "equivalencia": "Centro CNC demo", "activo": True}

MATERIALES = (
    # (sku, nombre, categoria, unidad, costo unitario, stock en lote)
    ("MP-DEMO-LAM3", "Lámina de acero 3 mm", CATEGORIA_MP, "UND", Decimal("85000.00"), 6.0),
    ("MP-DEMO-TORN", "Tornillería M8 (juego)", CATEGORIA_MP, "UND", Decimal("1200.00"), 40.0),
    ("MP-DEMO-PERF40", "Perfil de acero 40x40", CATEGORIA_MP, "M", Decimal("32000.00"), 0.0),
    ("MP-DEMO-SOLD", "Soldadura E6013", CATEGORIA_MP, "KG", Decimal("18000.00"), 5.0),
    ("MP-DEMO-CAJA", "Caja plástica de conexión", CATEGORIA_MP, "UND", Decimal("9000.00"), 30.0),
    ("MP-DEMO-PRENSA", "Prensaestopas PG9", CATEGORIA_MP, "UND", Decimal("2500.00"), 60.0),
    ("PT-DEMO-CC50", "Caja de conexión CC-50", CATEGORIA_PT, "UND", Decimal("45000.00"), 20.0),
)

PRODUCTOS = (
    # (codigo_rn, codigo anterior, descripcion, sku del producto terminado)
    ("RN-100-001-000001", "SM-100", "Soporte metálico SM-100", None),
    ("RN-100-002-000001", "BT-200", "Bastidor BT-200", None),
    ("RN-100-003-000001", "CC-50", "Caja de conexión CC-50", "PT-DEMO-CC50"),
    # E6: supuesto aprobado, producto con plano sin aprobar
    ("RN-100-001-000002", "SM-110", "Soporte metálico SM-110", None),
)

PLANOS = (
    # (codigo_plano, producto, aprobado, estado_diseno, BOM [(sku, cantidad, estado_abastecimiento)])
    ("PLN-DEMO-SM100", "SM-100", True, "LIBERADA",
     [("MP-DEMO-LAM3", 4.0, "ENTREGADO"), ("MP-DEMO-TORN", 8.0, "ENTREGADO")]),
    # BOM radicada sin recibir todo: la liberación de E5 depende del paso 3a (quality_gate.py)
    ("PLN-DEMO-BT200", "BT-200", True, "LISTA_PARA_LIBERAR",
     [("MP-DEMO-PERF40", 10.0, "SOLICITADO"), ("MP-DEMO-SOLD", 2.0, "EN_ALMACEN")]),
    # E6: PDF y material entregado, pero el plano sigue en borrador; nadie puede liberar la OP
    ("PLN-DEMO-SM110", "SM-110", False, "EN_DISENO",
     [("MP-DEMO-LAM3", 2.0, "ENTREGADO"), ("MP-DEMO-TORN", 4.0, "ENTREGADO")]),
)
REVISION = "REV-01"

COTIZACIONES = (
    # (numero, NIT cliente, estado, fecha, [(producto, cantidad, precio, origen)])
    ("COT-DEMO-001", "900000001", "EMITIDA", date(2026, 9, 1), [("SM-100", 10, Decimal("150000.00"), "PLANO")]),
    ("COT-DEMO-002", "900000001", "EMITIDA", date(2026, 9, 15), [("BT-200", 4, Decimal("420000.00"), "PLANO")]),
    ("COT-DEMO-003", "900000001", "EMITIDA", date(2026, 10, 1), [("CC-50", 5, Decimal("65000.00"), "STOCK_PT")]),
    ("COT-DEMO-004", "900000001", "EMITIDA", date(2026, 8, 1), [("SM-100", 2, Decimal("150000.00"), "PLANO")]),
    ("COT-DEMO-005", "900000003", "EMITIDA", date(2026, 10, 10), [("BT-200", 2, Decimal("420000.00"), "PLANO")]),
    # E20: emitida y sin pedido. Supuesto: cliente Industrias Demo Norte
    ("COT-DEMO-006", "900000001", "EMITIDA", date(2026, 10, 20), [("SM-100", 6, Decimal("150000.00"), "PLANO")]),
    # E6: supuesto aprobado
    ("COT-DEMO-008", "900000001", "EMITIDA", date(2026, 10, 25), [("SM-110", 3, Decimal("165000.00"), "PLANO")]),
)

PEDIDOS = (
    # (numero_pedido, cotizacion de origen o None, NIT, fecha de recepcion, fecha compromiso, escenario)
    ("PED-DEMO-001", "COT-DEMO-001", "900000001", date(2026, 9, 3), date(2026, 11, 30), "E1, E14, E15"),
    ("PED-DEMO-002", "COT-DEMO-002", "900000001", date(2026, 9, 17), date(2026, 12, 10), "E1, E5, E7"),
    ("PED-DEMO-003", "COT-DEMO-003", "900000001", date(2026, 10, 3), date(2026, 11, 20), "E1, E16 (cambio E4 pendiente)"),
    ("PED-DEMO-004", "COT-DEMO-004", "900000001", date(2026, 8, 3), date(2026, 10, 30), "E8 (CERRADO pendiente)"),
    ("PED-DEMO-005", "COT-DEMO-005", "900000003", date(2026, 10, 12), date(2026, 12, 20), "E9 (retención pendiente)"),
    ("PED-DEMO-008", "COT-DEMO-008", "900000001", date(2026, 10, 27), date(2026, 12, 15), "E6"),
    # E21: pedidos anteriores sin cotización de origen (la cotización retroactiva es del paso 3b)
    ("PED-DEMO-006", None, "900000001", date(2026, 3, 10), date(2026, 5, 10), "E21"),
    ("PED-DEMO-007", None, "900000001", date(2026, 4, 5), date(2026, 6, 5), "E21"),
)
LINEAS_SIN_COTIZACION = {"PED-DEMO-006": ("SM-100", 3), "PED-DEMO-007": ("BT-200", 1)}

ORDENES = (
    # (codigo_op, pedido, producto, cantidad, estado, avance, escenario)
    ("OP-DEMO-001", "PED-DEMO-001", "SM-100", 10, EstadoOPEnum.LIBERADA, 40.0, "E5 SM-100 liberada, E14, E15"),
    # Sin liberar: la libera DIBUJANTE o LIDER_DISENO en el recorrido cuando exista el paso 3a
    ("OP-DEMO-002", "PED-DEMO-002", "BT-200", 4, EstadoOPEnum.BORRADOR, 0.0, "E5 BT-200 con 60 % del perfil"),
    ("OP-DEMO-003", "PED-DEMO-008", "SM-110", 3, EstadoOPEnum.BORRADOR, 0.0, "E6 sin plano aprobado: no se libera"),
    ("OP-DEMO-004", "PED-DEMO-004", "SM-100", 2, EstadoOPEnum.TERMINADA, 100.0, "E8 terminada y aprobada por Calidad"),
)

SOLICITUDES = (
    # (numero, codigo_op, plano, pedido, sku, cantidad, estado, estado_bom)
    ("SC-DEMO-001", "OP-DEMO-001", "PLN-DEMO-SM100", "PED-DEMO-001", "MP-DEMO-LAM3", 4.0, "RADICADA", "ENTREGADO"),
    ("SC-DEMO-002", "OP-DEMO-001", "PLN-DEMO-SM100", "PED-DEMO-001", "MP-DEMO-TORN", 8.0, "RADICADA", "ENTREGADO"),
    ("SC-DEMO-003", "OP-DEMO-002", "PLN-DEMO-BT200", "PED-DEMO-002", "MP-DEMO-PERF40", 10.0, "RADICADA", "SOLICITADO"),
    ("SC-DEMO-004", "OP-DEMO-002", "PLN-DEMO-BT200", "PED-DEMO-002", "MP-DEMO-SOLD", 2.0, "RADICADA", "EN_ALMACEN"),
)
ENTREGAS = (
    # (codigo_op, sku, cantidad entregada); el perfil llega al 60 % (6 de 10 m)
    ("OP-DEMO-001", "MP-DEMO-LAM3", 4.0),
    ("OP-DEMO-001", "MP-DEMO-TORN", 8.0),
    ("OP-DEMO-002", "MP-DEMO-PERF40", 6.0),
)
TIEMPOS = (
    # (tipo, segundos) de OP-DEMO-001 en CT-DEMO-CNC
    ("SETUP", 1800),
    ("MECANIZADO", 14400),
)
# Supuesto: el temple se registra como servicio de tercero (la OP no tiene tabla de operaciones)
TEMPLE = {"proveedor": "Tratamientos Térmicos Demo S.A.S.", "descripcion": "Tratamiento térmico: temple",
          "numero_factura": "FAC-DEMO-0001", "costo": Decimal("250000.00")}

FECHA_BASE = datetime(2026, 10, 15, 8, 0, tzinfo=timezone.utc)

PENDIENTES = (
    # (escenario, depende de, que falta)
    ("E4", "paso 3b (SCRUM-28)", "cotización nueva referenciada al pedido original PED-DEMO-003: no hay campo de referencia"),
    ("E21", "paso 3b (SCRUM-31)", "cotización de respaldo marcada como retroactiva para PED-DEMO-006 y 007: no hay marca"),
    ("E2, E3", "paso 3b (SCRUM-28)", "bloqueo de pedido sin cotización y de edición de pedido confirmado (comportamiento, sin datos extra)"),
    ("E5", "paso 3a", "liberar OP-DEMO-002 con el perfil solo solicitado: quality_gate.py exige hoy EN_ALMACEN o ENTREGADO"),
    ("E8", "paso 4", "pedido PED-DEMO-004 en estado CERRADO: EstadoProyectoEnum no tiene CERRADO"),
    ("E9, E10, E11", "paso 5 (SCRUM-29)", "retención de PED-DEMO-005 con 'Obra en pausa por permisos': no hay tabla de retenciones"),
    ("E12-E17", "paso 6 (SCRUM-30)", "histórico de cliente, búsqueda y expediente filtrados por rol (los datos ya quedan cargados)"),
    ("E7", "modelo", "fecha prometida del proveedor y alerta por incumplimiento: no hay campos"),
    ("E18, E19", "modelo", "órdenes de compra, aprobadores y cadena: no hay tabla de órdenes de compra"),
    ("E20", "paso 8", "medición de KPI-VEN-04 sin meta (los datos de COT-DEMO-006 ya quedan cargados)"),
)


@dataclass
class Resultado:
    bloque: str
    estado: str = "no ejecutado"  # creado | sin cambios | actualizado | error | no ejecutado
    creados: int = 0
    actualizados: int = 0
    detalle: str = ""
    escenarios: list = field(default_factory=list)


def _normalizar(valor):
    if isinstance(valor, enum.Enum):
        return valor.value
    if isinstance(valor, Decimal):
        return valor.normalize()
    if isinstance(valor, float):
        return Decimal(str(valor)).normalize()
    return valor


class Sembrador:
    """Crea o devuelve a su valor cada registro por su clave natural y cuenta los cambios."""

    def __init__(self, db: Session):
        self.db = db
        self.creados = 0
        self.actualizados = 0

    def asegurar(self, modelo, claves: dict, valores: dict | None = None, al_crear: dict | None = None):
        valores = valores or {}
        instancia = self.db.query(modelo).filter_by(**claves).first()
        if instancia is None:
            instancia = modelo(**claves, **valores, **(al_crear or {}))
            self.db.add(instancia)
            self.db.flush()
            self.creados += 1
            return instancia
        cambio = False
        for nombre, valor in valores.items():
            if _normalizar(getattr(instancia, nombre)) != _normalizar(valor):
                setattr(instancia, nombre, valor)
                cambio = True
        if cambio:
            self.db.flush()
            self.actualizados += 1
        return instancia


def pdf_demo(codigo_plano: str) -> bytes:
    """PDF mínimo y siempre igual para el mismo plano (mismo sha256 en cada corrida)."""
    texto = f"PLANO DEMO {codigo_plano} {REVISION} - SGI sandbox (ficticio)"
    contenido = f"BT /F1 14 Tf 60 760 Td ({texto}) Tj ET".encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(contenido)).encode() + b" >>\nstream\n" + contenido + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for numero, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{numero} 0 obj\n".encode() + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for posicion in posiciones:
        salida += f"{posicion:010d} 00000 n \n".encode()
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return bytes(salida)


# --- Bloques -----------------------------------------------------------------------------------

def bloque_usuarios_demo(s: Sembrador, ctx: dict) -> str:
    encontrados = {u.email: u for u in s.db.query(Usuario).filter(Usuario.email.in_(CORREOS.values())).all()}
    faltan = sorted(set(CORREOS.values()) - {e for e, u in encontrados.items() if u.activo is not False})
    if faltan:
        raise RuntimeError(
            f"faltan usuarios demo activos: {', '.join(faltan)}. Corra preparar_sandbox --usuarios-demo"
        )
    ctx["usuarios"] = {clave: encontrados[correo] for clave, correo in CORREOS.items()}
    return f"{len(CORREOS)} cuentas demo verificadas (las crea preparar_sandbox)"


def bloque_clientes_y_proveedor(s: Sembrador, ctx: dict) -> str:
    ctx["socios"], ctx["clientes"] = {}, {}
    for nit, razon, _ in CLIENTES:
        ctx["socios"][nit] = s.asegurar(
            SocioNegocio, {"codigo_socio": nit},
            {"nit_cedula": nit, "razon_social": razon, "es_cliente": True, "es_proveedor": False, "estado_activo": True},
        )
        # proyectos apunta a clientes y cotizaciones a socios_negocio: el mismo NIT en las dos
        ctx["clientes"][nit] = s.asegurar(Cliente, {"nit_rut": nit}, {"razon_social": razon})
    nit, razon = PROVEEDOR
    ctx["proveedor"] = s.asegurar(
        SocioNegocio, {"codigo_socio": nit},
        {"nit_cedula": nit, "razon_social": razon, "es_cliente": False, "es_proveedor": True, "estado_activo": True},
    )
    return "3 clientes y 1 proveedor (supuesto: nombre del proveedor)"


def bloque_centro_trabajo(s: Sembrador, ctx: dict) -> str:
    valores = {k: v for k, v in CENTRO.items() if k != "codigo_centro"}
    ctx["centro"] = s.asegurar(CentroTrabajo, {"codigo_centro": CENTRO["codigo_centro"]}, valores)
    return f"{CENTRO['codigo_centro']} (supuesto: tarifas ficticias)"


def bloque_materiales_y_stock(s: Sembrador, ctx: dict) -> str:
    ctx["articulos"], ctx["lotes"] = {}, {}
    for sku, nombre, categoria, unidad, costo, stock in MATERIALES:
        ctx["articulos"][sku] = s.asegurar(
            ArticuloInventario, {"codigo_sku": sku},
            {"nombre": nombre, "categoria": categoria, "tipo_inventario": categoria, "unidad_medida": unidad,
             "stock_actual": stock, "stock_reservado": 0.0, "costo_unitario": costo, "ubicacion": "BODEGA-DEMO"},
        )
        ctx["lotes"][sku] = s.asegurar(
            LoteMaterial, {"codigo_lote": f"LOT-{sku}"},
            {"codigo_material": sku, "stock_disponible": stock, "stock_reservado": 0.0, "costo_unitario": costo,
             "inspeccionado_calidad": True, "estado_calidad": "LIBERADO", "almacen_fisico": "BODEGA-DEMO"},
        )
    return f"{len(MATERIALES)} artículos con su lote (CC-50 con 20 und de producto terminado)"


def bloque_productos(s: Sembrador, ctx: dict) -> str:
    ctx["productos"] = {}
    for codigo_rn, anterior, descripcion, sku in PRODUCTOS:
        ctx["productos"][anterior] = s.asegurar(
            Producto, {"codigo_rn": codigo_rn},
            {"codigo_anterior": anterior, "descripcion": descripcion, "estado": "ACTIVO",
             "id_articulo": ctx["articulos"][sku].id_articulo if sku else None},
        )
    return "SM-100, BT-200 y CC-50"


def bloque_planos_pdf_bom(s: Sembrador, ctx: dict) -> str:
    ctx["planos"] = {}
    DIRECTORIO_PLANOS.mkdir(parents=True, exist_ok=True)
    diseno = ctx["usuarios"]["diseno"]
    for codigo, producto, aprobado, estado_diseno, bom in PLANOS:
        contenido = pdf_demo(codigo)
        nombre = f"DEMO_{codigo}_{REVISION}.pdf"
        ruta_fisica = DIRECTORIO_PLANOS / nombre
        if not ruta_fisica.is_file() or ruta_fisica.read_bytes() != contenido:
            ruta_fisica.write_bytes(contenido)
        ruta = f"/static/planos/{nombre}"
        plano = s.asegurar(
            Plano, {"codigo_plano": codigo, "version": REVISION},
            {"id_producto": ctx["productos"][producto].id_producto, "unidad_planta": UNIDAD_PLANTA,
             "estado_diseno": estado_diseno,
             "estado": EstadoPlanoEnum.APROBADO if aprobado else EstadoPlanoEnum.BORRADOR,
             "aprobado_por": diseno.email if aprobado else None,
             "dibujante_asignado": "Dibujante Demo", "archivo_pdf_url": ruta,
             "material_requerido": ", ".join(sku for sku, _, _ in bom)},
            al_crear={"creado_por": diseno.id_usuario},
        )
        # La fecha de aprobación solo se fija una vez (y nunca en un plano sin aprobar)
        if aprobado and plano.fecha_aprobacion is None:
            plano.fecha_aprobacion = FECHA_BASE
        elif not aprobado and plano.fecha_aprobacion is not None:
            plano.fecha_aprobacion = None
            s.actualizados += 1
        s.asegurar(
            PlanoArchivo, {"id_plano": plano.id_plano, "tipo": "PDF", "vigente": True},
            {"ruta": ruta, "nombre_original": nombre, "tamano_bytes": len(contenido),
             "sha256": hashlib.sha256(contenido).hexdigest(), "revision": REVISION, "subido_por": diseno.email},
        )
        for sku, cantidad, estado in bom:
            articulo = ctx["articulos"][sku]
            s.asegurar(
                BOMListaMateriales, {"plano_id": plano.id_plano, "codigo_material": sku},
                {"descripcion": articulo.nombre, "cantidad_requerida": cantidad,
                 "unidad_medida": articulo.unidad_medida, "estado_abastecimiento": estado},
            )
        ctx["planos"][producto] = plano
    return f"2 planos aprobados y 1 en borrador ({UNIDAD_PLANTA}) con PDF en {DIRECTORIO_PLANOS.name}/ y BOM"


def bloque_cotizaciones(s: Sembrador, ctx: dict) -> str:
    ctx["cotizaciones"] = {}
    for numero, nit, estado, fecha, lineas in COTIZACIONES:
        total = sum(cantidad * precio for _, cantidad, precio, _ in lineas)
        cotizacion = s.asegurar(
            Cotizacion, {"numero_cotizacion": numero},
            {"id_socio": ctx["socios"][nit].id_socio, "fecha_emision": fecha, "estado": EstadoCotizacionEnum(estado),
             "valor_total": total, "condiciones_comerciales": "Datos ficticios de demostración (sgi_sandbox)"},
        )
        for producto, cantidad, precio, origen in lineas:
            articulo = ctx["articulos"]["PT-DEMO-CC50"] if origen == "STOCK_PT" else None
            s.asegurar(
                PosicionCotizacion, {"id_cotizacion": cotizacion.id_cotizacion, "numero_producto": producto},
                {"descripcion": ctx["productos"][producto].descripcion, "cantidad": cantidad, "precio_unitario": precio,
                 "origen": origen, "id_articulo": articulo.id_articulo if articulo else None},
            )
        ctx["cotizaciones"][numero] = (cotizacion, lineas)
    return "7 emitidas: 6 con su pedido y 1 sin pedido (E20)"


def bloque_pedidos(s: Sembrador, ctx: dict) -> str:
    ctx["pedidos"], ctx["detalles"] = {}, {}
    for numero, cotizacion, nit, recepcion, compromiso, _ in PEDIDOS:
        if cotizacion:
            lineas = [(p, c, precio, origen) for p, c, precio, origen in ctx["cotizaciones"][cotizacion][1]]
        else:
            producto, cantidad = LINEAS_SIN_COTIZACION[numero]
            lineas = [(producto, cantidad, None, "PLANO")]
        cliente = ctx["clientes"][nit]
        pedido = s.asegurar(
            Proyecto, {"numero_pedido": numero},
            {"codigo_proyecto": numero, "id_cliente": cliente.id_cliente, "cliente_nombre": cliente.razon_social,
             "cantidad": sum(c for _, c, _, _ in lineas),
             "detalle_producto": ", ".join(ctx["productos"][p].descripcion for p, _, _, _ in lineas),
             "requisitos_cliente": "Fabricación según cotización emitida" if cotizacion else "Pedido anterior sin cotización de origen",
             "fecha_compromiso": compromiso, "confirmado": True,
             "cotizacion_total": sum(c * precio for _, c, precio, _ in lineas if precio is not None) if cotizacion else None},
            al_crear={"creado_en": datetime(recepcion.year, recepcion.month, recepcion.day, 9, 0, tzinfo=timezone.utc)},
        )
        for producto, cantidad, _, origen in lineas:
            stock = origen == "STOCK_PT"
            detalle = s.asegurar(
                PedidoDetalle, {"pedido_id": pedido.id_proyecto, "codigo_producto": ctx["productos"][producto].codigo_rn},
                {"id_producto": ctx["productos"][producto].id_producto, "descripcion": ctx["productos"][producto].descripcion,
                 "tipo": "PIEZA", "cantidad_solicitada": cantidad, "unidad": "UND", "fecha_requerida": compromiso,
                 "origen": origen, "id_articulo": ctx["articulos"]["PT-DEMO-CC50"].id_articulo if stock else None},
                # El picking asigna las líneas de stock; las de fabricación quedan pendientes
                al_crear={"cantidad_asignada": 0, "cantidad_pendiente": cantidad},
            )
            ctx["detalles"][(numero, producto)] = detalle
        ctx["pedidos"][numero] = pedido
    return "6 desde cotización (PED-<número de la cotización>) y 2 sin cotización (E21)"


def bloque_ordenes_produccion(s: Sembrador, ctx: dict) -> str:
    ctx["ordenes"] = {}
    calidad = ctx["usuarios"]["calidad"]
    for codigo, pedido, producto, cantidad, estado, avance, _ in ORDENES:
        liberada = estado in (EstadoOPEnum.LIBERADA, EstadoOPEnum.TERMINADA)
        terminada = estado == EstadoOPEnum.TERMINADA
        ctx["ordenes"][codigo] = s.asegurar(
            OrdenProduccion, {"codigo_op": codigo},
            {"id_proyecto": ctx["pedidos"][pedido].id_proyecto, "id_plano": ctx["planos"][producto].id_plano,
             "id_producto": ctx["productos"][producto].id_producto,
             "id_detalle_pedido": ctx["detalles"][(pedido, producto)].detalle_id,
             "cantidad_fabricar": cantidad, "estado": estado, "reserva_stock_100": liberada,
             "porcentaje_avance": avance, "estado_calidad": "APROBADO" if terminada else None,
             "aprobado_por_calidad_id": calidad.id_usuario if terminada else None,
             "observaciones": "Datos ficticios de demostración (sgi_sandbox)"},
            al_crear={"liberada_en": FECHA_BASE if liberada else None},
        )
    return "OP-DEMO-001 liberada, 002 sin liberar (E5 pendiente del paso 3a), 003 sin plano aprobado (E6), 004 terminada"


def bloque_compras_y_entregas(s: Sembrador, ctx: dict) -> str:
    for numero, op, plano, pedido, sku, cantidad, estado, estado_bom in SOLICITUDES:
        articulo = ctx["articulos"][sku]
        producto = next(p for c, p, *_ in PLANOS if c == plano)
        s.asegurar(
            SolicitudCompra, {"numero_solicitud": numero},
            {"codigo_op": op, "codigo_plano": plano, "numero_pedido": pedido, "nombre_item": articulo.nombre,
             "codigo_sku": sku, "categoria": articulo.categoria, "cantidad_solicitada": cantidad,
             "unidad_medida": articulo.unidad_medida, "estado": estado, "estado_bom": estado_bom,
             "proveedor_sugerido": ctx["proveedor"].razon_social,
             "id_proyecto": ctx["pedidos"][pedido].id_proyecto, "id_plano": ctx["planos"][producto].id_plano},
            al_crear={"fecha_solicitud": FECHA_BASE},
        )
    usuarios = ctx["usuarios"]
    for op, sku, cantidad in ENTREGAS:
        s.asegurar(
            EntregaMaterialOP, {"op_id": ctx["ordenes"][op].id_op, "lote_id": ctx["lotes"][sku].id},
            {"cantidad_entregada": cantidad, "entregado_por": usuarios["almacen"].id_usuario,
             "recibido_por_produccion": usuarios["lider_produccion"].id_usuario},
            al_crear={"fecha_entrega": FECHA_BASE},
        )
    return "4 solicitudes radicadas y 3 entregas (perfil de BT-200: 6 de 10 m). Aprobaciones E18/E19 pendientes"


def bloque_costos_op(s: Sembrador, ctx: dict) -> str:
    orden = ctx["ordenes"]["OP-DEMO-001"]
    for op, sku, cantidad in ENTREGAS:
        if op != "OP-DEMO-001":
            continue
        articulo = ctx["articulos"][sku]
        s.asegurar(
            ConsumoMaterialOP, {"op_id": orden.id_op, "codigo_material": sku},
            {"descripcion_material": articulo.nombre, "cantidad": cantidad, "unidad_medida": articulo.unidad_medida,
             "costo_unitario": articulo.costo_unitario, "fuente": "SEMILLA_DEMO"},
        )
    for tipo, segundos in TIEMPOS:
        s.asegurar(
            RegistroTiemposProduccion,
            {"orden_produccion_id": orden.id_op, "tipo_tiempo": tipo, "estacion_id": CENTRO["codigo_centro"]},
            {"operario_id": CORREOS["operario"], "segundos_ejecutados": segundos, "pausado_por_turno": False},
            al_crear={"id_registro": uuid.uuid4(), "fecha_hora_inicio": FECHA_BASE},
        )
    s.asegurar(
        ServicioTerceroOP, {"op_id": orden.id_op, "numero_factura": TEMPLE["numero_factura"]},
        {"proveedor": TEMPLE["proveedor"], "descripcion": TEMPLE["descripcion"], "costo": TEMPLE["costo"]},
    )
    return "OP-DEMO-001: 2 consumos, setup y mecanizado, temple como servicio de tercero (supuesto)"


def bloque_picking(s: Sembrador, ctx: dict) -> str:
    pedido = ctx["pedidos"]["PED-DEMO-003"]
    if s.db.query(OrdenPicking).filter(OrdenPicking.id_proyecto == pedido.id_proyecto).first():
        return "PED-DEMO-003 ya tiene su orden de picking"
    lineas = [ctx["detalles"][("PED-DEMO-003", "CC-50")]]
    crear_picking_para_pedido(s.db, pedido, lineas, usuario=CORREOS["ventas"])
    s.creados += 1
    return "orden de picking PENDIENTE para 5 und de CC-50"


BLOQUES = (
    ("usuarios_demo", bloque_usuarios_demo),
    ("clientes_y_proveedor", bloque_clientes_y_proveedor),
    ("centro_trabajo", bloque_centro_trabajo),
    ("materiales_y_stock", bloque_materiales_y_stock),
    ("productos", bloque_productos),
    ("planos_pdf_bom", bloque_planos_pdf_bom),
    ("cotizaciones", bloque_cotizaciones),
    ("pedidos", bloque_pedidos),
    ("ordenes_produccion", bloque_ordenes_produccion),
    ("compras_y_entregas", bloque_compras_y_entregas),
    ("costos_op", bloque_costos_op),
    ("picking", bloque_picking),
)


def sembrar(db: Session) -> list[Resultado]:
    """Ejecuta los bloques en orden dentro de la transacción de db. Si uno falla, revierte todo
    y marca los siguientes como no ejecutados. No hace commit: lo decide quien llama."""
    resultados = [Resultado(nombre) for nombre, _ in BLOQUES]
    ctx: dict = {}
    for resultado, (_, funcion) in zip(resultados, BLOQUES):
        s = Sembrador(db)
        try:
            resultado.detalle = funcion(s, ctx)
        except Exception as error:
            db.rollback()
            resultado.estado = "error"
            resultado.detalle = (str(error).strip().splitlines() or [error.__class__.__name__])[0]
            return resultados
        resultado.creados, resultado.actualizados = s.creados, s.actualizados
        if s.creados:
            resultado.estado = "creado"
        elif s.actualizados:
            resultado.estado = "actualizado"
        else:
            resultado.estado = "sin cambios"
    return resultados


def imprimir(base: str, resultados: list[Resultado], confirmado: bool) -> None:
    print(f"Semilla de escenarios en {base}")
    print(f"{'Bloque':<22}{'Estado':<14}{'Creados':>8}{'Actualiz.':>10}  Detalle")
    for r in resultados:
        print(f"{r.bloque:<22}{r.estado:<14}{r.creados:>8}{r.actualizados:>10}  {r.detalle}")
    print()
    print("Pendiente (no se siembra):")
    for escenario, depende, falta in PENDIENTES:
        print(f"  {escenario:<13}{depende:<22}{falta}")
    print()
    print("Cambios guardados." if confirmado else "Hubo un error: se revirtió todo, no se guardó nada.")


def main() -> None:
    from scripts._pg_pruebas import conectar_admin, existe_base, fallar, url_base, validar_nombre

    parser = argparse.ArgumentParser(description="Semilla de escenarios (SCRUM-33) en sgi_sandbox o sgi_test_*.")
    parser.add_argument("base", help="sgi_sandbox o una copia sgi_test_* (nunca sgi_db).")
    base = validar_nombre(parser.parse_args().base, permitir_sandbox=True)

    admin = conectar_admin()
    try:
        if not existe_base(admin.cursor(), base):
            fallar(f"No existe la base {base}.")
    finally:
        admin.close()

    # URL sin clave (SGI_TEST_PG_ADMIN_URL con la base elegida); libpq toma la clave de PGPASSWORD
    engine = create_engine(url_base(base))
    try:
        with Session(engine) as db:
            actual = db.connection().exec_driver_sql("SELECT current_database()").scalar()
            if actual != base:
                fallar(f"La conexión apunta a {actual}, no a {base}.")
            resultados = sembrar(db)
            confirmado = all(r.estado != "error" for r in resultados)
            if confirmado:
                db.commit()
        imprimir(base, resultados, confirmado)
        if not confirmado:
            raise SystemExit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
