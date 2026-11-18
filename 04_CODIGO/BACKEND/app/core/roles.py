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
# "Líder de Servicios" (migración 32): OP de Servicios desde que se crean; cierra solo las de su área
LIDER_SERVICIOS = "LIDER_SERVICIOS"
OPERARIO = "OPERARIO"
COSTOS = "COSTOS"
LIDER_DISENO = "LIDER_DISENO"
DIBUJANTE = "DIBUJANTE"
GERENCIA = "GERENCIA"
SECRETARIA_GERENCIA = "SECRETARIA_GERENCIA"
LIDER_LOGISTICA = "LIDER_LOGISTICA"
DIRECTOR_PRODUCCION = "DIRECTOR_PRODUCCION"  # antes "ingeniero jefe"
# Carga manual de tiempos en cualquier unidad (migración 29): solo PERM_TIEMPOS_REGISTRAR
CAPTURISTA_TIEMPOS = "CAPTURISTA_TIEMPOS"

ROLES_CATALOGO = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, ALMACEN, JEFE_PRODUCCION, LIDER_MECANIZADOS,
    OPERARIO, COSTOS, MANTENIMIENTO, LIDER_DISENO, DIBUJANTE, GERENCIA, SECRETARIA_GERENCIA,
    LIDER_LOGISTICA, DIRECTOR_PRODUCCION, CAPTURISTA_TIEMPOS, LIDER_SERVICIOS,
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
    LIDER_SERVICIOS, COSTOS, LIDER_DISENO, DIBUJANTE, DIRECTOR_PRODUCCION, DISENO, PRODUCCION, CALIDAD,
]
# Movimientos de almacén, artículos, categorías, unidades y materiales
ROLES_GESTION_ALMACEN = [ADMIN, ALMACEN]
# Cotizaciones y confirmación del pedido
ROLES_VENTAS = [ADMIN, VENTAS]
# Stock de producto terminado: decisión de Alejo (2026-11-11), ALMACEN no lo ve
ROLES_STOCK_PT = [ADMIN, VENTAS, JEFE_PRODUCCION, COSTOS, LIDER_LOGISTICA]
# Expediente de OP (reglas/permisos-por-rol-modulo.md, "Búsqueda y expediente"): completo para
# JEFE_PRODUCCION, GESTION_CALIDAD y COSTOS; sin costos ni valor cotizado para los líderes,
# DIBUJANTE, LIDER_DISENO y CALIDAD_PRODUCTO (estos tres desde la división del expediente,
# 2026-11-17; CALIDAD_PRODUCTO, solo las OP en inspección o en Tercero). ALMACEN sigue por
# confirmar. VENTAS, OPERARIO y MANTENIMIENTO no lo ven. Los costos van por
# PERM_EXPEDIENTE_COSTOS_VER y el expediente de OP no trae valor cotizado.
ROLES_EXPEDIENTE_OP = [
    ADMIN, GESTION_CALIDAD, JEFE_PRODUCCION, LIDER_MECANIZADOS, LIDER_SERVICIOS, COSTOS, DIRECTOR_PRODUCCION,
    DIBUJANTE, LIDER_DISENO, CALIDAD_PRODUCTO, PRODUCCION, CALIDAD,
]
# Expediente del pedido (división del expediente, 2026-11-17). El valor cotizado va por
# PERM_VALOR_COTIZADO_VER (los líderes no lo tienen). VENTAS lo ve sin números de OP ni datos de
# producción (ROLES_PEDIDO_SIN_PRODUCCION). Los demás roles reciben 403.
ROLES_EXPEDIENTE_PEDIDO = [VENTAS, JEFE_PRODUCCION, COSTOS, GESTION_CALIDAD, LIDER_MECANIZADOS, LIDER_SERVICIOS]
ROLES_PEDIDO_SIN_PRODUCCION = [VENTAS]
# Cambios de estado de la OP distintos de la liberación (esa va por PERM_OP_LIBERAR)
ROLES_ACTUALIZAR_OP = [ADMIN, JEFE_PRODUCCION, PRODUCCION]
# LIDER_MECANIZADOS además notifica a CALIDAD_PRODUCTO que la OP terminó y pasa a inspección
ROLES_NOTIFICAR_OP_TERMINADA = [ADMIN, JEFE_PRODUCCION, LIDER_MECANIZADOS, PRODUCCION]
# Devolver a inspección una OP que el flujo anterior de Calidad dejó en LISTA_PARA_LIBERAR sin
# piezas aprobadas (app/api/v1/ordenes.py, devolver_a_inspeccion)
ROLES_DEVOLVER_A_INSPECCION = [JEFE_PRODUCCION]
# Cerrar la OP: LIDER_MECANIZADOS cierra OP de cualquier unidad como respaldo del Jefe de Producción;
# LIDER_SERVICIOS también es respaldo, pero solo de las OP de su área (ROLES_CIERRE_SOLO_SU_UNIDAD)
ROLES_CERRAR_OP = [ADMIN, JEFE_PRODUCCION, LIDER_MECANIZADOS, LIDER_SERVICIOS, PRODUCCION]
ROLES_CIERRE_SOLO_SU_UNIDAD = [LIDER_SERVICIOS]
# Unidad actual de la OP (app/services/unidad_op.py): el líder de cada unidad solo ve las OP de su
# unidad. El líder de Metalistería se agrega aquí cuando exista su rol.
UNIDAD_POR_LIDER = {LIDER_MECANIZADOS: "MECANIZADOS", LIDER_SERVICIOS: "SERVICIOS"}
# Líderes que ven las OP de su área desde que se crean (aún sin unidad, por la unidad de sus
# planos), no solo al llegar a su unidad
LIDERES_VEN_DESDE_CREACION = [LIDER_SERVICIOS]
# Líderes que trasladan las OP de su unidad hacia otras unidades. LIDER_MECANIZADOS y
# LIDER_SERVICIOS no cambian la unidad de la OP. LIDER_METALISTERIA se agrega aquí (y en
# UNIDAD_POR_LIDER) cuando exista su rol; mientras tanto la lista queda vacía.
LIDERES_CAMBIAN_UNIDAD: list = []
# CALIDAD_PRODUCTO traslada cualquier OP; ningún otro rol cambia la unidad (tampoco ADMIN).
ROLES_CAMBIAR_UNIDAD_OP = [*LIDERES_CAMBIAN_UNIDAD, CALIDAD_PRODUCTO]
# Carga manual de tiempos desde la orden de fabricación (app/api/v1/tiempos_manuales.py): la hace
# quien tiene PERM_TIEMPOS_REGISTRAR, salvo OPERARIO (registra con el cronómetro de su puesto, no
# agrega tiempos a mano). Los costos de los tiempos solo los ven COSTOS y JEFE_PRODUCCION.
ROLES_SIN_CARGA_MANUAL_TIEMPOS = [OPERARIO]
ROLES_COSTOS_TIEMPOS = [COSTOS, JEFE_PRODUCCION]
# Mapa de la OP en el modal de expediente (app/api/v1/mapa_op.py; tabla de Alejo, 2026-11-17).
# Nodos del mapa de relaciones por rol; el valor cotizado va por PERM_VALOR_COTIZADO_VER.
ROLES_MAPA_PEDIDO = [VENTAS, JEFE_PRODUCCION, COSTOS]
ROLES_MAPA_COTIZACION = [VENTAS, JEFE_PRODUCCION, COSTOS]
ROLES_MAPA_CLIENTE = [JEFE_PRODUCCION, VENTAS, LIDER_MECANIZADOS, LIDER_SERVICIOS, GESTION_CALIDAD]
# Los líderes de unidad (el de Metalistería entra con UNIDAD_POR_LIDER cuando exista) y el Jefe
ROLES_MAPA_OTRAS_OP = [*UNIDAD_POR_LIDER, JEFE_PRODUCCION]
ROLES_MAPA_PLANOS = [DIBUJANTE, LIDER_DISENO, JEFE_PRODUCCION, CALIDAD_PRODUCTO]
# Recibos de producción: entregas de material a la OP e ingresos a stock PT
ROLES_MAPA_RECIBOS = [COSTOS, JEFE_PRODUCCION]
# Mapa de procesos: roles de producción (sin OPERARIO) y COSTOS, que ve los tiempos
# (ROLES_COSTOS_TIEMPOS); los de producción lo abren por defecto
ROLES_MAPA_PROCESOS_POR_DEFECTO = [JEFE_PRODUCCION, LIDER_MECANIZADOS, LIDER_SERVICIOS, DIRECTOR_PRODUCCION, PRODUCCION]
ROLES_MAPA_PROCESOS = [*ROLES_MAPA_PROCESOS_POR_DEFECTO, COSTOS]
ROLES_APROBAR_PLANO = [ADMIN, LIDER_DISENO, DISENO]
ROLES_REVISION_PLANO = [ADMIN, LIDER_DISENO, DIBUJANTE, DISENO]
ROLES_CALIDAD_LOTE = [ADMIN, CALIDAD_PRODUCTO, CALIDAD]
ROLES_HISTORIAL_CONSULTA = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, ALMACEN, JEFE_PRODUCCION, LIDER_MECANIZADOS,
    LIDER_SERVICIOS, COSTOS, MANTENIMIENTO, LIDER_DISENO, DIBUJANTE, DIRECTOR_PRODUCCION, DISENO,
    PRODUCCION, CALIDAD,
]
# Suspender y reactivar documentos (congela el reloj de productividad)
ROLES_SUSPENDER = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, JEFE_PRODUCCION, LIDER_MECANIZADOS,
    MANTENIMIENTO, LIDER_DISENO, DIBUJANTE, DISENO, PRODUCCION, CALIDAD,
]
ROLES_TRAZABILIDAD = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, ALMACEN, JEFE_PRODUCCION, LIDER_MECANIZADOS,
    LIDER_SERVICIOS, COSTOS, LIDER_DISENO, DIBUJANTE, DIRECTOR_PRODUCCION, DISENO, PRODUCCION, CALIDAD,
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
    # Solo OP de su área (desde que se crean) e información e histórico del cliente
    LIDER_SERVICIOS: [BUSQUEDA_OP, BUSQUEDA_CLIENTE],
}
