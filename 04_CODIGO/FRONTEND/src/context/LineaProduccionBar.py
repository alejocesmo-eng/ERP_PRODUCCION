// src/components/LineaProduccionBar.jsx
import React from 'react';

export default function LineaProduccionBar({ proyecto }) {
  if (!proyecto || !proyecto.linea_produccion) return null;

  const linea = proyecto.linea_produccion;
  const pctGlobal = proyecto.porcentaje_avance_global || 0;

  const COLOR_AREA = {
    Ventas: 'bg-purple-600 text-white',
    Diseño: 'bg-blue-600 text-white',
    Producción: 'bg-amber-600 text-white',
  };

  return (
    <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3 mb-4">
      <div className="flex justify-between items-center border-b pb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Línea de Producción Transversal (8 Etapas SGI)
          </span>
          <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-extrabold rounded font-mono">
            {proyecto.numero_pedido}
          </span>
        </div>
        <div className="text-xs font-extrabold text-emerald-700">
          Avance Global: {pctGlobal}%
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-1.5 pt-1">
        {linea.map((item) => {
          const esCompletado = item.completado;
          const esActivo = item.estado_actual === 'EN_PROGRESO';

          return (
            <div
              key={item.paso}
              className={`p-2 rounded-lg border text-center transition-all ${
                esCompletado
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                  : esActivo
                  ? 'bg-blue-50 border-blue-500 ring-2 ring-blue-300 text-blue-900 font-bold'
                  : 'bg-slate-50 border-slate-200 text-slate-400'
              }`}
            >
              <div className="flex items-center justify-between text-[9px] font-extrabold mb-1">
                <span>Paso {item.paso}</span>
                <span className={`px-1 py-0.2 rounded text-[8px] ${COLOR_AREA[item.area] || 'bg-slate-500 text-white'}`}>
                  {item.area}
                </span>
              </div>
              <p className="text-[10px] font-bold leading-tight line-clamp-2">
                {item.actividad}
              </p>
              <div className="mt-1.5 text-[10px]">
                {esCompletado ? '✅ Listo' : esActivo ? '⏳ En proceso' : '⚪ Pendiente'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}