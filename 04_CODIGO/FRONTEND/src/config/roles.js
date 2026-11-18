// src/config/roles.js
// Roles de PRISMA (SCRUM-27, reglas/roles-catalogo.md) y grupos que usa la interfaz para mostrar
// u ocultar acciones. Copian los grupos de BACKEND/app/core/roles.py: el backend valida cada
// ruta por su cuenta, esto solo evita ofrecer botones que responderían 403.
// Durante la transición ADMIN está en todos los grupos y los roles anteriores (DISENO,
// PRODUCCION, CALIDAD) siguen donde estaban. Donde ya hay un permiso en rol_permisos se usa
// services/permisos.js en lugar de estos grupos.

export const ROLES_CATALOGO = [
  'ADMIN', 'VENTAS', 'CALIDAD_PRODUCTO', 'GESTION_CALIDAD', 'ALMACEN', 'JEFE_PRODUCCION',
  'LIDER_MECANIZADOS', 'OPERARIO', 'COSTOS', 'MANTENIMIENTO', 'LIDER_DISENO', 'DIBUJANTE',
  'GERENCIA', 'SECRETARIA_GERENCIA', 'LIDER_LOGISTICA', 'DIRECTOR_PRODUCCION', 'CAPTURISTA_TIEMPOS',
  'LIDER_SERVICIOS'
];
export const ROLES_ANTERIORES = ['DISENO', 'PRODUCCION', 'CALIDAD'];

// GET /ordenes/expediente/{op} (ROLES_EXPEDIENTE_OP). Sin este rol no se ofrece la búsqueda de OP
// ni el botón de expediente: la búsqueda solo muestra lo que el rol puede ver (VENTAS no entra).
// Igual que ROLES_EXPEDIENTE_OP del backend (sin los roles por confirmar, 2026-11-12)
// División del expediente (2026-11-17): DIBUJANTE, LIDER_DISENO y CALIDAD_PRODUCTO lo abren sin costos
export const ROLES_EXPEDIENTE_OP = [
  'ADMIN', 'GESTION_CALIDAD', 'JEFE_PRODUCCION', 'LIDER_MECANIZADOS', 'LIDER_SERVICIOS', 'COSTOS', 'DIRECTOR_PRODUCCION',
  'DIBUJANTE', 'LIDER_DISENO', 'CALIDAD_PRODUCTO', 'PRODUCCION', 'CALIDAD'
];

// Acciones dentro del expediente de OP (ExpedienteOpModal)
export const ROLES_EXPEDIENTE_VENTAS = ['ADMIN', 'VENTAS'];
// Cargar plano, solicitar BOM y liberar la OP (la liberación la decide PERM_OP_LIBERAR en el backend)
export const ROLES_EXPEDIENTE_DISENO = ['ADMIN', 'LIDER_DISENO', 'DIBUJANTE', 'DISENO'];
export const ROLES_EXPEDIENTE_ALMACEN = ['ADMIN', 'ALMACEN'];
// Asignar centro de trabajo y marcar la OP terminada para inspección
export const ROLES_EXPEDIENTE_PRODUCCION = ['ADMIN', 'JEFE_PRODUCCION', 'LIDER_MECANIZADOS', 'PRODUCCION'];
export const ROLES_EXPEDIENTE_CALIDAD = ['ADMIN', 'CALIDAD_PRODUCTO', 'CALIDAD'];
// POST /planos/{id}/aprobar (ROLES_APROBAR_PLANO)
export const ROLES_APROBAR_PLANO = ['ADMIN', 'LIDER_DISENO', 'DISENO'];

// Diseño (DisenoPlanosView)
export const ROLES_DIBUJANTE = ['DIBUJANTE', 'DISENO'];
export const ROLES_APERTURA_ASIGNACION_DISENO = ['ADMIN', 'LIDER_DISENO'];

// Movimientos de remanentes y sobrantes (RemanetesSobrantesView)
export const ROLES_MOVIMIENTOS_REMANENTES = ['ADMIN', 'ALMACEN', 'JEFE_PRODUCCION', 'LIDER_MECANIZADOS', 'PRODUCCION'];

// Captura de tiempos (CapturaTiemposView): CAPTURISTA_TIEMPOS solo ve esta pantalla en el menú y entra
// directo a ella. El backend exige PERM_TIEMPOS_REGISTRAR en cada petición.
export const ROL_CAPTURISTA_TIEMPOS = 'CAPTURISTA_TIEMPOS';
export const RUTA_CAPTURA_TIEMPOS = '/produccion/captura-tiempos';

export function normalizarRol(rol) {
  return String(rol || '').trim().toUpperCase();
}

// Rol reconocido (catálogo o anterior) o cadena vacía
export function rolConocido(rol) {
  const normalizado = normalizarRol(rol);
  return ROLES_CATALOGO.includes(normalizado) || ROLES_ANTERIORES.includes(normalizado) ? normalizado : '';
}

export function rolEn(rol, grupo) {
  return grupo.includes(normalizarRol(rol));
}

export function esCapturista(rol) {
  return normalizarRol(rol) === ROL_CAPTURISTA_TIEMPOS;
}

// Pantalla de inicio después de entrar: la captura para el capturista, Pedidos para los demás
export function rutaInicio(rol) {
  return esCapturista(rol) ? RUTA_CAPTURA_TIEMPOS : '/ventas/proyectos';
}
