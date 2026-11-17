# tests/test_matriz_roles.py
"""
Matriz de acceso por rol (SCRUM-27): qué roles pasan el requerir_roles de cada ruta de app.api.v1.

La matriz se escribe con los nombres de rol, no con los grupos de app.core.roles, para que un
cambio en un grupo no pase sin cambiar también esta tabla. Cada cambio de acceso se justifica con
reglas/permisos-por-rol-modulo.md del proyecto PRISMA.

- Las rutas con requerir_roles son exactamente las de la matriz (una ruta nueva con rol entra aquí).
- Cada ruta admite exactamente esos roles, en ese orden (el orden sale en el detalle del 403).
- Un rol fuera de la lista recibe 403 y uno de la lista pasa.

Inspecciona los routers sin importar app.main ni tocar ninguna base.
"""
import importlib
import inspect
import pkgutil

import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import app.api.v1 as v1
from app.api.deps import obtener_usuario_actual, requerir_roles
from app.api.v1 import ordenes
from app.core import roles

# Listas escritas a mano (no importadas de app.core.roles). ADMIN en todas durante la transición;
# los roles anteriores (DISENO, PRODUCCION, CALIDAD) siguen donde estaban.
LECTURA = [
    "ADMIN", "VENTAS", "CALIDAD_PRODUCTO", "GESTION_CALIDAD", "ALMACEN", "JEFE_PRODUCCION",
    "LIDER_MECANIZADOS", "LIDER_SERVICIOS", "COSTOS", "LIDER_DISENO", "DIBUJANTE", "DIRECTOR_PRODUCCION",
    "DISENO", "PRODUCCION", "CALIDAD",
]
# Sin CALIDAD_PRODUCTO, ALMACEN, DIBUJANTE, LIDER_DISENO ni DISENO hasta que se confirme (2026-11-12)
EXPEDIENTE_OP = [
    "ADMIN", "GESTION_CALIDAD", "JEFE_PRODUCCION", "LIDER_MECANIZADOS", "LIDER_SERVICIOS", "COSTOS",
    "DIRECTOR_PRODUCCION", "PRODUCCION", "CALIDAD",
]
HISTORIAL_CONSULTA = [
    "ADMIN", "VENTAS", "CALIDAD_PRODUCTO", "GESTION_CALIDAD", "ALMACEN", "JEFE_PRODUCCION",
    "LIDER_MECANIZADOS", "LIDER_SERVICIOS", "COSTOS", "MANTENIMIENTO", "LIDER_DISENO", "DIBUJANTE",
    "DIRECTOR_PRODUCCION", "DISENO", "PRODUCCION", "CALIDAD",
]
SUSPENDER = [
    "ADMIN", "VENTAS", "CALIDAD_PRODUCTO", "GESTION_CALIDAD", "JEFE_PRODUCCION", "LIDER_MECANIZADOS",
    "MANTENIMIENTO", "LIDER_DISENO", "DIBUJANTE", "DISENO", "PRODUCCION", "CALIDAD",
]
STOCK_PT = ["ADMIN", "VENTAS", "JEFE_PRODUCCION", "COSTOS", "LIDER_LOGISTICA"]

MATRIZ = {
    "almacen POST /recepcion-compra": ["ADMIN", "ALMACEN"],
    "almacen POST /salidas": ["ADMIN", "ALMACEN"],
    "almacen POST /traslados": ["ADMIN", "ALMACEN"],
    "cotizaciones POST /ventas/cotizaciones/": ["ADMIN", "VENTAS"],
    "cotizaciones POST /ventas/cotizaciones/{id_cotizacion}/enviar-cliente": ["ADMIN", "VENTAS"],
    "cotizaciones PUT /ventas/cotizaciones/{id_cotizacion}": ["ADMIN", "VENTAS"],
    "cotizaciones DELETE /ventas/cotizaciones/{id_cotizacion}": ["ADMIN", "VENTAS"],
    "cotizaciones POST /ventas/cotizaciones/{id_cotizacion}/emitir": ["ADMIN", "VENTAS"],
    "cotizaciones GET /ventas/cotizaciones/siguiente-consecutivo": ["ADMIN", "VENTAS"],
    "maestros GET /condiciones-pago": LECTURA,
    "cotizaciones PATCH /ventas/cotizaciones/{id_cotizacion}/aprobar-y-generar-pedido": ["ADMIN", "VENTAS"],
    "historial GET /historial/{tipo_entidad}/{identificador}": HISTORIAL_CONSULTA,
    "historial POST /historial/suspender": SUSPENDER,
    "historial POST /historial/reactivar": SUSPENDER,
    "inventario POST /centros": ["ADMIN"],
    "inventario POST /categorias": ["ADMIN", "ALMACEN"],
    "inventario POST /articulos": ["ADMIN", "ALMACEN"],
    "inventario PATCH /lotes/{id_lote}/calidad": ["ADMIN", "CALIDAD_PRODUCTO", "CALIDAD"],
    "maestros GET /socios": LECTURA,
    "maestros POST /socios": ["ADMIN"],
    "maestros PUT /socios/{id_socio}": ["ADMIN"],
    "maestros DELETE /socios/{id_socio}": ["ADMIN"],
    "maestros GET /personal": LECTURA,
    "maestros GET /personal/usuarios-disponibles": ["ADMIN"],
    "maestros POST /personal": ["ADMIN"],
    "maestros PUT /personal/{id_trabajador}": ["ADMIN"],
    "maestros DELETE /personal/{id_trabajador}": ["ADMIN"],
    "maestros GET /cuentas-costos": LECTURA,
    "maestros POST /cuentas-costos": ["ADMIN"],
    "maestros PUT /cuentas-costos/{id_elemento}": ["ADMIN"],
    "maestros DELETE /cuentas-costos/{id_elemento}": ["ADMIN"],
    "maestros GET /catalogos": LECTURA,
    "maestros GET /catalogos/categorias": LECTURA,
    "maestros POST /catalogos/categorias": ["ADMIN", "ALMACEN"],
    "maestros PUT /catalogos/categorias/{id_categoria}": ["ADMIN", "ALMACEN"],
    "maestros DELETE /catalogos/categorias/{id_categoria}": ["ADMIN", "ALMACEN"],
    "maestros GET /catalogos/unidades": LECTURA,
    "maestros POST /catalogos/unidades": ["ADMIN", "ALMACEN"],
    "maestros PUT /catalogos/unidades/{id_unidad}": ["ADMIN", "ALMACEN"],
    "maestros DELETE /catalogos/unidades/{id_unidad}": ["ADMIN", "ALMACEN"],
    "materiales POST /": ["ADMIN", "ALMACEN"],
    "ordenes GET /expediente/{codigo_op}": EXPEDIENTE_OP,
    "planos POST /{id_plano}/aprobar": ["ADMIN", "LIDER_DISENO", "DISENO"],
    "planos POST /{id_plano}/revision": ["ADMIN", "LIDER_DISENO", "DIBUJANTE", "DISENO"],
    "proyectos PATCH /{id_proyecto}/confirmar": ["ADMIN", "VENTAS"],
    "stock_pt GET /ventas/stock-pt": STOCK_PT,
    "trazabilidad GET /proyecto/{id_proyecto}": LECTURA,
    "trazabilidad GET /buscar": LECTURA,
    "usuarios GET /panel-admin": ["ADMIN"],
}

# Cambios de estado de la OP distintos de la liberación: se revisan en el cuerpo del PATCH.
# Terminar la OP y pasarla a inspección, y cerrarla como respaldo del Jefe de Producción, lo puede
# hacer también LIDER_MECANIZADOS.
ROLES_ACTUALIZAR_OP = ["ADMIN", "JEFE_PRODUCCION", "PRODUCCION"]
ROLES_NOTIFICAR_OP_TERMINADA = ["ADMIN", "JEFE_PRODUCCION", "LIDER_MECANIZADOS", "PRODUCCION"]
# LIDER_SERVICIOS cierra solo OP de su área (lo restringe la ruta, ROLES_CIERRE_SOLO_SU_UNIDAD)
ROLES_CERRAR_OP = ["ADMIN", "JEFE_PRODUCCION", "LIDER_MECANIZADOS", "LIDER_SERVICIOS", "PRODUCCION"]


def _roles_de(dependant):
    encontrados = []
    for dependencia in dependant.dependencies:
        llamada = dependencia.call
        if getattr(llamada, "__qualname__", "") == "requerir_roles.<locals>.rol_checker":
            encontrados.append(inspect.getclosurevars(llamada).nonlocals["roles_permitidos"])
        encontrados += _roles_de(dependencia)
    return encontrados


def matriz_actual():
    actual = {}
    for modulo in pkgutil.iter_modules(v1.__path__):
        objeto_modulo = importlib.import_module(f"app.api.v1.{modulo.name}")
        for objeto in vars(objeto_modulo).values():
            if type(objeto).__name__ != "APIRouter":
                continue
            for ruta in objeto.routes:
                if not isinstance(ruta, APIRoute):
                    continue
                encontrados = _roles_de(ruta.dependant)
                assert len(encontrados) <= 1, f"{modulo.name} {ruta.path}: más de un requerir_roles"
                for metodo in ruta.methods if encontrados else []:
                    actual[f"{modulo.name} {metodo} {ruta.path}"] = list(encontrados[0])
    return actual


def test_las_rutas_con_rol_son_las_de_la_matriz():
    actual = matriz_actual()
    assert sorted(set(actual) - set(MATRIZ)) == [], "Ruta con requerir_roles que falta en MATRIZ"
    assert sorted(set(MATRIZ) - set(actual)) == [], "Ruta de MATRIZ sin requerir_roles"


@pytest.mark.parametrize("ruta", sorted(MATRIZ))
def test_cada_ruta_admite_exactamente_sus_roles(ruta):
    assert matriz_actual()[ruta] == MATRIZ[ruta]


def test_actualizar_op_fuera_de_la_liberacion():
    assert ordenes.ROLES_ACTUALIZAR_OP == ROLES_ACTUALIZAR_OP
    assert ordenes.ROLES_NOTIFICAR_OP_TERMINADA == ROLES_NOTIFICAR_OP_TERMINADA
    assert ordenes.ROLES_CERRAR_OP == ROLES_CERRAR_OP
    assert {estado.value for estado in ordenes.ESTADOS_OP_NOTIFICAR_CALIDAD} == {"TERMINADA", "EN_INSPECCION"}


def test_admin_en_todas_las_rutas_durante_la_transicion():
    for ruta, lista in MATRIZ.items():
        assert "ADMIN" in lista, ruta
    assert "ADMIN" in ROLES_ACTUALIZAR_OP and "ADMIN" in ROLES_NOTIFICAR_OP_TERMINADA


def test_operario_y_mantenimiento_fuera_del_expediente_y_ventas_tambien():
    assert not {"OPERARIO", "MANTENIMIENTO", "VENTAS"} & set(MATRIZ["ordenes GET /expediente/{codigo_op}"])


def test_almacen_no_ve_stock_de_producto_terminado():
    assert "ALMACEN" not in MATRIZ["stock_pt GET /ventas/stock-pt"]


def test_el_catalogo_tiene_los_18_roles_y_los_anteriores_aparte():
    assert len(roles.ROLES_CATALOGO) == len(set(roles.ROLES_CATALOGO)) == 18
    assert set(roles.ROLES_ANTERIORES) == {"DISENO", "PRODUCCION", "CALIDAD"}
    assert not set(roles.ROLES_ANTERIORES) & set(roles.ROLES_CATALOGO)
    usados = (
        {rol for lista in MATRIZ.values() for rol in lista}
        | set(ROLES_ACTUALIZAR_OP) | set(ROLES_NOTIFICAR_OP_TERMINADA) | set(ROLES_CERRAR_OP)
    )
    assert usados <= set(roles.ROLES_CATALOGO) | set(roles.ROLES_ANTERIORES)


@pytest.fixture
def client():
    app = FastAPI()

    @app.get("/prueba")
    def ruta_prueba(usuario: dict = Depends(requerir_roles(["ADMIN", "VENTAS"]))):
        return {"rol": usuario["rol"]}

    app.dependency_overrides[obtener_usuario_actual] = lambda: {"email": "x@prueba.test", "rol": app.state.rol}
    with TestClient(app) as cliente:
        yield cliente, app


@pytest.mark.parametrize("rol, estado", [("VENTAS", 200), ("ADMIN", 200), ("OPERARIO", 403), ("DISENO", 403)])
def test_requerir_roles_responde_403_fuera_de_la_lista(client, rol, estado):
    cliente, app = client
    app.state.rol = rol
    respuesta = cliente.get("/prueba")
    assert respuesta.status_code == estado
    if estado == 403:
        assert respuesta.json()["detail"] == "Acceso denegado. Permisos requeridos para rol(es): ['ADMIN', 'VENTAS']"


def test_el_mensaje_del_403_solo_lista_roles_del_catalogo():
    from app.api.deps import detalle_acceso_denegado

    detalle = detalle_acceso_denegado(roles.ROLES_EXPEDIENTE_OP)

    assert "GESTION_CALIDAD" in detalle and "JEFE_PRODUCCION" in detalle
    for anterior in roles.ROLES_ANTERIORES:
        assert f"'{anterior}'" not in detalle
    # Sin roles del catálogo (caso teórico) se muestra la lista tal cual
    assert detalle_acceso_denegado(["DISENO"]).endswith("['DISENO']")

