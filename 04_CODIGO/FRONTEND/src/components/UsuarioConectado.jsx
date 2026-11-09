import React, { useEffect, useState } from 'react';
import { obtenerSesion } from '../services/sesion';

// Casilla global con el usuario autenticado (nombre y rol del login). Sin sesión no se muestra.
export default function UsuarioConectado({ className = '' }) {
  const [sesion, setSesion] = useState(() => obtenerSesion());

  useEffect(() => {
    // Otra pestaña puede iniciar o cerrar sesión
    const actualizar = () => setSesion(obtenerSesion());
    window.addEventListener('storage', actualizar);
    return () => window.removeEventListener('storage', actualizar);
  }, []);

  if (!sesion) return null;
  return (
    <div
      title={sesion.email}
      className={`bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-200 text-xs font-semibold text-blue-900 ${className}`}
    >
      👤 Usuario: <strong>{sesion.nombre}</strong>{sesion.rol ? ` [${sesion.rol}]` : ''}
    </div>
  );
}
