from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import EmpresaEmisora
from app.schemas.empresa_schema import EmpresaEmisoraResponse, EmpresaEmisoraUpdate

router = APIRouter()

@router.get("/", response_model=EmpresaEmisoraResponse, summary="Obtener datos de la empresa emisora")
def obtener_empresa_emisora(db: Session = Depends(get_db)):
    empresa = db.query(EmpresaEmisora).first()
    if not empresa:
        empresa = EmpresaEmisora(
            codigo_empresa="HD-01",
            razon_social="HD Precision & Technology S.A.S",
            nit="901.456.789-0",
            actividad_principal="Mecanizado de Precisión · Fabricación & Overhaul Industrial",
            direccion="Zona Industrial",
            ciudad="Funza / Medellín, Colombia",
            telefono="(004) 300 0000",
            email="ventas@hdprecision.com",
            sitio_web="www.hdprecision.com"
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
    return empresa

@router.put("/", response_model=EmpresaEmisoraResponse, summary="Actualizar datos de la empresa emisora")
def actualizar_empresa_emisora(datos: EmpresaEmisoraUpdate, db: Session = Depends(get_db)):
    empresa = db.query(EmpresaEmisora).first()
    if not empresa:
        empresa = EmpresaEmisora()
        db.add(empresa)
    
    campos = datos.model_dump(exclude_unset=True)
    for clave, valor in campos.items():
        setattr(empresa, clave, valor)
        
    db.commit()
    db.refresh(empresa)
    return empresa