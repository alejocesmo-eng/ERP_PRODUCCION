import os
from dotenv import load_dotenv

# Carga las variables de entorno desde el archivo .env
load_dotenv()

def _variable_obligatoria(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise RuntimeError(f"Falta la variable de entorno obligatoria {nombre}. Cree 04_CODIGO/BACKEND/.env a partir de .env.example.")
    return valor

class Settings:
    PROJECT_NAME: str = "Sistema de Gestión Integral (SGI)"

    # Variables obligatorias: sin valor por defecto. Si faltan o están vacías, el arranque falla con RuntimeError.
    DATABASE_URL: str = _variable_obligatoria("DATABASE_URL")

    SECRET_KEY: str = _variable_obligatoria("SECRET_KEY")
    ALGORITHM: str = os.environ.get("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 480))

settings = Settings()