# tests/test_preparar_sandbox.py
"""
Script preparar_sandbox sin base de datos: nombres permitidos, lista de migraciones que
aplica y confirmación antes de regenerar. La creación de sgi_sandbox la ejecuta el usuario.
"""
import pytest

from scripts import _pg_pruebas, preparar_sandbox


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

    preparar_sandbox.main()

    salida = capsys.readouterr()
    texto = salida.out + salida.err
    assert "sgi_sandbox lista" in texto
    assert "clave_que_no_debe_aparecer" not in texto
    assert "usuario_secreto" not in texto
