// src/services/sesion.js
// Sesión del usuario autenticado. El token de /auth/token es la fuente del identificador interno
// (sub = id_usuario, migración 34), del rol y de la caducidad; el nombre y el usuario son los que
// devolvió esa misma respuesta de login y solo se usan si pertenecen al mismo identificador del
// token. No hay valores por defecto: sin token válido no hay sesión.

const CLAVE_TOKEN = 'sgi_token';
const CLAVE_SESION = 'sgi_sesion';

function leer(clave) {
  try {
    return localStorage.getItem(clave);
  } catch {
    return null;
  }
}

// Carga útil del JWT (sin verificar la firma: la verifica el backend en cada petición)
export function datosDelToken(token) {
  try {
    const segmento = token.split('.')[1];
    const base64 = segmento.replace(/-/g, '+').replace(/_/g, '/');
    const relleno = '='.repeat((4 - (base64.length % 4)) % 4);
    const bytes = Uint8Array.from(window.atob(base64 + relleno), (caracter) => caracter.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

export function obtenerSesion() {
  const token = leer(CLAVE_TOKEN)?.trim();
  if (!token) return null;
  const datos = datosDelToken(token);
  if (!datos?.sub) return null;
  if (datos.exp && datos.exp * 1000 <= Date.now()) return null;
  let guardada = null;
  try {
    guardada = JSON.parse(leer(CLAVE_SESION) || 'null');
  } catch {
    guardada = null;
  }
  const propia = guardada?.id_usuario === datos.sub ? guardada : null;
  return {
    id_usuario: datos.sub,
    usuario: propia?.usuario || null,
    rol: datos.rol || null,
    nombre: propia?.nombre || propia?.usuario || 'Usuario'
  };
}

// Guarda la respuesta de POST /auth/token: el token, el nombre y el usuario con que se entró
export function guardarSesion(respuesta) {
  const token = respuesta.access_token;
  localStorage.setItem(CLAVE_TOKEN, token);
  const datos = datosDelToken(token);
  localStorage.setItem(CLAVE_SESION, JSON.stringify({
    id_usuario: datos?.sub || null,
    nombre: respuesta.usuario || null,
    usuario: respuesta.nombre_usuario || null
  }));
}

export function cerrarSesion() {
  localStorage.removeItem(CLAVE_TOKEN);
  localStorage.removeItem(CLAVE_SESION);
}
