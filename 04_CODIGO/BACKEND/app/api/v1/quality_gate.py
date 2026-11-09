import hashlib
import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import BOMListaMateriales, EstadoPlanoEnum, Plano, PlanoArchivo


# Liberación de OP: material en almacén o entregado
ESTADOS_BOM_LIBERABLES = {"EN_ALMACEN", "ENTREGADO"}
# Entrega de Diseño: solicitud de material radicada (o ya abastecida); SIN_SOLICITAR no cuenta
ESTADOS_BOM_RADICADOS = {"SOLICITADO", "EN_COMPRA", "EN_ALMACEN", "ENTREGADO"}


def validar_bom_radicada(db: Session, plano: Plano) -> None:
    estados = [
        item.estado_abastecimiento
        for item in db.query(BOMListaMateriales).filter(BOMListaMateriales.plano_id == plano.id_plano).all()
    ]
    if not estados or any(estado not in ESTADOS_BOM_RADICADOS for estado in estados):
        raise HTTPException(
            status_code=400,
            detail="RN-OP-004: 🔒 Requiere plano PDF y solicitud de material radicada (BOM sin solicitar).",
        )


def validar_bom_abastecida(db: Session, plano: Plano) -> None:
    materiales = db.query(BOMListaMateriales).filter(
        BOMListaMateriales.plano_id == plano.id_plano
    ).all()
    if not materiales:
        raise HTTPException(status_code=400, detail="RN-OP-004: la OP requiere al menos una línea BOM abastecida.")

    pendientes = [
        item.codigo_material
        for item in materiales
        if item.estado_abastecimiento not in ESTADOS_BOM_LIBERABLES
    ]
    if pendientes:
        raise HTTPException(
            status_code=400,
            detail=f"RN-OP-004: materiales BOM pendientes de almacén/entrega: {', '.join(pendientes)}.",
        )


def planos_vigentes_de_producto(db: Session, id_producto: UUID) -> list[Plano]:
    """Planos vigentes del producto: de cada codigo_plano, la fila más reciente por creado_en,
    excluyendo OBSOLETO. Las revisiones no se ordenan como texto."""
    candidatos = db.query(Plano).filter(
        Plano.id_producto == id_producto,
        or_(Plano.estado.is_(None), Plano.estado != EstadoPlanoEnum.OBSOLETO),
    ).order_by(Plano.codigo_plano, Plano.creado_en.desc().nulls_last(), Plano.id_plano).all()
    vigentes = {}
    for plano in candidatos:
        vigentes.setdefault(plano.codigo_plano, plano)
    return list(vigentes.values())


def archivos_vigentes(db: Session, planos: list[Plano]) -> dict[UUID, dict[str, PlanoArchivo]]:
    """Archivo vigente de cada tipo (PDF, STEP, DXF) por plano, desde planos_archivos."""
    ids = [plano.id_plano for plano in planos]
    resultado = {id_plano: {} for id_plano in ids}
    if ids:
        for archivo in db.query(PlanoArchivo).filter(
            PlanoArchivo.id_plano.in_(ids),
            PlanoArchivo.vigente.is_(True),
        ).all():
            resultado[archivo.id_plano][archivo.tipo] = archivo
    return resultado


def ruta_fisica_archivo(ruta: str) -> str:
    # Importación diferida: planos.py importa este módulo
    from app.api.v1 import planos as planos_api
    return os.path.join(planos_api.DIRECTORIO_STATIC_PLANOS, os.path.basename(ruta))


def sha256_de_archivo(ruta_fisica: str) -> str:
    calculo = hashlib.sha256()
    with open(ruta_fisica, "rb") as archivo:
        while bloque := archivo.read(1024 * 1024):
            calculo.update(bloque)
    return calculo.hexdigest()


def validar_pdf_vigente(db: Session, plano: Plano) -> None:
    """Condición 1: PDF vigente en planos_archivos, con hash y tamaño, archivo existente en disco
    y sha256 recalculado igual al registrado (si no, 409). STEP y DXF no se exigen."""
    pdf = db.query(PlanoArchivo).filter(
        PlanoArchivo.id_plano == plano.id_plano,
        PlanoArchivo.tipo == "PDF",
        PlanoArchivo.vigente.is_(True),
    ).first()
    if not pdf:
        raise HTTPException(
            status_code=400,
            detail=f"RN-OP-004: el plano {plano.codigo_plano} no tiene un PDF vigente cargado.",
        )
    if not pdf.sha256 or not pdf.tamano_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"RN-OP-004: el PDF vigente del plano {plano.codigo_plano} no tiene hash o tamaño registrados.",
        )
    ruta_fisica = ruta_fisica_archivo(pdf.ruta)
    if not os.path.isfile(ruta_fisica):
        raise HTTPException(
            status_code=400,
            detail=f"RN-OP-004: el PDF vigente del plano {plano.codigo_plano} no existe en el almacenamiento.",
        )
    if sha256_de_archivo(ruta_fisica) != pdf.sha256.strip():
        raise HTTPException(
            status_code=409,
            detail=(
                f"RN-OP-004: el PDF vigente del plano {plano.codigo_plano} no coincide con el registrado "
                "(sha256 distinto): el archivo en disco fue alterado. Vuelva a cargar el PDF."
            ),
        )


def validar_plano_aprobado(plano: Plano, accion: str) -> None:
    estado = plano.estado.value if hasattr(plano.estado, "value") else plano.estado
    if estado != EstadoPlanoEnum.APROBADO.value or not plano.aprobado_por or not plano.fecha_aprobacion:
        raise HTTPException(
            status_code=400,
            detail=f"El plano {plano.codigo_plano} debe estar APROBADO por Diseño (aprobado_por y fecha_aprobacion) antes de {accion}.",
        )


def validar_entrega_diseno(db: Session, plano: Plano) -> None:
    """Compuerta de entrega de Diseño (estado_diseno LISTA_PARA_LIBERAR): PDF vigente con hash
    verificado, plano APROBADO y BOM radicada. No es la liberación de OP."""
    validar_pdf_vigente(db, plano)
    validar_plano_aprobado(plano, "entregar el diseño")
    validar_bom_radicada(db, plano)


def validar_liberacion_op(db: Session, planos: list[Plano]) -> None:
    """Compuerta de liberación de OP (y de plano LIBERADA): cada plano con PDF vigente con hash
    verificado, plano APROBADO y BOM abastecida (EN_ALMACEN o ENTREGADO)."""
    if not planos:
        raise HTTPException(status_code=400, detail="El producto de la OP no tiene planos vigentes.")
    for plano in planos:
        validar_pdf_vigente(db, plano)
        validar_bom_abastecida(db, plano)
        validar_plano_aprobado(plano, "liberar la OP")


def motivos_liberacion_op(db: Session, planos: list[Plano]) -> list[str]:
    """Evalúa validar_liberacion_op plano a plano para el expediente.
    Lista vacía: la OP cumple la regla; si no, el primer motivo de cada plano que falla."""
    motivos = []
    for grupo in [[plano] for plano in planos] or [[]]:
        try:
            validar_liberacion_op(db, grupo)
        except HTTPException as error:
            if error.detail not in motivos:
                motivos.append(error.detail)
    return motivos


def _como_utc(valor: datetime) -> datetime:
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


def revision_posterior_a_aprobacion(fecha_ultima_revision: datetime | None, fecha_aprobacion: datetime | None) -> bool:
    """Marca "revisar": revisión posterior a la aprobación. Sin aprobación, False."""
    return bool(
        fecha_ultima_revision
        and fecha_aprobacion
        and _como_utc(fecha_ultima_revision) > _como_utc(fecha_aprobacion)
    )


def planos_por_revisar(planos: list[Plano]) -> list[str]:
    """Marca "revisar": planos con una revisión posterior a su aprobación. Solo es un aviso."""
    return [
        plano.codigo_plano
        for plano in planos
        if revision_posterior_a_aprobacion(plano.fecha_ultima_revision, plano.fecha_aprobacion)
    ]
