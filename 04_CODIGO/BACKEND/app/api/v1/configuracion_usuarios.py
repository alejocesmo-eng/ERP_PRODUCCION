# app/api/v1/configuracion_usuarios.py
"""
Administración de usuarios desde Configuración (34_MIGRACION_ACCESO_POR_USUARIO.sql,
reglas/acceso-por-usuario.md del proyecto PRISMA).

- Solo entra quien entra a Configuración de roles: ADMIN con PERM_CONFIGURACION_ROLES, rol leído
  de la base en cada consulta. Cualquier otro rol recibe 403.
- Crear usuarios, editar sus datos (incluido el usuario), asignarles rol y contraseña, desactivarlos
  y reactivarlos. "Eliminar" desactiva: la fila no se borra.
- El usuario sugerido es primer nombre.primer apellido y, si existe, con un número (juan.perez2);
  ADMIN puede escribir otro. El correo es opcional y único cuando tiene valor.
- La contraseña la asigna ADMIN y es definitiva: no se fuerza cambio al entrar.
- Cada cambio queda en usuarios_historial con el id_usuario de quien lo hizo; nunca la contraseña.
- ADMIN no puede desactivarse ni quitarse el rol ADMIN a sí mismo (se quedaría sin Configuración).
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.configuracion_roles import requerir_configuracion
from app.core import roles
from app.core.security import get_password_hash
from app.db.database import get_db
from app.db.models import Rol, Usuario, UsuarioHistorial
from app.services.usuarios import (
    MENSAJE_FORMATO, a_uuid, con_usuarios, normalizar_usuario, sugerir_usuario, usuario_valido,
)

router = APIRouter()

# bcrypt solo usa los primeros 72 bytes
LONGITUD_MINIMA_CLAVE = 8
LONGITUD_MAXIMA_CLAVE = 72
FORMATO_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UsuarioCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombres: str = Field(..., min_length=1, max_length=75)
    apellidos: str = Field(..., min_length=1, max_length=74)
    # Sin usuario se usa el sugerido
    usuario: Optional[str] = None
    email: Optional[str] = None
    id_rol: str
    clave: str


class UsuarioEditar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: Optional[str] = None
    nombre_completo: Optional[str] = Field(None, min_length=1, max_length=150)
    # "" quita el correo
    email: Optional[str] = None
    id_rol: Optional[str] = None


class ClaveUsuario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clave: str


def _cuenta(db: Session, id_usuario: str) -> Usuario:
    identificador = a_uuid(id_usuario)
    cuenta = db.query(Usuario).filter(Usuario.id_usuario == identificador).first() if identificador else None
    if not cuenta:
        raise HTTPException(status_code=404, detail="No existe el usuario indicado.")
    return cuenta


def _usuario_libre(db: Session, texto: str, excepto=None) -> str:
    usuario = normalizar_usuario(texto)
    if not usuario_valido(usuario):
        raise HTTPException(status_code=422, detail=MENSAJE_FORMATO)
    consulta = db.query(Usuario.id_usuario).filter(Usuario.usuario == usuario)
    if excepto is not None:
        consulta = consulta.filter(Usuario.id_usuario != excepto)
    if consulta.first():
        raise HTTPException(status_code=409, detail=f"El usuario {usuario} ya existe.")
    return usuario


def _correo_libre(db: Session, texto: Optional[str], excepto=None) -> Optional[str]:
    correo = (texto or "").strip().lower() or None
    if correo is None:
        return None
    if not FORMATO_CORREO.match(correo) or len(correo) > 100:
        raise HTTPException(status_code=422, detail="El correo no es válido.")
    consulta = db.query(Usuario.id_usuario).filter(Usuario.email == correo)
    if excepto is not None:
        consulta = consulta.filter(Usuario.id_usuario != excepto)
    if consulta.first():
        raise HTTPException(status_code=409, detail="Ese correo ya está en otra cuenta.")
    return correo


def _rol_existente(db: Session, id_rol: str) -> str:
    if not db.query(Rol.id_rol).filter(Rol.id_rol == id_rol).first():
        raise HTTPException(status_code=422, detail="El rol indicado no existe.")
    return id_rol


def _hash_clave(clave: str) -> str:
    if not LONGITUD_MINIMA_CLAVE <= len(clave.encode("utf-8")) <= LONGITUD_MAXIMA_CLAVE:
        raise HTTPException(
            status_code=422,
            detail=f"La contraseña debe tener de {LONGITUD_MINIMA_CLAVE} a {LONGITUD_MAXIMA_CLAVE} caracteres.",
        )
    return get_password_hash(clave)


def _auditar(db: Session, cuenta: Usuario, accion: str, quien: dict, cambios: Optional[dict] = None) -> None:
    db.add(UsuarioHistorial(id_usuario=cuenta.id_usuario, accion=accion, cambios=cambios or {},
                            realizado_por=quien["id_usuario"]))


def _confirmar(db: Session, mensaje: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=mensaje) from error


def _es_quien_configura(cuenta: Usuario, quien: dict) -> bool:
    return str(cuenta.id_usuario) == str(a_uuid(quien["id_usuario"]))


def _salida(cuenta: Usuario, nombres_rol: dict) -> dict:
    return {
        "id_usuario": str(cuenta.id_usuario),
        "usuario": cuenta.usuario,
        "nombre_completo": cuenta.nombre_completo,
        "email": cuenta.email,
        "id_rol": cuenta.id_rol,
        "nombre_rol": nombres_rol.get(cuenta.id_rol),
        "activo": cuenta.activo is not False,
        "creado_en": cuenta.creado_en.isoformat() if cuenta.creado_en else None,
    }


def _nombres_rol(db: Session) -> dict:
    return dict(db.query(Rol.id_rol, Rol.nombre_rol).all())


@router.get("")
def listar_usuarios(_: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    nombres_rol = _nombres_rol(db)
    return [_salida(cuenta, nombres_rol) for cuenta in db.query(Usuario).order_by(Usuario.usuario).all()]


@router.get("/sugerencia")
def sugerir(
    nombres: str = Query(..., min_length=1),
    apellidos: str = Query(..., min_length=1),
    _: dict = Depends(requerir_configuracion),
    db: Session = Depends(get_db),
):
    return {"usuario": sugerir_usuario(db, nombres, apellidos)}


@router.post("", status_code=status.HTTP_201_CREATED)
def crear_usuario(datos: UsuarioCrear, quien: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    if datos.usuario and datos.usuario.strip():
        usuario = _usuario_libre(db, datos.usuario)
    else:
        usuario = sugerir_usuario(db, datos.nombres, datos.apellidos)
        if not usuario:
            raise HTTPException(status_code=422, detail="No se pudo sugerir un usuario con esos nombres; escríbalo.")
    cuenta = Usuario(
        usuario=usuario,
        nombre_completo=f"{datos.nombres.strip()} {datos.apellidos.strip()}",
        email=_correo_libre(db, datos.email),
        id_rol=_rol_existente(db, datos.id_rol),
        password_hash=_hash_clave(datos.clave),
        activo=True,
    )
    db.add(cuenta)
    db.flush()
    _auditar(db, cuenta, "CREADO", quien, {
        "usuario": cuenta.usuario, "nombre_completo": cuenta.nombre_completo, "email": cuenta.email,
        "id_rol": cuenta.id_rol,
    })
    _confirmar(db, "No se pudo crear el usuario.")
    return _salida(cuenta, _nombres_rol(db))


@router.patch("/{id_usuario}")
def editar_usuario(
    id_usuario: str, datos: UsuarioEditar, quien: dict = Depends(requerir_configuracion), db: Session = Depends(get_db),
):
    cuenta = _cuenta(db, id_usuario)
    enviados = datos.model_dump(exclude_unset=True)
    nuevos = {}
    if "usuario" in enviados:
        nuevos["usuario"] = _usuario_libre(db, datos.usuario or "", excepto=cuenta.id_usuario)
    if "nombre_completo" in enviados:
        nombre = (datos.nombre_completo or "").strip()
        if not nombre:
            raise HTTPException(status_code=422, detail="El nombre es obligatorio.")
        nuevos["nombre_completo"] = nombre
    if "email" in enviados:
        nuevos["email"] = _correo_libre(db, datos.email, excepto=cuenta.id_usuario)
    if "id_rol" in enviados:
        nuevos["id_rol"] = _rol_existente(db, datos.id_rol or "")
        if _es_quien_configura(cuenta, quien) and nuevos["id_rol"] != roles.ADMIN:
            raise HTTPException(status_code=409, detail="No puede quitarse el rol ADMIN a sí mismo.")

    cambios = {
        campo: {"antes": getattr(cuenta, campo), "despues": valor}
        for campo, valor in nuevos.items() if getattr(cuenta, campo) != valor
    }
    if not cambios:
        return _salida(cuenta, _nombres_rol(db))
    for campo, cambio in cambios.items():
        setattr(cuenta, campo, cambio["despues"])
    rol = cambios.pop("id_rol", None)
    if cambios:
        _auditar(db, cuenta, "EDITADO", quien, cambios)
    if rol:
        _auditar(db, cuenta, "ROL_ASIGNADO", quien, {"id_rol": rol})
    _confirmar(db, "No se pudo guardar el usuario.")
    return _salida(cuenta, _nombres_rol(db))


@router.put("/{id_usuario}/clave", status_code=status.HTTP_204_NO_CONTENT)
def asignar_clave(
    id_usuario: str, datos: ClaveUsuario, quien: dict = Depends(requerir_configuracion), db: Session = Depends(get_db),
):
    cuenta = _cuenta(db, id_usuario)
    cuenta.password_hash = _hash_clave(datos.clave)
    _auditar(db, cuenta, "CLAVE_ASIGNADA", quien)
    _confirmar(db, "No se pudo asignar la contraseña.")


def _cambiar_activo(db: Session, id_usuario: str, quien: dict, activo: bool) -> dict:
    cuenta = _cuenta(db, id_usuario)
    if not activo and _es_quien_configura(cuenta, quien):
        raise HTTPException(status_code=409, detail="No puede desactivar su propia cuenta.")
    if (cuenta.activo is not False) != activo:
        cuenta.activo = activo
        _auditar(db, cuenta, "REACTIVADO" if activo else "DESACTIVADO", quien)
        _confirmar(db, "No se pudo cambiar el estado del usuario.")
    return _salida(cuenta, _nombres_rol(db))


@router.post("/{id_usuario}/desactivar")
def desactivar_usuario(id_usuario: str, quien: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    return _cambiar_activo(db, id_usuario, quien, False)


@router.post("/{id_usuario}/reactivar")
def reactivar_usuario(id_usuario: str, quien: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    return _cambiar_activo(db, id_usuario, quien, True)


@router.get("/{id_usuario}/historial")
def historial_usuario(id_usuario: str, _: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    cuenta = _cuenta(db, id_usuario)
    filas = (
        db.query(UsuarioHistorial).filter(UsuarioHistorial.id_usuario == cuenta.id_usuario)
        .order_by(UsuarioHistorial.registrado_en.desc(), UsuarioHistorial.id_historial.desc()).all()
    )
    return con_usuarios(db, [{
        "accion": fila.accion,
        "cambios": fila.cambios,
        "realizado_por": fila.realizado_por,
        "registrado_en": fila.registrado_en.isoformat() if fila.registrado_en else None,
    } for fila in filas], "realizado_por")
