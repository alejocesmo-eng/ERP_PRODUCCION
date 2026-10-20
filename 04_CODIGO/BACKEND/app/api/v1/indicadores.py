from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Dict, Any

from app.db.database import get_db
from app.db.models import Proyecto, Plano, OrdenProduccion, NoConformidad
from app.api.deps import obtener_usuario_actual

router = APIRouter()

# --- SCHEMAS (PYDANTIC) ---
class IndicadorKPI(BaseModel):
    codigo_kpi: str
    nombre: str
    proceso: str
    valor_actual: float
    meta: float
    unidad: str
    estado_semaforo: str  # VERDE | AMARILLO | ROJO
    formula: str

class DashboardKPIsResponse(BaseModel):
    resumen_general: Dict[str, Any]
    kpis: List[IndicadorKPI]

# --- ENDPOINT ---
@router.get("/", response_model=DashboardKPIsResponse, status_code=status.HTTP_200_OK)
def obtener_indicadores_sgi(
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual)
):
    """
    Calcula dinámicamente los KPIs de la Matriz de Indicadores (07_MATRIZ_DE_INDICADORES.md)
    consultando las tablas inmutables de PostgreSQL.
    """
    # 1. KPI-VEN-01: On-Time Delivery / Cumplimiento de Proyectos
    total_proyectos = db.query(func.count(Proyecto.id_proyecto)).scalar() or 1
    proyectos_confirmados = db.query(func.count(Proyecto.id_proyecto)).filter(Proyecto.confirmado == True).scalar() or 0
    kpi_ventas_val = round((proyectos_confirmados / total_proyectos) * 100, 1)

    # 2. KPI-DSN-01: Eficiencia en Paquete Técnico (Planos Aprobados)
    total_planos = db.query(func.count(Plano.id_plano)).scalar() or 1
    planos_aprobados = db.query(func.count(Plano.id_plano)).filter(Plano.estado == "APROBADO").scalar() or 0
    kpi_diseno_val = round((planos_aprobados / total_planos) * 100, 1)

    # 3. KPI-OP-01: Eficacia de Liberación con Stock 100% (RN-OP-004)
    total_ops = db.query(func.count(OrdenProduccion.id_op)).scalar() or 1
    ops_stock_100 = db.query(func.count(OrdenProduccion.id_op)).filter(OrdenProduccion.stock_disponible_100 == True).scalar() or 0
    kpi_op_val = round((ops_stock_100 / total_ops) * 100, 1)

    # 4. KPI-NC-01: Control de No Conformidades Cerradas (CAPA)
    total_ncs = db.query(func.count(NoConformidad.id_nc)).scalar() or 1
    ncs_cerradas = db.query(func.count(NoConformidad.id_nc)).filter(NoConformidad.estado == "CERRADA").scalar() or 0
    kpi_nc_val = round((ncs_cerradas / total_ncs) * 100, 1) if total_ncs > 0 else 100.0

    # Construcción de Semáforos
    kpis_calculados = [
        IndicadorKPI(
            codigo_kpi="KPI-VEN-01",
            nombre="Cumplimiento de Entregas (OTD)",
            proceso="PM-01 Ventas",
            valor_actual=kpi_ventas_val,
            meta=95.0,
            unidad="%",
            estado_semaforo="VERDE" if kpi_ventas_val >= 95.0 else ("AMARILLO" if kpi_ventas_val >= 85.0 else "ROJO"),
            formula="(Proyectos Confirmados / Total Proyectos) * 100"
        ),
        IndicadorKPI(
            codigo_kpi="KPI-DSN-01",
            nombre="Eficiencia en Paquete Técnico",
            proceso="PM-02 Diseño",
            valor_actual=kpi_diseno_val,
            meta=90.0,
            unidad="%",
            estado_semaforo="VERDE" if kpi_diseno_val >= 90.0 else ("AMARILLO" if kpi_diseno_val >= 75.0 else "ROJO"),
            formula="(Planos Aprobados / Total Planos) * 100"
        ),
        IndicadorKPI(
            codigo_kpi="KPI-OP-01",
            nombre="Eficacia de Liberación OP (RN-OP-004)",
            proceso="PM-03 Calidad",
            valor_actual=kpi_op_val,
            meta=100.0,
            unidad="%",
            estado_semaforo="VERDE" if kpi_op_val == 100.0 else "ROJO",
            formula="(OPs con Stock 100% / Total OPs) * 100"
        ),
        IndicadorKPI(
            codigo_kpi="KPI-NC-01",
            nombre="Cierre Efectivo de No Conformidades",
            proceso="PC-03 Calidad",
            valor_actual=kpi_nc_val,
            meta=90.0,
            unidad="%",
            estado_semaforo="VERDE" if kpi_nc_val >= 90.0 else "AMARILLO",
            formula="(RNCs Cerradas / Total RNCs) * 100"
        )
    ]

    return {
        "resumen_general": {
            "total_proyectos": total_proyectos,
            "total_planos": total_planos,
            "total_ordenes_produccion": total_ops,
            "total_no_conformidades": total_ncs
        },
        "kpis": kpis_calculados
    }