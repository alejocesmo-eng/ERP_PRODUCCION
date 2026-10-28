from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import requerir_roles
from app.db.database import get_db
from app.db.models import (
    ArticuloInventario,
    CatalogoMaterialSAP,
    CentroAlmacen,
    ClaseMovimientoSAP,
    ConsumoMaterialOP,
    LoteMaterial,
    MovimientoInventario,
    OrdenProduccion,
    SolicitudCompra,
)
from app.services.inventario_sap import crear_documento_material_sap

router = APIRouter()


class TipoDestinoEnum(str, Enum):
    ORDEN_PRODUCCION = "ORDEN_PRODUCCION"
    CENTRO_COSTOS = "CENTRO_COSTOS"
    ASIGNACION_OPERARIO = "ASIGNACION_OPERARIO"
    PRESTAMO_TEMPORAL = "PRESTAMO_TEMPORAL"
    SCRAP = "SCRAP"


class EntradaConFacturaCreate(BaseModel):
    numero_solicitud_compra: str = Field(min_length=1, max_length=50)
    id_solicitud: UUID
    codigo_sku: str = Field(min_length=1, max_length=50)
    cantidad_solicitada: Optional[Decimal] = Field(default=None, gt=0)
    cantidad_recibida: Decimal = Field(gt=0)
    costo_unitario: Decimal = Field(ge=0)
    numero_factura: str = Field(min_length=1, max_length=100)
    factura_digital_url: Optional[str] = Field(
        default=None,
        max_length=255,
        pattern="^https?://",
    )
    numero_lote: Optional[str] = Field(default=None, max_length=50)
    numero_colada: Optional[str] = Field(default=None, max_length=50)
    certificado_3_1_url: Optional[str] = Field(
        default=None,
        max_length=255,
        pattern="^https?://",
    )
    proveedor: Optional[str] = Field(default=None, max_length=150)
    recibido_por: Optional[str] = Field(default="Almacén Central", max_length=150)


class SalidaAlmacenCreate(BaseModel):
    codigo_sku: str = Field(min_length=1, max_length=50)
    cantidad_salida: Decimal = Field(gt=0)
    tipo_destino: TipoDestinoEnum
    codigo_op: Optional[str] = Field(default=None, max_length=50)
    id_op: Optional[UUID] = None
    centro_costos: Optional[str] = Field(default=None, max_length=100)
    operario_responsable: Optional[str] = Field(default=None, max_length=150)
    fecha_devolucion_estimada: Optional[str] = None
    observaciones: Optional[str] = None


class TrasladoAlmacenCreate(BaseModel):
    codigo_lote: str = Field(min_length=1, max_length=50)
    codigo_centro_destino: str = Field(min_length=1, max_length=50)
    almacen_destino: str = Field(min_length=1, max_length=50)
    observaciones: Optional[str] = None


def _decimal(value) -> Decimal:
    return Decimal(str(value or 0))


@router.post("/recepcion-compra", status_code=status.HTTP_201_CREATED)
def registrar_recepcion_compra(
    entrada: EntradaConFacturaCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    solicitud = db.query(SolicitudCompra).filter(
        SolicitudCompra.id_solicitud == entrada.id_solicitud
    ).with_for_update().first()
    if not solicitud or solicitud.numero_solicitud != entrada.numero_solicitud_compra:
        raise HTTPException(status_code=404, detail="La requisición de compra no existe.")
    if solicitud.estado_bom != "EN_COMPRA":
        raise HTTPException(
            status_code=409,
            detail="Almacén solo puede recibir requisiciones con estado EN_COMPRA.",
        )
    if solicitud.codigo_sku and solicitud.codigo_sku != entrada.codigo_sku:
        raise HTTPException(status_code=400, detail="El SKU no coincide con la requisición.")

    articulo = db.query(ArticuloInventario).filter(
        ArticuloInventario.codigo_sku == entrada.codigo_sku
    ).with_for_update().first()
    if not articulo:
        raise HTTPException(
            status_code=404,
            detail="El SKU no está registrado en Inventario General.",
        )
    catalogo = db.query(CatalogoMaterialSAP).filter(
        CatalogoMaterialSAP.id_articulo == articulo.id_articulo
    ).with_for_update().first()
    if not catalogo:
        raise HTTPException(status_code=409, detail="El SKU no tiene imputación maestra SAP configurada.")
    centro = db.query(CentroAlmacen).filter(
        CentroAlmacen.codigo_centro == catalogo.codigo_centro,
        CentroAlmacen.activo.is_(True),
    ).first()
    if not centro or "BOD-CUARENTENA-QM" not in (centro.almacenes or []):
        raise HTTPException(
            status_code=409,
            detail="El centro del material debe tener el almacén BOD-CUARENTENA-QM configurado.",
        )

    movimientos_previos = db.query(MovimientoInventario).filter(
        MovimientoInventario.referencia_tipo == "PR",
        MovimientoInventario.referencia_id == str(solicitud.id_solicitud),
        MovimientoInventario.tipo_movimiento == "101",
    ).all()
    recibido_previamente = sum((_decimal(movimiento.cantidad) for movimiento in movimientos_previos), Decimal("0"))
    cantidad_solicitada = _decimal(solicitud.cantidad_solicitada)
    if recibido_previamente + entrada.cantidad_recibida > cantidad_solicitada:
        raise HTTPException(
            status_code=409,
            detail="La cantidad recibida supera el saldo pendiente de la requisición.",
        )

    codigo_lote = (entrada.numero_lote or "").strip() or (
        f"REC-{entrada.codigo_sku[:25]}-{uuid4().hex[:8].upper()}"
    )
    if db.query(LoteMaterial).filter(LoteMaterial.codigo_lote == codigo_lote).first():
        raise HTTPException(status_code=409, detail="El código de lote ya existe.")

    costo_unitario = _decimal(articulo.costo_unitario)
    articulo_cantidad_anterior = _decimal(articulo.stock_actual)
    precio = entrada.costo_unitario
    if catalogo.metodo_valoracion != "PRECIO_ESTANDAR":
        valor_anterior = articulo_cantidad_anterior * costo_unitario
        articulo.costo_unitario = (
            (valor_anterior + entrada.cantidad_recibida * precio)
            / (articulo_cantidad_anterior + entrada.cantidad_recibida)
        ).quantize(Decimal("0.0001")) if articulo_cantidad_anterior + entrada.cantidad_recibida else costo_unitario

    lote = LoteMaterial(
        codigo_lote=codigo_lote,
        codigo_material=articulo.codigo_sku,
        codigo_centro=catalogo.codigo_centro,
        almacen_fisico="BOD-CUARENTENA-QM",
        numero_colada=entrada.numero_colada or entrada.numero_lote,
        stock_disponible=float(entrada.cantidad_recibida),
        stock_reservado=0,
        costo_unitario=precio,
        inspeccionado_calidad=False,
        estado_calidad="CUARENTENA",
        certificado_calidad_url=entrada.certificado_3_1_url,
    )
    articulo.stock_actual = float(articulo_cantidad_anterior + entrada.cantidad_recibida)

    try:
        db.add(lote)
        db.flush()
        db.add(
            MovimientoInventario(
                id_articulo=articulo.id_articulo,
                id_lote=lote.id,
                tipo_movimiento="101",
                cantidad=float(entrada.cantidad_recibida),
                costo_unitario=precio,
                valor_total=entrada.cantidad_recibida * precio,
                saldo_cantidad=articulo.stock_actual,
                referencia_tipo="PR",
                referencia_id=str(solicitud.id_solicitud),
                documento_externo=entrada.numero_factura,
                documento_url=entrada.factura_digital_url,
                registrado_por=usuario["email"],
                proveedor=entrada.proveedor,
            )
        )
        db.add(
            crear_documento_material_sap(
                catalogo=catalogo,
                clase_movimiento=ClaseMovimientoSAP.ENTRADA_COMPRA_101,
                cantidad=entrada.cantidad_recibida,
                costo_unitario=precio,
                cuenta_debito=catalogo.cuenta_contable_activo,
                cuenta_credito=catalogo.cuenta_contable_transitoria,
                registrado_por=usuario["email"],
                codigo_centro=catalogo.codigo_centro,
                almacen_destino="BOD-CUARENTENA-QM",
                centro_costo_imputado=catalogo.centro_costo_defecto,
                referencia_externa=entrada.numero_factura,
            )
        )
        catalogo.precio_unitario_valorado = (
            articulo.costo_unitario
            if catalogo.metodo_valoracion != "PRECIO_ESTANDAR"
            else catalogo.precio_unitario_valorado
        )

        recibido_total = recibido_previamente + entrada.cantidad_recibida
        completo = recibido_total >= cantidad_solicitada
        if completo:
            solicitud.estado = "RECIBIDA_QM"
        else:
            solicitud.estado = "PARCIAL_RECIBIDA"
        db.commit()
        db.refresh(lote)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar la recepción.") from error

    return {
        "status": "exito",
        "mensaje": "Recepción registrada; el lote queda en CUARENTENA hasta su liberación por Calidad.",
        "estado_calidad": lote.estado_calidad,
        "estado_requisicion": solicitud.estado_bom,
        "cantidad_recibida_acumulada": float(recibido_total),
        "cantidad_pendiente": float(max(cantidad_solicitada - recibido_total, Decimal("0"))),
        "codigo_lote": lote.codigo_lote,
        "costo_unitario": float(precio),
    }


@router.post("/salidas", status_code=status.HTTP_201_CREATED)
def registrar_salida_almacen(
    salida: SalidaAlmacenCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    articulo = db.query(ArticuloInventario).filter(
        ArticuloInventario.codigo_sku == salida.codigo_sku
    ).with_for_update().first()
    if not articulo:
        raise HTTPException(status_code=404, detail="SKU no encontrado en Inventario General.")
    catalogo = db.query(CatalogoMaterialSAP).filter(
        CatalogoMaterialSAP.id_articulo == articulo.id_articulo
    ).with_for_update().first()
    if not catalogo:
        raise HTTPException(status_code=409, detail="El SKU no tiene imputación maestra SAP configurada.")

    orden = None
    if salida.tipo_destino == TipoDestinoEnum.ORDEN_PRODUCCION:
        if not salida.codigo_op and not salida.id_op:
            raise HTTPException(
                status_code=400,
                detail="Para despachar a una OP se exige seleccionar la Orden de Producción.",
            )
        consulta_op = db.query(OrdenProduccion)
        if salida.id_op:
            consulta_op = consulta_op.filter(OrdenProduccion.id_op == salida.id_op)
        else:
            consulta_op = consulta_op.filter(OrdenProduccion.codigo_op == salida.codigo_op)
        orden = consulta_op.with_for_update().first()
        if not orden:
            raise HTTPException(status_code=404, detail="La Orden de Producción no existe.")

    consulta_lotes = db.query(LoteMaterial).filter(
        LoteMaterial.codigo_material == articulo.codigo_sku,
        LoteMaterial.stock_disponible > 0,
    )
    if salida.tipo_destino == TipoDestinoEnum.SCRAP:
        consulta_lotes = consulta_lotes.filter(LoteMaterial.estado_calidad == "RECHAZADO")
    else:
        consulta_lotes = consulta_lotes.filter(
            or_(
                LoteMaterial.estado_calidad == "LIBERADO",
                (
                    LoteMaterial.estado_calidad.is_(None)
                    & LoteMaterial.inspeccionado_calidad.is_(True)
                ),
            )
        )
    lotes = consulta_lotes.order_by(
        LoteMaterial.fecha_ingreso.asc(),
        LoteMaterial.id.asc(),
    ).with_for_update().all()
    if not lotes:
        raise HTTPException(
            status_code=409,
            detail=(
                "No hay lotes RECHAZADOS disponibles para descarte."
                if salida.tipo_destino == TipoDestinoEnum.SCRAP
                else "No hay lotes LIBERADOS disponibles para este SKU; se bloquea el despacho por RN-OP-004."
            ),
        )

    total_liberado = min(
        sum((_decimal(lote.stock_disponible) for lote in lotes), Decimal("0")),
        max(_decimal(articulo.stock_actual), Decimal("0")),
    )
    reservado_lotes = sum(
        (
            min(
                _decimal(lote.stock_reservado),
                _decimal(lote.stock_disponible),
            )
            for lote in lotes
        ),
        Decimal("0"),
    )
    reservado_articulo = min(_decimal(articulo.stock_reservado), total_liberado)
    reservado_efectivo = min(max(reservado_articulo, reservado_lotes), total_liberado)
    reservado_sin_lote = max(reservado_articulo - reservado_lotes, Decimal("0"))
    es_op = salida.tipo_destino == TipoDestinoEnum.ORDEN_PRODUCCION
    disponible = total_liberado if es_op else max(
        total_liberado - reservado_efectivo, Decimal("0")
    )
    if salida.cantidad_salida > disponible:
        raise HTTPException(
            status_code=409,
            detail=f"Cantidad disponible para despacho: {disponible}.",
        )

    retenido_por_lote: dict[int, Decimal] = {}
    if not es_op and reservado_sin_lote:
        pendiente_reserva = reservado_sin_lote
        for lote in reversed(lotes):
            capacidad = max(
                _decimal(lote.stock_disponible) - _decimal(lote.stock_reservado),
                Decimal("0"),
            )
            retenido = min(capacidad, pendiente_reserva)
            retenido_por_lote[lote.id] = retenido
            pendiente_reserva -= retenido
            if pendiente_reserva <= 0:
                break

    referencia_id = str(uuid4())
    restante = salida.cantidad_salida
    stock_actual = _decimal(articulo.stock_actual)
    valor_total_salida = Decimal("0")
    movimientos = []
    consumo_op = []

    try:
        for lote in lotes:
            reservado_lote = _decimal(lote.stock_reservado)
            reservado_no_asignado = retenido_por_lote.get(lote.id, Decimal("0"))
            capacidad = _decimal(lote.stock_disponible)
            if not es_op:
                capacidad -= reservado_lote + reservado_no_asignado
            cantidad = min(max(capacidad, Decimal("0")), restante)
            if cantidad <= 0:
                continue

            costo = (
                _decimal(lote.costo_unitario)
                if articulo.metodo_valoracion == "FIFO"
                else _decimal(articulo.costo_unitario)
            )
            valor = cantidad * costo
            lote.stock_disponible = float(_decimal(lote.stock_disponible) - cantidad)
            if es_op:
                lote.stock_reservado = float(
                    min(reservado_lote, _decimal(lote.stock_disponible))
                )
            stock_actual -= cantidad
            restante -= cantidad
            valor_total_salida += valor
            movimiento = MovimientoInventario(
                id_articulo=articulo.id_articulo,
                id_lote=lote.id,
                tipo_movimiento="261" if es_op else "201",
                cantidad=float(cantidad),
                costo_unitario=costo,
                valor_total=valor,
                saldo_cantidad=float(stock_actual),
                referencia_tipo="OP" if es_op else "SALIDA",
                referencia_id=orden.codigo_op if orden else referencia_id,
                documento_externo=salida.observaciones,
                codigo_op=orden.codigo_op if orden else None,
                destino=salida.tipo_destino.value,
                registrado_por=usuario["email"],
            )
            movimientos.append(movimiento)
            if salida.tipo_destino == TipoDestinoEnum.SCRAP:
                clase_sap = ClaseMovimientoSAP.SCRAP_551
                cuenta_debito = catalogo.cuenta_contable_gasto
                cuenta_credito = catalogo.cuenta_contable_activo
            elif orden:
                clase_sap = ClaseMovimientoSAP.CONSUMO_OP_261
                cuenta_debito = catalogo.cuenta_contable_gasto
                cuenta_credito = catalogo.cuenta_contable_activo
            else:
                clase_sap = ClaseMovimientoSAP.SALIDA_CENTRO_COSTO_201
                cuenta_debito = catalogo.cuenta_contable_gasto
                cuenta_credito = catalogo.cuenta_contable_activo
            db.add(
                crear_documento_material_sap(
                    catalogo=catalogo,
                    clase_movimiento=clase_sap,
                    cantidad=cantidad,
                    costo_unitario=costo,
                    cuenta_debito=cuenta_debito,
                    cuenta_credito=cuenta_credito,
                    registrado_por=usuario["email"],
                    codigo_centro=lote.codigo_centro or catalogo.codigo_centro,
                    almacen_origen=lote.almacen_fisico or catalogo.almacen_fisico,
                    centro_costo_imputado=(
                        catalogo.centro_costo_defecto
                        if salida.tipo_destino == TipoDestinoEnum.SCRAP
                        else salida.centro_costos or catalogo.centro_costo_defecto
                    ),
                    referencia_op=orden.codigo_op if orden else None,
                    referencia_externa=salida.observaciones,
                )
            )
            if orden:
                consumo_op.append(
                    ConsumoMaterialOP(
                        op_id=orden.id_op,
                        codigo_material=articulo.codigo_sku,
                        descripcion_material=articulo.nombre,
                        cantidad=float(cantidad),
                        unidad_medida=articulo.unidad_medida or "UND",
                        costo_unitario=costo,
                        fuente="KARDEX",
                    )
                )

        if restante > 0:
            raise HTTPException(
                status_code=409,
                detail="No se pudo completar el despacho con lotes liberados y no reservados.",
            )

        articulo.stock_actual = float(stock_actual)
        if orden:
            reserva_objetivo = min(
                max(reservado_efectivo - salida.cantidad_salida, Decimal("0")),
                max(total_liberado - salida.cantidad_salida, Decimal("0")),
            )
            reserva_lotes_actual = sum(
                (_decimal(lote.stock_reservado) for lote in lotes),
                Decimal("0"),
            )
            if reserva_lotes_actual > reserva_objetivo:
                por_liberar = reserva_lotes_actual - reserva_objetivo
                for lote in reversed(lotes):
                    reservado_lote = _decimal(lote.stock_reservado)
                    liberado = min(reservado_lote, por_liberar)
                    lote.stock_reservado = float(reservado_lote - liberado)
                    por_liberar -= liberado
                    if por_liberar <= 0:
                        break
            elif reserva_lotes_actual < reserva_objetivo:
                por_reservar = reserva_objetivo - reserva_lotes_actual
                for lote in lotes:
                    capacidad = max(
                        _decimal(lote.stock_disponible) - _decimal(lote.stock_reservado),
                        Decimal("0"),
                    )
                    reservado = min(capacidad, por_reservar)
                    lote.stock_reservado = float(_decimal(lote.stock_reservado) + reservado)
                    por_reservar -= reservado
                    if por_reservar <= 0:
                        break
            articulo.stock_reservado = float(reserva_objetivo)
        db.add_all(movimientos)
        if consumo_op:
            db.add_all(consumo_op)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar la salida de almacén.") from error

    return {
        "status": "exito",
        "mensaje": f"Salida de {salida.cantidad_salida} {articulo.unidad_medida} registrada.",
        "codigo_sku": articulo.codigo_sku,
        "codigo_op": orden.codigo_op if orden else None,
        "tipo_movimiento": "261" if es_op else "201",
        "cantidad_salida": float(salida.cantidad_salida),
        "valor_total": float(valor_total_salida),
        "saldo_stock": articulo.stock_actual,
        "lotes_consumidos": [movimiento.id_lote for movimiento in movimientos],
    }


@router.post("/traslados", status_code=status.HTTP_201_CREATED)
def registrar_traslado_almacen(
    traslado: TrasladoAlmacenCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(requerir_roles(["ADMIN", "ALMACEN"])),
):
    lote = db.query(LoteMaterial).filter(
        LoteMaterial.codigo_lote == traslado.codigo_lote
    ).with_for_update().first()
    if not lote:
        raise HTTPException(status_code=404, detail="Lote no encontrado.")
    if lote.stock_disponible <= 0:
        raise HTTPException(status_code=409, detail="El lote no tiene cantidad disponible para trasladar.")
    if lote.stock_reservado > 0:
        raise HTTPException(status_code=409, detail="No se puede trasladar un lote con cantidad reservada.")

    articulo = db.query(ArticuloInventario).filter(
        ArticuloInventario.codigo_sku == lote.codigo_material
    ).with_for_update().first()
    catalogo = db.query(CatalogoMaterialSAP).filter(
        CatalogoMaterialSAP.sku_codigo == lote.codigo_material
    ).with_for_update().first()
    centro_destino = db.query(CentroAlmacen).filter(
        CentroAlmacen.codigo_centro == traslado.codigo_centro_destino,
        CentroAlmacen.activo.is_(True),
    ).first()
    if not articulo or not catalogo:
        raise HTTPException(status_code=409, detail="El lote no tiene maestro de material SAP asociado.")
    if not centro_destino:
        raise HTTPException(status_code=404, detail="Centro destino no encontrado o inactivo.")
    if traslado.almacen_destino not in (centro_destino.almacenes or []):
        raise HTTPException(status_code=422, detail="El almacén no pertenece al centro de destino.")

    almacen_origen = lote.almacen_fisico or catalogo.almacen_fisico
    centro_origen = lote.codigo_centro or catalogo.codigo_centro
    cantidad = _decimal(lote.stock_disponible)
    costo = _decimal(lote.costo_unitario)
    try:
        lote.codigo_centro = centro_destino.codigo_centro
        lote.almacen_fisico = traslado.almacen_destino
        movimiento = MovimientoInventario(
            id_articulo=articulo.id_articulo,
            id_lote=lote.id,
            tipo_movimiento="311",
            cantidad=float(cantidad),
            costo_unitario=costo,
            valor_total=cantidad * costo,
            saldo_cantidad=articulo.stock_actual,
            referencia_tipo="TRASLADO",
            referencia_id=traslado.codigo_lote,
            documento_externo=traslado.observaciones,
            codigo_op=None,
            destino=traslado.almacen_destino,
            registrado_por=usuario["email"],
        )
        db.add(movimiento)
        documento_sap = crear_documento_material_sap(
            catalogo=catalogo,
            clase_movimiento=ClaseMovimientoSAP.TRASLADO_311,
            cantidad=cantidad,
            costo_unitario=costo,
            cuenta_debito=catalogo.cuenta_contable_activo,
            cuenta_credito=catalogo.cuenta_contable_activo,
            registrado_por=usuario["email"],
            codigo_centro=centro_destino.codigo_centro,
            almacen_origen=almacen_origen,
            almacen_destino=traslado.almacen_destino,
            referencia_externa=traslado.observaciones or traslado.codigo_lote,
        )
        db.add(documento_sap)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar el traslado.") from error

    return {
        "status": "exito",
        "numero_documento_material": documento_sap.numero_documento_material,
        "codigo_lote": lote.codigo_lote,
        "codigo_centro": centro_destino.codigo_centro,
        "almacen_destino": traslado.almacen_destino,
        "cantidad_trasladada": float(cantidad),
    }
