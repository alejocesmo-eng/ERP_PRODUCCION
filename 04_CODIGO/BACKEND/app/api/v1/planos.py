import hashlib
import os
import re
import shutil
import unicodedata
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, date, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, computed_field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
import jwt

from app.db.database import get_db
from app.db.models import BOMListaMateriales, EstadoPlanoEnum, Plano, PlanoArchivo, Proyecto
from app.api.deps import obtener_usuario_actual, requerir_roles
from app.core.roles import ROLES_APROBAR_PLANO, ROLES_REVISION_PLANO
from app.api.v1.quality_gate import (
    ESTADOS_BOM_LIBERABLES,
    revision_posterior_a_aprobacion,
    ruta_fisica_archivo,
    sha256_de_archivo,
    validar_entrega_diseno,
    validar_liberacion_op,
)
from app.services.auditoria import agregar_evento_trazabilidad
from app.services.historial_planos import (
    exigir_justificacion,
    historial_por_plano,
    justificacion_opcional,
    registrar_evento_plano,
)

router = APIRouter()

DIRECTORIO_STATIC_PLANOS = "static/planos"
os.makedirs(DIRECTORIO_STATIC_PLANOS, exist_ok=True)

SECRET_KEY_PLANOS = os.getenv("JWT_SECRET_KEY_PLANOS")
if not SECRET_KEY_PLANOS:
    raise RuntimeError("Falta la variable de entorno obligatoria JWT_SECRET_KEY_PLANOS. Cree 04_CODIGO/BACKEND/.env a partir de .env.example.")
ALGORITHM = "HS256"

ESTADOS_ENTREGA_DISENO = {"LISTA_PARA_LIBERAR", "LIBERADA"}

# tipo -> (columna destino, extensiones admitidas, extensión estandarizada)
FORMATOS_CAD = {
    "pdf": ("archivo_pdf_url", (".pdf",), ".pdf"),
    "step": ("archivo_step_url", (".step", ".stp"), ".step"),
    "dxf": ("archivo_dxf_url", (".dxf",), ".dxf"),
}
TAMANO_BLOQUE_CARGA = 1024 * 1024
CAMPOS_ARCHIVO = ("archivo_pdf_url", "archivo_step_url", "archivo_dxf_url")


def _tipo_por_extension(nombre: Optional[str]) -> str:
    nombre = (nombre or "").lower()
    for tipo, (_, extensiones, _) in FORMATOS_CAD.items():
        if nombre.endswith(extensiones):
            return tipo
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Formato no permitido. Use .pdf, .step/.stp o .dxf.",
    )


def _obtener_plano_para_carga(db: Session, id_plano: UUID) -> Plano:
    # Bloquea la fila del plano: dos cargas simultáneas del mismo plano se serializan
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).with_for_update().first()
    if not plano:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano no encontrado.")
    return plano


def _guardar_archivo_cad(
    db: Session, plano: Plano, archivo: UploadFile, tipo: str, usuario_actual: dict, justificacion: Optional[str] = None
) -> Plano:
    """Guarda el archivo con sha256 y tamaño en planos_archivos (migración 19).
    El vigente anterior del mismo tipo pasa a histórico; la columna archivo_*_url sigue al vigente.
    Historial (migración 21): la primera carga del tipo es CARGA_ARCHIVO sin justificación;
    reemplazar el vigente por otro contenido es CAMBIO_ARCHIVO y exige justificación (422)."""
    if tipo not in FORMATOS_CAD:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo CAD inválido. Use pdf, step o dxf.")
    # Inmutabilidad post-liberación: el paquete técnico liberado queda congelado
    if plano.estado_diseno == "LIBERADA":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La OP está LIBERADA: los archivos CAD son de solo consulta.",
        )

    campo, extensiones, ext_final = FORMATOS_CAD[tipo]
    if not (archivo.filename or "").lower().endswith(extensiones):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato inválido para {tipo.upper()}. Extensiones admitidas: {', '.join(extensiones)}.",
        )

    # Se escribe en un temporal calculando sha256 y tamaño; el nombre final incluye el hash
    # para que una carga nueva no sobrescriba el archivo del histórico.
    os.makedirs(DIRECTORIO_STATIC_PLANOS, exist_ok=True)
    tipo_archivo = tipo.upper()
    vigente = db.query(PlanoArchivo).filter(
        PlanoArchivo.id_plano == plano.id_plano,
        PlanoArchivo.tipo == tipo_archivo,
        PlanoArchivo.vigente.is_(True),
    ).first()
    ruta_temporal = os.path.join(DIRECTORIO_STATIC_PLANOS, f".carga_{uuid4().hex}.tmp")
    calculo = hashlib.sha256()
    tamano_bytes = 0
    try:
        with open(ruta_temporal, "wb") as destino:
            while bloque := archivo.file.read(TAMANO_BLOQUE_CARGA):
                calculo.update(bloque)
                tamano_bytes += len(bloque)
                destino.write(bloque)
        if tamano_bytes == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")
        sha256 = calculo.hexdigest()
        # Reemplazo con otro contenido: la justificación se valida antes de dejar el archivo en disco
        cambio_archivo = bool(vigente) and vigente.sha256 != sha256
        texto_justificacion = exigir_justificacion(justificacion) if cambio_archivo else None
        prefijo = f"{plano.codigo_plano}_{plano.version}_{sha256[:12]}"
        nombre_archivo = re.sub(r"[^A-Za-z0-9._-]", "_", prefijo) + ext_final
        os.replace(ruta_temporal, os.path.join(DIRECTORIO_STATIC_PLANOS, nombre_archivo))
    finally:
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)

    ruta = f"/static/planos/{nombre_archivo}"
    try:
        # El mismo archivo ya vigente (mismo contenido y misma ruta) no crea otra entrada en el histórico
        if not (vigente and vigente.sha256 == sha256 and vigente.ruta == ruta):
            if vigente is None or cambio_archivo:
                registrar_evento_plano(
                    db, plano,
                    "CAMBIO_ARCHIVO" if cambio_archivo else "CARGA_ARCHIVO",
                    usuario_actual["email"],
                    tipo_archivo=tipo_archivo,
                    sha256=sha256,
                    justificacion=texto_justificacion,
                )
            if vigente:
                vigente.vigente = False
                db.flush()
            db.add(PlanoArchivo(
                id_plano=plano.id_plano,
                tipo=tipo_archivo,
                ruta=ruta,
                nombre_original=os.path.basename(archivo.filename)[:255],
                tamano_bytes=tamano_bytes,
                sha256=sha256,
                revision=plano.version,
                vigente=True,
                subido_por=usuario_actual["email"],
            ))
        setattr(plano, campo, ruta)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar el archivo del plano.") from error
    db.refresh(plano)
    return plano


def _archivo_almacenado(tipo: str, url: str) -> dict:
    """Archivo que POST /planos/ referencia por ruta: debe estar ya en el almacenamiento de
    planos con la extensión del tipo. Devuelve ruta, nombre, tamaño y sha256 calculados del
    archivo en disco para registrarlo como vigente en planos_archivos."""
    _, extensiones, _ = FORMATOS_CAD[tipo]
    nombre = os.path.basename(url or "")
    if not nombre.lower().endswith(extensiones):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato inválido para {tipo.upper()}. Extensiones admitidas: {', '.join(extensiones)}.",
        )
    ruta_fisica = ruta_fisica_archivo(url)
    if not os.path.isfile(ruta_fisica):
        raise HTTPException(
            status_code=422,
            detail=(
                f"El archivo {tipo.upper()} '{nombre}' no existe en el almacenamiento de planos: "
                f"súbalo con POST /planos/upload-cad/{{id_plano}}/{tipo} después de crear el plano."
            ),
        )
    tamano_bytes = os.path.getsize(ruta_fisica)
    if tamano_bytes == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El archivo {tipo.upper()} '{nombre}' está vacío.")
    return {
        "ruta": f"/static/planos/{nombre}",
        "nombre": nombre,
        "tamano_bytes": tamano_bytes,
        "sha256": sha256_de_archivo(ruta_fisica),
    }


def _como_utc(valor: datetime) -> datetime:
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor


def _detener_cronometro_diseno(plano: Plano, ahora: datetime) -> None:
    """Cierra el tramo activo: tiempo trabajado = fecha_fin_diseno - fecha_inicio_diseno."""
    plano.fecha_fin_diseno = ahora
    if plano.fecha_inicio_diseno:
        plano.tiempo_total_diseno_minutos = int((ahora - _como_utc(plano.fecha_inicio_diseno)).total_seconds() / 60)


def _nombre_base_dibujante(nombre: Optional[str]) -> str:
    """Normaliza el dibujante: "Ing. Carlós Ruiz - Diseñador" equivale a "carlos ruiz"."""
    base = unicodedata.normalize("NFD", (nombre or "").split(" - ")[0])
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    return re.sub(r"^(ing|arq|tec|sr|sra)\.?\s+", "", base.strip(), flags=re.IGNORECASE).strip().lower()


def _reanudar_cronometro_diseno(plano: Plano, ahora: datetime) -> None:
    """Al reanudar, desplaza el inicio efectivo por la duración de la pausa para no contarla."""
    if plano.fecha_inicio_diseno and plano.fecha_fin_diseno:
        plano.fecha_inicio_diseno = _como_utc(plano.fecha_inicio_diseno) + (ahora - _como_utc(plano.fecha_fin_diseno))
    else:
        plano.fecha_inicio_diseno = ahora
    plano.fecha_fin_diseno = None


# =============================================================================
# SCHEMAS PYDANTIC
# =============================================================================

class BOMItemResponse(BaseModel):
    codigo_material: str
    descripcion: str
    cantidad_requerida: float
    unidad_medida: str
    estado_abastecimiento: str

    class Config:
        from_attributes = True


class PlanoResponse(BaseModel):
    id_plano: UUID
    # Opcionales desde la migración 18: el plano pertenece al producto
    id_proyecto: Optional[UUID] = None
    id_producto: Optional[UUID] = None
    codigo_op: Optional[str] = None
    codigo_plano: str
    version: str
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = "Mecanizados"
    estado_diseno: str
    material_requerido: Optional[str] = None
    archivo_pdf_url: Optional[str] = None
    archivo_step_url: Optional[str] = None
    archivo_dxf_url: Optional[str] = None
    fecha_entrega_produccion: Optional[date] = None
    fecha_inicio_diseno: Optional[datetime] = None
    fecha_fin_diseno: Optional[datetime] = None
    tiempo_total_diseno_minutos: Optional[int] = None
    observaciones_tecnicas: Optional[str] = None
    estado: Optional[EstadoPlanoEnum] = None
    aprobado_por: Optional[str] = None
    fecha_aprobacion: Optional[datetime] = None
    fecha_ultima_revision: Optional[datetime] = None
    creado_en: datetime
    bom_items: List["BOMItemResponse"] = Field(default_factory=list)

    @computed_field
    @property
    def revisar(self) -> bool:
        return revision_posterior_a_aprobacion(self.fecha_ultima_revision, self.fecha_aprobacion)

    class Config:
        from_attributes = True
class PiezaPlanoWrite(BaseModel):
    codigo_plano: Optional[str] = None
    version: Optional[str] = "V-01"
    detalle_pieza: Optional[str] = None
    cantidad: Optional[int] = 1
    material_requerido: Optional[str] = None
    codigo_material: Optional[str] = None
    cantidad_material: Optional[float] = None
    unidad_medida: Optional[str] = "UND"
    archivo_pdf_url: Optional[str] = None
    archivo_step_url: Optional[str] = None
    archivo_dxf_url: Optional[str] = None


class PlanoWriteRequest(BaseModel):
    id_proyecto: UUID
    codigo_op: str
    codigo_plano: Optional[str] = None
    version: Optional[str] = "V-01"
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = "Mecanizados"
    estado_diseno: Optional[str] = "PLANIFICADA"
    causa_espera: Optional[str] = None
    material_requerido: Optional[str] = None
    archivo_pdf_url: Optional[str] = None
    archivo_step_url: Optional[str] = None
    archivo_dxf_url: Optional[str] = None
    piezas: List[PiezaPlanoWrite] = Field(default_factory=list)


class PlanoUpdateRequest(BaseModel):
    estado_diseno: Optional[str] = None
    causa_espera: Optional[str] = None
    archivo_pdf_url: Optional[str] = None
    archivo_step_url: Optional[str] = None
    archivo_dxf_url: Optional[str] = None
    material_requerido: Optional[str] = None
    version: Optional[str] = None
    dibujante_asignado: Optional[str] = None
    unidad_planta: Optional[str] = None
    observaciones_tecnicas: Optional[str] = None
    piezas: Optional[List[PiezaPlanoWrite]] = None
    # Obligatoria (mínimo 10 caracteres) cuando cambia la versión
    justificacion: Optional[str] = None


class JustificacionPlanoRequest(BaseModel):
    """Cuerpo de la revisión (justificación obligatoria) y de la aprobación (opcional)."""
    justificacion: Optional[str] = None


class TokenPlanoResponse(BaseModel):
    token_temporal: str
    url_acceso_temporal: str
    expira_en_minutos: int = 15


# =============================================================================
# HELPER TOKEN TEMPORAL TTL
# =============================================================================

def generar_token_plano_ttl(id_plano: UUID, ttl_minutos: int = 15) -> str:
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutos)
    payload = {
        "sub": str(id_plano),
        "exp": expiracion,
        "type": "plano_temp_access"
    }
    return jwt.encode(payload, SECRET_KEY_PLANOS, algorithm=ALGORITHM)


# =============================================================================
# ENDPOINTS GESTIÓN Y SERVIDO DE PLANOS CON TOKENS TTL
# =============================================================================

@router.get("/", response_model=List[PlanoResponse])
def listar_planos(
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual),
):
    return db.query(Plano).options(
        joinedload(Plano.bom_items)
    ).order_by(Plano.creado_en.desc()).all()


def _datos_pieza(plano_in: PlanoWriteRequest, pieza: PiezaPlanoWrite):
    codigo_material = (pieza.codigo_material or pieza.material_requerido or plano_in.material_requerido or "").strip()
    descripcion = (pieza.material_requerido or plano_in.material_requerido or codigo_material).strip()
    return {
        "codigo_material": codigo_material[:50],
        "descripcion": descripcion[:200],
        "cantidad_requerida": pieza.cantidad_material if pieza.cantidad_material is not None else 1.0,
        "unidad_medida": pieza.unidad_medida or "UND",
    }


@router.post("/", response_model=List[PlanoResponse], status_code=status.HTTP_201_CREATED)
def crear_planos(
    plano_in: PlanoWriteRequest,
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual),
):
    proyecto = db.query(Proyecto).filter(Proyecto.id_proyecto == plano_in.id_proyecto).first()
    if not proyecto:
        raise HTTPException(status_code=404, detail="El proyecto asociado al plano no existe.")

    # Sin piezas: un solo plano con los datos de la cabecera (campos de PlanoWriteRequest)
    piezas = plano_in.piezas or [
        PiezaPlanoWrite(
            codigo_plano=plano_in.codigo_plano,
            version=plano_in.version,
            material_requerido=plano_in.material_requerido,
            archivo_pdf_url=plano_in.archivo_pdf_url,
            archivo_step_url=plano_in.archivo_step_url,
            archivo_dxf_url=plano_in.archivo_dxf_url,
        )
    ]
    # Archivos referenciados por ruta: se validan todos antes de escribir y se registran con
    # sha256 y tamaño en planos_archivos y en el historial, igual que una primera carga
    archivos_por_pieza = [
        {
            tipo: _archivo_almacenado(tipo, url)
            for tipo, (campo, _, _) in FORMATOS_CAD.items()
            if (url := getattr(pieza, campo) or getattr(plano_in, campo))
        }
        for pieza in piezas
    ]
    planos_creados = []
    try:
        for pieza, archivos in zip(piezas, archivos_por_pieza):
            plano = Plano(
                id_proyecto=proyecto.id_proyecto,
                codigo_op=plano_in.codigo_op,
                codigo_plano=pieza.codigo_plano or plano_in.codigo_plano or plano_in.codigo_op,
                version=pieza.version or plano_in.version or "V-01",
                dibujante_asignado=plano_in.dibujante_asignado,
                unidad_planta=plano_in.unidad_planta,
                estado_diseno=plano_in.estado_diseno or "PLANIFICADA",
                causa_espera=plano_in.causa_espera,
                material_requerido=pieza.material_requerido or plano_in.material_requerido,
            )
            db.add(plano)
            db.flush()
            registrar_evento_plano(db, plano, "CREACION", usuario_actual["email"])
            for tipo, archivo in archivos.items():
                db.add(PlanoArchivo(
                    id_plano=plano.id_plano,
                    tipo=tipo.upper(),
                    ruta=archivo["ruta"],
                    nombre_original=archivo["nombre"][:255],
                    tamano_bytes=archivo["tamano_bytes"],
                    sha256=archivo["sha256"],
                    revision=plano.version,
                    vigente=True,
                    subido_por=usuario_actual["email"],
                ))
                setattr(plano, FORMATOS_CAD[tipo][0], archivo["ruta"])
                registrar_evento_plano(
                    db, plano, "CARGA_ARCHIVO", usuario_actual["email"],
                    tipo_archivo=tipo.upper(), sha256=archivo["sha256"],
                )
            db.flush()
            datos_bom = _datos_pieza(plano_in, pieza)
            if datos_bom["codigo_material"]:
                db.add(BOMListaMateriales(
                    plano_id=plano.id_plano,
                    estado_abastecimiento="SIN_SOLICITAR",
                    **datos_bom,
                ))
                db.flush()
            if plano.estado_diseno == "LISTA_PARA_LIBERAR":
                validar_entrega_diseno(db, plano)
            elif plano.estado_diseno == "LIBERADA":
                validar_liberacion_op(db, [plano])
            planos_creados.append(plano)
        db.commit()
        for plano in planos_creados:
            db.refresh(plano)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudieron guardar los planos.") from error
    return planos_creados


@router.patch("/{id_plano}", response_model=PlanoResponse)
def actualizar_plano(
    id_plano: UUID,
    plano_in: PlanoUpdateRequest,
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual),
):
    plano = db.query(Plano).options(joinedload(Plano.bom_items)).filter(
        Plano.id_plano == id_plano
    ).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Plano no encontrado.")

    # Los archivos no se editan aquí: solo con las rutas de carga (hash, planos_archivos e historial)
    campos_editables = {
        "estado_diseno",
        "causa_espera",
        "material_requerido",
        "version",
        "dibujante_asignado",
        "unidad_planta",
        "observaciones_tecnicas",
    }
    estado_anterior = plano.estado_diseno
    estado_nuevo = plano_in.estado_diseno
    if estado_nuevo and estado_nuevo != estado_anterior:
        if estado_nuevo == "PAUSADA" and estado_anterior != "EN_DISENO":
            raise HTTPException(status_code=400, detail="Solo se puede pausar una orden EN_DISENO.")
        if estado_anterior == "PAUSADA" and estado_nuevo not in {"EN_DISENO", "LISTA_PARA_LIBERAR"}:
            raise HTTPException(status_code=400, detail="Una orden PAUSADA solo puede reanudarse o entregarse.")
    datos_actualizacion = plano_in.dict(exclude_unset=True)
    # 422 antes de escribir: un archivo distinto del actual o una versión nueva sin justificación.
    # El mismo valor que ya tiene el plano se acepta (la mesa de Diseño reenvía el plano completo).
    archivos_cambiados = [
        campo for campo in CAMPOS_ARCHIVO
        if campo in datos_actualizacion and (datos_actualizacion[campo] or None) != (getattr(plano, campo) or None)
    ]
    if archivos_cambiados:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Los archivos del plano ({', '.join(archivos_cambiados)}) no se cambian con PATCH: "
                "use la carga de archivos POST /planos/upload-cad/{id_plano}/{tipo}."
            ),
        )
    version_anterior = plano.version
    version_nueva = datos_actualizacion.get("version")
    cambio_version = bool(version_nueva) and version_nueva != version_anterior
    texto_justificacion = exigir_justificacion(plano_in.justificacion) if cambio_version else None
    for campo in campos_editables:
        if campo in datos_actualizacion:
            setattr(plano, campo, datos_actualizacion[campo])

    piezas = plano_in.piezas or []
    if piezas:
        pieza = piezas[0]
        datos_bom = {
            "codigo_material": str(pieza.codigo_material or pieza.material_requerido or plano.material_requerido or "").strip()[:50],
            "descripcion": str(pieza.material_requerido or plano.material_requerido or "").strip()[:200],
            "cantidad_requerida": pieza.cantidad_material or 1,
            "unidad_medida": pieza.unidad_medida or "UND",
        }
        if datos_bom["codigo_material"]:
            if plano.bom_items:
                item = plano.bom_items[0]
                if (
                    item.codigo_material != datos_bom["codigo_material"]
                    or item.descripcion != datos_bom["descripcion"]
                ):
                    item.estado_abastecimiento = "SIN_SOLICITAR"
                for campo, valor in datos_bom.items():
                    setattr(item, campo, valor)
            else:
                db.add(BOMListaMateriales(
                    plano_id=plano.id_plano,
                    estado_abastecimiento="SIN_SOLICITAR",
                    **datos_bom,
                ))
    try:
        db.flush()
        # Entrega de Diseño: compuerta de entrega; plano LIBERADA: compuerta de liberación
        if plano.estado_diseno != estado_anterior and plano.estado_diseno == "LISTA_PARA_LIBERAR":
            validar_entrega_diseno(db, plano)
        elif plano.estado_diseno != estado_anterior and plano.estado_diseno == "LIBERADA":
            validar_liberacion_op(db, [plano])

        # Cronómetro de diseño: una sola OP EN_DISENO por dibujante; iniciar otra pausa la anterior
        ahora = datetime.now(timezone.utc)
        if plano.estado_diseno == "EN_DISENO" and estado_anterior != "EN_DISENO":
            dibujante = _nombre_base_dibujante(plano.dibujante_asignado)
            if dibujante:
                ordenes_activas = db.query(Plano).filter(
                    Plano.estado_diseno == "EN_DISENO",
                    Plano.id_plano != plano.id_plano,
                ).all()
                for orden_activa in ordenes_activas:
                    if _nombre_base_dibujante(orden_activa.dibujante_asignado) != dibujante:
                        continue
                    _detener_cronometro_diseno(orden_activa, ahora)
                    orden_activa.estado_diseno = "PAUSADA"
                    registrar_evento_plano(db, orden_activa, "CAMBIO_ESTADO", usuario_actual["email"])
            if estado_anterior == "PAUSADA" or not plano.fecha_inicio_diseno:
                _reanudar_cronometro_diseno(plano, ahora)
        if estado_anterior == "EN_DISENO" and plano.estado_diseno in ESTADOS_ENTREGA_DISENO | {"PAUSADA"}:
            _detener_cronometro_diseno(plano, ahora)

        # Historial (migración 21); la versión nueva cuenta como revisión del plano
        if cambio_version:
            plano.fecha_ultima_revision = ahora
            registrar_evento_plano(
                db, plano, "CAMBIO_VERSION", usuario_actual["email"],
                version_anterior=version_anterior, justificacion=texto_justificacion,
            )
        if plano.estado_diseno != estado_anterior:
            registrar_evento_plano(db, plano, "CAMBIO_ESTADO", usuario_actual["email"])
        db.commit()
        db.refresh(plano)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo actualizar el plano.") from error
    return plano


@router.post("/{id_plano}/aprobar", response_model=PlanoResponse)
def aprobar_plano(
    id_plano: UUID,
    datos: Optional[JustificacionPlanoRequest] = None,
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(requerir_roles(ROLES_APROBAR_PLANO)),
):
    """Aprobación de Diseño: condición 3 de la regla de liberación de la OP.
    La justificación es opcional y queda en el historial del plano."""
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano no encontrado.")

    estado_anterior = plano.estado.value if hasattr(plano.estado, "value") else plano.estado
    plano.estado = EstadoPlanoEnum.APROBADO
    plano.aprobado_por = usuario_actual["email"]
    plano.fecha_aprobacion = datetime.now(timezone.utc)
    try:
        registrar_evento_plano(
            db, plano, "APROBACION", usuario_actual["email"],
            justificacion=justificacion_opcional(datos.justificacion if datos else None),
        )
        agregar_evento_trazabilidad(
            db,
            tipo_entidad="PLANO",
            identificador=plano.codigo_plano,
            accion="PLANO_APROBADO",
            usuario=usuario_actual["email"],
            area=usuario_actual["rol"],
            estado_anterior=str(estado_anterior) if estado_anterior else None,
            estado_nuevo=EstadoPlanoEnum.APROBADO.value,
        )
        db.commit()
        db.refresh(plano)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo aprobar el plano.") from error
    return plano


@router.get("/{id_plano}/historial")
def obtener_historial_plano(
    id_plano: UUID,
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual),
):
    """Línea de tiempo append-only del plano (migración 21), en orden cronológico."""
    if not db.query(Plano.id_plano).filter(Plano.id_plano == id_plano).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano no encontrado.")
    return historial_por_plano(db, [id_plano]).get(id_plano, [])


@router.post("/{id_plano}/revision", response_model=PlanoResponse)
def registrar_revision_plano(
    id_plano: UUID,
    datos: Optional[JustificacionPlanoRequest] = None,
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(requerir_roles(ROLES_REVISION_PLANO)),
):
    """Revisión de Diseño sin cambio de versión: exige justificación y fija
    fecha_ultima_revision, de modo que un plano ya aprobado queda marcado como Revisar."""
    texto_justificacion = exigir_justificacion(datos.justificacion if datos else None)
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano no encontrado.")

    plano.fecha_ultima_revision = datetime.now(timezone.utc)
    try:
        registrar_evento_plano(db, plano, "REVISION", usuario_actual["email"], justificacion=texto_justificacion)
        db.commit()
        db.refresh(plano)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo registrar la revisión del plano.") from error
    return plano


@router.get("/token/{id_plano}", response_model=TokenPlanoResponse)
def obtener_token_temporal_plano(
    id_plano: UUID,
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual),
):
    """
    Genera un token de acceso temporal firmado con TTL de 15 minutos para visualizar el plano PDF.
    """
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano or not plano.archivo_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plano no encontrado o no posee un archivo PDF cargado."
        )

    token = generar_token_plano_ttl(id_plano, ttl_minutos=15)
    url_acceso = f"/api/v1/planos/visor-seguro?token={token}"

    return TokenPlanoResponse(
        token_temporal=token,
        url_acceso_temporal=url_acceso,
        expira_en_minutos=15
    )


@router.get("/visor-seguro")
def servir_plano_pdf_seguro(token: str, db: Session = Depends(get_db)):
    """
    Valida la firma y vigencia TTL del token para servir el archivo PDF congelado.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY_PLANOS, algorithms=[ALGORITHM])
        id_plano_str = payload.get("sub")
        if not id_plano_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no válido.")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="❌ El token de acceso al plano ha expirado.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token alterado o no válido.")

    plano = db.query(Plano).filter(Plano.id_plano == UUID(id_plano_str)).first()
    if not plano or not plano.archivo_pdf_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo PDF no encontrado."
        )

    nombre_archivo = os.path.basename(plano.archivo_pdf_url)
    ruta_fisica = os.path.join(DIRECTORIO_STATIC_PLANOS, nombre_archivo)

    if not os.path.exists(ruta_fisica):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El archivo físico PDF no existe en el almacenamiento.")

    # inline: el visor modal (iframe) muestra el PDF en lugar de forzar la descarga
    return FileResponse(
        ruta_fisica,
        media_type="application/pdf",
        filename=nombre_archivo,
        content_disposition_type="inline",
    )


@router.post("/upload-pdf/{id_plano}", response_model=PlanoResponse)
def subir_pdf_plano(
    id_plano: UUID,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual),
    justificacion: Optional[str] = Form(None),
):
    """Carga por extensión: acepta PDF, STEP y DXF (la mesa de Diseño envía aquí los tres)."""
    tipo = _tipo_por_extension(archivo.filename)
    plano = _obtener_plano_para_carga(db, id_plano)
    return _guardar_archivo_cad(db, plano, archivo, tipo, usuario_actual, justificacion)

@router.post("/upload-cad/{id_plano}", response_model=PlanoResponse)
def subir_cad_plano(
    id_plano: UUID,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual),
    justificacion: Optional[str] = Form(None),
):
    """Carga por extensión: .pdf, .step/.stp o .dxf."""
    tipo = _tipo_por_extension(archivo.filename)
    plano = _obtener_plano_para_carga(db, id_plano)
    return _guardar_archivo_cad(db, plano, archivo, tipo, usuario_actual, justificacion)

@router.post("/upload-cad/{id_plano}/{tipo}", response_model=PlanoResponse)
def subir_archivo_cad_por_tipo(
    id_plano: UUID,
    tipo: str,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual),
    justificacion: Optional[str] = Form(None),
):
    """Carga multiformato: tipo = pdf | step | dxf (.pdf, .step/.stp, .dxf).
    justificacion (Form): obligatoria al reemplazar el archivo vigente por otro contenido."""
    plano = _obtener_plano_para_carga(db, id_plano)
    return _guardar_archivo_cad(db, plano, archivo, tipo.lower(), usuario_actual, justificacion)

@router.get("/descargar-cad/{id_plano}/{tipo}")
def descargar_cad_plano(
    id_plano: UUID,
    tipo: str,
    db: Session = Depends(get_db),
    usuario_actual: dict = Depends(obtener_usuario_actual),
):
    """
    Descarga de archivos CAD (.step o .dxf).
    tipos: 'step', 'dxf'
    Sirve solo el archivo vigente de planos_archivos; las columnas archivo_step_url y
    archivo_dxf_url no se usan como respaldo.
    """
    plano = db.query(Plano).filter(Plano.id_plano == id_plano).first()
    if not plano:
        raise HTTPException(status_code=404, detail="Plano no encontrado.")

    tipo = tipo.lower()
    if tipo not in {"step", "dxf"}:
        raise HTTPException(status_code=400, detail="Tipo de descarga inválido. Use step o dxf.")

    vigente = db.query(PlanoArchivo).filter(
        PlanoArchivo.id_plano == plano.id_plano,
        PlanoArchivo.tipo == tipo.upper(),
        PlanoArchivo.vigente.is_(True),
    ).first()
    if not vigente:
        raise HTTPException(status_code=404, detail=f"El plano no tiene un archivo {tipo.upper()} vigente.")

    ruta_fisica = ruta_fisica_archivo(vigente.ruta)
    if not os.path.isfile(ruta_fisica):
        raise HTTPException(status_code=404, detail="Archivo físico no encontrado.")

    return FileResponse(ruta_fisica, filename=vigente.nombre_original or os.path.basename(ruta_fisica))
