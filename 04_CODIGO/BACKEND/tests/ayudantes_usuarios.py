# tests/ayudantes_usuarios.py
"""
Cuentas de prueba con el inicio de sesión por usuario (34_MIGRACION_ACCESO_POR_USUARIO.sql).

El token lleva en sub el id_usuario y la auditoría guarda ese mismo identificador. Para que las
pruebas sepan de antemano cuál es, cada usuario de prueba tiene un id fijo derivado de su nombre
(uuid5): id_prueba("jefe_produccion") es siempre el mismo.
"""
import uuid

ESPACIO_PRUEBAS = uuid.UUID("5b1d6f8e-4c3a-4e2b-9a7d-0c1e2f3a4b5c")


def id_prueba(usuario: str) -> uuid.UUID:
    return uuid.uuid5(ESPACIO_PRUEBAS, usuario)


def datos_usuario(usuario: str) -> dict:
    """id_usuario, usuario y correo de contacto de una cuenta de prueba, para Usuario(**...)."""
    return {"id_usuario": id_prueba(usuario), "usuario": usuario, "email": f"{usuario}@prueba.test"}
