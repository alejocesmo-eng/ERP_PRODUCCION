"""
Respalda y limpia sgi_sandbox de la carga anterior (cargar_semilla.py, que llega con la
plantilla sgi_test_template): clientes como Ecopetrol, pedidos PED-2026-DEMO-*, cotizaciones,
OP, planos, inventario, compras y calidad. Prepara la base para la semilla de escenarios
(scripts/sembrar_escenarios_sandbox.py, SCRUM-33).

Solo actua sobre sgi_sandbox: el nombre esta fijo, se valida con _pg_pruebas.validar_nombre y,
antes de borrar, se comprueba current_database() en la conexion. Nunca sgi_db ni sgi_test_*.

Tres pasos separados, para revisar cada uno antes del siguiente:
    python -m scripts.limpiar_sandbox --respaldar [--carpeta RUTA]
        pg_dump -Fc de sgi_sandbox a una carpeta fuera del repositorio (por defecto
        %USERPROFILE%/Documents/respaldos_sgi). Verifica el archivo con pg_restore --list.
    python -m scripts.limpiar_sandbox --revisar
        Muestra cuantas filas tiene cada tabla que se vaciaria. No cambia nada.
    python -m scripts.limpiar_sandbox --vaciar --respaldo RUTA_DEL_RESPALDO --confirmar sgi_sandbox
        Exige un respaldo valido de sgi_sandbox y --confirmar con el nombre exacto de la base,
        que debe coincidir con current_database() de la conexion, y vacia las tablas en una
        sola transaccion (TRUNCATE sin CASCADE: si otra tabla apunta
        a una de la lista, PostgreSQL lo rechaza y no se borra nada).

Se conservan usuarios, roles, permisos, rol_permisos, migracion_25_registro, catalogos
(unidades, categorias), centros de trabajo y de almacen, maquinas y mantenimiento, personal y
la empresa emisora. Los PDF de static/planos no se borran.

Credenciales solo por variables de entorno (ADR-005): SGI_TEST_PG_ADMIN_URL (sin clave) y
PGPASSWORD. pg_dump recibe host, puerto y usuario por argumentos y la clave por PGPASSWORD; el
script no imprime ni guarda credenciales. pg_dump se busca en SGI_PG_BIN, en el PATH o en
C:/Program Files/PostgreSQL/*/bin.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from psycopg2 import sql

from scripts._pg_pruebas import SANDBOX, conectar, conectar_admin, existe_base, fallar, url_admin, validar_nombre

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[3]
CARPETA_POR_DEFECTO = Path.home() / "Documents" / "respaldos_sgi"

# Datos de la carga anterior, en orden de dependencias inverso solo por legibilidad: TRUNCATE
# de la lista completa en una sentencia resuelve las llaves entre ellas.
TABLAS_A_VACIAR = (
    # Comercial
    "ordenes_picking_detalle", "ordenes_picking", "posiciones_cotizacion", "cotizaciones",
    "ot_detalles", "pedido_detalles", "proyectos", "clientes", "socios_negocio_codigo_anterior",
    "socios_negocio",
    # Diseño
    "solicitudes_cambio_tecnico", "bom_lista_materiales", "planos_historial", "planos_archivos",
    "planos", "productos",
    # Producción
    "notificaciones_lider", "registros_tiempo_operario", "sublotes_operacion", "operaciones_ot",
    "tiempos_manuales_correcciones", "registro_tiempos_produccion", "consumos_material_op", "entregas_material_op",
    "servicios_terceros_op", "op_traslados_unidad", "ordenes_produccion",
    # Compras y MRP
    "trazabilidad_requisicion_mrp", "requisiciones_mrp", "ejecuciones_mrp", "solicitudes_compra",
    "evaluaciones_rea", "entradas_mercancia",
    # Inventario
    "auditoria_calidad_lotes", "movimientos_kardex_sap", "catalogo_materiales_sap",
    "ajustes_inventario", "movimientos_inventario", "retales_sobrantes", "lotes_material",
    "articulos_inventario",
    # Calidad e historial
    "acciones_capa", "no_conformidades", "fichas_metrologia", "inspecciones_calidad",
    "historial_acciones_documento",
)
# De la lista, las que crea una migración y no tienen modelo (respaldo del código anterior de
# cada socio, migración 24; apunta a socios_negocio)
TABLAS_SOLO_MIGRACION = ("socios_negocio_codigo_anterior",)

# Llaves foraneas de tablas que NO estan en la lista hacia tablas de la lista
CONSULTA_REFERENCIAS_EXTERNAS = """
SELECT hija.relname, padre.relname
  FROM pg_constraint c
  JOIN pg_class hija ON hija.oid = c.conrelid
  JOIN pg_class padre ON padre.oid = c.confrelid
  JOIN pg_namespace n ON n.oid = hija.relnamespace
 WHERE c.contype = 'f' AND n.nspname = 'public'
   AND padre.relname = ANY(%s) AND NOT hija.relname = ANY(%s)
 ORDER BY 1, 2
"""


def herramienta(nombre: str) -> str:
    """Ruta de pg_dump o pg_restore: SGI_PG_BIN, PATH o la instalacion de PostgreSQL en Windows."""
    ejecutable = f"{nombre}.exe" if os.name == "nt" else nombre
    carpeta = os.environ.get("SGI_PG_BIN")
    if carpeta and (Path(carpeta) / ejecutable).is_file():
        return str(Path(carpeta) / ejecutable)
    en_path = shutil.which(nombre)
    if en_path:
        return en_path
    instalaciones = sorted(Path("C:/Program Files/PostgreSQL").glob(f"*/bin/{ejecutable}"), reverse=True)
    if instalaciones:
        return str(instalaciones[0])
    fallar(f"No se encontro {nombre}. Defina SGI_PG_BIN con la carpeta bin de PostgreSQL.")


def argumentos_conexion() -> list[str]:
    url = url_admin()
    return ["-h", url.host or "localhost", "-p", str(url.port or 5432), "-U", url.username or "postgres"]


def carpeta_fuera_del_repositorio(carpeta: Path) -> Path:
    carpeta = carpeta.resolve()
    if carpeta == RAIZ_REPOSITORIO or RAIZ_REPOSITORIO in carpeta.parents:
        fallar(f"La carpeta del respaldo debe estar fuera del repositorio ({RAIZ_REPOSITORIO}).")
    return carpeta


def sha256_de(ruta: Path) -> str:
    calculo = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        while bloque := archivo.read(1024 * 1024):
            calculo.update(bloque)
    return calculo.hexdigest()


def verificar_respaldo(ruta: Path) -> None:
    """El archivo existe, no esta vacio y pg_restore lo lee como respaldo de sgi_sandbox."""
    if not ruta.is_file() or ruta.stat().st_size == 0:
        fallar(f"No existe un respaldo valido en {ruta}.")
    resultado = subprocess.run(
        [herramienta("pg_restore"), "--list", str(ruta)], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if resultado.returncode != 0:
        fallar(f"pg_restore no pudo leer {ruta}: el respaldo no es valido.")
    cabecera = [linea for linea in resultado.stdout.splitlines()[:20] if "dbname:" in linea.lower()]
    if not cabecera or cabecera[0].split(":", 1)[1].strip() != SANDBOX:
        fallar(f"{ruta} no es un respaldo de {SANDBOX}.")


def respaldar(carpeta: Path) -> Path:
    carpeta = carpeta_fuera_del_repositorio(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{SANDBOX}_{datetime.now():%Y%m%d_%H%M%S}.dump"
    resultado = subprocess.run(
        [herramienta("pg_dump"), *argumentos_conexion(), "-d", SANDBOX, "-Fc", "-f", str(ruta)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if resultado.returncode != 0:
        causa = (resultado.stderr.strip().splitlines() or ["sin detalle"])[0]
        fallar(f"pg_dump fallo: {causa}")
    verificar_respaldo(ruta)
    print(f"Respaldo de {SANDBOX} creado y verificado con pg_restore --list.")
    print(f"Ruta: {ruta}")
    print(f"Tamano: {ruta.stat().st_size} bytes | sha256: {sha256_de(ruta)}")
    return ruta


def confirmar_base(cur) -> None:
    cur.execute("SELECT current_database()")
    actual = cur.fetchone()[0]
    if actual != SANDBOX:
        fallar(f"La conexion apunta a {actual}, no a {SANDBOX}: no se borra nada.")
    print(f"Conexion verificada: current_database() = {actual}")


def conteos(cur) -> dict[str, int | None]:
    """Filas por tabla de la lista; None si la tabla no existe en la base."""
    resultado = {}
    for tabla in TABLAS_A_VACIAR:
        cur.execute("SELECT to_regclass(%s)", (f"public.{tabla}",))
        if cur.fetchone()[0] is None:
            resultado[tabla] = None
            continue
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabla)))
        resultado[tabla] = cur.fetchone()[0]
    return resultado


def referencias_externas(cur, existentes: list[str]) -> list[tuple[str, str]]:
    cur.execute(CONSULTA_REFERENCIAS_EXTERNAS, (existentes, existentes))
    return cur.fetchall()


def revisar(cur) -> dict[str, int | None]:
    confirmar_base(cur)
    filas = conteos(cur)
    print(f"{'Tabla':<32}{'Filas':>10}")
    for tabla, total in filas.items():
        print(f"{tabla:<32}{'no existe' if total is None else total:>10}")
    print(f"Total de filas a borrar: {sum(t for t in filas.values() if t)}")
    externas = referencias_externas(cur, [t for t, total in filas.items() if total is not None])
    if externas:
        print("ATENCION: tablas fuera de la lista apuntan a tablas de la lista (TRUNCATE las rechazaria):")
        for hija, padre in externas:
            print(f"  {hija} -> {padre}")
    return filas


def validar_confirmacion(confirmacion: str | None) -> None:
    """--confirmar debe ser exactamente sgi_sandbox (sin espacios ni otros caracteres).
    Reemplaza la pregunta interactiva: en la consola de Windows la respuesta de input() puede
    llegar con caracteres invisibles y no coincidir."""
    if confirmacion != SANDBOX:
        fallar(f"Vaciado cancelado: --confirmar debe ser exactamente {SANDBOX}. No se modifico nada.")


def vaciar(conexion, confirmacion: str | None) -> None:
    validar_confirmacion(confirmacion)
    cur = conexion.cursor()
    filas = revisar(cur)
    existentes = [t for t, total in filas.items() if total is not None]
    if referencias_externas(cur, existentes):
        fallar("Hay tablas fuera de la lista que apuntan a la lista: no se borra nada.")
    conexion.autocommit = False
    try:
        # Dentro de la transaccion del TRUNCATE: la base conectada es la confirmada
        cur.execute("SELECT current_database()")
        actual = cur.fetchone()[0]
        if actual != confirmacion:
            raise RuntimeError(f"la conexion apunta a {actual}, no a {confirmacion}")
        cur.execute(sql.SQL("TRUNCATE TABLE {}").format(sql.SQL(", ").join(sql.Identifier(t) for t in existentes)))
        conexion.commit()
    except Exception as error:
        conexion.rollback()
        causa = (str(error).strip().splitlines() or [error.__class__.__name__])[0]
        fallar(f"El vaciado fallo y se revirtio: {causa}")
    restantes = conteos(cur)
    print(f"Vaciado completo en {SANDBOX}: {len(existentes)} tablas, {sum(restantes[t] or 0 for t in existentes)} filas restantes.")


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Respalda y limpia {SANDBOX} de la carga anterior.")
    accion = parser.add_mutually_exclusive_group(required=True)
    accion.add_argument("--respaldar", action="store_true", help="pg_dump de sgi_sandbox fuera del repositorio.")
    accion.add_argument("--revisar", action="store_true", help="Muestra lo que se vaciaria, sin cambiar nada.")
    accion.add_argument("--vaciar", action="store_true", help="Vacia las tablas (exige --respaldo y confirmacion).")
    parser.add_argument("--carpeta", type=Path, default=CARPETA_POR_DEFECTO, help="Carpeta del respaldo (fuera del repositorio).")
    parser.add_argument("--respaldo", type=Path, help="Con --vaciar: ruta del respaldo creado con --respaldar.")
    parser.add_argument("--confirmar", help=f"Con --vaciar: el nombre exacto de la base, {SANDBOX}.")
    argumentos = parser.parse_args()
    if argumentos.vaciar and not argumentos.respaldo:
        parser.error("--vaciar exige --respaldo con la ruta del respaldo de sgi_sandbox.")
    if argumentos.vaciar and argumentos.confirmar is None:
        parser.error(f"--vaciar exige --confirmar {SANDBOX}.")
    if argumentos.confirmar is not None and not argumentos.vaciar:
        parser.error("--confirmar solo se usa junto con --vaciar.")
    if argumentos.vaciar:
        validar_confirmacion(argumentos.confirmar)
    validar_nombre(SANDBOX, permitir_sandbox=True)

    admin = conectar_admin()
    try:
        if not existe_base(admin.cursor(), SANDBOX):
            fallar(f"No existe {SANDBOX}.")
    finally:
        admin.close()

    if argumentos.respaldar:
        respaldar(argumentos.carpeta)
        return
    if argumentos.vaciar:
        verificar_respaldo(argumentos.respaldo)
        print(f"Respaldo verificado: {argumentos.respaldo}")
    conexion = conectar(SANDBOX)
    try:
        if argumentos.revisar:
            revisar(conexion.cursor())
        else:
            vaciar(conexion, argumentos.confirmar)
    finally:
        conexion.close()


if __name__ == "__main__":
    main()
