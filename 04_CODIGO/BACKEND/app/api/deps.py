from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.security import SECRET_KEY, ALGORITHM
from app.db.database import get_db
from app.db.models import RolPermiso, Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def usuario_vigente(db: Session, email: str) -> bool:
    """El usuario del token sigue existiendo y no está desactivado (activo NULL cuenta como activo)."""
    fila = db.query(Usuario.activo).filter(Usuario.email == email).first()
    return fila is not None and fila.activo is not False


def obtener_usuario_actual(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
    except JWTError:
        raise credentials_exception
    # El JWT no tiene estado: se revisa el usuario en cada petición para que desactivarlo
    # (o eliminarlo) invalide de inmediato sus tokens vigentes.
    if not usuario_vigente(db, email):
        raise credentials_exception
    return {"email": email, "rol": rol}

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