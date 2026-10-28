from pydantic import BaseModel, ConfigDict
from typing import Optional

class EmpresaEmisoraBase(BaseModel):
    codigo_empresa: str = "HD-01"
    razon_social: str = "HD Precision & Technology S.A.S"
    nit: str = "901.456.789-0"
    actividad_principal: Optional[str] = "Mecanizado de Precisión · Fabricación & Overhaul Industrial"
    direccion: Optional[str] = "Zona Industrial"
    ciudad: Optional[str] = "Funza / Medellín, Colombia"
    telefono: Optional[str] = "(004) 300 0000"
    email: Optional[str] = "ventas@hdprecision.com"
    sitio_web: Optional[str] = "www.hdprecision.com"
    terminos_garantia: Optional[str] = None

class EmpresaEmisoraUpdate(BaseModel):
    codigo_empresa: Optional[str] = None
    razon_social: Optional[str] = None
    nit: Optional[str] = None
    actividad_principal: Optional[str] = None
    direccion: Optional[str] = None
    ciudad: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    sitio_web: Optional[str] = None
    terminos_garantia: Optional[str] = None

class EmpresaEmisoraResponse(EmpresaEmisoraBase):
    id: int
    model_config = ConfigDict(from_attributes=True)