// src/components/DevolverInspeccion.jsx
// Devolver a inspección (POST /ordenes/{op}/devolver-a-inspeccion), solo JEFE_PRODUCCION. El servidor
// valida todo: rol de la base, OP lista para liberar sin piezas aprobadas (nunca cerrada) y motivo
// de al menos 15 caracteres; aquí solo se envía y se muestra su respuesta.
import React, { useState } from 'react';
import API, { mensajeError } from '../services/api';

export default function DevolverInspeccion({ codigoOp, onDevuelta }) {
  const [motivo, setMotivo] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');

  const devolver = async (evento) => {
    evento.preventDefault();
    setError('');
    setAviso('');
    setEnviando(true);
    try {
      await API.post(`/ordenes/${encodeURIComponent(codigoOp)}/devolver-a-inspeccion`, { motivo });
      setAviso('La OP volvió a inspección de calidad. Calidad registrará la cantidad aprobada.');
      setMotivo('');
      if (onDevuelta) onDevuelta();
    } catch (fallo) {
      setError(mensajeError(fallo, 'No se pudo devolver la OP a inspección.'));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={devolver} className="space-y-2 rounded border border-slate-300 bg-white p-3">
      <p className="text-slate-600">
        Para OP que Calidad dejó en "lista para liberar" sin registrar cuántas piezas aprobó. Vuelve a inspección de calidad.
      </p>
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
        {enviando ? 'Enviando…' : 'Devolver a inspección'}
      </button>
    </form>
  );
}
