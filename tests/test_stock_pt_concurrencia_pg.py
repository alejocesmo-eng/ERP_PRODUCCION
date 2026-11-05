# tests/test_stock_pt_concurrencia_pg.py
"""
OT-2026-008 (CA-9): concurrencia real de confirmacion de pedidos con stock PT.

Requiere una base PostgreSQL DE PRUEBA indicada en SGI_TEST_PG_URL con el esquema ya
creado (incluida la migracion 13). Se salta si la variable no existe y ABORTA si el
nombre de la base es sgi_db (base operativa). Datos ficticios; limpia lo que crea.
"""
import os
import threading
import uuid
from datetime import timedelta

import pytest

PG_URL = os.environ.get("SGI_TEST_PG_URL")

pytestmark = pytest.mark.skipif(not PG_URL, reason="SGI_TEST_PG_URL no definida: prueba de concurrencia PostgreSQL omitida")


def _nombre_bd(url: str) -> str:
    from sqlalchemy.engine import make_url
    return (make_url(url).database or "").strip()


def test_ca9_dos_confirmaciones_simultaneas_una_sola_exitosa():
    nombre = _nombre_bd(PG_URL)
    if nombre.lower() == "sgi_db":
        pytest.exit("SGI_TEST_PG_URL apunta a sgi_db (base operativa): ejecucion abortada.", returncode=2)

    import sys
    backend = os.path.join(os.path.dirname(__file__), "..", "04_CODIGO", "BACKEND")
    sys.path.insert(0, os.path.abspath(backend))
    os.environ.setdefault("SECRET_KEY", "clave_solo_para_pruebas_sesion_no_usar_en_produccion")
    os.environ.setdefault("JWT_SECRET_KEY_PLANOS", "clave_solo_para_pruebas_planos_no_usar_en_produccion")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.api.v1 import proyectos
    from app.core.security import create_access_token
    from app.db.database import get_db
    from app.db.models import (
        ArticuloInventario, LoteMaterial, OrdenPicking, OrdenPickingDetalle, PedidoDetalle, Proyecto,
    )

    engine = create_engine(PG_URL)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    app = FastAPI()
    app.include_router(proyectos.router, prefix="/api/v1/proyectos")

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    sufijo = uuid.uuid4().hex[:8].upper()
    sku = f"PT-CONC-{sufijo}"
    ids_pedidos = []

    s = Sesion()
    art = ArticuloInventario(codigo_sku=sku, nombre="PT concurrencia ficticio", categoria="PRODUCTO_TERMINADO",
                             unidad_medida="UND", stock_actual=10, stock_reservado=0, costo_unitario=1)
    s.add(art)
    s.flush()
    id_art = art.id_articulo
    s.add(LoteMaterial(codigo_lote=f"L-{sku}", codigo_material=sku, stock_disponible=10, stock_reservado=0,
                       estado_calidad="LIBERADO", inspeccionado_calidad=True))
    s.commit()
    s.close()

    try:
        client = TestClient(app)
        for n in range(2):
            r = client.post("/api/v1/proyectos/", json={
                "numero_pedido": f"PED-CONC-{sufijo}-{n}", "cliente_nombre": "Cliente Ficticio",
                "detalles": [{"descripcion": "x", "origen": "STOCK_PT", "id_articulo": str(id_art), "cantidad_solicitada": 8}],
            })
            assert r.status_code == 201, r.text
            ids_pedidos.append(r.json()["id_proyecto"])

        h = {"Authorization": "Bearer " + create_access_token({"sub": "ventas@prueba.test", "rol": "VENTAS"}, timedelta(minutes=5))}
        resultados = []
        barrera = threading.Barrier(2)

        def confirmar(id_p):
            c = TestClient(app)
            barrera.wait()
            resultados.append(c.patch(f"/api/v1/proyectos/{id_p}/confirmar", headers=h).status_code)

        hilos = [threading.Thread(target=confirmar, args=(i,)) for i in ids_pedidos]
        [t.start() for t in hilos]
        [t.join() for t in hilos]
        assert sorted(resultados) == [200, 400]

        s = Sesion()
        assert s.query(OrdenPickingDetalle).filter(OrdenPickingDetalle.id_articulo == id_art).count() == 1
    finally:
        s = Sesion()
        pids = [uuid.UUID(i) for i in ids_pedidos]
        picks = s.query(OrdenPicking).filter(OrdenPicking.id_proyecto.in_(pids)).all()
        for p in picks:
            s.delete(p)
        s.flush()
        s.query(PedidoDetalle).filter(PedidoDetalle.pedido_id.in_(pids)).delete(synchronize_session=False)
        s.query(Proyecto).filter(Proyecto.id_proyecto.in_(pids)).delete(synchronize_session=False)
        s.query(LoteMaterial).filter(LoteMaterial.codigo_material == sku).delete(synchronize_session=False)
        s.query(ArticuloInventario).filter(ArticuloInventario.id_articulo == id_art).delete(synchronize_session=False)
        s.commit()
        s.close()
        engine.dispose()
