// src/componentes/TarjetaProgresoProyecto.jsx
import React from 'react';

export function TarjetaProgresoProyecto({ proyecto }) {
  if (!proyecto) return null;

  const totalSolicitado = proyecto.total_solicitado ?? proyecto.cantidad ?? 0;
  const totalAsignado = proyecto.total_asignado ?? 0;
  const coberturaPct = proyecto.cobertura_pct || (totalSolicitado > 0 ? Math.round((totalAsignado / totalSolicitado) * 100) : 0);

  return (
    <div className="p-3 bg-white border border-slate-200 rounded-lg shadow-sm space-y-2 text-xs">
      <div className="flex justify-between items-center">
        <span className="font-mono font-bold text-purple-700">📋 {proyecto.numero_pedido}</span>
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
          proyecto.confirmado ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
        }`}>
          {proyecto.confirmado ? 'CONFIRMADO' : 'POR CONFIRMAR'}
        </span>
      </div>

      <div className="font-bold text-slate-800 truncate">{proyecto.cliente_nombre}</div>

      <div className="space-y-1">
        <div className="flex justify-between text-[11px] font-semibold text-slate-600">
          <span>Cobertura OTs / Piezas:</span>
          <span>{totalAsignado} / {totalSolicitado} ({coberturaPct}%)</span>
        </div>
        <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
          <div
            className="bg-emerald-500 h-1.5 rounded-full transition-all duration-300"
            style={{ width: `${coberturaPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}