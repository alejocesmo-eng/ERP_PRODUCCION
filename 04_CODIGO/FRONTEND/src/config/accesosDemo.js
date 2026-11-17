// src/config/accesosDemo.js
// Acceso rápido de desarrollo (SCRUM-34): los 18 usuarios de reglas/usuarios-demo.md, uno por
// rol, agrupados por área. Solo lo usa LoginView cuando import.meta.env.DEV es true; en el build
// de producción la lista queda fuera del bundle. Se entra con el usuario (migración 34): la parte
// antes de la @ de los correos de USUARIOS_DEMO en BACKEND/scripts/preparar_sandbox.py. La clave no va aquí: sale de VITE_DEV_LOGIN_PASSWORD.

export const ACCESOS_DEMO = [
  { area: 'Administración', usuarios: [
    { usuario: 'admin', label: 'Admin técnico' }
  ] },
  { area: 'Comercial', usuarios: [
    { usuario: 'ventas', label: 'Ventas' }
  ] },
  { area: 'Diseño', usuarios: [
    { usuario: 'liderdiseno', label: 'Líder de diseño' },
    { usuario: 'dibujante', label: 'Dibujante' }
  ] },
  { area: 'Producción', usuarios: [
    { usuario: 'director', label: 'Director de producción' },
    { usuario: 'jefeprod', label: 'Jefe de producción' },
    { usuario: 'liderprod', label: 'Líder de Mecanizados' },
    { usuario: 'liderservicios', label: 'Líder de Servicios' },
    { usuario: 'operario', label: 'Operario' },
    { usuario: 'capturista_tiempos', label: 'Capturista de tiempos' }
  ] },
  { area: 'Calidad', usuarios: [
    { usuario: 'calidadprod', label: 'Calidad de producto' },
    { usuario: 'gestioncal', label: 'Gestión de calidad' }
  ] },
  { area: 'Almacén y logística', usuarios: [
    { usuario: 'almacen', label: 'Almacén' },
    { usuario: 'logistica', label: 'Líder de logística' }
  ] },
  { area: 'Costos', usuarios: [
    { usuario: 'costos', label: 'Costos' }
  ] },
  { area: 'Mantenimiento', usuarios: [
    { usuario: 'mantenimiento', label: 'Mantenimiento' }
  ] },
  { area: 'Gerencia', usuarios: [
    { usuario: 'gerencia', label: 'Gerencia' },
    { usuario: 'secretaria', label: 'Secretaria de gerencia' }
  ] }
];
