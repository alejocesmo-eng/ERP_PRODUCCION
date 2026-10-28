# 04_CODIGO/BACKEND/verificar_bd.py
from app.db.database import SessionLocal, engine, Base
# Importar TODOS los modelos para asegurar que Base conozca todas las tablas
import app.db.models 

def verificar_y_crear():
    print("🔨 [1/2] Sincronizando esquema: creando tablas faltantes en PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas creadas/sincronizadas correctamente.")

    print("\n🔍 [2/2] VERIFICACIÓN DE CONTEO DE REGISTROS EN BASE DE DATOS:")
    db = SessionLocal()
    try:
        from app.db.models import (
            Usuario, Proyecto, Plano, OrdenProduccion, 
            SocioNegocio, EstructuraFinanciera, Maquina
        )
        print(f"👤 Usuarios: {db.query(Usuario).count()}")
        print(f"🏢 Socios de Negocio (Clientes/Prov): {db.query(SocioNegocio).count()}")
        print(f"🏦 Estructura Financiera (Cuentas/CC): {db.query(EstructuraFinanciera).count()}")
        print(f"⚙️ Máquinas: {db.query(Maquina).count()}")
        print(f"📦 Pedidos Comerciales (Proyectos): {db.query(Proyecto).count()}")
        print(f"📐 Planos / OTs: {db.query(Plano).count()}")
        print(f"🏭 Órdenes de Producción: {db.query(OrdenProduccion).count()}")
        print("---------------------------------------------------------")
    except Exception as e:
        print(f"❌ Error al consultar PostgreSQL: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verificar_y_crear()