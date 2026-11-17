// src/components/MapaOp.jsx
// Mapa de la OP (GET /mapa-op/{op}). El backend decide, con el rol de la base, qué mapas ve el usuario
// (relaciones y/o procesos), cuál abre por defecto y qué nodos y datos trae cada uno: aquí solo se
// dibuja lo que llega. Si el rol tiene más de un mapa, se cambia entre ellos en el mismo panel.
import React, { useEffect, useState } from 'react';
import API, { mensajeError } from '../services/api';

const NOMBRE_MAPA = { relaciones: 'Relaciones', procesos: 'Procesos' };
const GRUPOS = [
  { tipo: 'PEDIDO', titulo: 'Pedido' },
  { tipo: 'COTIZACION', titulo: 'Cotización' },
  { tipo: 'CLIENTE', titulo: 'Cliente' },
  { tipo: 'OP_PEDIDO', titulo: 'Otras OP del pedido' },
  { tipo: 'PLANO', titulo: 'Planos' },
  { tipo: 'ENTREGA_MATERIAL', titulo: 'Entregas de material a la OP' },
  { tipo: 'INGRESO_PT', titulo: 'Ingreso a stock PT' }
];
const ETIQUETAS_DATO = {
  estado: 'Estado',
  fecha_compromiso: 'Compromiso',
  fecha_emision: 'Emisión',
  valor_cotizado: 'Valor cotizado',
  unidad_actual: 'Unidad',
  porcentaje_avance: 'Avance %',
  revision: 'Revisión',
  numero_colada: 'Colada',
  cantidad: 'Cantidad',
  fecha: 'Fecha',
  producto: 'Producto'
};

function texto(clave, valor, datos) {
  if (valor === null || valor === undefined || valor === '') return '—';
  if (clave === 'valor_cotizado') {
    return Number(valor).toLocaleString('es-CO', { style: 'currency', currency: datos.moneda || 'COP', maximumFractionDigits: 0 });
  }
  if (clave.startsWith('fecha')) {
    const fecha = new Date(valor);
    return Number.isNaN(fecha.getTime()) ? valor : fecha.toLocaleDateString('es-CO');
  }
  return String(valor).replaceAll('_', ' ');
}

function TarjetaNodo({ nodo }) {
  const datos = Object.entries(nodo.datos || {}).filter(([clave]) => ETIQUETAS_DATO[clave]);
  return (
    <div className="rounded border border-slate-300 bg-white p-2 shadow-sm">
      <p className="font-mono font-bold text-slate-900">{nodo.etiqueta || '—'}</p>
      {datos.map(([clave, valor]) => (
        <p key={clave} className="text-slate-600">{ETIQUETAS_DATO[clave]}: {texto(clave, valor, nodo.datos)}</p>
      ))}
    </div>
  );
}

function MapaRelaciones({ mapa }) {
  const centro = mapa.nodos.find((nodo) => nodo.tipo === 'OP');
  const grupos = GRUPOS
    .map((grupo) => ({ ...grupo, nodos: mapa.nodos.filter((nodo) => nodo.tipo === grupo.tipo) }))
    .filter((grupo) => grupo.nodos.length);
  return (
    <div className="space-y-3">
      <div className="mx-auto max-w-xs rounded-lg border-2 border-blue-700 bg-blue-50 p-3 text-center">
        <p className="text-[10px] font-bold uppercase text-blue-800">Orden de producción</p>
        <p className="font-mono text-base font-extrabold text-slate-900">{centro?.etiqueta}</p>
        <p className="text-slate-600">{texto('estado', centro?.datos?.estado, {})}</p>
      </div>
      {grupos.length ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {grupos.map((grupo) => (
            <section key={grupo.tipo} className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
              <h4 className="font-bold text-slate-700">{grupo.titulo}</h4>
              {grupo.nodos.map((nodo) => <TarjetaNodo key={nodo.id} nodo={nodo} />)}
            </section>
          ))}
        </div>
      ) : (
        <p className="text-center text-slate-500">No hay relaciones que su rol pueda ver.</p>
      )}
    </div>
  );
}

function MapaProcesos({ mapa }) {
  if (!mapa.nodos.length) return <p className="text-center text-slate-500">La OP no tiene operaciones en su ruta.</p>;
  return (
    <ol className="flex flex-wrap items-stretch gap-2">
      {mapa.nodos.map((nodo, indice) => (
        <li key={nodo.id} className="flex items-center gap-2">
          <div className="w-52 rounded border border-slate-300 bg-white p-2 shadow-sm">
            <p className="text-[10px] font-bold text-slate-500">Paso {nodo.datos.secuencia}</p>
            <p className="font-bold text-slate-900">{nodo.etiqueta}</p>
            <p className="text-slate-600">Estado: {texto('estado', nodo.datos.estado, {})}</p>
            <p className="text-slate-600">Máquina: {nodo.datos.maquinas.join(', ') || '—'}</p>
            <p className="text-slate-600">Operario: {nodo.datos.operarios.join(', ') || '—'}</p>
            {mapa.con_tiempos && (
              <p className="mt-1 font-mono text-slate-800">
                {nodo.datos.minutos_operacion} min operación · {nodo.datos.minutos_setup} min setup
              </p>
            )}
          </div>
          {indice < mapa.nodos.length - 1 && <span aria-hidden="true" className="text-lg text-slate-400">→</span>}
        </li>
      ))}
    </ol>
  );
}

export default function MapaOp({ codigoOp }) {
  const [datos, setDatos] = useState(null);
  const [vista, setVista] = useState('');
  const [error, setError] = useState('');
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let activo = true;
    setCargando(true);
    setError('');
    setDatos(null);
    API.get(`/mapa-op/${encodeURIComponent(codigoOp)}`)
      .then((respuesta) => {
        if (!activo) return;
        setDatos(respuesta.data);
        setVista(respuesta.data.por_defecto);
      })
      .catch((fallo) => {
        if (!activo) return;
        setError(fallo.response?.status === 403
          ? 'Su rol no ve el mapa de la OP.'
          : mensajeError(fallo, 'No fue posible cargar el mapa de la OP.'));
      })
      .finally(() => {
        if (activo) setCargando(false);
      });
    return () => {
      activo = false;
    };
  }, [codigoOp]);

  if (cargando) return <p className="rounded bg-white p-4 text-center font-semibold text-slate-600">Cargando mapa…</p>;
  if (error) return <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 font-semibold text-red-800">{error}</p>;

  return (
    <div className="space-y-3">
      {datos.mapas.length > 1 && (
        <div role="tablist" aria-label="Mapa de la OP" className="flex gap-1">
          {datos.mapas.map((mapa) => (
            <button
              key={mapa}
              type="button"
              role="tab"
              aria-selected={vista === mapa}
              onClick={() => setVista(mapa)}
              className={`rounded border px-3 py-1 font-semibold ${vista === mapa ? 'border-blue-700 bg-blue-700 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'}`}
            >
              {NOMBRE_MAPA[mapa] || mapa}
            </button>
          ))}
        </div>
      )}
      {vista === 'relaciones' && datos.relaciones && <MapaRelaciones mapa={datos.relaciones} />}
      {vista === 'procesos' && datos.procesos && <MapaProcesos mapa={datos.procesos} />}
    </div>
  );
}
