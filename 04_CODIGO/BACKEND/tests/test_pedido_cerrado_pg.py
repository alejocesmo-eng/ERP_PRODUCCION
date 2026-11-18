# tests/test_pedido_cerrado_pg.py
"""
Migración 36 sobre PostgreSQL: estado CERRADO del pedido y aviso OP_CERRADA_RESPALDO.
- proyectos.estado queda con tipo estado_proyecto, NOT NULL, por defecto BORRADOR y con CERRADO.
- tiponotificacionenum recibe OP_CERRADA_RESPALDO. La migración es idempotente.
- Reversión: se detiene con pedidos CERRADO; si no, quita CERRADO y OP_CERRADA_RESPALDO.

Misma copia sgi_test_* y transacción revertida que tests/test_roles_permisos_pg.py. PostgreSQL no
deja usar en la misma transacción un valor de ENUM recién agregado: la parte que guarda un pedido
CERRADO solo corre si la copia ya tenía la migración 36.
"""
import pytest
from sqlalchemy import text

from tests.test_roles_permisos_pg import RUTA_BASE_DATOS, ejecutar_sql, sesion  # noqa: F401  (sesion es la fixture)

pytestmark = pytest.mark.pg

MIGRACION_36 = RUTA_BASE_DATOS / "36_MIGRACION_PEDIDO_CERRADO.sql"
REVERSION_36 = RUTA_BASE_DATOS / "36_REVERSION_PEDIDO_CERRADO.sql"


def valores(sesion, tipo):
    return set(sesion.execute(text(
        "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = :tipo"
    ), {"tipo": tipo}).scalars())


def columna_estado(sesion):
    return sesion.execute(text(
        "SELECT udt_name, is_nullable, column_default FROM information_schema.columns "
        "WHERE table_name = 'proyectos' AND column_name = 'estado'"
    )).first()


def test_la_migracion_agrega_cerrado_y_es_idempotente(sesion):
    ejecutar_sql(sesion, MIGRACION_36)
    ejecutar_sql(sesion, MIGRACION_36)

    assert "CERRADO" in valores(sesion, "estado_proyecto")
    assert "OP_CERRADA_RESPALDO" in valores(sesion, "tiponotificacionenum")
    tipo, nula, defecto = columna_estado(sesion)
    assert (tipo, nula) == ("estado_proyecto", "NO") and "BORRADOR" in defecto
    # Los pedidos existentes toman su estado de confirmado
    assert sesion.execute(text(
        "SELECT count(*) FROM proyectos WHERE estado::text NOT IN ('BORRADOR', 'CONFIRMADO', 'EN_DISENO', "
        "'FINALIZADO', 'CANCELADO', 'CERRADO')"
    )).scalar() == 0


def test_la_reversion_quita_los_valores_nuevos(sesion):
    ejecutar_sql(sesion, MIGRACION_36)
    sesion.execute(text("DELETE FROM notificaciones_lider WHERE tipo_notificacion::text = 'OP_CERRADA_RESPALDO'"))
    sesion.execute(text("UPDATE proyectos SET estado = 'CONFIRMADO' WHERE estado::text = 'CERRADO'"))

    ejecutar_sql(sesion, REVERSION_36)
    ejecutar_sql(sesion, REVERSION_36)  # idempotente

    assert "CERRADO" not in valores(sesion, "estado_proyecto")
    assert "OP_CERRADA_RESPALDO" not in valores(sesion, "tiponotificacionenum")


def test_la_reversion_se_detiene_con_pedidos_cerrados(sesion):
    if "CERRADO" not in valores(sesion, "estado_proyecto"):
        pytest.skip("La copia no tiene la migración 36: CERRADO no se puede usar en la misma transacción.")
    ejecutar_sql(sesion, MIGRACION_36)
    id_proyecto = sesion.execute(text("SELECT id_proyecto FROM proyectos LIMIT 1")).scalar()
    if id_proyecto is None:
        pytest.skip("La copia no tiene pedidos.")
    sesion.execute(text("UPDATE proyectos SET estado = 'CERRADO' WHERE id_proyecto = :id"), {"id": id_proyecto})

    with pytest.raises(Exception, match="CERRADO"):
        with sesion.begin_nested():
            ejecutar_sql(sesion, REVERSION_36)
    assert "CERRADO" in valores(sesion, "estado_proyecto")
