"""
Prepara la base local sgi_sandbox para pruebas manuales de la aplicacion:

1. Crea sgi_sandbox desde la plantilla sgi_test_template (CREATE DATABASE ... TEMPLATE).
2. Aplica en orden las migraciones 05_BASE_DATOS/NN_MIGRACION_*.sql desde la 17. La plantilla
   se construye con create_all, que no instala triggers, extensiones, funciones ni indices
   de expresion (migraciones 21 y 22), y puede ser anterior a los modelos de 18 a 21.
   Todas son idempotentes.
3. Verifica el trigger del historial de planos, las extensiones pg_trgm y unaccent y la
   funcion sgi_normalizar.
4. Datos de demostracion: crea los usuarios de prueba que falten (uno por rol, con los
   correos de los botones "Acceso de Pruebas (Dev Mode)" del login) y sus roles. Los que
   ya existen no se tocan. La clave de demostracion sale de SGI_SANDBOX_DEMO_PASSWORD y se
   guarda con bcrypt; sin esa variable se omite este paso.

Credenciales solo por variables de entorno, como el resto de scripts (ADR-005):
SGI_TEST_PG_ADMIN_URL (sin clave) y PGPASSWORD. El script no imprime ni guarda credenciales.

Si sgi_sandbox ya existe se detiene; con --regenerar la elimina y la vuelve a crear despues
de pedir confirmacion escribiendo su nombre.

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.preparar_sandbox
    python -m scripts.preparar_sandbox --regenerar
    python -m scripts.preparar_sandbox --usuarios-demo   # solo usuarios que falten
"""
import argparse
import os
import re
import sys
import uuid
from pathlib import Path

import bcrypt
from psycopg2 import errors, sql

from scripts._pg_pruebas import (
    PLANTILLA,
    SANDBOX,
    conectar,
    conectar_admin,
    existe_base,
    fallar,
    identificador,
    sesiones_activas,
    validar_nombre,
)

RUTA_BASE_DATOS = Path(__file__).resolve().parents[3] / "05_BASE_DATOS"
PRIMERA_MIGRACION = 17
_MIGRACION = re.compile(r"^(\d{2})_MIGRACION_.+\.sql$")

VERIFICACIONES = (
    (
        "Trigger append-only del historial de planos (migracion 21)",
        "SELECT 1 FROM pg_trigger WHERE tgname = 'trg_planos_historial_inmutable'",
    ),
    ("Extension pg_trgm (migracion 22)", "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"),
    ("Extension unaccent (migracion 22)", "SELECT 1 FROM pg_extension WHERE extname = 'unaccent'"),
    ("Funcion sgi_normalizar (migracion 22)", "SELECT 1 FROM pg_proc WHERE proname = 'sgi_normalizar'"),
)


VARIABLE_CLAVE_DEMO = "SGI_SANDBOX_DEMO_PASSWORD"
# Roles que usan los usuarios de demostracion (se crean solo si faltan; FK usuarios.id_rol)
ROLES_DEMO = (
    ("ADMIN", "Administrador General"),
    ("JEFE_ING", "Jefe de Ingeniería"),
    ("DISENO", "Dibujante"),
    ("VENTAS", "Ventas"),
    ("PRODUCCION", "Líder de Producción"),
    ("ALMACEN", "Almacén y Compras"),
    ("CALIDAD", "Calidad"),
)
# Mismos correos que cargar_semilla.py y los botones de Dev Mode de LoginView.jsx
USUARIOS_DEMO = (
    ("admin@sgi.com", "Administrador SGI", "ADMIN"),
    ("jefe_diseno@sgi.local", "Roberto Méndez - Jefe Diseño", "JEFE_ING"),
    ("dibujante_1@sgi.local", "Carlos Ruiz - Dibujante 1", "DISENO"),
    ("dibujante_2@sgi.local", "Ana María Silva - Dibujante 2", "DISENO"),
    ("ventas@sgi.local", "Laura Gómez - Ventas", "VENTAS"),
    ("lider_produccion@sgi.local", "Jorge Méndez - Líder Prod", "PRODUCCION"),
    ("almacen@sgi.local", "Andrés Torres - Almacén", "ALMACEN"),
    ("calidad@sgi.local", "Paula Rojas - Calidad", "CALIDAD"),
)


def filas_usuarios_demo(clave: str) -> list[tuple]:
    """(id_usuario, email, hash bcrypt, nombre, rol) por usuario; bcrypt con 12 rondas como la app."""
    return [
        (str(uuid.uuid4()), email, bcrypt.hashpw(clave.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8"), nombre, rol)
        for email, nombre, rol in USUARIOS_DEMO
    ]


def migraciones_sandbox() -> list[Path]:
    """Migraciones NN_MIGRACION_*.sql desde la 17, en orden numerico."""
    encontradas = []
    for ruta in RUTA_BASE_DATOS.glob("*_MIGRACION_*.sql"):
        coincidencia = _MIGRACION.match(ruta.name)
        if coincidencia and int(coincidencia.group(1)) >= PRIMERA_MIGRACION:
            encontradas.append((int(coincidencia.group(1)), ruta))
    return [ruta for _, ruta in sorted(encontradas)]


def confirmar_regeneracion(leer=input) -> bool:
    """Pide escribir el nombre de la base; cualquier otra respuesta cancela."""
    if leer is input and not sys.stdin.isatty():
        fallar("--regenerar necesita confirmacion interactiva: ejecute el script desde una terminal.")
    respuesta = leer(f"Se eliminara {SANDBOX} y todos sus datos. Escriba {SANDBOX} para confirmar: ")
    return respuesta.strip() == SANDBOX


def _crear_sandbox(regenerar: bool) -> None:
    admin = conectar_admin()
    try:
        cur = admin.cursor()
        if not existe_base(cur, PLANTILLA):
            fallar(f"No existe la plantilla {PLANTILLA}. Ejecute: python -m scripts.preparar_plantilla_pruebas")
        if existe_base(cur, SANDBOX):
            if not regenerar:
                fallar(f"La base {SANDBOX} ya existe. Use --regenerar para eliminarla y crearla de nuevo.")
            if not confirmar_regeneracion():
                fallar("Regeneracion cancelada: no se modifico nada.")
            activas = sesiones_activas(cur, SANDBOX)
            if activas:
                fallar(
                    f"{SANDBOX} tiene {activas} conexion(es) activa(s). Detenga el backend y cierre "
                    "psql o pgAdmin sobre esa base antes de regenerarla."
                )
            cur.execute(sql.SQL("DROP DATABASE {}").format(identificador(SANDBOX)))
            print(f"Base {SANDBOX} eliminada.")
        try:
            cur.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(identificador(SANDBOX), identificador(PLANTILLA)))
        except errors.ObjectInUse:
            fallar(
                f"No se puede copiar {PLANTILLA}: tiene {sesiones_activas(cur, PLANTILLA)} conexion(es) activa(s). "
                "Cierre las sesiones abiertas sobre la plantilla y reintente."
            )
        print(f"Base {SANDBOX} creada desde {PLANTILLA}.")
    finally:
        admin.close()


def _aplicar_migraciones() -> None:
    conexion = conectar(SANDBOX)
    try:
        cur = conexion.cursor()
        for ruta in migraciones_sandbox():
            try:
                cur.execute(ruta.read_text(encoding="utf-8-sig"))
            except Exception as error:
                # Primera linea del error de PostgreSQL (mensaje SQL; libpq no incluye la clave)
                causa = (str(error).strip().splitlines() or [error.__class__.__name__])[0]
                fallar(
                    f"Fallo la migracion {ruta.name}: {causa}. {SANDBOX} quedo a medio migrar; "
                    "corrija la causa y vuelva a crearla con --regenerar."
                )
            print(f"Migracion aplicada: {ruta.name}")
    finally:
        conexion.close()


def _verificar() -> None:
    conexion = conectar(SANDBOX)
    try:
        cur = conexion.cursor()
        faltantes = []
        for descripcion, consulta in VERIFICACIONES:
            cur.execute(consulta)
            if cur.fetchone() is None:
                faltantes.append(descripcion)
        if faltantes:
            fallar("Verificacion incompleta en sgi_sandbox: " + "; ".join(faltantes))
        print("Verificacion correcta: historial append-only y busqueda de productos instalados.")
    finally:
        conexion.close()


def _cargar_usuarios_demo() -> None:
    clave = os.environ.get(VARIABLE_CLAVE_DEMO)
    if not clave:
        print(
            f"Usuarios de demostracion omitidos: defina {VARIABLE_CLAVE_DEMO} en la sesion "
            "(la misma clave de los botones de Dev Mode si quiere usarlos) y ejecute "
            "python -m scripts.preparar_sandbox --usuarios-demo."
        )
        return
    conexion = conectar(SANDBOX)
    try:
        cur = conexion.cursor()
        cur.executemany(
            "INSERT INTO roles (id_rol, nombre_rol) VALUES (%s, %s) ON CONFLICT (id_rol) DO NOTHING",
            ROLES_DEMO,
        )
        creados = 0
        for fila in filas_usuarios_demo(clave):
            cur.execute(
                "INSERT INTO usuarios (id_usuario, email, password_hash, nombre_completo, id_rol, activo, creado_en) "
                "VALUES (%s, %s, %s, %s, %s, TRUE, now()) ON CONFLICT (email) DO NOTHING",
                fila,
            )
            creados += cur.rowcount
        print(
            f"Usuarios de demostracion: {creados} creados y {len(USUARIOS_DEMO) - creados} ya existian "
            "(los existentes no se modifican)."
        )
    finally:
        conexion.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Prepara {SANDBOX} desde {PLANTILLA} con las migraciones recientes.")
    parser.add_argument("--regenerar", action="store_true", help=f"Elimina {SANDBOX} (con confirmacion) y la crea de nuevo.")
    parser.add_argument(
        "--usuarios-demo", action="store_true",
        help=f"Solo crea los usuarios de demostracion que falten en {SANDBOX} ya existente.",
    )
    argumentos = parser.parse_args()
    validar_nombre(SANDBOX, permitir_sandbox=True)

    if argumentos.usuarios_demo:
        admin = conectar_admin()
        try:
            if not existe_base(admin.cursor(), SANDBOX):
                fallar(f"No existe {SANDBOX}. Creela primero con: python -m scripts.preparar_sandbox")
        finally:
            admin.close()
        _cargar_usuarios_demo()
        return

    _crear_sandbox(argumentos.regenerar)
    _aplicar_migraciones()
    _verificar()
    _cargar_usuarios_demo()
    print(
        f"{SANDBOX} lista. Para el backend use como DATABASE_URL la conexion de SGI_TEST_PG_ADMIN_URL "
        f"con la base {SANDBOX}; la clave sigue solo en PGPASSWORD."
    )


if __name__ == "__main__":
    main()
