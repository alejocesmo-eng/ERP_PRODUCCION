// src/services/permisos.js
// Permisos del rol del usuario (GET /auth/permisos, desde rol_permisos). Deciden qué módulos y
// pestañas muestra la interfaz; el backend sigue validando cada ruta por su cuenta.
// Sin respuesta del backend no hay permisos: nada se muestra por defecto.
import { useEffect, useState } from 'react';
import API from './api';

// Durante la transición de SCRUM-27 ADMIN ve todos los módulos
const PERMISO_ADMIN_TOTAL = 'PERM_ADMIN_ALL';

let cache = { token: null, promesa: null };

export function cargarPermisos() {
  const token = localStorage.getItem('sgi_token')?.trim() || null;
  if (!token) return Promise.resolve([]);
  if (cache.token !== token || !cache.promesa) {
    cache = {
      token,
      promesa: API.get('/auth/permisos')
        .then((respuesta) => (Array.isArray(respuesta.data?.permisos) ? respuesta.data.permisos : []))
        .catch(() => {
          cache = { token: null, promesa: null };
          return [];
        })
    };
  }
  return cache.promesa;
}

// Tras cambiar permisos en Configuración: la siguiente consulta vuelve a pedirlos al backend
export function limpiarCachePermisos() {
  cache = { token: null, promesa: null };
}

export function tienePermiso(permisos, idPermiso) {
  return permisos.includes(idPermiso) || permisos.includes(PERMISO_ADMIN_TOTAL);
}

export function usePermisos() {
  const [permisos, setPermisos] = useState([]);
  useEffect(() => {
    let activo = true;
    cargarPermisos().then((lista) => {
      if (activo) setPermisos(lista);
    });
    return () => {
      activo = false;
    };
  }, []);
  return permisos;
}
