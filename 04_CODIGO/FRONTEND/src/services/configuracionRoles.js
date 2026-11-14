// src/services/configuracionRoles.js
// Configuración de roles y permisos (BACKEND/app/api/v1/configuracion_roles.py). Solo ADMIN entra:
// el backend lee el rol de la base en cada consulta y responde 403 a cualquier otro rol.
import { useEffect, useState } from 'react';
import API from './api';

const RUTA = '/configuracion/roles';

let cache = { token: null, promesa: null };

// Si el usuario ve Configuración de roles en el menú (GET /configuracion/roles/acceso)
export function cargarAccesoConfiguracion() {
  const token = localStorage.getItem('sgi_token')?.trim() || null;
  if (!token) return Promise.resolve(false);
  if (cache.token !== token || !cache.promesa) {
    cache = {
      token,
      promesa: API.get(`${RUTA}/acceso`)
        .then((respuesta) => respuesta.data?.acceso === true)
        .catch(() => {
          cache = { token: null, promesa: null };
          return false;
        })
    };
  }
  return cache.promesa;
}

export function useAccesoConfiguracion() {
  // null mientras se consulta: la vista no decide antes de tener la respuesta
  const [acceso, setAcceso] = useState(null);
  useEffect(() => {
    let activo = true;
    cargarAccesoConfiguracion().then((valor) => {
      if (activo) setAcceso(valor);
    });
    return () => {
      activo = false;
    };
  }, []);
  return acceso;
}

export const listarRoles = () => API.get(`${RUTA}/`);
export const listarCatalogoPermisos = () => API.get(`${RUTA}/permisos`);
export const crearRol = (datos) => API.post(`${RUTA}/`, datos);
export const editarRol = (idRol, datos) => API.patch(`${RUTA}/${encodeURIComponent(idRol)}`, datos);
export const guardarPermisosRol = (idRol, permisos) =>
  API.put(`${RUTA}/${encodeURIComponent(idRol)}/permisos`, { permisos });
export const historialPermisosRol = (idRol) => API.get(`${RUTA}/${encodeURIComponent(idRol)}/historial`);
export const eliminarRol = (idRol) => API.delete(`${RUTA}/${encodeURIComponent(idRol)}`);
