import sys
import os

from dotenv import load_dotenv

# OT-2026-001 (RK-1, decisión G2-5): variables obligatorias para la recolección de pruebas.
# El orden es obligatorio: primero se carga 04_CODIGO/BACKEND/.env (si existe) y solo
# después se completan con valores ficticios las variables que sigan sin definir.
# Un setdefault de DATABASE_URL antes de load_dotenv desviaría las pruebas que usan la BD real.
_BACKEND_DIR_ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_BACKEND_DIR_ENV, ".env"))
os.environ.setdefault("SECRET_KEY", "clave_solo_para_pruebas_sesion_no_usar_en_produccion")
os.environ.setdefault("JWT_SECRET_KEY_PLANOS", "clave_solo_para_pruebas_planos_no_usar_en_produccion")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Asegurar que el directorio de la aplicación backend esté en sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
