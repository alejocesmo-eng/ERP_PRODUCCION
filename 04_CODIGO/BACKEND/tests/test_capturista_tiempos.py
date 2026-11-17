# tests/test_capturista_tiempos.py
"""
Perfil CAPTURISTA_TIEMPOS (migración 29): solo registra tiempos de operaciones de OP, en cualquier
unidad, con PERM_TIEMPOS_REGISTRAR (que LIDER_MECANIZADOS también tiene desde la migración 30). La dependencia global alcance_por_rol le cierra el resto
(cliente, planos, costos, valor cotizado, unidad, liberación, cierre, retención) aunque la ruta
solo pida token, y OcultarCamposPorRol le quita de la cola de sublotes todo lo del plano. El rol se
lee de la base, no del token.

SQLite en memoria con override de get_db; aplicación FastAPI mínima con la misma dependencia global
que app.main (no se importa app.main).
"""
import inspect
import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth, busqueda, costos, ordenes, produccion, tiempos_manuales, unidades_op, usuarios
from app.api.v1.endpoints.produccion import cola_router
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Permiso, Plano, Rol, RolPermiso, Usuario
from app.db.models_produccion import OperacionOT, SubLoteOperacion
from app.services import acceso_bd
from tests.ayudantes_usuarios import datos_usuario, id_prueba

CAPTURISTA = roles.CAPTURISTA_TIEMPOS
REGISTRO_TIEMPOS = [
    "/api/v1/operaciones/setup/iniciar",
    "/api/v1/operaciones/mecanizado/conmutar",
    "/api/v1/operaciones/pausa/turno",
    "/api/v1/operaciones/sublotes/finalizar",
]
CERRADAS = [
    ("get", "/api/v1/ordenes/"),
    ("get", "/api/v1/ordenes/expediente/OP-1"),
    ("get", "/api/v1/costos/op/OP-1"),
    ("get", "/api/v1/busqueda/?q=op"),
    ("post", "/api/v1/unidades-op/OP-1/traslado"),
    ("patch", f"/api/v1/ordenes/{uuid.uuid4()}"),
    ("patch", "/api/v1/ordenes/liberar/OP-1"),
    ("post", "/api/v1/operaciones/sublotes/crear"),
]


def crear_app():
    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.add_middleware(acceso_bd.OcultarCamposPorRol)
    app.include_router(auth.router, prefix="/api/v1/auth")
    app.include_router(usuarios.router, prefix="/api/v1/usuarios")
    app.include_router(busqueda.router, prefix="/api/v1/busqueda")
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")
    app.include_router(costos.router, prefix="/api/v1/costos")
    app.include_router(produccion.router, prefix="/api/v1/operaciones")
    app.include_router(cola_router, prefix="/api/v1/operaciones")
    app.include_router(unidades_op.router, prefix="/api/v1/unidades-op")
    app.include_router(tiempos_manuales.router, prefix="/api/v1/tiempos-manuales")
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
    with Sesion() as s:
        todos = (CAPTURISTA, roles.JEFE_PRODUCCION, roles.LIDER_MECANIZADOS, roles.VENTAS)
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in todos)
        s.add(Permiso(id_permiso=acceso_bd.PERMISO_TIEMPOS, modulo="PRODUCCION"))
        # Como las migraciones 29 y 30
        s.add_all(RolPermiso(id_rol=rol, id_permiso=acceso_bd.PERMISO_TIEMPOS)
                  for rol in (CAPTURISTA, roles.JEFE_PRODUCCION, roles.LIDER_MECANIZADOS))
        s.add_all(
            Usuario(**datos_usuario(f"{rol.lower()}"), password_hash="!SIN_CLAVE", nombre_completo=rol, id_rol=rol)
            for rol in todos
        )
        plano = Plano(codigo_plano="PLN-CAP-1", material_requerido="Acero 1045", archivo_url="/static/planos/PLN-CAP-1.pdf")
        s.add(plano)
        s.flush()
        operacion = OperacionOT(id_plano=plano.id_plano, codigo_op="OP-CAP-1", codigo_plano="PLN-CAP-1",
                                secuencia_paso=10, nombre_proceso="Torneado", cantidad_total_orden=4)
        s.add(operacion)
        s.flush()
        s.add(SubLoteOperacion(id_operacion=operacion.id_operacion, cantidad_asignada=4, operario_nombre="Operario",
                               maquina_codigo="CNC-1"))
        s.commit()
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol, rol_en_token=None):
    t = create_access_token({"sub": str(id_prueba(f"{rol.lower()}")), "rol": rol_en_token or rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def llamar(client, metodo, ruta, cabeceras):
    extra = {} if metodo == "get" else {"json": {}}
    return getattr(client, metodo)(ruta, headers=cabeceras, **extra)


@pytest.mark.parametrize("ruta", REGISTRO_TIEMPOS)
def test_el_capturista_registra_tiempos(ctx, ruta):
    # Cuerpo vacío: pasa el filtro y el permiso y llega a la validación del endpoint
    assert ctx.post(ruta, json={}, headers=token(CAPTURISTA)).status_code == 422


@pytest.mark.parametrize("ruta", REGISTRO_TIEMPOS)
def test_el_lider_de_mecanizados_registra_tiempos(ctx, ruta):
    assert ctx.post(ruta, json={}, headers=token(roles.LIDER_MECANIZADOS)).status_code == 422


@pytest.mark.parametrize("ruta", REGISTRO_TIEMPOS)
def test_sin_el_permiso_no_se_registran_tiempos(ctx, ruta):
    assert ctx.post(ruta, json={}, headers=token(roles.VENTAS)).status_code == 403


@pytest.mark.parametrize("metodo, ruta", CERRADAS, ids=[r for _, r in CERRADAS])
def test_el_capturista_no_entra_a_nada_mas(ctx, metodo, ruta):
    respuesta = llamar(ctx, metodo, ruta, token(CAPTURISTA))

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Su rol solo registra tiempos de operaciones."


def test_el_capturista_ve_su_cola_y_su_sesion(ctx):
    assert ctx.get("/api/v1/operaciones/sublotes", headers=token(CAPTURISTA)).status_code == 200
    assert ctx.get("/api/v1/usuarios/me", headers=token(CAPTURISTA)).status_code == 200
    alcance = ctx.get("/api/v1/busqueda/alcance", headers=token(CAPTURISTA)).json()
    assert alcance["tipos"] == [] and alcance["costos"] is False and alcance["valor_cotizado"] is False


def test_la_cola_del_capturista_no_trae_nada_del_plano(ctx):
    (capturista,) = ctx.get("/api/v1/operaciones/sublotes", headers=token(CAPTURISTA)).json()
    (jefe,) = ctx.get("/api/v1/operaciones/sublotes", headers=token(roles.JEFE_PRODUCCION)).json()

    assert not acceso_bd.CAMPOS_PLANO & set(capturista)
    assert "PLN-CAP-1" not in str(capturista) and "Acero 1045" not in str(capturista)
    # Lo que necesita para registrar tiempos sigue ahí
    assert (capturista["codigo_op"], capturista["nombre_proceso"], capturista["maquina_codigo"],
            capturista["cantidad_asignada"]) == ("OP-CAP-1", "Torneado", "CNC-1", 4)
    # Otro rol sí recibe el plano
    assert jefe["codigo_plano"] == "PLN-CAP-1" and jefe["archivo_url"]


def test_los_demas_roles_no_cambian(ctx):
    assert ctx.get("/api/v1/ordenes/", headers=token(roles.JEFE_PRODUCCION)).status_code == 200


def test_el_filtro_usa_el_rol_de_la_base(ctx):
    # El token dice JEFE_PRODUCCION, pero en la base es CAPTURISTA_TIEMPOS: se cierra
    assert ctx.get("/api/v1/ordenes/", headers=token(CAPTURISTA, rol_en_token=roles.JEFE_PRODUCCION)).status_code == 403
    # El token dice CAPTURISTA_TIEMPOS, pero en la base es JEFE_PRODUCCION: no se cierra
    assert ctx.get("/api/v1/ordenes/", headers=token(roles.JEFE_PRODUCCION, rol_en_token=CAPTURISTA)).status_code == 200


def test_sin_token_sigue_respondiendo_401(ctx):
    assert ctx.get("/api/v1/ordenes/").status_code == 401
    assert ctx.get("/api/v1/ordenes/", headers={"Authorization": "Bearer no-es-un-jwt"}).status_code == 401


@pytest.mark.parametrize("metodo, ruta", sorted(acceso_bd.RUTAS_CAPTURISTA))
def test_las_rutas_del_capturista_existen(ctx, metodo, ruta):
    # Una ruta de la lista que no existe (o cambia de método) respondería 404 o 405
    assert ctx.request(metodo, ruta).status_code not in (404, 405)


def test_el_capturista_no_esta_en_ningun_grupo_de_acceso():
    grupos = {
        nombre: valor for nombre, valor in inspect.getmembers(roles)
        if nombre.startswith("ROLES_") and nombre not in ("ROLES_CATALOGO", "ROLES_ANTERIORES")
    }
    assert not [nombre for nombre, lista in grupos.items() if CAPTURISTA in lista]
    assert CAPTURISTA in roles.ROLES_CATALOGO and CAPTURISTA not in roles.TIPOS_BUSQUEDA_POR_ROL
