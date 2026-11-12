"""
Acceso según el rol guardado en la base, leído en cada consulta (no el rol del token).

Lo usan la búsqueda general y los costos de OP: si a un usuario le cambian el rol, el cambio
cuenta desde su siguiente consulta, aunque su token diga otro rol.
"""
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual, rol_tiene_permiso
from app.core import roles
from app.core.security import ALGORITHM, SECRET_KEY
from app.db.database import get_db
from app.db.models import Usuario

PERMISO_COSTOS = "PERM_EXPEDIENTE_COSTOS_VER"
PERMISO_VALOR_COTIZADO = "PERM_VALOR_COTIZADO_VER"
# Registrar tiempos de operaciones de OP (migración 29): OPERARIO, CAPTURISTA_TIEMPOS,
# JEFE_PRODUCCION y ADMIN
PERMISO_TIEMPOS = "PERM_TIEMPOS_REGISTRAR"

# Lo único que puede usar CAPTURISTA_TIEMPOS: sesión, cola de sublotes y registro de tiempos.
# Todo lo demás (cliente, planos, costos, valor cotizado, unidad, liberación, cierre,
# retención) le responde 403, aunque la ruta solo pida token.
RUTAS_CAPTURISTA = {
    ("POST", "/api/v1/auth/token"),
    ("GET", "/api/v1/auth/permisos"),
    ("GET", "/api/v1/usuarios/me"),
    ("GET", "/api/v1/busqueda/alcance"),
    ("GET", "/api/v1/operaciones/sublotes"),
    ("POST", "/api/v1/operaciones/setup/iniciar"),
    ("POST", "/api/v1/operaciones/mecanizado/conmutar"),
    ("POST", "/api/v1/operaciones/pausa/turno"),
    ("POST", "/api/v1/operaciones/sublotes/finalizar"),
}

# Rol anterior que se trata como su sucesor durante la transición (decisión de Alejo, 2026-11-12)
EQUIVALENTES = {roles.CALIDAD: roles.GESTION_CALIDAD}


def rol_en_bd(db: Session, email: str) -> str | None:
    """Rol vigente del usuario en usuarios.id_rol, con la equivalencia de transición."""
    if not email:
        return None
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


def limitar_rol_capturista(request: Request, db: Session = Depends(get_db)) -> None:
    """Dependencia global de la aplicación: si el usuario del token es CAPTURISTA_TIEMPOS en la
    base, solo pasa a RUTAS_CAPTURISTA. Sin token o con token inválido no decide: la ruta responde."""
    cabecera = request.headers.get("authorization", "")
    if not cabecera.lower().startswith("bearer "):
        return
    try:
        email = jwt.decode(cabecera[7:].strip(), SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
    except JWTError:
        return
    if rol_en_bd(db, email) != roles.CAPTURISTA_TIEMPOS:
        return
    # Ruta completa de la petición: RUTAS_CAPTURISTA no tiene rutas con parámetros
    if (request.method, request.scope["path"].rstrip("/") or "/") not in RUTAS_CAPTURISTA:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Su rol solo registra tiempos de operaciones.")
