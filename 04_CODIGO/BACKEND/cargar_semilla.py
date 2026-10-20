# cargar_semilla.py
import uuid
from datetime import datetime, date, timedelta
from app.db.database import SessionLocal, engine, Base
from app.db.models import (
    Proyecto, 
    PedidoDetalle, 
    OTDetalle, 
    Plano, 
    OrdenProduccion, 
    NoConformidad,
    ArticuloInventario,
    EntradaMercancia,
    AjusteInventario,
    MantenimientoMaquina,
    MantenimientoPiezaDet,
    Usuario, 
    Rol, 
    Permiso,
    Maquina, 
    Empleado
)
from app.db.models_produccion import (
    OperacionOT, 
    SubLoteOperacion, 
    RegistroTiempoOperario, 
    NotificacionLider,
    EstadoOperacionEnum,
    TipoUnidadPlantaEnum,
    TipoNotificacionEnum
)
from app.core.security import get_password_hash


def cargar_semilla_db():
    print("🌱 Iniciando purga y repoblación de Base de Datos SGI...")
    
    # 1. Asegurar la creación de tablas en PostgreSQL
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 2. Limpieza de tablas en orden estricto de claves foráneas
        print("🔄 Borrando datos base de todas las tablas...")
        db.query(NotificacionLider).delete()
        db.query(RegistroTiempoOperario).delete()
        db.query(SubLoteOperacion).delete()
        db.query(OperacionOT).delete()
        db.query(NoConformidad).delete()
        db.query(OrdenProduccion).delete()
        db.query(OTDetalle).delete()
        db.query(Plano).delete()
        db.query(MantenimientoPiezaDet).delete()
        db.query(MantenimientoMaquina).delete()
        db.query(PedidoDetalle).delete()
        db.query(Proyecto).delete()
        db.query(AjusteInventario).delete()
        db.query(EntradaMercancia).delete()
        db.query(ArticuloInventario).delete()
        db.query(Usuario).delete()
        db.query(Permiso).delete()
        db.query(Rol).delete()
        db.query(Maquina).delete()
        db.query(Empleado).delete()
        db.commit()

        # =====================================================================
        # 3. ROLES Y PERMISOS
        # =====================================================================
        print("👤 Insertando Roles del Sistema...")
        rol_admin = Rol(id_rol="ADMIN", nombre_rol="Administrador SGI", descripcion="Acceso Total SGI")
        rol_jefe = Rol(id_rol="JEFE_AREA", nombre_rol="Jefe de Área", descripcion="Gestión Operativa de Planta")
        rol_almacen = Rol(id_rol="ALMACENISTA", nombre_rol="Almacenista", descripcion="Gestión de Inventarios")
        rol_operario = Rol(id_rol="OPERARIO", nombre_rol="Operario MES", descripcion="Captura en Tablet MES")
        rol_consulta = Rol(id_rol="CONSULTA", nombre_rol="Consulta", descripcion="Acceso de Solo Lectura")

        db.add_all([rol_admin, rol_jefe, rol_almacen, rol_operario, rol_consulta])
        db.flush()

        # =====================================================================
        # 4. USUARIOS DEL SISTEMA
        # =====================================================================
        print("👤 Insertando Usuarios del Sistema...")
        id_admin = uuid.uuid4()
        id_operario_carlos = uuid.uuid4()
        hash_password_inicial = get_password_hash("admin123")

        admin_user = Usuario(
            id_usuario=id_admin,
            email="admin@sgi.com",
            password_hash=hash_password_inicial,
            nombre_completo="Administrador General SGI",
            id_rol="ADMIN",
            activo=True
        )

        op_user = Usuario(
            id_usuario=id_operario_carlos,
            email="cruiz@sgi.com",
            password_hash=hash_password_inicial,
            nombre_completo="Carlos Ruiz",
            id_rol="OPERARIO",
            activo=True
        )

        db.add_all([admin_user, op_user])
        db.flush()

        # =====================================================================
        # 5. MÁQUINAS Y EMPLEADOS
        # =====================================================================
        print("🏭 Insertando Máquinas y Empleados...")
        m1 = Maquina(id_maquina="TORN-CNC-01", nombre_maquina="Torno CNC Haas ST-20", tipo_maquina="Torno", estado="OPERATIVA")
        m2 = Maquina(id_maquina="FRES-CNC-01", nombre_maquina="Centro de Mecanizado VF-2", tipo_maquina="Fresadora", estado="OPERATIVA")
        db.add_all([m1, m2])

        e1 = Empleado(id_empleado="EMP-001", nombre_completo="Carlos Ruiz", cargo="Operario CNC", area="Mecanizados")
        e2 = Empleado(id_empleado="EMP-002", nombre_completo="Ing. Juan Pérez", cargo="Jefe de Planta", area="Producción")
        db.add_all([e1, e2])
        db.flush()

        # =====================================================================
        # 6. PEDIDOS COMERCIALES Y DRAFT BASE DE PROYECTOS
        # =====================================================================
        print("📦 Insertando Pedido Base Limpio...")
        uuid_p1 = uuid.UUID("a1b2c3d4-0001-4000-8000-000000000088")
        p1 = Proyecto(
            id_proyecto=uuid_p1,
            numero_pedido="PED-2026-088",
            codigo_proyecto="PED-2026-088",
            cliente_nombre="Ecopetrol S.A.",
            contacto_nombre="Ing. Juan Pérez",
            contacto_telefono="+57 310 456 7890",
            contacto_email="jperez@ecopetrol.com.co",
            ubicacion_cliente="Refinería Barrancabermeja - Bodega 4",
            detalle_producto="Lote de Bridas Forjadas y Servicio de Metrología",
            cantidad=11,
            requisitos_cliente="Norma ASME B16.5 / Certificado 3.1 según EN 10204",
            confirmado=False,
            fecha_compromiso=date(2026, 11, 15)
        )
        db.add(p1)
        db.flush()

        det1 = PedidoDetalle(
            detalle_id=uuid.uuid4(),
            pedido_id=uuid_p1,
            codigo_producto="PROD-BR-12",
            descripcion="Brida Forjada 12 ANSI 600",
            tipo="PIEZA",
            cantidad_solicitada=10,
            unidad="UND",
            cantidad_asignada=0,
            cantidad_pendiente=10,
            prioridad="ALTA"
        )
        db.add(det1)
        db.flush()

        db.commit()
        print("🚀 ¡ÉXITO! Base de datos reiniciada y semilla cargada correctamente.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error al ejecutar la semilla: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    cargar_semilla_db()