import pytest
from pydantic import ValidationError

from app.api.v1.costos import (
    _anexar_presupuesto,
    _crear_indice_presupuestos,
)
from app.api.v1.proyectos import PresupuestoComponente, validar_referencias_presupuestales


class ProyectoPresupuestado:
    presupuestos_componentes = [
        {
            "categoria": "MATERIA_PRIMA",
            "referencia": "MP-A105-014",
            "monto_presupuestado": 30000,
        },
        {
            "categoria": "HORAS_MES",
            "referencia": "CC-100-MECANIZADO|SETUP",
            "monto_presupuestado": 25000,
        },
    ]


def test_compara_costos_reales_con_presupuesto_por_referencia():
    indice = _crear_indice_presupuestos(ProyectoPresupuestado())
    material = {"codigo_material": "MP-A105-014", "costo_total": 32000}
    tiempo = {"centro_trabajo": "CC-100-MECANIZADO", "tipo": "SETUP", "costo_total": 24000}

    _anexar_presupuesto(
        material, indice, "MATERIA_PRIMA", "MP-A105-014", material["costo_total"]
    )
    _anexar_presupuesto(
        tiempo,
        indice,
        "HORAS_MES",
        "CC-100-MECANIZADO|SETUP",
        tiempo["costo_total"],
    )

    assert material["presupuesto"] == 30000
    assert material["variacion_presupuestal"] == 2000
    assert material["desviacion_presupuestal"] is True
    assert tiempo["variacion_presupuestal"] == -1000
    assert tiempo["desviacion_presupuestal"] is False


def test_presupuestos_permiten_categoria_y_referencia_normalizadas():
    presupuesto = PresupuestoComponente(
        categoria=" horas_mes ",
        referencia=" CC-100-MECANIZADO|SETUP ",
        monto_presupuestado=25000,
    )

    assert presupuesto.categoria == "HORAS_MES"
    assert presupuesto.referencia == "CC-100-MECANIZADO|SETUP"


def test_rechaza_referencias_presupuestales_duplicadas():
    presupuestos = [
        PresupuestoComponente(
            categoria="MATERIA_PRIMA",
            referencia="MP-A105-014",
            monto_presupuestado=30000,
        ),
        PresupuestoComponente(
            categoria="materia_prima",
            referencia="mp-a105-014",
            monto_presupuestado=35000,
        ),
    ]

    with pytest.raises(ValueError, match="duplicadas"):
        validar_referencias_presupuestales(presupuestos)


def test_rechaza_categoria_de_presupuesto_no_admitida():
    with pytest.raises(ValidationError, match="categoría"):
        PresupuestoComponente(
            categoria="COSTO_GENERAL",
            referencia="PRUEBA",
            monto_presupuestado=100,
        )
