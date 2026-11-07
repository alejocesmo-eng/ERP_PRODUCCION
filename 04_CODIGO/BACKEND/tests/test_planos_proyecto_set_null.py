# tests/test_planos_proyecto_set_null.py
"""
Migración 18: el plano pertenece al producto y sobrevive al proyecto.
Borrar un proyecto con planos deja los planos con id_proyecto nulo y no los borra,
tanto desde el ORM (Proyecto.planos sin delete-orphan) como en la base (ON DELETE SET NULL).

Se ejecuta sobre la copia PostgreSQL de SGI_TEST_PG_URL (sgi_test_*), dentro de una
transacción que se revierte al terminar.
"""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.models import Plano, Proyecto

URL_PG = os.environ.get("SGI_TEST_PG_URL")

pytestmark = pytest.mark.pg


@pytest.fixture
def sesion():
    assert (make_url(URL_PG).database or "").startswith("sgi_test_"), "Solo se prueba sobre copias sgi_test_*."
    engine = create_engine(URL_PG)
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()
        engine.dispose()


def crear_proyecto_con_planos(sesion, cantidad=2):
    sufijo = uuid.uuid4().hex[:8].upper()
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(),
        numero_pedido=f"PED-SN-{sufijo}",
        codigo_proyecto=f"PRY-SN-{sufijo}",
        cliente_nombre="Cliente SET NULL",
        requisitos_cliente="Según plano",
        confirmado=True,
    )
    planos = [
        Plano(
            id_plano=uuid.uuid4(),
            id_proyecto=proyecto.id_proyecto,
            codigo_op=f"OP-SN-{sufijo}",
            codigo_plano=f"PLN-SN-{sufijo}-{indice}",
            version="V-01",
        )
        for indice in range(cantidad)
    ]
    sesion.add(proyecto)
    sesion.add_all(planos)
    sesion.commit()
    return proyecto, [plano.id_plano for plano in planos]


def test_borrar_proyecto_desde_el_orm_conserva_los_planos_con_id_proyecto_nulo(sesion):
    proyecto, ids_planos = crear_proyecto_con_planos(sesion)
    assert len(proyecto.planos) == 2

    sesion.delete(proyecto)
    sesion.commit()

    sesion.expire_all()
    assert sesion.get(Proyecto, proyecto.id_proyecto) is None
    planos = sesion.query(Plano).filter(Plano.id_plano.in_(ids_planos)).all()
    assert len(planos) == 2
    assert all(plano.id_proyecto is None for plano in planos)


def test_borrar_proyecto_en_la_base_aplica_on_delete_set_null(sesion):
    proyecto, ids_planos = crear_proyecto_con_planos(sesion)

    sesion.execute(text("DELETE FROM proyectos WHERE id_proyecto = :id"), {"id": proyecto.id_proyecto})
    sesion.commit()

    sesion.expire_all()
    planos = sesion.query(Plano).filter(Plano.id_plano.in_(ids_planos)).all()
    assert len(planos) == 2
    assert all(plano.id_proyecto is None for plano in planos)
