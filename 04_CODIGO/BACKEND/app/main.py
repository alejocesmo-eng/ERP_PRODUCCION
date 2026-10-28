# app/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.v1.endpoints import empresa
from app.api.v1 import (
    auth,
    maestros,
    costos,
    proyectos,
    planos,
    produccion,
    mantenimientos,
    mantenimiento_planta,
    carga_maquinas,
    almacen,
    inventario,
    materiales,
    ordenes,
    calidad,
    indicadores,
    trazabilidad,
    solicitudes_compra,
    diseno,
    ventas,
    cotizaciones
)
from app.api.v1.endpoints.produccion import cola_router as cola_operaciones_router
from app.api.v1.historial import router as historial_router

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
app.include_router(maestros.router, prefix="/api/v1/maestros", tags=["Datos Maestros"])
app.include_router(proyectos.router, prefix="/api/v1/proyectos", tags=["Ventas / Pedidos"])
app.include_router(planos.router, prefix="/api/v1/planos", tags=["Diseño e Ingeniería"])
app.include_router(ordenes.router, prefix="/api/v1/ordenes", tags=["Órdenes de Producción"])
app.include_router(costos.router, prefix="/api/v1/costos", tags=["Costos reales"])
app.include_router(produccion.router, prefix="/api/v1/operaciones", tags=["Producción MES"])
app.include_router(cola_operaciones_router, prefix="/api/v1/operaciones", tags=["Cola de planta y sublotes"])
app.include_router(mantenimientos.router, prefix="/api/v1/mantenimientos", tags=["Mantenimientos & Overhaul"])
app.include_router(mantenimiento_planta.router, prefix="/api/v1/mantenimientos", tags=["Mantenimiento de planta"])
app.include_router(carga_maquinas.router, prefix="/api/v1/produccion", tags=["Planificación de capacidad"])
app.include_router(almacen.router, prefix="/api/v1/almacen", tags=["Almacén"])
app.include_router(inventario.router, prefix="/api/v1/inventario", tags=["Inventario y Kárdex"])
app.include_router(materiales.router, prefix="/api/v1/materiales", tags=["Materiales"])
app.include_router(solicitudes_compra.router, prefix="/api/v1/solicitudes-compra", tags=["Compras / BOM"])
app.include_router(calidad.router, prefix="/api/v1/calidad", tags=["Calidad y RNC"])
app.include_router(indicadores.router, prefix="/api/v1/indicadores", tags=["Indicadores / KPIs"])
app.include_router(trazabilidad.router, prefix="/api/v1/trazabilidad", tags=["Trazabilidad"])
app.include_router(diseno.router, prefix="/api/v1/diseno", tags=["Diseño MES"])
# app.include_router(ventas.router, prefix="/api/v1/ventas", tags=["Ventas / Cotizaciones"])
app.include_router(empresa.router, prefix="/api/v1/configuracion/empresa", tags=["Configuración Empresa"])
app.include_router(historial_router, prefix="/api/v1")
app.include_router(cotizaciones.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {
        "sistema": "SGI ERP Empresarial",
        "estado": "Operativo",
        "version": "1.0.0",
        "documentacion": "/docs"
    }