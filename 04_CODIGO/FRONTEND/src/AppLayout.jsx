// src/AppLayout.jsx
import React, { useCallback, useEffect, useState } from 'react';
import SidebarNavigation from './components/SidebarNavigation';
import { Outlet, useNavigate } from 'react-router-dom';
import { ProyectosProvider } from './context/ProyectosContext';
import ExpedienteOpModal from './components/modals/ExpedienteOpModal';
import UsuarioConectado from './components/UsuarioConectado';
import BusquedaGeneral, { useAlcanceBusqueda } from './components/BusquedaGeneral';

export default function AppLayout() {
  const navigate = useNavigate();
  const [codigoOpConsultada, setCodigoOpConsultada] = useState('');
  // Alcance de la búsqueda según el rol en la base: tipos de dato y acceso al expediente de OP.
  // Sin tipos no se muestra la caja; sin expediente no se abre el modal (el backend también lo rechaza)
  const alcance = useAlcanceBusqueda();
  const puedeVerExpediente = Boolean(alcance.expediente_op);

  const manejarAccionExpediente = useCallback((accion) => {
    const rutasPorAccion = {
      CONSULTAR_PEDIDO_COMERCIAL: '/ventas/proyectos',
      CARGAR_REEMPLAZAR_PLANO: '/diseno/planos',
      SOLICITAR_BOM: '/diseno/planos',
      IMPUTAR_MATERIAL_KARDEX: '/almacen/inventario',
      DESPACHAR_INSUMOS_PLANTA: '/almacen/inventario',
      ASIGNAR_CENTRO_TRABAJO: '/produccion',
      MARCAR_OP_TERMINADA: '/produccion',
      REGISTRAR_INSPECCION_METROLOGICA: '/calidad/producto',
      SUBIR_EVIDENCIA_FOTOGRAFICA: '/calidad/producto'
    };
    const ruta = rutasPorAccion[accion];
    if (ruta) {
      setCodigoOpConsultada('');
      navigate(ruta);
    }
  }, [navigate]);

  useEffect(() => {
    const manejarEventoExpediente = (evento) => manejarAccionExpediente(evento.detail?.accion);
    window.addEventListener('sgi:expediente-action', manejarEventoExpediente);
    return () => window.removeEventListener('sgi:expediente-action', manejarEventoExpediente);
  }, [manejarAccionExpediente]);

  useEffect(() => {
    const abrirExpedienteOp = (evento) => {
      const codigo = evento.detail?.codigoOp;
      if (typeof codigo === 'string' && codigo.trim()) {
        setCodigoOpConsultada(codigo.trim());
      }
    };
    window.addEventListener('sgi:abrir-expediente-op', abrirExpedienteOp);
    return () => window.removeEventListener('sgi:abrir-expediente-op', abrirExpedienteOp);
  }, []);

  return (
    <ProyectosProvider>
      <div className="flex min-h-screen bg-slate-100 font-sans text-slate-900">
        <SidebarNavigation />
        <main className="flex-1 p-6 overflow-y-auto">
          {/* pl-14: deja libre la esquina del botón flotante de menú (SidebarNavigation, fixed top-4 left-4) */}
          <div className="mb-5 flex flex-wrap items-center justify-end gap-2 rounded-lg border border-slate-200 bg-white p-3 pl-14 shadow-sm">
            <UsuarioConectado className="mr-auto self-center" />
            {alcance.tipos?.length > 0 && (
              <BusquedaGeneral alcance={alcance} onAbrirOp={setCodigoOpConsultada} />
            )}
          </div>
          <Outlet />
        </main>
        <ExpedienteOpModal
          abierto={puedeVerExpediente && Boolean(codigoOpConsultada)}
          codigoOp={codigoOpConsultada}
          onClose={() => setCodigoOpConsultada('')}
          onAction={manejarAccionExpediente}
        />
      </div>
    </ProyectosProvider>
  );
}