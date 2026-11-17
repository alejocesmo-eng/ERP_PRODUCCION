# tests/test_tiempos_manuales_pg.py
"""
Migración 33 sobre PostgreSQL: columnas de carga manual en registro_tiempos_produccion, correcciones
con motivo, operarios por máquina y reversión que se detiene si hay filas manuales o correcciones.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py. La 33 se aplica
dentro de la prueba (es idempotente), esté o no aplicada en la copia.
"""
import uuid

import pytest
from sqlalchemy import text

from app.db.models import EstadoOPEnum, OrdenProduccion, Plano, Proyecto
from app.db.models_produccion import OperacionOT
from tests.test_roles_permisos_pg import RUTA_BASE_DATOS, ejecutar_sql, sesion  # noqa: F401  (sesion es la fixture)

pytestmark = pytest.mark.pg

MIGRACION_33 = RUTA_BASE_DATOS / "33_MIGRACION_CARGA_TIEMPOS_MANUAL.sql"
REVERSION_33 = RUTA_BASE_DATOS / "33_REVERSION_CARGA_TIEMPOS_MANUAL.sql"


def crear_op_y_proceso(sesion):
    """OP ficticia con un proceso en su ruta; devuelve (id_op, id_operacion)."""
    sufijo = uuid.uuid4().hex[:6]
    pedido = Proyecto(id_proyecto=uuid.uuid4(), numero_pedido=f"PED-M33-{sufijo}", codigo_proyecto=f"PED-M33-{sufijo}",
                      cliente_nombre="Cliente ficticio M33", requisitos_cliente="Según plano", confirmado=True)
    sesion.add(pedido)
    sesion.flush()
    plano = Plano(id_proyecto=pedido.id_proyecto, codigo_plano=f"PLN-M33-{sufijo}", unidad_planta="Mecanizados")
    op = OrdenProduccion(id_proyecto=pedido.id_proyecto, codigo_op=f"OP-M33-{sufijo}", cantidad_fabricar=1,
                         estado=EstadoOPEnum.EN_PRODUCCION)
    sesion.add_all([plano, op])
    sesion.flush()
    proceso = OperacionOT(id_plano=plano.id_plano, codigo_op=op.codigo_op, codigo_plano=plano.codigo_plano,
                          secuencia_paso=10, nombre_proceso="Torneado")
    sesion.add(proceso)
    sesion.flush()
    return op.id_op, proceso.id_operacion


def insertar_manual(sesion, id_op, id_operacion, **cambios):
    valores = {"op": id_op, "proc": id_operacion, "fecha": "2026-11-16", "por": "capturista@prueba.test", **cambios}
    return sesion.execute(text(
        "INSERT INTO registro_tiempos_produccion (orden_produccion_id, operario_id, estacion_id, tipo_tiempo, "
        "segundos_ejecutados, segundos_setup, id_operacion, fecha_trabajo, origen, registrado_por) "
        "VALUES (:op, 'operario@prueba.test', 'TORNO-01', 'MECANIZADO', 2700, 900, :proc, :fecha, 'MANUAL', :por) "
        "RETURNING id"
    ), valores).scalar_one()


def existe(sesion, tabla):
    return sesion.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{tabla}"}).scalar() is not None


def columnas(sesion):
    return set(sesion.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'registro_tiempos_produccion'"
    )).scalars())


def test_la_migracion_agrega_columnas_y_tablas_y_es_idempotente(sesion):
    ejecutar_sql(sesion, MIGRACION_33)
    ejecutar_sql(sesion, MIGRACION_33)

    assert {"id_operacion", "segundos_setup", "fecha_trabajo", "origen", "registrado_por"} <= columnas(sesion)
    assert existe(sesion, "tiempos_manuales_correcciones") and existe(sesion, "maquina_operarios")
    # Las filas del cronómetro quedan con origen CRONOMETRO
    assert sesion.execute(text(
        "SELECT count(*) FROM registro_tiempos_produccion WHERE origen IS DISTINCT FROM 'CRONOMETRO' AND origen <> 'MANUAL'"
    )).scalar() == 0


def test_una_fila_manual_exige_proceso_fecha_y_quien_registro(sesion):
    ejecutar_sql(sesion, MIGRACION_33)
    id_op, id_operacion = crear_op_y_proceso(sesion)
    insertar_manual(sesion, id_op, id_operacion)

    for cambios in ({"proc": None}, {"fecha": None}, {"por": None}):
        with pytest.raises(Exception, match="ck_registro_tiempos_manual"):
            with sesion.begin_nested():
                insertar_manual(sesion, id_op, id_operacion, **cambios)


def test_la_correccion_exige_motivo(sesion):
    ejecutar_sql(sesion, MIGRACION_33)
    id_op, id_operacion = crear_op_y_proceso(sesion)
    id_registro = insertar_manual(sesion, id_op, id_operacion)
    insertar = text(
        "INSERT INTO tiempos_manuales_correcciones (id_registro, valores_anteriores, valores_nuevos, motivo, corregido_por) "
        "VALUES (:r, '{}'::jsonb, '{}'::jsonb, :m, 'lider@prueba.test')"
    )
    sesion.execute(insertar, {"r": id_registro, "m": "Se digitó mal"})

    with pytest.raises(Exception, match="tiempos_manuales_correcciones_motivo_check"):
        with sesion.begin_nested():
            sesion.execute(insertar, {"r": id_registro, "m": "   "})


def test_la_reversion_se_detiene_si_hay_tiempos_manuales_y_si_no_quita_todo(sesion):
    ejecutar_sql(sesion, MIGRACION_33)
    id_op, id_operacion = crear_op_y_proceso(sesion)
    # Datos que ya tuviera la copia: se quitan dentro de la transacción de la prueba
    sesion.execute(text("DELETE FROM tiempos_manuales_correcciones"))
    sesion.execute(text("DELETE FROM registro_tiempos_produccion WHERE origen = 'MANUAL'"))
    insertar_manual(sesion, id_op, id_operacion)

    with pytest.raises(Exception, match="fila\\(s\\) manuales"):
        with sesion.begin_nested():
            ejecutar_sql(sesion, REVERSION_33)
    assert existe(sesion, "tiempos_manuales_correcciones")

    sesion.execute(text("DELETE FROM registro_tiempos_produccion WHERE origen = 'MANUAL'"))
    ejecutar_sql(sesion, REVERSION_33)
    ejecutar_sql(sesion, REVERSION_33)

    assert not existe(sesion, "tiempos_manuales_correcciones") and not existe(sesion, "maquina_operarios")
    assert not {"id_operacion", "segundos_setup", "fecha_trabajo", "origen", "registrado_por"} & columnas(sesion)
