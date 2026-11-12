# tests/test_op_unidad_actual_pg.py
"""
Migración 28 sobre PostgreSQL: unidad_actual de la OP según el proceso en el que está, tabla de
traslados con sus restricciones y reversión que se detiene si hay traslados.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py. La 28 se
aplica dentro de la prueba (es idempotente), esté o no aplicada en la copia; las OP de prueba se
crean en SIN_ASIGNAR y se vuelve a aplicar la migración para que las deduzca.
"""
import uuid

import pytest
from sqlalchemy import text

from app.db.models import EstadoOPEnum, OrdenProduccion, Plano, Proyecto, TrasladoUnidadOP
from app.db.models_calidad import InspeccionCalidad
from tests.test_roles_permisos_pg import RUTA_BASE_DATOS, ejecutar_sql, sesion  # noqa: F401  (sesion es la fixture)

pytestmark = pytest.mark.pg

MIGRACION_28 = RUTA_BASE_DATOS / "28_MIGRACION_OP_UNIDAD_ACTUAL.sql"
REVERSION_28 = RUTA_BASE_DATOS / "28_REVERSION_OP_UNIDAD_ACTUAL.sql"


def crear_ops(sesion):
    """OP de prueba en SIN_ASIGNAR; devuelve {codigo: unidad esperada tras la migración}."""
    sufijo = uuid.uuid4().hex[:6]
    pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido=f"PED-M28-{sufijo}", codigo_proyecto=f"PED-M28-{sufijo}",
                      cliente_nombre="Cliente ficticio M28", requisitos_cliente="Según plano", confirmado=True)
    sesion.add(pedido)
    sesion.flush()
    planos = {
        unidad: Plano(id_proyecto=pedido.id_proyecto, codigo_plano=f"PLN-M28-{unidad[:3]}-{sufijo}", unidad_planta=unidad)
        for unidad in ("Metalistería", "Servicios", "Pintura")
    }
    sesion.add_all(planos.values())
    sesion.flush()
    casos = {
        # codigo: (estado, plano, última inspección, unidad esperada)
        "EN-PROD-MET": (EstadoOPEnum.EN_PRODUCCION, "Metalistería", None, "METALISTERIA"),
        "LIBERADA-SER": (EstadoOPEnum.LIBERADA, "Servicios", None, "SERVICIOS"),
        "TERCERO": (EstadoOPEnum.EN_INSPECCION, "Servicios", "APROBADO_TRATAMIENTO", "TERCERO"),
        "DESPACHO": (EstadoOPEnum.LISTA_PARA_LIBERAR, "Servicios", "APROBADO_DESPACHO", "DESPACHO"),
        "CERRADA": (EstadoOPEnum.CERRADA, None, None, "DESPACHO"),
        "BORRADOR": (EstadoOPEnum.BORRADOR, "Servicios", None, "SIN_ASIGNAR"),
        "SIN-PLANO": (EstadoOPEnum.EN_PRODUCCION, None, None, "SIN_ASIGNAR"),
        "PLANO-RARO": (EstadoOPEnum.EN_PRODUCCION, "Pintura", None, "SIN_ASIGNAR"),
        "LISTA-SIN-INSP": (EstadoOPEnum.LISTA_PARA_LIBERAR, "Servicios", None, "SIN_ASIGNAR"),
    }
    esperados = {}
    for nombre, (estado, plano, inspeccion, esperado) in casos.items():
        codigo = f"OP-M28-{nombre}-{sufijo}"
        sesion.add(OrdenProduccion(
            id_proyecto=pedido.id_proyecto, codigo_op=codigo, cantidad_fabricar=1, estado=estado,
            id_plano=planos[plano].id_plano if plano else None, unidad_actual="SIN_ASIGNAR",
        ))
        if inspeccion:
            sesion.add(InspeccionCalidad(codigo_op=codigo, codigo_plano="PLN-M28", inspector_nombre="Inspector M28",
                                         resultado_inspeccion=inspeccion))
        esperados[codigo] = esperado
    sesion.flush()
    return esperados


def unidades(sesion, codigos):
    return dict(sesion.execute(
        text("SELECT codigo_op, unidad_actual FROM ordenes_produccion WHERE codigo_op = ANY(:c)"), {"c": list(codigos)}
    ).all())


def test_la_migracion_deduce_la_unidad_segun_el_proceso(sesion):
    ejecutar_sql(sesion, MIGRACION_28)
    esperados = crear_ops(sesion)

    ejecutar_sql(sesion, MIGRACION_28)

    assert unidades(sesion, esperados) == esperados


def test_volver_a_aplicarla_no_deshace_un_traslado(sesion):
    ejecutar_sql(sesion, MIGRACION_28)
    esperados = crear_ops(sesion)
    ejecutar_sql(sesion, MIGRACION_28)
    codigo = next(c for c, u in esperados.items() if u == "METALISTERIA")
    sesion.execute(text("UPDATE ordenes_produccion SET unidad_actual = 'TERCERO' WHERE codigo_op = :c"), {"c": codigo})

    ejecutar_sql(sesion, MIGRACION_28)

    assert unidades(sesion, [codigo]) == {codigo: "TERCERO"}


def test_la_tabla_de_traslados_exige_unidades_validas(sesion):
    ejecutar_sql(sesion, MIGRACION_28)
    esperados = crear_ops(sesion)
    id_op = sesion.execute(
        text("SELECT id_op FROM ordenes_produccion WHERE codigo_op = :c"), {"c": next(iter(esperados))}
    ).scalar_one()

    for origen, destino in [("MECANIZADOS", "SIN_ASIGNAR"), ("MECANIZADOS", "MECANIZADOS"), ("MECANIZADOS", "BODEGA")]:
        with pytest.raises(Exception, match="ck_op_traslados_unidad"):
            with sesion.begin_nested():
                sesion.add(TrasladoUnidadOP(id_op=id_op, unidad_origen=origen, unidad_destino=destino,
                                            usuario_email="m28@prueba.test"))
                sesion.flush()
    with pytest.raises(Exception, match="ck_ordenes_produccion_unidad_actual"):
        with sesion.begin_nested():
            sesion.execute(text("UPDATE ordenes_produccion SET unidad_actual = 'BODEGA' WHERE id_op = :id"), {"id": id_op})


def test_la_reversion_se_detiene_si_hay_traslados_y_si_no_quita_todo(sesion):
    ejecutar_sql(sesion, MIGRACION_28)
    esperados = crear_ops(sesion)
    id_op = sesion.execute(
        text("SELECT id_op FROM ordenes_produccion WHERE codigo_op = :c"), {"c": next(iter(esperados))}
    ).scalar_one()
    # Traslados que ya tuviera la copia: se quitan dentro de la transacción de la prueba
    sesion.execute(text("DELETE FROM op_traslados_unidad"))
    sesion.add(TrasladoUnidadOP(id_op=id_op, unidad_origen="SIN_ASIGNAR", unidad_destino="MECANIZADOS",
                                usuario_email="m28@prueba.test"))
    sesion.flush()

    with pytest.raises(Exception, match="respáldelos"):
        with sesion.begin_nested():
            ejecutar_sql(sesion, REVERSION_28)

    sesion.execute(text("DELETE FROM op_traslados_unidad"))
    ejecutar_sql(sesion, REVERSION_28)
    ejecutar_sql(sesion, REVERSION_28)  # idempotente
    assert sesion.execute(text("SELECT to_regclass('public.op_traslados_unidad')")).scalar() is None
    assert sesion.execute(text(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'ordenes_produccion' AND column_name = 'unidad_actual'"
    )).scalar() == 0
