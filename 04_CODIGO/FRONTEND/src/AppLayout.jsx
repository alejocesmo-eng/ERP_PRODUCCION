// src/AppLayout.jsx
import React, { useCallback, useEffect, useState } from 'react';
import SidebarNavigation from './components/SidebarNavigation';
import { Outlet, useNavigate } from 'react-router-dom';
import { ProyectosProvider } from './context/ProyectosContext';
import ExpedienteOpModal from './components/modals/ExpedienteOpModal';

export default function AppLayout() {
  const navigate = useNavigate();
  const [codigoOp, setCodigoOp] = useState('');
  const [codigoOpConsultada, setCodigoOpConsultada] = useState('');

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
          <div className="mb-5 flex flex-wrap items-end justify-end gap-2 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
            <form
              className="flex flex-wrap items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (codigoOp.trim()) setCodigoOpConsultada(codigoOp.trim());
              }}
            >
              <label className="text-[11px] font-bold text-slate-600">
                Consultar expediente de OP
                <input
                  value={codigoOp}
                  onChange={(event) => setCodigoOp(event.target.value)}
                  placeholder="Código de OP"
                  className="ml-2 rounded border border-slate-300 px-2 py-1.5 font-mono text-xs outline-none focus:border-emerald-500"
                  maxLength={50}
                  required
                />
              </label>
              <button type="submit" className="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-800">
                Abrir expediente
              </button>
            </form>
          </div>
          <Outlet />
        </main>
        <ExpedienteOpModal
          abierto={Boolean(codigoOpConsultada)}
          codigoOp={codigoOpConsultada}
          onClose={() => setCodigoOpConsultada('')}
          onAction={manejarAccionExpediente}
        />
      </div>
    </ProyectosProvider>
  );
}