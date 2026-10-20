from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core import security
from app.db import models

router = APIRouter()

@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    usuario = None
    
    # 1. Intentar buscar usuario en PostgreSQL por email
    try:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == form_data.username).first()
    except Exception:
        usuario = None

    # 2. Validar contraseña contra el atributo real password_hash si el usuario existe en BD
    if usuario and hasattr(usuario, 'password_hash') and usuario.password_hash:
        if security.verify_password(form_data.password, usuario.password_hash):
            access_token = security.create_access_token(
                data={"sub": usuario.email, "rol": getattr(usuario, 'id_rol', 'ADMIN')}
            )
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "usuario": getattr(usuario, 'nombre_completo', usuario.email),
                "rol": getattr(usuario, 'id_rol', 'ADMIN')
            }

    # 3. Fallback de contingencia para usuario administrador por defecto (desarrollo/pruebas)
    if form_data.username == "admin@sgi.com" and form_data.password in ["admin123", "admin", "admin2026"]:
        access_token = security.create_access_token(
            data={"sub": "admin@sgi.com", "rol": "ADMIN"}
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "usuario": "Administrador Sistema SGI",
            "rol": "ADMIN"
        }

    # 4. Rechazar credenciales si no coinciden en BD ni en fallback
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o usuario no registrado.",
        headers={"WWW-Authenticate": "Bearer"},
    )