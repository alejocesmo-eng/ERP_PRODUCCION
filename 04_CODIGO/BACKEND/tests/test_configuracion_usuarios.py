# tests/test_configuracion_usuarios.py
"""
Administración de usuarios desde Configuración e inicio de sesión por usuario
(app/api/v1/configuracion_usuarios.py, app/api/v1/auth.py, migración 34;
reglas/acceso-por-usuario.md del proyecto PRISMA):
- Solo ADMIN (con PERM_CONFIGURACION_ROLES) crea, edita, desactiva, reactiva y asigna rol y
  contraseña; los demás reciben 403. El rol se lee de la base.
- Usuario único de 3 a 50 caracteres (minúsculas, números, punto, guion bajo, guion); las
  mayúsculas se convierten. Sugerencia primer nombre.primer apellido, con número si existe.
- Correo opcional y único cuando tiene valor. Se entra solo con el usuario.
- "Eliminar" desactiva. Cada cambio queda en usuarios_historial con el id de quien lo hizo y sin
  contraseñas.

Se marca usuario_real: el token se valida contra la base (usuario existente y activo).
SQLite en memoria con override de get_db; aplicación FastAPI mínima.
"""
import uuid
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth, configuracion_roles, configuracion_usuarios
from app.core import roles
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.database import Base, get_db
from app.db.models import Permiso, Rol, RolPermiso, Usuario, UsuarioHistorial
from app.services import acceso_bd
from app.services.usuarios import sugerir_usuario
from tests.ayudantes_usuarios import datos_usuario, id_prueba

pytestmark = pytest.mark.usuario_real

RUTA = "/api/v1/configuracion/usuarios"
CLAVE = "clave-inicial-1"


@pytest.fixture
def ctx():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.include_router(auth.router, prefix="/api/v1/auth")
    app.include_router(configuracion_usuarios.router, prefix=RUTA)
    app.include_router(configuracion_roles.router, prefix="/api/v1/configuracion/roles")
    app.dependency_overrides[get_db] = _get_db
    with Sesion() as s:
        s.add_all(Rol(id_rol=rol, nombre_rol=rol.title()) for rol in (roles.ADMIN, roles.VENTAS, roles.OPERARIO))
        s.add(Permiso(id_permiso=configuracion_roles.PERMISO_CONFIGURACION, modulo="CONFIGURACION"))
        s.add(RolPermiso(id_rol=roles.ADMIN, id_permiso=configuracion_roles.PERMISO_CONFIGURACION))
        s.add_all(
            Usuario(**datos_usuario(rol.lower()), password_hash=get_password_hash(CLAVE), nombre_completo=rol, id_rol=rol)
            for rol in (roles.ADMIN, roles.VENTAS)
        )
        s.commit()
    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


def token(usuario, rol):
    t = create_access_token({"sub": str(id_prueba(usuario)), "rol": rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


def admin():
    # Cuenta "admin" del fixture, con su id fijo
    return token("admin", roles.ADMIN)


def crear(client, **datos):
    cuerpo = {"nombres": "Juan Carlos", "apellidos": "Pérez Gómez", "id_rol": roles.VENTAS, "clave": "clave-segura-1", **datos}
    return client.post(RUTA, json=cuerpo, headers=admin())


def login(client, usuario, clave):
    return client.post("/api/v1/auth/token", data={"username": usuario, "password": clave})


def historial(Sesion, id_usuario):
    with Sesion() as s:
        return [(f.accion, f.cambios, f.realizado_por) for f in
                s.query(UsuarioHistorial).filter(UsuarioHistorial.id_usuario == id_usuario)
                .order_by(UsuarioHistorial.id_historial).all()]


# --- Acceso -------------------------------------------------------------------------------------

@pytest.mark.parametrize("metodo, ruta", [
    ("get", RUTA), ("post", RUTA), ("get", f"{RUTA}/sugerencia?nombres=a&apellidos=b"),
    ("patch", f"{RUTA}/{id_prueba('admin')}"), ("put", f"{RUTA}/{id_prueba('admin')}/clave"),
    ("post", f"{RUTA}/{id_prueba('admin')}/desactivar"), ("get", f"{RUTA}/{id_prueba('admin')}/historial"),
])
def test_solo_admin_administra_usuarios(ctx, metodo, ruta):
    client, _ = ctx
    assert client.request(metodo, ruta, json={}, headers=token("ventas", roles.VENTAS)).status_code == 403


def test_no_hay_ruta_para_borrar(ctx):
    client, _ = ctx
    assert client.delete(f"{RUTA}/{id_prueba('ventas')}", headers=admin()).status_code == 405


# --- Crear y sugerir ----------------------------------------------------------------------------

def test_sugiere_primer_nombre_punto_primer_apellido_y_numera_si_existe(ctx):
    client, _ = ctx
    sugerencia = client.get(f"{RUTA}/sugerencia", params={"nombres": "José Ángel", "apellidos": "Núñez Ruiz"},
                            headers=admin()).json()
    assert sugerencia == {"usuario": "jose.nunez"}

    assert crear(client).json()["usuario"] == "juan.perez"
    assert crear(client).json()["usuario"] == "juan.perez2"
    assert crear(client).json()["usuario"] == "juan.perez3"


def test_crea_con_el_usuario_que_escribe_admin_en_minusculas(ctx):
    client, Sesion = ctx
    respuesta = crear(client, usuario="  JPerez.Taller ", email="JUAN@EMPRESA.TEST")

    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()
    assert (datos["usuario"], datos["email"], datos["nombre_completo"], datos["id_rol"], datos["activo"]) == (
        "jperez.taller", "juan@empresa.test", "Juan Carlos Pérez Gómez", roles.VENTAS, True,
    )
    with Sesion() as s:
        cuenta = s.query(Usuario).filter_by(usuario="jperez.taller").one()
        assert verify_password("clave-segura-1", cuenta.password_hash) and cuenta.password_hash != "clave-segura-1"
    assert historial(Sesion, cuenta.id_usuario) == [("CREADO", {
        "usuario": "jperez.taller", "nombre_completo": "Juan Carlos Pérez Gómez", "email": "juan@empresa.test",
        "id_rol": roles.VENTAS,
    }, str(id_prueba("admin")))]


@pytest.mark.parametrize("usuario", ["juan perez", "josé", "ab", "a" * 51, "juan@perez", "juan/perez"])
def test_formato_de_usuario(ctx, usuario):
    client, _ = ctx
    respuesta = crear(client, usuario=usuario)
    assert respuesta.status_code == 422


def test_el_correo_es_opcional_y_unico_cuando_tiene_valor(ctx):
    client, _ = ctx
    assert crear(client).json()["email"] is None
    assert crear(client).status_code == 201
    assert crear(client, email="ventas@prueba.test").status_code == 409
    assert crear(client, email="no-es-correo").status_code == 422


def test_usuario_repetido_rol_inexistente_y_clave_corta(ctx):
    client, _ = ctx
    assert crear(client, usuario="ventas").status_code == 409
    assert crear(client, usuario="Ventas").status_code == 409
    assert crear(client, id_rol="NO_EXISTE").status_code == 422
    assert crear(client, clave="corta").status_code == 422


# --- Inicio de sesión ---------------------------------------------------------------------------

def test_la_cuenta_nueva_entra_con_su_usuario_y_no_con_el_correo(ctx):
    client, _ = ctx
    crear(client, usuario="nuevo.usuario", email="nuevo@empresa.test")

    assert login(client, "nuevo.usuario", "clave-segura-1").status_code == 200
    assert login(client, "NUEVO.USUARIO", "clave-segura-1").status_code == 200
    assert login(client, "nuevo@empresa.test", "clave-segura-1").status_code == 401


def test_admin_asigna_contrasena_definitiva_sin_registrarla(ctx):
    client, Sesion = ctx
    id_usuario = crear(client, usuario="olvido").json()["id_usuario"]

    assert client.put(f"{RUTA}/{id_usuario}/clave", json={"clave": "nueva-clave-9"}, headers=admin()).status_code == 204
    assert login(client, "olvido", "clave-segura-1").status_code == 401
    assert login(client, "olvido", "nueva-clave-9").status_code == 200
    acciones = historial(Sesion, uuid.UUID(id_usuario))
    assert acciones[-1] == ("CLAVE_ASIGNADA", {}, str(id_prueba("admin")))
    assert "nueva-clave-9" not in str(acciones)


# --- Editar, desactivar, reactivar --------------------------------------------------------------

def test_editar_usuario_correo_nombre_y_rol_queda_en_la_auditoria(ctx):
    client, Sesion = ctx
    id_usuario = crear(client, usuario="editable", email="editable@empresa.test").json()["id_usuario"]
    token_previo = login(client, "editable", "clave-segura-1").json()["access_token"]

    respuesta = client.patch(f"{RUTA}/{id_usuario}", json={
        "usuario": "Editado", "email": "", "nombre_completo": "Nombre Nuevo", "id_rol": roles.OPERARIO,
    }, headers=admin())

    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()
    assert (datos["usuario"], datos["email"], datos["nombre_completo"], datos["id_rol"]) == (
        "editado", None, "Nombre Nuevo", roles.OPERARIO,
    )
    acciones = historial(Sesion, uuid.UUID(id_usuario))
    assert [a for a, _, _ in acciones] == ["CREADO", "EDITADO", "ROL_ASIGNADO"]
    assert acciones[1][1]["usuario"] == {"antes": "editable", "despues": "editado"}
    assert acciones[2][1] == {"id_rol": {"antes": roles.VENTAS, "despues": roles.OPERARIO}}
    # El token lleva el identificador interno: sigue sirviendo tras cambiar el usuario
    me = client.get(f"{RUTA}", headers={"Authorization": f"Bearer {token_previo}"})
    assert me.status_code == 403  # sigue vigente (no 401), pero no es ADMIN
    assert login(client, "editado", "clave-segura-1").status_code == 200


def test_desactivar_corta_el_acceso_y_reactivar_lo_devuelve(ctx):
    client, Sesion = ctx
    id_usuario = crear(client, usuario="temporal").json()["id_usuario"]

    assert client.post(f"{RUTA}/{id_usuario}/desactivar", headers=admin()).json()["activo"] is False
    assert login(client, "temporal", "clave-segura-1").status_code == 401
    with Sesion() as s:
        assert s.query(Usuario).filter_by(usuario="temporal").count() == 1  # la fila no se borra

    assert client.post(f"{RUTA}/{id_usuario}/reactivar", headers=admin()).json()["activo"] is True
    assert login(client, "temporal", "clave-segura-1").status_code == 200
    assert [a for a, _, _ in historial(Sesion, uuid.UUID(id_usuario))] == ["CREADO", "DESACTIVADO", "REACTIVADO"]


def test_admin_no_se_desactiva_ni_se_quita_el_rol_admin(ctx):
    client, _ = ctx
    propio = f"{RUTA}/{id_prueba('admin')}"
    assert client.post(f"{propio}/desactivar", headers=admin()).status_code == 409
    assert client.patch(propio, json={"id_rol": roles.VENTAS}, headers=admin()).status_code == 409


def test_el_historial_muestra_el_usuario_de_quien_hizo_el_cambio(ctx):
    client, _ = ctx
    id_usuario = crear(client, usuario="con.historial").json()["id_usuario"]

    filas = client.get(f"{RUTA}/{id_usuario}/historial", headers=admin()).json()
    assert [(f["accion"], f["realizado_por"]) for f in filas] == [("CREADO", "admin")]


def test_listado_con_rol_y_estado(ctx):
    client, _ = ctx
    usuarios = {u["usuario"]: u for u in client.get(RUTA, headers=admin()).json()}
    assert usuarios["ventas"]["nombre_rol"] == "Ventas" and usuarios["ventas"]["activo"] is True
    assert "password_hash" not in usuarios["ventas"]


def test_sugerencia_sin_nombres_validos(ctx):
    _, Sesion = ctx
    with Sesion() as s:
        assert sugerir_usuario(s, "", "") is None
        assert sugerir_usuario(s, "Ñ", "") is None
