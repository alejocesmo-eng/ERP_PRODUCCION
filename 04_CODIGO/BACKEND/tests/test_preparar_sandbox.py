# tests/test_preparar_sandbox.py
"""
Script preparar_sandbox sin base de datos: nombres permitidos, lista de migraciones que
aplica, confirmación antes de regenerar y usuarios de demostración (los 18 de
reglas/usuarios-demo.md, iguales al acceso rápido del login, y cuentas anteriores
desactivadas sin borrarlas). La creación de sgi_sandbox la ejecuta el usuario.
"""
import re
from pathlib import Path

import bcrypt
import pytest

from app.core import roles
from scripts import _pg_pruebas, preparar_sandbox

CLAVE_DEMO = "clave_demo_de_prueba"


def test_sgi_sandbox_solo_se_acepta_de_forma_explicita():
    assert _pg_pruebas.validar_nombre("sgi_sandbox", permitir_sandbox=True) == "sgi_sandbox"
    with pytest.raises(SystemExit):
        _pg_pruebas.validar_nombre("sgi_sandbox")


@pytest.mark.parametrize("nombre", ["sgi_db", "SGI_DB", "sgi_sandbox_2", "postgres"])
def test_el_permiso_de_sandbox_no_abre_otras_bases(nombre):
    with pytest.raises(SystemExit):
        _pg_pruebas.validar_nombre(nombre, permitir_sandbox=True)


def test_las_copias_sgi_test_siguen_permitidas():
    assert _pg_pruebas.validar_nombre("sgi_test_copia") == "sgi_test_copia"


def test_aplica_las_migraciones_desde_la_17_en_orden_numerico():
    nombres = [ruta.name for ruta in preparar_sandbox.migraciones_sandbox()]

    numeros = [int(nombre[:2]) for nombre in nombres]
    assert numeros[0] == 17
    assert numeros == sorted(numeros)
    assert {"21_MIGRACION_PLANOS_HISTORIAL.sql", "22_MIGRACION_BUSQUEDA_PRODUCTOS.sql"} <= set(nombres)
    assert not any("REVERSION" in nombre for nombre in nombres)
    assert all(ruta.is_file() for ruta in preparar_sandbox.migraciones_sandbox())


@pytest.mark.parametrize(("respuesta", "esperado"), [
    ("sgi_sandbox", True),
    ("  sgi_sandbox  ", True),
    ("si", False),
    ("", False),
    ("SGI_SANDBOX", False),
])
def test_regenerar_exige_escribir_el_nombre_de_la_base(respuesta, esperado):
    preguntas = []

    def leer(pregunta):
        preguntas.append(pregunta)
        return respuesta

    assert preparar_sandbox.confirmar_regeneracion(leer) is esperado
    assert "sgi_sandbox" in preguntas[0]


def test_el_script_no_imprime_credenciales(capsys, monkeypatch):
    # main() con todas las operaciones de base sustituidas: solo se revisa lo que imprime
    monkeypatch.setenv("SGI_TEST_PG_ADMIN_URL", "postgresql://usuario_secreto@localhost:5432/postgres")
    monkeypatch.setenv("PGPASSWORD", "clave_que_no_debe_aparecer")
    monkeypatch.setattr("sys.argv", ["preparar_sandbox"])
    monkeypatch.setattr(preparar_sandbox, "_crear_sandbox", lambda regenerar: print("Base sgi_sandbox creada."))
    monkeypatch.setattr(preparar_sandbox, "_aplicar_migraciones", lambda: None)
    monkeypatch.setattr(preparar_sandbox, "_verificar", lambda: None)
    monkeypatch.setattr(preparar_sandbox, "_cargar_usuarios_demo", lambda: None)

    preparar_sandbox.main()

    salida = capsys.readouterr()
    texto = salida.out + salida.err
    assert "sgi_sandbox lista" in texto
    assert "clave_que_no_debe_aparecer" not in texto
    assert "usuario_secreto" not in texto


# --- Usuarios de demostración ---

ACCESOS_DEMO = Path(__file__).resolve().parents[2] / "FRONTEND" / "src" / "config" / "accesosDemo.js"
LOGIN = Path(__file__).resolve().parents[2] / "FRONTEND" / "src" / "views" / "LoginView.jsx"
REUTILIZADAS = {"ventas@sgi.local", "almacen@sgi.local", "mantenimiento@sgi.local"}


class CursorFalso:
    """Registra las sentencias. INSERT: 0 filas si el correo ya existe. UPDATE de un usuario demo:
    1 fila si existe. UPDATE de desactivación: tantas filas como cuentas anteriores activas."""

    def __init__(self, existentes=(), roles=None, anteriores_activas=()):
        self.existentes = set(existentes)
        self.roles = set(roles_demo() if roles is None else roles)
        self.anteriores_activas = set(anteriores_activas)
        self.sentencias = []
        self.rowcount = 0
        self._filas = []

    def execute(self, sentencia, parametros=None):
        self.sentencias.append((sentencia, parametros))
        if sentencia.startswith("SELECT id_rol FROM roles"):
            self._filas = [(rol,) for rol in parametros[0] if rol in self.roles]
        elif sentencia.startswith("INSERT INTO usuarios"):
            self.rowcount = 0 if parametros[1] in self.existentes else 1
        elif "activo = FALSE" in sentencia:
            self.rowcount = len(self.anteriores_activas & set(parametros[0]))
        else:
            self.rowcount = 1 if parametros[-1] in self.existentes else 0

    def fetchall(self):
        return self._filas


class ConexionFalsa:
    def __init__(self, cursor):
        self._cursor = cursor
        self.cerrada = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.cerrada = True


def roles_demo():
    return {rol for _, _, rol in preparar_sandbox.USUARIOS_DEMO}


def actualizaciones(cursor):
    return [(s, p) for s, p in cursor.sentencias if s.startswith("UPDATE usuarios SET") and "activo = FALSE" not in s]


def test_los_18_usuarios_demo_son_los_de_usuarios_demo_md_uno_por_rol():
    correos = [email for email, _, _ in preparar_sandbox.USUARIOS_DEMO]

    assert len(correos) == len(set(correos)) == 18
    assert sorted(rol for _, _, rol in preparar_sandbox.USUARIOS_DEMO) == sorted(roles.ROLES_CATALOGO)
    assert all(email.endswith("@sgi.local") for email in correos)
    assert REUTILIZADAS <= set(correos)


def test_el_acceso_rapido_del_login_usa_exactamente_los_18_usuarios_demo():
    botones = re.findall(r"email: '([^']+)'", ACCESOS_DEMO.read_text(encoding="utf-8"))

    assert sorted(botones) == sorted(email for email, _, _ in preparar_sandbox.USUARIOS_DEMO)
    # El login no repite correos: los toma del módulo, solo en desarrollo
    login = LOGIN.read_text(encoding="utf-8")
    assert "@sgi.local" not in login
    assert "import.meta.env.DEV ? ACCESOS_DEMO : []" in login


def test_las_cuentas_anteriores_se_desactivan_menos_el_admin_tecnico():
    anteriores = set(preparar_sandbox.CUENTAS_ANTERIORES)

    assert len(anteriores) == 6
    assert "admin@sgi.com" not in anteriores
    assert not anteriores & {email for email, _, _ in preparar_sandbox.USUARIOS_DEMO}


def test_las_filas_guardan_hash_bcrypt_y_nunca_la_clave():
    filas = preparar_sandbox.filas_usuarios_demo(CLAVE_DEMO)

    assert len(filas) == len(preparar_sandbox.USUARIOS_DEMO)
    for _, _, hash_clave, _, _ in filas:
        assert hash_clave != CLAVE_DEMO and hash_clave.startswith("$2")
        assert bcrypt.checkpw(CLAVE_DEMO.encode("utf-8"), hash_clave.encode("utf-8"))
    assert len({hash_clave for _, _, hash_clave, _, _ in filas}) == len(filas)


def test_sin_variable_de_clave_omite_los_usuarios_sin_conectar(monkeypatch, capsys):
    monkeypatch.delenv(preparar_sandbox.VARIABLE_CLAVE_DEMO, raising=False)

    def no_conectar(base):
        raise AssertionError("No debe conectar sin clave de demostración")

    monkeypatch.setattr(preparar_sandbox, "conectar", no_conectar)

    preparar_sandbox._cargar_usuarios_demo()

    assert "omitidos" in capsys.readouterr().out


def test_sin_la_migracion_25_se_detiene_antes_de_crear_usuarios(monkeypatch):
    monkeypatch.setenv(preparar_sandbox.VARIABLE_CLAVE_DEMO, CLAVE_DEMO)
    cursor = CursorFalso(roles={"ADMIN", "VENTAS", "ALMACEN", "MANTENIMIENTO", "OPERARIO"})
    monkeypatch.setattr(preparar_sandbox, "conectar", lambda base: ConexionFalsa(cursor))

    with pytest.raises(SystemExit):
        preparar_sandbox._cargar_usuarios_demo()

    assert not any(s.startswith(("INSERT", "UPDATE")) for s, _ in cursor.sentencias)


def test_crea_los_que_faltan_reutiliza_los_existentes_y_desactiva_los_anteriores(monkeypatch, capsys):
    monkeypatch.setenv(preparar_sandbox.VARIABLE_CLAVE_DEMO, CLAVE_DEMO)
    cursor = CursorFalso(existentes=REUTILIZADAS, anteriores_activas={"dibujante_1@sgi.local", "calidad@sgi.local"})
    conexion = ConexionFalsa(cursor)
    bases = []
    monkeypatch.setattr(preparar_sandbox, "conectar", lambda base: bases.append(base) or conexion)

    preparar_sandbox._cargar_usuarios_demo()

    salida = capsys.readouterr().out
    assert bases == ["sgi_sandbox"]
    assert "15 creados y 3 actualizados" in salida
    assert "desactivadas (no borradas): 2" in salida
    assert CLAVE_DEMO not in salida
    assert conexion.cerrada
    # Los reutilizados toman nombre, rol y activo de la tabla, sin tocar la clave
    nombres = {email: (nombre, rol) for email, nombre, rol in preparar_sandbox.USUARIOS_DEMO}
    cambios = actualizaciones(cursor)
    assert {p[-1] for _, p in cambios} == REUTILIZADAS
    for sentencia, (nombre, rol, email) in cambios:
        assert "password_hash" not in sentencia
        assert (nombre, rol) == nombres[email]
    # Desactivar, nunca borrar; solo las cuentas anteriores
    assert not any("DELETE" in s for s, _ in cursor.sentencias)
    desactivacion = [p for s, p in cursor.sentencias if "activo = FALSE" in s]
    assert desactivacion == [(list(preparar_sandbox.CUENTAS_ANTERIORES),)]
    assert all(CLAVE_DEMO not in str(p) for _, p in cursor.sentencias)


def test_restablecer_devuelve_tambien_la_clave(monkeypatch, capsys):
    monkeypatch.setenv(preparar_sandbox.VARIABLE_CLAVE_DEMO, CLAVE_DEMO)
    cursor = CursorFalso(existentes={"ventas@sgi.local", "admin@sgi.local"})
    monkeypatch.setattr(preparar_sandbox, "conectar", lambda base: ConexionFalsa(cursor))

    preparar_sandbox._cargar_usuarios_demo(restablecer=True)

    cambios = actualizaciones(cursor)
    assert {p[-1] for _, p in cambios} == {"ventas@sgi.local", "admin@sgi.local"}
    for _, (hash_clave, _, rol, email) in cambios:
        assert bcrypt.checkpw(CLAVE_DEMO.encode("utf-8"), hash_clave.encode("utf-8"))
        assert rol == {e: r for e, _, r in preparar_sandbox.USUARIOS_DEMO}[email]
    salida = capsys.readouterr().out
    assert "16 creados y 2 actualizados (clave, nombre, rol y activo)" in salida
    assert CLAVE_DEMO not in salida


def test_restablecer_exige_usuarios_demo(monkeypatch):
    monkeypatch.setattr("sys.argv", ["preparar_sandbox", "--restablecer-claves"])

    with pytest.raises(SystemExit):
        preparar_sandbox.main()


def test_base_exige_usuarios_demo(monkeypatch):
    monkeypatch.setattr("sys.argv", ["preparar_sandbox", "--base", "sgi_test_run"])

    with pytest.raises(SystemExit):
        preparar_sandbox.main()


@pytest.mark.parametrize("base", ["sgi_db", "SGI_DB", "postgres", "sgi_test_template"])
def test_usuarios_demo_rechaza_bases_que_no_son_de_prueba(monkeypatch, base):
    monkeypatch.setattr("sys.argv", ["preparar_sandbox", "--usuarios-demo", "--base", base])
    monkeypatch.setattr(preparar_sandbox, "conectar_admin", lambda: pytest.fail("No debe conectar"))

    with pytest.raises(SystemExit):
        preparar_sandbox.main()


@pytest.mark.parametrize(("argumentos", "esperado"), [
    (["--usuarios-demo", "--restablecer-claves"], (True, "sgi_sandbox")),
    (["--usuarios-demo", "--base", "sgi_test_run"], (False, "sgi_test_run")),
])
def test_usuarios_demo_no_crea_ni_migra_la_base(monkeypatch, argumentos, esperado):
    llamadas = []
    monkeypatch.setattr("sys.argv", ["preparar_sandbox", *argumentos])
    monkeypatch.setattr(preparar_sandbox, "conectar_admin", lambda: ConexionFalsa(CursorExiste()))
    monkeypatch.setattr(preparar_sandbox, "existe_base", lambda cursor, nombre: True)
    monkeypatch.setattr(preparar_sandbox, "_crear_sandbox", lambda regenerar: llamadas.append("crear"))
    monkeypatch.setattr(preparar_sandbox, "_aplicar_migraciones", lambda: llamadas.append("migrar"))
    monkeypatch.setattr(
        preparar_sandbox, "_cargar_usuarios_demo",
        lambda restablecer=False, base="sgi_sandbox": llamadas.append((restablecer, base)),
    )

    preparar_sandbox.main()

    assert llamadas == [esperado]


class CursorExiste:
    pass

def test_el_rechazo_en_win1252_se_lee_sin_mostrar_usuario_ni_base(capsys, monkeypatch):
    # PostgreSQL en español sobre Windows responde antes de autenticar en WIN1252 y psycopg2
    # lanza UnicodeDecodeError (0xf3, 0xab) en lugar del mensaje
    crudo = "FATAL:  la autentificación password falló para el usuario «usuario_secreto»".encode("cp1252")

    def connect(**_):
        posicion = crudo.index(0xF3)
        raise UnicodeDecodeError("utf-8", crudo, posicion, posicion + 1, "invalid continuation byte")

    monkeypatch.setenv("SGI_TEST_PG_ADMIN_URL", "postgresql://usuario_secreto@localhost:5432/postgres")
    monkeypatch.setattr(_pg_pruebas.psycopg2, "connect", connect)

    with pytest.raises(SystemExit):
        _pg_pruebas.conectar("sgi_sandbox")

    error = capsys.readouterr().err
    assert "la autentificación password falló para el usuario [oculto]" in error
    assert "usuario_secreto" not in error
