from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# 1. Crear el motor (Engine) que maneja las conexiones a PostgreSQL
engine = create_engine(settings.DATABASE_URL)

# 2. Configurar la fábrica de sesiones (SessionLocal)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Base declarativa de la que heredarán todos nuestros modelos de tablas (Empleados, Retales, etc.)
Base = declarative_base()

# 4. Dependencia para inyectar la sesión activa en los endpoints (rutas) de FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        # app/db/database.py
import os

# Ajusta "tu_contrasena_real" por la clave real de tu PostgreSQL local
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:tu_contrasena_real@localhost:5432/sgi_db"
)