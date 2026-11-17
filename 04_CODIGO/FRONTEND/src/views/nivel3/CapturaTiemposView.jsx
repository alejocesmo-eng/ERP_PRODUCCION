// src/views/nivel3/CapturaTiemposView.jsx
// Captura de tiempos (rol CAPTURISTA_TIEMPOS). Lista las OP abiertas con su código, pedido y
// producto (GET /tiempos-manuales/ops: sin costos, cliente ni planos) y, al elegir una, abre la
// misma parrilla de carga del expediente de OP (CargaTiemposOp). El backend exige
// PERM_TIEMPOS_REGISTRAR en la base en cada petición y responde 403 a los demás roles.
import React, { useEffect, useMemo, useState } from 'react';
import API, { mensajeError } from '../../services/api';
import CargaTiemposOp from '../../components/CargaTiemposOp';

export default function CapturaTiemposView() {
  const [ops, setOps] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [denegado, setDenegado] = useState(false);
  const [filtro, setFiltro] = useState('');
  const [seleccionada, setSeleccionada] = useState('');

  useEffect(() => {
    let activo = true;
    API.get('/tiempos-manuales/ops')
      .then((respuesta) => {
        if (activo) setOps(Array.isArray(respuesta.data) ? respuesta.data : []);
      })
      .catch((fallo) => {
        if (!activo) return;
        if (fallo.response?.status === 403) setDenegado(true);
        else setError(mensajeError(fallo, 'No fue posible cargar las OP abiertas.'));
      })
      .finally(() => {
        if (activo) setCargando(false);
      });
    return () => {
      activo = false;
    };
  }, []);

  const visibles = useMemo(() => {
    const texto = filtro.trim().toLowerCase();
    if (!texto) return ops;
    return ops.filter((op) => [op.codigo_op, op.numero_pedido, op.codigo_producto, op.producto]
      .some((valor) => String(valor || '').toLowerCase().includes(texto)));
  }, [ops, filtro]);

  if (denegado) {
    return (
      <div role="alert" className="mx-auto mt-6 max-w-lg rounded-xl border border-red-200 bg-white p-6 text-center text-xs shadow-sm">
        <p className="text-2xl font-extrabold text-red-700">403</p>
        <p className="mt-1 font-bold text-slate-900">Acceso denegado</p>
        <p className="mt-1 text-slate-500">Su rol no carga tiempos de OP.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 text-xs text-slate-800">
      <header className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h1 className="text-xl font-extrabold text-slate-900">Captura de tiempos</h1>
        <p className="mt-1 text-slate-500">Elija una OP abierta para cargar o corregir sus tiempos.</p>
      </header>

      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 font-semibold text-red-800">{error}</p>}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <section className="space-y-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <label className="block font-bold text-slate-600">
            Buscar OP, pedido o producto
            <input value={filtro} onChange={(e) => setFiltro(e.target.value)} className="mt-1 w-full rounded border border-slate-300 px-2 py-1 font-normal" />
          </label>
          {cargando && <p className="text-slate-500">Cargando OP abiertas…</p>}
          <ul className="max-h-[70vh] divide-y divide-slate-100 overflow-y-auto">
            {visibles.map((op) => (
              <li key={op.codigo_op}>
                <button
                  type="button"
                  onClick={() => setSeleccionada(op.codigo_op)}
                  aria-pressed={seleccionada === op.codigo_op}
                  className={`w-full px-2 py-2 text-left hover:bg-slate-50 ${seleccionada === op.codigo_op ? 'bg-emerald-50' : ''}`}
                >
                  <span className="block font-mono font-bold text-slate-900">{op.codigo_op}</span>
                  <span className="block text-slate-500">Pedido {op.numero_pedido || '—'}</span>
                  <span className="block text-slate-600">{[op.codigo_producto, op.producto].filter(Boolean).join(' · ') || 'Sin producto'}</span>
                </button>
              </li>
            ))}
            {!cargando && !visibles.length && <li className="py-4 text-center text-slate-500">No hay OP abiertas.</li>}
          </ul>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          {seleccionada ? (
            <>
              <h2 className="mb-2 font-mono text-sm font-extrabold text-slate-900">{seleccionada}</h2>
              <CargaTiemposOp codigoOp={seleccionada} />
            </>
          ) : (
            <p className="py-8 text-center text-slate-500">Elija una OP de la lista.</p>
          )}
        </section>
      </div>
    </div>
  );
}
