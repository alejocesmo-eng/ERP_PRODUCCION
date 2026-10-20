from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal

from app.db.database import get_db
from app.db.models import ArticuloInventario, EntradaMercancia, AjusteInventario, Usuario
from app.api.deps import obtener_usuario_actual, requerir_roles

router = APIRouter()

# --- SCHEMAS ---
class ArticuloCreate(BaseModel):
    codigo_sku: str
    nombre: str
    descripcion: str | None = None
    unidad_medida: str = "UND"
    tipo_inventario: str = "GENERAL"
    stock_minimo: Decimal = Decimal('0.00')

class EntradaCreate(BaseModel):
    id_articulo: UUID
    numero_lote: str
    cantidad_recibida: Decimal
    proveedor: str | None = None

# --- ENDPOINTS SUBMÓDULO 1: DATOS MAESTROS ---
@router.post("/articulos", status_code=status.HTTP_201_CREATED)
def registrar_articulo(
    articulo_in: ArticuloCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requerir_roles(["ADMIN", "ALMACEN"]))
):
    """1. Datos Maestros: Registrar nuevo artículo en el catálogo."""
    if db.query(ArticuloInventario).filter(ArticuloInventario.codigo_sku == articulo_in.codigo_sku).first():
        raise HTTPException(status_code=400, detail="El SKU ya existe en el sistema.")
    
    nuevo_articulo = ArticuloInventario(**articulo_in.model_dump())
    db.add(nuevo_articulo)
    db.commit()
    db.refresh(nuevo_articulo)
    return nuevo_articulo

# --- ENDPOINTS SUBMÓDULO 2: ENTRADA DE MERCANCÍA ---
@router.post("/entradas", status_code=status.HTTP_201_CREATED)
def registrar_entrada(
    entrada_in: EntradaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requerir_roles(["ADMIN", "ALMACEN", "CALIDAD"]))
):
    """2. Entrada de Mercancía: Incrementa stock y registra lote de trazabilidad."""
    articulo = db.query(ArticuloInventario).filter(ArticuloInventario.id_articulo == entrada_in.id_articulo).first()
    if not articulo:
        raise HTTPException(status_code=404, detail="Artículo no encontrado.")
    
    # Registrar entrada
    nueva_entrada = EntradaMercancia(
        **entrada_in.model_dump(),
        recibido_por=usuario.id_usuario
    )
    # Actualizar stock maestro
    articulo.stock_actual += entrada_in.cantidad_recibida
    
    db.add(nueva_entrada)
    db.commit()
    return {"message": "Entrada registrada y stock actualizado con éxito."}

# --- ENDPOINTS SUBMÓDULO 3: GESTIÓN DE INVENTARIOS ---
@router.get("/resumen")
def listar_inventario(
    tipo: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obtener_usuario_actual)
):
    """3. Gestión de Inventarios: Consultar stocks filtrados por tipo de inventario."""
    query = db.query(ArticuloInventario)
    if tipo:
        query = query.filter(ArticuloInventario.tipo_inventario == tipo)
    return query.all()