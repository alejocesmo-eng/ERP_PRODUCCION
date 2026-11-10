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

MATRIZ = {
    "almacen POST /recepcion-compra": ["ADMIN", "ALMACEN"],
    "almacen POST /salidas": ["ADMIN", "ALMACEN"],
    "almacen POST /traslados": ["ADMIN", "ALMACEN"],
    "cotizaciones POST /ventas/cotizaciones/": ["ADMIN", "VENTAS"],
    "cotizaciones POST /ventas/cotizaciones/{id_cotizacion}/enviar-cliente": ["ADMIN", "VENTAS"],
    "cotizaciones PATCH /ventas/cotizaciones/{id_cotizacion}/aprobar-y-generar-pedido": ["ADMIN", "VENTAS"],
    "historial GET /historial/{tipo_entidad}/{identificador}": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD", "MANTENIMIENTO"],
    "historial POST /historial/suspender": ["ADMIN", "VENTAS", "DISENO", "PRODUCCION", "CALIDAD", "MANTENIMIENTO"],
    "historial POST /historial/reactivar": ["ADMIN", "VENTAS", "DISENO", "PRODUCCION", "CALIDAD", "MANTENIMIENTO"],
    "inventario POST /centros": ["ADMIN"],
    "inventario POST /categorias": ["ADMIN", "ALMACEN"],
    "inventario POST /articulos": ["ADMIN", "ALMACEN"],
    "inventario PATCH /lotes/{id_lote}/calidad": ["ADMIN", "CALIDAD"],
    "maestros GET /socios": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"],
    "maestros POST /socios": ["ADMIN"],
    "maestros PUT /socios/{id_socio}": ["ADMIN"],
    "maestros DELETE /socios/{id_socio}": ["ADMIN"],
    "maestros GET /personal": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"],
    "maestros GET /personal/usuarios-disponibles": ["ADMIN"],
    "maestros POST /personal": ["ADMIN"],
    "maestros PUT /personal/{id_trabajador}": ["ADMIN"],
    "maestros DELETE /personal/{id_trabajador}": ["ADMIN"],
    "maestros GET /cuentas-costos": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"],
    "maestros POST /cuentas-costos": ["ADMIN"],
    "maestros PUT /cuentas-costos/{id_elemento}": ["ADMIN"],
    "maestros DELETE /cuentas-costos/{id_elemento}": ["ADMIN"],
    "maestros GET /catalogos": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"],
    "maestros GET /catalogos/categorias": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"],
    "maestros POST /catalogos/categorias": ["ADMIN", "ALMACEN"],
    "maestros PUT /catalogos/categorias/{id_categoria}": ["ADMIN", "ALMACEN"],
    "maestros DELETE /catalogos/categorias/{id_categoria}": ["ADMIN", "ALMACEN"],
    "maestros GET /catalogos/unidades": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"],
    "maestros POST /catalogos/unidades": ["ADMIN", "ALMACEN"],
    "maestros PUT /catalogos/unidades/{id_unidad}": ["ADMIN", "ALMACEN"],
    "maestros DELETE /catalogos/unidades/{id_unidad}": ["ADMIN", "ALMACEN"],
    "materiales POST /": ["ADMIN", "ALMACEN"],
    "ordenes GET /expediente/{codigo_op}": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"],
    "planos POST /{id_plano}/aprobar": ["DISENO"],
    "planos POST /{id_plano}/revision": ["DISENO"],
    "proyectos PATCH /{id_proyecto}/confirmar": ["ADMIN", "VENTAS"],
    "stock_pt GET /ventas/stock-pt": ["ADMIN", "VENTAS", "ALMACEN"],
    "trazabilidad GET /proyecto/{id_proyecto}": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"],
    "trazabilidad GET /buscar": ["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"],
    "usuarios GET /panel-admin": ["ADMIN"],
}

# Cambios de estado de la OP distintos de la liberación: se revisan en el cuerpo del PATCH
ROLES_ACTUALIZAR_OP = ["ADMIN", "PRODUCCION"]


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


def test_el_catalogo_tiene_los_16_roles_y_los_anteriores_aparte():
    assert len(roles.ROLES_CATALOGO) == len(set(roles.ROLES_CATALOGO)) == 16
    assert set(roles.ROLES_ANTERIORES) == {"DISENO", "PRODUCCION", "CALIDAD"}
    assert not set(roles.ROLES_ANTERIORES) & set(roles.ROLES_CATALOGO)
    usados = {rol for lista in MATRIZ.values() for rol in lista} | set(ROLES_ACTUALIZAR_OP)
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
