"""
Prepara la base local sgi_sandbox para pruebas manuales de la aplicacion:

1. Crea sgi_sandbox desde la plantilla sgi_test_template (CREATE DATABASE ... TEMPLATE).
2. Aplica en orden las migraciones 05_BASE_DATOS/NN_MIGRACION_*.sql desde la 17. La plantilla
   se construye con create_all, que no instala triggers, extensiones, funciones ni indices
   de expresion (migraciones 21 y 22), y puede ser anterior a los modelos de 18 a 21.
   Todas son idempotentes.
3. Verifica el trigger del historial de planos, las extensiones pg_trgm y unaccent y la
   funcion sgi_normalizar.
4. Datos de demostracion: los 16 usuarios de reglas/usuarios-demo.md (uno por rol, los mismos
   del acceso rapido de Dev Mode del login). Crea los que falten; a los que ya existen les
   devuelve el nombre, el rol y el estado activo de la tabla, sin tocar su clave salvo con
   --restablecer-claves. Desactiva (no borra) las cuentas anteriores de cargar_semilla.py que
   no son de demostracion; admin@sgi.com sigue activo como ADMIN tecnico. Los roles los crea
   la migracion 25. La clave sale de SGI_SANDBOX_DEMO_PASSWORD y se guarda con bcrypt; sin
   esa variable se omite este paso.

Credenciales solo por variables de entorno, como el resto de scripts (ADR-005):
SGI_TEST_PG_ADMIN_URL (sin clave) y PGPASSWORD. El script no imprime ni guarda credenciales.

Si sgi_sandbox ya existe se detiene; con --regenerar la elimina y la vuelve a crear despues
de pedir confirmacion escribiendo su nombre.

Uso, desde 04_CODIGO/BACKEND:
    python -m scripts.preparar_sandbox
    python -m scripts.preparar_sandbox --regenerar
    python -m scripts.preparar_sandbox --usuarios-demo   # solo los usuarios de demostracion
    python -m scripts.preparar_sandbox --usuarios-demo --restablecer-claves
        # ademas devuelve a los usuarios demo existentes su clave
    python -m scripts.preparar_sandbox --usuarios-demo --base sgi_test_run
        # los mismos usuarios en una copia sgi_test_* (para probar antes que en sgi_sandbox)
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
    (
        "Estado EMITIDA en cotizaciones.estado (migracion 23)",
        "SELECT 1 FROM pg_attribute a JOIN pg_enum e ON e.enumtypid = a.atttypid "
        "WHERE a.attrelid = 'public.cotizaciones'::regclass AND a.attname = 'estado' AND e.enumlabel = 'EMITIDA' "
        "UNION ALL SELECT 1 FROM pg_constraint WHERE conname = 'chk_cotizaciones_estado' "
        "AND pg_get_constraintdef(oid) LIKE '%EMITIDA%'",
    ),
    (
        "codigo_socio = NIT solo numeros en socios_negocio (migracion 24)",
        "SELECT 1 FROM pg_constraint WHERE conrelid = 'public.socios_negocio'::regclass "
        "AND conname = 'ck_socios_negocio_codigo_nit'",
    ),
    (
        "PERM_OP_LIBERAR solo en LIDER_DISENO y DIBUJANTE (migracion 25)",
        "SELECT 1 FROM rol_permisos WHERE id_permiso = 'PERM_OP_LIBERAR' "
        "HAVING count(*) = 2 AND bool_and(id_rol IN ('LIDER_DISENO', 'DIBUJANTE'))",
    ),
    (
        "Moneda y condiciones de pago de la cotizacion (migracion 26)",
        "SELECT 1 FROM pg_attribute WHERE attrelid = 'public.cotizaciones'::regclass AND attname = 'moneda' "
        "AND EXISTS (SELECT 1 FROM condiciones_pago HAVING count(*) >= 7)",
    ),
)


VARIABLE_CLAVE_DEMO = "SGI_SANDBOX_DEMO_PASSWORD"
# reglas/usuarios-demo.md: un usuario por rol del catalogo (los mismos del acceso rapido de
# Dev Mode, FRONTEND/src/config/accesosDemo.js). ventas@, almacen@ y mantenimiento@ ya existian
# en cargar_semilla.py y se reutilizan con el nombre de la tabla.
USUARIOS_DEMO = (
    ("admin@sgi.local", "Admin Demo", "ADMIN"),
    ("ventas@sgi.local", "Vendedora Demo", "VENTAS"),
    ("calidadprod@sgi.local", "Inspector Demo", "CALIDAD_PRODUCTO"),
    ("gestioncal@sgi.local", "Gestión Calidad Demo", "GESTION_CALIDAD"),
    ("almacen@sgi.local", "Almacenista Demo", "ALMACEN"),
    ("jefeprod@sgi.local", "Jefe Producción Demo", "JEFE_PRODUCCION"),
    ("liderprod@sgi.local", "Líder Producción Demo", "LIDER_PRODUCCION"),
    ("operario@sgi.local", "Operario Demo", "OPERARIO"),
    ("costos@sgi.local", "Costos Demo", "COSTOS"),
    ("mantenimiento@sgi.local", "Mantenimiento Demo", "MANTENIMIENTO"),
    ("liderdiseno@sgi.local", "Líder Diseño Demo", "LIDER_DISENO"),
    ("dibujante@sgi.local", "Dibujante Demo", "DIBUJANTE"),
    ("gerencia@sgi.local", "Gerencia Demo", "GERENCIA"),
    ("secretaria@sgi.local", "Secretaria Demo", "SECRETARIA_GERENCIA"),
    ("logistica@sgi.local", "Logística Demo", "LIDER_LOGISTICA"),
    ("director@sgi.local", "Director Producción Demo", "DIRECTOR_PRODUCCION"),
)
# Cuentas de cargar_semilla.py que no son de demostracion: se desactivan, no se borran (el
# historial conserva sus referencias). admin@sgi.com no esta: sigue como ADMIN tecnico.
CUENTAS_ANTERIORES = (
    "jefe_diseno@sgi.local",
    "dibujante_1@sgi.local",
    "dibujante_2@sgi.local",
    "lider_produccion@sgi.local",
    "operario_1@sgi.local",
    "calidad@sgi.local",
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
        print(
            "Verificacion correcta: historial append-only, busqueda de productos, estado EMITIDA, "
            "codigo_socio por NIT, roles de SCRUM-27 y formato de cotizacion instalados."
        )
    finally:
        conexion.close()


def _cargar_usuarios_demo(restablecer: bool = False, base: str = SANDBOX) -> None:
    clave = os.environ.get(VARIABLE_CLAVE_DEMO)
    if not clave:
        print(
            f"Usuarios de demostracion omitidos: defina {VARIABLE_CLAVE_DEMO} en la sesion "
            "(la misma clave de los botones de Dev Mode si quiere usarlos) y ejecute "
            "python -m scripts.preparar_sandbox --usuarios-demo."
        )
        return
    conexion = conectar(base)
    try:
        cur = conexion.cursor()
        roles = sorted({rol for _, _, rol in USUARIOS_DEMO})
        cur.execute("SELECT id_rol FROM roles WHERE id_rol = ANY(%s)", (roles,))
        faltan = sorted(set(roles) - {fila[0] for fila in cur.fetchall()})
        if faltan:
            fallar(
                f"Faltan roles en {base}: {', '.join(faltan)}. Aplique la migracion 25: "
                f"python -m scripts.aplicar_migracion {base} 25"
            )
        creados = actualizados = 0
        for fila in filas_usuarios_demo(clave):
            cur.execute(
                "INSERT INTO usuarios (id_usuario, email, password_hash, nombre_completo, id_rol, activo, creado_en) "
                "VALUES (%s, %s, %s, %s, %s, TRUE, now()) ON CONFLICT (email) DO NOTHING",
                fila,
            )
            if cur.rowcount:
                creados += 1
                continue
            # Ya existia: vuelve al nombre, rol y estado de usuarios-demo.md; la clave solo con
            # --restablecer-claves. Solo correos de USUARIOS_DEMO y solo en sgi_sandbox o sgi_test_*.
            _, email, hash_clave, nombre, rol = fila
            if restablecer:
                cur.execute(
                    "UPDATE usuarios SET password_hash = %s, nombre_completo = %s, id_rol = %s, activo = TRUE "
                    "WHERE email = %s",
                    (hash_clave, nombre, rol, email),
                )
            else:
                cur.execute(
                    "UPDATE usuarios SET nombre_completo = %s, id_rol = %s, activo = TRUE WHERE email = %s",
                    (nombre, rol, email),
                )
            actualizados += cur.rowcount
        cur.execute(
            "UPDATE usuarios SET activo = FALSE WHERE email = ANY(%s) AND activo IS DISTINCT FROM FALSE",
            (list(CUENTAS_ANTERIORES),),
        )
        desactivados = cur.rowcount
        detalle = "clave, nombre, rol y activo" if restablecer else "nombre, rol y activo; la clave no se toca"
        print(f"Usuarios de demostracion en {base}: {creados} creados y {actualizados} actualizados ({detalle}).")
        print(f"Cuentas anteriores desactivadas (no borradas): {desactivados}.")
    finally:
        conexion.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Prepara {SANDBOX} desde {PLANTILLA} con las migraciones recientes.")
    parser.add_argument("--regenerar", action="store_true", help=f"Elimina {SANDBOX} (con confirmacion) y la crea de nuevo.")
    parser.add_argument(
        "--usuarios-demo", action="store_true",
        help=f"Solo crea los usuarios de demostracion que falten en {SANDBOX} ya existente.",
    )
    parser.add_argument(
        "--restablecer-claves", action="store_true",
        help="Con --usuarios-demo: devuelve tambien la clave a los usuarios demo existentes.",
    )
    parser.add_argument(
        "--base", default=SANDBOX,
        help=f"Con --usuarios-demo: {SANDBOX} (por defecto) o una copia sgi_test_*. Nunca sgi_db.",
    )
    argumentos = parser.parse_args()
    if argumentos.restablecer_claves and not argumentos.usuarios_demo:
        parser.error("--restablecer-claves solo se usa junto con --usuarios-demo.")
    if argumentos.base != SANDBOX and not argumentos.usuarios_demo:
        parser.error("--base solo se usa junto con --usuarios-demo.")
    base = validar_nombre(argumentos.base, permitir_sandbox=True)

    if argumentos.usuarios_demo:
        admin = conectar_admin()
        try:
            if not existe_base(admin.cursor(), base):
                fallar(f"No existe {base}. Creela primero (sgi_sandbox: python -m scripts.preparar_sandbox).")
        finally:
            admin.close()
        _cargar_usuarios_demo(restablecer=argumentos.restablecer_claves, base=base)
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
