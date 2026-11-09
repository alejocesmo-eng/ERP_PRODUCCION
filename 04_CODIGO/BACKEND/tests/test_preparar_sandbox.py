# tests/test_preparar_sandbox.py
"""
Script preparar_sandbox sin base de datos: nombres permitidos, lista de migraciones que
aplica y confirmación antes de regenerar. La creación de sgi_sandbox la ejecuta el usuario.
"""
import re
from pathlib import Path

import bcrypt
import pytest

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

class CursorFalso:
    """Registra las sentencias; ON CONFLICT DO NOTHING se simula con los correos ya existentes."""

    def __init__(self, existentes=()):
        self.existentes = set(existentes)
        self.sentencias = []
        self.rowcount = 0

    def executemany(self, sentencia, filas):
        self.sentencias.append((sentencia, list(filas)))

    def execute(self, sentencia, parametros=None):
        self.sentencias.append((sentencia, parametros))
        self.rowcount = 0 if parametros and parametros[1] in self.existentes else 1


class ConexionFalsa:
    def __init__(self, cursor):
        self._cursor = cursor
        self.cerrada = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.cerrada = True


def test_los_usuarios_demo_cubren_los_botones_de_dev_mode_y_un_usuario_por_rol():
    login = Path(__file__).resolve().parents[2] / "FRONTEND" / "src" / "views" / "LoginView.jsx"
    botones = set(re.findall(r"email: '([^']+)'", login.read_text(encoding="utf-8")))
    correos = {email for email, _, _ in preparar_sandbox.USUARIOS_DEMO}
    roles_usuarios = {rol for _, _, rol in preparar_sandbox.USUARIOS_DEMO}

    assert botones and botones <= correos
    assert {"ADMIN", "DISENO", "VENTAS", "PRODUCCION", "ALMACEN", "CALIDAD"} <= roles_usuarios
    assert roles_usuarios <= {rol for rol, _ in preparar_sandbox.ROLES_DEMO}


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


def test_crea_solo_los_que_faltan_y_no_imprime_la_clave(monkeypatch, capsys):
    monkeypatch.setenv(preparar_sandbox.VARIABLE_CLAVE_DEMO, CLAVE_DEMO)
    cursor = CursorFalso(existentes={"admin@sgi.com", "ventas@sgi.local"})
    conexion = ConexionFalsa(cursor)
    monkeypatch.setattr(preparar_sandbox, "conectar", lambda base: conexion)

    preparar_sandbox._cargar_usuarios_demo()

    salida = capsys.readouterr().out
    total = len(preparar_sandbox.USUARIOS_DEMO)
    assert f"{total - 2} creados y 2 ya existian" in salida
    assert CLAVE_DEMO not in salida
    assert conexion.cerrada
    roles, filas_roles = cursor.sentencias[0]
    assert "ON CONFLICT (id_rol) DO NOTHING" in roles and len(filas_roles) == len(preparar_sandbox.ROLES_DEMO)
    inserciones = cursor.sentencias[1:]
    assert all("ON CONFLICT (email) DO NOTHING" in sentencia for sentencia, _ in inserciones)
    assert all(CLAVE_DEMO not in parametros for _, parametros in inserciones)

def test_los_usuarios_demo_incluyen_operario_y_mantenimiento():
    roles = {rol for _, _, rol in preparar_sandbox.USUARIOS_DEMO}

    assert {"OPERARIO", "MANTENIMIENTO"} <= roles
    assert len({email for email, _, _ in preparar_sandbox.USUARIOS_DEMO}) == len(preparar_sandbox.USUARIOS_DEMO)


class CursorRestablecer(CursorFalso):
    """INSERT: 0 filas si el correo ya existe. UPDATE: 1 fila por correo existente."""

    def execute(self, sentencia, parametros=None):
        self.sentencias.append((sentencia, parametros))
        if sentencia.startswith("INSERT INTO usuarios"):
            self.rowcount = 0 if parametros[1] in self.existentes else 1
        else:
            self.rowcount = 1 if parametros[-1] in self.existentes else 0


def test_restablecer_actualiza_solo_los_usuarios_demo_existentes(monkeypatch, capsys):
    monkeypatch.setenv(preparar_sandbox.VARIABLE_CLAVE_DEMO, CLAVE_DEMO)
    existentes = {"admin@sgi.com", "dibujante_1@sgi.local"}
    cursor = CursorRestablecer(existentes=existentes)
    monkeypatch.setattr(preparar_sandbox, "conectar", lambda base: ConexionFalsa(cursor))

    preparar_sandbox._cargar_usuarios_demo(restablecer=True)

    actualizaciones = [(s, p) for s, p in cursor.sentencias if s.startswith("UPDATE usuarios")]
    assert {p[-1] for _, p in actualizaciones} == existentes
    for _, (hash_clave, _, rol, email) in actualizaciones:
        assert bcrypt.checkpw(CLAVE_DEMO.encode("utf-8"), hash_clave.encode("utf-8"))
        assert rol == {e: r for e, _, r in preparar_sandbox.USUARIOS_DEMO}[email]
    salida = capsys.readouterr().out
    assert f"{len(preparar_sandbox.USUARIOS_DEMO) - 2} creados y 2 restablecidos" in salida
    assert CLAVE_DEMO not in salida


def test_sin_restablecer_no_actualiza_usuarios_existentes(monkeypatch, capsys):
    monkeypatch.setenv(preparar_sandbox.VARIABLE_CLAVE_DEMO, CLAVE_DEMO)
    cursor = CursorRestablecer(existentes={"admin@sgi.com"})
    monkeypatch.setattr(preparar_sandbox, "conectar", lambda base: ConexionFalsa(cursor))

    preparar_sandbox._cargar_usuarios_demo()

    assert not any(s.startswith("UPDATE") for s, _ in cursor.sentencias)
    assert "1 ya existian" in capsys.readouterr().out


def test_restablecer_exige_usuarios_demo(monkeypatch):
    monkeypatch.setattr("sys.argv", ["preparar_sandbox", "--restablecer-claves"])

    with pytest.raises(SystemExit):
        preparar_sandbox.main()


def test_usuarios_demo_con_restablecer_no_crea_ni_migra_la_base(monkeypatch):
    llamadas = []
    monkeypatch.setattr("sys.argv", ["preparar_sandbox", "--usuarios-demo", "--restablecer-claves"])
    monkeypatch.setattr(preparar_sandbox, "conectar_admin", lambda: ConexionFalsa(CursorExiste()))
    monkeypatch.setattr(preparar_sandbox, "existe_base", lambda cursor, nombre: True)
    monkeypatch.setattr(preparar_sandbox, "_crear_sandbox", lambda regenerar: llamadas.append("crear"))
    monkeypatch.setattr(preparar_sandbox, "_aplicar_migraciones", lambda: llamadas.append("migrar"))
    monkeypatch.setattr(preparar_sandbox, "_cargar_usuarios_demo", lambda restablecer=False: llamadas.append(("usuarios", restablecer)))

    preparar_sandbox.main()

    assert llamadas == [("usuarios", True)]


class CursorExiste:
    pass

