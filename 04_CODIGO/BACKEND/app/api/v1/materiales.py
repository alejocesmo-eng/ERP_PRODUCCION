from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List
from app.api.deps import requerir_roles

router = APIRouter()

# Esquema Pydantic para validar los datos de entrada/salida
class MaterialSchema(BaseModel):
    codigo_material: str
    descripcion: str
    categoria: str
    unidad_medida: str
    stock_minimo: float
    stock_maximo: float

# Simulador de catálogo de materiales
CATALOGO_MATERIALES = [
    {
        "codigo_material": "MAT-ACERO-1045",
        "descripcion": "Barra de Acero AISI 1045 D=2 pulgadas",
        "categoria": "Materia Prima",
        "unidad_medida": "Metros",
        "stock_minimo": 5.0,
        "stock_maximo": 50.0
    },
    {
        "codigo_material": "INS-DNMG-150608",
        "descripcion": "Inserto para Torneado DNMG 150608 Aceros",
        "categoria": "Herramental",
        "unidad_medida": "Piezas",
        "stock_minimo": 10.0,
        "stock_maximo": 100.0
    }
]

@router.get("/", response_model=List[MaterialSchema])
def listar_materiales():
    """
    Consulta todo el catálogo maestro de materiales e insertos.
    Apto para cualquier rol del sistema.
    """
    return CATALOGO_MATERIALES

@router.post("/", response_model=MaterialSchema, status_code=status.HTTP_201_CREATED)
def crear_material(
    material: MaterialSchema,
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"]))
):
    """
    Agrega un nuevo material al catálogo maestro.
    Protegido por RBAC: Solo Administradores y Personal de Almacén.
    """
    CATALOGO_MATERIALES.append(material.model_dump())
    return material