# tests/test_configuracion_roles.py
"""
Configuración de roles y permisos (migración 31, app/api/v1/configuracion_roles.py): solo ADMIN
entra, con el rol leído de la base y PERM_CONFIGURACION_ROLES; crea roles con código fijo, asigna
permisos del catálogo con registro de quién y cuándo, no deja que ADMIN se quite el acceso ni que
se elimine un rol con usuarios. Los cambios aplican en la siguiente consulta, sin reiniciar.

SQLite en memoria con override de get_db; aplicación FastAPI mínima con la misma dependencia global
que app.main (no se importa app.main). Los roles y permisos son ficticios, salvo ADMIN y el permiso
técnico de la pantalla.
"""
from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth, configuracion_roles
from app.api.v1.configuracion_roles import PERMISO_CONFIGURACION
from app.core import roles
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.db.models import Permiso, Rol, RolPermiso, RolPermisoHistorial, Usuario
from app.services import acceso_bd

RUTA = "/api/v1/configuracion/roles"
SIN_ACCESO = [roles.OPERARIO, roles.LIDER_MECANIZADOS, roles.JEFE_PRODUCCION]
PERMISO_A = "PERM_PRUEBA_A"
PERMISO_B = "PERM_PRUEBA_B"
RUTAS_CONFIGURACION = [
    ("get", f"{RUTA}/"),
    ("get", f"{RUTA}/permisos"),
    ("post", f"{RUTA}/"),
    ("patch", f"{RUTA}/{roles.OPERARIO}"),
    ("put", f"{RUTA}/{roles.OPERARIO}/permisos"),
    ("get", f"{RUTA}/{roles.OPERARIO}/historial"),
    ("delete", f"{RUTA}/ROL_SIN_USUARIOS"),
]


def crear_app():
    app = FastAPI(dependencies=[Depends(acceso_bd.alcance_por_rol)])
    app.add_middleware(acceso_bd.OcultarCamposPorRol)
    app.include_router(auth.router, prefix="/api/v1/auth")
    app.include_router(configuracion_roles.router, prefix=RUTA)
    return app


@pytest.fixture
def entorno():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def _get_db():
        s = Sesion()
        try:
            yield s
        finally:
            s.close()

    app = crear_app()
    app.dependency_overrides[get_db] = _get_db
    with Sesion() as s:
        con_usuario = (roles.ADMIN, *SIN_ACCESO)
        s.add_all(Rol(id_rol=rol, nombre_rol=rol) for rol in (*con_usuario, "ROL_SIN_USUARIOS"))
        s.add_all(Permiso(id_permiso=p, modulo="PRUEBA") for p in (PERMISO_CONFIGURACION, PERMISO_A, PERMISO_B))
        s.add(RolPermiso(id_rol=roles.ADMIN, id_permiso=PERMISO_CONFIGURACION))
        s.add(RolPermiso(id_rol="ROL_SIN_USUARIOS", id_permiso=PERMISO_A))
        s.add_all(
            Usuario(email=f"{rol.lower()}@prueba.test", password_hash="!SIN_CLAVE", nombre_completo=rol, id_rol=rol)
            for rol in con_usuario
        )
        s.commit()
    with TestClient(app) as client:
        yield client, Sesion
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(entorno):
    return entorno[0]


def token(rol, rol_en_token=None):
    t = create_access_token({"sub": f"{rol.lower()}@prueba.test", "rol": rol_en_token or rol}, timedelta(minutes=5))
    return {"Authorization": f"Bearer {t}"}


ADMIN = token(roles.ADMIN)


def llamar(client, metodo, ruta, cabeceras):
    extra = {"json": {}} if metodo in ("post", "patch", "put") else {}
    return getattr(client, metodo)(ruta, headers=cabeceras, **extra)


# --- Acceso -----------------------------------------------------------------------------------

@pytest.mark.parametrize("rol", SIN_ACCESO)
@pytest.mark.parametrize("metodo, ruta", RUTAS_CONFIGURACION, ids=[f"{m} {r}" for m, r in RUTAS_CONFIGURACION])
def test_operario_lider_mecanizados_y_jefe_produccion_reciben_403(client, rol, metodo, ruta):
    respuesta = llamar(client, metodo, ruta, token(rol))

    assert respuesta.status_code == 403
    assert respuesta.json()["detail"] == "Solo ADMIN entra a Configuración de roles."


@pytest.mark.parametrize("rol", SIN_ACCESO)
def test_el_menu_no_muestra_configuracion_a_otros_roles(client, rol):
    assert client.get(f"{RUTA}/acceso", headers=token(rol)).json() == {"acceso": False}
    assert client.get(f"{RUTA}/acceso", headers=ADMIN).json() == {"acceso": True}


def test_admin_entra(client):
    assert client.get(f"{RUTA}/", headers=ADMIN).status_code == 200
    assert client.get(f"{RUTA}/permisos", headers=ADMIN).status_code == 200


def test_el_filtro_lee_el_rol_de_la_base_y_no_el_del_token(client):
    # El token dice ADMIN, pero en la base es OPERARIO
    assert client.get(f"{RUTA}/", headers=token(roles.OPERARIO, rol_en_token=roles.ADMIN)).status_code == 403
    # El token dice OPERARIO, pero en la base es ADMIN
    assert client.get(f"{RUTA}/", headers=token(roles.ADMIN, rol_en_token=roles.OPERARIO)).status_code == 200


def test_un_cambio_de_rol_en_la_base_cuenta_desde_la_siguiente_consulta(entorno):
    client, Sesion = entorno
    cabeceras = token(roles.JEFE_PRODUCCION)
    assert client.get(f"{RUTA}/", headers=cabeceras).status_code == 403
    with Sesion() as s:
        s.query(Usuario).filter(Usuario.email == "jefe_produccion@prueba.test").update({"id_rol": roles.ADMIN})
        s.commit()
    assert client.get(f"{RUTA}/", headers=cabeceras).status_code == 200


def test_admin_sin_el_permiso_de_configuracion_no_entra(entorno):
    client, Sesion = entorno
    with Sesion() as s:
        s.query(RolPermiso).filter(RolPermiso.id_permiso == PERMISO_CONFIGURACION).delete()
        s.commit()
    assert client.get(f"{RUTA}/", headers=ADMIN).status_code == 403


def test_sin_token_responde_401(client):
    assert client.get(f"{RUTA}/").status_code == 401
    assert client.get(f"{RUTA}/acceso").status_code == 401


# --- Crear y editar roles ---------------------------------------------------------------------

def test_crea_un_rol_con_nombre_de_negocio_y_codigo_tecnico(client):
    respuesta = client.post(f"{RUTA}/", json={"id_rol": "ROL_NUEVO_2", "nombre_rol": "Rol nuevo"}, headers=ADMIN)

    assert respuesta.status_code == 201
    assert respuesta.json() == {
        "id_rol": "ROL_NUEVO_2", "nombre_rol": "Rol nuevo", "descripcion": None, "permisos": [], "usuarios": 0,
    }
    assert "ROL_NUEVO_2" in [r["id_rol"] for r in client.get(f"{RUTA}/", headers=ADMIN).json()]


@pytest.mark.parametrize("codigo", ["ROL NUEVO", "rol_nuevo", "Rol_Nuevo", "1ROL", "R", "ROL-NUEVO", " ROL", "X" * 51])
def test_el_codigo_va_en_mayusculas_y_sin_espacios(client, codigo):
    respuesta = client.post(f"{RUTA}/", json={"id_rol": codigo, "nombre_rol": "Rol"}, headers=ADMIN)
    assert respuesta.status_code == 422


def test_el_nombre_de_negocio_es_obligatorio(client):
    assert client.post(f"{RUTA}/", json={"id_rol": "ROL_X", "nombre_rol": "  "}, headers=ADMIN).status_code == 422


def test_el_codigo_no_se_repite(client):
    respuesta = client.post(f"{RUTA}/", json={"id_rol": roles.OPERARIO, "nombre_rol": "Otro"}, headers=ADMIN)

    assert respuesta.status_code == 409
    assert roles.OPERARIO in respuesta.json()["detail"]


def test_el_codigo_no_se_cambia_despues_de_crearlo(client):
    cambio = client.patch(f"{RUTA}/{roles.OPERARIO}", json={"id_rol": "OTRO_CODIGO"}, headers=ADMIN)
    assert cambio.status_code == 422

    editado = client.patch(f"{RUTA}/{roles.OPERARIO}", json={"nombre_rol": "Operario de planta"}, headers=ADMIN)
    assert editado.status_code == 200
    assert (editado.json()["id_rol"], editado.json()["nombre_rol"]) == (roles.OPERARIO, "Operario de planta")


# --- Permisos ---------------------------------------------------------------------------------

def test_asigna_permisos_del_catalogo_y_registra_quien_y_cuando(entorno):
    client, Sesion = entorno
    respuesta = client.put(f"{RUTA}/{roles.OPERARIO}/permisos", json={"permisos": [PERMISO_A, PERMISO_B]}, headers=ADMIN)
    assert respuesta.status_code == 200
    assert respuesta.json()["asignados"] == [PERMISO_A, PERMISO_B]

    respuesta = client.put(f"{RUTA}/{roles.OPERARIO}/permisos", json={"permisos": [PERMISO_B]}, headers=ADMIN)
    assert (respuesta.json()["asignados"], respuesta.json()["retirados"]) == ([], [PERMISO_A])

    historial = client.get(f"{RUTA}/{roles.OPERARIO}/historial", headers=ADMIN).json()
    assert sorted((h["id_permiso"], h["accion"]) for h in historial) == [
        (PERMISO_A, "ASIGNADO"), (PERMISO_A, "RETIRADO"), (PERMISO_B, "ASIGNADO"),
    ]
    assert {h["usuario_email"] for h in historial} == {"admin@prueba.test"}
    assert all(h["registrado_en"] for h in historial)
    with Sesion() as s:
        assert s.query(RolPermisoHistorial).count() == 3


def test_sin_cambios_no_se_registra_nada(client):
    client.put(f"{RUTA}/{roles.OPERARIO}/permisos", json={"permisos": [PERMISO_A]}, headers=ADMIN)
    client.put(f"{RUTA}/{roles.OPERARIO}/permisos", json={"permisos": [PERMISO_A]}, headers=ADMIN)

    assert len(client.get(f"{RUTA}/{roles.OPERARIO}/historial", headers=ADMIN).json()) == 1


def test_no_se_crean_permisos_desde_la_pantalla(entorno):
    client, Sesion = entorno
    respuesta = client.put(f"{RUTA}/{roles.OPERARIO}/permisos", json={"permisos": ["PERM_INVENTADO"]}, headers=ADMIN)

    assert respuesta.status_code == 400
    assert "PERM_INVENTADO" in respuesta.json()["detail"]
    with Sesion() as s:
        assert s.get(Permiso, "PERM_INVENTADO") is None
    # No hay ruta para crear permisos
    assert client.post(f"{RUTA}/permisos", json={"id_permiso": "PERM_X"}, headers=ADMIN).status_code == 405


def test_admin_no_se_quita_el_acceso_a_configuracion(client):
    respuesta = client.put(f"{RUTA}/{roles.ADMIN}/permisos", json={"permisos": [PERMISO_A]}, headers=ADMIN)

    assert respuesta.status_code == 409
    assert client.get(f"{RUTA}/", headers=ADMIN).status_code == 200
    # Con el permiso dentro, sí puede cambiar los demás permisos de su rol
    respuesta = client.put(
        f"{RUTA}/{roles.ADMIN}/permisos", json={"permisos": [PERMISO_CONFIGURACION, PERMISO_A]}, headers=ADMIN
    )
    assert respuesta.status_code == 200


def test_el_acceso_a_configuracion_no_se_da_a_otros_roles(client):
    respuesta = client.put(f"{RUTA}/{roles.OPERARIO}/permisos", json={"permisos": [PERMISO_CONFIGURACION]}, headers=ADMIN)
    assert respuesta.status_code == 400


def test_los_cambios_de_permisos_aplican_sin_reiniciar(client):
    cabeceras = token(roles.OPERARIO)
    assert PERMISO_A not in client.get("/api/v1/auth/permisos", headers=cabeceras).json()["permisos"]

    client.put(f"{RUTA}/{roles.OPERARIO}/permisos", json={"permisos": [PERMISO_A]}, headers=ADMIN)
    assert PERMISO_A in client.get("/api/v1/auth/permisos", headers=cabeceras).json()["permisos"]

    client.put(f"{RUTA}/{roles.OPERARIO}/permisos", json={"permisos": []}, headers=ADMIN)
    assert PERMISO_A not in client.get("/api/v1/auth/permisos", headers=cabeceras).json()["permisos"]


def test_listado_con_permisos_y_usuarios(client):
    por_rol = {r["id_rol"]: r for r in client.get(f"{RUTA}/", headers=ADMIN).json()}

    assert por_rol[roles.ADMIN]["permisos"] == [PERMISO_CONFIGURACION]
    assert por_rol[roles.OPERARIO]["usuarios"] == 1
    assert por_rol["ROL_SIN_USUARIOS"] == {
        "id_rol": "ROL_SIN_USUARIOS", "nombre_rol": "ROL_SIN_USUARIOS", "descripcion": None,
        "permisos": [PERMISO_A], "usuarios": 0,
    }


# --- Eliminar ---------------------------------------------------------------------------------

def test_un_rol_con_usuarios_no_se_elimina(client):
    respuesta = client.delete(f"{RUTA}/{roles.OPERARIO}", headers=ADMIN)

    assert respuesta.status_code == 409
    assert roles.OPERARIO in [r["id_rol"] for r in client.get(f"{RUTA}/", headers=ADMIN).json()]


def test_un_rol_sin_usuarios_se_elimina_y_queda_el_registro(entorno):
    client, Sesion = entorno
    assert client.delete(f"{RUTA}/ROL_SIN_USUARIOS", headers=ADMIN).status_code == 204

    assert "ROL_SIN_USUARIOS" not in [r["id_rol"] for r in client.get(f"{RUTA}/", headers=ADMIN).json()]
    historial = client.get(f"{RUTA}/ROL_SIN_USUARIOS/historial", headers=ADMIN).json()
    assert [(h["id_permiso"], h["accion"]) for h in historial] == [(PERMISO_A, "RETIRADO")]
    with Sesion() as s:
        assert s.query(RolPermiso).filter(RolPermiso.id_rol == "ROL_SIN_USUARIOS").count() == 0


def test_rol_inexistente_responde_404(client):
    assert client.delete(f"{RUTA}/NO_EXISTE", headers=ADMIN).status_code == 404
    assert client.put(f"{RUTA}/NO_EXISTE/permisos", json={"permisos": []}, headers=ADMIN).status_code == 404
