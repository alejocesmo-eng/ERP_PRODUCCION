import sys
import os

# Obtener la ruta absoluta del directorio donde se encuentra este script
DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))

# Agregar la carpeta raíz al path de búsqueda de módulos de Python
if DIRECTORIO_ACTUAL not in sys.path:
    sys.path.insert(0, DIRECTORIO_ACTUAL)

from sqlalchemy import text
from app.db.database import engine

def ejecutar_migracion():
    print("🔄 Iniciando migración de columnas en 'mantenimientos_maquinas'...")
    
    script_sql = text("""
        ALTER TABLE mantenimientos_maquinas ADD COLUMN IF NOT EXISTS cliente_nombre VARCHAR(150);
        ALTER TABLE mantenimientos_maquinas ADD COLUMN IF NOT EXISTS marca_modelo VARCHAR(150);
        ALTER TABLE mantenimientos_maquinas ADD COLUMN IF NOT EXISTS serie_maquina VARCHAR(100);
        ALTER TABLE mantenimientos_maquinas ADD COLUMN IF NOT EXISTS observaciones_ingreso TEXT;
    """)

    try:
        with engine.begin() as connection:
            connection.execute(script_sql)
        print("✅ Migración ejecutada exitosamente. Columnas agregadas a PostgreSQL.")
    except Exception as e:
        print(f"❌ Error al ejecutar la migración: {e}")

if __name__ == "__main__":
    ejecutar_migracion()