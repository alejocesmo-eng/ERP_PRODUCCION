# tests/test_puesto_cnc.py
"""
Suite de Pruebas Automatizadas Asíncronas (pytest + httpx)
Validación de Puesto de Trabajo CNC, Cronómetro Dual y Manejo de Excepciones (ADR-001 / TC-PROD-001).
"""
import pytest
import httpx
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.orm import Session

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath("04_CODIGO/BACKEND"))

from app.main import app
from app.db.database import SessionLocal
from app.db.models import (
    Proyecto,
    Plano,
    OrdenProduccion,
    RegistroTiemposProduccion,
    EstadoOPEnum
)


@pytest.fixture(scope="function")
def db_session():
    """Provee una sesión limpia de base de datos para setup y verificación."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def op_test_liberada(db_session: Session):
    """
    Crea o asegura una Orden de Producción de prueba en estado LIBERADA_PRODUCCION.
    """
    consecutivo_op = f"OP-TEST-{uuid4().hex[:6].upper()}"
    
    # 1. Crear proyecto base
    proyecto = Proyecto(
        id_proyecto=uuid4(),
        numero_pedido=f"PED-{consecutivo_op}",
        codigo_proyecto=f"PRY-{consecutivo_op}",
        cliente_nombre="Cliente Metalmecánico Test S.A.",
        requisitos_cliente="Estándar ISO 9001:2026 - Tolerancia ±0.01mm",
        detalle_producto="Eje de Transmisión Especial CNC"
    )
    db_session.add(proyecto)
    db_session.flush()

    # 2. Crear plano técnico asociado
    plano = Plano(
        id_plano=uuid4(),
        id_proyecto=proyecto.id_proyecto,
        codigo_op=consecutivo_op,
        codigo_plano=f"PLN-{consecutivo_op}",
        revision="REV-01",
        unidad_planta="Mecanizados",
        dibujante_asignado="Ing. Carlos Ruiz",
        archivo_url=f"/static/planos/{consecutivo_op}.pdf",
        estado_diseno="LIBERADA"
    )
    db_session.add(plano)
    db_session.flush()

    # 3. Crear OP en estado LIBERADA_PRODUCCION con estándar de 20 min (1200s)
    op = OrdenProduccion(
        id_op=uuid4(),
        id_proyecto=proyecto.id_proyecto,
        id_plano=plano.id_plano,
        codigo_op=consecutivo_op,
        cantidad_fabricar=5,
        estado=EstadoOPEnum.LIBERADA_PRODUCCION,
        reserva_stock_100=True,
        tiempo_setup_estandar_minutos=20.0,
        observaciones="OP liberada para pruebas de Puesto CNC"
    )
    db_session.add(op)
    db_session.commit()
    db_session.refresh(op)

    return op


# =============================================================================
# CASO TC-01: INICIO DE SETUP Y SINCRONIZACIÓN DE ESTADO EN PUESTO CNC
# =============================================================================

@pytest.mark.asyncio
async def test_tc_01_iniciar_setup(op_test_liberada: OrdenProduccion, db_session: Session):
    """
    TC-01: OP en estado LIBERADA asignada a operario.
    1. Presionar 'Iniciar Setup' (POST /api/v1/produccion/setup/iniciar).
    2. Verificar que el estado pasa a 'EN_PROCESO_CNC'.
    3. Verificar que se registra el TIMESTAMP inicial en 'registro_tiempos_produccion'.
    Criterio de éxito: Código HTTP 200 y registro persistido en BD PostgreSQL.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "orden_id": str(op_test_liberada.id_op),
            "operario_id": "operario_cnc_01",
            "estacion_id": "CNC-01",
            "tiempo_estandar_minutos": 20.0
        }

        response = await ac.post("/api/v1/produccion/setup/iniciar", json=payload)
        assert response.status_code == 200, f"Error en respuesta: {response.text}"
        data = response.json()

        # Validaciones de respuesta
        assert data["status"] == "ok"
        assert data["estado_op"] == "EN_PROCESO_CNC"
        assert data["tipo_tiempo"] == "SETUP"
        assert "fecha_hora_inicio" in data

        # Verificación directa en PostgreSQL
        op_actualizada = db_session.query(OrdenProduccion).filter(
            OrdenProduccion.id_op == op_test_liberada.id_op
        ).first()
        assert op_actualizada.estado == EstadoOPEnum.EN_PROCESO_CNC

        registro_bd = db_session.query(RegistroTiemposProduccion).filter(
            RegistroTiemposProduccion.orden_produccion_id == op_test_liberada.id_op,
            RegistroTiemposProduccion.tipo_tiempo == "SETUP"
        ).first()
        assert registro_bd is not None
        assert registro_bd.estacion_id == "CNC-01"
        assert registro_bd.operario_id == "operario_cnc_01"
        assert registro_bd.fecha_hora_inicio is not None


# =============================================================================
# CASO TC-03: EXCEPCIÓN POR DESVIACIÓN DE SETUP (+50%) Y JUSTIFICACIÓN OBLIGATORIA
# =============================================================================

@pytest.mark.asyncio
async def test_tc_03_bloqueo_desviacion_setup_sin_justificacion(op_test_liberada: OrdenProduccion, db_session: Session):
    """
    TC-03: OP con tiempo de Setup estándar de 20 min (umbral 150% = 30 min / 1800 seg).
    Paso 1: Simular acumulación de >30 min (ej. 35 min = 2100 seg) en Setup.
    Paso 2: Intentar conmutar a 'Mecanizado' SIN justificación.
    Resultado esperado: HTTP 400 Bad Request solicitando el campo 'observacion_desviacion'.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Iniciar Setup primero
        await ac.post("/api/v1/produccion/setup/iniciar", json={
            "orden_id": str(op_test_liberada.id_op),
            "operario_id": "operario_cnc_01",
            "tiempo_estandar_minutos": 20.0
        })

        # 2. Intentar pasar a Mecanizado con 35 minutos de Setup (2100 segundos > 1800 segundos) SIN justificación
        payload_sin_justificacion = {
            "orden_id": str(op_test_liberada.id_op),
            "tiempo_setup_segundos": 2100,  # 35 minutos (desviación del 75%, excede el 50%)
            "tiempo_estandar_minutos": 20.0,
            "observacion_desviacion": None  # Omitido / nulo
        }

        response_error = await ac.post("/api/v1/produccion/mecanizado/iniciar", json=payload_sin_justificacion)
        assert response_error.status_code == 400
        error_detail = response_error.json()["detail"]
        assert "observacion_desviacion" in error_detail
        assert "supera el 50%" in error_detail or "excede" in error_detail

        # Verificar que la OP NO conmutó a Mecanizado de forma anómala
        reg_mecanizado = db_session.query(RegistroTiemposProduccion).filter(
            RegistroTiemposProduccion.orden_produccion_id == op_test_liberada.id_op,
            RegistroTiemposProduccion.tipo_tiempo == "MECANIZADO"
        ).first()
        assert reg_mecanizado is None, "No debió crearse registro de Mecanizado sin justificación"


@pytest.mark.asyncio
async def test_tc_03_aprobacion_desviacion_setup_con_justificacion(op_test_liberada: OrdenProduccion, db_session: Session):
    """
    TC-03 continuación: Conmutar a Mecanizado tras ingresar la justificación obligatoria.
    Resultado esperado: HTTP 200 OK, registro conmutado a 'MECANIZADO' y persistencia de observacion_desviacion.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Iniciar Setup
        await ac.post("/api/v1/produccion/setup/iniciar", json={
            "orden_id": str(op_test_liberada.id_op),
            "operario_id": "operario_cnc_01",
            "tiempo_estandar_minutos": 20.0
        })

        # Enviar conmutación con justificación explícita según ADR-001
        justificacion = "Ajuste/centrado complejo de pieza o herramental."
        payload_con_justificacion = {
            "orden_id": str(op_test_liberada.id_op),
            "tiempo_setup_segundos": 2100,
            "tiempo_estandar_minutos": 20.0,
            "observacion_desviacion": justificacion
        }

        response_ok = await ac.post("/api/v1/produccion/mecanizado/iniciar", json=payload_con_justificacion)
        assert response_ok.status_code == 200
        data_ok = response_ok.json()
        assert data_ok["status"] == "ok"
        assert data_ok["tipo_tiempo"] == "MECANIZADO"
        assert data_ok["desviacion_detectada"] is True
        assert data_ok["observacion_desviacion"] == justificacion

        # Verificar persistencia en base de datos
        reg_setup = db_session.query(RegistroTiemposProduccion).filter(
            RegistroTiemposProduccion.orden_produccion_id == op_test_liberada.id_op,
            RegistroTiemposProduccion.tipo_tiempo == "SETUP"
        ).first()
        assert reg_setup is not None
        assert reg_setup.segundos_ejecutados == 2100
        assert reg_setup.observacion_desviacion == justificacion

        reg_mecanizado = db_session.query(RegistroTiemposProduccion).filter(
            RegistroTiemposProduccion.orden_produccion_id == op_test_liberada.id_op,
            RegistroTiemposProduccion.tipo_tiempo == "MECANIZADO"
        ).first()
        assert reg_mecanizado is not None
        assert reg_mecanizado.fecha_hora_inicio is not None


# =============================================================================
# CASO TC-02: GENERACIÓN DE TOKEN SEGURO Y VISOR TEMPORAL DE PLANOS
# =============================================================================

@pytest.mark.asyncio
async def test_tc_02_servido_seguro_planos_token(op_test_liberada: OrdenProduccion, db_session: Session):
    """
    TC-02: Generación de token JWT temporal (TTL expirable) para ver el plano de la OP activa.
    Valida la generación del token y el acceso restringido al finalizar la orden.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Generar token para la OP activa
        resp_token = await ac.get(f"/api/v1/planos/token/{op_test_liberada.id_op}")
        assert resp_token.status_code == 200
        data_token = resp_token.json()
        assert "token" in data_token
        assert data_token["expires_in_minutes"] == 15
        token = data_token["token"]

        # 2. Acceder al visor con el token mientras la OP está activa
        resp_visor = await ac.get(f"/api/v1/planos/visor/{token}")
        assert resp_visor.status_code in [200, 307]

        # 3. Finalizar / Cerrar la OP
        op_test_liberada.estado = EstadoOPEnum.CERRADA
        db_session.commit()

        # 4. Intentar acceder al plano una vez finalizada la OP (debe retornar 403 Forbidden)
        resp_bloqueado = await ac.get(f"/api/v1/planos/visor/{token}")
        assert resp_bloqueado.status_code == 403
        assert "finalizó" in resp_bloqueado.json()["detail"] or "bloqueado" in resp_bloqueado.json()["detail"]


# =============================================================================
# PRUEBA ADICIONAL: PAUSAR TURNO CON PRESERVACIÓN DE SEGUNDOS
# =============================================================================

@pytest.mark.asyncio
async def test_pausar_turno_cronometro(op_test_liberada: OrdenProduccion, db_session: Session):
    """
    Verifica que la pausa por cambio de turno guarda los segundos y marca pausado_por_turno = True.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Iniciar Setup
        await ac.post("/api/v1/produccion/setup/iniciar", json={
            "orden_id": str(op_test_liberada.id_op),
            "operario_id": "operario_cnc_01"
        })

        # Pausar turno
        resp_pausa = await ac.post("/api/v1/produccion/pausar-turno", json={
            "orden_id": str(op_test_liberada.id_op),
            "segundos_adicionales": 300,
            "motivo": "Cambio de turno vespertino"
        })
        assert resp_pausa.status_code == 200
        data_pausa = resp_pausa.json()
        assert data_pausa["status"] == "ok"
        assert data_pausa["pausado_por_turno"] is True
        assert data_pausa["segundos_conservados"] >= 300
