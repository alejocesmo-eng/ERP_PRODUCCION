from fastapi import APIRouter, Depends
from app.api.deps import requerir_roles, obtener_usuario_actual

router = APIRouter()

@router.get("/me")
def obtener_perfil(usuario_actual: dict = Depends(obtener_usuario_actual)):
    """
    Consulta los datos del usuario autenticado actual.
    """
    return usuario_actual

@router.get("/panel-admin")
def panel_administrador(
    usuario_actual: dict = Depends(requerir_roles(["ADMIN"]))
):
    """
    Ruta protegida por RBAC: Solo accesible para usuarios con el rol ADMIN.
    """
    return {
        "mensaje": "Bienvenido al Panel de Administración",
        "usuario": usuario_actual["email"]
    }