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
PRODUCCION = "PRODUCCION"  # pasa a JEFE_PRODUCCION, LIDER_PRODUCCION y OPERARIO
CALIDAD = "CALIDAD"  # pasa a CALIDAD_PRODUCTO y GESTION_CALIDAD

# --- Roles nuevos de SCRUM-27 -----------------------------------------------------------------
CALIDAD_PRODUCTO = "CALIDAD_PRODUCTO"
GESTION_CALIDAD = "GESTION_CALIDAD"
JEFE_PRODUCCION = "JEFE_PRODUCCION"
LIDER_PRODUCCION = "LIDER_PRODUCCION"
OPERARIO = "OPERARIO"
COSTOS = "COSTOS"
LIDER_DISENO = "LIDER_DISENO"
DIBUJANTE = "DIBUJANTE"
GERENCIA = "GERENCIA"
SECRETARIA_GERENCIA = "SECRETARIA_GERENCIA"
LIDER_LOGISTICA = "LIDER_LOGISTICA"
DIRECTOR_PRODUCCION = "DIRECTOR_PRODUCCION"  # antes "ingeniero jefe"

ROLES_CATALOGO = [
    ADMIN, VENTAS, CALIDAD_PRODUCTO, GESTION_CALIDAD, ALMACEN, JEFE_PRODUCCION, LIDER_PRODUCCION,
    OPERARIO, COSTOS, MANTENIMIENTO, LIDER_DISENO, DIBUJANTE, GERENCIA, SECRETARIA_GERENCIA,
    LIDER_LOGISTICA, DIRECTOR_PRODUCCION,
]
ROLES_ANTERIORES = [DISENO, PRODUCCION, CALIDAD]

# --- Grupos por acción ------------------------------------------------------------------------
ROLES_SOLO_ADMIN = [ADMIN]
# Datos maestros: socios, personal, cuentas de costos y catálogos (lectura)
ROLES_LECTURA = [ADMIN, VENTAS, DISENO, ALMACEN, PRODUCCION, CALIDAD]
# Movimientos de almacén, artículos, categorías, unidades y materiales
ROLES_GESTION_ALMACEN = [ADMIN, ALMACEN]
# Cotizaciones y confirmación del pedido
ROLES_VENTAS = [ADMIN, VENTAS]
ROLES_STOCK_PT = [ADMIN, VENTAS, ALMACEN]
ROLES_EXPEDIENTE_OP = [ADMIN, VENTAS, DISENO, ALMACEN, PRODUCCION, CALIDAD]
# Cambios de estado de la OP distintos de la liberación (esa va por PERM_OP_LIBERAR)
ROLES_ACTUALIZAR_OP = [ADMIN, PRODUCCION]
ROLES_APROBAR_PLANO = [DISENO]
ROLES_REVISION_PLANO = [DISENO]
ROLES_CALIDAD_LOTE = [ADMIN, CALIDAD]
ROLES_HISTORIAL_CONSULTA = [ADMIN, VENTAS, DISENO, ALMACEN, PRODUCCION, CALIDAD, MANTENIMIENTO]
# Suspender y reactivar documentos (congela el reloj de productividad)
ROLES_SUSPENDER = [ADMIN, VENTAS, DISENO, PRODUCCION, CALIDAD, MANTENIMIENTO]
ROLES_TRAZABILIDAD = [ADMIN, VENTAS, DISENO, ALMACEN, PRODUCCION, CALIDAD]
