# tests/test_limpiar_sandbox.py
"""
Script limpiar_sandbox sin base de datos ni pg_dump: solo sgi_sandbox, respaldo fuera del
repositorio y verificado, confirmación escrita, comprobación de current_database() antes del
TRUNCATE y lista de tablas coherente con los modelos (no vacía usuarios, roles ni permisos, y
ninguna tabla que se conserva apunta a una que se vacía).
"""
import importlib
import pkgutil
import subprocess
from pathlib import Path

import pytest

import app.db as paquete_db
from app.db.database import Base
from scripts import limpiar_sandbox

for _modulo in pkgutil.iter_modules(paquete_db.__path__):
    if _modulo.name.startswith("models"):
        importlib.import_module(f"app.db.{_modulo.name}")


def test_las_tablas_existen_en_el_modelo_y_no_incluyen_usuarios_ni_permisos():
    tablas = set(limpiar_sandbox.TABLAS_A_VACIAR)

    assert len(tablas) == len(limpiar_sandbox.TABLAS_A_VACIAR)
    assert tablas - set(limpiar_sandbox.TABLAS_SOLO_MIGRACION) <= set(Base.metadata.tables)
    # socios_negocio_codigo_anterior (migración 24) apunta a socios_negocio: va en la lista
    assert "socios_negocio_codigo_anterior" in tablas
    assert not tablas & {"usuarios", "roles", "permisos", "rol_permisos", "unidades_medida", "categorias_inventario",
                         "centros_trabajo", "empresa_emisora", "trabajadores_usuarios", "empleados"}
    assert {"socios_negocio", "clientes", "cotizaciones", "proyectos", "ordenes_produccion", "planos"} <= tablas


def test_ninguna_tabla_que_se_conserva_apunta_a_una_que_se_vacia():
    tablas = set(limpiar_sandbox.TABLAS_A_VACIAR)
    conflictos = [
        f"{tabla.name} -> {fk.column.table.name}"
        for tabla in Base.metadata.sorted_tables
        for fk in tabla.foreign_keys
        if tabla.name not in tablas and fk.column.table.name in tablas
    ]
    assert conflictos == []


def test_el_respaldo_no_puede_quedar_dentro_del_repositorio():
    with pytest.raises(SystemExit):
        limpiar_sandbox.carpeta_fuera_del_repositorio(limpiar_sandbox.RAIZ_REPOSITORIO / "respaldos")
    fuera = limpiar_sandbox.RAIZ_REPOSITORIO.parent / "respaldos_sgi_prueba"
    assert limpiar_sandbox.carpeta_fuera_del_repositorio(fuera) == fuera.resolve()


def test_vaciar_exige_la_ruta_del_respaldo(monkeypatch):
    monkeypatch.setattr("sys.argv", ["limpiar_sandbox", "--vaciar"])

    with pytest.raises(SystemExit):
        limpiar_sandbox.main()


class Listado:
    def __init__(self, codigo, salida):
        self.returncode, self.stdout = codigo, salida


@pytest.mark.parametrize(("salida", "valido"), [
    (";\n; Archive created at 2026-11-11\n;     dbname: sgi_sandbox\n", True),
    (";\n;     dbname: sgi_db\n", False),
    (";\n;     dbname: sgi_test_run\n", False),
])
def test_el_respaldo_debe_ser_de_sgi_sandbox(tmp_path, monkeypatch, salida, valido):
    ruta = tmp_path / "respaldo.dump"
    ruta.write_bytes(b"PGDMP contenido")
    monkeypatch.setattr(limpiar_sandbox, "herramienta", lambda nombre: nombre)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Listado(0, salida))

    if valido:
        limpiar_sandbox.verificar_respaldo(ruta)
    else:
        with pytest.raises(SystemExit):
            limpiar_sandbox.verificar_respaldo(ruta)


def test_sin_archivo_de_respaldo_no_sigue(tmp_path):
    with pytest.raises(SystemExit):
        limpiar_sandbox.verificar_respaldo(tmp_path / "no_existe.dump")


@pytest.mark.parametrize("confirmacion", ["si", "SGI_SANDBOX", "", " sgi_sandbox", "﻿sgi_sandbox", "sgi_db", None])
def test_confirmar_debe_ser_exactamente_sgi_sandbox(confirmacion):
    with pytest.raises(SystemExit):
        limpiar_sandbox.validar_confirmacion(confirmacion)


def test_confirmar_sgi_sandbox_es_valido():
    limpiar_sandbox.validar_confirmacion("sgi_sandbox")


@pytest.mark.parametrize("argumentos", [
    ["--vaciar", "--respaldo", "r.dump"],
    ["--revisar", "--confirmar", "sgi_sandbox"],
    ["--vaciar", "--respaldo", "r.dump", "--confirmar", "si"],
])
def test_argumentos_de_confirmacion_invalidos_no_conectan(monkeypatch, argumentos):
    monkeypatch.setattr("sys.argv", ["limpiar_sandbox", *argumentos])
    monkeypatch.setattr(limpiar_sandbox, "conectar_admin", lambda: pytest.fail("No debe conectar"))

    with pytest.raises(SystemExit):
        limpiar_sandbox.main()


class CursorFalso:
    def __init__(self, base):
        self.base = base
        self.sentencias = []
        self._fila = None

    def execute(self, sentencia, parametros=None):
        texto = sentencia if isinstance(sentencia, str) else repr(sentencia)
        self.sentencias.append(texto)
        if "current_database" in texto:
            self._fila = (self.base,)
        elif "to_regclass" in texto:
            self._fila = ("tabla",)
        else:
            self._fila = (0,)

    def fetchone(self):
        return self._fila

    def fetchall(self):
        return []


class ConexionFalsa:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = True
        self.confirmada = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.confirmada = True

    def rollback(self):
        pass


def test_con_otra_base_en_la_conexion_no_trunca(capsys):
    cursor = CursorFalso("sgi_test_run")

    with pytest.raises(SystemExit):
        limpiar_sandbox.vaciar(ConexionFalsa(cursor), "sgi_sandbox")

    assert not any("TRUNCATE" in s for s in cursor.sentencias)


def test_sin_confirmacion_valida_no_consulta_ni_trunca():
    cursor = CursorFalso("sgi_sandbox")

    with pytest.raises(SystemExit):
        limpiar_sandbox.vaciar(ConexionFalsa(cursor), "si")

    assert cursor.sentencias == []


def test_si_la_base_cambia_antes_del_truncate_no_trunca():
    cursor = CursorFalso("sgi_sandbox")
    conexion = ConexionFalsa(cursor)
    consultas = []
    original = cursor.execute

    def execute(sentencia, parametros=None):
        original(sentencia, parametros)
        if "current_database" in str(sentencia):
            consultas.append(sentencia)
            if len(consultas) > 1:
                cursor._fila = ("otra_base",)

    cursor.execute = execute

    with pytest.raises(SystemExit):
        limpiar_sandbox.vaciar(conexion, "sgi_sandbox")

    assert not any("TRUNCATE" in s for s in cursor.sentencias)


def test_con_confirmacion_trunca_las_tablas_en_una_transaccion(capsys):
    cursor = CursorFalso("sgi_sandbox")
    conexion = ConexionFalsa(cursor)

    limpiar_sandbox.vaciar(conexion, "sgi_sandbox")

    truncados = [s for s in cursor.sentencias if "TRUNCATE" in s]
    assert len(truncados) == 1 and conexion.confirmada and conexion.autocommit is False
    assert all(tabla in truncados[0] for tabla in limpiar_sandbox.TABLAS_A_VACIAR)
    assert "usuarios" not in truncados[0].replace("usuarios_", "")
    assert "current_database() = sgi_sandbox" in capsys.readouterr().out
