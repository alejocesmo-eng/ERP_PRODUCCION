// src/services/configuracionUsuarios.js
// Administración de usuarios (BACKEND/app/api/v1/configuracion_usuarios.py). Solo ADMIN: el backend
// lee el rol de la base en cada consulta y responde 403 a cualquier otro rol.
import API from './api';

const RUTA = '/configuracion/usuarios';

export const listarUsuarios = () => API.get(RUTA).then((respuesta) => respuesta.data);

export const sugerirUsuario = (nombres, apellidos) =>
  API.get(`${RUTA}/sugerencia`, { params: { nombres, apellidos } }).then((respuesta) => respuesta.data?.usuario || '');

export const crearUsuario = (datos) => API.post(RUTA, datos).then((respuesta) => respuesta.data);

export const editarUsuario = (idUsuario, cambios) =>
  API.patch(`${RUTA}/${idUsuario}`, cambios).then((respuesta) => respuesta.data);

export const asignarClave = (idUsuario, clave) => API.put(`${RUTA}/${idUsuario}/clave`, { clave });

export const cambiarActivo = (idUsuario, activo) =>
  API.post(`${RUTA}/${idUsuario}/${activo ? 'reactivar' : 'desactivar'}`).then((respuesta) => respuesta.data);

export const historialUsuario = (idUsuario) =>
  API.get(`${RUTA}/${idUsuario}/historial`).then((respuesta) => respuesta.data);
