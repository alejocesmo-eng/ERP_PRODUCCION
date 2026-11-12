"""
Acceso según el rol guardado en la base, leído en cada consulta (no el rol del token).

Lo usan la búsqueda general y los costos de OP: si a un usuario le cambian el rol, el cambio
cuenta desde su siguiente consulta, aunque su token diga otro rol.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual, rol_tiene_permiso
from app.core import roles
from app.db.database import get_db
from app.db.models import Usuario

PERMISO_COSTOS = "PERM_EXPEDIENTE_COSTOS_VER"
PERMISO_VALOR_COTIZADO = "PERM_VALOR_COTIZADO_VER"

# Rol anterior que se trata como su sucesor durante la transición (decisión de Alejo, 2026-11-12)
EQUIVALENTES = {roles.CALIDAD: roles.GESTION_CALIDAD}


def rol_en_bd(db: Session, email: str) -> str | None:
    """Rol vigente del usuario en usuarios.id_rol, con la equivalencia de transición."""
    fila = db.query(Usuario.id_rol).filter(Usuario.email == email).first()
    rol = fila.id_rol if fila else None
    return EQUIVALENTES.get(rol, rol)


def puede(db: Session, rol: str | None, id_permiso: str) -> bool:
    """El permiso exacto en rol_permisos. PERM_ADMIN_ALL no lo sustituye: ADMIN no ve costos
    ni valor cotizado salvo que se le asignen."""
    return rol_tiene_permiso(db, rol, id_permiso)


def requerir_permiso_bd(id_permiso: str):
    def verificar(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)) -> dict:
        rol = rol_en_bd(db, usuario["email"])
        if not puede(db, rol, id_permiso):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Su rol no tiene acceso a esta información.")
        return {**usuario, "rol": rol}
    return verificar
