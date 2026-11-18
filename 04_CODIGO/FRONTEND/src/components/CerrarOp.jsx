// src/components/CerrarOp.jsx
// Cierre seguro de la OP (reglas/cierre-op-seguro.md): resumen de GET /ordenes/{op}/cierre (OP, pedido,
// cliente, cantidad, total de tiempos y aprobación de Calidad), número de la OP escrito para confirmar y
// motivo si cierra un líder de respaldo. POST /ordenes/{op}/cerrar valida todo de nuevo en el servidor.
// Si el Jefe cierra la última OP del pedido, ofrece cerrar el pedido (a mano, CerrarPedido).
import React, { useEffect, useState } from 'react';
import API, { mensajeError } from '../services/api';
import CerrarPedido from './CerrarPedido';

const fmtMinutos = (minutos) => `${Number(minutos || 0).toLocaleString('es-CO')} min`;

export default function CerrarOp({ codigoOp, onCerrada }) {
  const [resumen, setResumen] = useState(null);
  const [confirmacion, setConfirmacion] = useState('');
  const [motivo, setMotivo] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');
  const [cierre, setCierre] = useState(null);

  useEffect(() => {
    let vigente = true;
    setResumen(null);
    setError('');
    API.get(`/ordenes/${encodeURIComponent(codigoOp)}/cierre`)
      .then((respuesta) => { if (vigente) setResumen(respuesta.data); })
      .catch((fallo) => { if (vigente) setError(mensajeError(fallo, 'No se pudo cargar el resumen del cierre.')); });
    return () => { vigente = false; };
  }, [codigoOp]);

  const cerrar = async (evento) => {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      const { data } = await API.post(`/ordenes/${encodeURIComponent(codigoOp)}/cerrar`, { confirmacion, motivo });
      setCierre(data);
      if (onCerrada) onCerrada();
    } catch (fallo) {
      setError(mensajeError(fallo, 'No se pudo cerrar la OP.'));
    } finally {
      setEnviando(false);
    }
  };

  if (cierre) {
    return (
      <div className="space-y-2">
        <p role="status" className="rounded border border-emerald-200 bg-emerald-50 p-2 font-semibold text-emerald-800">
          La OP {cierre.codigo_op} quedó cerrada.{cierre.aviso_jefe && ' Se avisó al Jefe de Producción.'}
        </p>
        {cierre.pedido_listo_para_cerrar && (
          <CerrarPedido idProyecto={cierre.id_proyecto} numeroPedido={cierre.numero_pedido} />
        )}
      </div>
    );
  }

  if (!resumen) {
    return error
      ? <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 font-semibold text-red-800">{error}</p>
      : <p className="text-slate-500">Cargando resumen…</p>;
  }

  const motivoCorto = resumen.requiere_motivo && motivo.trim().length < resumen.longitud_minima_motivo;
  const listo = resumen.puede_cerrar && confirmacion.trim() === resumen.codigo_op && !motivoCorto;

  return (
    <form onSubmit={cerrar} className="space-y-2 rounded border border-slate-300 bg-white p-3">
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
        <dt className="text-slate-500">OP</dt><dd className="font-mono font-bold">{resumen.codigo_op}</dd>
        <dt className="text-slate-500">Pedido</dt><dd className="font-mono">{resumen.numero_pedido || '—'}</dd>
        <dt className="text-slate-500">Cliente</dt><dd>{resumen.cliente || '—'}</dd>
        <dt className="text-slate-500">Cantidad</dt><dd>{resumen.cantidad}</dd>
        <dt className="text-slate-500">Tiempos cargados</dt>
        <dd>{fmtMinutos(resumen.minutos_tiempos)} · {resumen.tiempos_completos ? 'todos los procesos' : 'incompletos'}</dd>
        <dt className="text-slate-500">Calidad de producto</dt>
        <dd className={resumen.aprobada_calidad ? 'font-semibold text-emerald-800' : 'font-semibold text-red-800'}>
          {resumen.aprobada_calidad ? 'Aprobada' : 'Sin aprobar'} ({resumen.piezas_aprobadas} de {resumen.cantidad})
        </dd>
      </dl>

      {resumen.faltantes.length > 0 ? (
        <ul role="alert" className="list-disc rounded border border-amber-200 bg-amber-50 py-2 pl-6 pr-2 text-amber-900">
          {resumen.faltantes.map((faltante) => <li key={faltante}>{faltante}</li>)}
        </ul>
      ) : (
        <>
          <label className="block font-semibold text-slate-700">
            Escriba el número de la OP para confirmar
            <input
              value={confirmacion}
              onChange={(e) => setConfirmacion(e.target.value)}
              placeholder={resumen.codigo_op}
              autoComplete="off"
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1 font-mono font-normal"
            />
          </label>
          {resumen.requiere_motivo && (
            <label className="block font-semibold text-slate-700">
              Motivo (cierra como respaldo del Jefe de Producción; mínimo {resumen.longitud_minima_motivo} caracteres)
              <textarea
                rows="3"
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1 font-normal"
              />
            </label>
          )}
        </>
      )}
      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 font-semibold text-red-800">{error}</p>}
      {resumen.puede_cerrar && (
        <button type="submit" disabled={enviando || !listo} className="rounded bg-slate-800 px-3 py-1 font-bold text-white hover:bg-slate-900 disabled:opacity-50">
          {enviando ? 'Cerrando…' : 'Cerrar OP'}
        </button>
      )}
    </form>
  );
}
