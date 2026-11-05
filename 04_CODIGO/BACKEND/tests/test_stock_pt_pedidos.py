# tests/test_stock_pt_pedidos.py
"""
OT-2026-008 (F4): pruebas de stock de producto terminado en cotizaciones y pedidos.

SQLite en memoria, override de get_db y tokens ficticios. Se monta una aplicacion
FastAPI minima con los routers de la OT (no se importa app.main) para no tocar
ninguna base real. Lo que requiere PostgreSQL (FOR UPDATE, concurrencia real) queda
en tests/test_stock_pt_concurrencia_pg.py.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import cotizaciones, proyectos, stock_pt
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import (
    ArticuloInventario,
    LoteMaterial,
    OrdenPicking,
    OrdenPickingDetalle,
    OrdenProduccion,
    OTDetalle,
    PedidoDetalle,
    Plano,
    PosicionCotizacion,
    Proyecto,
)


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = FastAPI()
    app.include_router(proyectos.router, prefix="/api/v1/proyectos")
    app.include_router(cotizaciones.router, prefix="/api/v1")
    app.include_router(stock_pt.router, prefix="/api/v1")

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)
    yield client, Sesion
    client.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(rol: str) -> dict:
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def crear_articulo(Sesion, sku, categoria, stock=0, estado_lote="LIBERADO", unidad="UND", ubicacion="A-01"):
    s = Sesion()
    art = ArticuloInventario(
        codigo_sku=sku,
        nombre=f"Articulo ficticio {sku}",
        categoria=categoria,
        unidad_medida=unidad,
        stock_actual=stock,
        stock_reservado=0,
        costo_unitario=100,
        ubicacion=ubicacion,
    )
    s.add(art)
    s.flush()
    s.add(LoteMaterial(
        codigo_lote=f"L-{sku}",
        codigo_material=sku,
        stock_disponible=stock,
        stock_reservado=0,
        estado_calidad=estado_lote,
        inspeccionado_calidad=(estado_lote == "LIBERADO"),
    ))
    s.commit()
    id_art = art.id_articulo
    s.close()
    return id_art


def linea_stock(id_art, cantidad, **extra):
    d = {
        "codigo_producto": "SKU-FALSO",
        "descripcion": "descripcion falsa del cliente",
        "origen": "STOCK_PT",
        "id_articulo": str(id_art),
        "cantidad_solicitada": cantidad,
        "unidad": "XXX",
    }
    d.update(extra)
    return d


def linea_plano(descripcion="Pieza sobre plano", cantidad=2):
    return {"codigo_producto": "PZA-001", "descripcion": descripcion, "cantidad_solicitada": cantidad}


def cuerpo_pedido(numero, detalles):
    return {
        "numero_pedido": numero,
        "cliente_nombre": "Cliente Ficticio SAS",
        "detalles": detalles,
    }


def crear_pedido(client, numero, detalles):
    r = client.post("/api/v1/proyectos/", json=cuerpo_pedido(numero, detalles))
    assert r.status_code == 201, r.text
    return r.json()


def contar(Sesion, modelo):
    s = Sesion()
    try:
        return s.query(func.count()).select_from(modelo).scalar()
    finally:
        s.close()


@pytest.fixture
def catalogo(ctx):
    _, Sesion = ctx
    return {
        "mp": crear_articulo(Sesion, "MP-X", "MATERIA_PRIMA", 50),
        "co": crear_articulo(Sesion, "CO-X", "CONSUMIBLE", 50),
        "se": crear_articulo(Sesion, "SE-X", "SEMIELABORADO", 50),
        "pt": crear_articulo(Sesion, "PT-X", "PRODUCTO_TERMINADO", 10),
    }


# ----------------------------------------------------------------------------
# CA-1 / CA-2: catalogo
# ----------------------------------------------------------------------------

def test_ca1_catalogo_solo_producto_terminado(ctx, catalogo):
    client, _ = ctx
    r = client.get("/api/v1/ventas/stock-pt", headers=token("VENTAS"))
    assert r.status_code == 200
    skus = [i["codigo_sku"] for i in r.json()["items"]]
    assert skus == ["PT-X"]
    for q in ("MP-X", "CO-X", "SE-X"):
        r = client.get("/api/v1/ventas/stock-pt", params={"q": q}, headers=token("VENTAS"))
        assert r.status_code == 200
        assert r.json()["items"] == []
        assert r.json()["total"] == 0


def test_ca1_catalogo_busqueda_por_sku_descripcion_y_ubicacion(ctx, catalogo):
    client, Sesion = ctx
    crear_articulo(Sesion, "PT-Y", "PRODUCTO_TERMINADO", 4, ubicacion="BOD-ZETA-9")
    h = token("VENTAS")
    assert [i["codigo_sku"] for i in client.get("/api/v1/ventas/stock-pt", params={"q": "pt-y"}, headers=h).json()["items"]] == ["PT-Y"]
    assert [i["codigo_sku"] for i in client.get("/api/v1/ventas/stock-pt", params={"q": "zeta"}, headers=h).json()["items"]] == ["PT-Y"]
    assert len(client.get("/api/v1/ventas/stock-pt", params={"q": "Articulo ficticio"}, headers=h).json()["items"]) == 2


def test_ca1_catalogo_paginado_en_servidor(ctx, catalogo):
    client, Sesion = ctx
    for n in range(2, 6):
        crear_articulo(Sesion, f"PT-P{n}", "PRODUCTO_TERMINADO", 3)
    h = token("ALMACEN")
    p1 = client.get("/api/v1/ventas/stock-pt", params={"limit": 2, "offset": 0}, headers=h).json()
    p2 = client.get("/api/v1/ventas/stock-pt", params={"limit": 2, "offset": 2}, headers=h).json()
    assert p1["total"] == 5 and p2["total"] == 5
    assert len(p1["items"]) == 2 and len(p2["items"]) == 2
    assert not ({i["codigo_sku"] for i in p1["items"]} & {i["codigo_sku"] for i in p2["items"]})
    assert client.get("/api/v1/ventas/stock-pt", params={"limit": 0}, headers=h).status_code == 422
    assert client.get("/api/v1/ventas/stock-pt", params={"limit": 201}, headers=h).status_code == 422


def test_catalogo_exige_token_y_rol(ctx, catalogo):
    client, _ = ctx
    assert client.get("/api/v1/ventas/stock-pt").status_code == 401
    assert client.get("/api/v1/ventas/stock-pt", headers=token("PRODUCCION")).status_code == 403


def test_ca2_disponible_resta_comprometido_y_en_picking(ctx, catalogo):
    client, Sesion = ctx
    id_pt = crear_articulo(Sesion, "PT-D", "PRODUCTO_TERMINADO", 10)
    ped_a = crear_pedido(client, "PED-D-A", [linea_stock(id_pt, 3)])
    ped_b = crear_pedido(client, "PED-D-B", [linea_stock(id_pt, 2)])
    for ped in (ped_a, ped_b):
        r = client.patch(f"/api/v1/proyectos/{ped['id_proyecto']}/confirmar", headers=token("VENTAS"))
        assert r.status_code == 200, r.text
    s = Sesion()
    pick_b = s.query(OrdenPicking).filter(OrdenPicking.id_proyecto == uuid.UUID(ped_b["id_proyecto"])).one()
    pick_b.estado = "EN_PICKING"
    s.commit()
    s.close()
    item = next(
        i for i in client.get("/api/v1/ventas/stock-pt", params={"q": "PT-D"}, headers=token("VENTAS")).json()["items"]
    )
    assert item["stock_fisico"] == 10
    assert item["stock_comprometido"] == 3
    assert item["stock_en_picking"] == 2
    assert item["stock_disponible"] == 5


def test_ca2_saldo_cero_solo_con_solo_con_saldo_false(ctx, catalogo):
    client, Sesion = ctx
    crear_articulo(Sesion, "PT-CERO", "PRODUCTO_TERMINADO", 7, estado_lote="CUARENTENA")
    h = token("VENTAS")
    por_defecto = [i["codigo_sku"] for i in client.get("/api/v1/ventas/stock-pt", headers=h).json()["items"]]
    assert "PT-CERO" not in por_defecto
    todos = client.get("/api/v1/ventas/stock-pt", params={"solo_con_saldo": "false"}, headers=h).json()["items"]
    cero = next(i for i in todos if i["codigo_sku"] == "PT-CERO")
    assert cero["stock_disponible"] == 0


# ----------------------------------------------------------------------------
# CA-3: cotizar no reserva
# ----------------------------------------------------------------------------

def cotizacion_stock(id_pt, numero="COT-2026-900", cantidad=4):
    return {
        "numero_cotizacion": numero,
        "razon_social": "Cliente Cotizante Ficticio",
        "posiciones": [{
            "numero_producto": "SKU-FALSO",
            "descripcion": "texto falso",
            "cantidad": cantidad,
            "precio_unitario": 120.0,
            "origen": "STOCK_PT",
            "id_articulo": str(id_pt),
        }],
    }


def foto_inventario(Sesion, id_art):
    s = Sesion()
    try:
        art = s.get(ArticuloInventario, id_art)
        lotes = s.query(LoteMaterial).filter(LoteMaterial.codigo_material == art.codigo_sku).all()
        return (
            art.stock_actual,
            art.stock_reservado,
            [(l.stock_disponible, l.stock_reservado) for l in lotes],
            s.query(func.count()).select_from(OrdenPicking).scalar(),
            s.query(func.count()).select_from(OrdenPickingDetalle).scalar(),
        )
    finally:
        s.close()


def test_ca3_cotizar_con_stock_no_cambia_saldos(ctx, catalogo):
    client, Sesion = ctx
    antes = foto_inventario(Sesion, catalogo["pt"])
    r = client.post("/api/v1/ventas/cotizaciones/", json=cotizacion_stock(catalogo["pt"]), headers=token("VENTAS"))
    assert r.status_code == 201, r.text
    assert foto_inventario(Sesion, catalogo["pt"]) == antes
    s = Sesion()
    pos = s.query(PosicionCotizacion).one()
    assert pos.origen == "STOCK_PT" and pos.id_articulo == catalogo["pt"]
    assert pos.numero_producto == "PT-X"
    s.close()
    item = client.get("/api/v1/ventas/stock-pt", params={"q": "PT-X"}, headers=token("VENTAS")).json()["items"][0]
    assert item["stock_disponible"] == 10


def test_ca3_cotizacion_con_articulo_no_pt_o_inexistente_responde_400(ctx, catalogo):
    client, _ = ctx
    r = client.post("/api/v1/ventas/cotizaciones/", json=cotizacion_stock(catalogo["mp"], "COT-2026-901"), headers=token("VENTAS"))
    assert r.status_code == 400
    r = client.post("/api/v1/ventas/cotizaciones/", json=cotizacion_stock(uuid.uuid4(), "COT-2026-902"), headers=token("VENTAS"))
    assert r.status_code == 400


# ----------------------------------------------------------------------------
# CA-5 / CA-8: guardar pedido y validaciones de cantidad
# ----------------------------------------------------------------------------

def test_ca5_linea_stock_guarda_origen_sku_y_sin_ot_detalles(ctx, catalogo):
    client, Sesion = ctx
    ped = crear_pedido(client, "PED-5", [linea_stock(catalogo["pt"], 3)])
    d = ped["detalles"][0]
    assert d["origen"] == "STOCK_PT"
    assert d["id_articulo"] == str(catalogo["pt"])
    assert d["codigo_producto"] == "PT-X"           # el servidor ignora el SKU falso del cliente
    assert d["descripcion"] == "Articulo ficticio PT-X"
    assert d["unidad"] == "UND"
    s = Sesion()
    assert s.query(func.count()).select_from(OTDetalle).scalar() == 0
    s.close()
    listado = client.get("/api/v1/proyectos/").json()
    det = listado[0]["detalles"][0]
    assert det["estado_asignacion"] == "DESDE_STOCK"
    assert det["cantidad_asignada"] == 3 and det["cantidad_pendiente"] == 0


def test_ca8_exceso_responde_400_con_detail_objeto_sin_datos_sensibles(ctx, catalogo):
    client, _ = ctx
    r = client.post("/api/v1/proyectos/", json=cuerpo_pedido("PED-8A", [linea_stock(catalogo["pt"], 11)]))
    assert r.status_code == 400
    det = r.json()["detail"]
    assert isinstance(det, dict)
    assert det["codigo"] == "STOCK_INSUFICIENTE"
    assert det["sku"] == "PT-X" and det["disponible"] == 10 and det["unidad"] == "UND"
    assert "Disponible: 10" in det["mensaje"]
    assert set(det) == {"codigo", "sku", "disponible", "unidad", "mensaje"}
    assert "costo" not in str(det).lower() and "stock_actual" not in str(det)


def test_ca8_suma_por_sku_al_crear(ctx, catalogo):
    client, Sesion = ctx
    id_pt = crear_articulo(Sesion, "PT-100", "PRODUCTO_TERMINADO", 100)
    r = client.post("/api/v1/proyectos/", json=cuerpo_pedido(
        "PED-8B", [linea_stock(id_pt, 80), linea_stock(id_pt, 80)]))
    assert r.status_code == 400
    assert r.json()["detail"]["codigo"] == "STOCK_INSUFICIENTE"
    assert r.json()["detail"]["disponible"] == 100
    assert contar(Sesion, Proyecto) == 0
    r = client.post("/api/v1/proyectos/", json=cuerpo_pedido(
        "PED-8B2", [linea_stock(id_pt, 50), linea_stock(id_pt, 50)]))
    assert r.status_code == 201


def test_ca8_suma_por_sku_al_editar(ctx, catalogo):
    client, Sesion = ctx
    id_pt = crear_articulo(Sesion, "PT-100", "PRODUCTO_TERMINADO", 100)
    ped = crear_pedido(client, "PED-8C", [linea_stock(id_pt, 10)])
    r = client.patch(f"/api/v1/proyectos/{ped['id_proyecto']}", json={
        "detalles": [linea_stock(id_pt, 80), linea_stock(id_pt, 80)]})
    assert r.status_code == 400
    assert r.json()["detail"]["codigo"] == "STOCK_INSUFICIENTE"
    s = Sesion()
    lineas = s.query(PedidoDetalle).filter(PedidoDetalle.pedido_id == uuid.UUID(ped["id_proyecto"])).all()
    assert len(lineas) == 1 and lineas[0].cantidad_solicitada == 10   # sin cambios
    s.close()


def test_ca8_suma_por_sku_al_confirmar(ctx, catalogo):
    """Dos pedidos sin confirmar caben por separado (borrador no reserva); al confirmar revalida."""
    client, Sesion = ctx
    ped_a = crear_pedido(client, "PED-9A", [linea_stock(catalogo["pt"], 8)])
    ped_b = crear_pedido(client, "PED-9B", [linea_stock(catalogo["pt"], 8)])
    ra = client.patch(f"/api/v1/proyectos/{ped_a['id_proyecto']}/confirmar", headers=token("VENTAS"))
    assert ra.status_code == 200, ra.text
    rb = client.patch(f"/api/v1/proyectos/{ped_b['id_proyecto']}/confirmar", headers=token("VENTAS"))
    assert rb.status_code == 400
    det = rb.json()["detail"]
    assert isinstance(det, dict) and det["codigo"] == "STOCK_INSUFICIENTE"
    assert det["disponible"] == 2          # saldo no negativo: 10 - 8
    s = Sesion()
    assert s.query(func.count()).select_from(OrdenPicking).scalar() == 1   # CA-9 secuencial
    pb = s.query(Proyecto).filter(Proyecto.id_proyecto == uuid.UUID(ped_b["id_proyecto"])).one()
    assert pb.confirmado is False
    s.close()


def test_ca8_articulo_no_pt_responde_400(ctx, catalogo):
    client, _ = ctx
    r = client.post("/api/v1/proyectos/", json=cuerpo_pedido("PED-8D", [linea_stock(catalogo["mp"], 1)]))
    assert r.status_code == 400


def test_ca8_articulo_inexistente_o_sin_id_responde_400(ctx, catalogo):
    client, _ = ctx
    r = client.post("/api/v1/proyectos/", json=cuerpo_pedido("PED-8E", [linea_stock(uuid.uuid4(), 1)]))
    assert r.status_code == 400
    sin_id = linea_stock(catalogo["pt"], 1)
    sin_id["id_articulo"] = None
    r = client.post("/api/v1/proyectos/", json=cuerpo_pedido("PED-8F", [sin_id]))
    assert r.status_code == 400


@pytest.mark.parametrize("cantidad", [0, -3, 1.5])
def test_ca8_desviacion_cantidad_invalida_responde_422_no_400(ctx, catalogo, cantidad):
    """
    DESVIACION registrada de CA-8: la OT exige HTTP 400 para cantidad 0, negativa o decimal.
    El comportamiento real es 422 (validacion de esquema Pydantic, ge=1 / entero). Esta prueba
    fija el comportamiento real; Direccion/revisor deciden si se acepta el 422 o se cambia a 400.
    """
    client, Sesion = ctx
    r = client.post("/api/v1/proyectos/", json=cuerpo_pedido("PED-8G", [linea_stock(catalogo["pt"], cantidad)]))
    assert r.status_code == 422, r.text
    assert contar(Sesion, Proyecto) == 0


# ----------------------------------------------------------------------------
# CA-4: pedido confirmado inmutable
# ----------------------------------------------------------------------------

def test_ca4_editar_pedido_confirmado_responde_400_y_no_cambia_detalles(ctx, catalogo):
    client, Sesion = ctx
    ped = crear_pedido(client, "PED-4", [linea_stock(catalogo["pt"], 3)])
    assert client.patch(f"/api/v1/proyectos/{ped['id_proyecto']}/confirmar", headers=token("VENTAS")).status_code == 200
    r = client.patch(f"/api/v1/proyectos/{ped['id_proyecto']}", json={"detalles": [linea_stock(catalogo["pt"], 1)]})
    assert r.status_code == 400
    s = Sesion()
    lineas = s.query(PedidoDetalle).filter(PedidoDetalle.pedido_id == uuid.UUID(ped["id_proyecto"])).all()
    assert len(lineas) == 1 and lineas[0].cantidad_solicitada == 3
    s.close()


# ----------------------------------------------------------------------------
# CA-6 / CA-10 / CA-7: confirmar
# ----------------------------------------------------------------------------

def test_ca6_confirmar_crea_un_picking_y_ninguna_op(ctx, catalogo):
    client, Sesion = ctx
    id_pt2 = crear_articulo(Sesion, "PT-Z", "PRODUCTO_TERMINADO", 6)
    ped = crear_pedido(client, "PED-6", [linea_stock(catalogo["pt"], 3), linea_stock(id_pt2, 2)])
    r = client.patch(f"/api/v1/proyectos/{ped['id_proyecto']}/confirmar", headers=token("VENTAS"))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["confirmado"] is True
    assert cuerpo["picking"]["estado"] == "PENDIENTE"
    assert cuerpo["picking"]["codigo_picking"].startswith("PCK-")
    s = Sesion()
    assert s.query(func.count()).select_from(OrdenPicking).scalar() == 1
    assert s.query(func.count()).select_from(OrdenPickingDetalle).scalar() == 2
    assert s.query(func.count()).select_from(OrdenProduccion).scalar() == 0
    assert s.query(func.count()).select_from(Plano).scalar() == 0
    assert s.query(func.count()).select_from(OTDetalle).scalar() == 0
    s.close()


def test_ca10_confirmar_dos_veces_no_duplica_picking(ctx, catalogo):
    client, Sesion = ctx
    ped = crear_pedido(client, "PED-10", [linea_stock(catalogo["pt"], 3)])
    url = f"/api/v1/proyectos/{ped['id_proyecto']}/confirmar"
    r1 = client.patch(url, headers=token("ADMIN"))
    r2 = client.patch(url, headers=token("ADMIN"))
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["picking"]["codigo_picking"] == r2.json()["picking"]["codigo_picking"]
    assert contar(Sesion, OrdenPicking) == 1
    assert contar(Sesion, OrdenPickingDetalle) == 1
    item = client.get("/api/v1/ventas/stock-pt", params={"q": "PT-X"}, headers=token("VENTAS")).json()["items"][0]
    assert item["stock_comprometido"] == 3 and item["stock_disponible"] == 7


def test_ca10_unique_id_proyecto_en_ordenes_picking(ctx, catalogo):
    client, Sesion = ctx
    ped = crear_pedido(client, "PED-10U", [linea_stock(catalogo["pt"], 1)])
    client.patch(f"/api/v1/proyectos/{ped['id_proyecto']}/confirmar", headers=token("VENTAS"))
    s = Sesion()
    s.add(OrdenPicking(codigo_picking="PCK-DUP-0001", id_proyecto=uuid.UUID(ped["id_proyecto"]), estado="PENDIENTE"))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()
    s.close()


def test_confirmar_sin_token_401_y_rol_no_autorizado_403(ctx, catalogo):
    client, Sesion = ctx
    ped = crear_pedido(client, "PED-AUTH", [linea_stock(catalogo["pt"], 1)])
    url = f"/api/v1/proyectos/{ped['id_proyecto']}/confirmar"
    assert client.patch(url).status_code == 401
    assert client.patch(url, headers={"Authorization": "Bearer token-invalido"}).status_code == 401
    assert client.patch(url, headers=token("ALMACEN")).status_code == 403
    assert client.patch(url, headers=token("PRODUCCION")).status_code == 403
    assert contar(Sesion, OrdenPicking) == 0
    s = Sesion()
    assert s.query(Proyecto).one().confirmado is False
    s.close()


def test_confirmar_pedido_inexistente_404(ctx, catalogo):
    client, _ = ctx
    assert client.patch(f"/api/v1/proyectos/{uuid.uuid4()}/confirmar", headers=token("VENTAS")).status_code == 404


def test_ca7_pedido_sobre_plano_sin_regresion(ctx, catalogo):
    client, Sesion = ctx
    ped = crear_pedido(client, "PED-7", [linea_plano(cantidad=2)])
    d = ped["detalles"][0]
    assert d["origen"] == "PLANO" and d["id_articulo"] is None
    assert d["codigo_producto"] == "PZA-001" and d["cantidad_pendiente"] == 2
    r = client.patch(f"/api/v1/proyectos/{ped['id_proyecto']}", json={"detalles": [linea_plano("Pieza editada", 5)]})
    assert r.status_code == 200
    assert r.json()["detalles"][0]["descripcion"] == "Pieza editada"
    assert r.json()["detalles"][0]["origen"] == "PLANO"
    rc = client.patch(f"/api/v1/proyectos/{ped['id_proyecto']}/confirmar", headers=token("VENTAS"))
    assert rc.status_code == 200
    assert rc.json()["confirmado"] is True and rc.json()["picking"] is None
    assert contar(Sesion, OrdenPicking) == 0
    assert contar(Sesion, OrdenProduccion) == 0
    listado = client.get("/api/v1/proyectos/").json()
    assert listado[0]["detalles"][0]["estado_asignacion"] == "SIN_ASIGNAR"


def test_ca7_origen_explicito_plano_con_id_articulo_se_descarta(ctx, catalogo):
    client, _ = ctx
    ped = crear_pedido(client, "PED-7B", [linea_plano() | {"origen": "PLANO", "id_articulo": str(catalogo["pt"])}])
    assert ped["detalles"][0]["id_articulo"] is None


def test_origen_invalido_responde_422(ctx, catalogo):
    client, _ = ctx
    r = client.post("/api/v1/proyectos/", json=cuerpo_pedido("PED-OR", [linea_plano() | {"origen": "OTRO"}]))
    assert r.status_code == 422


def test_pedido_mixto_picking_solo_con_lineas_de_stock(ctx, catalogo):
    client, Sesion = ctx
    ped = crear_pedido(client, "PED-MIX", [linea_plano(cantidad=4), linea_stock(catalogo["pt"], 3)])
    r = client.patch(f"/api/v1/proyectos/{ped['id_proyecto']}/confirmar", headers=token("VENTAS"))
    assert r.status_code == 200, r.text
    s = Sesion()
    det_pick = s.query(OrdenPickingDetalle).all()
    assert len(det_pick) == 1
    linea = s.get(PedidoDetalle, det_pick[0].detalle_pedido_id)
    assert linea.origen == "STOCK_PT" and linea.cantidad_solicitada == 3
    plano = s.query(PedidoDetalle).filter(PedidoDetalle.origen == "PLANO").one()
    assert plano.cantidad_asignada == 0 and plano.cantidad_pendiente == 4   # sigue su flujo normal
    assert s.query(func.count()).select_from(OTDetalle).scalar() == 0
    assert s.query(func.count()).select_from(OrdenProduccion).scalar() == 0
    s.close()
    estados = {d["origen"]: d["estado_asignacion"] for d in client.get("/api/v1/proyectos/").json()[0]["detalles"]}
    assert estados == {"PLANO": "SIN_ASIGNAR", "STOCK_PT": "DESDE_STOCK"}


# ----------------------------------------------------------------------------
# aprobar-y-generar-pedido (cotizaciones.py)
# ----------------------------------------------------------------------------

def test_aprobar_y_generar_pedido_propaga_origen_e_id_articulo(ctx, catalogo):
    client, Sesion = ctx
    cuerpo = cotizacion_stock(catalogo["pt"], "COT-2026-910", cantidad=3)
    cuerpo["posiciones"].append({
        "numero_producto": "PZA-PLANO", "descripcion": "Pieza sobre plano", "cantidad": 2, "precio_unitario": 50.0,
    })
    r = client.post("/api/v1/ventas/cotizaciones/", json=cuerpo, headers=token("VENTAS"))
    assert r.status_code == 201, r.text
    id_cot = r.json()["id_cotizacion"]
    antes = foto_inventario(Sesion, catalogo["pt"])
    ra = client.patch(f"/api/v1/ventas/cotizaciones/{id_cot}/aprobar-y-generar-pedido", headers=token("VENTAS"))
    assert ra.status_code == 200, ra.text
    assert foto_inventario(Sesion, catalogo["pt"]) == antes      # aprobar tampoco reserva
    s = Sesion()
    pedido = s.get(Proyecto, uuid.UUID(ra.json()["id_proyecto"]))
    assert pedido.confirmado is False
    por_origen = {d.origen: d for d in pedido.detalles}
    assert set(por_origen) == {"STOCK_PT", "PLANO"}
    assert por_origen["STOCK_PT"].id_articulo == catalogo["pt"]
    assert por_origen["STOCK_PT"].codigo_producto == "PT-X"
    assert por_origen["PLANO"].id_articulo is None
    s.close()
    # El pedido nacido de cotizacion queda sujeto a la revalidacion al confirmar.
    rc = client.patch(f"/api/v1/proyectos/{ra.json()['id_proyecto']}/confirmar", headers=token("VENTAS"))
    assert rc.status_code == 200
    assert contar(Sesion, OrdenPicking) == 1
