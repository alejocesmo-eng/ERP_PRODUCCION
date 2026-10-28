import base64
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.calidad import (
    InspeccionCalidadCreate,
    _generar_informe_tratamiento_html,
    _generar_informe_tratamiento_pdf,
    registrar_inspeccion_calidad,
)
from app.api.v1.endpoints.produccion import (
    ReordenarSublotesSchema,
    EstadoSubloteUpdateSchema,
    actualizar_estado_sublote,
    reordenar_sublotes,
)
from app.db.database import Base
from app.db.models import Plano, Proyecto
from app.db.models_produccion import OperacionOT, SubLoteOperacion, TipoUnidadPlantaEnum


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Proyecto.__table__,
        Plano.__table__,
        OperacionOT.__table__,
        SubLoteOperacion.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tables)
        engine.dispose()


def crear_cola(db):
    proyecto = Proyecto(
        id_proyecto=uuid.uuid4(),
        numero_pedido="PED-TEST-001",
        codigo_proyecto="PRY-TEST-001",
        cliente_nombre="Cliente de prueba",
        detalle_producto="Eje de prueba",
        requisitos_cliente="Plano de prueba aprobado",
        confirmado=True,
    )
    plano = Plano(
        id_plano=uuid.uuid4(),
        id_proyecto=proyecto.id_proyecto,
        codigo_op="4001001",
        codigo_plano="PLN-TEST-001",
    )
    operacion = OperacionOT(
        id_operacion=uuid.uuid4(),
        id_plano=plano.id_plano,
        codigo_op="4001001",
        codigo_plano="PLN-TEST-001",
        secuencia_paso=10,
        unidad_planta=TipoUnidadPlantaEnum.MECANIZADOS,
        nombre_proceso="Torneado",
        cantidad_total_orden=2,
    )
    primero = SubLoteOperacion(
        id_sublote=uuid.uuid4(),
        id_operacion=operacion.id_operacion,
        numero_sublote="SUB-01",
        cantidad_asignada=1,
        operario_nombre="Operario de prueba",
        maquina_codigo="TORN-CNC-01",
        prioridad_cola=1,
    )
    segundo = SubLoteOperacion(
        id_sublote=uuid.uuid4(),
        id_operacion=operacion.id_operacion,
        numero_sublote="SUB-02",
        cantidad_asignada=1,
        operario_nombre="Operario de prueba",
        maquina_codigo="TORN-CNC-01",
        prioridad_cola=2,
    )
    db.add_all([proyecto, plano, operacion, primero, segundo])
    db.commit()
    return primero, segundo


def test_reordenamiento_persistente_de_sublotes(db):
    primero, segundo = crear_cola(db)

    resultado = reordenar_sublotes(
        ReordenarSublotesSchema(
            operario_nombre="Operario de prueba",
            orden_ids=[segundo.id_sublote, primero.id_sublote],
        ),
        db=db,
    )

    assert resultado["orden_ids"] == [segundo.id_sublote, primero.id_sublote]
    db.expire_all()
    assert db.get(SubLoteOperacion, segundo.id_sublote).prioridad_cola == 1
    assert db.get(SubLoteOperacion, primero.id_sublote).prioridad_cola == 2


def test_rechaza_colas_con_ids_duplicados_o_incompletos(db):
    primero, segundo = crear_cola(db)

    with pytest.raises(HTTPException) as error:
        reordenar_sublotes(
            ReordenarSublotesSchema(
                operario_nombre="Operario de prueba",
                orden_ids=[primero.id_sublote, primero.id_sublote],
            ),
            db=db,
        )

    assert error.value.status_code == 409
    assert db.get(SubLoteOperacion, segundo.id_sublote).prioridad_cola == 2


def test_reordenamiento_solo_afecta_la_cola_pendiente_de_la_estacion(db):
    primero, segundo = crear_cola(db)
    actualizar_estado_sublote(
        primero.id_sublote,
        EstadoSubloteUpdateSchema(estado_sublote="EN_SETUP"),
        db=db,
    )

    resultado = reordenar_sublotes(
        ReordenarSublotesSchema(
            operario_nombre="Operario de prueba",
            maquina_codigo="TORN-CNC-01",
            orden_ids=[segundo.id_sublote],
        ),
        db=db,
    )

    assert resultado["orden_ids"] == [segundo.id_sublote]
    assert db.get(SubLoteOperacion, primero.id_sublote).estado_sublote.value == "EN_SETUP"
    assert db.get(SubLoteOperacion, segundo.id_sublote).prioridad_cola == 1


def test_estado_sublote_rechaza_transiciones_no_permitidas(db):
    primero, _ = crear_cola(db)

    with pytest.raises(HTTPException) as error:
        actualizar_estado_sublote(
            primero.id_sublote,
            EstadoSubloteUpdateSchema(estado_sublote="COMPLETADA"),
            db=db,
        )

    assert error.value.status_code == 409
    assert db.get(SubLoteOperacion, primero.id_sublote).estado_sublote.value == "EN_COLA"


def test_inspeccion_requiere_fotografia_jpg_o_png_valida():
    solicitud = InspeccionCalidadCreate(
        codigo_op="4001001",
        codigo_plano="PLN-TEST-001",
        inspector_nombre="Inspector",
        resultado_inspeccion="APROBADO_DESPACHO",
        mediciones_dimensionales=[
            {
                "caracteristica": "Diámetro",
                "nominal": 25,
                "tolerancia_min": 24.98,
                "tolerancia_max": 25.02,
                "valor_medido": 25,
            }
        ],
        registros_fotograficos=["data:image/png;base64,no-es-una-imagen"],
    )

    with pytest.raises(HTTPException) as error:
        registrar_inspeccion_calidad(solicitud, db=None)

    assert error.value.status_code == 422


def test_informe_de_tratamiento_escapa_datos_del_proveedor():
    solicitud = InspeccionCalidadCreate(
        codigo_op="4001001",
        codigo_plano="PLN-TEST-001",
        inspector_nombre="Inspector",
        resultado_inspeccion="APROBADO_TRATAMIENTO",
        descripcion_tratamiento="<script>alert(1)</script>",
        proveedor_tratamiento="Proveedor <Industrial>",
        piezas_enviadas_tratamiento=1,
        proveedor_tratamiento_email="servicio@example.test",
        mediciones_dimensionales=[
            {
                "caracteristica": "Diámetro",
                "nominal": 25,
                "tolerancia_min": 24.98,
                "tolerancia_max": 25.02,
                "valor_medido": 25,
            }
        ],
        registros_fotograficos=["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/T2sAAAAASUVORK5CYII="],
    )

    informe = _generar_informe_tratamiento_html(solicitud)

    assert "<script>" not in informe
    assert "&lt;script&gt;" in informe
    assert "Proveedor &lt;Industrial&gt;" in informe


def test_informe_de_tratamiento_genera_pdf_descargable():
    solicitud = InspeccionCalidadCreate(
        codigo_op="4001001",
        codigo_plano="PLN-TEST-001",
        inspector_nombre="Inspector",
        resultado_inspeccion="APROBADO_TRATAMIENTO",
        descripcion_tratamiento="Alivio de esfuerzos",
        proveedor_tratamiento="Proveedor de prueba",
        proveedor_tratamiento_email="proveedor@example.test",
        piezas_enviadas_tratamiento=1,
        mediciones_dimensionales=[
            {
                "caracteristica": "Diámetro",
                "nominal": 25,
                "tolerancia_min": 24.98,
                "tolerancia_max": 25.02,
                "valor_medido": 25,
            }
        ],
    )

    documento = base64.b64decode(_generar_informe_tratamiento_pdf(solicitud))

    assert documento.startswith(b"%PDF-")
