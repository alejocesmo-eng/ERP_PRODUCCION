"""
Cuentas de usuario (34_MIGRACION_ACCESO_POR_USUARIO.sql, reglas/acceso-por-usuario.md del proyecto
PRISMA).

- Se entra solo con el usuario: 3 a 50 caracteres con minúsculas, números, punto, guion bajo y
  guion. Las mayúsculas se convierten a minúsculas; espacios y tildes no se admiten.
- El sistema sugiere primer nombre.primer apellido y, si ya existe, agrega un número (juan.perez2).
- El token y la auditoría usan el identificador interno (id_usuario), no el correo ni el nombre.
  Las filas de auditoría anteriores guardan el correo y no se tocan: etiquetas_usuarios muestra el
  usuario de los identificadores y deja los demás valores como están.
"""
import re
import unicodedata
import uuid
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.db.models import Usuario

FORMATO_USUARIO = re.compile(r"^[a-z0-9._-]{3,50}$")
MENSAJE_FORMATO = (
    "El usuario debe tener de 3 a 50 caracteres: minúsculas, números, punto, guion bajo o guion, "
    "sin espacios ni tildes."
)


def normalizar_usuario(texto: Optional[str]) -> str:
    """Quita espacios de los extremos y pasa a minúsculas (no corrige tildes ni espacios internos)."""
    return (texto or "").strip().lower()


def usuario_valido(usuario: str) -> bool:
    return bool(FORMATO_USUARIO.match(usuario))


def a_uuid(valor) -> Optional[uuid.UUID]:
    if isinstance(valor, uuid.UUID):
        return valor
    try:
        return uuid.UUID(str(valor))
    except (TypeError, ValueError):
        return None


def _parte(texto: Optional[str]) -> str:
    """Primera palabra en minúsculas, sin tildes y solo con letras y números."""
    palabra = (texto or "").strip().split(" ")[0] if (texto or "").strip() else ""
    sin_tildes = unicodedata.normalize("NFKD", palabra).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", sin_tildes.lower())


def sugerir_usuario(db: Session, nombres: str, apellidos: str) -> Optional[str]:
    """primer nombre.primer apellido; si existe, con el primer número libre desde 2. None si los
    nombres no dan un usuario válido."""
    base = ".".join(parte for parte in (_parte(nombres), _parte(apellidos)) if parte)[:48]
    if not usuario_valido(base):
        return None
    existentes = {
        fila.usuario for fila in db.query(Usuario.usuario).filter(Usuario.usuario.like(f"{base}%")).all()
    }
    if base not in existentes:
        return base
    numero = 2
    while f"{base}{numero}" in existentes:
        numero += 1
    return f"{base}{numero}"


def etiquetas_usuarios(db: Session, valores: Iterable) -> dict:
    """{valor: usuario} para los valores que son id_usuario de una cuenta. Los demás (correos de
    filas anteriores, textos libres) no aparecen: quien llama los muestra tal cual."""
    ids = {a_uuid(valor) for valor in valores if valor}
    ids.discard(None)
    if not ids:
        return {}
    filas = db.query(Usuario.id_usuario, Usuario.usuario).filter(Usuario.id_usuario.in_(ids)).all()
    por_id = {str(id_usuario): usuario for id_usuario, usuario in filas}
    return {valor: por_id[str(a_uuid(valor))] for valor in valores if valor and str(a_uuid(valor)) in por_id}


def mostrar(etiquetas: dict, valor):
    """El usuario si el valor es un id_usuario conocido; si no, el valor tal cual."""
    return etiquetas.get(valor, valor)


def con_usuarios(db: Session, filas: list, *campos: str) -> list:
    """Cambia, en cada fila (dict), los campos indicados que guardan un id_usuario por el usuario.
    Los valores anteriores (correos) quedan como están. Devuelve las mismas filas."""
    etiquetas = etiquetas_usuarios(db, [fila.get(campo) for fila in filas for campo in campos])
    for fila in filas:
        for campo in campos:
            if fila.get(campo) in etiquetas:
                fila[campo] = etiquetas[fila[campo]]
    return filas
