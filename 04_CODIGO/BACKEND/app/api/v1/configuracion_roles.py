# app/api/v1/configuracion_roles.py
"""
Configuración de roles y permisos (migración 31).

- Solo entra ADMIN, con el rol leído de la base en cada consulta (no el del token), y solo si su
  rol tiene PERM_CONFIGURACION_ROLES. Cualquier otro rol recibe 403.
- Los roles se crean con nombre de negocio y código técnico (mayúsculas, sin espacios). El código
  no se repite ni se cambia después.
- Los permisos se eligen de la tabla permisos, que solo llenan las migraciones: aquí no se crea
  ninguno. Cada permiso asignado o retirado queda en rol_permisos_historial con quién y cuándo.
- Los permisos se consultan en rol_permisos en cada petición, así que los cambios aplican sin
  reiniciar la aplicación.
- ADMIN no puede quitarse PERM_CONFIGURACION_ROLES, y un rol con usuarios no se elimina.
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual, rol_tiene_permiso
from app.core import roles
from app.db.database import get_db
from app.db.models import Permiso, Rol, RolPermiso, RolPermisoHistorial, Usuario
from app.services.acceso_bd import rol_en_bd

PERMISO_CONFIGURACION = "PERM_CONFIGURACION_ROLES"
CODIGO_ROL = re.compile(r"^[A-Z][A-Z0-9_]{1,49}$")

router = APIRouter()


def puede_configurar(db: Session, email: str) -> Optional[str]:
    """Rol de la base si puede entrar a Configuración; None si no."""
    rol = rol_en_bd(db, email)
    if rol == roles.ADMIN and rol_tiene_permiso(db, rol, PERMISO_CONFIGURACION):
        return rol
    return None


def requerir_configuracion(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)) -> dict:
    rol = puede_configurar(db, usuario["email"])
    if not rol:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo ADMIN entra a Configuración de roles.")
    return {**usuario, "rol": rol}


class RolCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_rol: str = Field(..., description="Código técnico: mayúsculas, dígitos y guion bajo, sin espacios")
    nombre_rol: str = Field(..., min_length=1, max_length=100)
    descripcion: Optional[str] = None

    @field_validator("id_rol")
    @classmethod
    def _codigo(cls, valor: str) -> str:
        if not CODIGO_ROL.match(valor):
            raise ValueError("El código debe ir en mayúsculas, sin espacios, con letras, dígitos o guion bajo (2 a 50).")
        return valor

    @field_validator("nombre_rol")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("El nombre del rol es obligatorio.")
        return valor.strip()


class RolEditar(BaseModel):
    # Sin id_rol: el código no se cambia después de crearlo (extra="forbid" lo rechaza con 422)
    model_config = ConfigDict(extra="forbid")

    nombre_rol: Optional[str] = Field(None, min_length=1, max_length=100)
    descripcion: Optional[str] = None


class PermisosRol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permisos: list[str]


def _rol(db: Session, id_rol: str) -> Rol:
    rol = db.query(Rol).filter(Rol.id_rol == id_rol).first()
    if not rol:
        raise HTTPException(status_code=404, detail="No existe el rol indicado.")
    return rol


def _permisos_por_rol(db: Session) -> dict[str, list[str]]:
    resultado: dict[str, list[str]] = {}
    for fila in db.query(RolPermiso).order_by(RolPermiso.id_permiso).all():
        resultado.setdefault(fila.id_rol, []).append(fila.id_permiso)
    return resultado


def _usuarios_por_rol(db: Session) -> dict[str, int]:
    return dict(db.query(Usuario.id_rol, func.count(Usuario.id_usuario)).group_by(Usuario.id_rol).all())


def _salida_rol(rol: Rol, permisos: list[str], usuarios: int) -> dict:
    return {
        "id_rol": rol.id_rol,
        "nombre_rol": rol.nombre_rol,
        "descripcion": rol.descripcion,
        "permisos": permisos,
        "usuarios": usuarios,
    }


@router.get("/acceso")
def acceso(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    """Si el usuario ve Configuración en el menú. No responde 403: el menú solo lo oculta."""
    return {"acceso": puede_configurar(db, usuario["email"]) is not None}


@router.get("/")
def listar_roles(_: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    permisos = _permisos_por_rol(db)
    usuarios = _usuarios_por_rol(db)
    return [
        _salida_rol(rol, permisos.get(rol.id_rol, []), usuarios.get(rol.id_rol, 0))
        for rol in db.query(Rol).order_by(Rol.id_rol).all()
    ]


@router.get("/permisos")
def catalogo_permisos(_: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    """Catálogo de permisos (lo llenan las migraciones). Solo lectura."""
    return [
        {"id_permiso": p.id_permiso, "modulo": p.modulo, "descripcion": p.descripcion}
        for p in db.query(Permiso).order_by(Permiso.modulo, Permiso.id_permiso).all()
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_rol(datos: RolCrear, _: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    if db.query(Rol).filter(Rol.id_rol == datos.id_rol).first():
        raise HTTPException(status_code=409, detail=f"Ya existe un rol con el código {datos.id_rol}.")
    rol = Rol(id_rol=datos.id_rol, nombre_rol=datos.nombre_rol, descripcion=datos.descripcion)
    db.add(rol)
    db.commit()
    return _salida_rol(rol, [], 0)


@router.patch("/{id_rol}")
def editar_rol(id_rol: str, datos: RolEditar, _: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    rol = _rol(db, id_rol)
    cambios = datos.model_dump(exclude_unset=True)
    if "nombre_rol" in cambios:
        nombre = (cambios["nombre_rol"] or "").strip()
        if not nombre:
            raise HTTPException(status_code=400, detail="El nombre del rol es obligatorio.")
        rol.nombre_rol = nombre
    if "descripcion" in cambios:
        rol.descripcion = cambios["descripcion"]
    db.commit()
    return _salida_rol(rol, _permisos_por_rol(db).get(id_rol, []), _usuarios_por_rol(db).get(id_rol, 0))


@router.put("/{id_rol}/permisos")
def asignar_permisos(
    id_rol: str,
    datos: PermisosRol,
    usuario: dict = Depends(requerir_configuracion),
    db: Session = Depends(get_db),
):
    """Deja al rol exactamente con los permisos indicados y registra cada alta y baja."""
    rol = _rol(db, id_rol)
    nuevos = set(datos.permisos)
    existentes = {p for (p,) in db.query(Permiso.id_permiso).filter(Permiso.id_permiso.in_(nuevos)).all()} if nuevos else set()
    desconocidos = sorted(nuevos - existentes)
    if desconocidos:
        raise HTTPException(
            status_code=400,
            detail=f"Permisos fuera del catálogo (aquí no se crean permisos): {', '.join(desconocidos)}",
        )
    if PERMISO_CONFIGURACION in nuevos and id_rol != roles.ADMIN:
        raise HTTPException(status_code=400, detail="El acceso a Configuración es solo de ADMIN.")
    if id_rol == usuario["rol"] and PERMISO_CONFIGURACION not in nuevos:
        raise HTTPException(status_code=409, detail="No puede quitarse a sí mismo el acceso a Configuración.")

    actuales = {p for (p,) in db.query(RolPermiso.id_permiso).filter(RolPermiso.id_rol == id_rol).all()}
    asignados, retirados = sorted(nuevos - actuales), sorted(actuales - nuevos)
    if retirados:
        db.query(RolPermiso).filter(RolPermiso.id_rol == id_rol, RolPermiso.id_permiso.in_(retirados)).delete(
            synchronize_session=False
        )
    db.add_all(RolPermiso(id_rol=id_rol, id_permiso=p) for p in asignados)
    db.add_all(
        RolPermisoHistorial(id_rol=id_rol, id_permiso=p, accion=accion, usuario_email=usuario["email"])
        for accion, lista in (("ASIGNADO", asignados), ("RETIRADO", retirados))
        for p in lista
    )
    db.commit()
    return {
        **_salida_rol(rol, sorted(nuevos), _usuarios_por_rol(db).get(id_rol, 0)),
        "asignados": asignados,
        "retirados": retirados,
    }


@router.get("/{id_rol}/historial")
def historial_permisos(id_rol: str, _: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    filas = (
        db.query(RolPermisoHistorial)
        .filter(RolPermisoHistorial.id_rol == id_rol)
        .order_by(RolPermisoHistorial.registrado_en.desc(), RolPermisoHistorial.id.desc())
        .all()
    )
    return [
        {
            "id_permiso": f.id_permiso,
            "accion": f.accion,
            "usuario_email": f.usuario_email,
            "registrado_en": f.registrado_en.isoformat() if f.registrado_en else None,
        }
        for f in filas
    ]


@router.delete("/{id_rol}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_rol(id_rol: str, usuario: dict = Depends(requerir_configuracion), db: Session = Depends(get_db)):
    rol = _rol(db, id_rol)
    con_usuarios = db.query(func.count(Usuario.id_usuario)).filter(Usuario.id_rol == id_rol).scalar()
    if con_usuarios:
        raise HTTPException(
            status_code=409,
            detail=f"El rol {id_rol} tiene {con_usuarios} usuario(s) asignado(s); reasígnelos antes de eliminarlo.",
        )
    retirados = [p for (p,) in db.query(RolPermiso.id_permiso).filter(RolPermiso.id_rol == id_rol).all()]
    db.query(RolPermiso).filter(RolPermiso.id_rol == id_rol).delete(synchronize_session=False)
    db.add_all(
        RolPermisoHistorial(id_rol=id_rol, id_permiso=p, accion="RETIRADO", usuario_email=usuario["email"])
        for p in sorted(retirados)
    )
    db.delete(rol)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
