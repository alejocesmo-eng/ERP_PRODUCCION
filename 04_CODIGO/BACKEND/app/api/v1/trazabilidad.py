from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from app.api.deps import requerir_roles

router = APIRouter()

# --- ESQUEMAS PYDANTIC ---

class ArbolTrazabilidadSchema(BaseModel):
    id_proyecto: str
    cliente: str
    nombre_proyecto: str
    orden_produccion: dict
    documentacion_tecnica: dict
    material_y_retal: dict
    planta_y_maquinado: dict
    dictamen_metrologia: dict

# --- BASE DE DATOS SIMULADA PARA TRAZABILIDAD (MVP) ---

BASE_TRAZABILIDAD = {
    "PROY-2026-001": {
        "id_proyecto": "PROY-2026-001",
        "cliente": "Industrias Metalmecánicas S.A.",
        "nombre_proyecto": "Eje de Transmisión Especial 3in",
        "orden_produccion": {
            "id_op": "OP-2026-0001",
            "estado_actual": "PRODUCCION_TERMINADA",
            "cantidad_requerida": 10,
            "generada_por": "calidad@hd.com",
            "fecha_generacion": "2026-09-28T10:00:00"
        },
        "documentacion_tecnica": {
            "id_plano": "PL-0357-A",
            "revision_activa": "REV-02",
            "disenador": "diseno@hd.com",
            "aprobado_calidad": True
        },
        "material_y_retal": {
            "material_base": "AISI 4140 D=3in",
            "lote_entrada": "LOT-2026-089",
            "id_retal_utilizado": "RET-2026-0001",
            "despachado_por": "almacen@hd.com"
        },
        "planta_y_maquinado": {
            "maquina_asignada": "Torno CNC 0357",
            "herramental_utilizado": "0357-01",
            "operario": "carlos.perez@hd.com",
            "piezas_conformes": 10,
            "piezas_mermas": 0
        },
        "dictamen_metrologia": {
            "inspector": "ana.gomez@hd.com",
            "dictamen_final": "APROBADO",
            "piezas_inspeccionadas": 10,
            "instrumento_utilizado": "CALIPER-001",
            "fecha_inspeccion": "2026-09-29T09:30:00"
        }
    }
}

# --- ENDPOINTS REST ---

@router.get("/proyecto/{id_proyecto}", response_model=ArbolTrazabilidadSchema)
def consultar_trazabilidad_proyecto(
    id_proyecto: str,
    usuario: dict = Depends(requerir_roles(["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"]))
):
    """
    Búsqueda genealógica completa por ID de Proyecto.
    Permite reconstruir toda la historia operativa, desde la solicitud del cliente hasta el dictamen de Metrología.
    """
    if id_proyecto not in BASE_TRAZABILIDAD:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró historial de trazabilidad para el proyecto '{id_proyecto}'."
        )
    
    return BASE_TRAZABILIDAD[id_proyecto]

@router.get("/buscar", response_model=List[dict])
def busqueda_multicriterio(
    criterio: str,
    usuario: dict = Depends(requerir_roles(["ADMIN", "VENTAS", "DISENO", "ALMACEN", "PRODUCCION", "CALIDAD"]))
):
    """
    Motor de búsqueda rápida multicriterio por código de plano, número de retal (RET-XXXXXX), lote de material o número de OP.
    """
    resultados = []
    criterio_lower = criterio.lower()
    
    for key, item in BASE_TRAZABILIDAD.items():
        if (criterio_lower in item["id_proyecto"].lower() or
            criterio_lower in item["orden_produccion"]["id_op"].lower() or
            criterio_lower in item["documentacion_tecnica"]["id_plano"].lower() or
            criterio_lower in item["material_y_retal"]["id_retal_utilizado"].lower()):
            resultados.append(item)
            
    return resultados