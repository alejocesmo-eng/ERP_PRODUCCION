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
    username = (form_data.username or "").strip()
    password = form_data.password or ""

    # Buscar usuario en PostgreSQL por email
    usuario = db.query(models.Usuario).filter(models.Usuario.email == username).first()

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

    access_token = security.create_access_token(
        data={"sub": usuario.email, "rol": usuario.id_rol}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "usuario": usuario.nombre_completo,
        "rol": usuario.id_rol,
    }