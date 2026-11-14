// src/config/accesosDemo.js
// Acceso rápido de desarrollo (SCRUM-34): los 18 usuarios de reglas/usuarios-demo.md, uno por
// rol, agrupados por área. Solo lo usa LoginView cuando import.meta.env.DEV es true; en el build
// de producción la lista queda fuera del bundle. Los mismos correos están en USUARIOS_DEMO de
// BACKEND/scripts/preparar_sandbox.py. La clave no va aquí: sale de VITE_DEV_LOGIN_PASSWORD.

export const ACCESOS_DEMO = [
  { area: 'Administración', usuarios: [
    { email: 'admin@sgi.local', label: 'Admin técnico' }
  ] },
  { area: 'Comercial', usuarios: [
    { email: 'ventas@sgi.local', label: 'Ventas' }
  ] },
  { area: 'Diseño', usuarios: [
    { email: 'liderdiseno@sgi.local', label: 'Líder de diseño' },
    { email: 'dibujante@sgi.local', label: 'Dibujante' }
  ] },
  { area: 'Producción', usuarios: [
    { email: 'director@sgi.local', label: 'Director de producción' },
    { email: 'jefeprod@sgi.local', label: 'Jefe de producción' },
    { email: 'liderprod@sgi.local', label: 'Líder de Mecanizados' },
    { email: 'liderservicios@sgi.local', label: 'Líder de Servicios' },
    { email: 'operario@sgi.local', label: 'Operario' },
    { email: 'capturista_tiempos@sgi.local', label: 'Capturista de tiempos' }
  ] },
  { area: 'Calidad', usuarios: [
    { email: 'calidadprod@sgi.local', label: 'Calidad de producto' },
    { email: 'gestioncal@sgi.local', label: 'Gestión de calidad' }
  ] },
  { area: 'Almacén y logística', usuarios: [
    { email: 'almacen@sgi.local', label: 'Almacén' },
    { email: 'logistica@sgi.local', label: 'Líder de logística' }
  ] },
  { area: 'Costos', usuarios: [
    { email: 'costos@sgi.local', label: 'Costos' }
  ] },
  { area: 'Mantenimiento', usuarios: [
    { email: 'mantenimiento@sgi.local', label: 'Mantenimiento' }
  ] },
  { area: 'Gerencia', usuarios: [
    { email: 'gerencia@sgi.local', label: 'Gerencia' },
    { email: 'secretaria@sgi.local', label: 'Secretaria de gerencia' }
  ] }
];
