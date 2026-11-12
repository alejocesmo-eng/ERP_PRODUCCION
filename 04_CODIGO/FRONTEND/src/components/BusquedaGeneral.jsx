// src/components/BusquedaGeneral.jsx
// Búsqueda general por código o nombre (GET /busqueda/). El backend decide con el rol guardado en
// la base qué tipos de dato encuentra cada rol (reglas/permisos-por-rol-modulo.md): los que no
// puede ver no aparecen. Una OP abre su expediente si el rol tiene acceso; las relaciones entre
// resultados (OP -> pedido -> cotización) quedan para una segunda etapa.
import React, { useEffect, useState } from 'react';
import API from '../services/api';

const ETIQUETA_TIPO = {
  COTIZACION: 'Cotizaciones',
  PEDIDO: 'Pedidos',
  OP: 'Órdenes de producción',
  CLIENTE: 'Clientes',
  PRODUCTO: 'Productos'
};

// Alcance del rol: { tipos, expediente_op, costos, valor_cotizado }. Sin respuesta, nada.
export function useAlcanceBusqueda() {
  const [alcance, setAlcance] = useState({ tipos: [], expediente_op: false });
  useEffect(() => {
    let activo = true;
    API.get('/busqueda/alcance')
      .then((respuesta) => { if (activo) setAlcance(respuesta.data); })
      .catch(() => { if (activo) setAlcance({ tipos: [], expediente_op: false }); });
    return () => { activo = false; };
  }, []);
  return alcance;
}

function formatoValor(valor, moneda = 'COP') {
  if (valor === null || valor === undefined) return '—';
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency: moneda, maximumFractionDigits: moneda === 'USD' ? 2 : 0 }).format(valor);
}

export default function BusquedaGeneral({ alcance, onAbrirOp }) {
  const [texto, setTexto] = useState('');
  const [resultados, setResultados] = useState(null);
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState('');

  const buscar = async (event) => {
    event.preventDefault();
    const consulta = texto.trim();
    if (consulta.length < 2) {
      setError('Escriba al menos 2 caracteres.');
      setResultados(null);
      return;
    }
    setBuscando(true);
    setError('');
    try {
      const respuesta = await API.get('/busqueda/', { params: { q: consulta } });
      setResultados(respuesta.data.resultados || []);
    } catch {
      setError('No fue posible buscar. Intente de nuevo.');
      setResultados(null);
    } finally {
      setBuscando(false);
    }
  };

  const abrirOp = (codigo) => {
    setResultados(null);
    onAbrirOp(codigo);
  };

  const grupos = (alcance.tipos || [])
    .map((tipo) => ({ tipo, filas: (resultados || []).filter((fila) => fila.tipo === tipo) }))
    .filter((grupo) => grupo.filas.length);

  return (
    <div className="relative">
      <form role="search" className="flex items-center gap-2" onSubmit={buscar}>
        <input
          type="text"
          value={texto}
          onChange={(event) => setTexto(event.target.value)}
          aria-label="Buscar en PRISMA por código o nombre"
          className="w-64 rounded border border-slate-300 px-2 py-1.5 text-xs outline-none focus:border-emerald-500"
          maxLength={100}
        />
        <button
          type="submit"
          disabled={buscando}
          className="rounded bg-emerald-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-800 disabled:opacity-60"
        >
          Buscar
        </button>
      </form>

      {(error || resultados) && (
        <div className="absolute right-0 z-40 mt-1 max-h-96 w-[28rem] overflow-y-auto rounded-lg border border-slate-200 bg-white p-2 text-xs shadow-lg">
          <div className="mb-1 flex justify-end">
            <button type="button" onClick={() => { setResultados(null); setError(''); }} className="text-slate-400 hover:text-slate-600" aria-label="Cerrar resultados">✕</button>
          </div>
          {error && <p className="p-2 text-red-700">{error}</p>}
          {resultados && !grupos.length && <p className="p-2 text-slate-600">Sin resultados.</p>}
          {grupos.map(({ tipo, filas }) => (
            <section key={tipo} className="mb-2">
              <h3 className="px-2 py-1 text-[10px] font-bold uppercase text-slate-500">{ETIQUETA_TIPO[tipo] || tipo}</h3>
              <ul>
                {filas.map((fila) => {
                  const abreExpediente = tipo === 'OP' && alcance.expediente_op;
                  const contenido = (
                    <>
                      <span className="font-mono font-bold text-slate-800">{fila.codigo}</span>
                      <span className="ml-2 text-slate-600">{fila.nombre}</span>
                      {fila.estado && <span className="ml-2 text-[10px] text-slate-400">{fila.estado}</span>}
                      {'valor_cotizado' in fila && (
                        <span className="ml-2 font-mono text-emerald-700">{formatoValor(fila.valor_cotizado, fila.moneda)}</span>
                      )}
                    </>
                  );
                  return (
                    <li key={`${tipo}-${fila.codigo}`}>
                      {abreExpediente ? (
                        <button type="button" onClick={() => abrirOp(fila.codigo)} className="w-full rounded px-2 py-1 text-left hover:bg-emerald-50">
                          {contenido}
                        </button>
                      ) : (
                        <div className="px-2 py-1">{contenido}</div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
