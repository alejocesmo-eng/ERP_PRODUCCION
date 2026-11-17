# tests/test_tiempos_manuales.py
"""
Carga manual de tiempos desde la orden de fabricación (app/api/v1/tiempos_manuales.py, migración 33;
reglas/carga-tiempos-manual.md del proyecto PRISMA):
- Registran CAPTURISTA_TIEMPOS, los líderes de unidad (solo en las OP de su área) y JEFE_PRODUCCION,
  con PERM_TIEMPOS_REGISTRAR; OPERARIO no, aunque tenga el permiso. El rol se lee de la base.
- Proceso de la ruta de la OP, máquina del catálogo y operario asignado a esa máquina en
  Configuración; setup opcional; fecha de hoy si no se indica. No se validan solapamientos.
- Se agregan y corrigen mientras la OP no esté cerrada; no se borran; la corrección pide motivo y
  guarda los valores anteriores.
- Los costos de los tiempos solo los ven COSTOS y JEFE_PRODUCCION.

SQLite en memoria con override de get_db; aplicación FastAPI mínima con la misma dependencia global
y el mismo middleware que app.main (no se importa app.main).
"""
import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import configuracion_roles, costos, maquina_operarios, tiempos_manuales
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import (
    CentroTrabajo, CorreccionTiempoManual, EquipoPlanta, EstadoOPEnum, OrdenProduccion, Permiso, Plano, Proyecto,
    RegistroTiemposProduccion, Rol, RolPermiso, Usuario,
)
from app.db.models_produccion import OperacionOT
from app.services import acceso_bd
from tests.ayudantes_usuarios import datos_usuario, id_prueba

MEC, SER, CAP = roles.LIDER_MECANIZADOS, roles.LIDER_SERVICIOS, roles.CAPTURISTA_TIEMPOS
REGISTRAN = [CAP, MEC, SER, roles.JEFE_PRODUCCION, roles.OPERARIO, roles.ADMIN]
ROLES_PRUEBA = [*REGISTRAN, roles.COSTOS, roles.GESTION_CALIDAD, roles.VENTAS]
PERMISOS = {
    **{rol: [acceso_bd.PERMISO_TIEMPOS] for rol in REGISTRAN},
    roles.ADMIN: [acceso_bd.PERMISO_TIEMPOS, configuracion_roles.PERMISO_CONFIGURACION],
    roles.COSTOS: [acceso_bd.PERMISO_COSTOS],
    roles.JEFE_PRODUCCION: [acceso_bd.PERMISO_TIEMPOS, acceso_bd.PERMISO_COSTOS],
    # Tiene el permiso de costos del expediente, pero no ve los de tiempos
    roles.GESTION_CALIDAD: [acceso_bd.PERMISO_COSTOS],
}
RUTA = "/api/v1/tiempos-manuales"
# Usuarios de los operarios (se entra y se eligen por usuario, no por correo)
OPERARIOS = ["operario.uno", "operario.dos"]


def crear_app():
    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.add_middleware(acceso_bd.OcultarCamposPorRol)
    app.include_router(tiempos_manuales.router, prefix=RUTA)
    app.include_router(maquina_operarios.router, prefix="/api/v1/configuracion/maquinas")
    app.include_router(costos.router, prefix="/api/v1/costos")
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
        s.add_all(
            Usuario(**datos_usuario(usuario), password_hash="!SIN_CLAVE", nombre_completo=f"Operario {indice}",
                    id_rol=roles.OPERARIO)
            for indice, usuario in enumerate(OPERARIOS, start=1)
        )
        s.add(CentroTrabajo(codigo_centro="CT-TORNO", tarifa_hora_mecanizado=60, tarifa_hora_setup=30))
        s.flush()
        s.add_all([
            EquipoPlanta(codigo_maquina="TORNO-01", nombre="Torno ficticio", centro_trabajo_asociado="CT-TORNO"),
            EquipoPlanta(codigo_maquina="FRESA-01", nombre="Fresadora ficticia"),
        ])
        pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido="PED-TM-1", codigo_proyecto="PED-TM-1",
                          cliente_nombre="Cliente ficticio", requisitos_cliente="Según plano", confirmado=True)
        s.add(pedido)
        s.flush()
        plano = Plano(codigo_plano="PLN-TM-1", id_proyecto=pedido.id_proyecto, unidad_planta="Mecanizados")
        s.add(plano)
        s.flush()
        for codigo, unidad, estado in (
            ("OP-MEC", "MECANIZADOS", EstadoOPEnum.EN_PRODUCCION),
            ("OP-SER", "SERVICIOS", EstadoOPEnum.EN_PRODUCCION),
            ("OP-CERRADA", "MECANIZADOS", EstadoOPEnum.CERRADA),
        ):
            s.add(OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op=codigo, cantidad_fabricar=1,
                                  unidad_actual=unidad, estado=estado))
            proceso = OperacionOT(id_plano=plano.id_plano, codigo_op=codigo, codigo_plano=plano.codigo_plano,
                                  secuencia_paso=10, nombre_proceso="Torneado")
            s.add(proceso)
            s.flush()
            ids[codigo] = str(proceso.id_operacion)
        s.commit()

    with TestClient(app) as client:
        # Operario 1 en el torno y operario 2 en la fresa, desde Configuración
        assert client.put("/api/v1/configuracion/maquinas/TORNO-01/operarios", json={"usuarios": [OPERARIOS[0]]},
                          headers=token(roles.ADMIN)).status_code == 200
        assert client.put("/api/v1/configuracion/maquinas/FRESA-01/operarios", json={"usuarios": [OPERARIOS[1]]},
                          headers=token(roles.ADMIN)).status_code == 200
        yield client, Sesion, ids
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol):
    t = create_access_token({"sub": str(id_prueba(f"{rol.lower()}")), "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def fila(ids, codigo="OP-MEC", **cambios):
    return {
        "codigo_op": codigo, "id_operacion": ids[codigo], "codigo_maquina": "TORNO-01", "operario": OPERARIOS[0],
        "minutos_operacion": 45, "minutos_setup": 15, "fecha": "2026-11-16", **cambios,
    }


def agregar(client, rol, cuerpo):
    return client.post(RUTA, json=cuerpo, headers=token(rol))


def corregir(client, rol, cuerpo):
    return client.post(f"{RUTA}/corregir", json=cuerpo, headers=token(rol))


def parrilla(client, rol, codigo="OP-MEC"):
    return client.get(RUTA, params={"codigo_op": codigo}, headers=token(rol))


# --- Quién registra ---------------------------------------------------------------------------

@pytest.mark.parametrize("rol", [CAP, MEC, roles.JEFE_PRODUCCION])
def test_registran_el_capturista_el_lider_y_el_jefe(ctx, rol):
    client, Sesion, ids = ctx
    respuesta = agregar(client, rol, fila(ids))

    assert respuesta.status_code == 201, respuesta.text
    with Sesion() as s:
        registro = s.query(RegistroTiemposProduccion).one()
        assert (registro.origen, registro.tipo_tiempo, registro.estacion_id) == ("MANUAL", "MECANIZADO", "TORNO-01")
        assert (registro.segundos_ejecutados, registro.segundos_setup) == (45 * 60, 15 * 60)
        assert registro.fecha_trabajo == date(2026, 11, 16)
        assert registro.pausado_por_turno is False
        # Solo hay fecha: inicio a las 00:00 y fin = inicio + 45 min de operación (el setup no cuenta)
        inicio, fin = (valor.replace(tzinfo=None) for valor in (registro.fecha_hora_inicio, registro.fecha_hora_fin))
        assert (inicio, fin) == (datetime(2026, 11, 16), datetime(2026, 11, 16, 0, 45))
        # Operario y autor se guardan con el identificador interno
        assert registro.operario_id == str(id_prueba(OPERARIOS[0])) and registro.registrado_por == str(id_prueba(rol.lower()))


def test_el_lider_de_servicios_registra_en_su_area(ctx):
    client, _, ids = ctx
    assert agregar(client, SER, fila(ids, "OP-SER")).status_code == 201


@pytest.mark.parametrize("rol, codigo", [(MEC, "OP-SER"), (SER, "OP-MEC")])
def test_el_lider_no_registra_fuera_de_su_area(ctx, rol, codigo):
    client, _, ids = ctx
    assert agregar(client, rol, fila(ids, codigo)).status_code == 404


@pytest.mark.parametrize("rol", [roles.OPERARIO, roles.COSTOS, roles.VENTAS, roles.GESTION_CALIDAD])
def test_otros_roles_no_agregan_tiempos(ctx, rol):
    client, Sesion, ids = ctx
    assert agregar(client, rol, fila(ids)).status_code == 403
    with Sesion() as s:
        assert s.query(RegistroTiemposProduccion).count() == 0


@pytest.mark.parametrize("rol", [roles.OPERARIO, roles.VENTAS, roles.GESTION_CALIDAD])
def test_operario_y_roles_sin_permiso_no_ven_la_parrilla(ctx, rol):
    client, _, _ = ctx
    assert parrilla(client, rol).status_code == 403


# --- Datos de la fila -------------------------------------------------------------------------

def test_setup_opcional_y_fecha_de_hoy_por_defecto(ctx):
    client, Sesion, ids = ctx
    cuerpo = fila(ids)
    del cuerpo["minutos_setup"], cuerpo["fecha"]

    assert agregar(client, CAP, cuerpo).status_code == 201
    with Sesion() as s:
        registro = s.query(RegistroTiemposProduccion).one()
        assert registro.segundos_setup is None and registro.fecha_trabajo == date.today()


@pytest.mark.parametrize("cambios, mensaje", [
    ({"codigo_maquina": "NO-EXISTE"}, "catálogo de máquinas"),
    ({"operario": OPERARIOS[1]}, "no está asignado a esa máquina"),
])
def test_maquina_del_catalogo_y_operario_asignado_a_ella(ctx, cambios, mensaje):
    client, _, ids = ctx
    respuesta = agregar(client, CAP, fila(ids, **cambios))
    assert respuesta.status_code == 422 and mensaje in respuesta.json()["detail"]


def test_el_proceso_es_de_la_ruta_de_la_op(ctx):
    client, _, ids = ctx
    respuesta = agregar(client, CAP, fila(ids, id_operacion=ids["OP-SER"]))
    assert respuesta.status_code == 422 and "ruta de la OP" in respuesta.json()["detail"]


@pytest.mark.parametrize("cambios", [{"minutos_operacion": 0}, {"minutos_setup": -1}])
def test_minutos_validos(ctx, cambios):
    client, _, ids = ctx
    assert agregar(client, CAP, fila(ids, **cambios)).status_code == 422


def test_no_se_validan_solapamientos(ctx):
    client, Sesion, ids = ctx
    for _ in range(2):
        assert agregar(client, CAP, fila(ids)).status_code == 201
    with Sesion() as s:
        assert s.query(RegistroTiemposProduccion).count() == 2


def test_la_op_cerrada_no_recibe_tiempos(ctx):
    client, _, ids = ctx
    respuesta = agregar(client, CAP, fila(ids, "OP-CERRADA"))
    assert respuesta.status_code == 409 and respuesta.json()["detail"] == tiempos_manuales.MENSAJE_OP_CERRADA


# --- Correcciones -----------------------------------------------------------------------------

def test_la_correccion_pide_motivo_y_guarda_los_valores_anteriores(ctx):
    client, Sesion, ids = ctx
    id_registro = agregar(client, CAP, fila(ids)).json()["id_registro"]
    cambio = {**fila(ids, minutos_operacion=50), "id_registro": id_registro}
    del cambio["codigo_op"]

    sin_motivo = corregir(client, MEC, {**cambio, "motivo": "  "})
    assert sin_motivo.status_code == 422 and sin_motivo.json()["detail"] == tiempos_manuales.MENSAJE_SIN_MOTIVO

    assert corregir(client, MEC, {**cambio, "motivo": "Se digitó mal el tiempo"}).status_code == 200
    with Sesion() as s:
        registro = s.query(RegistroTiemposProduccion).one()
        assert registro.segundos_ejecutados == 50 * 60
        assert registro.fecha_hora_fin.replace(tzinfo=None) == datetime(2026, 11, 16, 0, 50)
        correccion = s.query(CorreccionTiempoManual).one()
        assert correccion.motivo == "Se digitó mal el tiempo" and correccion.corregido_por == str(id_prueba("lider_mecanizados"))
        assert correccion.valores_anteriores["minutos_operacion"] == 45
        assert correccion.valores_nuevos["minutos_operacion"] == 50

    historial = parrilla(client, CAP).json()["registros"][0]["correcciones"]
    assert [c["motivo"] for c in historial] == ["Se digitó mal el tiempo"]


def test_una_correccion_sin_cambios_no_se_guarda(ctx):
    client, Sesion, ids = ctx
    id_registro = agregar(client, CAP, fila(ids)).json()["id_registro"]
    cambio = {**fila(ids), "id_registro": id_registro, "motivo": "Revisión"}
    del cambio["codigo_op"]

    assert corregir(client, CAP, cambio).status_code == 422
    with Sesion() as s:
        assert s.query(CorreccionTiempoManual).count() == 0


def test_no_se_corrige_si_la_op_esta_cerrada(ctx):
    client, Sesion, ids = ctx
    id_registro = agregar(client, CAP, fila(ids)).json()["id_registro"]
    with Sesion() as s:
        s.query(OrdenProduccion).filter_by(codigo_op="OP-MEC").one().estado = EstadoOPEnum.CERRADA
        s.commit()
    cambio = {**fila(ids, minutos_operacion=50), "id_registro": id_registro, "motivo": "Ajuste"}
    del cambio["codigo_op"]

    assert corregir(client, CAP, cambio).status_code == 409
    assert agregar(client, CAP, fila(ids)).status_code == 409


def test_no_hay_ruta_para_borrar(ctx):
    client, _, ids = ctx
    id_registro = agregar(client, CAP, fila(ids)).json()["id_registro"]
    assert client.delete(f"{RUTA}/{id_registro}", headers=token(CAP)).status_code in (404, 405)


def test_operario_no_corrige(ctx):
    client, _, ids = ctx
    id_registro = agregar(client, CAP, fila(ids)).json()["id_registro"]
    cambio = {**fila(ids, minutos_operacion=50), "id_registro": id_registro, "motivo": "Ajuste"}
    del cambio["codigo_op"]
    assert corregir(client, roles.OPERARIO, cambio).status_code == 403


# --- Parrilla y costos ------------------------------------------------------------------------

def test_la_parrilla_trae_procesos_maquinas_y_operarios_asignados(ctx):
    client, _, ids = ctx
    agregar(client, CAP, fila(ids))
    datos = parrilla(client, CAP).json()

    assert datos["puede_registrar"] is True and datos["op_cerrada"] is False
    assert [p["nombre_proceso"] for p in datos["procesos"]] == ["Torneado"]
    operarios = {m["codigo_maquina"]: [o["usuario"] for o in m["operarios"]] for m in datos["maquinas"]}
    assert operarios == {"FRESA-01": [OPERARIOS[1]], "TORNO-01": [OPERARIOS[0]]}
    (registro,) = datos["registros"]
    assert (registro["proceso"], registro["minutos_operacion"], registro["minutos_setup"]) == ("Torneado", 45, 15)
    assert (registro["operario"], registro["operario_nombre"]) == (OPERARIOS[0], "Operario 1")
    # registrado_por se muestra con el usuario, no con el identificador interno
    assert registro["registrado_por"] == "capturista_tiempos"


@pytest.mark.parametrize("rol, ve", [
    (roles.COSTOS, True), (roles.JEFE_PRODUCCION, True), (CAP, False), (MEC, False), (roles.ADMIN, False),
])
def test_los_costos_de_tiempos_solo_para_costos_y_jefe(ctx, rol, ve):
    client, _, ids = ctx
    agregar(client, CAP, fila(ids))
    datos = parrilla(client, rol).json()

    assert datos["ve_costos"] is ve
    (registro,) = datos["registros"]
    if ve:
        # 45 min a 60/h + 15 min de setup a 30/h
        assert registro["costo"] == 52.5
    else:
        assert "costo" not in registro


def test_costos_no_registra_pero_ve_la_parrilla(ctx):
    client, _, _ = ctx
    datos = parrilla(client, roles.COSTOS).json()
    assert datos["puede_registrar"] is False


def test_el_costo_de_la_op_suma_operacion_y_setup_manual_con_el_centro_de_la_maquina(ctx):
    client, _, ids = ctx
    agregar(client, CAP, fila(ids))

    respuesta = client.get("/api/v1/costos/liquidar/OP-MEC", headers=token(roles.COSTOS))
    assert respuesta.status_code == 200, respuesta.text
    tiempos = {(t["centro_trabajo"], t["tipo"]): t for t in respuesta.json()["detalle_tiempos"]}
    assert tiempos[("CT-TORNO", "MECANIZADO")]["costo_total"] == pytest.approx(45.0)
    assert tiempos[("CT-TORNO", "SETUP")]["costo_total"] == pytest.approx(7.5)


# --- Configuración de operarios por máquina ---------------------------------------------------

def test_solo_admin_asigna_operarios(ctx):
    client, _, _ = ctx
    respuesta = client.put("/api/v1/configuracion/maquinas/TORNO-01/operarios", json={"usuarios": OPERARIOS},
                           headers=token(roles.JEFE_PRODUCCION))
    assert respuesta.status_code == 403


def test_solo_se_asignan_operarios_activos(ctx):
    client, _, _ = ctx
    respuesta = client.put("/api/v1/configuracion/maquinas/TORNO-01/operarios",
                           json={"usuarios": ["jefe_produccion"]}, headers=token(roles.ADMIN))
    assert respuesta.status_code == 422


def test_la_asignacion_reemplaza_la_lista_de_la_maquina(ctx):
    client, _, _ = ctx
    ruta = "/api/v1/configuracion/maquinas/TORNO-01/operarios"
    assert client.put(ruta, json={"usuarios": [OPERARIOS[1]]}, headers=token(roles.ADMIN)).status_code == 200

    datos = client.get("/api/v1/configuracion/maquinas", headers=token(roles.ADMIN)).json()
    torno = next(m for m in datos["maquinas"] if m["codigo_maquina"] == "TORNO-01")
    assert [o["usuario"] for o in torno["operarios"]] == [OPERARIOS[1]]
    assert {o["usuario"] for o in datos["operarios_disponibles"]} >= set(OPERARIOS)
