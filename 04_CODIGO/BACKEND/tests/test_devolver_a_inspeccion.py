# tests/test_devolver_a_inspeccion.py
"""
Devolver a inspección (app/api/v1/ordenes.py): el flujo anterior de Calidad dejaba la OP aprobada en
LISTA_PARA_LIBERAR, que es el estado previo a la liberación de Diseño. JEFE_PRODUCCION la devuelve a
INSPECCION_CALIDAD para que Calidad registre la cantidad aprobada (migración 35).
- Solo JEFE_PRODUCCION, con el rol leído de la base.
- Solo OP en LISTA_PARA_LIBERAR sin piezas aprobadas y con una aprobación para despacho del flujo
  anterior de Calidad (si no, la OP no fue inspeccionada: está lista para liberar por Diseño); nunca
  OP cerradas.
- Motivo de al menos 15 caracteres (sin contar espacios de los extremos).
- Queda en el historial: quién (id_usuario), cuándo, estado previo, estado nuevo y motivo.
- No toca otras OP.

SQLite en memoria con override de get_db; aplicación FastAPI mínima con la misma dependencia global
que app.main (no se importa app.main).
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import ordenes
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import EstadoOPEnum, HistorialAccionesDocumento, OrdenProduccion, Proyecto, Rol, Usuario
from app.db.models_calidad import InspeccionCalidad
from app.services import acceso_bd
from tests.ayudantes_usuarios import datos_usuario, id_prueba

ROLES_PRUEBA = [roles.JEFE_PRODUCCION, roles.ADMIN, roles.CALIDAD_PRODUCTO, roles.LIDER_MECANIZADOS, roles.LIDER_DISENO]
MOTIVO = "Calidad aprobó con el flujo anterior sin registrar cantidad"
ANTERIOR = ["APROBADO_DESPACHO"]  # aprobación para despacho del flujo anterior (sin cantidad)
OPS = {
    # codigo: (estado, piezas ya aprobadas, dictámenes del flujo anterior)
    "OP-LISTA": (EstadoOPEnum.LISTA_PARA_LIBERAR, 0, ANTERIOR),
    "OP-LISTA-APROBADA": (EstadoOPEnum.LISTA_PARA_LIBERAR, 2, ANTERIOR),
    "OP-CERRADA": (EstadoOPEnum.CERRADA, 0, ANTERIOR),
    "OP-EN-PRODUCCION": (EstadoOPEnum.EN_PRODUCCION, 0, ANTERIOR),
    "OP-OTRA-LISTA": (EstadoOPEnum.LISTA_PARA_LIBERAR, 0, ANTERIOR),
    # Lista para liberar por Diseño: nunca pasó por Calidad
    "OP-LISTA-SIN-INSPECCION": (EstadoOPEnum.LISTA_PARA_LIBERAR, 0, []),
    # Inspeccionada pero sin aprobación para despacho
    "OP-LISTA-RECHAZADA": (EstadoOPEnum.LISTA_PARA_LIBERAR, 0, ["RECHAZADO", "APROBADO_TRATAMIENTO"]),
}


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
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")
    app.dependency_overrides[get_db] = _get_db
    with Sesion() as s:
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in ROLES_PRUEBA)
        s.add_all(Usuario(**datos_usuario(rol.lower()), password_hash="!", nombre_completo=rol, id_rol=rol)
                  for rol in ROLES_PRUEBA)
        pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido="PED-DEV-1", codigo_proyecto="PED-DEV-1",
                          cliente_nombre="Cliente ficticio", requisitos_cliente="Según plano", confirmado=True)
        s.add(pedido)
        s.flush()
        for codigo, (estado, aprobadas, dictamenes) in OPS.items():
            s.add(OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op=codigo, cantidad_fabricar=3, estado=estado))
            # Inspecciones del flujo anterior (sin cantidad) y, si aplica, una con piezas aprobadas
            s.add_all(InspeccionCalidad(codigo_op=codigo, codigo_plano="PLN-DEV", inspector_nombre="Inspector",
                                        resultado_inspeccion=dictamen) for dictamen in dictamenes)
            if aprobadas:
                s.add(InspeccionCalidad(codigo_op=codigo, codigo_plano="PLN-DEV", inspector_nombre="Inspector",
                                        resultado_inspeccion="APROBADO_DESPACHO", cantidad_aprobada=aprobadas,
                                        tipo_aprobacion="LOTE"))
        s.commit()
    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol, rol_en_token=None):
    t = create_access_token({"sub": str(id_prueba(rol.lower())), "rol": rol_en_token or rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def devolver(client, codigo, rol=roles.JEFE_PRODUCCION, motivo=MOTIVO, **kwargs):
    return client.post(f"/api/v1/ordenes/{codigo}/devolver-a-inspeccion", json={"motivo": motivo}, headers=token(rol, **kwargs))


def estados(Sesion):
    with Sesion() as s:
        return {op.codigo_op: op.estado for op in s.query(OrdenProduccion).all()}


def eventos(Sesion):
    with Sesion() as s:
        return s.query(HistorialAccionesDocumento).filter_by(accion="OP_DEVUELTA_A_INSPECCION").all()


def test_el_jefe_devuelve_a_inspeccion_y_queda_en_el_historial(ctx):
    client, Sesion = ctx
    antes = estados(Sesion)

    respuesta = devolver(client, "OP-LISTA", motivo=f"  {MOTIVO}  ")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"codigo_op": "OP-LISTA", "estado_anterior": "LISTA_PARA_LIBERAR", "estado": "INSPECCION_CALIDAD"}
    despues = estados(Sesion)
    assert despues["OP-LISTA"] == EstadoOPEnum.INSPECCION_CALIDAD
    # No toca otras OP
    assert {codigo: estado for codigo, estado in despues.items() if codigo != "OP-LISTA"} == {
        codigo: estado for codigo, estado in antes.items() if codigo != "OP-LISTA"
    }
    (evento,) = eventos(Sesion)
    assert (evento.tipo_entidad, evento.identificador_documento) == ("ORDEN_PRODUCCION", "OP-LISTA")
    assert (evento.estado_anterior, evento.estado_nuevo) == ("LISTA_PARA_LIBERAR", "INSPECCION_CALIDAD")
    assert evento.usuario_responsable == str(id_prueba("jefe_produccion"))
    assert evento.area_origen == roles.JEFE_PRODUCCION
    assert evento.motivo_observacion == MOTIVO and evento.fecha_hora is not None


@pytest.mark.parametrize("motivo", ["", "corto", "   catorce letras  ", "a" * 14])
def test_el_motivo_exige_al_menos_15_caracteres(ctx, motivo):
    client, Sesion = ctx
    respuesta = devolver(client, "OP-LISTA", motivo=motivo)

    assert respuesta.status_code == 422 and "15 caracteres" in respuesta.json()["detail"]
    assert estados(Sesion)["OP-LISTA"] == EstadoOPEnum.LISTA_PARA_LIBERAR and not eventos(Sesion)


@pytest.mark.parametrize("codigo, mensaje", [
    ("OP-CERRADA", "cerrada"),
    ("OP-EN-PRODUCCION", "lista para liberar"),
    ("OP-LISTA-APROBADA", "piezas aprobadas"),
    ("OP-LISTA-SIN-INSPECCION", "no fue inspeccionada"),
    ("OP-LISTA-RECHAZADA", "no fue inspeccionada"),
])
def test_solo_op_listas_para_liberar_sin_piezas_aprobadas_y_nunca_cerradas(ctx, codigo, mensaje):
    client, Sesion = ctx
    antes = estados(Sesion)[codigo]
    respuesta = devolver(client, codigo)

    assert respuesta.status_code == 409 and mensaje in respuesta.json()["detail"]
    assert estados(Sesion)[codigo] == antes and not eventos(Sesion)


def test_una_op_lista_para_liberar_sin_inspeccion_previa_no_cambia_ni_toca_otras(ctx):
    client, Sesion = ctx
    antes = estados(Sesion)

    respuesta = devolver(client, "OP-LISTA-SIN-INSPECCION")

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == (
        "La OP no fue inspeccionada ni aprobada para despacho por Calidad: no se devuelve a inspección."
    )
    assert estados(Sesion) == antes and not eventos(Sesion)


def test_op_inexistente(ctx):
    client, _ = ctx
    assert devolver(client, "OP-NO-EXISTE").status_code == 404


@pytest.mark.parametrize("rol", [roles.ADMIN, roles.CALIDAD_PRODUCTO, roles.LIDER_MECANIZADOS, roles.LIDER_DISENO])
def test_solo_el_jefe_de_produccion(ctx, rol):
    client, Sesion = ctx
    assert devolver(client, "OP-LISTA", rol=rol).status_code == 403
    assert estados(Sesion)["OP-LISTA"] == EstadoOPEnum.LISTA_PARA_LIBERAR


def test_el_rol_se_lee_de_la_base_y_no_del_token(ctx):
    client, Sesion = ctx
    # El token dice JEFE_PRODUCCION, pero el usuario es LIDER_DISENO en la base
    assert devolver(client, "OP-LISTA", rol=roles.LIDER_DISENO, rol_en_token=roles.JEFE_PRODUCCION).status_code == 403
    assert estados(Sesion)["OP-LISTA"] == EstadoOPEnum.LISTA_PARA_LIBERAR
