# tests/test_piezas_aprobadas.py
"""
Reglas de la cantidad aprobada por Calidad (app/services/piezas_aprobadas.validar_aprobacion), las
mismas que el CHECK ck_inspecciones_tipo_aprobacion de la migración 35:
- APROBADO_DESPACHO: con tipo INDIVIDUAL o LOTE, al menos una pieza, e INDIVIDUAL exactamente una.
- Tratamiento o rechazo: sin piezas ni tipo.
"""
import pytest
from fastapi import HTTPException

from app.services.piezas_aprobadas import validar_aprobacion


@pytest.mark.parametrize("resultado, cantidad, tipo", [
    ("APROBADO_DESPACHO", 1, "INDIVIDUAL"),
    ("APROBADO_DESPACHO", 5, "LOTE"),
    ("APROBADO_DESPACHO", 1, "LOTE"),
    ("RECHAZADO", 0, None),
    ("APROBADO_TRATAMIENTO", 0, None),
])
def test_aprobaciones_validas(resultado, cantidad, tipo):
    validar_aprobacion(resultado, cantidad, tipo)


@pytest.mark.parametrize("resultado, cantidad, tipo, mensaje", [
    ("APROBADO_DESPACHO", 3, None, "INDIVIDUAL"),          # despacho sin tipo
    ("APROBADO_DESPACHO", 0, "LOTE", "cuántas piezas"),     # despacho con menos de una pieza
    ("APROBADO_DESPACHO", 0, None, "INDIVIDUAL"),
    ("APROBADO_DESPACHO", 2, "INDIVIDUAL", "una sola pieza"),
    ("APROBADO_DESPACHO", 2, "OTRO", "INDIVIDUAL"),
    ("RECHAZADO", 1, "LOTE", "Solo la aprobación para despacho"),
    ("APROBADO_TRATAMIENTO", 0, "LOTE", "Solo la aprobación para despacho"),
])
def test_aprobaciones_no_validas(resultado, cantidad, tipo, mensaje):
    with pytest.raises(HTTPException) as error:
        validar_aprobacion(resultado, cantidad, tipo)
    assert error.value.status_code == 422 and mensaje in error.value.detail
