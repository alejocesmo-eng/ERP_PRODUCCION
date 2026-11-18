# tests/test_cierre_op.py
"""
Cierre seguro de OP y cierre manual del pedido (reglas/cierre-op-seguro.md; Regla 6 de
reglas/pedido-cotizacion-cambios.md; app/services/cierre_op.py; migración 36):
- El servidor rechaza el cierre sin aprobación de Calidad de todas las piezas o con procesos sin
  tiempo cargado, aunque el botón esté visible.
- Confirmación escribiendo el número de la OP; el resumen trae OP, pedido, cliente, cantidad,
  total de tiempos y aprobación de Calidad.
- Motivo de al menos 15 caracteres para los líderes de respaldo; el Jefe no lo necesita.
- Historial con quién, estado previo y motivo; aviso al Jefe cuando cierra un líder de respaldo.
- Quién cierra: Jefe cualquier OP, LIDER_MECANIZADOS cualquiera, LIDER_SERVICIOS solo su área.
  Solo el Jefe reabre, con motivo, y nunca con el pedido cerrado.
- Pedido: solo el Jefe lo cierra, a mano, con todas sus OP cerradas y escribiendo su número. Un
  pedido CERRADO no se edita, no recibe OP nuevas y sus OP no cambian.
- El rol se lee de la base, no del token.

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

from app.api.v1 import ordenes, proyectos
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import (
    EstadoOPEnum, EstadoProyectoEnum, HistorialAccionesDocumento, OrdenProduccion, PedidoDetalle, Plano, Producto,
    Proyecto, RegistroTiemposProduccion, Rol, Usuario,
)
from app.db.models_calidad import InspeccionCalidad
from app.db.models_produccion import NotificacionLider, OperacionOT, TipoNotificacionEnum
from app.services import acceso_bd
from tests.ayudantes_usuarios import datos_usuario, id_prueba

JEFE, MEC, SER = roles.JEFE_PRODUCCION, roles.LIDER_MECANIZADOS, roles.LIDER_SERVICIOS
ROLES_PRUEBA = [JEFE, MEC, SER, roles.ADMIN, roles.OPERARIO, roles.VENTAS, roles.CALIDAD_PRODUCTO]
MOTIVO = "Jefe de Producción en auditoría externa"
# (código, unidad actual, cantidad)
OPS = (("OP-CIE-MEC", "MECANIZADOS", 2), ("OP-CIE-SER", "SERVICIOS", 1))


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
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")
    app.include_router(proyectos.router, prefix="/api/v1/proyectos")
    app.dependency_overrides[get_db] = _get_db
    with Sesion() as s:
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in ROLES_PRUEBA)
        s.add_all(Usuario(**datos_usuario(rol.lower()), password_hash="!", nombre_completo=rol, id_rol=rol)
                  for rol in ROLES_PRUEBA)
        pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido="PED-CIE-1", codigo_proyecto="PED-CIE-1",
                          cliente_nombre="Cliente ficticio cierre", requisitos_cliente="Según plano", confirmado=True,
                          estado=EstadoProyectoEnum.CONFIRMADO)
        producto = Producto(id_producto=uuid.uuid4(), codigo_rn="RN-CIE-1", descripcion="Eje ficticio")
        s.add_all([pedido, producto])
        s.flush()
        linea = PedidoDetalle(pedido_id=pedido.id_proyecto, codigo_producto="RN-CIE-1", descripcion="Eje",
                              cantidad_solicitada=3, unidad="UN", id_producto=producto.id_producto)
        s.add(linea)
        for codigo, unidad, cantidad in OPS:
            plano = Plano(codigo_plano=f"PLN-{codigo}", id_proyecto=pedido.id_proyecto, id_producto=producto.id_producto,
                          unidad_planta="Servicios" if unidad == "SERVICIOS" else "Mecanizados")
            s.add(plano)
            s.flush()
            op = OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op=codigo, cantidad_fabricar=cantidad,
                                 unidad_actual=unidad, estado=EstadoOPEnum.TERMINADA, id_plano=plano.id_plano,
                                 id_producto=producto.id_producto)
            s.add(op)
            s.flush()
            procesos = [OperacionOT(id_plano=plano.id_plano, codigo_op=codigo, codigo_plano=plano.codigo_plano,
                                    secuencia_paso=secuencia, nombre_proceso=nombre)
                        for secuencia, nombre in ((10, "Torneado"), (20, "Fresado"))]
            s.add_all(procesos)
            s.flush()
            # 30 + 10 minutos por proceso: 80 minutos por OP
            s.add_all(RegistroTiemposProduccion(
                orden_produccion_id=op.id_op, id_operacion=proceso.id_operacion, estacion_id="TORNO-01",
                operario_id=str(id_prueba("operario")), tipo_tiempo="MECANIZADO", segundos_ejecutados=30 * 60,
                segundos_setup=10 * 60, origen="MANUAL", fecha_trabajo=date(2026, 11, 17), pausado_por_turno=False,
            ) for proceso in procesos)
            s.add(InspeccionCalidad(codigo_op=codigo, codigo_plano=plano.codigo_plano, inspector_nombre="Inspector ficticio",
                                    resultado_inspeccion="APROBADO_DESPACHO", cantidad_aprobada=cantidad,
                                    tipo_aprobacion="LOTE"))
        s.commit()
        ids = {"pedido": pedido.id_proyecto, "linea": linea.detalle_id}
    with TestClient(app) as client:
        yield client, Sesion, ids
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol, rol_en_token=None):
    t = create_access_token({"sub": str(id_prueba(rol.lower())), "rol": rol_en_token or rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def cerrar(client, codigo, rol, confirmacion=None, motivo="", **kwargs):
    return client.post(f"/api/v1/ordenes/{codigo}/cerrar",
                       json={"confirmacion": codigo if confirmacion is None else confirmacion, "motivo": motivo},
                       headers=token(rol, **kwargs))


def cerrar_pedido(client, ids, rol=JEFE, confirmacion="PED-CIE-1"):
    return client.post(f"/api/v1/proyectos/{ids['pedido']}/cerrar", json={"confirmacion": confirmacion},
                       headers=token(rol))


def estado_op(Sesion, codigo):
    with Sesion() as s:
        return s.query(OrdenProduccion).filter_by(codigo_op=codigo).one().estado


def historial(Sesion, accion):
    with Sesion() as s:
        return s.query(HistorialAccionesDocumento).filter_by(accion=accion).all()


def cerrar_todas(client):
    for codigo, _, _ in OPS:
        assert cerrar(client, codigo, JEFE).status_code == 200


# --- Resumen ------------------------------------------------------------------------------------

def test_el_resumen_trae_lo_que_pide_la_confirmacion(ctx):
    client, _, _ = ctx
    resumen = client.get("/api/v1/ordenes/OP-CIE-MEC/cierre", headers=token(JEFE)).json()

    assert {clave: resumen[clave] for clave in (
        "codigo_op", "numero_pedido", "cliente", "cantidad", "minutos_tiempos", "aprobada_calidad", "piezas_aprobadas",
    )} == {"codigo_op": "OP-CIE-MEC", "numero_pedido": "PED-CIE-1", "cliente": "Cliente ficticio cierre",
           "cantidad": 2, "minutos_tiempos": 80.0, "aprobada_calidad": True, "piezas_aprobadas": 2}
    assert resumen["puede_cerrar"] is True and resumen["faltantes"] == []
    assert resumen["requiere_motivo"] is False


def test_el_resumen_pide_motivo_al_lider_de_respaldo(ctx):
    client, _, _ = ctx
    assert client.get("/api/v1/ordenes/OP-CIE-MEC/cierre", headers=token(MEC)).json()["requiere_motivo"] is True


# --- 1. Validación en el servidor ---------------------------------------------------------------

def test_sin_todas_las_piezas_aprobadas_no_se_cierra(ctx):
    client, Sesion, _ = ctx
    with Sesion() as s:
        s.query(InspeccionCalidad).filter_by(codigo_op="OP-CIE-MEC").update({"cantidad_aprobada": 1})
        s.commit()

    respuesta = cerrar(client, "OP-CIE-MEC", JEFE)

    assert respuesta.status_code == 409 and "1 de 2" in respuesta.json()["detail"]
    assert estado_op(Sesion, "OP-CIE-MEC") == EstadoOPEnum.TERMINADA


def test_con_un_proceso_sin_tiempo_no_se_cierra(ctx):
    client, Sesion, _ = ctx
    with Sesion() as s:
        fresado = s.query(OperacionOT).filter_by(codigo_op="OP-CIE-MEC", nombre_proceso="Fresado").one()
        s.query(RegistroTiemposProduccion).filter_by(id_operacion=fresado.id_operacion).delete()
        s.commit()

    respuesta = cerrar(client, "OP-CIE-MEC", JEFE)

    assert respuesta.status_code == 409 and "Fresado" in respuesta.json()["detail"]
    assert estado_op(Sesion, "OP-CIE-MEC") == EstadoOPEnum.TERMINADA


def test_sin_procesos_en_la_ruta_no_se_cierra(ctx):
    client, Sesion, _ = ctx
    with Sesion() as s:
        s.query(RegistroTiemposProduccion).delete()
        s.query(OperacionOT).filter_by(codigo_op="OP-CIE-MEC").delete()
        s.commit()

    assert cerrar(client, "OP-CIE-MEC", JEFE).status_code == 409


def test_una_op_cerrada_no_se_vuelve_a_cerrar(ctx):
    client, _, _ = ctx
    assert cerrar(client, "OP-CIE-MEC", JEFE).status_code == 200
    assert cerrar(client, "OP-CIE-MEC", JEFE).status_code == 409


# --- 2. Confirmación con escritura --------------------------------------------------------------

@pytest.mark.parametrize("confirmacion", ["", "OP-CIE-SER", "op-cie-mec"])
def test_hay_que_escribir_el_numero_de_la_op(ctx, confirmacion):
    client, Sesion, _ = ctx
    respuesta = cerrar(client, "OP-CIE-MEC", JEFE, confirmacion=confirmacion)

    assert respuesta.status_code == 422 and "número de la OP" in respuesta.json()["detail"]
    assert estado_op(Sesion, "OP-CIE-MEC") == EstadoOPEnum.TERMINADA


# --- 3. Motivo para los líderes de respaldo -----------------------------------------------------

@pytest.mark.parametrize("motivo", ["", "corto", "  catorce chars "])
def test_el_lider_de_respaldo_da_motivo_de_15_caracteres(ctx, motivo):
    client, Sesion, _ = ctx
    respuesta = cerrar(client, "OP-CIE-MEC", MEC, motivo=motivo)

    assert respuesta.status_code == 422 and "mínimo 15" in respuesta.json()["detail"]
    assert estado_op(Sesion, "OP-CIE-MEC") == EstadoOPEnum.TERMINADA


def test_el_jefe_cierra_sin_motivo_y_sin_aviso(ctx):
    client, Sesion, _ = ctx
    respuesta = cerrar(client, "OP-CIE-MEC", JEFE)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["aviso_jefe"] is False
    assert estado_op(Sesion, "OP-CIE-MEC") == EstadoOPEnum.CERRADA
    with Sesion() as s:
        assert s.query(NotificacionLider).count() == 0


# --- 4. Registro y aviso ------------------------------------------------------------------------

def test_el_cierre_queda_en_el_historial(ctx):
    client, Sesion, _ = ctx
    assert cerrar(client, "OP-CIE-MEC", MEC, motivo=MOTIVO).status_code == 200

    (evento,) = historial(Sesion, "OP_CERRADA")
    assert (evento.identificador_documento, evento.usuario_responsable, evento.area_origen) == (
        "OP-CIE-MEC", str(id_prueba("lider_mecanizados")), MEC)
    assert (evento.estado_anterior, evento.estado_nuevo, evento.motivo_observacion) == ("TERMINADA", "CERRADA", MOTIVO)
    assert evento.fecha_hora is not None


def test_el_cierre_por_respaldo_avisa_al_jefe(ctx):
    client, Sesion, _ = ctx
    respuesta = cerrar(client, "OP-CIE-SER", SER, motivo=MOTIVO)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["aviso_jefe"] is True
    with Sesion() as s:
        (aviso,) = s.query(NotificacionLider).all()
    assert aviso.tipo_notificacion == TipoNotificacionEnum.OP_CERRADA_RESPALDO
    assert aviso.codigo_op == "OP-CIE-SER" and MOTIVO in aviso.mensaje


# --- Quién cierra -------------------------------------------------------------------------------

@pytest.mark.parametrize("codigo", ["OP-CIE-MEC", "OP-CIE-SER"])
def test_el_lider_de_mecanizados_cierra_cualquier_op(ctx, codigo):
    client, _, _ = ctx
    assert cerrar(client, codigo, MEC, motivo=MOTIVO).status_code == 200


def test_el_lider_de_servicios_solo_cierra_las_de_su_area(ctx):
    client, Sesion, _ = ctx
    respuesta = cerrar(client, "OP-CIE-MEC", SER, motivo=MOTIVO)

    assert respuesta.status_code == 403 and respuesta.json()["detail"] == "Solo puede cerrar OP de su área."
    assert estado_op(Sesion, "OP-CIE-MEC") == EstadoOPEnum.TERMINADA
    assert cerrar(client, "OP-CIE-SER", SER, motivo=MOTIVO).status_code == 200


@pytest.mark.parametrize("rol", [roles.ADMIN, roles.OPERARIO, roles.VENTAS, roles.CALIDAD_PRODUCTO])
def test_los_demas_roles_no_cierran(ctx, rol):
    client, Sesion, _ = ctx
    assert cerrar(client, "OP-CIE-MEC", rol, motivo=MOTIVO).status_code == 403
    assert client.get("/api/v1/ordenes/OP-CIE-MEC/cierre", headers=token(rol)).status_code == 403
    assert estado_op(Sesion, "OP-CIE-MEC") == EstadoOPEnum.TERMINADA


def test_el_rol_del_cierre_se_lee_de_la_base(ctx):
    client, _, _ = ctx
    # El token dice JEFE_PRODUCCION, pero el usuario es OPERARIO en la base
    assert cerrar(client, "OP-CIE-MEC", roles.OPERARIO, rol_en_token=JEFE).status_code == 403


def test_el_patch_no_cierra_ni_saca_a_una_op_de_cerrada(ctx):
    client, Sesion, _ = ctx
    with Sesion() as s:
        id_op = s.query(OrdenProduccion).filter_by(codigo_op="OP-CIE-MEC").one().id_op
    assert client.patch(f"/api/v1/ordenes/{id_op}", json={"estado": "CERRADA"}, headers=token(JEFE)).status_code == 409

    assert cerrar(client, "OP-CIE-MEC", JEFE).status_code == 200
    respuesta = client.patch(f"/api/v1/ordenes/{id_op}", json={"estado": "EN_PRODUCCION"}, headers=token(JEFE))
    assert respuesta.status_code == 409
    assert estado_op(Sesion, "OP-CIE-MEC") == EstadoOPEnum.CERRADA


# --- Reapertura ---------------------------------------------------------------------------------

def reabrir(client, codigo, rol=JEFE, motivo=MOTIVO):
    return client.post(f"/api/v1/ordenes/{codigo}/reabrir", json={"motivo": motivo}, headers=token(rol))


def test_el_jefe_reabre_con_motivo_y_queda_en_el_historial(ctx):
    client, Sesion, _ = ctx
    assert cerrar(client, "OP-CIE-MEC", JEFE).status_code == 200

    assert reabrir(client, "OP-CIE-MEC", motivo="corto").status_code == 422
    respuesta = reabrir(client, "OP-CIE-MEC")

    assert respuesta.status_code == 200, respuesta.text
    assert estado_op(Sesion, "OP-CIE-MEC") == EstadoOPEnum.TERMINADA
    (evento,) = historial(Sesion, "OP_REABIERTA")
    assert (evento.estado_anterior, evento.estado_nuevo, evento.motivo_observacion) == ("CERRADA", "TERMINADA", MOTIVO)


@pytest.mark.parametrize("rol", [MEC, SER, roles.ADMIN])
def test_solo_el_jefe_reabre(ctx, rol):
    client, Sesion, _ = ctx
    assert cerrar(client, "OP-CIE-SER", JEFE).status_code == 200
    assert reabrir(client, "OP-CIE-SER", rol=rol).status_code == 403
    assert estado_op(Sesion, "OP-CIE-SER") == EstadoOPEnum.CERRADA


def test_solo_se_reabre_una_op_cerrada(ctx):
    client, _, _ = ctx
    assert reabrir(client, "OP-CIE-MEC").status_code == 409


# --- Pedido -------------------------------------------------------------------------------------

def test_al_cerrar_la_ultima_op_el_jefe_ve_que_puede_cerrar_el_pedido(ctx):
    client, _, _ = ctx
    primera = cerrar(client, "OP-CIE-MEC", JEFE).json()
    ultima = cerrar(client, "OP-CIE-SER", JEFE).json()

    assert (primera["pedido_listo_para_cerrar"], ultima["pedido_listo_para_cerrar"]) == (False, True)
    assert ultima["numero_pedido"] == "PED-CIE-1"


def test_el_lider_no_recibe_el_aviso_de_pedido_listo(ctx):
    client, _, _ = ctx
    assert "pedido_listo_para_cerrar" not in cerrar(client, "OP-CIE-MEC", MEC, motivo=MOTIVO).json()


def test_el_pedido_no_se_cierra_con_op_abiertas_ni_solo(ctx):
    client, Sesion, ids = ctx
    cerrar(client, "OP-CIE-MEC", JEFE)

    respuesta = cerrar_pedido(client, ids)

    assert respuesta.status_code == 409 and "OP-CIE-SER" in respuesta.json()["detail"]
    with Sesion() as s:
        assert s.get(Proyecto, ids["pedido"]).estado == EstadoProyectoEnum.CONFIRMADO


def test_el_jefe_cierra_el_pedido_a_mano_escribiendo_su_numero(ctx):
    client, Sesion, ids = ctx
    cerrar_todas(client)
    # El cierre del pedido es manual: cerrar la última OP no lo cierra
    with Sesion() as s:
        assert s.get(Proyecto, ids["pedido"]).estado == EstadoProyectoEnum.CONFIRMADO

    assert cerrar_pedido(client, ids, confirmacion="PED-OTRO").status_code == 422
    respuesta = cerrar_pedido(client, ids)

    assert respuesta.status_code == 200, respuesta.text
    with Sesion() as s:
        assert s.get(Proyecto, ids["pedido"]).estado == EstadoProyectoEnum.CERRADO
    (evento,) = historial(Sesion, "PEDIDO_CERRADO")
    assert (evento.identificador_documento, evento.estado_anterior, evento.estado_nuevo) == ("PED-CIE-1", "CONFIRMADO", "CERRADO")
    assert cerrar_pedido(client, ids).status_code == 409


def test_una_op_cancelada_no_impide_cerrar_el_pedido(ctx):
    client, Sesion, ids = ctx
    cerrar(client, "OP-CIE-MEC", JEFE)
    with Sesion() as s:
        s.query(OrdenProduccion).filter_by(codigo_op="OP-CIE-SER").update({"estado": EstadoOPEnum.CANCELADA})
        s.commit()

    assert cerrar_pedido(client, ids).status_code == 200


@pytest.mark.parametrize("rol", [MEC, SER, roles.VENTAS, roles.ADMIN])
def test_solo_el_jefe_cierra_el_pedido(ctx, rol):
    client, _, ids = ctx
    cerrar_todas(client)
    assert cerrar_pedido(client, ids, rol=rol).status_code == 403


def test_el_expediente_del_pedido_trae_su_estado_y_al_jefe_lo_que_falta(ctx):
    client, _, ids = ctx
    url = f"/api/v1/proyectos/{ids['pedido']}/expediente"
    jefe = client.get(url, headers=token(JEFE)).json()
    ventas = client.get(url, headers=token(roles.VENTAS)).json()

    assert jefe["estado"] == ventas["estado"] == "CONFIRMADO"
    assert "OP-CIE-MEC" in " ".join(jefe["pendientes_cierre"])
    assert "pendientes_cierre" not in ventas


def test_un_pedido_cerrado_es_historico(ctx):
    client, Sesion, ids = ctx
    cerrar_todas(client)
    assert cerrar_pedido(client, ids).status_code == 200

    # Sus OP no se reabren ni cambian
    assert reabrir(client, "OP-CIE-MEC").status_code == 409
    with Sesion() as s:
        id_op = s.query(OrdenProduccion).filter_by(codigo_op="OP-CIE-MEC").one().id_op
    assert client.patch(f"/api/v1/ordenes/{id_op}", json={"observaciones": "x"}, headers=token(JEFE)).status_code == 409
    # El pedido no se edita
    editar = client.patch(f"/api/v1/proyectos/{ids['pedido']}", json={"cliente_nombre": "Otro"}, headers=token(roles.VENTAS))
    assert editar.status_code == 409
    # Ni recibe OP nuevas
    nueva = client.post("/api/v1/ordenes/", json={"codigo_op": "OP-CIE-NUEVA", "detalle_id": str(ids["linea"])}, headers=token(JEFE))
    assert nueva.status_code == 409 and "cerrado" in nueva.json()["detail"]
    with Sesion() as s:
        assert s.get(Proyecto, ids["pedido"]).cliente_nombre == "Cliente ficticio cierre"
