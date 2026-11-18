# tests/test_mapa_op_pg.py
"""
Mapa de la OP sobre PostgreSQL, con los roles y permisos reales de la copia (migraciones 25 a 34):
- COSTOS ve pedido y cotización con valor (PERM_VALOR_COTIZADO_VER de la migración 25), sin cliente.
- VENTAS no ve números de OP: no abre el mapa (403).
- JEFE_PRODUCCION abre por defecto el mapa de procesos y ve los tiempos.
- OPERARIO recibe 403.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py. Requiere la
migración 34 aplicada (usuario obligatorio).
"""
import random
import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.v1 import mapa_op
from app.core import roles
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import Cotizacion, EstadoOPEnum, OrdenProduccion, Proyecto, SocioNegocio
from app.services import acceso_bd
from tests.test_roles_permisos_pg import sesion  # noqa: F401  (sesion es la fixture)

pytestmark = pytest.mark.pg


@pytest.fixture
def cliente(sesion):
    sufijo = uuid.uuid4().hex[:8]
    ids = {}
    for rol in (roles.VENTAS, roles.COSTOS, roles.JEFE_PRODUCCION, roles.OPERARIO):
        ids[rol] = str(uuid.uuid4())
        sesion.execute(text(
            "INSERT INTO usuarios (id_usuario, usuario, email, password_hash, nombre_completo, id_rol, activo) "
            "VALUES (:id, :usuario, NULL, '!SIN_CLAVE', 'Prueba mapa', :rol, true)"
        ), {"id": ids[rol], "usuario": f"mapa-{rol.lower()}-{sufijo}"[:50], "rol": rol})
    socio = SocioNegocio(id_socio=uuid.uuid4(), codigo_socio=str(random.randint(10_000_000, 99_999_999)), nit_cedula=str(uuid.uuid4().int)[:10],
                         razon_social="Cliente ficticio mapa", es_cliente=True)
    sesion.add(socio)
    sesion.flush()
    sesion.add(Cotizacion(id_socio=socio.id_socio, numero_cotizacion=f"COT-MAPA-{sufijo}", valor_total=2500000))
    pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido=f"PED-MAPA-{sufijo}", codigo_proyecto=f"PED-MAPA-{sufijo}",
                      cliente_nombre="Cliente ficticio mapa", requisitos_cliente="Según plano", confirmado=True,
                      cotizacion_total=2500000)
    sesion.add(pedido)
    sesion.flush()
    codigo = f"OP-MAPA-{sufijo}"
    sesion.add(OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op=codigo, cantidad_fabricar=1,
                               estado=EstadoOPEnum.EN_PRODUCCION))
    sesion.flush()

    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.add_middleware(acceso_bd.OcultarCamposPorRol)
    app.include_router(mapa_op.router, prefix="/api/v1/mapa-op")
    app.dependency_overrides[get_db] = lambda: sesion
    with TestClient(app) as client:
        yield client, ids, codigo, sufijo


def cabeceras(id_usuario, rol):
    t = create_access_token({"sub": id_usuario, "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def test_costos_ve_pedido_y_cotizacion_con_valor_sin_cliente(cliente):
    client, ids, codigo, sufijo = cliente
    datos = client.get(f"/api/v1/mapa-op/{codigo}", headers=cabeceras(ids[roles.COSTOS], roles.COSTOS)).json()

    nodos = {n["tipo"]: n for n in datos["relaciones"]["nodos"]}
    assert set(nodos) == {"OP", "PEDIDO", "COTIZACION"}
    assert nodos["COTIZACION"]["etiqueta"] == f"COT-MAPA-{sufijo}"
    assert nodos["COTIZACION"]["datos"]["valor_cotizado"] == 2500000
    assert datos["procesos"]["con_tiempos"] is True


def test_ventas_no_abre_el_mapa(cliente):
    client, ids, codigo, _ = cliente
    assert client.get(f"/api/v1/mapa-op/{codigo}", headers=cabeceras(ids[roles.VENTAS], roles.VENTAS)).status_code == 403


def test_el_jefe_abre_procesos_por_defecto_con_tiempos(cliente):
    client, ids, codigo, _ = cliente
    datos = client.get(f"/api/v1/mapa-op/{codigo}", headers=cabeceras(ids[roles.JEFE_PRODUCCION], roles.JEFE_PRODUCCION)).json()

    assert datos["por_defecto"] == "procesos" and datos["procesos"]["con_tiempos"] is True
    assert datos["mapas"] == ["relaciones", "procesos"]


def test_operario_recibe_403(cliente):
    client, ids, codigo, _ = cliente
    assert client.get(f"/api/v1/mapa-op/{codigo}", headers=cabeceras(ids[roles.OPERARIO], roles.JEFE_PRODUCCION)).status_code == 403
