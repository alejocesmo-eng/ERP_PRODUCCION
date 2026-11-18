// src/components/ReabrirOp.jsx
// Reabrir una OP cerrada (POST /ordenes/{op}/reabrir), solo JEFE_PRODUCCION, con motivo de al menos
// 15 caracteres y nunca si el pedido ya está cerrado. El servidor valida todo; aquí solo se envía.
import React, { useState } from 'react';
import API, { mensajeError } from '../services/api';

export default function ReabrirOp({ codigoOp, onReabierta }) {
  const [motivo, setMotivo] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');

  const reabrir = async (evento) => {
    evento.preventDefault();
    setError('');
    setAviso('');
    setEnviando(true);
    try {
      await API.post(`/ordenes/${encodeURIComponent(codigoOp)}/reabrir`, { motivo });
      setAviso('La OP se reabrió y quedó terminada.');
      setMotivo('');
      if (onReabierta) onReabierta();
    } catch (fallo) {
      setError(mensajeError(fallo, 'No se pudo reabrir la OP.'));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={reabrir} className="space-y-2 rounded border border-slate-300 bg-white p-3">
      <p className="text-slate-600">Solo para una OP cerrada cuyo pedido sigue abierto. Queda en el historial con el motivo.</p>
      <label className="block font-semibold text-slate-700">
        Motivo
        <textarea
          rows="3"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          className="mt-1 w-full rounded border border-slate-300 px-2 py-1 font-normal"
        />
      </label>
      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 font-semibold text-red-800">{error}</p>}
      {aviso && <p role="status" className="rounded border border-emerald-200 bg-emerald-50 p-2 font-semibold text-emerald-800">{aviso}</p>}
      <button type="submit" disabled={enviando} className="rounded bg-blue-700 px-3 py-1 font-bold text-white hover:bg-blue-800 disabled:opacity-50">
        {enviando ? 'Enviando…' : 'Reabrir OP'}
      </button>
    </form>
  );
}
