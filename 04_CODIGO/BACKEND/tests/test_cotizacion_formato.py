# tests/test_cotizacion_formato.py
"""
Formato aprobado de la cotización (reglas/cotizacion-formato-y-borrador.md, migración 26):
- Número de la empresa HD-XXXXX-AA, sugerido por GET /ventas/cotizaciones/siguiente-consecutivo.
- Moneda COP por defecto o USD; validez de la oferta y condición de pago (datos maestros
  activos) por cotización; término de negociación, referencia y observaciones.
- Firma "Elaboró": el usuario que creó la cotización.
- GET /maestros/condiciones-pago lista las activas en su orden.

SQLite en memoria con override de get_db y una aplicación FastAPI mínima con los routers de
cotizaciones y maestros (no se importa app.main) para no tocar ninguna base real.
"""
import uuid
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import cotizaciones, maestros
from app.api.v1.cotizaciones import siguiente_numero_hd
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import CondicionPago, Cotizacion, Rol, Usuario

URL = "/api/v1/ventas/cotizaciones"
CONDICIONES = [("ANTICIPADO", "Anticipado", 10, True), ("30_DIAS", "30 días", 30, True), ("VIEJA", "Condición retirada", 5, False)]


@pytest.fixture
def ctx():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with Sesion() as s:
        for codigo, descripcion, orden, activo in CONDICIONES:
            s.add(CondicionPago(codigo=codigo, descripcion=descripcion, orden=orden, activo=activo))
        s.add(Rol(id_rol="VENTAS", nombre_rol="Ventas"))
        s.add(Usuario(id_usuario=uuid.uuid4(), email="ventas@prueba.test", password_hash="!", nombre_completo="Vendedora Prueba", id_rol="VENTAS"))
        s.commit()

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI()
    app.include_router(cotizaciones.router, prefix="/api/v1")
    app.include_router(maestros.router, prefix="/api/v1/maestros")
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol="VENTAS"):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def id_condicion(Sesion, codigo):
    with Sesion() as s:
        return s.query(CondicionPago).filter_by(codigo=codigo).one().id_condicion_pago


def cuerpo(numero="HD-00001-26", **extra):
    datos = {
        "numero_cotizacion": numero,
        "razon_social": "Cliente Formato Ficticio",
        "nit": "900333222-1",
        "posiciones": [{"numero_producto": "P-1", "descripcion": "Dado", "cantidad": 1, "precio_unitario": 10.0}],
    }
    datos.update(extra)
    return datos


def test_siguiente_numero_hd_sigue_el_mayor_consecutivo():
    hoy = date(2026, 11, 11)
    assert siguiente_numero_hd([], hoy) == "HD-00001-26"
    assert siguiente_numero_hd(["HD-24234-26", "HD-00007-25", "COT-2026-0099", None], hoy) == "HD-24235-26"
    # El consecutivo no reinicia con el año; el sufijo es el año actual
    assert siguiente_numero_hd(["HD-00041-26"], date(2027, 1, 2)) == "HD-00042-27"


def test_la_ruta_sugiere_el_siguiente_numero(ctx):
    client, _ = ctx
    client.post(f"{URL}/", json=cuerpo("HD-00012-26"), headers=token())

    r = client.get(f"{URL}/siguiente-consecutivo", headers=token())

    assert r.status_code == 200
    assert r.json()["siguiente_numero"] == f"HD-00013-{date.today().year % 100:02d}"


def test_por_defecto_cop_y_puesto_en_planta(ctx):
    client, _ = ctx
    id_cot = client.post(f"{URL}/", json=cuerpo(), headers=token()).json()["id_cotizacion"]

    detalle = client.get(f"{URL}/{id_cot}", headers=token()).json()

    assert detalle["moneda"] == "COP"
    assert detalle["termino_negociacion"] == "Puesto en planta HD"
    assert detalle["condicion_pago"] is None and detalle["validez_oferta_dias"] is None


def test_guarda_el_formato_y_la_firma_de_quien_elaboro(ctx):
    client, Sesion = ctx
    datos = cuerpo(
        moneda="USD", validez_oferta_dias=8, id_condicion_pago=id_condicion(Sesion, "30_DIAS"),
        termino_negociacion="Puesto en planta HD.", referencia_global="DADO IMPO", observaciones="MAS FLETE",
    )

    id_cot = client.post(f"{URL}/", json=datos, headers=token()).json()["id_cotizacion"]
    detalle = client.get(f"{URL}/{id_cot}", headers=token()).json()

    assert detalle["moneda"] == "USD" and detalle["validez_oferta_dias"] == 8
    assert detalle["condicion_pago"]["descripcion"] == "30 días"
    assert (detalle["referencia"], detalle["observaciones"]) == ("DADO IMPO", "MAS FLETE")
    assert detalle["elaborado_por"] == {"email": "ventas@prueba.test", "nombre": "Vendedora Prueba"}
    assert client.get(f"{URL}/", headers=token()).json()[0]["moneda"] == "USD"


def test_editar_el_borrador_cambia_el_formato(ctx):
    client, Sesion = ctx
    id_cot = client.post(f"{URL}/", json=cuerpo(), headers=token()).json()["id_cotizacion"]

    r = client.put(f"{URL}/{id_cot}", json=cuerpo(moneda="USD", id_condicion_pago=id_condicion(Sesion, "ANTICIPADO")), headers=token())

    assert r.status_code == 200, r.text
    with Sesion() as s:
        cot = s.get(Cotizacion, uuid.UUID(id_cot))
        assert cot.moneda == "USD" and cot.condicion_pago.codigo == "ANTICIPADO"


@pytest.mark.parametrize("extra, codigo", [
    ({"moneda": "EUR"}, 422),
    ({"validez_oferta_dias": 0}, 422),
    ({"id_condicion_pago": 9999}, 400),
])
def test_rechaza_valores_fuera_del_formato(ctx, extra, codigo):
    client, Sesion = ctx

    r = client.post(f"{URL}/", json=cuerpo(**extra), headers=token())

    assert r.status_code == codigo
    with Sesion() as s:
        assert s.query(Cotizacion).count() == 0


def test_no_acepta_una_condicion_inactiva(ctx):
    client, Sesion = ctx

    r = client.post(f"{URL}/", json=cuerpo(id_condicion_pago=id_condicion(Sesion, "VIEJA")), headers=token())

    assert r.status_code == 400


def test_condiciones_de_pago_activas_en_su_orden(ctx):
    client, _ = ctx

    r = client.get("/api/v1/maestros/condiciones-pago", headers=token())

    assert r.status_code == 200
    assert [c["descripcion"] for c in r.json()] == ["Anticipado", "30 días"]


def test_la_migracion_26_trae_la_lista_inicial_del_documento():
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[3] / "05_BASE_DATOS" / "26_MIGRACION_COTIZACION_FORMATO.sql").read_text(encoding="utf-8")
    for descripcion in ("Anticipado", "8 días", "30 días", "60 días", "120 días",
                        "50% Anticipo - 50% Saldo a 30 días", "Contra documentos de embarque"):
        assert f"'{descripcion}'" in sql
    assert "CHECK (moneda IN ('COP', 'USD'))" in sql
