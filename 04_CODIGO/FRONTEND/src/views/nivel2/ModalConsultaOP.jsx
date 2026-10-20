import React from 'react';

export default function ModalConsultaOP({ detalleOPSeleccionada, onClose }) {
  if (!detalleOPSeleccionada) return null;

  const { orden, planos } = detalleOPSeleccionada;

  return (
    <div className="fixed inset-0 bg-slate-900 bg-opacity-70 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-4xl w-full p-6 shadow-2xl border border-slate-300 max-h-[90vh] overflow-y-auto">
        <div className="border-b border-slate-200 pb-3 mb-4 flex justify-between items-start">
          <div>
            <span className="px-2 py-0.5 bg-blue-800 text-white font-bold rounded text-[10px] uppercase mb-1 inline-block">
              🔍 Consulta de Trazabilidad SGI [ISO 9001:2026]
            </span>
            <h3 className="text-xl font-extrabold text-slate-900">
              Expediente de la Orden de Producción: <span className="text-blue-700">{orden.codigo_proyecto}</span>
            </h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-2xl font-bold">
            ✕
          </button>
        </div>

        {/* DATOS COMERCIALES */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs mb-4">
          <div className="p-3 bg-slate-50 border border-slate-200 rounded">
            <span className="font-bold text-slate-800 block mb-1 text-xs">🏢 Cliente & Ubicación</span>
            <p><strong>Razón Social:</strong> {orden.cliente_nombre}</p>
            <p><strong>Sede / Ubicación:</strong> 📍 {orden.ubicacion_cliente || 'Planta Principal'}</p>
            <p><strong>Contacto:</strong> {orden.contacto_nombre || '-'} ({orden.contacto_telefono || '-'})</p>
          </div>

          <div className="p-3 bg-slate-50 border border-slate-200 rounded">
            <span className="font-bold text-slate-800 block mb-1 text-xs">📋 Pedido & Producto</span>
            <p><strong>N° Pedido Agrupador:</strong> {orden.numero_pedido || 'S/P'}</p>
            <p><strong>Detalle Producto:</strong> {orden.detalle_producto || 'Pieza mecanizada'}</p>
            <p><strong>Cantidad Programada:</strong> {orden.cantidad || 1} UND</p>
          </div>
        </div>

        {/* PLANTA Y DIBUJANTE */}
        <div className="p-3 bg-blue-50/50 border border-blue-200 rounded text-xs mb-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <span className="text-slate-500 block text-[10px] uppercase font-bold">Dibujante Encargado</span>
            <strong className="text-slate-800 text-sm">👤 {planos[0]?.dibujante_asignado || 'Carlos Ruiz'}</strong>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px] uppercase font-bold">Unidad de Planta</span>
            <strong className="text-blue-800 text-sm">🏭 {planos[0]?.unidad_planta || 'Mecanizados'}</strong>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px] uppercase font-bold">Estado de Diseño</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-emerald-100 text-emerald-900 border border-emerald-300 inline-block mt-1">
              {planos[0]?.estado_diseno || 'ABIERTA'}
            </span>
          </div>
        </div>

        {/* TABLA DE PLANOS Y BOM */}
        <h4 className="text-xs font-bold text-slate-800 uppercase mb-2">📐 Documentación Técnica y Lista de Materiales (BOM)</h4>
        <div className="overflow-x-auto mb-4 border border-slate-200 rounded">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-100 text-slate-700 font-semibold uppercase border-b border-slate-200">
              <tr>
                <th className="p-2">Código Plano</th>
                <th className="p-2">Materia Prima (BOM)</th>
                <th className="p-2">Insumos Opcionales</th>
                <th className="p-2">Estado Materiales</th>
                <th className="p-2">Límite Producción</th>
                <th className="p-2">Digital</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {planos.length === 0 ? (
                <tr>
                  <td colSpan="6" className="p-3 text-center text-slate-400">Sin planos asignados actualmente.</td>
                </tr>
              ) : (
                planos.map(pl => (
                  <tr key={pl.id_plano || pl.id}>
                    <td className="p-2 font-bold text-slate-800">{pl.codigo_plano} ({pl.revision})</td>
                    <td className="p-2 font-semibold text-slate-700">{pl.material_requerido || '-'}</td>
                    <td className="p-2 text-slate-500">{pl.insumos_opcionales || '-'}</td>
                    <td className="p-2">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200">
                        🛒 En Almacén / Reservado
                      </span>
                    </td>
                    <td className="p-2 font-bold text-blue-900">⚙ {pl.fecha_entrega_produccion || '-'}</td>
                    <td className="p-2">
                      {pl.archivo_url ? (
                        <a href={pl.archivo_url} target="_blank" rel="noreferrer" className="text-blue-600 font-bold underline">
                          📄 Abrir PDF
                        </a>
                      ) : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-5 flex justify-end">
          <button 
            onClick={onClose} 
            className="px-5 py-2 bg-slate-800 hover:bg-slate-900 text-white text-xs font-bold rounded transition shadow"
          >
            Cerrar Consulta de OP
          </button>
        </div>
      </div>
    </div>
  );
}