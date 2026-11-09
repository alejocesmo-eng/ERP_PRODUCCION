# tests/test_verificar_logins_sandbox.py
"""
Script verificar_logins_sandbox con un backend simulado (sin red ni base de datos):
tabla de logins, rol devuelto, módulos visibles, bloqueados y sin protección, solo hosts
locales y que la salida no contiene la clave ni los tokens.
"""
import json

import pytest

from scripts import preparar_sandbox, verificar_logins_sandbox as verificador

CLAVE = "clave_demo_de_prueba"
OPENAPI = {
    "paths": {
        "/api/v1/auth/token": {"post": {}},
        "/api/v1/calidad/rnc": {"get": {}},
        "/api/v1/maestros/socios": {"get": {}},
        "/api/v1/planos/{id_plano}": {"get": {}},
        "/api/v1/ventas/cotizaciones/": {"get": {}},
        "/api/v1/costos/oee": {"get": {}},
    }
}


def backend_simulado(fallan=()):
    """Calidad sin protección; maestros bloqueado para OPERARIO; cotizaciones solo ADMIN y
    VENTAS; costos responde 500. Los correos de `fallan` no inician sesión."""

    def peticion(metodo, url, datos=None, cabeceras=None):
        ruta = url.replace("http://127.0.0.1:8000", "")
        if ruta == "/openapi.json":
            return 200, json.dumps(OPENAPI).encode()
        if ruta == "/api/v1/auth/token":
            formulario = dict(p.split("=", 1) for p in datos.decode().split("&"))
            email = formulario["username"].replace("%40", "@")
            if email in fallan or formulario["password"] != CLAVE:
                return 401, b'{"detail": "Credenciales incorrectas"}'
            rol = {e: r for e, _, r in preparar_sandbox.USUARIOS_DEMO}[email]
            return 200, json.dumps({"access_token": f"tok-secreto-{rol}", "rol": rol}).encode()
        autorizacion = (cabeceras or {}).get("Authorization", "")
        rol = autorizacion.replace("Bearer tok-secreto-", "") if autorizacion else None
        if ruta == "/api/v1/calidad/rnc":
            return 200, b"[]"
        if not rol:
            return 401, b""
        if ruta == "/api/v1/maestros/socios":
            return (403, b"") if rol == "OPERARIO" else (200, b"[]")
        if ruta == "/api/v1/ventas/cotizaciones/":
            return (200, b"[]") if rol in ("ADMIN", "VENTAS") else (403, b"")
        return 500, b""

    return peticion


@pytest.fixture
def entorno(monkeypatch):
    monkeypatch.setenv(preparar_sandbox.VARIABLE_CLAVE_DEMO, CLAVE)
    monkeypatch.delenv(verificador.VARIABLE_API, raising=False)


def filas(salida):
    return {linea.split(" | ")[0].lstrip("| "): linea for linea in salida.splitlines() if "@" in linea}


def test_tabla_con_login_rol_y_modulos(entorno, monkeypatch, capsys):
    monkeypatch.setattr(verificador, "peticion", backend_simulado())

    verificador.main()

    salida = capsys.readouterr().out
    tabla = filas(salida)
    assert set(tabla) == {email for email, _, _ in preparar_sandbox.USUARIOS_DEMO}
    ventas = tabla["ventas@sgi.local"]
    assert "| VENTAS | VENTAS | OK |" in ventas
    assert "calidad (sin proteccion)" in ventas and "ventas/cotizaciones" in ventas and "maestros" in ventas
    operario = tabla["operario_1@sgi.local"]
    assert operario.split(" | ")[5] == "maestros, ventas/cotizaciones"
    assert operario.split(" | ")[6].strip(" |") == "costos"
    assert "planos" not in salida  # las rutas con parámetros no se consultan
    assert f"Logins correctos: {len(preparar_sandbox.USUARIOS_DEMO)} de {len(preparar_sandbox.USUARIOS_DEMO)}." in salida


def test_un_login_fallido_se_reporta_y_termina_con_error(entorno, monkeypatch, capsys):
    monkeypatch.setattr(verificador, "peticion", backend_simulado(fallan={"calidad@sgi.local"}))

    with pytest.raises(SystemExit) as salida_error:
        verificador.main()

    assert salida_error.value.code == 1
    assert "FALLO (HTTP 401)" in filas(capsys.readouterr().out)["calidad@sgi.local"]


def test_no_imprime_la_clave_ni_los_tokens(entorno, monkeypatch, capsys):
    monkeypatch.setattr(verificador, "peticion", backend_simulado())

    verificador.main()

    salida = capsys.readouterr()
    texto = salida.out + salida.err
    assert CLAVE not in texto
    assert "tok-secreto" not in texto


def test_sin_clave_no_consulta_el_backend(monkeypatch):
    monkeypatch.delenv(preparar_sandbox.VARIABLE_CLAVE_DEMO, raising=False)

    def sin_red(*args, **kwargs):
        raise AssertionError("No debe consultar el backend sin clave")

    monkeypatch.setattr(verificador, "peticion", sin_red)

    with pytest.raises(SystemExit):
        verificador.main()


@pytest.mark.parametrize("url", ["http://sgi.empresa.example:8000", "https://10.0.0.5"])
def test_solo_admite_backends_locales(entorno, monkeypatch, url):
    monkeypatch.setenv(verificador.VARIABLE_API, url)
    monkeypatch.setattr(verificador, "peticion", backend_simulado())

    with pytest.raises(SystemExit):
        verificador.main()
