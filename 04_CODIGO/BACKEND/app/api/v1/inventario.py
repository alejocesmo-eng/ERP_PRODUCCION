from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual, requerir_roles
from app.db.database import get_db
from app.db.models import (
    ArticuloInventario,
    BOMListaMateriales,
    CategoriaInventario,
    CentroAlmacen,
    CatalogoMaterialSAP,
    ClaseMovimientoSAP,
    LoteMaterial,
    MetodoValoracionSAP,
    MovimientoKardexSAP,
    MovimientoInventario,
    Plano,
    RequisicionMRP,
    RegistroCalidadLote,
    SolicitudCompra,
    TipoMaterialSAP,
    TrazabilidadRequisicionMRP,
)
from app.services.inventario_sap import crear_documento_material_sap

router = APIRouter()


class CategoriaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=100)
    icono: Optional[str] = Field(default="📦", max_length=10)
    descripcion: Optional[str] = None


class ArticuloCreate(BaseModel):
    codigo_sku: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: Optional[str] = None
    categoria: str = Field(min_length=1, max_length=50)
    tipo_material_sap: TipoMaterialSAP = TipoMaterialSAP.ROH
    unidad_medida: str = Field(default="UND", max_length=20)
    clase_valoracion: Optional[str] = Field(default=None, min_length=1, max_length=50)
    cuenta_contable_activo: Optional[str] = Field(default=None, min_length=1, max_length=100)
    cuenta_contable_gasto: Optional[str] = Field(default=None, min_length=1, max_length=100)
    cuenta_contable_transitoria: str = Field(
        default="220505 - Recepción de facturas por conciliar",
        min_length=1,
        max_length=100,
    )
    centro_costo_defecto: str = Field(default="CC-100-PLANTA", min_length=1, max_length=50)
    metodo_valoracion: MetodoValoracionSAP = MetodoValoracionSAP.CPP
    precio_unitario_valorado: Decimal = Field(default=Decimal("0"), ge=0)
    stock_minimo: Decimal = Field(default=Decimal("0"), ge=0)
    stock_seguridad: Decimal = Field(default=Decimal("0"), ge=0)
    punto_reorden: Decimal = Field(default=Decimal("0"), ge=0)
    codigo_centro: str = Field(default="CENTRO-01-FUNZA", min_length=1, max_length=50)
    almacen_fisico: str = Field(default="BOD-MP-01", min_length=1, max_length=50)
    ubicacion: Optional[str] = Field(default=None, max_length=100)


class CentroAlmacenCreate(BaseModel):
    codigo_centro: str = Field(min_length=1, max_length=50)
    nombre_centro: str = Field(min_length=1, max_length=150)
    almacenes: list[str] = Field(min_length=1)


class CalidadLoteUpdate(BaseModel):
    estado_calidad: str = Field(pattern="^(CUARENTENA|LIBERADO|RECHAZADO)$")
    motivo: str = Field(min_length=3, max_length=1000)


def _stock_por_lote(db: Session, codigos: list[str]) -> dict[str, dict[str, float]]:
    resultado: dict[str, dict[str, float]] = {}
    if not codigos:
        return resultado

    lotes = db.query(LoteMaterial).filter(LoteMaterial.codigo_material.in_(codigos)).all()
    for lote in lotes:
        totales = resultado.setdefault(
            lote.codigo_material,
            {
                "LIBERADO": 0.0,
                "CUARENTENA": 0.0,
                "RECHAZADO": 0.0,
                "valor": 0.0,
                "reservado": 0.0,
            },
        )
        estado = lote.estado_calidad or (
            "LIBERADO" if lote.inspeccionado_calidad else "CUARENTENA"
        )
        cantidad = max(float(lote.stock_disponible or 0), 0.0)
        totales[estado] = totales.get(estado, 0.0) + cantidad
        totales["reservado"] += max(float(lote.stock_reservado or 0), 0.0)
        totales["valor"] += cantidad * float(lote.costo_unitario or 0)
    return resultado


def _articulo_response(articulo: ArticuloInventario, lotes: dict[str, dict[str, float]]) -> dict:
    cantidades = lotes.get(articulo.codigo_sku, {})
    catalogo = getattr(articulo, "catalogo_sap", None)
    stock_liberado = min(
        cantidades.get("LIBERADO", 0.0),
        max(float(articulo.stock_actual or 0), 0.0),
    )
    stock_reservado = max(
        float(articulo.stock_reservado or 0),
        cantidades.get("reservado", 0.0),
    )
    if catalogo and catalogo.metodo_valoracion == MetodoValoracionSAP.PRECIO_ESTANDAR:
        valor_inventario = max(float(articulo.stock_actual or 0), 0.0) * float(
            catalogo.precio_unitario_valorado or 0
        )
    else:
        valor_inventario = cantidades.get("valor", 0.0)
    return {
        "id_articulo": articulo.id_articulo,
        "codigo_sku": articulo.codigo_sku,
        "nombre": articulo.nombre,
        "descripcion": articulo.descripcion,
        "categoria": articulo.categoria,
        "tipo_inventario": articulo.tipo_inventario,
        "tipo_material_sap": catalogo.tipo_material_sap.value if catalogo else "ROH",
        "unidad_medida": articulo.unidad_medida,
        "stock_actual": float(articulo.stock_actual or 0),
        "stock_liberado": stock_liberado,
        "stock_cuarentena": cantidades.get("CUARENTENA", 0.0),
        "stock_rechazado": cantidades.get("RECHAZADO", 0.0),
        "stock_reservado": stock_reservado,
        "stock_disponible": max(stock_liberado - stock_reservado, 0.0),
        "costo_unitario": float(articulo.costo_unitario or 0),
        "precio_unitario_valorado": float(
            catalogo.precio_unitario_valorado if catalogo else articulo.costo_unitario or 0
        ),
        "valor_inventario": valor_inventario,
        "metodo_valoracion": catalogo.metodo_valoracion.value if catalogo else (
            "FIFO" if articulo.metodo_valoracion == "FIFO" else "CPP"
        ),
        "stock_minimo": float(articulo.stock_minimo or 0),
        "stock_seguridad": float(catalogo.stock_seguridad or 0) if catalogo else 0,
        "punto_reorden": float(catalogo.punto_reorden or articulo.stock_minimo or 0) if catalogo else float(articulo.stock_minimo or 0),
        "clase_valoracion": catalogo.clase_valoracion if catalogo else None,
        "cuenta_contable_activo": catalogo.cuenta_contable_activo if catalogo else None,
        "cuenta_contable_gasto": catalogo.cuenta_contable_gasto if catalogo else None,
        "cuenta_contable_transitoria": catalogo.cuenta_contable_transitoria if catalogo else None,
        "centro_costo_defecto": catalogo.centro_costo_defecto if catalogo else None,
        "codigo_centro": catalogo.codigo_centro if catalogo else None,
        "almacen_fisico": catalogo.almacen_fisico if catalogo else articulo.ubicacion,
        "ubicacion": articulo.ubicacion,
        "creado_en": articulo.creado_en,
    }


def _catalogo_data(catalogo: CatalogoMaterialSAP) -> dict:
    return {
        "id_material": catalogo.id_material,
        "id_articulo": catalogo.id_articulo,
        "sku_codigo": catalogo.sku_codigo,
        "descripcion_tecnica": catalogo.descripcion_tecnica,
        "tipo_material_sap": catalogo.tipo_material_sap.value,
        "unidad_medida": catalogo.unidad_medida,
        "clase_valoracion": catalogo.clase_valoracion,
        "cuenta_contable_activo": catalogo.cuenta_contable_activo,
        "cuenta_contable_gasto": catalogo.cuenta_contable_gasto,
        "cuenta_contable_transitoria": catalogo.cuenta_contable_transitoria,
        "centro_costo_defecto": catalogo.centro_costo_defecto,
        "metodo_valoracion": catalogo.metodo_valoracion.value,
        "precio_unitario_valorado": float(catalogo.precio_unitario_valorado or 0),
        "stock_seguridad": float(catalogo.stock_seguridad or 0),
        "punto_reorden": float(catalogo.punto_reorden or 0),
        "codigo_centro": catalogo.codigo_centro,
        "almacen_fisico": catalogo.almacen_fisico,
    }


def _actualizar_estado_pr_y_bom(db: Session, solicitud: SolicitudCompra, estado: str) -> None:
    solicitud.estado_bom = estado
    requisiciones = db.query(RequisicionMRP).filter(
        RequisicionMRP.solicitud_id == solicitud.id_solicitud
    ).all()
    for requisicion in requisiciones:
        requisicion.estado = estado
        detalles = db.query(TrazabilidadRequisicionMRP).filter(
            TrazabilidadRequisicionMRP.requisicion_id == requisicion.id_requisicion
        ).all()
        for detalle in detalles:
            plano = db.query(Plano).filter(
                Plano.codigo_op == detalle.codigo_op,
                Plano.codigo_plano == detalle.codigo_plano,
            ).first()
            if plano:
                db.query(BOMListaMateriales).filter(
                    BOMListaMateriales.plano_id == plano.id_plano,
                    BOMListaMateriales.codigo_material == requisicion.codigo_material,
                ).update(
                    {"estado_abastecimiento": estado},
                    synchronize_session=False,
                )
    if not requisiciones and solicitud.id_plano and solicitud.codigo_sku:
        db.query(BOMListaMateriales).filter(
            BOMListaMateriales.plano_id == solicitud.id_plano,
            BOMListaMateriales.codigo_material == solicitud.codigo_sku,
        ).update(
            {"estado_abastecimiento": estado},
            synchronize_session=False,
        )


@router.get("/centros")
def listar_centros_almacen(
    activos: bool = True,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    consulta = db.query(CentroAlmacen)
    if activos:
        consulta = consulta.filter(CentroAlmacen.activo.is_(True))
    return [
        {
            "id_centro": centro.id_centro,
            "codigo_centro": centro.codigo_centro,
            "nombre_centro": centro.nombre_centro,
            "almacenes": centro.almacenes or [],
            "activo": centro.activo,
        }
        for centro in consulta.order_by(CentroAlmacen.codigo_centro).all()
    ]


@router.post("/centros", status_code=status.HTTP_201_CREATED)
def crear_centro_almacen(
    centro_in: CentroAlmacenCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN"])),
):
    codigo = centro_in.codigo_centro.strip().upper()
    almacenes = list(dict.fromkeys(
        almacen.strip().upper() for almacen in centro_in.almacenes if almacen.strip()
    ))
    if not almacenes:
        raise HTTPException(status_code=422, detail="El centro debe tener al menos un almacén.")
    if "BOD-CUARENTENA-QM" not in almacenes:
        raise HTTPException(
            status_code=422,
            detail="El centro debe incluir BOD-CUARENTENA-QM para recepción e inspección de lotes.",
        )
    if db.query(CentroAlmacen).filter(CentroAlmacen.codigo_centro == codigo).first():
        raise HTTPException(status_code=409, detail="El código de centro ya existe.")
    centro = CentroAlmacen(
        codigo_centro=codigo,
        nombre_centro=centro_in.nombre_centro.strip(),
        almacenes=almacenes,
    )
    try:
        db.add(centro)
        db.commit()
        db.refresh(centro)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar el centro/almacenes.") from error
    return {
        "id_centro": centro.id_centro,
        "codigo_centro": centro.codigo_centro,
        "nombre_centro": centro.nombre_centro,
        "almacenes": centro.almacenes,
        "activo": centro.activo,
    }


@router.get("/categorias")
def listar_categorias(db: Session = Depends(get_db)):
    categorias = db.query(CategoriaInventario).order_by(CategoriaInventario.nombre.asc()).all()
    if categorias:
        return categorias
    return [
        {"codigo": "MATERIA_PRIMA", "nombre": "Materia Prima Directa", "icono": "📦"},
        {"codigo": "HERRAMENTAL", "nombre": "Herramental CNC", "icono": "🔧"},
        {"codigo": "CONSUMIBLE", "nombre": "Consumibles", "icono": "🛠"},
        {"codigo": "EPP", "nombre": "Equipos de Protección", "icono": "🥽"},
        {"codigo": "REPUESTO", "nombre": "Repuestos", "icono": "⚙"},
    ]


@router.post("/categorias", status_code=status.HTTP_201_CREATED)
def crear_categoria(
    categoria_in: CategoriaCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    codigo = categoria_in.codigo.strip().upper().replace(" ", "_")
    if db.query(CategoriaInventario).filter(CategoriaInventario.codigo == codigo).first():
        raise HTTPException(status_code=409, detail="El código de categoría ya existe.")

    categoria = CategoriaInventario(
        codigo=codigo,
        nombre=categoria_in.nombre.strip(),
        icono=categoria_in.icono or "📦",
        descripcion=categoria_in.descripcion,
        es_personalizada=True,
    )
    try:
        db.add(categoria)
        db.commit()
        db.refresh(categoria)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar la categoría.") from error
    return categoria


@router.post("/articulos", status_code=status.HTTP_201_CREATED)
def registrar_articulo(
    articulo_in: ArticuloCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    codigo_sku = articulo_in.codigo_sku.strip()
    if db.query(ArticuloInventario).filter(ArticuloInventario.codigo_sku == codigo_sku).first():
        raise HTTPException(status_code=409, detail="El SKU ya existe en el sistema.")

    if articulo_in.codigo_centro:
        centro = db.query(CentroAlmacen).filter(
            CentroAlmacen.codigo_centro == articulo_in.codigo_centro,
            CentroAlmacen.activo.is_(True),
        ).first()
        if not centro:
            raise HTTPException(status_code=422, detail="El centro seleccionado no existe o está inactivo.")
        if articulo_in.almacen_fisico not in (centro.almacenes or []):
            raise HTTPException(status_code=422, detail="El almacén físico no pertenece al centro seleccionado.")

    tipo_inventario = {
        TipoMaterialSAP.ROH: "MATERIA_PRIMA",
        TipoMaterialSAP.HALB: "SEMIELABORADO",
        TipoMaterialSAP.FERT: "PRODUCTO_TERMINADO",
        TipoMaterialSAP.VERB: "CONSUMIBLE",
        TipoMaterialSAP.ERSA: "REPUESTO",
    }[articulo_in.tipo_material_sap]
    metodo_legacy = (
        "FIFO" if articulo_in.metodo_valoracion == MetodoValoracionSAP.FIFO else "PROMEDIO"
    )
    articulo = ArticuloInventario(
        codigo_sku=codigo_sku,
        nombre=articulo_in.nombre.strip(),
        descripcion=articulo_in.descripcion,
        categoria=articulo_in.categoria,
        tipo_inventario=tipo_inventario,
        unidad_medida=articulo_in.unidad_medida.strip(),
        metodo_valoracion=metodo_legacy,
        stock_minimo=float(articulo_in.punto_reorden or articulo_in.stock_minimo),
        ubicacion=articulo_in.almacen_fisico or articulo_in.ubicacion,
        stock_actual=0,
        stock_reservado=0,
        costo_unitario=(
            articulo_in.precio_unitario_valorado
            if articulo_in.metodo_valoracion == MetodoValoracionSAP.PRECIO_ESTANDAR
            else 0
        ),
    )
    defaults_contables = {
        TipoMaterialSAP.ROH: ("3000-MP", "143505 - Inventario Materia Prima", "710505 - Consumo de Materia Prima"),
        TipoMaterialSAP.HALB: ("3100-HALB", "143506 - Inventario Semielaborados", "710505 - Consumo de Materia Prima"),
        TipoMaterialSAP.FERT: ("3200-FERT", "143515 - Inventario Producto Terminado", "613595 - Costo de Ventas"),
        TipoMaterialSAP.VERB: ("4000-CONSUMIBLES", "143510 - Inventario Consumibles", "510506 - Consumo de Insumos"),
        TipoMaterialSAP.ERSA: ("5000-REPUESTOS", "143520 - Inventario Repuestos", "510520 - Consumo de Repuestos"),
    }
    clase_default, activo_default, gasto_default = defaults_contables[articulo_in.tipo_material_sap]
    catalogo = CatalogoMaterialSAP(
        sku_codigo=codigo_sku,
        descripcion_tecnica=articulo_in.nombre.strip(),
        tipo_material_sap=articulo_in.tipo_material_sap,
        unidad_medida=articulo_in.unidad_medida.strip(),
        clase_valoracion=(articulo_in.clase_valoracion or clase_default).strip(),
        cuenta_contable_activo=(articulo_in.cuenta_contable_activo or activo_default).strip(),
        cuenta_contable_gasto=(articulo_in.cuenta_contable_gasto or gasto_default).strip(),
        cuenta_contable_transitoria=articulo_in.cuenta_contable_transitoria.strip(),
        centro_costo_defecto=articulo_in.centro_costo_defecto.strip(),
        metodo_valoracion=articulo_in.metodo_valoracion,
        precio_unitario_valorado=(
            articulo_in.precio_unitario_valorado
            if articulo_in.metodo_valoracion == MetodoValoracionSAP.PRECIO_ESTANDAR
            else 0
        ),
        stock_seguridad=articulo_in.stock_seguridad,
        punto_reorden=articulo_in.punto_reorden or articulo_in.stock_minimo,
        codigo_centro=articulo_in.codigo_centro,
        almacen_fisico=articulo_in.almacen_fisico,
    )
    try:
        articulo.catalogo_sap = catalogo
        db.add(articulo)
        db.commit()
        db.refresh(articulo)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar el SKU.") from error
    return _articulo_response(articulo, {})


@router.get("/articulos")
def listar_articulos(
    q: Optional[str] = Query(default=None, max_length=100),
    categoria: Optional[str] = None,
    disponible: bool = False,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    consulta = db.query(ArticuloInventario)
    if q and q.strip():
        termino = f"%{q.strip()}%"
        consulta = consulta.filter(
            (ArticuloInventario.codigo_sku.ilike(termino))
            | (ArticuloInventario.nombre.ilike(termino))
        )
    if categoria:
        consulta = consulta.filter(ArticuloInventario.categoria == categoria)

    articulos = consulta.order_by(ArticuloInventario.codigo_sku.asc()).all()
    stocks = _stock_por_lote(db, [articulo.codigo_sku for articulo in articulos])
    resultados = [_articulo_response(articulo, stocks) for articulo in articulos]
    if disponible:
        resultados = [articulo for articulo in resultados if articulo["stock_disponible"] > 0]
    return resultados


@router.get("/materiales-sap")
def listar_catalogo_material_sap(
    q: Optional[str] = Query(default=None, max_length=100),
    tipo_material: Optional[TipoMaterialSAP] = None,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    consulta = db.query(CatalogoMaterialSAP)
    if q and q.strip():
        termino = f"%{q.strip()}%"
        consulta = consulta.filter(
            (CatalogoMaterialSAP.sku_codigo.ilike(termino))
            | (CatalogoMaterialSAP.descripcion_tecnica.ilike(termino))
        )
    if tipo_material:
        consulta = consulta.filter(CatalogoMaterialSAP.tipo_material_sap == tipo_material)
    return [_catalogo_data(item) for item in consulta.order_by(CatalogoMaterialSAP.sku_codigo).all()]


@router.get("/resumen")
def listar_inventario(
    tipo: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    consulta = db.query(ArticuloInventario)
    if tipo:
        consulta = consulta.filter(ArticuloInventario.tipo_inventario == tipo)
    articulos = consulta.order_by(ArticuloInventario.codigo_sku.asc()).all()
    stocks = _stock_por_lote(db, [articulo.codigo_sku for articulo in articulos])
    return [_articulo_response(articulo, stocks) for articulo in articulos]


@router.get("/lotes")
def listar_lotes(
    estado_calidad: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    consulta = db.query(LoteMaterial)
    if estado_calidad:
        consulta = consulta.filter(LoteMaterial.estado_calidad == estado_calidad)
    return [
        {
            "id": lote.id,
            "codigo_lote": lote.codigo_lote,
            "codigo_material": lote.codigo_material,
            "codigo_centro": lote.codigo_centro,
            "almacen_fisico": lote.almacen_fisico,
            "nombre_material": db.query(ArticuloInventario.nombre).filter(
                ArticuloInventario.codigo_sku == lote.codigo_material
            ).scalar(),
            "numero_colada": lote.numero_colada,
            "stock_disponible": float(lote.stock_disponible or 0),
            "stock_reservado": float(lote.stock_reservado or 0),
            "costo_unitario": float(lote.costo_unitario or 0),
            "estado_calidad": lote.estado_calidad or (
                "LIBERADO" if lote.inspeccionado_calidad else "CUARENTENA"
            ),
            "certificado_calidad_url": lote.certificado_calidad_url,
            "fecha_ingreso": lote.fecha_ingreso,
        }
        for lote in consulta.order_by(LoteMaterial.fecha_ingreso.desc()).all()
    ]


@router.patch("/lotes/{id_lote}/calidad")
def actualizar_estado_calidad_lote(
    id_lote: int,
    actualizacion: CalidadLoteUpdate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "CALIDAD"])),
):
    lote = db.query(LoteMaterial).filter(LoteMaterial.id == id_lote).with_for_update().first()
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")

    estado_anterior = lote.estado_calidad or (
        "LIBERADO" if lote.inspeccionado_calidad else "CUARENTENA"
    )
    if estado_anterior == actualizacion.estado_calidad:
        raise HTTPException(status_code=409, detail="El lote ya tiene ese estado de calidad.")

    try:
        db.add(
            RegistroCalidadLote(
                id_lote=lote.id,
                estado_anterior=estado_anterior,
                estado_nuevo=actualizacion.estado_calidad,
                motivo=actualizacion.motivo.strip(),
                registrado_por=usuario["email"],
            )
        )
        lote.estado_calidad = actualizacion.estado_calidad
        lote.inspeccionado_calidad = actualizacion.estado_calidad == "LIBERADO"

        if actualizacion.estado_calidad == "LIBERADO" and estado_anterior == "CUARENTENA":
            catalogo = db.query(CatalogoMaterialSAP).filter(
                CatalogoMaterialSAP.sku_codigo == lote.codigo_material
            ).with_for_update().first()
            if catalogo:
                almacen_origen = lote.almacen_fisico or "BOD-CUARENTENA-QM"
                almacen_destino = catalogo.almacen_fisico or "BOD-MP-01"
                centro = catalogo.codigo_centro or lote.codigo_centro or "CENTRO-01-FUNZA"
                lote.codigo_centro = centro
                lote.almacen_fisico = almacen_destino
                articulo = db.query(ArticuloInventario).filter(
                    ArticuloInventario.codigo_sku == lote.codigo_material
                ).with_for_update().first()
                if articulo:
                    db.add(
                        MovimientoInventario(
                            id_articulo=articulo.id_articulo,
                            id_lote=lote.id,
                            tipo_movimiento="311",
                            cantidad=lote.stock_disponible,
                            costo_unitario=lote.costo_unitario,
                            valor_total=Decimal(str(lote.stock_disponible)) * Decimal(str(lote.costo_unitario)),
                            saldo_cantidad=articulo.stock_actual,
                            referencia_tipo="TRASLADO_QM",
                            referencia_id=lote.codigo_lote,
                            documento_externo="Liberación de lote QM",
                            registrado_por=usuario["email"],
                            destino=almacen_destino,
                        )
                    )
                if catalogo and lote.stock_disponible > 0:
                    db.add(
                        crear_documento_material_sap(
                            catalogo=catalogo,
                            clase_movimiento=ClaseMovimientoSAP.TRASLADO_311,
                            cantidad=Decimal(str(lote.stock_disponible)),
                            costo_unitario=Decimal(str(lote.costo_unitario)),
                            cuenta_debito=catalogo.cuenta_contable_activo,
                            cuenta_credito=catalogo.cuenta_contable_activo,
                            registrado_por=usuario["email"],
                            codigo_centro=centro,
                            almacen_origen=almacen_origen,
                            almacen_destino=almacen_destino,
                            referencia_externa=f"Liberación QM {lote.codigo_lote}",
                        )
                    )

        movimientos_recepcion = db.query(MovimientoInventario).filter(
            MovimientoInventario.id_lote == lote.id,
            MovimientoInventario.referencia_tipo == "PR",
            MovimientoInventario.tipo_movimiento == "101",
        ).all()
        if movimientos_recepcion:
            id_solicitud = UUID(movimientos_recepcion[0].referencia_id)
            solicitud = db.query(SolicitudCompra).filter(
                SolicitudCompra.id_solicitud == id_solicitud
            ).with_for_update().first()
            if solicitud:
                movimientos_pr = db.query(MovimientoInventario).filter(
                    MovimientoInventario.referencia_tipo == "PR",
                    MovimientoInventario.referencia_id == str(solicitud.id_solicitud),
                    MovimientoInventario.tipo_movimiento == "101",
                ).all()
                total_recibido = sum(float(movimiento.cantidad) for movimiento in movimientos_pr)
                id_lotes_pr = {movimiento.id_lote for movimiento in movimientos_pr}
                lotes_pr = db.query(LoteMaterial).filter(
                    LoteMaterial.id.in_(id_lotes_pr)
                ).all()
                completo_y_liberado = (
                    total_recibido >= float(solicitud.cantidad_solicitada or 0)
                    and bool(lotes_pr)
                    and all(
                        (item.estado_calidad or (
                            "LIBERADO" if item.inspeccionado_calidad else "CUARENTENA"
                        )) == "LIBERADO"
                        for item in lotes_pr
                    )
                )
                estado_pr = "EN_ALMACEN" if completo_y_liberado else "EN_COMPRA"
                solicitud.estado = (
                    "EN_ALMACEN"
                    if completo_y_liberado
                    else "RECIBIDA_QM"
                    if total_recibido >= float(solicitud.cantidad_solicitada or 0)
                    else "PARCIAL_RECIBIDA"
                )
                _actualizar_estado_pr_y_bom(db, solicitud, estado_pr)

        db.commit()
        db.refresh(lote)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo actualizar la calidad del lote.") from error

    return {
        "id": lote.id,
        "codigo_lote": lote.codigo_lote,
        "estado_calidad": lote.estado_calidad,
    }


@router.get("/lotes/{id_lote}/auditoria")
def consultar_auditoria_lote(
    id_lote: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    if not db.query(LoteMaterial.id).filter(LoteMaterial.id == id_lote).first():
        raise HTTPException(status_code=404, detail="Lote no encontrado.")
    registros = db.query(RegistroCalidadLote).filter(
        RegistroCalidadLote.id_lote == id_lote
    ).order_by(RegistroCalidadLote.creado_en.desc()).all()
    return [
        {
            "estado_anterior": registro.estado_anterior,
            "estado_nuevo": registro.estado_nuevo,
            "motivo": registro.motivo,
            "registrado_por": registro.registrado_por,
            "creado_en": registro.creado_en,
        }
        for registro in registros
    ]


@router.get("/kardex")
def consultar_kardex(
    codigo_sku: Optional[str] = None,
    limite: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    consulta = db.query(MovimientoInventario, ArticuloInventario, LoteMaterial).join(
        ArticuloInventario,
        MovimientoInventario.id_articulo == ArticuloInventario.id_articulo,
    ).join(
        LoteMaterial,
        MovimientoInventario.id_lote == LoteMaterial.id,
    )
    if codigo_sku:
        consulta = consulta.filter(ArticuloInventario.codigo_sku == codigo_sku)
    filas = consulta.order_by(MovimientoInventario.creado_en.desc()).limit(limite).all()
    return [
        {
            "id_movimiento": movimiento.id_movimiento,
            "codigo_sku": articulo.codigo_sku,
            "nombre_articulo": articulo.nombre,
            "codigo_lote": lote.codigo_lote,
            "numero_colada": lote.numero_colada,
            "tipo_movimiento": movimiento.tipo_movimiento,
            "cantidad": movimiento.cantidad,
            "saldo_cantidad": movimiento.saldo_cantidad,
            "costo_unitario": float(movimiento.costo_unitario),
            "valor_total": float(movimiento.valor_total),
            "referencia_tipo": movimiento.referencia_tipo,
            "referencia_id": movimiento.referencia_id,
            "documento_externo": movimiento.documento_externo,
            "documento_url": movimiento.documento_url,
            "proveedor": movimiento.proveedor,
            "codigo_op": movimiento.codigo_op,
            "destino": movimiento.destino,
            "registrado_por": movimiento.registrado_por,
            "creado_en": movimiento.creado_en,
        }
        for movimiento, articulo, lote in filas
    ]


@router.get("/kardex-sap")
def consultar_kardex_sap(
    sku_codigo: Optional[str] = None,
    limite: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
    usuario: dict = Depends(obtener_usuario_actual),
):
    consulta = db.query(MovimientoKardexSAP)
    if sku_codigo:
        consulta = consulta.filter(MovimientoKardexSAP.sku_codigo == sku_codigo)
    documentos = consulta.order_by(MovimientoKardexSAP.fecha_hora.desc()).limit(limite).all()
    return [
        {
            "id_movimiento": documento.id_movimiento,
            "numero_documento_material": documento.numero_documento_material,
            "clase_movimiento": documento.clase_movimiento.value,
            "sku_codigo": documento.sku_codigo,
            "codigo_centro": documento.codigo_centro,
            "almacen_origen": documento.almacen_origen,
            "almacen_destino": documento.almacen_destino,
            "cantidad": float(documento.cantidad),
            "costo_unitario": float(documento.costo_unitario),
            "costo_total_movimiento": float(documento.costo_total_movimiento),
            "cuenta_debito": documento.cuenta_debito,
            "cuenta_credito": documento.cuenta_credito,
            "centro_costo_imputado": documento.centro_costo_imputado,
            "referencia_op": documento.referencia_op,
            "referencia_externa": documento.referencia_externa,
            "registrado_por": documento.registrado_por,
            "fecha_hora": documento.fecha_hora,
        }
        for documento in documentos
    ]
