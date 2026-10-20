// src/components/VisorPlanoModal.jsx
import React from 'react';
import { API_ORIGIN } from '../services/api';

export default function VisorPlanoModal({ abierto, onClose, archivoUrl, codigoOp, codigoPlano }) {
  if (!abierto) return null;

  // Si la ruta es relativa, construimos la URL hacia el backend FastAPI
  const urlCompleta = archivoUrl
    ? (/^https?:\/\//i.test(archivoUrl) ? archivoUrl : `${API_ORIGIN}${archivoUrl}`)
    : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 font-sans backdrop-blur-sm">
      <div className="flex h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border-t-4 border-blue-600 bg-white shadow-2xl">
        {/* Cabecera del Visor Modal */}
        <div className="p-4 bg-slate-800 text-white flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="text-lg">📐</span>
            <h3 className="font-bold text-sm font-mono tracking-wide">
              Plano Técnico PDF | OP: <span className="text-amber-400">{codigoOp || 'S/OP'}</span> | Plano: <span className="text-blue-300">{codigoPlano || 'S/PLN'}</span>
            </h3>
          </div>
          <button 
            type="button"
            onClick={onClose} 
            aria-label="Cerrar visor de plano"
            className="cursor-pointer rounded-lg bg-slate-700 px-2 py-1 text-sm font-extrabold text-slate-200 transition hover:bg-slate-600 hover:text-white"
          >
            ✕
          </button>
        </div>

        {/* Visor Iframe de PDF / Estado Vacío */}
        <div className="flex-1 bg-slate-100 p-2 relative">
          {urlCompleta ? (
            <iframe 
              src={urlCompleta} 
              title={`Plano ${codigoPlano}`} 
              className="w-full h-full rounded border border-slate-300 shadow-inner"
            />
          ) : (
            <div className="flex flex-col justify-center items-center h-full text-slate-500 space-y-2">
              <span className="text-4xl">⚠️</span>
              <p className="font-bold text-sm">No hay un archivo PDF adjunto a este plano.</p>
              <p className="text-xs text-slate-400">Cargue el archivo PDF desde el módulo de Diseño e Ingeniería para congelar la versión [ISO 9001:2026].</p>
            </div>
          )}
        </div>

        {/* Cierre inferior */}
        <div className="p-3 bg-slate-50 border-t flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer rounded-lg bg-blue-600 px-4 py-2 text-[11px] font-extrabold text-white shadow-sm transition hover:bg-blue-700"
          >
            Cerrar Visor
          </button>
        </div>
      </div>
    </div>
  );
}