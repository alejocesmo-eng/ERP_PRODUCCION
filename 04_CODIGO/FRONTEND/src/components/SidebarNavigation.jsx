// src/componentes/SidebarNavigation.jsx
import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

export const SidebarNavigation = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('sgi_token');
    window.location.href = '/';
  };

  const isActive = (path) => 
    location.pathname === path 
      ? 'bg-blue-600 text-white font-bold' 
      : 'text-slate-300 hover:bg-slate-800 hover:text-white';

  return (
    <aside className="w-64 bg-slate-900 text-white min-h-screen p-4 flex flex-col justify-between border-r border-slate-800 shadow-xl">
      <div>
        {/* ENCABEZADO CORPORATIVO SGI */}
        <div className="border-b border-slate-800 pb-4 mb-6">
          <h1 className="font-extrabold text-lg tracking-wide text-blue-400">SGI — ISO 9001:2026</h1>
          <p className="text-[11px] text-slate-400 mt-0.5">Sistema de Gestión Integral</p>
        </div>

        {/* NAVEGACIÓN MISIONAL POR NIVELES */}
        <nav className="space-y-6 text-xs">
          {/* NIVEL 1 — DIRECCIÓN */}
          <div>
            <h2 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Nivel 1 — Dirección</h2>
            <ul className="space-y-1">
              <li>
                <Link to="/dashboard" className={`block py-2 px-3 rounded transition ${isActive('/dashboard')}`}>
                  📊 Dashboard Gerencial
                </Link>
              </li>
            </ul>
          </div>

          {/* NIVEL 2 — OPERACIÓN */}
          <div>
            <h2 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Nivel 2 — Operación</h2>
            <ul className="space-y-1">
              <li>
                <Link to="/ventas/proyectos" className={`block py-2 px-3 rounded transition ${isActive('/ventas/proyectos')}`}>
                  🤝 Ventas / Proyectos
                </Link>
              </li>
              <li>
                <Link to="/diseno/planos" className={`block py-2 px-3 rounded transition ${isActive('/diseno/planos')}`}>
                  📐 Diseño e Ingeniería
                </Link>
              </li>
              <li>
                <Link to="/compras/gestion" className={`block py-2 px-3 rounded transition ${isActive('/compras/gestion')}`}>
                  🛒 Compras y Proveedores
                </Link>
              </li>
              <li>
                <Link to="/inventario/general" className={`block py-2 px-3 rounded transition ${isActive('/inventario/general')}`}>
                  🧾 Inventario General
                </Link>
              </li>
              <li>
                <Link to="/configuracion/maestros" className={`block py-2 px-3 rounded transition ${isActive('/configuracion/maestros')}`}>
                  ⚙️ Datos Maestros
                </Link>
              </li>
              <li>
                <Link to="/almacen/inventario" className={`block py-2 px-3 rounded transition ${isActive('/almacen/inventario')}`}>
                  📦 Almacén Operativo
                </Link>
              </li>
              <li>
                <Link to="/produccion" className={`block py-2 px-3 rounded transition ${isActive('/produccion')}`}>
                  🏭 Producción y Planta
                </Link>
              </li>
              <li>
                <Link to="/mantenimiento/planta" className={`block py-2 px-3 rounded transition ${isActive('/mantenimiento/planta')}`}>
                  🔧 Mantenimiento de Planta
                </Link>
              </li>
              <li>
                <Link to="/produccion/capacidad" className={`block py-2 px-3 rounded transition ${isActive('/produccion/capacidad')}`}>
                  🕹️ Carga de Máquinas
                </Link>
              </li>
              <li>
                <Link to="/costos/liquidacion" className={`block py-2 px-3 rounded transition ${isActive('/costos/liquidacion')}`}>
                  💵 Costos por OP
                </Link>
              </li>
            </ul>
          </div>

          {/* NIVEL 3 — CALIDAD & METROLOGÍA */}
          <div>
            <h2 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Nivel 3 — Calidad & Metrología</h2>
            <ul className="space-y-1">
              <li>
                <Link to="/calidad/producto" className={`block py-2 px-3 rounded transition ${isActive('/calidad/producto')}`}>
                  🗜️ Metrología / Calidad de Producto
                </Link>
              </li>
             
              <li>
                <Link to="/calidad/rnc-capa" className={`block py-2 px-3 rounded transition ${isActive('/calidad/rnc-capa')}`}>
                  📋 RNC / Acciones Correctivas
                </Link>
              </li>
            </ul>
          </div>

          {/* NIVEL 4 — EJECUCIÓN MES EN PLANTA */}
          <div>
            <h2 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
              Nivel 4 — Ejecución Planta
            </h2>
            <ul className="space-y-1">
              <li>
                <button
                  type="button"
                  onClick={() => navigate('/produccion/operario')}
                  className={`w-full text-left py-2 px-3 rounded transition font-bold flex items-center gap-2 cursor-pointer ${isActive('/produccion/operario')}`}
                >
                  📱 Tablet Operario MES
                </button>
              </li>
            </ul>
          </div>
        </nav>
      </div>

      {/* PIE DE PÁGINA CON BOTÓN DE CERRAR SESIÓN */}
      <div className="border-t border-slate-800 pt-4 space-y-3">
        <button
          type="button"
          onClick={handleLogout}
          className="w-full py-2 bg-red-900/40 hover:bg-red-800 text-red-200 border border-red-700/50 rounded text-xs font-bold transition flex items-center justify-center gap-2 cursor-pointer"
        >
          🚪 Cerrar Sesión
        </button>
        <div className="text-[10px] text-slate-500 text-center">
          Control de Acceso & Trazabilidad
        </div>
      </div>
    </aside>
  );
};

export default SidebarNavigation;