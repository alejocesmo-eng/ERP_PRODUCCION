# tests/test_mapa_op.py
"""
Mapa de la OP (app/api/v1/mapa_op.py; tabla de nodos por rol de Alejo, 2026-11-17):
- Relaciones: pedido y cotización (VENTAS, JEFE_PRODUCCION, COSTOS; valor solo con
  PERM_VALOR_COTIZADO_VER), cliente (JEFE, VENTAS, líderes, GESTION_CALIDAD), otras OP del pedido
  (líderes y JEFE), planos (DIBUJANTE, LIDER_DISENO, JEFE, CALIDAD_PRODUCTO) y recibos de producción
  (COSTOS y JEFE).
- Procesos: roles de producción y COSTOS; minutos solo para COSTOS y JEFE_PRODUCCION. Los de
  producción lo abren por defecto.
- OPERARIO (y quien no tenga ningún mapa) recibe 403. El rol se lee de la base.

SQLite en memoria con override de get_db; aplicación FastAPI mínima con la misma dependencia global
y el mismo middleware que app.main (no se importa app.main).
"""
import uuid
from datetime import date, timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import mapa_op
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import (
    ArticuloInventario, Cotizacion, EntregaMaterialOP, EstadoOPEnum, LoteMaterial, MovimientoInventario,
    OrdenProduccion, Permiso, Plano, Producto, Proyecto, RegistroTiemposProduccion, Rol, RolPermiso, SocioNegocio,
    Usuario,
)
from app.db.models_produccion import OperacionOT
from app.services import acceso_bd
from tests.ayudantes_usuarios import datos_usuario, id_prueba

MEC, SER = roles.LIDER_MECANIZADOS, roles.LIDER_SERVICIOS
ROLES_PRUEBA = [
    roles.ADMIN, roles.VENTAS, roles.JEFE_PRODUCCION, roles.COSTOS, MEC, SER, roles.GESTION_CALIDAD, roles.DIBUJANTE,
    roles.LIDER_DISENO, roles.CALIDAD_PRODUCTO, roles.DIRECTOR_PRODUCCION, roles.OPERARIO, roles.CAPTURISTA_TIEMPOS,
]
# Como la migración 25: valor cotizado para VENTAS, JEFE_PRODUCCION, COSTOS y GESTION_CALIDAD
CON_VALOR = [roles.VENTAS, roles.JEFE_PRODUCCION, roles.COSTOS, roles.GESTION_CALIDAD]
RUTA = "/api/v1/mapa-op"


@pytest.fixture
def ctx():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.add_middleware(acceso_bd.OcultarCamposPorRol)
    app.include_router(mapa_op.router, prefix=RUTA)
    app.dependency_overrides[get_db] = _get_db
    with Sesion() as s:
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in ROLES_PRUEBA)
        s.add(Permiso(id_permiso=acceso_bd.PERMISO_VALOR_COTIZADO, modulo="PRUEBA"))
        s.add_all(RolPermiso(id_rol=rol, id_permiso=acceso_bd.PERMISO_VALOR_COTIZADO) for rol in CON_VALOR)
        s.add_all(Usuario(**datos_usuario(rol.lower()), password_hash="!SIN_CLAVE", nombre_completo=rol, id_rol=rol)
                  for rol in ROLES_PRUEBA)
        s.add(Usuario(**datos_usuario("operario.uno"), password_hash="!SIN_CLAVE", nombre_completo="Operario 1",
                      id_rol=roles.OPERARIO))
        socio = SocioNegocio(id_socio=uuid.uuid4(), codigo_socio="CL-MAPA", nit_cedula="900000001", razon_social="Cliente ficticio", es_cliente=True)
        s.add(socio)
        s.flush()
        s.add(Cotizacion(id_socio=socio.id_socio, numero_cotizacion="COT-MAPA-1", valor_total=1500000, moneda="COP"))
        pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido="PED-MAPA-1", codigo_proyecto="PED-MAPA-1",
                          cliente_nombre="Cliente ficticio", requisitos_cliente="Según plano", confirmado=True,
                          cotizacion_total=1500000, fecha_compromiso=date(2026, 12, 15))
        producto = Producto(id_producto=uuid.uuid4(), codigo_rn="RN-MAPA-1", descripcion="Eje ficticio")
        s.add_all([pedido, producto])
        s.flush()
        plano = Plano(codigo_plano="PLN-MAPA-1", id_producto=producto.id_producto, revision="B", unidad_planta="Mecanizados")
        s.add(plano)
        s.flush()
        # TERMINADA en Mecanizados: la ven el líder de Mecanizados y CALIDAD_PRODUCTO (inspección)
        op = OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op="OP-MAPA-1", cantidad_fabricar=2,
                             unidad_actual="MECANIZADOS", estado=EstadoOPEnum.TERMINADA, id_producto=producto.id_producto)
        hermana = OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op="OP-MAPA-2", cantidad_fabricar=1,
                                  unidad_actual="SERVICIOS", estado=EstadoOPEnum.EN_PRODUCCION)
        s.add_all([op, hermana])
        s.flush()
        operaciones = [
            OperacionOT(id_plano=plano.id_plano, codigo_op="OP-MAPA-1", codigo_plano=plano.codigo_plano,
                        secuencia_paso=secuencia, nombre_proceso=nombre)
            for secuencia, nombre in ((20, "Fresado"), (10, "Torneado"))
        ]
        s.add_all(operaciones)
        s.flush()
        s.add(RegistroTiemposProduccion(
            orden_produccion_id=op.id_op, id_operacion=operaciones[1].id_operacion, estacion_id="TORNO-01",
            operario_id=str(id_prueba("operario.uno")), tipo_tiempo="MECANIZADO", segundos_ejecutados=45 * 60,
            segundos_setup=15 * 60, origen="MANUAL", fecha_trabajo=date(2026, 11, 16),
            registrado_por=str(id_prueba("capturista_tiempos")), pausado_por_turno=False,
        ))
        lote = LoteMaterial(codigo_lote="LOTE-MAPA-1", codigo_material="MAT-1", numero_colada="COL-1")
        articulo = ArticuloInventario(codigo_sku="PT-MAPA-1", nombre="Eje ficticio terminado", categoria="PRODUCTO_TERMINADO")
        s.add_all([lote, articulo])
        s.flush()
        s.add(EntregaMaterialOP(op_id=op.id_op, lote_id=lote.id, cantidad_entregada=3.5,
                                entregado_por=id_prueba("almacen"), recibido_por_produccion=id_prueba("jefe_produccion")))
        s.add(MovimientoInventario(
            id_articulo=articulo.id_articulo, id_lote=lote.id, tipo_movimiento="101", cantidad=2, costo_unitario=10,
            valor_total=20, saldo_cantidad=2, referencia_tipo="OP", referencia_id="OP-MAPA-1", codigo_op="OP-MAPA-1",
            registrado_por="almacen",
        ))
        s.commit()

    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol):
    t = create_access_token({"sub": str(id_prueba(rol.lower())), "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def mapa(client, rol, codigo="OP-MAPA-1"):
    return client.get(f"{RUTA}/{codigo}", headers=token(rol))


def tipos(datos):
    return {nodo["tipo"] for nodo in datos["relaciones"]["nodos"]} if datos["relaciones"] else None


# --- Nodos y mapas por rol ----------------------------------------------------------------------

@pytest.mark.parametrize("rol, nodos, mapas, por_defecto", [
    (roles.VENTAS, {"OP", "PEDIDO", "COTIZACION", "CLIENTE"}, ["relaciones"], "relaciones"),
    (roles.JEFE_PRODUCCION, {"OP", "PEDIDO", "COTIZACION", "CLIENTE", "OP_PEDIDO", "PLANO", "ENTREGA_MATERIAL", "INGRESO_PT"},
     ["relaciones", "procesos"], "procesos"),
    (roles.COSTOS, {"OP", "PEDIDO", "COTIZACION", "ENTREGA_MATERIAL", "INGRESO_PT"}, ["relaciones", "procesos"], "relaciones"),
    (MEC, {"OP", "CLIENTE", "OP_PEDIDO"}, ["relaciones", "procesos"], "procesos"),
    (roles.GESTION_CALIDAD, {"OP", "CLIENTE"}, ["relaciones"], "relaciones"),
    (roles.DIBUJANTE, {"OP", "PLANO"}, ["relaciones"], "relaciones"),
    (roles.LIDER_DISENO, {"OP", "PLANO"}, ["relaciones"], "relaciones"),
    (roles.CALIDAD_PRODUCTO, {"OP", "PLANO"}, ["relaciones"], "relaciones"),
    (roles.DIRECTOR_PRODUCCION, None, ["procesos"], "procesos"),
])
def test_cada_rol_recibe_solo_sus_nodos_y_su_mapa_por_defecto(ctx, rol, nodos, mapas, por_defecto):
    client, _ = ctx
    respuesta = mapa(client, rol)

    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert (tipos(datos), datos["mapas"], datos["por_defecto"]) == (nodos, mapas, por_defecto)
    assert (datos["procesos"] is not None) == ("procesos" in mapas)


@pytest.mark.parametrize("rol", [roles.OPERARIO, roles.ADMIN, roles.CAPTURISTA_TIEMPOS])
def test_sin_mapa_permitido_recibe_403(ctx, rol):
    client, _ = ctx
    assert mapa(client, rol).status_code == 403


def test_el_rol_se_lee_de_la_base_y_no_del_token(ctx):
    client, _ = ctx
    t = create_access_token({"sub": str(id_prueba("operario")), "rol": roles.JEFE_PRODUCCION}, timedelta(minutes=5))
    assert client.get(f"{RUTA}/OP-MAPA-1", headers={"Authorization": f"Bearer {t}"}).status_code == 403


def test_el_lider_solo_ve_el_mapa_de_las_op_de_su_unidad(ctx):
    client, _ = ctx
    assert mapa(client, SER).status_code == 404
    assert mapa(client, SER, "OP-MAPA-2").status_code == 200


# --- Contenido de los nodos ---------------------------------------------------------------------

def nodo(datos, tipo):
    return next(n for n in datos["relaciones"]["nodos"] if n["tipo"] == tipo)


def test_valor_cotizado_solo_con_el_permiso(ctx):
    client, Sesion = ctx
    cotizacion = nodo(mapa(client, roles.VENTAS).json(), "COTIZACION")
    assert (cotizacion["etiqueta"], cotizacion["datos"]["valor_cotizado"]) == ("COT-MAPA-1", 1500000)

    with Sesion() as s:
        s.query(RolPermiso).filter_by(id_rol=roles.VENTAS).delete()
        s.commit()
    assert "valor_cotizado" not in nodo(mapa(client, roles.VENTAS).json(), "COTIZACION")["datos"]


def test_los_nodos_se_unen_a_la_op_o_al_pedido(ctx):
    client, _ = ctx
    datos = mapa(client, roles.JEFE_PRODUCCION).json()["relaciones"]
    aristas = {(a["desde"], a["hasta"]) for a in datos["aristas"]}

    assert {("op", "pedido"), ("pedido", "cotizacion"), ("pedido", "cliente"), ("pedido", "op:OP-MAPA-2")} <= aristas
    # Sin el nodo de pedido, el cliente cuelga de la OP
    lider = mapa(client, MEC).json()["relaciones"]
    assert ("op", "cliente") in {(a["desde"], a["hasta"]) for a in lider["aristas"]}


def test_recibos_de_produccion_sin_costos(ctx):
    client, _ = ctx
    datos = mapa(client, roles.COSTOS).json()
    entrega, ingreso = nodo(datos, "ENTREGA_MATERIAL"), nodo(datos, "INGRESO_PT")

    assert (entrega["etiqueta"], entrega["datos"]["numero_colada"], entrega["datos"]["cantidad"]) == ("LOTE-MAPA-1", "COL-1", 3.5)
    assert (ingreso["etiqueta"], ingreso["datos"]["cantidad"]) == ("PT-MAPA-1", 2)
    assert not {"costo_unitario", "valor_total"} & set(ingreso["datos"])


# --- Mapa de procesos ---------------------------------------------------------------------------

def test_procesos_en_orden_con_maquina_y_operario(ctx):
    client, _ = ctx
    procesos = mapa(client, roles.JEFE_PRODUCCION).json()["procesos"]

    assert [(n["etiqueta"], n["datos"]["secuencia"]) for n in procesos["nodos"]] == [("Torneado", 10), ("Fresado", 20)]
    torneado = procesos["nodos"][0]["datos"]
    assert (torneado["maquinas"], torneado["operarios"]) == (["TORNO-01"], ["operario.uno"])
    assert [(a["desde"], a["hasta"]) for a in procesos["aristas"]] == [(procesos["nodos"][0]["id"], procesos["nodos"][1]["id"])]


@pytest.mark.parametrize("rol, ve", [
    (roles.JEFE_PRODUCCION, True), (roles.COSTOS, True), (MEC, False), (roles.DIRECTOR_PRODUCCION, False),
])
def test_los_tiempos_solo_para_costos_y_jefe(ctx, rol, ve):
    client, _ = ctx
    procesos = mapa(client, rol).json()["procesos"]
    torneado = procesos["nodos"][0]["datos"]

    assert procesos["con_tiempos"] is ve
    if ve:
        assert (torneado["minutos_operacion"], torneado["minutos_setup"]) == (45, 15)
    else:
        assert not {"minutos_operacion", "minutos_setup"} & set(torneado)
        # El mismo mapa: mismas operaciones, máquinas y operarios
        assert (torneado["maquinas"], torneado["operarios"]) == (["TORNO-01"], ["operario.uno"])
