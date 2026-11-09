import React, { useState } from 'react';
import API from '../services/api';

export default function LoginView({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await API.post('/auth/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        timeout: 5000
      });

      const { access_token } = response.data;
      if (typeof access_token !== 'string' || !access_token.trim()) {
        throw new Error('El servidor de autenticación no devolvió un token válido.');
      }

      // 1. Guardar token inmutable en localStorage
      localStorage.setItem('sgi_token', access_token);

      // 2. Ejecutar callback de éxito o forzar redirección
      if (onLoginSuccess) {
        onLoginSuccess(access_token);
      } else {
        window.location.href = '/ventas/proyectos';
      }
    } catch (err) {
      console.error("Error en autenticación:", err);
      if (err.code === 'ECONNABORTED') {
        setError('El servidor Backend (FastAPI) no responde en el puerto 8000.');
      } else if (err.message === 'El servidor de autenticación no devolvió un token válido.') {
        setError(err.message);
      } else {
        setError(err.response?.data?.detail || 'Credenciales inválidas o servidor inalcanzable.');
      }
    } finally {
      setLoading(false);
    }
  };

  // Acceso rápido solo en desarrollo: en el build de producción import.meta.env.DEV es false
  // y ni la función ni la clave se incluyen en el bundle.
  // La clave de los usuarios demo no se escribe en el código: sale de VITE_DEV_LOGIN_PASSWORD
  // (04_CODIGO/FRONTEND/.env.local, no versionado), con el mismo valor que SGI_SANDBOX_DEMO_PASSWORD.
  const claveAccesoRapido = import.meta.env.DEV ? import.meta.env.VITE_DEV_LOGIN_PASSWORD : undefined;
  const fastLogin = import.meta.env.DEV ? async (email) => {
    if (!claveAccesoRapido) {
      setError('Acceso rápido no configurado: defina VITE_DEV_LOGIN_PASSWORD en 04_CODIGO/FRONTEND/.env.local y reinicie Vite.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', claveAccesoRapido);

      const response = await API.post('/auth/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      const { access_token } = response.data;
      localStorage.setItem('sgi_token', access_token);
      if (onLoginSuccess) {
        onLoginSuccess(access_token);
      } else {
        window.location.href = '/ventas/proyectos';
      }
    } catch (err) {
      setError('Error en acceso rápido: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  } : null;

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-lg shadow-xl p-8 border border-slate-200">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-slate-800">SGI — ISO 9001:2026</h1>
          <p className="text-xs text-slate-500 mt-1">Sistema de Gestión Integral & Control de Procesos</p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-300 text-red-800 rounded text-xs font-semibold">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Usuario / Correo Corporativo</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full p-2.5 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              placeholder="admin@sgi.com"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full p-2.5 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded text-sm transition"
          >
            {loading ? 'Autenticando...' : 'Iniciar Sesión en SGI'}
          </button>
        </form>

        <div className="mt-6 text-center text-[11px] text-slate-400">
          Control de Acceso Autenticado — [ISO 9001:2026]
        </div>

        {import.meta.env.DEV && (
        <div className="mt-8 pt-6 border-t border-slate-100">
          <p className="text-[10px] font-bold text-slate-400 uppercase mb-3 text-center">Acceso de Pruebas (Dev Mode)</p>
          {!claveAccesoRapido && (
            <p className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 mb-3 text-center">
              Defina VITE_DEV_LOGIN_PASSWORD en 04_CODIGO/FRONTEND/.env.local y reinicie Vite para usar estos accesos.
            </p>
          )}
          <div className="grid grid-cols-2 gap-2">
            {[
              { email: 'admin@sgi.com', label: 'Admin' },
              { email: 'jefe_diseno@sgi.local', label: 'Jefe Ing.' },
              { email: 'dibujante_1@sgi.local', label: 'Dibujante 1' },
              { email: 'lider_produccion@sgi.local', label: 'Líder Prod.' },
            ].map((user) => (
              <button
                key={user.email}
                onClick={() => fastLogin(user.email)}
                disabled={loading || !claveAccesoRapido}
                className="py-1.5 px-2 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded text-[10px] transition border border-slate-200 font-medium"
              >
                {user.label}
              </button>
            ))}
          </div>
        </div>
        )}
      </div>
    </div>
  );
}