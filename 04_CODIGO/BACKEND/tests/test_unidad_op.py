# tests/test_unidad_op.py
"""
Unidad actual de la OP y traslado obligatorio (app/services/unidad_op.py, migración 28):
- Solo CALIDAD_PRODUCTO traslada; ningún otro rol, tampoco ADMIN ni LIDER_MECANIZADOS o
  LIDER_SERVICIOS. Cuando exista LIDER_METALISTERIA trasladará las OP de su unidad hacia otras
  (roles.LIDERES_CAMBIAN_UNIDAD). El rol se lee de la base.
- Sin unidad destino no hay traslado; cada traslado guarda quién, cuándo y de qué unidad a cuál.
- El líder solo ve las OP de su unidad; CALIDAD_PRODUCTO, las que le llegan para inspección y las
  que están en Tercero.
- Almacén no cambia la unidad: la OP queda en Tercero hasta que Calidad la traslade.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import ordenes, unidades_op
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import EstadoOPEnum, OrdenProduccion, Plano, Proyecto, Rol, TrasladoUnidadOP, Usuario
from app.services import unidad_op

ROLES_PRUEBA = [
    roles.ADMIN, roles.VENTAS, roles.JEFE_PRODUCCION, roles.LIDER_MECANIZADOS, roles.LIDER_SERVICIOS,
    roles.CALIDAD_PRODUCTO, roles.ALMACEN,
]
OPS = {
    # codigo: (unidad_actual, estado)
    "OP-MEC": ("MECANIZADOS", EstadoOPEnum.EN_PRODUCCION),
    "OP-SER": ("SERVICIOS", EstadoOPEnum.EN_PRODUCCION),
    "OP-TER": ("TERCERO", EstadoOPEnum.EN_INSPECCION),
    "OP-INS": ("MECANIZADOS", EstadoOPEnum.TERMINADA),
    "OP-SIN": ("SIN_ASIGNAR", EstadoOPEnum.BORRADOR),
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

    app = FastAPI()
    app.include_router(ordenes.router, prefix="/api/v1/ordenes")
    app.include_router(unidades_op.router, prefix="/api/v1/unidades-op")
    app.dependency_overrides[get_db] = _get_db

    with Sesion() as s:
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in ROLES_PRUEBA)
        s.add_all(
            Usuario(email=f"{rol.lower()}@prueba.test", password_hash="!SIN_CLAVE", nombre_completo=rol, id_rol=rol)
            for rol in ROLES_PRUEBA
        )
        pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido="PED-UNI-1", codigo_proyecto="PED-UNI-1",
                          cliente_nombre="Cliente ficticio", requisitos_cliente="Según plano", confirmado=True)
        s.add(pedido)
        s.flush()
        s.add_all(
            OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op=codigo, cantidad_fabricar=1,
                            unidad_actual=unidad, estado=estado)
            for codigo, (unidad, estado) in OPS.items()
        )
        s.commit()

    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol, rol_en_token=None):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol_en_token or rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def trasladar(client, rol, codigo, cuerpo, **kwargs):
    return client.post(f"/api/v1/unidades-op/{codigo}/traslado", json=cuerpo, headers=token(rol, **kwargs))


def unidad_y_traslados(Sesion, codigo):
    with Sesion() as s:
        op = s.query(OrdenProduccion).filter_by(codigo_op=codigo).one()
        return op.unidad_actual, s.query(TrasladoUnidadOP).filter_by(id_op=op.id_op).all()


def test_calidad_de_producto_traslada_y_queda_registrado(ctx):
    client, Sesion = ctx
    r = trasladar(client, roles.CALIDAD_PRODUCTO, "OP-MEC", {"unidad_destino": "SERVICIOS", "observacion": "Rectificado"})

    assert r.status_code == 200, r.text
    assert (r.json()["unidad_origen"], r.json()["unidad_destino"]) == ("MECANIZADOS", "SERVICIOS")
    unidad, traslados = unidad_y_traslados(Sesion, "OP-MEC")
    assert unidad == "SERVICIOS"
    (traslado,) = traslados
    assert (traslado.unidad_origen, traslado.unidad_destino) == ("MECANIZADOS", "SERVICIOS")
    assert traslado.usuario_email == "calidad_producto@prueba.test" and traslado.rol == roles.CALIDAD_PRODUCTO
    assert traslado.registrado_en is not None and traslado.observacion == "Rectificado"


@pytest.mark.parametrize("cuerpo", [{}, {"unidad_destino": ""}, {"unidad_destino": "   "}])
def test_sin_unidad_destino_no_se_confirma(ctx, cuerpo):
    client, Sesion = ctx
    r = trasladar(client, roles.CALIDAD_PRODUCTO, "OP-MEC", cuerpo)

    assert r.status_code == 422
    assert r.json()["detail"] == unidad_op.MENSAJE_SIN_DESTINO
    assert unidad_y_traslados(Sesion, "OP-MEC") == ("MECANIZADOS", [])


@pytest.mark.parametrize("destino, estado", [("SIN_ASIGNAR", 422), ("BODEGA", 422), ("MECANIZADOS", 409)])
def test_destino_invalido_o_igual_al_actual(ctx, destino, estado):
    client, Sesion = ctx
    assert trasladar(client, roles.CALIDAD_PRODUCTO, "OP-MEC", {"unidad_destino": destino}).status_code == estado
    assert unidad_y_traslados(Sesion, "OP-MEC") == ("MECANIZADOS", [])


@pytest.mark.parametrize("rol", [roles.LIDER_MECANIZADOS, roles.LIDER_SERVICIOS])
@pytest.mark.parametrize("codigo, destino", [("OP-MEC", "DESPACHO"), ("OP-SER", "TERCERO"), ("OP-MEC", "SERVICIOS")])
def test_los_lideres_de_mecanizados_y_servicios_no_cambian_la_unidad(ctx, rol, codigo, destino):
    client, Sesion = ctx
    antes = unidad_y_traslados(Sesion, codigo)[0]

    r = trasladar(client, rol, codigo, {"unidad_destino": destino})

    assert r.status_code == 403
    assert r.json()["detail"] == "Su rol no puede cambiar la unidad de la OP."
    assert unidad_y_traslados(Sesion, codigo) == (antes, [])


@pytest.mark.parametrize("rol", [roles.ADMIN, roles.JEFE_PRODUCCION, roles.VENTAS, roles.ALMACEN])
def test_ningun_otro_rol_cambia_la_unidad(ctx, rol):
    client, Sesion = ctx
    r = trasladar(client, rol, "OP-MEC", {"unidad_destino": "SERVICIOS"})

    assert r.status_code == 403
    assert unidad_y_traslados(Sesion, "OP-MEC") == ("MECANIZADOS", [])


def test_almacen_no_saca_la_op_de_tercero_y_calidad_si(ctx):
    client, Sesion = ctx
    assert trasladar(client, roles.ALMACEN, "OP-TER", {"unidad_destino": "MECANIZADOS"}).status_code == 403
    assert unidad_y_traslados(Sesion, "OP-TER")[0] == "TERCERO"

    r = trasladar(client, roles.CALIDAD_PRODUCTO, "OP-TER", {"unidad_destino": "MECANIZADOS"})
    assert r.status_code == 200, r.text
    assert unidad_y_traslados(Sesion, "OP-TER")[0] == "MECANIZADOS"


def test_el_rol_para_trasladar_se_lee_de_la_base(ctx):
    client, Sesion = ctx
    # El token dice CALIDAD_PRODUCTO, pero el usuario es ALMACEN en la base
    r = trasladar(client, roles.ALMACEN, "OP-TER", {"unidad_destino": "DESPACHO"}, rol_en_token=roles.CALIDAD_PRODUCTO)
    assert r.status_code == 403


def codigos_listados(client, rol):
    r = client.get("/api/v1/ordenes/", headers=token(rol))
    assert r.status_code == 200, r.text
    return {fila["codigo_op"] for fila in r.json()}


def test_cada_rol_ve_las_op_que_le_tocan(ctx):
    client, _ = ctx

    assert codigos_listados(client, roles.LIDER_MECANIZADOS) == {"OP-MEC", "OP-INS"}
    assert codigos_listados(client, roles.CALIDAD_PRODUCTO) == {"OP-TER", "OP-INS"}
    assert codigos_listados(client, roles.JEFE_PRODUCCION) == set(OPS)


def test_el_lider_deja_de_ver_la_op_que_sale_de_su_unidad(ctx):
    client, _ = ctx
    assert trasladar(client, roles.CALIDAD_PRODUCTO, "OP-MEC", {"unidad_destino": "TERCERO"}).status_code == 200

    assert "OP-MEC" not in codigos_listados(client, roles.LIDER_MECANIZADOS)
    assert client.get("/api/v1/unidades-op/OP-MEC/traslados", headers=token(roles.LIDER_MECANIZADOS)).status_code == 404
    historial = client.get("/api/v1/unidades-op/OP-MEC/traslados", headers=token(roles.JEFE_PRODUCCION)).json()
    assert historial["unidad_actual"] == "TERCERO"
    assert [(t["unidad_origen"], t["unidad_destino"]) for t in historial["traslados"]] == [("MECANIZADOS", "TERCERO")]


def test_unidad_de_proceso_de_los_planos():
    assert unidad_op.unidad_de_proceso(" Metalistería ") == "METALISTERIA"
    assert unidad_op.unidad_de_proceso("mecanizados") == "MECANIZADOS"
    assert unidad_op.unidad_de_proceso("Pintura") is None
    assert unidad_op.unidad_de_planos([Plano(unidad_planta="Servicios"), Plano(unidad_planta="servicios")]) == "SERVICIOS"
    assert unidad_op.unidad_de_planos([Plano(unidad_planta="Servicios"), Plano(unidad_planta="Mecanizados")]) is None
    assert unidad_op.unidad_de_planos([]) is None


def test_solo_calidad_de_producto_cambia_la_unidad():
    assert roles.ROLES_CAMBIAR_UNIDAD_OP == [roles.CALIDAD_PRODUCTO]
    # Preparada para LIDER_METALISTERIA, sin asignar a nadie mientras el rol no exista
    assert roles.LIDERES_CAMBIAN_UNIDAD == []
    assert not hasattr(roles, "LIDER_METALISTERIA")
    assert roles.UNIDAD_POR_LIDER == {roles.LIDER_MECANIZADOS: "MECANIZADOS", roles.LIDER_SERVICIOS: "SERVICIOS"}


def test_un_lider_que_cambia_unidad_traslada_las_op_de_su_unidad_hacia_otras(ctx, monkeypatch):
    # Simula LIDER_METALISTERIA en LIDERES_CAMBIAN_UNIDAD (el rol aún no existe)
    _, Sesion = ctx
    lider = "LIDER_METALISTERIA"
    monkeypatch.setattr(roles, "UNIDAD_POR_LIDER", {**roles.UNIDAD_POR_LIDER, lider: "METALISTERIA"})
    monkeypatch.setattr(roles, "ROLES_CAMBIAR_UNIDAD_OP", [lider, roles.CALIDAD_PRODUCTO])
    with Sesion() as s:
        op = s.query(OrdenProduccion).filter_by(codigo_op="OP-MEC").one()
        with pytest.raises(HTTPException) as fuera_de_su_unidad:
            unidad_op.trasladar(s, op, "DESPACHO", "lider@prueba.test", lider)
        assert fuera_de_su_unidad.value.status_code == 403

        op.unidad_actual = "METALISTERIA"
        with pytest.raises(HTTPException) as misma_unidad:
            unidad_op.trasladar(s, op, "METALISTERIA", "lider@prueba.test", lider)
        assert misma_unidad.value.status_code == 409

        traslado = unidad_op.trasladar(s, op, "DESPACHO", "lider@prueba.test", lider)
        assert (traslado.unidad_origen, traslado.unidad_destino, op.unidad_actual) == ("METALISTERIA", "DESPACHO", "DESPACHO")
        s.rollback()
