"""
Acceso según el rol guardado en la base, leído en cada consulta (no el rol del token).

Lo usan la búsqueda general, los costos de OP, el registro de tiempos y el alcance global por rol:
si a un usuario le cambian el rol, el cambio cuenta desde su siguiente consulta, aunque su token
diga otro rol.
"""
import json

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.api.deps import obtener_usuario_actual, rol_tiene_permiso
from app.core import roles
from app.core.security import ALGORITHM, SECRET_KEY
from app.db.database import get_db
from app.db.models import Usuario

PERMISO_COSTOS = "PERM_EXPEDIENTE_COSTOS_VER"
PERMISO_VALOR_COTIZADO = "PERM_VALOR_COTIZADO_VER"
# Registrar tiempos de operaciones de OP (migraciones 29, 30 y 32): OPERARIO, CAPTURISTA_TIEMPOS,
# JEFE_PRODUCCION, ADMIN, LIDER_MECANIZADOS y LIDER_SERVICIOS. Se lee de rol_permisos en cada
# petición: ADMIN lo asigna o retira desde Configuración de roles sin tocar código
PERMISO_TIEMPOS = "PERM_TIEMPOS_REGISTRAR"

# Lo único que puede usar CAPTURISTA_TIEMPOS: sesión, cola de sublotes, registro de tiempos y
# carga manual de tiempos (app/api/v1/tiempos_manuales.py).
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
    ("GET", "/api/v1/tiempos-manuales"),
    ("POST", "/api/v1/tiempos-manuales"),
    ("POST", "/api/v1/tiempos-manuales/corregir"),
}

# Rol anterior que se trata como su sucesor durante la transición (decisión de Alejo, 2026-11-12)
EQUIVALENTES = {roles.CALIDAD: roles.GESTION_CALIDAD}


def rol_en_bd(db: Session, id_usuario) -> str | None:
    """Rol vigente del usuario (por id_usuario, el sub del token) en usuarios.id_rol, con la
    equivalencia de transición."""
    from app.services.usuarios import a_uuid

    identificador = a_uuid(id_usuario)
    if identificador is None:
        return None
    fila = db.query(Usuario.id_rol).filter(Usuario.id_usuario == identificador).first()
    rol = fila.id_rol if fila else None
    return EQUIVALENTES.get(rol, rol)


def puede(db: Session, rol: str | None, id_permiso: str) -> bool:
    """El permiso exacto en rol_permisos. PERM_ADMIN_ALL no lo sustituye: ADMIN no ve costos
    ni valor cotizado salvo que se le asignen."""
    return rol_tiene_permiso(db, rol, id_permiso)


def requerir_permiso_bd(id_permiso: str):
    def verificar(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)) -> dict:
        rol = rol_en_bd(db, usuario["id_usuario"])
        if not puede(db, rol, id_permiso):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Su rol no tiene acceso a esta información.")
        return {**usuario, "rol": rol}
    return verificar


# Datos del cliente que OPERARIO y CAPTURISTA_TIEMPOS no reciben en ninguna respuesta
# (reglas/permisos-por-rol-modulo.md: OPERARIO sin datos de cliente). Se quitan por nombre de campo.
CAMPOS_CLIENTE = frozenset({
    "cliente", "cliente_nombre", "nombre_cliente", "ubicacion_cliente", "id_cliente", "cliente_id",
    "id_socio", "socio", "razon_social", "nit", "nit_rut", "nit_cedula", "codigo_socio", "contacto",
    "contacto_nombre", "contacto_telefono", "contacto_email", "email_contacto", "telefono", "ciudad",
    "direccion", "pais", "condiciones_pago_dias",
})
# CAPTURISTA_TIEMPOS tampoco recibe nada del plano: le basta la OP, la operación, la máquina,
# el operario y la cantidad para registrar tiempos
CAMPOS_PLANO = frozenset({
    "id_plano", "codigo_plano", "archivo_url", "detalle_pieza", "instrucciones", "observaciones_tecnicas",
})
# Valor cotizado: solo VENTAS, JEFE_PRODUCCION, COSTOS y GESTION_CALIDAD (PERM_VALOR_COTIZADO_VER).
# Algunas rutas que solo piden token lo devuelven (expediente del pedido, cotizaciones): a OPERARIO
# y a CAPTURISTA_TIEMPOS se les quita por campo. "valor_total" también es el valor de movimientos
# de inventario, que tampoco deben ver (sin costos). "valor_cotizado" no está: en la búsqueda solo
# sale con el permiso, y en /busqueda/alcance es el indicador de si el rol lo ve.
CAMPOS_VALOR_COTIZADO = frozenset({
    "valor_total_cotizado", "cotizacion_total", "cotizacion_comercial", "valor_total", "precio_unitario",
    "subtotal",
})
CAMPOS_OCULTOS_POR_ROL = {
    roles.OPERARIO: CAMPOS_CLIENTE | CAMPOS_VALOR_COTIZADO,
    roles.CAPTURISTA_TIEMPOS: CAMPOS_CLIENTE | CAMPOS_VALOR_COTIZADO | CAMPOS_PLANO,
    # Los líderes de unidad ven el cliente y su histórico, pero no el valor cotizado (expediente del
    # pedido, cotizaciones) ni valores de inventario
    roles.LIDER_MECANIZADOS: CAMPOS_VALOR_COTIZADO,
    roles.LIDER_SERVICIOS: CAMPOS_VALOR_COTIZADO,
}


def alcance_por_rol(request: Request, db: Session = Depends(get_db)) -> None:
    """Dependencia global de la aplicación, con el rol de la base:
    - CAPTURISTA_TIEMPOS solo pasa a RUTAS_CAPTURISTA.
    - OPERARIO, CAPTURISTA_TIEMPOS y los líderes de unidad marcan la petición para que
      OcultarCamposPorRol quite de la respuesta los campos de CAMPOS_OCULTOS_POR_ROL (valor
      cotizado; a OPERARIO y al capturista, también el cliente; al capturista, el plano).
    Sin token o con token inválido no decide: la ruta responde."""
    cabecera = request.headers.get("authorization", "")
    if not cabecera.lower().startswith("bearer "):
        return
    try:
        id_usuario = jwt.decode(cabecera[7:].strip(), SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
    except JWTError:
        return
    rol = rol_en_bd(db, id_usuario)
    if rol in CAMPOS_OCULTOS_POR_ROL:
        request.state.campos_ocultos = CAMPOS_OCULTOS_POR_ROL[rol]
    # Ruta completa de la petición: RUTAS_CAPTURISTA no tiene rutas con parámetros
    if rol == roles.CAPTURISTA_TIEMPOS and (request.method, request.scope["path"].rstrip("/") or "/") not in RUTAS_CAPTURISTA:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Su rol solo registra tiempos de operaciones.")


def quitar_campos(valor, ocultos: frozenset):
    if isinstance(valor, dict):
        return {clave: quitar_campos(dato, ocultos) for clave, dato in valor.items() if clave not in ocultos}
    if isinstance(valor, list):
        return [quitar_campos(dato, ocultos) for dato in valor]
    return valor


class OcultarCamposPorRol(BaseHTTPMiddleware):
    """Quita de las respuestas JSON los campos que alcance_por_rol marcó para el rol."""

    async def dispatch(self, request: Request, call_next):
        respuesta = await call_next(request)
        ocultos = getattr(request.state, "campos_ocultos", None)
        if not ocultos or "application/json" not in respuesta.headers.get("content-type", ""):
            return respuesta
        cuerpo = b"".join([parte async for parte in respuesta.body_iterator])
        try:
            datos = json.loads(cuerpo)
        except ValueError:
            return Response(content=cuerpo, status_code=respuesta.status_code, headers=dict(respuesta.headers))
        cabeceras = {k: v for k, v in respuesta.headers.items() if k.lower() != "content-length"}
        return Response(
            content=json.dumps(quitar_campos(datos, ocultos), ensure_ascii=False).encode("utf-8"),
            status_code=respuesta.status_code,
            headers=cabeceras,
            media_type="application/json",
        )
