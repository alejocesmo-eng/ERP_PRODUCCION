from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.security import SECRET_KEY, ALGORITHM
from app.db.models import RolPermiso

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def obtener_usuario_actual(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación no válidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        rol: str = payload.get("rol")
        if email is None or rol is None:
            raise credentials_exception
        return {"email": email, "rol": rol}
    except JWTError:
        raise credentials_exception

def requerir_roles(roles_permitidos: list[str]):
    def rol_checker(usuario_actual: dict = Depends(obtener_usuario_actual)):
        if usuario_actual["rol"] not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Permisos requeridos para rol(es): {roles_permitidos}"
            )
        return usuario_actual
    return rol_checker

def rol_tiene_permiso(db: Session, rol: str | None, id_permiso: str) -> bool:
    """Consulta rol_permisos (migraciones 15 y 16)."""
    if not rol:
        return False
    return db.query(RolPermiso).filter(
        RolPermiso.id_rol == rol,
        RolPermiso.id_permiso == id_permiso,
    ).first() is not None