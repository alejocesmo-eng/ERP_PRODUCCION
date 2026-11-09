import React from 'react';

// Línea de tiempo append-only de un plano (GET /planos/{id}/historial o planos[].historial
// del expediente de la OP), en orden cronológico.
const EVENTOS = {
  CREACION: { etiqueta: 'Creación', estilo: 'bg-slate-600' },
  CAMBIO_VERSION: { etiqueta: 'Cambio de versión', estilo: 'bg-purple-600' },
  CARGA_ARCHIVO: { etiqueta: 'Carga de archivo', estilo: 'bg-blue-600' },
  CAMBIO_ARCHIVO: { etiqueta: 'Cambio de archivo', estilo: 'bg-amber-600' },
  REVISION: { etiqueta: 'Revisión', estilo: 'bg-orange-600' },
  CAMBIO_ESTADO: { etiqueta: 'Cambio de estado', estilo: 'bg-teal-600' },
  APROBACION: { etiqueta: 'Aprobación de Diseño', estilo: 'bg-emerald-600' }
};

function formatearFecha(valor) {
  if (!valor) return '—';
  const fecha = new Date(valor);
  return Number.isNaN(fecha.getTime()) ? valor : fecha.toLocaleString('es-CO');
}

export default function LineaTiempoPlano({ eventos = [], cargando = false, error = '' }) {
  if (cargando) {
    return <p className="rounded bg-slate-50 p-3 text-center text-[11px] font-semibold text-slate-500">Cargando historial del plano…</p>;
  }
  if (error) {
    return <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-[11px] font-semibold text-red-800">{error}</p>;
  }
  if (!eventos.length) {
    return <p className="rounded bg-slate-50 p-3 text-center text-[11px] text-slate-500">El plano aún no tiene eventos registrados en el historial.</p>;
  }
  return (
    <ol className="relative space-y-2 border-l-2 border-slate-200 pl-4 text-[11px]">
      {eventos.map((evento) => {
        const tipo = EVENTOS[evento.tipo_evento] || { etiqueta: evento.tipo_evento, estilo: 'bg-slate-500' };
        return (
          <li key={evento.id_evento} className="relative">
            <span className={`absolute -left-[1.4rem] top-1 h-3 w-3 rounded-full border-2 border-white ${tipo.estilo}`} aria-hidden="true" />
            <div className="rounded border border-slate-200 bg-slate-50 p-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className={`rounded px-2 py-0.5 text-[10px] font-extrabold text-white ${tipo.estilo}`}>{tipo.etiqueta}</span>
                <span className="font-mono text-[10px] text-slate-500">{formatearFecha(evento.fecha)}</span>
              </div>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-slate-700">
                <span>
                  Versión: <strong className="font-mono">
                    {evento.version_anterior ? `${evento.version_anterior} → ${evento.version || '—'}` : evento.version || '—'}
                  </strong>
                </span>
                <span>Estado: <strong>{(evento.estado || '—').replaceAll('_', ' ')}</strong></span>
                <span>Usuario: <strong>{evento.usuario}</strong></span>
                {evento.tipo_archivo && (
                  <span>
                    Archivo: <strong>{evento.tipo_archivo}</strong>
                    {evento.sha256 && (
                      <span title={`sha256: ${evento.sha256}`} className="ml-1 font-mono text-slate-500">
                        sha256 {evento.sha256.slice(0, 12)}…
                      </span>
                    )}
                  </span>
                )}
              </div>
              {evento.justificacion && (
                <p className="mt-1 border-t border-slate-200 pt-1 text-slate-800">
                  <span className="font-semibold text-slate-500">Justificación: </span>{evento.justificacion}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
