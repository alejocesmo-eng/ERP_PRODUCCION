"""
Catálogo de roles de PRISMA (SCRUM-27, reglas/roles-catalogo.md del proyecto PRISMA).

Los grupos ROLES_* dicen qué roles pasan cada requerir_roles. Se nombran por la acción que
autorizan, no por el módulo, para que cada uno cambie solo con su regla
(reglas/permisos-por-rol-modulo.md). tests/test_matriz_roles.py fija el acceso de cada ruta.

Son listas, no tuplas: requerir_roles repite la lista en el detalle del 403.
"""

# --- Roles vigentes ---------------------------------------------------------------------------
ADMIN = "ADMIN"  # rol técnico: usuarios y datos maestros
VENTAS = "VENTAS"
ALMACEN = "ALMACEN"
MANTENIMIENTO = "MANTENIMIENTO"

# --- Roles anteriores a SCRUM-27 --------------------------------------------------------------
# Siguen aceptados mientras haya usuarios con ellos; se retiran cuando ninguno los tenga.
DISENO = "DISENO"  # pasa a LIDER_DISENO y DIBUJANTE
PRODUCCION = "PRODUCCION"  # pasa a JEFE_PRODUCCION, LIDER_MECANIZADOS y OPERARIO
CALIDAD = "CALIDAD"  # pasa a CALIDAD_PRODUCTO y GESTION_CALIDAD

# --- Roles nuevos de SCRUM-27 -----------------------------------------------------------------
CALIDAD_PRODUCTO = "CALIDAD_PRODUCTO"
GESTION_CALIDAD = "GESTION_CALIDAD"
JEFE_PRODUCCION = "JEFE_PRODUCCION"
LIDER_MECANIZADOS = "LIDER_MECANIZADOS"  # "Líder de Mecanizados"; antes LIDER_PRODUCCION (migración 27)
OPERARIO = "OPERARIO"
COSTOS = "COSTOS"
LIDER_DISENO = "LIDER_DISENO"
DIBUJANTE = "DIBUJANTE"
GERENCIA = "GERENCIA"
SECRETARIA_GERENCIA = "SECRETARIA_GERENCIA"
LIDER_LOGISTICA = "LIDER_LOGISTICA"
DIRECTOR_PRODUCCION = "DIRECTOR_PRODUCCION"  # antes "ingeniero jefe"

ROLES_CATALOGO = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, ALMACEN, JEFE_PRODUCCION, LIDER_MECANIZADOS,
    OPERARIO, COSTOS, MANTENIMIENTO, LIDER_DISENO, DIBUJANTE, GERENCIA, SECRETARIA_GERENCIA,
    LIDER_LOGISTICA, DIRECTOR_PRODUCCION,
]
ROLES_ANTERIORES = [DISENO, PRODUCCION, CALIDAD]

# --- Grupos por acción ------------------------------------------------------------------------
# Durante la transición ADMIN está en todos los grupos y los roles anteriores siguen donde
# estaban; cada uno se reemplazó por sus sucesores de reglas/roles-catalogo.md, menos lo que
# reglas/permisos-por-rol-modulo.md prohíbe (OPERARIO sin datos de cliente, MANTENIMIENTO sin OP).
ROLES_SOLO_ADMIN = [ADMIN]
# Datos maestros: socios, personal, cuentas de costos y catálogos (lectura)
ROLES_LECTURA = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, ALMACEN, JEFE_PRODUCCION, LIDER_MECANIZADOS,
    COSTOS, LIDER_DISENO, DIBUJANTE, DIRECTOR_PRODUCCION, DISENO, PRODUCCION, CALIDAD,
]
# Movimientos de almacén, artículos, categorías, unidades y materiales
ROLES_GESTION_ALMACEN = [ADMIN, ALMACEN]
# Cotizaciones y confirmación del pedido
ROLES_VENTAS = [ADMIN, VENTAS]
# Stock de producto terminado: decisión de Alejo (2026-11-11), ALMACEN no lo ve
ROLES_STOCK_PT = [ADMIN, VENTAS, JEFE_PRODUCCION, COSTOS, LIDER_LOGISTICA]
# Expediente de OP (reglas/permisos-por-rol-modulo.md, "Búsqueda y expediente"): completo para
# JEFE_PRODUCCION, GESTION_CALIDAD y COSTOS; sin costos para LIDER_MECANIZADOS. CALIDAD_PRODUCTO,
# ALMACEN, DIBUJANTE y LIDER_DISENO quedan fuera hasta que se confirme (decisión de Alejo,
# 2026-11-12), igual que DISENO, el rol anterior de los dos últimos. VENTAS, OPERARIO y
# MANTENIMIENTO no lo ven. Los costos dentro del expediente van por PERM_EXPEDIENTE_COSTOS_VER.
ROLES_EXPEDIENTE_OP = [
    ADMIN, GESTION_CALIDAD, JEFE_PRODUCCION, LIDER_MECANIZADOS, COSTOS, DIRECTOR_PRODUCCION,
    PRODUCCION, CALIDAD,
]
# Cambios de estado de la OP distintos de la liberación (esa va por PERM_OP_LIBERAR)
ROLES_ACTUALIZAR_OP = [ADMIN, JEFE_PRODUCCION, PRODUCCION]
# LIDER_MECANIZADOS además notifica a CALIDAD_PRODUCTO que la OP terminó y pasa a inspección
ROLES_NOTIFICAR_OP_TERMINADA = [ADMIN, JEFE_PRODUCCION, LIDER_MECANIZADOS, PRODUCCION]
# Cerrar la OP: LIDER_MECANIZADOS cierra OP de cualquier unidad como respaldo del Jefe de Producción
ROLES_CERRAR_OP = [ADMIN, JEFE_PRODUCCION, LIDER_MECANIZADOS, PRODUCCION]
ROLES_APROBAR_PLANO = [ADMIN, LIDER_DISENO, DISENO]
ROLES_REVISION_PLANO = [ADMIN, LIDER_DISENO, DIBUJANTE, DISENO]
ROLES_CALIDAD_LOTE = [ADMIN, CALIDAD_PRODUCTO, CALIDAD]
ROLES_HISTORIAL_CONSULTA = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, ALMACEN, JEFE_PRODUCCION, LIDER_MECANIZADOS,
    COSTOS, MANTENIMIENTO, LIDER_DISENO, DIBUJANTE, DIRECTOR_PRODUCCION, DISENO, PRODUCCION, CALIDAD,
]
# Suspender y reactivar documentos (congela el reloj de productividad)
ROLES_SUSPENDER = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, JEFE_PRODUCCION, LIDER_MECANIZADOS,
    MANTENIMIENTO, LIDER_DISENO, DIBUJANTE, DISENO, PRODUCCION, CALIDAD,
]
ROLES_TRAZABILIDAD = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, ALMACEN, JEFE_PRODUCCION, LIDER_MECANIZADOS,
    COSTOS, LIDER_DISENO, DIBUJANTE, DIRECTOR_PRODUCCION, DISENO, PRODUCCION, CALIDAD,
]

# --- Búsqueda general (reglas/permisos-por-rol-modulo.md, "Búsqueda y expediente") ------------
# Tipos de dato que cada rol encuentra por código o nombre. Un rol que no está aquí no ve la caja.
# El rol se lee de la base en cada consulta (app/services/acceso_bd.py).
BUSQUEDA_COTIZACION = "COTIZACION"
BUSQUEDA_PEDIDO = "PEDIDO"
BUSQUEDA_OP = "OP"
BUSQUEDA_CLIENTE = "CLIENTE"
BUSQUEDA_PRODUCTO = "PRODUCTO"
TIPOS_BUSQUEDA = [BUSQUEDA_COTIZACION, BUSQUEDA_PEDIDO, BUSQUEDA_OP, BUSQUEDA_CLIENTE, BUSQUEDA_PRODUCTO]
TIPOS_BUSQUEDA_POR_ROL = {
    # Transición: ADMIN en todo; el valor cotizado y los costos siguen sus permisos (no los ve)
    ADMIN: TIPOS_BUSQUEDA,
    VENTAS: [BUSQUEDA_COTIZACION, BUSQUEDA_PEDIDO, BUSQUEDA_CLIENTE, BUSQUEDA_PRODUCTO],
    JEFE_PRODUCCION: [BUSQUEDA_PEDIDO, BUSQUEDA_OP, BUSQUEDA_CLIENTE, BUSQUEDA_PRODUCTO],
    GESTION_CALIDAD: [BUSQUEDA_PEDIDO, BUSQUEDA_OP, BUSQUEDA_CLIENTE, BUSQUEDA_PRODUCTO],
    COSTOS: [BUSQUEDA_PEDIDO, BUSQUEDA_OP, BUSQUEDA_CLIENTE, BUSQUEDA_PRODUCTO],
    # "OP al llegar a su unidad": la OP aún no guarda unidad, así que ve todas (pendiente).
    # Información e histórico del cliente; sin valor cotizado ni costos (no tiene los permisos)
    LIDER_MECANIZADOS: [BUSQUEDA_OP, BUSQUEDA_CLIENTE],
}
