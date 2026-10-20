# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import (
    auth,
    proyectos,
    planos,
    produccion,
    mantenimientos,
    almacen,
    inventario,
    materiales,
    ordenes,
    calidad,
    indicadores,
    trazabilidad,
    solicitudes_compra
)

app = FastAPI(
    title="SGI ERP Empresarial - API Backend ISO 9001:2026",
    description="Sistema de Gestión Integral con Manufactura, Control MES e Inventarios",
    version="1.0.0"
)

# Configuración de CORS para permitir solicitudes del Frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Carpeta de archivos estáticos (planos PDF)
if not os.path.exists("static/planos"):
    os.makedirs("static/planos", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# =============================================================================
# REGISTRO CENTRALIZADO DE ROUTERS (API V1)
# =============================================================================
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Autenticación"])
app.include_router(proyectos.router, prefix="/api/v1/proyectos", tags=["Ventas / Pedidos"])
app.include_router(planos.router, prefix="/api/v1/planos", tags=["Diseño e Ingeniería"])
app.include_router(ordenes.router, prefix="/api/v1/ordenes", tags=["Órdenes de Producción"])
app.include_router(produccion.router, prefix="/api/v1/operaciones", tags=["Producción MES"])
app.include_router(mantenimientos.router, prefix="/api/v1/mantenimientos", tags=["Mantenimientos & Overhaul"])
app.include_router(almacen.router, prefix="/api/v1/almacen", tags=["Almacén"])
app.include_router(inventario.router, prefix="/api/v1/inventario", tags=["Inventario y Kárdex"])
app.include_router(materiales.router, prefix="/api/v1/materiales", tags=["Materiales"])
app.include_router(solicitudes_compra.router, prefix="/api/v1/solicitudes-compra", tags=["Compras / BOM"])
app.include_router(calidad.router, prefix="/api/v1/calidad", tags=["Calidad y RNC"])
app.include_router(indicadores.router, prefix="/api/v1/indicadores", tags=["Indicadores / KPIs"])
app.include_router(trazabilidad.router, prefix="/api/v1/trazabilidad", tags=["Trazabilidad"])


@app.get("/")
def read_root():
    return {
        "sistema": "SGI ERP Empresarial",
        "estado": "Operativo",
        "version": "1.0.0",
        "documentacion": "/docs"
    }