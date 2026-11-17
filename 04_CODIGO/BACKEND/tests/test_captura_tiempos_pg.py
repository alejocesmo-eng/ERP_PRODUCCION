# tests/test_captura_tiempos_pg.py
"""
Pantalla "Captura de tiempos" sobre PostgreSQL: GET /tiempos-manuales/ops con los permisos reales
de las migraciones 29, 30 y 32 (PERM_TIEMPOS_REGISTRAR leído de rol_permisos en cada petición).
- CAPTURISTA_TIEMPOS entra (es una ruta fija de RUTAS_CAPTURISTA) y ve solo las OP abiertas, sin
  costos, cliente ni planos.
- OPERARIO tiene el permiso pero no carga tiempos a mano: 403. VENTAS no tiene el permiso: 403.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py. Requiere la
migración 34 aplicada en la copia (usuario obligatorio).
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.v1 import tiempos_manuales
from app.core import roles
from app.core.security import create_access_token
from app.db.database import get_db
from app.db.models import EstadoOPEnum, OrdenProduccion, Proyecto
from app.services import acceso_bd
from tests.test_roles_permisos_pg import RUTA_BASE_DATOS, ejecutar_sql, sesion  # noqa: F401  (sesion es la fixture)

pytestmark = pytest.mark.pg

MIGRACIONES = [RUTA_BASE_DATOS / nombre for nombre in (
    "29_MIGRACION_ROL_CAPTURISTA_TIEMPOS.sql", "30_MIGRACION_TIEMPOS_LIDER_MECANIZADOS.sql",
    "32_MIGRACION_ROL_LIDER_SERVICIOS.sql",
)]


@pytest.fixture
def cliente(sesion):
    for migracion in MIGRACIONES:
        ejecutar_sql(sesion, migracion)
    sufijo = uuid.uuid4().hex[:8]
    ids = {}
    for rol in (roles.CAPTURISTA_TIEMPOS, roles.OPERARIO, roles.VENTAS):
        ids[rol] = str(uuid.uuid4())
        sesion.execute(text(
            "INSERT INTO usuarios (id_usuario, usuario, email, password_hash, nombre_completo, id_rol, activo) "
            "VALUES (:id, :usuario, NULL, '!SIN_CLAVE', 'Prueba captura', :rol, true)"
        ), {"id": ids[rol], "usuario": f"cap-{rol.lower()}-{sufijo}"[:50], "rol": rol})
    pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido=f"PED-CAP-{sufijo}", codigo_proyecto=f"PED-CAP-{sufijo}",
                      cliente_nombre="Cliente ficticio captura", requisitos_cliente="Según plano", confirmado=True)
    sesion.add(pedido)
    sesion.flush()
    codigos = {}
    for nombre, estado in (("ABIERTA", EstadoOPEnum.EN_PRODUCCION), ("CERRADA", EstadoOPEnum.CERRADA)):
        codigos[nombre] = f"OP-CAP-{nombre}-{sufijo}"
        sesion.add(OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op=codigos[nombre], cantidad_fabricar=1,
                                   estado=estado))
    sesion.flush()

    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.add_middleware(acceso_bd.OcultarCamposPorRol)
    app.include_router(tiempos_manuales.router, prefix="/api/v1/tiempos-manuales")
    app.dependency_overrides[get_db] = lambda: sesion
    with TestClient(app) as client:
        yield client, ids, codigos


def cabeceras(id_usuario, rol):
    t = create_access_token({"sub": id_usuario, "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def test_el_capturista_ve_las_op_abiertas_sin_cliente_costos_ni_planos(cliente):
    client, ids, codigos = cliente
    respuesta = client.get("/api/v1/tiempos-manuales/ops", headers=cabeceras(ids[roles.CAPTURISTA_TIEMPOS], roles.CAPTURISTA_TIEMPOS))

    assert respuesta.status_code == 200, respuesta.text
    por_codigo = {fila["codigo_op"]: fila for fila in respuesta.json()}
    assert codigos["ABIERTA"] in por_codigo and codigos["CERRADA"] not in por_codigo
    assert set(por_codigo[codigos["ABIERTA"]]) == {"codigo_op", "numero_pedido", "codigo_producto", "producto"}


@pytest.mark.parametrize("rol", [roles.OPERARIO, roles.VENTAS])
def test_operario_y_roles_sin_permiso_reciben_403(cliente, rol):
    client, ids, _ = cliente
    # El rol del token no cuenta: se lee de la base
    assert client.get("/api/v1/tiempos-manuales/ops", headers=cabeceras(ids[rol], roles.CAPTURISTA_TIEMPOS)).status_code == 403
