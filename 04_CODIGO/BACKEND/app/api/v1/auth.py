from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.api.deps import obtener_usuario_actual, permisos_de_rol
from app.core import security
from app.db import models
from app.services.usuarios import normalizar_usuario

router = APIRouter()

@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Solo se entra con el usuario (34_MIGRACION_ACCESO_POR_USUARIO.sql); el correo no sirve.
    # Las mayúsculas se convierten a minúsculas, como al crear la cuenta.
    username = normalizar_usuario(form_data.username)
    password = form_data.password or ""

    usuario = db.query(models.Usuario).filter(models.Usuario.usuario == username).first() if username else None

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o usuario no registrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    contraseña_valida = security.verify_password(password, usuario.password_hash)

    if not contraseña_valida:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o usuario no registrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Usuario desactivado: no recibe token. Se informa solo después de validar la clave, para
    # no revelar qué cuentas existen. activo admite NULL (filas antiguas): solo False es inactivo.
    if usuario.activo is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo. Contacte al administrador.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = security.create_access_token(
        data={"sub": str(usuario.id_usuario), "rol": usuario.id_rol}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        # Nombre para mostrar (la interfaz lo usa así desde antes) y usuario con que se entró
        "usuario": usuario.nombre_completo,
        "nombre_usuario": usuario.usuario,
        "rol": usuario.id_rol,
    }


@router.get("/permisos")
def permisos_del_usuario(
    usuario_actual: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Permisos del rol del usuario (rol_permisos), para que el frontend muestre u oculte
    módulos. Solo orienta la interfaz: cada ruta sigue validando el acceso por su cuenta."""
    return {"rol": usuario_actual["rol"], "permisos": permisos_de_rol(db, usuario_actual["rol"])}
