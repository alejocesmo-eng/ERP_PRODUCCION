# app/api/v1/mantenimientos.py
from typing import List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, Field, validator

from app.db.database import get_db
from app.db.models import MantenimientoMaquina, MantenimientoPiezaDet, Plano, Proyecto

router = APIRouter()

# =============================================================================
# SCHEMAS PYDANTIC
# =============================================================================

class MantenimientoKitResponse(BaseModel):
    id_mantenimiento: int
    id_proyecto: Optional[Any] = None
    codigo_mantenimiento: str
    nombre_maquina: str
    cliente_nombre: str
    codigo_op: str
    fase_mantenimiento: str
    confirmado: bool = False
    piezas_terminadas_ok: int = 0
    total_piezas_autorizadas: int = 0
    porcentaje_kit_listo: float = 0.0
    marca_modelo: Optional[str] = None
    serie_maquina: Optional[str] = None
    observaciones_ingreso: Optional[str] = None
    piezas: List[dict] = Field(default_factory=list)

    class Config:
        from_attributes = True


class MantenimientoCreate(BaseModel):
    codigo_mantenimiento: str
    cliente_nombre: str
    codigo_op: str
    nombre_maquina: str
    marca_modelo: Optional[str] = None
    serie_maquina: Optional[str] = None
    observaciones_ingreso: Optional[str] = None
    fecha_compromiso: Optional[date] = None

    @validator('fecha_compromiso', pre=True)
    def parse_fechas_vacias(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.strptime(v[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
        return v

    @validator('marca_modelo', 'serie_maquina', 'observaciones_ingreso', pre=True)
    def parse_strings_vacios(cls, v):
        if v == "":
            return None
        return v


class MantenimientoUpdate(BaseModel):
    fase_mantenimiento: Optional[str] = None
    confirmado: Optional[bool] = None
    total_piezas_autorizadas: Optional[int] = None
    piezas_terminadas_ok: Optional[int] = None
    porcentaje_kit_listo: Optional[float] = None
    observaciones_ingreso: Optional[str] = None

    class Config:
        extra = "ignore"


class PiezaLevantamientoItem(BaseModel):
    codigo_pieza_plano: str
    descripcion_pieza: str
    cantidad_requerida: int = 1
    accion_requerida: str = "FABRICAR_NUEVA"
    material_especificado: Optional[str] = "AISI 1045"
    precio_unitario_cotizado: Optional[float] = 0.0
    autorizado_cliente: Optional[bool] = True


# =============================================================================
# ENDPOINTS API (MANTENIMIENTO & OVERHAUL)
# =============================================================================

@router.get("/monitor-kits")
def listar_monitor_kits(db: Session = Depends(get_db)):
    """
    Retorna el listado de proyectos de mantenimiento real desde PostgreSQL.
    """
    try:
        registros = db.query(MantenimientoMaquina).order_by(MantenimientoMaquina.id_mantenimiento.desc()).all()
        resultado = []
        for m in registros:
            resultado.append({
                "id_mantenimiento": m.id_mantenimiento,
                "id_proyecto": m.id_mantenimiento,
                "codigo_mantenimiento": m.codigo_mantenimiento,
                "cliente_nombre": m.cliente_nombre,
                "nombre_maquina": m.nombre_maquina,
                "codigo_op": m.codigo_op,
                "fase_mantenimiento": m.fase_mantenimiento or "LAVADO_DESARME",
                "confirmado": bool(getattr(m, "confirmado", False)),
                "total_piezas_autorizadas": m.total_piezas_autorizadas or 0,
                "piezas_terminadas_ok": m.piezas_terminadas_ok or 0,
                "porcentaje_kit_listo": float(m.porcentaje_kit_listo or 0.0),
                "marca_modelo": m.marca_modelo,
                "serie_maquina": m.serie_maquina,
                "observaciones_ingreso": m.observaciones_ingreso,
                "piezas": [
                    {
                        "codigo_pieza_plano": p.codigo_item,
                        "descripcion_pieza": p.descripcion_pieza,
                        "cantidad_requerida": p.cantidad,
                        "accion_requerida": p.accion_tecnica,
                        "estado_fabricacion": p.estado_pieza
                    } for p in (m.piezas_det or [])
                ]
            })
        return resultado
    except SQLAlchemyError:
        db.rollback()
        return []
    except Exception:
        return []


@router.get("/{id_mantenimiento}/piezas")
def obtener_piezas_mantenimiento(id_mantenimiento: int, db: Session = Depends(get_db)):
    """
    Retorna la lista granular de piezas de un proyecto de mantenimiento en vivo.
    """
    piezas = db.query(MantenimientoPiezaDet).filter(
        MantenimientoPiezaDet.id_mantenimiento == id_mantenimiento
    ).all()
    
    return [
        {
            "codigo_pieza_plano": p.codigo_item,
            "descripcion_pieza": p.descripcion_pieza,
            "cantidad_requerida": p.cantidad,
            "accion_requerida": p.accion_tecnica,
            "material_especificado": "AISI 1045",
            "autorizado_cliente": True
        } for p in piezas
    ]


@router.post("/{id_mantenimiento}/piezas/carga-masiva")
def agregar_piezas_levantamiento(
    id_mantenimiento: int, 
    piezas: List[PiezaLevantamientoItem], 
    db: Session = Depends(get_db)
):
    """
    Guarda las piezas del levantamiento técnico. Si el cliente ya confirmó (P5), bloquea con 403.
    """
    mant = db.query(MantenimientoMaquina).filter(MantenimientoMaquina.id_mantenimiento == id_mantenimiento).first()
    if not mant:
        raise HTTPException(status_code=404, detail="Proyecto de Mantenimiento no encontrado.")

    if mant.confirmado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="❌ Bloqueo Comercial (ISO 9001): La cotización ya fue confirmada por el cliente."
        )

    try:
        db.query(MantenimientoPiezaDet).filter(MantenimientoPiezaDet.id_mantenimiento == id_mantenimiento).delete()
        
        for p in piezas:
            nueva_p = MantenimientoPiezaDet(
                id_mantenimiento=id_mantenimiento,
                codigo_item=p.codigo_pieza_plano,
                descripcion_pieza=p.descripcion_pieza,
                cantidad=p.cantidad_requerida,
                accion_tecnica=p.accion_requerida
            )
            db.add(nueva_p)

        mant.total_piezas_autorizadas = len(piezas)
        db.commit()
        return {"mensaje": f"Se registraron {len(piezas)} piezas del levantamiento exitosamente."}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al guardar piezas del levantamiento: {str(e)}"
        )


@router.patch("/{id_mantenimiento}/confirmar-cotizacion")
def confirmar_cotizacion_mantenimiento(id_mantenimiento: int, db: Session = Depends(get_db)):
    """
    Aprobación del Cliente. Congela piezas y vincula/crea la OT.
    """
    mant = db.query(MantenimientoMaquina).filter(MantenimientoMaquina.id_mantenimiento == id_mantenimiento).first()
    if not mant:
        raise HTTPException(status_code=404, detail="Proyecto de Mantenimiento no encontrado.")

    try:
        mant.confirmado = True
        mant.fase_mantenimiento = "DIAGNOSTICO_DISENO"

        plano_ot = db.query(Plano).filter(Plano.id_mantenimiento == id_mantenimiento).first()
        if not plano_ot:
            proyecto = db.query(Proyecto).filter(Proyecto.numero_pedido == mant.codigo_mantenimiento).first()
            if not proyecto:
                proyecto = Proyecto(
                    numero_pedido=mant.codigo_mantenimiento,
                    codigo_proyecto=mant.codigo_mantenimiento,
                    cliente_nombre=mant.cliente_nombre,
                    detalle_producto=mant.nombre_maquina,
                    requisitos_cliente="Mantenimiento e Inspección Técnica SGI",
                    confirmado=True
                )
                db.add(proyecto)
                db.flush()

            nuevo_plano = Plano(
                id_proyecto=proyecto.id_proyecto,
                id_mantenimiento=mant.id_mantenimiento,
                codigo_op=mant.codigo_op,
                codigo_plano=f"PLN-{mant.codigo_mantenimiento}",
                unidad_planta="Mecanizados",
                estado_diseno="PLANIFICADA"
            )
            db.add(nuevo_plano)

        db.commit()
        return {"mensaje": f"Cotización {mant.codigo_mantenimiento} confirmada por el cliente."}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al confirmar cotización: {str(e)}"
        )


@router.post("/nuevo", status_code=status.HTTP_201_CREATED)
def crear_nuevo_mantenimiento(mant_in: MantenimientoCreate, db: Session = Depends(get_db)):
    """
    Registra el ingreso de una máquina a taller para mantenimiento/overhaul.
    """
    codigo_mant = mant_in.codigo_mantenimiento.strip()
    cliente = mant_in.cliente_nombre.strip()
    op = mant_in.codigo_op.strip()
    maquina = mant_in.nombre_maquina.strip()

    if not codigo_mant or not cliente or not maquina:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los campos Código de Mantenimiento, Cliente y Nombre de la Máquina son obligatorios."
        )

    existente = db.query(MantenimientoMaquina).filter(
        MantenimientoMaquina.codigo_mantenimiento == codigo_mant
    ).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El código de mantenimiento [{codigo_mant}] ya se encuentra registrado."
        )

    nuevo_mant = MantenimientoMaquina(
        codigo_mantenimiento=codigo_mant,
        cliente_nombre=cliente,
        codigo_op=op,
        nombre_maquina=maquina,
        marca_modelo=mant_in.marca_modelo.strip() if mant_in.marca_modelo else None,
        serie_maquina=mant_in.serie_maquina.strip() if mant_in.serie_maquina else None,
        observaciones_ingreso=mant_in.observaciones_ingreso.strip() if mant_in.observaciones_ingreso else None,
        fase_mantenimiento="LAVADO_DESARME",
        confirmado=False,
        total_piezas_autorizadas=0,
        piezas_terminadas_ok=0,
        porcentaje_kit_listo=0.0
    )

    try:
        db.add(nuevo_mant)
        db.commit()
        db.refresh(nuevo_mant)

        return {
            "id_mantenimiento": nuevo_mant.id_mantenimiento,
            "id_proyecto": nuevo_mant.id_mantenimiento,
            "codigo_mantenimiento": nuevo_mant.codigo_mantenimiento,
            "cliente_nombre": nuevo_mant.cliente_nombre,
            "nombre_maquina": nuevo_mant.nombre_maquina,
            "codigo_op": nuevo_mant.codigo_op,
            "fase_mantenimiento": nuevo_mant.fase_mantenimiento,
            "confirmado": nuevo_mant.confirmado,
            "total_piezas_autorizadas": nuevo_mant.total_piezas_autorizadas or 0,
            "piezas_terminadas_ok": nuevo_mant.piezas_terminadas_ok or 0,
            "porcentaje_kit_listo": float(nuevo_mant.porcentaje_kit_listo or 0.0),
            "marca_modelo": nuevo_mant.marca_modelo,
            "serie_maquina": nuevo_mant.serie_maquina,
            "observaciones_ingreso": nuevo_mant.observaciones_ingreso,
            "piezas": [],
            "mensaje": f"Mantenimiento [{nuevo_mant.codigo_mantenimiento}] guardado exitosamente."
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar mantenimiento en PostgreSQL: {str(e)}"
        )


@router.patch("/{id_mantenimiento}")
def actualizar_mantenimiento(
    id_mantenimiento: int,
    datos: MantenimientoUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza la fase o propiedades de un proyecto de mantenimiento.
    """
    mant = db.query(MantenimientoMaquina).filter(MantenimientoMaquina.id_mantenimiento == id_mantenimiento).first()
    if not mant:
        raise HTTPException(status_code=404, detail="Proyecto de Mantenimiento no encontrado.")

    try:
        if datos.fase_mantenimiento is not None:
            mant.fase_mantenimiento = datos.fase_mantenimiento
        if datos.confirmado is not None:
            mant.confirmado = datos.confirmado
        if datos.total_piezas_autorizadas is not None:
            mant.total_piezas_autorizadas = datos.total_piezas_autorizadas
        if datos.piezas_terminadas_ok is not None:
            mant.piezas_terminadas_ok = datos.piezas_terminadas_ok
        if datos.porcentaje_kit_listo is not None:
            mant.porcentaje_kit_listo = datos.porcentaje_kit_listo
        if datos.observaciones_ingreso is not None:
            mant.observaciones_ingreso = datos.observaciones_ingreso

        db.commit()
        db.refresh(mant)

        return {
            "status": "exito",
            "id_mantenimiento": mant.id_mantenimiento,
            "fase_mantenimiento": mant.fase_mantenimiento,
            "mensaje": f"Proyecto {mant.codigo_mantenimiento} actualizado exitosamente."
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al actualizar mantenimiento en base de datos: {str(e)}"
        )