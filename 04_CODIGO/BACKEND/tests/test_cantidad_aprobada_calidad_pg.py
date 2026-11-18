# tests/test_cantidad_aprobada_calidad_pg.py
"""
Migración 35 sobre PostgreSQL: cantidad_aprobada y tipo_aprobacion en inspecciones_calidad.
- Solo APROBADO_DESPACHO aprueba piezas; INDIVIDUAL aprueba exactamente una; sin piezas, sin tipo.
- Las inspecciones anteriores quedan con 0.
- Reversión: se detiene si alguna inspección aprobó piezas; si no, quita las columnas.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py. La 35 se aplica
dentro de la prueba (es idempotente), esté o no aplicada en la copia.
"""
import uuid

import pytest
from sqlalchemy import text

from app.db.models_calidad import InspeccionCalidad
from tests.test_roles_permisos_pg import RUTA_BASE_DATOS, ejecutar_sql, sesion  # noqa: F401  (sesion es la fixture)

pytestmark = pytest.mark.pg

MIGRACION_35 = RUTA_BASE_DATOS / "35_MIGRACION_CANTIDAD_APROBADA_CALIDAD.sql"
REVERSION_35 = RUTA_BASE_DATOS / "35_REVERSION_CANTIDAD_APROBADA_CALIDAD.sql"


def inspeccion(resultado, cantidad, tipo):
    return InspeccionCalidad(
        codigo_op=f"OP-M35-{uuid.uuid4().hex[:6]}", codigo_plano="PLN-M35", inspector_nombre="Inspector M35",
        resultado_inspeccion=resultado, cantidad_aprobada=cantidad, tipo_aprobacion=tipo,
    )


def columnas(sesion):
    return set(sesion.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'inspecciones_calidad'"
    )).scalars())


def test_la_migracion_agrega_las_columnas_y_es_idempotente(sesion):
    ejecutar_sql(sesion, MIGRACION_35)
    ejecutar_sql(sesion, MIGRACION_35)

    assert {"cantidad_aprobada", "tipo_aprobacion"} <= columnas(sesion)
    # Las inspecciones anteriores quedan sin piezas ni tipo
    assert sesion.execute(text(
        "SELECT count(*) FROM inspecciones_calidad WHERE cantidad_aprobada < 0 "
        "OR (cantidad_aprobada = 0 AND tipo_aprobacion IS NOT NULL)"
    )).scalar() == 0


def test_aprobaciones_validas(sesion):
    ejecutar_sql(sesion, MIGRACION_35)
    sesion.add_all([
        inspeccion("APROBADO_DESPACHO", 1, "INDIVIDUAL"),
        inspeccion("APROBADO_DESPACHO", 5, "LOTE"),
        inspeccion("RECHAZADO", 0, None),
        inspeccion("APROBADO_TRATAMIENTO", 0, None),
    ])
    sesion.flush()


@pytest.mark.parametrize("resultado, cantidad, tipo", [
    ("APROBADO_DESPACHO", 2, "INDIVIDUAL"),   # individual = una pieza
    ("RECHAZADO", 1, "LOTE"),                 # solo el despacho aprueba piezas
    ("APROBADO_DESPACHO", 3, None),           # con piezas, con tipo
    ("APROBADO_DESPACHO", 0, "LOTE"),         # sin piezas, sin tipo
    ("APROBADO_DESPACHO", 2, "OTRO"),
])
def test_aprobaciones_no_validas(sesion, resultado, cantidad, tipo):
    ejecutar_sql(sesion, MIGRACION_35)
    with pytest.raises(Exception, match="ck_inspecciones_tipo_aprobacion"):
        with sesion.begin_nested():
            sesion.add(inspeccion(resultado, cantidad, tipo))
            sesion.flush()


def test_la_cantidad_aprobada_no_es_negativa(sesion):
    ejecutar_sql(sesion, MIGRACION_35)
    with pytest.raises(Exception, match="ck_inspecciones_cantidad_aprobada"):
        with sesion.begin_nested():
            sesion.add(inspeccion("APROBADO_DESPACHO", -1, "LOTE"))
            sesion.flush()


def test_la_reversion_se_detiene_con_piezas_aprobadas_y_si_no_quita_las_columnas(sesion):
    ejecutar_sql(sesion, MIGRACION_35)
    fila = inspeccion("APROBADO_DESPACHO", 2, "LOTE")
    sesion.add(fila)
    sesion.flush()
    # Aprobaciones que ya tuviera la copia: se dejan en 0 dentro de la transacción de la prueba
    sesion.execute(text("UPDATE inspecciones_calidad SET cantidad_aprobada = 0, tipo_aprobacion = NULL "
                        "WHERE id_inspeccion <> :id"), {"id": fila.id_inspeccion})

    with pytest.raises(Exception, match="piezas aprobadas"):
        with sesion.begin_nested():
            ejecutar_sql(sesion, REVERSION_35)
    assert "cantidad_aprobada" in columnas(sesion)

    sesion.execute(text("UPDATE inspecciones_calidad SET cantidad_aprobada = 0, tipo_aprobacion = NULL"))
    ejecutar_sql(sesion, REVERSION_35)
    ejecutar_sql(sesion, REVERSION_35)  # idempotente

    assert not {"cantidad_aprobada", "tipo_aprobacion"} & columnas(sesion)
