import React, { useMemo, useState } from 'react';

const FORMATO_MONEDA = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
});

const CATEGORIAS = {
  materiales: {
    etiqueta: 'Materia prima directa',
    color: '#059669',
    fondo: '#ecfdf5',
    borde: '#a7f3d0',
  },
  tiempos: {
    etiqueta: 'Horas MES',
    color: '#2563eb',
    fondo: '#eff6ff',
    borde: '#bfdbfe',
  },
  servicios: {
    etiqueta: 'Servicios externos',
    color: '#9333ea',
    fondo: '#faf5ff',
    borde: '#e9d5ff',
  },
};

const ETIQUETAS_TIEMPO = {
  SETUP: 'Preparación de máquina',
  MECANIZADO: 'Mecanizado',
  PRODUCCION: 'Producción',
};

function obtenerNodos(datos) {
  const materialesPorCodigo = new Map();
  (datos.detalle_materiales || []).forEach((item) => {
    const codigo = item.codigo_material || 'MATERIAL-SIN-CODIGO';
    const material = materialesPorCodigo.get(codigo) || {
      codigo,
      costo: 0,
      cantidad: 0,
      unidad: item.unidad_medida || '',
      presupuesto: item.presupuesto,
      lotes: [],
    };
    material.costo += Number(item.costo_total || 0);
    material.cantidad += Number(item.cantidad || 0);
    if (material.unidad !== (item.unidad_medida || '')) material.unidad = '';
    if (item.lote_codigo || item.numero_colada) {
      material.lotes.push({
        lote: item.lote_codigo || 'Lote sin código',
        colada: item.numero_colada,
        costo: Number(item.costo_total || 0),
      });
    }
    materialesPorCodigo.set(codigo, material);
  });

  return [
    ...Array.from(materialesPorCodigo.values()).map((item) => ({
      id: `material-${item.codigo}`,
      categoria: 'materiales',
      titulo: item.codigo,
      detalle: item.lotes.length
        ? `${item.lotes.length} lote(s) consumido(s)`
        : 'Consumo registrado sin lote asociado',
      costo: item.costo,
      cantidad: `${item.cantidad} ${item.unidad}`.trim(),
      presupuesto: item.presupuesto,
      variacionPresupuestal: item.presupuesto == null
        ? null
        : item.costo - Number(item.presupuesto),
      lotes: item.lotes,
    })),
    ...(datos.detalle_tiempos || []).map((item, indice) => ({
      id: `tiempo-${indice}`,
      categoria: 'tiempos',
      titulo: item.centro_trabajo || 'Centro sin identificar',
      detalle: ETIQUETAS_TIEMPO[item.tipo] || item.tipo,
      costo: Number(item.costo_total || 0),
      cantidad: `${Number(item.horas || 0).toFixed(2)} h · ${FORMATO_MONEDA.format(Number(item.tarifa_hora || 0))}/h`,
      presupuesto: item.presupuesto,
      variacionPresupuestal: item.variacion_presupuestal,
    })),
    ...(datos.detalle_servicios_terceros || []).map((item, indice) => ({
      id: `servicio-${indice}`,
      categoria: 'servicios',
      titulo: item.proveedor || 'Proveedor sin identificar',
      detalle: `${item.descripcion || 'Servicio externo'} · Factura ${item.numero_factura || 'sin número'}`,
      costo: Number(item.costo || 0),
      cantidad: 'Servicio facturado',
      presupuesto: item.presupuesto,
      variacionPresupuestal: item.variacion_presupuestal,
    })),
  ];
}

function NodoRed({ nodo, posicion, seleccionado, alSeleccionar }) {
  const estilo = CATEGORIAS[nodo.categoria];
  const desviado = nodo.presupuesto != null
    && Number.isFinite(Number(nodo.presupuesto))
    && nodo.costo > Number(nodo.presupuesto);
  const activarConTeclado = (evento) => {
    if (evento.key === 'Enter' || evento.key === ' ') {
      evento.preventDefault();
      alSeleccionar(nodo);
    }
  };

  return (
    <g
      transform={`translate(${posicion.x}, ${posicion.y})`}
      role="button"
      tabIndex="0"
      aria-label={`${nodo.titulo}, ${FORMATO_MONEDA.format(nodo.costo)}. Seleccionar detalle`}
      aria-pressed={seleccionado}
      onClick={() => alSeleccionar(nodo)}
      onKeyDown={activarConTeclado}
      className="cursor-pointer"
    >
      <rect
        width="280"
        height="82"
        rx="10"
        fill={estilo.fondo}
        stroke={desviado ? '#dc2626' : seleccionado ? estilo.color : estilo.borde}
        strokeWidth={desviado || seleccionado ? 2.5 : 1.5}
      />
      <text x="14" y="21" fill={estilo.color} fontSize="10" fontWeight="700">
        {estilo.etiqueta.toLocaleUpperCase('es-CO')}
      </text>
      <text x="14" y="40" fill="#0f172a" fontSize="12" fontWeight="700">
        {nodo.titulo.length > 34 ? `${nodo.titulo.slice(0, 31)}…` : nodo.titulo}
      </text>
      <text x="14" y="56" fill="#475569" fontSize="10">
        {nodo.detalle.length > 43 ? `${nodo.detalle.slice(0, 40)}…` : nodo.detalle}
      </text>
      <text x="14" y="73" fill="#0f172a" fontSize="11" fontWeight="700">
        {FORMATO_MONEDA.format(nodo.costo)}
      </text>
      {desviado && (
        <g>
          <rect x="169" y="59" width="101" height="17" rx="8" fill="#fee2e2" />
          <text x="219.5" y="71" textAnchor="middle" fill="#b91c1c" fontSize="7.5" fontWeight="800">
            DESVIACIÓN DE COSTO
          </text>
        </g>
      )}
    </g>
  );
}

export default function VistaGrafoCostos({ datos }) {
  const [visibles, setVisibles] = useState({
    materiales: true,
    tiempos: true,
    servicios: true,
  });
  const [seleccionado, setSeleccionado] = useState(null);

  const nodos = useMemo(() => obtenerNodos(datos), [datos]);
  const nodosVisibles = nodos.filter((nodo) => visibles[nodo.categoria]);
  const cantidadPorCategoria = Object.keys(CATEGORIAS).reduce((resultado, categoria) => {
    resultado[categoria] = nodosVisibles.filter((nodo) => nodo.categoria === categoria).length;
    return resultado;
  }, {});
  const filas = Math.max(1, ...Object.values(cantidadPorCategoria));
  const alto = 190 + filas * 100;
  const centroX = 512;
  const posiciones = nodosVisibles.map((nodo) => {
    const indiceCategoria = nodosVisibles
      .filter((candidato) => candidato.categoria === nodo.categoria)
      .indexOf(nodo);
    const columna = { materiales: 0, tiempos: 1, servicios: 2 }[nodo.categoria];
    return {
      id: nodo.id,
      x: 18 + columna * 346,
      y: 160 + indiceCategoria * 100,
      centro: x => x + 140,
    };
  });
  const cotizacion = datos.cotizacion_comercial == null
    ? null
    : Number(datos.cotizacion_comercial);
  const costoTotal = Number(datos.costos?.real_total || 0);
  const margen = datos.margen_real_porcentaje;
  const opDesviada = cotizacion != null && Number.isFinite(cotizacion) && costoTotal > cotizacion;
  const raizBorde = opDesviada ? '#dc2626' : '#cbd5e1';

  const alternarCategoria = (categoria) => {
    setVisibles((actuales) => ({ ...actuales, [categoria]: !actuales[categoria] }));
    setSeleccionado(null);
  };

  return (
    <section className="space-y-3 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-bold text-slate-800">Red de costos de la OP {datos.codigo_op}</h2>
          <p className="mt-1 text-slate-500">Seleccione un nodo para consultar su detalle y filtre los componentes de costo.</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(CATEGORIAS).map(([categoria, config]) => (
            <button
              key={categoria}
              type="button"
              aria-pressed={visibles[categoria]}
              onClick={() => alternarCategoria(categoria)}
              className={`rounded border px-2 py-1 font-semibold ${visibles[categoria] ? 'bg-white' : 'bg-slate-100 text-slate-400'}`}
              style={{ borderColor: config.borde, color: visibles[categoria] ? config.color : undefined }}
            >
              {config.etiqueta} ({cantidadPorCategoria[categoria]})
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-auto rounded border border-slate-100 bg-slate-50">
        <svg
          viewBox={`0 0 1056 ${alto}`}
          role="img"
          aria-label={`Red de costos de la orden ${datos.codigo_op}`}
          className="min-w-[840px] w-full"
        >
          {nodosVisibles.map((nodo) => {
            const posicion = posiciones.find((item) => item.id === nodo.id);
            return (
              <path
                key={`conexion-${nodo.id}`}
                d={`M ${centroX} 117 C ${centroX} 140, ${posicion.centro(posicion.x)} 135, ${posicion.centro(posicion.x)} ${posicion.y}`}
                fill="none"
                stroke="#94a3b8"
                strokeWidth="1.5"
              />
            );
          })}
          <g>
            <rect x="397" y="24" width="230" height="94" rx="14" fill="#fff" stroke={raizBorde} strokeWidth={opDesviada ? 3 : 1.5} />
            <text x="512" y="45" textAnchor="middle" fill="#64748b" fontSize="10" fontWeight="700">ORDEN DE PRODUCCIÓN</text>
            <text x="512" y="67" textAnchor="middle" fill="#0f172a" fontSize="18" fontWeight="800">{datos.codigo_op}</text>
            <text x="512" y="86" textAnchor="middle" fill="#334155" fontSize="11">
              Margen real: {margen == null ? 'Sin cotización' : `${Number(margen).toFixed(1)}%`}
            </text>
            <text x="512" y="103" textAnchor="middle" fill="#64748b" fontSize="10">
              Estado: {String(datos.estado_op || 'No informado').replaceAll('_', ' ')}
            </text>
          </g>
          {opDesviada && (
            <g>
              <rect x="637" y="28" width="101" height="18" rx="9" fill="#fee2e2" />
              <text x="687.5" y="40" textAnchor="middle" fill="#b91c1c" fontSize="7.5" fontWeight="800">DESVIACIÓN DE COSTO</text>
            </g>
          )}
          {nodosVisibles.map((nodo) => (
            <NodoRed
              key={nodo.id}
              nodo={nodo}
              posicion={posiciones.find((item) => item.id === nodo.id)}
              seleccionado={seleccionado?.id === nodo.id}
              alSeleccionar={setSeleccionado}
            />
          ))}
        </svg>
      </div>

      {cotizacion != null && Number.isFinite(cotizacion) && (
        <p className={`rounded border px-3 py-2 ${opDesviada ? 'border-red-200 bg-red-50 text-red-800' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
          Cotización comercial de la OP: {FORMATO_MONEDA.format(cotizacion)} · Costo real acumulado: {FORMATO_MONEDA.format(costoTotal)}.
          La alerta compara el costo total de la OP con la cotización registrada en Ventas.
        </p>
      )}
      {seleccionado && (
        <aside aria-live="polite" className="rounded border border-slate-200 bg-white p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="font-bold text-slate-800">{seleccionado.titulo}</p>
              <p className="mt-1 text-slate-500">{seleccionado.detalle}</p>
            </div>
            <strong className="text-base text-slate-900">{FORMATO_MONEDA.format(seleccionado.costo)}</strong>
          </div>
          <p className="mt-1 text-slate-600">{seleccionado.cantidad}</p>
          {seleccionado.presupuesto == null && <p className="mt-1 text-amber-700">No existe presupuesto individual configurado para este concepto.</p>}
          {seleccionado.presupuesto != null && (
            <p className={`mt-1 font-semibold ${seleccionado.variacionPresupuestal > 0 ? 'text-red-700' : 'text-emerald-700'}`}>
              Presupuesto: {FORMATO_MONEDA.format(Number(seleccionado.presupuesto))}
              {' · '}Variación: {FORMATO_MONEDA.format(Number(seleccionado.variacionPresupuestal || 0))}
            </p>
          )}
          {seleccionado.lotes?.length > 0 && (
            <ul className="mt-2 space-y-1 border-t border-slate-100 pt-2 text-slate-600">
              {seleccionado.lotes.map((lote, indice) => (
                <li key={`${lote.lote}-${indice}`}>
                  Lote {lote.lote}
                  {lote.colada ? ` · Colada ${lote.colada}` : ''}
                  {' · '}{FORMATO_MONEDA.format(lote.costo)}
                </li>
              ))}
            </ul>
          )}
        </aside>
      )}
      {nodosVisibles.length === 0 && <p className="rounded border border-amber-200 bg-amber-50 p-3 text-amber-800">No hay componentes de costo registrados para esta orden.</p>}
    </section>
  );
}
