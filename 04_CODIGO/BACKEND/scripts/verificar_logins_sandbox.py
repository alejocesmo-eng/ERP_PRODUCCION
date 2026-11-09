"""
Verifica el login de cada usuario de demostracion de sgi_sandbox contra el backend local y
muestra una tabla con el rol que devuelve el login y los modulos que puede ver.

- Usuarios: USUARIOS_DEMO de scripts/preparar_sandbox.py.
- Clave: SGI_SANDBOX_DEMO_PASSWORD (la misma con que se crearon los usuarios demo).
- Backend: SGI_SANDBOX_API_URL, por defecto http://127.0.0.1:8000. Solo se admiten hosts
  locales: el script no se usa contra servidores compartidos ni contra sgi_db.
- Modulos visibles: se consultan, con el token de cada usuario, todas las rutas GET sin
  parametros de ruta que publica el backend (/openapi.json). Un modulo es visible si alguna
  responde 2xx; esta bloqueado si todas responden 401 o 403. Las rutas que tambien responden
  sin token se marcan como "sin proteccion". Solo hace GET: no modifica datos.

No imprime la clave, los tokens ni los hashes.

Uso, desde 04_CODIGO/BACKEND y con el backend apuntando a sgi_sandbox:
    python -m scripts.verificar_logins_sandbox
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from scripts.preparar_sandbox import USUARIOS_DEMO, VARIABLE_CLAVE_DEMO

VARIABLE_API = "SGI_SANDBOX_API_URL"
API_POR_DEFECTO = "http://127.0.0.1:8000"
HOSTS_LOCALES = {"127.0.0.1", "localhost", "::1"}
PREFIJO_API = "/api/v1/"


def fallar(mensaje: str) -> None:
    print(f"ERROR: {mensaje}", file=sys.stderr)
    sys.exit(1)


def url_api() -> str:
    url = os.environ.get(VARIABLE_API, API_POR_DEFECTO).rstrip("/")
    if urllib.parse.urlparse(url).hostname not in HOSTS_LOCALES:
        fallar(f"{VARIABLE_API} debe apuntar a un backend local (127.0.0.1 o localhost).")
    return url


def peticion(metodo: str, url: str, datos: bytes | None = None, cabeceras: dict | None = None) -> tuple[int, bytes]:
    """(codigo HTTP, cuerpo). Los errores HTTP se devuelven como codigo, no como excepcion."""
    solicitud = urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras or {})
    try:
        with urllib.request.urlopen(solicitud, timeout=15) as respuesta:
            return respuesta.status, respuesta.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()
    except urllib.error.URLError as error:
        fallar(f"No se pudo conectar con el backend ({error.reason}). ¿Esta en marcha?")


def modulo_de(ruta: str) -> str:
    partes = ruta[len(PREFIJO_API):].strip("/").split("/")
    if partes[0] in ("ventas", "configuracion") and len(partes) > 1:
        return f"{partes[0]}/{partes[1]}"
    return partes[0]


def rutas_get(base: str) -> dict[str, list[str]]:
    """Rutas GET sin parametros de ruta, agrupadas por modulo (sin /auth)."""
    codigo, cuerpo = peticion("GET", f"{base}/openapi.json")
    if codigo != 200:
        fallar(f"No se pudo leer {base}/openapi.json (HTTP {codigo}).")
    por_modulo: dict[str, list[str]] = {}
    for ruta, operaciones in json.loads(cuerpo).get("paths", {}).items():
        if "get" not in operaciones or "{" in ruta or not ruta.startswith(PREFIJO_API):
            continue
        modulo = modulo_de(ruta)
        if modulo != "auth":
            por_modulo.setdefault(modulo, []).append(ruta)
    return dict(sorted(por_modulo.items()))


def iniciar_sesion(base: str, email: str, clave: str) -> tuple[int, str | None, str | None]:
    """(codigo, token, rol). El token solo se usa en memoria."""
    datos = urllib.parse.urlencode({"username": email, "password": clave}).encode("utf-8")
    codigo, cuerpo = peticion(
        "POST", f"{base}/api/v1/auth/token", datos, {"Content-Type": "application/x-www-form-urlencoded"}
    )
    if codigo != 200:
        return codigo, None, None
    respuesta = json.loads(cuerpo)
    return codigo, respuesta.get("access_token"), respuesta.get("rol")


def estado_modulo(base: str, rutas: list[str], cabeceras: dict) -> str:
    codigos = [peticion("GET", f"{base}{ruta}", cabeceras=cabeceras)[0] for ruta in rutas]
    if any(200 <= codigo < 300 for codigo in codigos):
        return "visible"
    if all(codigo in (401, 403) for codigo in codigos):
        return "bloqueado"
    return "error"


def main() -> None:
    clave = os.environ.get(VARIABLE_CLAVE_DEMO)
    if not clave:
        fallar(f"Defina {VARIABLE_CLAVE_DEMO} en la sesion con la clave de los usuarios demo.")
    base = url_api()
    modulos = rutas_get(base)
    abiertos = {m for m, rutas in modulos.items() if estado_modulo(base, rutas, {}) == "visible"}

    print(f"Backend: {base} | modulos con rutas GET: {len(modulos)} | visibles sin token: {len(abiertos)}")
    print()
    print("| Usuario | Rol esperado | Rol en el login | Login | Modulos visibles | Bloqueados | Con error |")
    print("|---|---|---|---|---|---|---|")
    fallos = 0
    for email, _, rol_esperado in USUARIOS_DEMO:
        codigo, token, rol = iniciar_sesion(base, email, clave)
        if not token:
            fallos += 1
            print(f"| {email} | {rol_esperado} | — | FALLO (HTTP {codigo}) | — | — | — |")
            continue
        if rol != rol_esperado:
            fallos += 1
        cabeceras = {"Authorization": f"Bearer {token}"}
        estados = {m: estado_modulo(base, rutas, cabeceras) for m, rutas in modulos.items()}
        visibles = [m + (" (sin proteccion)" if m in abiertos else "") for m, e in estados.items() if e == "visible"]
        bloqueados = [m for m, e in estados.items() if e == "bloqueado"]
        errores = [m for m, e in estados.items() if e == "error"]
        login = "OK" if rol == rol_esperado else "OK, rol distinto"
        print(
            f"| {email} | {rol_esperado} | {rol} | {login} | {', '.join(visibles) or '—'} | "
            f"{', '.join(bloqueados) or '—'} | {', '.join(errores) or '—'} |"
        )
    print()
    print(f"Logins correctos: {len(USUARIOS_DEMO) - fallos} de {len(USUARIOS_DEMO)}.")
    if fallos:
        sys.exit(1)


if __name__ == "__main__":
    main()
