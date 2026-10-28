from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.db.models import CatalogoMaterialSAP, ClaseMovimientoSAP, MovimientoKardexSAP


def crear_documento_material_sap(
    *,
    catalogo: CatalogoMaterialSAP,
    clase_movimiento: ClaseMovimientoSAP,
    cantidad: Decimal,
    costo_unitario: Decimal,
    cuenta_debito: str,
    cuenta_credito: str,
    registrado_por: str,
    codigo_centro: str | None = None,
    almacen_origen: str | None = None,
    almacen_destino: str | None = None,
    centro_costo_imputado: str | None = None,
    referencia_op: str | None = None,
    referencia_externa: str | None = None,
) -> MovimientoKardexSAP:
    cantidad_decimal = Decimal(cantidad)
    costo_decimal = Decimal(costo_unitario)
    ahora = datetime.now(timezone.utc)
    return MovimientoKardexSAP(
        numero_documento_material=f"DOC-{ahora:%Y%m%d}-{uuid4().hex[:8].upper()}",
        clase_movimiento=clase_movimiento,
        sku_codigo=catalogo.sku_codigo,
        codigo_centro=codigo_centro or catalogo.codigo_centro or "CENTRO-01-FUNZA",
        almacen_origen=almacen_origen,
        almacen_destino=almacen_destino,
        cantidad=cantidad_decimal,
        costo_unitario=costo_decimal,
        costo_total_movimiento=(cantidad_decimal * costo_decimal).quantize(Decimal("0.0001")),
        cuenta_debito=cuenta_debito,
        cuenta_credito=cuenta_credito,
        centro_costo_imputado=centro_costo_imputado,
        referencia_op=referencia_op,
        referencia_externa=referencia_externa,
        registrado_por=registrado_por,
        fecha_hora=ahora,
    )
