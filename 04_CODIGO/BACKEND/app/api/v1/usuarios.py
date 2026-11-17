from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import requerir_roles, obtener_usuario_actual
from app.core.roles import ROLES_SOLO_ADMIN
from app.db.database import get_db
from app.db.models import Usuario
from app.services.usuarios import a_uuid

router = APIRouter()

@router.get("/me")
def obtener_perfil(usuario_actual: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    """
    Consulta los datos del usuario autenticado actual.
    """
    cuenta = db.query(Usuario).filter(Usuario.id_usuario == a_uuid(usuario_actual["id_usuario"])).first()
    return {
        **usuario_actual,
        "usuario": cuenta.usuario if cuenta else None,
        "nombre": cuenta.nombre_completo if cuenta else None,
        "email": cuenta.email if cuenta else None,
    }

@router.get("/panel-admin")
def panel_administrador(
    usuario_actual: dict = Depends(requerir_roles(ROLES_SOLO_ADMIN))
):
    """
    Ruta protegida por RBAC: Solo accesible para usuarios con el rol ADMIN.
    """
    return {
        "mensaje": "Bienvenido al Panel de Administración",
        "usuario": usuario_actual["id_usuario"]
    }