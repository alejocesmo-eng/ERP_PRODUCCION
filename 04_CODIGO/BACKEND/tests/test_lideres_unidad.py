# tests/test_lideres_unidad.py
"""
Líderes de unidad (reglas/permisos-por-rol-modulo.md del proyecto PRISMA; migraciones 27, 30 y 32):

- LIDER_MECANIZADOS cierra OP de cualquier unidad como respaldo del Jefe de Producción; no libera
  ni ve costos ni valor cotizado; ve cliente e histórico y, en el expediente, las OP del mismo pedido.
- LIDER_SERVICIOS ve solo las OP de su área (Servicios), también desde que se crean (aún sin unidad,
  si los planos vigentes de su producto son de Servicios), con datos técnicos; ve cliente e
  histórico; sin costos ni valor cotizado; cierra solo OP de su área; registra avance y tiempos con
  PERM_TIEMPOS_REGISTRAR, que ADMIN asigna o retira desde Configuración de roles.
- Cambio de unidad: solo CALIDAD_PRODUCTO, con destino obligatorio. LIDER_MECANIZADOS y
  LIDER_SERVICIOS no cambian la unidad de la OP (403), aunque ven su historial de traslados.

El rol se lee de la base. SQLite en memoria con override de get_db; aplicación FastAPI mínima con la
misma dependencia global y el mismo middleware que app.main (no se importa app.main).
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import busqueda, configuracion_roles, ordenes, produccion, proyectos, unidades_op
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import (
    EstadoOPEnum, OrdenProduccion, Permiso, Plano, Producto, Proyecto, Rol, RolPermiso, Usuario,
)
from app.services import acceso_bd
from tests.ayudantes_usuarios import datos_usuario, id_prueba

MEC, SER = roles.LIDER_MECANIZADOS, roles.LIDER_SERVICIOS
ROLES_PRUEBA = [roles.ADMIN, roles.VENTAS, roles.JEFE_PRODUCCION, MEC, SER, roles.CALIDAD_PRODUCTO]
PERMISOS = {
    roles.ADMIN: [configuracion_roles.PERMISO_CONFIGURACION, acceso_bd.PERMISO_TIEMPOS],
    roles.VENTAS: [acceso_bd.PERMISO_VALOR_COTIZADO],
    roles.JEFE_PRODUCCION: ["PERM_OP_CERRAR", acceso_bd.PERMISO_TIEMPOS, acceso_bd.PERMISO_VALOR_COTIZADO,
                            acceso_bd.PERMISO_COSTOS],
    # Como las migraciones 27, 30 y 32
    MEC: ["PERM_OP_CERRAR", acceso_bd.PERMISO_TIEMPOS],
    SER: ["PERM_OP_CERRAR", acceso_bd.PERMISO_TIEMPOS],
}
REGISTRO_TIEMPOS = "/api/v1/operaciones/setup/iniciar"


def crear_app():
    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.add_middleware(acceso_bd.OcultarCamposPorRol)
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")
    app.include_router(unidades_op.router, prefix="/api/v1/unidades-op")
    app.include_router(busqueda.router, prefix="/api/v1/busqueda")
    app.include_router(proyectos.router, prefix="/api/v1/proyectos")
    app.include_router(produccion.router, prefix="/api/v1/operaciones")
    app.include_router(configuracion_roles.router, prefix="/api/v1/configuracion/roles")
    return app


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

    app = crear_app()
    app.dependency_overrides[get_db] = _get_db
    ids = {}
    with Sesion() as s:
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in ROLES_PRUEBA)
        s.add_all(Permiso(id_permiso=p, modulo="PRUEBA") for p in {p for lista in PERMISOS.values() for p in lista})
        s.add_all(RolPermiso(id_rol=rol, id_permiso=p) for rol, lista in PERMISOS.items() for p in lista)
        s.add_all(
            Usuario(**datos_usuario(f"{rol.lower()}"), password_hash="!SIN_CLAVE", nombre_completo=rol, id_rol=rol)
            for rol in ROLES_PRUEBA
        )
        pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido="PED-LID-1", codigo_proyecto="PED-LID-1",
                          cliente_nombre="Cliente ficticio", requisitos_cliente="Según plano", confirmado=True,
                          cotizacion_total=1234567)
        s.add(pedido)
        productos = {}
        for clave, unidad_planta in (("SER", "Servicios"), ("MEC", "Mecanizados")):
            producto = Producto(id_producto=uuid.uuid4(), codigo_rn=f"RN-{clave}", descripcion=f"Producto {clave}")
            s.add(producto)
            s.flush()
            s.add(Plano(codigo_plano=f"PLN-{clave}", id_producto=producto.id_producto, unidad_planta=unidad_planta,
                        material_requerido="Acero 1045", archivo_url=f"/static/planos/PLN-{clave}.pdf"))
            productos[clave] = producto.id_producto
        s.flush()
        ops = {
            # codigo: (unidad_actual, estado, producto)
            "OP-SER": ("SERVICIOS", EstadoOPEnum.EN_PRODUCCION, "SER"),
            "OP-MEC": ("MECANIZADOS", EstadoOPEnum.EN_PRODUCCION, "MEC"),
            # Recién creadas, sin unidad: la de Servicios la ve su líder desde ya
            "OP-SER-NUEVA": ("SIN_ASIGNAR", EstadoOPEnum.BORRADOR, "SER"),
            "OP-MEC-NUEVA": (None, EstadoOPEnum.BORRADOR, "MEC"),
        }
        for codigo, (unidad, estado, producto) in ops.items():
            op = OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op=codigo, cantidad_fabricar=1,
                                 unidad_actual=unidad, estado=estado, id_producto=productos[producto])
            s.add(op)
            s.flush()
            ids[codigo] = op.id_op
        ids["pedido"] = pedido.id_proyecto
        s.commit()

    with TestClient(app) as client:
        yield client, Sesion, ids
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol, rol_en_token=None):
    t = create_access_token({"sub": str(id_prueba(f"{rol.lower()}")), "rol": rol_en_token or rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def codigos_visibles(client, rol):
    respuesta = client.get("/api/v1/ordenes/", headers=token(rol))
    assert respuesta.status_code == 200, respuesta.text
    return {op["codigo_op"] for op in respuesta.json()}


def cerrar(client, ids, codigo, rol):
    # Resumen del cierre: valida rol y área igual que el cierre (las demás condiciones, en
    # tests/test_cierre_op.py)
    return client.get(f"/api/v1/ordenes/{codigo}/cierre", headers=token(rol))


# --- Visibilidad ------------------------------------------------------------------------------

def test_lider_de_servicios_ve_solo_su_area_desde_que_se_crean(ctx):
    client, _, _ = ctx
    assert codigos_visibles(client, SER) == {"OP-SER", "OP-SER-NUEVA"}


def test_lider_de_mecanizados_ve_las_op_al_llegar_a_su_unidad(ctx):
    client, _, _ = ctx
    assert codigos_visibles(client, MEC) == {"OP-MEC"}


def test_expediente_con_datos_tecnicos_para_lider_de_servicios(ctx):
    client, _, _ = ctx
    for codigo in ("OP-SER", "OP-SER-NUEVA"):
        respuesta = client.get(f"/api/v1/ordenes/expediente/{codigo}", headers=token(SER))
        assert respuesta.status_code == 200, respuesta.text
        (plano,) = respuesta.json()["planos"]
        assert (plano["codigo_plano"], plano["material_requerido"]) == ("PLN-SER", "Acero 1045")
    for codigo in ("OP-MEC", "OP-MEC-NUEVA"):
        assert client.get(f"/api/v1/ordenes/expediente/{codigo}", headers=token(SER)).status_code == 404


def test_la_busqueda_del_lider_de_servicios_solo_trae_su_area(ctx):
    client, _, _ = ctx
    respuesta = client.get("/api/v1/busqueda/?q=OP-", headers=token(SER)).json()

    assert {r["codigo"] for r in respuesta["resultados"] if r["tipo"] == roles.BUSQUEDA_OP} == {"OP-SER", "OP-SER-NUEVA"}


@pytest.mark.parametrize("rol", [MEC, SER])
def test_los_lideres_ven_cliente_e_historico_sin_costos_ni_valor_cotizado(ctx, rol):
    client, _, _ = ctx
    alcance = client.get("/api/v1/busqueda/alcance", headers=token(rol)).json()

    assert set(alcance["tipos"]) == {roles.BUSQUEDA_OP, roles.BUSQUEDA_CLIENTE}
    assert alcance["expediente_op"] is True
    assert alcance["costos"] is False and alcance["valor_cotizado"] is False
    clientes = client.get("/api/v1/busqueda/?q=Cliente", headers=token(rol)).json()
    assert clientes["tipos"] == alcance["tipos"]
    assert rol in roles.ROLES_LECTURA and rol in roles.ROLES_HISTORIAL_CONSULTA and rol in roles.ROLES_TRAZABILIDAD


@pytest.mark.parametrize("rol", [MEC, SER])
def test_los_lideres_no_reciben_el_valor_cotizado_del_pedido(ctx, rol):
    client, _, ids = ctx
    lider = client.get(f"/api/v1/proyectos/{ids['pedido']}/expediente", headers=token(rol))
    ventas = client.get(f"/api/v1/proyectos/{ids['pedido']}/expediente", headers=token(roles.VENTAS))

    assert lider.status_code == ventas.status_code == 200
    assert "1234567" not in lider.text and "valor_total_cotizado" not in lider.text
    assert ventas.json()["valor_total_cotizado"] == 1234567
    # El cliente sí lo ven
    assert "Cliente ficticio" in lider.text


def test_el_expediente_trae_las_op_del_mismo_pedido(ctx):
    client, _, _ = ctx
    expediente = client.get("/api/v1/ordenes/expediente/OP-MEC", headers=token(MEC)).json()

    hermanas = {op["codigo_op"]: op for op in expediente["ops_del_pedido"]}
    assert set(hermanas) == {"OP-SER", "OP-SER-NUEVA", "OP-MEC-NUEVA"}
    assert hermanas["OP-SER"]["unidad_actual"] == "SERVICIOS"
    assert expediente["pedido"]["cliente"] == "Cliente ficticio"
    assert not {"costo", "valor_total_cotizado", "cotizacion_total"} & set(hermanas["OP-SER"])


# --- Cierre -----------------------------------------------------------------------------------

@pytest.mark.parametrize("codigo", ["OP-MEC", "OP-SER"])
def test_lider_de_mecanizados_cierra_op_de_cualquier_unidad(ctx, codigo):
    client, _, ids = ctx
    respuesta = cerrar(client, ids, codigo, MEC)
    assert respuesta.status_code == 200, respuesta.text


def test_lider_de_servicios_cierra_solo_op_de_su_area(ctx):
    client, _, ids = ctx
    assert cerrar(client, ids, "OP-SER", SER).status_code == 200
    respuesta = cerrar(client, ids, "OP-MEC", SER)
    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Solo puede cerrar OP de su área."


def test_el_cierre_por_area_usa_el_rol_de_la_base(ctx):
    client, _, ids = ctx
    # El token dice JEFE_PRODUCCION, pero en la base es LIDER_SERVICIOS
    t = create_access_token({"sub": str(id_prueba("lider_servicios")), "rol": roles.JEFE_PRODUCCION}, timedelta(minutes=5))
    respuesta = client.get("/api/v1/ordenes/OP-MEC/cierre", headers={"Authorization": f"Bearer {t}"})
    assert respuesta.status_code == 403


@pytest.mark.parametrize("rol", [MEC, SER])
def test_los_lideres_no_liberan(ctx, rol):
    client, _, _ = ctx
    respuesta = client.patch("/api/v1/ordenes/liberar/OP-SER", json={}, headers=token(rol))
    assert respuesta.status_code == 403


# --- Avance y tiempos -------------------------------------------------------------------------

def test_lider_de_servicios_registra_tiempos_y_admin_lo_decide_desde_configuracion(ctx):
    client, _, _ = ctx
    # Cuerpo vacío: pasa el permiso y llega a la validación del endpoint
    assert client.post(REGISTRO_TIEMPOS, json={}, headers=token(SER)).status_code == 422

    ruta = f"/api/v1/configuracion/roles/{SER}/permisos"
    admin = token(roles.ADMIN)
    assert client.put(ruta, json={"permisos": ["PERM_OP_CERRAR"]}, headers=admin).status_code == 200
    assert client.post(REGISTRO_TIEMPOS, json={}, headers=token(SER)).status_code == 403

    assert client.put(ruta, json={"permisos": ["PERM_OP_CERRAR", acceso_bd.PERMISO_TIEMPOS]}, headers=admin).status_code == 200
    assert client.post(REGISTRO_TIEMPOS, json={}, headers=token(SER)).status_code == 422


# --- Cambio de unidad -------------------------------------------------------------------------

def trasladar(client, rol, codigo, cuerpo):
    return client.post(f"/api/v1/unidades-op/{codigo}/traslado", json=cuerpo, headers=token(rol))


@pytest.mark.parametrize("rol, codigo", [
    (SER, "OP-SER"), (SER, "OP-MEC"), (SER, "OP-SER-NUEVA"), (MEC, "OP-MEC"), (MEC, "OP-SER"),
])
@pytest.mark.parametrize("cuerpo", [{"unidad_destino": "TERCERO"}, {"unidad_destino": "DESPACHO"}, {}])
def test_los_lideres_no_cambian_la_unidad_en_ningun_destino(ctx, rol, codigo, cuerpo):
    client, _, _ = ctx
    respuesta = trasladar(client, rol, codigo, cuerpo)

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Su rol no puede cambiar la unidad de la OP."


@pytest.mark.parametrize("rol, codigo", [(SER, "OP-SER"), (MEC, "OP-MEC")])
def test_los_lideres_ven_el_historial_de_traslados_sin_poder_trasladar(ctx, rol, codigo):
    client, _, _ = ctx
    historial = client.get(f"/api/v1/unidades-op/{codigo}/traslados", headers=token(rol))

    assert historial.status_code == 200, historial.text
    assert trasladar(client, rol, codigo, {"unidad_destino": "DESPACHO"}).status_code == 403


def test_el_destino_es_obligatorio(ctx):
    client, _, _ = ctx
    assert trasladar(client, roles.CALIDAD_PRODUCTO, "OP-SER", {}).status_code == 422


@pytest.mark.parametrize("rol", [roles.ADMIN, roles.JEFE_PRODUCCION, roles.VENTAS])
def test_otros_roles_no_cambian_la_unidad(ctx, rol):
    client, _, _ = ctx
    assert trasladar(client, rol, "OP-SER", {"unidad_destino": "DESPACHO"}).status_code == 403


def test_calidad_de_producto_traslada_cualquier_op(ctx):
    client, _, _ = ctx
    assert trasladar(client, roles.CALIDAD_PRODUCTO, "OP-MEC", {"unidad_destino": "SERVICIOS"}).status_code == 200


def test_cambia_la_unidad_solo_calidad_de_producto():
    assert roles.ROLES_CAMBIAR_UNIDAD_OP == [roles.CALIDAD_PRODUCTO]
    assert MEC not in roles.LIDERES_CAMBIAN_UNIDAD and SER not in roles.LIDERES_CAMBIAN_UNIDAD
    assert roles.ROLES_CIERRE_SOLO_SU_UNIDAD == [SER]
