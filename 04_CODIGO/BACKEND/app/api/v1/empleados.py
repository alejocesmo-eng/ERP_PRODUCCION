from fastapi import APIRouter, Depends, status, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List
from app.api.deps import requerir_roles

router = APIRouter()

class EmpleadoSchema(BaseModel):
    id_empleado: str
    nombre: str
    apellido: str
    email: EmailStr
    cargo: str
    area: str
    activo: bool = True

CATALOGO_EMPLEADOS = [
    {
        "id_empleado": "EMP-001",
        "nombre": "Carlos",
        "apellido": "Pérez",
        "email": "carlos.perez@hd.com",
        "cargo": "Operario de Torno CNC",
        "area": "Producción",
        "activo": True
    }
]

@router.get("/", response_model=List[EmpleadoSchema])
def listar_empleados():
    return CATALOGO_EMPLEADOS