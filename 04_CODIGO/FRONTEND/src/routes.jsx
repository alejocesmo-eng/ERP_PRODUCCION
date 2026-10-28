// src/routes.jsx
import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './AppLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import LoginView from './views/LoginView';

import ProyectosView from './views/nivel2/ProyectosView';
import DisenoPlanosView from './views/nivel2/DisenoPlanosView';
import ComprasGestionView from './views/nivel2/ComprasGestionView';
import AlmacenInventarioView from './views/nivel2/AlmacenInventarioView';
import InventarioGeneralView from './views/nivel2/InventarioGeneralView';
import ConfiguracionMaestrosView from './views/nivel2/ConfiguracionMaestrosView';
import MantenimientoPlantaView from './views/nivel2/MantenimientoPlantaView';
import GanttCargaMaquinasView from './views/nivel2/GanttCargaMaquinasView';
import CalidadRncCapaView from './views/nivel2/CalidadRncCapaView';
import CostosLiquidacionOpView from './views/nivel2/CostosLiquidacionOpView';

// MÓDULOS DE PRODUCCIÓN Y EJECUCIÓN MES (NIVEL 3)
import ProduccionLiderView from './views/nivel3/ProduccionLiderView';
import ProduccionOperarioView from './views/nivel3/ProduccionOperarioView';

// MÓDULO DE CALIDAD Y METROLOGÍA DE PRODUCTO (NIVEL 3 - ISO 9001:2026)
import CalidadProductoView from './views/nivel3/CalidadProductoView';

export const AppRoutes = () => {
  const token = localStorage.getItem('sgi_token');

  return (
    <Routes>
      <Route
        path="/login"
        element={token ? <Navigate to="/ventas/proyectos" replace /> : <LoginView />}
      />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/ventas/proyectos" replace />} />
          <Route path="/ventas/proyectos" element={<ProyectosView />} />
          <Route path="/diseno/planos" element={<DisenoPlanosView />} />
          <Route path="/compras/gestion" element={<ComprasGestionView />} />
          <Route path="/inventario/general" element={<InventarioGeneralView />} />
          <Route path="/configuracion/maestros" element={<ConfiguracionMaestrosView />} />
          <Route path="/configuracion" element={<Navigate to="/configuracion/maestros" replace />} />
          <Route path="/mantenimiento/planta" element={<MantenimientoPlantaView />} />
          <Route path="/produccion/capacidad" element={<GanttCargaMaquinasView />} />
          <Route path="/calidad/rnc-capa" element={<CalidadRncCapaView />} />
          <Route path="/costos/liquidacion" element={<CostosLiquidacionOpView />} />
          <Route path="/almacen/inventario" element={<AlmacenInventarioView />} />

          {/* RUTAS DE PRODUCCIÓN MES [ISO 9001:2026] */}
          <Route path="/produccion" element={<ProduccionLiderView />} />
          <Route path="/produccion/operario" element={<ProduccionOperarioView />} />
          <Route path="/operario" element={<ProduccionOperarioView />} />

          {/* RUTA DE CALIDAD DE PRODUCTO E INSPECCIÓN */}
          <Route path="/calidad/producto" element={<CalidadProductoView />} />

          <Route path="*" element={<Navigate to="/ventas/proyectos" replace />} />
        </Route>
      </Route>
    </Routes>
  );
};

export default AppRoutes;