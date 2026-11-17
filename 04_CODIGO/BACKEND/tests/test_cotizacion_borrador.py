# tests/test_cotizacion_borrador.py
"""
Borrador de cotización (reglas/cotizacion-formato-y-borrador.md, revisión de Alejo 2026-11-11):
- Una cotización nueva queda en BORRADOR; se puede editar y eliminar sin dejar pedidos.
- Al emitirla pasa a EMITIDA y ya no se edita ni se elimina.
- Solo una cotización EMITIDA se convierte en pedido.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con el router de
cotizaciones (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import cotizaciones
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Cotizacion, HistorialAccionesDocumento, PosicionCotizacion, Proyecto
from tests.ayudantes_usuarios import id_prueba

URL = "/api/v1/ventas/cotizaciones"


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
    app.include_router(cotizaciones.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol="VENTAS"):
    t = create_access_token({"sub": str(id_prueba(f"{rol.lower()}")), "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def cuerpo(numero="COT-BOR-1", descripcion="Soporte", cantidad=2, precio=100.0):
    return {
        "numero_cotizacion": numero,
        "razon_social": "Cliente Borrador Ficticio",
        "nit": "900777888-1",
        "posiciones": [{"numero_producto": "P-1", "descripcion": descripcion, "cantidad": cantidad, "precio_unitario": precio}],
    }


def crear(client, **kwargs):
    r = client.post(f"{URL}/", json=cuerpo(**kwargs), headers=token())
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "BORRADOR"
    return r.json()["id_cotizacion"]


def estado(Sesion, id_cot):
    with Sesion() as s:
        cot = s.get(Cotizacion, uuid.UUID(id_cot))
        return cot.estado.value if cot else None


def acciones(Sesion, numero):
    with Sesion() as s:
        return [h.accion for h in s.query(HistorialAccionesDocumento).filter_by(identificador_documento=numero)]


def test_el_borrador_se_edita_y_reemplaza_sus_posiciones(ctx):
    client, Sesion = ctx
    id_cot = crear(client)

    r = client.put(f"{URL}/{id_cot}", json=cuerpo(numero="OTRO-NUMERO", descripcion="Soporte corregido", cantidad=5), headers=token())

    assert r.status_code == 200, r.text
    with Sesion() as s:
        cot = s.get(Cotizacion, uuid.UUID(id_cot))
        assert cot.numero_cotizacion == "COT-BOR-1"  # el número no cambia al editar
        assert [(p.descripcion, p.cantidad) for p in cot.posiciones] == [("Soporte corregido", 5)]
        assert float(cot.valor_total) == 500.0
        assert s.query(PosicionCotizacion).count() == 1
    assert "COTIZACION_EDITADA" in acciones(Sesion, "COT-BOR-1")


def test_el_borrador_se_elimina_sin_dejar_pedidos(ctx):
    client, Sesion = ctx
    id_cot = crear(client)

    r = client.delete(f"{URL}/{id_cot}", headers=token())

    assert r.status_code == 200, r.text
    assert estado(Sesion, id_cot) is None
    with Sesion() as s:
        assert s.query(PosicionCotizacion).count() == 0
        assert s.query(Proyecto).count() == 0
    assert "COTIZACION_ELIMINADA" in acciones(Sesion, "COT-BOR-1")


def test_emitir_pasa_a_emitida_y_bloquea_edicion_y_eliminacion(ctx):
    client, Sesion = ctx
    id_cot = crear(client)

    assert client.post(f"{URL}/{id_cot}/emitir", headers=token()).status_code == 200
    assert estado(Sesion, id_cot) == "EMITIDA"

    editar = client.put(f"{URL}/{id_cot}", json=cuerpo(descripcion="Cambio tardío"), headers=token())
    eliminar = client.delete(f"{URL}/{id_cot}", headers=token())
    reemitir = client.post(f"{URL}/{id_cot}/emitir", headers=token())

    assert (editar.status_code, eliminar.status_code, reemitir.status_code) == (409, 409, 409)
    assert "EMITIDA" in editar.json()["detail"]
    with Sesion() as s:
        assert [p.descripcion for p in s.get(Cotizacion, uuid.UUID(id_cot)).posiciones] == ["Soporte"]


def test_un_borrador_no_se_convierte_en_pedido(ctx):
    client, Sesion = ctx
    id_cot = crear(client)

    r = client.patch(f"{URL}/{id_cot}/aprobar-y-generar-pedido", headers=token())

    assert r.status_code == 409 and "emítala primero" in r.json()["detail"]
    assert estado(Sesion, id_cot) == "BORRADOR"
    with Sesion() as s:
        assert s.query(Proyecto).count() == 0


def test_la_emitida_se_convierte_en_pedido(ctx):
    client, Sesion = ctx
    id_cot = crear(client)
    client.post(f"{URL}/{id_cot}/emitir", headers=token())

    r = client.patch(f"{URL}/{id_cot}/aprobar-y-generar-pedido", headers=token())

    assert r.status_code == 200, r.text
    # EMITIDA reemplaza a APROBADA: convertida en pedido sigue EMITIDA
    assert estado(Sesion, id_cot) == "EMITIDA"
    assert r.json()["numero_pedido"] == "PED-BOR-1"
    assert client.get(f"{URL}/", headers=token()).json()[0]["numero_pedido"] == "PED-BOR-1"
    # Convertir otra vez devuelve el mismo pedido sin duplicarlo
    otra = client.patch(f"{URL}/{id_cot}/aprobar-y-generar-pedido", headers=token())
    assert otra.status_code == 200 and otra.json()["id_proyecto"] == r.json()["id_proyecto"]
    with Sesion() as s:
        assert s.query(Proyecto).count() == 1
    # Ya emitida: no se edita ni se elimina
    assert client.delete(f"{URL}/{id_cot}", headers=token()).status_code == 409


def test_no_reutiliza_el_numero_de_un_pedido_sin_cotizacion(ctx):
    client, Sesion = ctx
    id_cot = crear(client)
    client.post(f"{URL}/{id_cot}/emitir", headers=token())
    with Sesion() as s:
        s.add(Proyecto(numero_pedido="PED-BOR-1", codigo_proyecto="PED-BOR-1", cliente_nombre="Anterior", cantidad=1,
                       requisitos_cliente="Pedido anterior sin cotización"))
        s.commit()

    r = client.patch(f"{URL}/{id_cot}/aprobar-y-generar-pedido", headers=token())

    assert r.status_code == 409 and "sin cotización de origen" in r.json()["detail"]
    assert estado(Sesion, id_cot) == "EMITIDA"
    assert client.get(f"{URL}/", headers=token()).json()[0]["numero_pedido"] is None


@pytest.mark.parametrize("metodo, sufijo", [("put", ""), ("delete", ""), ("post", "/emitir")])
def test_solo_ventas_y_admin(ctx, metodo, sufijo):
    client, _ = ctx
    id_cot = crear(client)
    kwargs = {"json": cuerpo()} if metodo == "put" else {}

    r = getattr(client, metodo)(f"{URL}/{id_cot}{sufijo}", headers=token("JEFE_PRODUCCION"), **kwargs)

    assert r.status_code == 403


@pytest.mark.parametrize("metodo, sufijo", [("put", ""), ("delete", ""), ("post", "/emitir")])
def test_cotizacion_inexistente_404(ctx, metodo, sufijo):
    client, _ = ctx
    kwargs = {"json": cuerpo()} if metodo == "put" else {}

    r = getattr(client, metodo)(f"{URL}/{uuid.uuid4()}{sufijo}", headers=token(), **kwargs)

    assert r.status_code == 404


def test_no_se_emite_sin_posiciones(ctx):
    client, Sesion = ctx
    id_cot = crear(client)
    with Sesion() as s:
        s.query(PosicionCotizacion).delete()
        s.commit()

    r = client.post(f"{URL}/{id_cot}/emitir", headers=token())

    assert r.status_code == 400
    assert estado(Sesion, id_cot) == "BORRADOR"
