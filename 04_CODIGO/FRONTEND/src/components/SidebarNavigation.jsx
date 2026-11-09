// src/componentes/SidebarNavigation.jsx
import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { cerrarSesion } from '../services/sesion';

export const SidebarNavigation = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);

  const handleLogout = () => {
    cerrarSesion();
    window.location.href = '/';
  };

  const isActive = (path) =>
    location.pathname === path
      ? 'bg-blue-600 text-white font-bold shadow-sm'
      : 'text-slate-300 hover:bg-slate-800 hover:text-white';

  return (
    <>
      {/* 1. BOTÓN FLOTANTE PARA DESPLEGAR */}
      <button
        type="button"
        onClick={() => setVisible(true)}
        onMouseEnter={() => setVisible(true)}
        aria-label="Abrir menú de navegación"
        className={`fixed top-4 left-4 z-40 p-2.5 rounded-xl bg-slate-900/90 text-white border border-slate-700 shadow-xl backdrop-blur-md hover:bg-slate-800 hover:border-blue-500 transition-all duration-300 flex items-center justify-center cursor-pointer ${
          visible ? 'opacity-0 pointer-events-none scale-75' : 'opacity-100 scale-100'
        }`}
      >
        <svg
          className="w-5 h-5 text-blue-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 6h16M4 12h16M4 18h16"
          />
        </svg>
      </button>

      {/* 2. MENÚ LATERAL (Se oculta solo al retirar el cursor con onMouseLeave) */}
      <aside
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        className={`fixed top-4 left-0 w-64 bg-slate-900/95 backdrop-blur-md text-white border-y border-r border-slate-800 rounded-r-2xl shadow-2xl p-4 z-50 transition-all duration-300 ease-in-out select-none flex flex-col gap-4 ${
          visible
            ? 'translate-x-0 opacity-100 pointer-events-auto'
            : '-translate-x-full opacity-0 pointer-events-none'
        }`}
      >
        {/* CABECERA */}
        <div className="border-b border-slate-800 pb-3 flex items-center justify-between">
          <div>
            <h1 className="font-extrabold text-3xl tracking-wide text-blue-400">
              PRISMA
            </h1>
            <p className="text-[10px] text-slate-400 mt-0.5">Sistema de Gestión Integral</p>
          </div>
          {/* Botón opcional para cerrar de forma manual */}
          <button
            type="button"
            onClick={() => setVisible(false)}
            className="text-slate-400 hover:text-white p-1 rounded-md hover:bg-slate-800 transition"
            aria-label="Cerrar menú"
          >
            ✕
          </button>
        </div>

        {/* NAVEGACIÓN MISIONAL */}
        <nav className="space-y-4 text-xs overflow-y-auto max-h-[calc(100vh-140px)] pr-1">
          {/* NIVEL 2 — OPERACIÓN */}
          <div>
            <h2 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
              Nivel 2 — Operación
            </h2>
            <ul className="space-y-1">
              <li>
                <Link
                  to="/ventas/proyectos"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/ventas/proyectos')}`}
                >
                  <span className="text-sm">🤝</span>
                  <span className="truncate">Ventas / Proyectos</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/diseno/planos"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/diseno/planos')}`}
                >
                  <span className="text-sm">📐</span>
                  <span className="truncate">Diseño e Ingeniería</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/compras/gestion"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/compras/gestion')}`}
                >
                  <span className="text-sm">🛒</span>
                  <span className="truncate">Compras y Proveedores</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/inventario/general"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/inventario/general')}`}
                >
                  <span className="text-sm">📋</span>
                  <span className="truncate">Inventario General</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/almacen/inventario"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/almacen/inventario')}`}
                >
                  <span className="text-sm">📦</span>
                  <span className="truncate">Almacén e Inventarios</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/produccion"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/produccion')}`}
                >
                  <span className="text-sm">🏭</span>
                  <span className="truncate">Producción y Planta</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/mantenimiento/planta"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/mantenimiento/planta')}`}
                >
                  <span className="text-sm">🔧</span>
                  <span className="truncate">Mantenimiento de Planta</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/produccion/capacidad"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/produccion/capacidad')}`}
                >
                  <span className="text-sm">🕹️</span>
                  <span className="truncate">Carga de Máquinas</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/costos/liquidacion"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/costos/liquidacion')}`}
                >
                  <span className="text-sm">💵</span>
                  <span className="truncate">Costos por OP</span>
                </Link>
              </li>
            </ul>
          </div>

          {/* NIVEL 3 — CALIDAD */}
          <div>
            <h2 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
              Nivel 3 — Calidad
            </h2>
            <ul className="space-y-1">
              <li>
                <Link
                  to="/calidad/producto"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/calidad/producto')}`}
                >
                  <span className="text-sm">🗜️</span>
                  <span className="truncate">Metrología / Calidad</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/calidad/rnc-capa"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/calidad/rnc-capa')}`}
                >
                  <span className="text-sm">📋</span>
                  <span className="truncate">RNC / Acciones Correctivas</span>
                </Link>
              </li>
            </ul>
          </div>

          {/* NIVEL 4 — PLANTA */}
          <div>
            <h2 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
              Nivel 4 — Planta
            </h2>
            <ul className="space-y-1">
              <li>
                <button
                  type="button"
                  onClick={() => {
                    setVisible(false);
                    navigate('/produccion/operario');
                  }}
                  className={`w-full text-left py-1.5 px-2.5 rounded-lg transition font-bold flex items-center gap-2.5 cursor-pointer ${isActive(
                    '/produccion/operario'
                  )}`}
                >
                  <span className="text-sm">📱</span>
                  <span className="truncate">Tablet Operario MES</span>
                </button>
              </li>
            </ul>
          </div>

          {/* NIVEL 5 — CONFIGURACIÓN & DATOS MAESTROS */}
          <div>
            <h2 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
              Nivel 5 — Configuración
            </h2>
            <ul className="space-y-1">
              <li>
                <Link
                  to="/configuracion/maestros"
                  onClick={() => setVisible(false)}
                  className={`flex items-center gap-2.5 py-1.5 px-2.5 rounded-lg transition ${isActive('/configuracion/maestros')}`}
                >
                  <span className="text-sm">⚙️</span>
                  <span className="truncate">Datos Maestros</span>
                </Link>
              </li>
            </ul>
          </div>
        </nav>

        {/* PIE CON BOTÓN DE CERRAR SESIÓN */}
        <div className="border-t border-slate-800 pt-3">
          <button
            type="button"
            onClick={handleLogout}
            className="w-full py-2 px-3 bg-red-950/60 hover:bg-red-800 text-red-200 border border-red-800/60 rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 cursor-pointer shadow-sm"
          >
            <span>🚪</span>
            <span>Cerrar Sesión</span>
          </button>
        </div>
      </aside>
    </>
  );
};

export default SidebarNavigation;