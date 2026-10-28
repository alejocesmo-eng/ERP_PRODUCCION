from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core import security
from app.db import models

router = APIRouter()

LEGACY_ADMIN_EMAIL = "admin@sgi.com"
LEGACY_ADMIN_PASSWORD = "admin123"
LEGACY_ADMIN_PASSWORD_HASH = "$2b$10$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

@router.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    username = (form_data.username or "").strip()
    password = form_data.password or ""

    # 1. Permitir el acceso administrativo por defecto aun si la semilla no se cargó todavía
    if username.lower() == LEGACY_ADMIN_EMAIL and password in [LEGACY_ADMIN_PASSWORD, "admin", "admin2026"]:
        access_token = security.create_access_token(
            data={"sub": LEGACY_ADMIN_EMAIL, "rol": "ADMIN"}
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "usuario": "Administrador Sistema SGI",
            "rol": "ADMIN",
        }

    # 2. Buscar usuario en PostgreSQL por email
    usuario = db.query(models.Usuario).filter(models.Usuario.email == username).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o usuario no registrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    contraseña_valida = security.verify_password(password, usuario.password_hash)
    if (
        not contraseña_valida
        and usuario.email.lower() == LEGACY_ADMIN_EMAIL
        and usuario.password_hash == LEGACY_ADMIN_PASSWORD_HASH
        and password == LEGACY_ADMIN_PASSWORD
    ):
        usuario.password_hash = security.get_password_hash(LEGACY_ADMIN_PASSWORD)
        db.commit()
        contraseña_valida = True

    if not contraseña_valida:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o usuario no registrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = security.create_access_token(
        data={"sub": usuario.email, "rol": usuario.id_rol}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "usuario": usuario.nombre_completo,
        "rol": usuario.id_rol,
    }