# tests/test_operario_sin_cliente.py
"""
OPERARIO no recibe datos del cliente (reglas/permisos-por-rol-modulo.md): ninguna lectura GET de la
aplicación le devuelve nombre, NIT, contacto ni ubicación del cliente, también las que solo piden
token. Tampoco recibe el valor cotizado (solo VENTAS, JEFE_PRODUCCION, COSTOS y GESTION_CALIDAD).
Conserva plano, cantidad y detalles técnicos de sus operaciones.

Recorre todas las rutas GET de app.main (desde su OpenAPI) con un cliente ficticio sembrado y busca
sus datos en el cuerpo de la respuesta. Control: JEFE_PRODUCCION sí los recibe en las mismas rutas,
así que la prueba no pasa por vacío. SQLite en memoria con override de get_db.
"""
import re
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import (
    Cliente, Cotizacion, EstadoOPEnum, OrdenProduccion, Plano, Proyecto, Rol, SocioNegocio, Usuario,
)
from app.db.models_produccion import OperacionOT, SubLoteOperacion
from tests.ayudantes_usuarios import datos_usuario, id_prueba

# Datos del cliente ficticio que no deben llegarle a OPERARIO
RAZON_SOCIAL = "Cliente Reservado Zeta SAS"
NIT = "900777555"
CONTACTO = "Contacto Reservado Zeta"
CORREO = "reservado.zeta@cliente.test"
TELEFONO = "3009998877"
UBICACION = "Sede Reservada Zeta"
DATOS_CLIENTE = [RAZON_SOCIAL, NIT, CONTACTO, CORREO, TELEFONO, UBICACION]
# Valor cotizado del pedido y de la cotización: una cifra que no aparece en otro dato sembrado
VALOR_COTIZADO = 7654321.5
ROLES_PRUEBA = [roles.OPERARIO, roles.JEFE_PRODUCCION]


@pytest.fixture(scope="module")
def ctx():
    from app.main import app

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    ids = {}
    with Sesion() as s:
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in ROLES_PRUEBA)
        s.add_all(
            Usuario(**datos_usuario(f"{rol.lower()}"), password_hash="!SIN_CLAVE", nombre_completo=rol, id_rol=rol)
            for rol in ROLES_PRUEBA
        )
        cliente = Cliente(nit_rut=NIT, razon_social=RAZON_SOCIAL, contacto=CONTACTO, email_contacto=CORREO, telefono=TELEFONO)
        socio = SocioNegocio(codigo_socio=NIT, nit_cedula=NIT, razon_social=RAZON_SOCIAL, es_cliente=True,
                             es_proveedor=False, estado_activo=True)
        s.add_all([cliente, socio])
        s.flush()
        cotizacion = Cotizacion(id_socio=socio.id_socio, numero_cotizacion="COT-ZETA-1", valor_total=VALOR_COTIZADO)
        pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido="PED-ZETA-1", codigo_proyecto="PED-ZETA-1",
                          id_cliente=cliente.id_cliente, cliente_nombre=RAZON_SOCIAL, ubicacion_cliente=UBICACION,
                          requisitos_cliente="Tolerancia general ISO 2768-m", detalle_producto="Eje ZT",
                          cantidad=5, confirmado=True, cotizacion_total=VALOR_COTIZADO)
        s.add_all([cotizacion, pedido])
        s.flush()
        plano = Plano(id_proyecto=pedido.id_proyecto, codigo_plano="PLN-ZETA-1", codigo_op="OP-ZETA-1",
                      material_requerido="Acero 1045")
        s.add(plano)
        s.flush()
        s.add(OrdenProduccion(id_proyecto=pedido.id_proyecto, id_plano=plano.id_plano, codigo_op="OP-ZETA-1",
                              cantidad_fabricar=5, estado=EstadoOPEnum.TERMINADA, unidad_actual="MECANIZADOS"))
        operacion = OperacionOT(id_plano=plano.id_plano, codigo_op="OP-ZETA-1", codigo_plano="PLN-ZETA-1",
                                secuencia_paso=10, nombre_proceso="Torneado", cantidad_total_orden=5)
        s.add(operacion)
        s.flush()
        s.add(SubLoteOperacion(id_operacion=operacion.id_operacion, cantidad_asignada=5, operario_nombre="Operario"))
        s.commit()
        ids.update(id_proyecto=pedido.id_proyecto, id_cotizacion=cotizacion.id_cotizacion, id_plano=plano.id_plano,
                   id_cliente=cliente.id_cliente, id_socio=socio.id_socio)

    app.dependency_overrides[get_db] = _get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, ids, app
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def token(rol):
    t = create_access_token({"sub": str(id_prueba(f"{rol.lower()}")), "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def rutas_get(app, ids):
    """Cada ruta GET de la aplicación, con sus parámetros de ruta y de consulta obligatorios."""
    valores = {**{k: str(v) for k, v in ids.items()}, "codigo_op": "OP-ZETA-1", "codigo_plano": "PLN-ZETA-1",
               "numero_pedido": "PED-ZETA-1", "q": "zeta"}
    rutas = []
    for ruta, metodos in app.openapi()["paths"].items():
        if "get" not in metodos:
            continue
        url = re.sub(r"\{(\w+)\}", lambda m: valores.get(m.group(1), str(uuid.uuid4())), ruta)
        consulta = {
            p["name"]: valores.get(p["name"], "zeta")
            for p in metodos["get"].get("parameters", []) if p.get("in") == "query" and p.get("required")
        }
        rutas.append((url, consulta))
    return rutas


def con_datos_de_cliente(client, rol, rutas, datos=DATOS_CLIENTE):
    encontradas = {}
    for url, consulta in rutas:
        texto = client.get(url, params=consulta, headers=token(rol)).text
        presentes = [dato for dato in datos if dato.lower() in texto.lower()]
        if presentes:
            encontradas[url] = presentes
    return encontradas


def test_operario_no_recibe_datos_del_cliente_en_ninguna_lectura(ctx):
    client, ids, app = ctx
    rutas = rutas_get(app, ids)

    assert len(rutas) >= 42
    assert con_datos_de_cliente(client, roles.OPERARIO, rutas) == {}


def test_control_otro_rol_si_los_recibe_en_las_mismas_rutas(ctx):
    client, ids, app = ctx
    con_cliente = con_datos_de_cliente(client, roles.JEFE_PRODUCCION, rutas_get(app, ids))

    # La prueba anterior no pasa por vacío: esas rutas sí traen datos del cliente
    assert {"/api/v1/ordenes/", "/api/v1/proyectos/"} <= set(con_cliente)


def test_operario_no_recibe_el_valor_cotizado_en_ninguna_lectura(ctx):
    client, ids, app = ctx
    rutas = rutas_get(app, ids)
    cifra = [str(int(VALOR_COTIZADO))]

    assert con_datos_de_cliente(client, roles.OPERARIO, rutas, cifra) == {}
    # Control: el mismo valor sí sale a JEFE_PRODUCCION en el expediente del pedido
    assert f"/api/v1/proyectos/{ids['id_proyecto']}/expediente" in con_datos_de_cliente(
        client, roles.JEFE_PRODUCCION, rutas, cifra)


def test_el_expediente_del_pedido_de_operario_no_trae_valor_cotizado(ctx):
    client, ids, _ = ctx
    url = f"/api/v1/proyectos/{ids['id_proyecto']}/expediente"
    operario = client.get(url, headers=token(roles.OPERARIO)).json()
    jefe = client.get(url, headers=token(roles.JEFE_PRODUCCION)).json()

    assert "valor_total_cotizado" not in operario
    assert jefe["valor_total_cotizado"] == VALOR_COTIZADO
    # El resto del expediente sigue llegando
    assert operario["numero_pedido"] == "PED-ZETA-1"


def test_operario_conserva_plano_cantidad_y_detalles_tecnicos(ctx):
    client, _, _ = ctx
    (op,) = client.get("/api/v1/ordenes/", headers=token(roles.OPERARIO)).json()
    (sublote,) = client.get("/api/v1/operaciones/sublotes", headers=token(roles.OPERARIO)).json()

    assert (op["codigo_op"], op["codigo_plano"], op["cantidad"]) == ("OP-ZETA-1", "PLN-ZETA-1", 5)
    assert op["requisitos_cliente"] == "Tolerancia general ISO 2768-m"
    assert "cliente_nombre" not in op and "ubicacion_cliente" not in op
    assert (sublote["codigo_plano"], sublote["cantidad_asignada"], sublote["detalle_pieza"]) == ("PLN-ZETA-1", 5, "Acero 1045")
