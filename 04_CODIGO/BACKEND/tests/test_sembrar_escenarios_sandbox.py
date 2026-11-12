# tests/test_sembrar_escenarios_sandbox.py
"""
Semilla de escenarios (SCRUM-33) sin PostgreSQL: se ejecuta dos veces sobre SQLite en memoria
con el esquema de los modelos y los usuarios demo que usa. La segunda corrida no crea ni
cambia nada (repetible), los datos cubren los escenarios representables y lo que depende de
otros pasos queda en PENDIENTES. Los PDF se escriben en una carpeta temporal.
Las restricciones propias de PostgreSQL (CHECK de codigo_rn, NIT y sha256) se revisan aparte.
"""
import hashlib
import re
import uuid

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import (
    BOMListaMateriales,
    Cotizacion,
    EntregaMaterialOP,
    OrdenPicking,
    OrdenProduccion,
    Plano,
    PlanoArchivo,
    Producto,
    Proyecto,
    Rol,
    SocioNegocio,
    Usuario,
)
from scripts import sembrar_escenarios_sandbox as semilla


@pytest.fixture
def Sesion(tmp_path, monkeypatch):
    monkeypatch.setattr(semilla, "DIRECTORIO_PLANOS", tmp_path / "planos")
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)
    yield fabrica
    Base.metadata.drop_all(engine)
    engine.dispose()


def crear_usuarios_demo(Sesion, activos=True):
    with Sesion() as s:
        s.add(Rol(id_rol="DEMO", nombre_rol="Demo"))
        for correo in semilla.CORREOS.values():
            s.add(Usuario(id_usuario=uuid.uuid4(), email=correo, password_hash="!SIN_CLAVE",
                          nombre_completo=correo, id_rol="DEMO", activo=activos))
        s.commit()


def correr(Sesion):
    with Sesion() as s:
        resultados = semilla.sembrar(s)
        if all(r.estado != "error" for r in resultados):
            s.commit()
    return {r.bloque: r for r in resultados}


def conteos(Sesion):
    with Sesion() as s:
        return {
            tabla.name: s.execute(func.count().select().select_from(tabla)).scalar()
            for tabla in Base.metadata.sorted_tables
        }


def test_completa_todos_los_bloques_y_la_segunda_corrida_no_cambia_nada(Sesion):
    crear_usuarios_demo(Sesion)

    primera = correr(Sesion)
    despues_primera = conteos(Sesion)
    segunda = correr(Sesion)

    assert [r.estado for r in primera.values()] == ["sin cambios"] + ["creado"] * (len(semilla.BLOQUES) - 1)
    assert all(r.estado == "sin cambios" and r.creados == r.actualizados == 0 for r in segunda.values()), segunda
    assert conteos(Sesion) == despues_primera


def test_datos_de_los_escenarios(Sesion):
    crear_usuarios_demo(Sesion)
    correr(Sesion)

    with Sesion() as s:
        clientes = {x.codigo_socio: x for x in s.query(SocioNegocio).filter(SocioNegocio.es_cliente.is_(True))}
        assert set(clientes) == {"900000001", "900000002", "900000003"}
        assert all(re.fullmatch(r"[0-9]{5,15}", nit) for nit in clientes)
        # E12: Comercial Demo Sur sin trabajos
        sur = s.query(Proyecto).filter(Proyecto.cliente_nombre == "Comercial Demo Sur Ltda.").count()
        assert sur == 0
        # Productos con código RN válido para el CHECK de PostgreSQL
        assert all(re.fullmatch(r"RN-[0-9]{3}-[0-9]{3}-[0-9]{6}", p.codigo_rn) for p in s.query(Producto))
        # E1: cada pedido desde cotización sigue la convención PED-<número de la cotización>
        for numero, cotizacion, *_ in semilla.PEDIDOS:
            pedido = s.query(Proyecto).filter(Proyecto.numero_pedido == numero).one()
            assert pedido.confirmado and pedido.id_cliente is not None
            if cotizacion:
                assert numero == "PED-" + cotizacion.replace("COT-", "")
        # EMITIDA reemplaza a APROBADA: todas emitidas; E20: COT-DEMO-006 sin pedido nacido de ella
        assert {c.estado.value for c in s.query(Cotizacion)} == {"EMITIDA"}
        con_pedido = {p.numero_pedido for p in s.query(Proyecto) if p.cotizacion_total is not None}
        assert {numero for numero, cotizacion, *_ in semilla.PEDIDOS if cotizacion} == con_pedido
        assert s.query(Proyecto).filter(Proyecto.numero_pedido == "PED-DEMO-006").one().cotizacion_total is None
        # Planos de Mecanizados con PDF vigente cuyo sha256 coincide con el archivo; solo SM-110 sin aprobar
        aprobados = {p.codigo_plano for p in s.query(Plano) if p.estado.value == "APROBADO" and p.aprobado_por and p.fecha_aprobacion}
        assert aprobados == {"PLN-DEMO-SM100", "PLN-DEMO-BT200"}
        for plano in s.query(Plano):
            assert plano.unidad_planta == "Mecanizados"
            pdf = s.query(PlanoArchivo).filter_by(id_plano=plano.id_plano, tipo="PDF", vigente=True).one()
            contenido = (semilla.DIRECTORIO_PLANOS / pdf.nombre_original).read_bytes()
            assert contenido.startswith(b"%PDF-") and hashlib.sha256(contenido).hexdigest() == pdf.sha256
            assert pdf.tamano_bytes == len(contenido) and re.fullmatch(r"[0-9a-f]{64}", pdf.sha256)
        # E5: BT-200 con el perfil solo solicitado, 6 de 10 m entregados y la OP sin liberar
        bt200 = s.query(Plano).filter_by(codigo_plano="PLN-DEMO-BT200").one()
        perfil = s.query(BOMListaMateriales).filter_by(plano_id=bt200.id_plano, codigo_material="MP-DEMO-PERF40").one()
        assert perfil.estado_abastecimiento == "SOLICITADO" and perfil.cantidad_requerida == 10.0
        op2 = s.query(OrdenProduccion).filter_by(codigo_op="OP-DEMO-002").one()
        assert op2.estado.value == "BORRADOR" and not op2.reserva_stock_100
        assert [e.cantidad_entregada for e in s.query(EntregaMaterialOP).filter_by(op_id=op2.id_op)] == [6.0]
        # E6: OP de SM-110 con su plano en borrador (sin aprobación), con PDF y material entregado
        sm110 = s.query(Plano).filter_by(codigo_plano="PLN-DEMO-SM110").one()
        assert sm110.estado.value == "BORRADOR" and sm110.aprobado_por is None and sm110.fecha_aprobacion is None
        op3 = s.query(OrdenProduccion).filter_by(codigo_op="OP-DEMO-003").one()
        assert op3.id_plano == sm110.id_plano and op3.estado.value == "BORRADOR" and not op3.reserva_stock_100
        assert s.query(Proyecto).filter(Proyecto.numero_pedido == "PED-DEMO-008").one().confirmado
        # E8: OP terminada y aprobada por Calidad de producto
        op4 = s.query(OrdenProduccion).filter_by(codigo_op="OP-DEMO-004").one()
        calidad = s.query(Usuario).filter_by(email="calidadprod@sgi.local").one()
        assert op4.estado.value == "TERMINADA" and op4.aprobado_por_calidad_id == calidad.id_usuario
        # E16: una sola orden de picking para la línea de stock de PED-DEMO-003
        assert s.query(OrdenPicking).count() == 1


def test_sin_usuarios_demo_se_detiene_y_no_deja_nada(Sesion):
    crear_usuarios_demo(Sesion, activos=False)
    antes = conteos(Sesion)

    resultados = correr(Sesion)

    assert resultados["usuarios_demo"].estado == "error"
    assert "preparar_sandbox --usuarios-demo" in resultados["usuarios_demo"].detalle
    assert all(r.estado == "no ejecutado" for nombre, r in resultados.items() if nombre != "usuarios_demo")
    assert conteos(Sesion) == antes


def test_un_error_en_un_bloque_revierte_los_anteriores(Sesion, monkeypatch):
    crear_usuarios_demo(Sesion)
    antes = conteos(Sesion)

    def falla(s, ctx):
        raise RuntimeError("fallo simulado")

    bloques = list(semilla.BLOQUES)
    indice = [n for n, _ in bloques].index("pedidos")
    bloques[indice] = ("pedidos", falla)
    monkeypatch.setattr(semilla, "BLOQUES", tuple(bloques))

    resultados = correr(Sesion)

    assert resultados["pedidos"].estado == "error" and resultados["pedidos"].detalle == "fallo simulado"
    assert resultados["cotizaciones"].estado == "creado"
    assert resultados["picking"].estado == "no ejecutado"
    assert conteos(Sesion) == antes


def test_lo_que_depende_de_otros_pasos_queda_pendiente():
    pendientes = " ".join(escenario for escenario, _, _ in semilla.PENDIENTES)
    for escenario in ("E4", "E5", "E7", "E8", "E9", "E18", "E21"):
        assert escenario in pendientes
    # E6 ya se siembra (SM-110 con plano en borrador)
    assert "E6" not in [escenario for escenario, _, _ in semilla.PENDIENTES]
    dependencias = " ".join(depende for _, depende, _ in semilla.PENDIENTES)
    for paso in ("paso 3a", "paso 3b", "paso 4", "paso 5", "paso 6"):
        assert paso in dependencias


def test_el_pdf_demo_es_siempre_el_mismo():
    assert semilla.pdf_demo("PLN-X") == semilla.pdf_demo("PLN-X")
    assert semilla.pdf_demo("PLN-X") != semilla.pdf_demo("PLN-Y")
    assert semilla.pdf_demo("PLN-X").rstrip().endswith(b"%%EOF")


@pytest.mark.parametrize("base", ["sgi_db", "SGI_DB", "postgres", "sgi_test_template"])
def test_rechaza_bases_que_no_son_de_prueba_antes_de_conectar(monkeypatch, base):
    monkeypatch.setattr("sys.argv", ["sembrar_escenarios_sandbox", base])
    monkeypatch.setattr("scripts._pg_pruebas.conectar_admin", lambda: pytest.fail("No debe conectar"))

    with pytest.raises(SystemExit):
        semilla.main()
