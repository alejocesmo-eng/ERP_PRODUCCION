// src/components/CerrarPedido.jsx
// Cierre manual del pedido (POST /proyectos/{id}/cerrar), solo JEFE_PRODUCCION, cuando todas sus OP
// están cerradas (Regla 6). Se confirma escribiendo el número del pedido. El servidor valida rol,
// OP pendientes y confirmación; aquí solo se envía y se muestra su respuesta.
import React, { useState } from 'react';
import API, { mensajeError } from '../services/api';

export default function CerrarPedido({ idProyecto, numeroPedido, pendientes = [], onCerrado }) {
  const [confirmacion, setConfirmacion] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');

  const cerrar = async (evento) => {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await API.post(`/proyectos/${encodeURIComponent(idProyecto)}/cerrar`, { confirmacion });
      setAviso(`El pedido ${numeroPedido} quedó cerrado: es histórico y no se edita.`);
      if (onCerrado) onCerrado();
    } catch (fallo) {
      setError(mensajeError(fallo, 'No se pudo cerrar el pedido.'));
    } finally {
      setEnviando(false);
    }
  };

  if (aviso) {
    return <p role="status" className="rounded border border-emerald-200 bg-emerald-50 p-2 font-semibold text-emerald-800">{aviso}</p>;
  }

  return (
    <form onSubmit={cerrar} className="space-y-2 rounded border border-slate-300 bg-white p-3">
      <h4 className="font-bold text-slate-800">Cerrar pedido {numeroPedido}</h4>
      {pendientes.length > 0 ? (
        <ul className="list-disc pl-5 text-amber-800">
          {pendientes.map((pendiente) => <li key={pendiente}>{pendiente}</li>)}
        </ul>
      ) : (
        <>
          <p className="text-slate-600">Todas las OP están cerradas. El pedido quedará CERRADO, como histórico y sin edición.</p>
          <label className="block font-semibold text-slate-700">
            Escriba el número del pedido para confirmar
            <input
              value={confirmacion}
              onChange={(e) => setConfirmacion(e.target.value)}
              placeholder={numeroPedido}
              autoComplete="off"
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1 font-mono font-normal"
            />
          </label>
        </>
      )}
      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 font-semibold text-red-800">{error}</p>}
      {pendientes.length === 0 && (
        <button
          type="submit"
          disabled={enviando || confirmacion.trim() !== numeroPedido}
          className="rounded bg-slate-800 px-3 py-1 font-bold text-white hover:bg-slate-900 disabled:opacity-50"
        >
          {enviando ? 'Cerrando…' : 'Cerrar pedido'}
        </button>
      )}
    </form>
  );
}
