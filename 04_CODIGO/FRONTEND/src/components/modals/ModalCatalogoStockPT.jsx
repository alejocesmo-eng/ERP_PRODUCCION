// src/components/modals/ModalCatalogoStockPT.jsx
// OT-2026-008: catálogo de stock de producto terminado (PT), solo lectura.
// Compartido por cotizaciones y pedidos. Consultar no reserva unidades.
// Se monta con createPortal fuera de cualquier <form> para que Enter no envíe el formulario padre.
import React, { useState, useEffect, useRef, useId } from 'react';
import { createPortal } from 'react-dom';
import { consultarStockPT } from '../../services/api';

const LIMITE_PAGINA = 50;
const FOCO = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2';
const CLASE_BADGE = 'inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-extrabold uppercase';

// Acepta lista simple o { items, total }. Contrato exacto definido en OT-2026-008 sección 2.4.
const normalizarRespuesta = (data) => {
  const items = Array.isArray(data) ? data : (data?.items || data?.resultados || data?.data || []);
  const total = typeof data?.total === 'number' ? data.total : null;
  return { items, total };
};

const disponibleEntero = (item) => Math.max(0, Math.floor(Number(item?.stock_disponible) || 0));

const formatoPrecio = (valor) => `$ ${Math.round(Number(valor) || 0).toLocaleString('es-CO')}`;

export default function ModalCatalogoStockPT({ abierto, modo = 'cotizacion', lineasAgregadas = [], onAgregar, onCerrar }) {
  const idTitulo = useId();
  const idAyuda = useId();
  const idCantidadAyuda = useId();
  const idCantidadError = useId();
  const idMotivo = useId();

  const [busqueda, setBusqueda] = useState('');
  const [busquedaDebounce, setBusquedaDebounce] = useState('');
  const [soloConSaldo, setSoloConSaldo] = useState(true);
  const [recarga, setRecarga] = useState(0);
  const [estado, setEstado] = useState('cargando'); // cargando | ok | error | sinpermiso
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(null);
  const [ocultos, setOcultos] = useState(null);
  const [cargandoMas, setCargandoMas] = useState(false);
  const [seleccion, setSeleccion] = useState(null);
  const [cantidad, setCantidad] = useState('1');
  const [agregando, setAgregando] = useState(false);
  const [mensajeOk, setMensajeOk] = useState('');
  const [errorAgregar, setErrorAgregar] = useState('');
  const [saldoCambio, setSaldoCambio] = useState(null);
  const [focoIdx, setFocoIdx] = useState(-1);

  const panelRef = useRef(null);
  const buscadorRef = useRef(null);
  const filasRef = useRef([]);
  const solicitudRef = useRef(0);
  const onCerrarRef = useRef(onCerrar);
  onCerrarRef.current = onCerrar;

  // Apertura: reinicia estado, guarda el disparador y lleva el foco al buscador. Al cerrar devuelve el foco.
  useEffect(() => {
    if (!abierto) return undefined;
    const disparador = document.activeElement;
    setBusqueda('');
    setBusquedaDebounce('');
    setSoloConSaldo(true);
    setSeleccion(null);
    setCantidad('1');
    setMensajeOk('');
    setErrorAgregar('');
    setSaldoCambio(null);
    setFocoIdx(-1);
    const temporizador = setTimeout(() => buscadorRef.current?.focus(), 0);
    return () => {
      clearTimeout(temporizador);
      if (disparador && typeof disparador.focus === 'function') disparador.focus();
    };
  }, [abierto]);

  // Esc cierra solo este modal (captura en document para no llegar a los ancestros).
  useEffect(() => {
    if (!abierto) return undefined;
    const alPresionar = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        e.preventDefault();
        onCerrarRef.current?.();
      }
    };
    document.addEventListener('keydown', alPresionar, true);
    return () => document.removeEventListener('keydown', alPresionar, true);
  }, [abierto]);

  // Debounce de 300 ms del buscador.
  useEffect(() => {
    if (!abierto) return undefined;
    const temporizador = setTimeout(() => setBusquedaDebounce(busqueda.trim()), 300);
    return () => clearTimeout(temporizador);
  }, [busqueda, abierto]);

  // Consulta al servidor (la categoría PRODUCTO_TERMINADO la fija el backend, no el cliente).
  useEffect(() => {
    if (!abierto) return;
    const idSolicitud = ++solicitudRef.current;
    setEstado('cargando');
    setFocoIdx(-1);
    (async () => {
      try {
        const [respuesta, respuestaTodos] = await Promise.all([
          consultarStockPT({ q: busquedaDebounce, soloConSaldo, limit: LIMITE_PAGINA, offset: 0 }),
          soloConSaldo
            ? consultarStockPT({ q: busquedaDebounce, soloConSaldo: false, limit: 1, offset: 0 })
            : Promise.resolve(null)
        ]);
        if (idSolicitud !== solicitudRef.current) return;
        const principal = normalizarRespuesta(respuesta.data);
        setItems(principal.items);
        setTotal(principal.total);
        if (respuestaTodos) {
          const todos = normalizarRespuesta(respuestaTodos.data);
          setOcultos(principal.total !== null && todos.total !== null ? Math.max(0, todos.total - principal.total) : null);
        } else {
          setOcultos(0);
        }
        setEstado('ok');
      } catch (err) {
        if (idSolicitud !== solicitudRef.current) return;
        setEstado(err?.response?.status === 403 ? 'sinpermiso' : 'error');
      }
    })();
  }, [abierto, busquedaDebounce, soloConSaldo, recarga]);

  if (!abierto) return null;

  const yaAgregado = seleccion
    ? lineasAgregadas
        .filter(l => (l.id_articulo && l.id_articulo === seleccion.id_articulo) || (!l.id_articulo && l.sku === seleccion.codigo_sku))
        .reduce((acc, l) => acc + (Number(l.cantidad) || 0), 0)
    : 0;
  const unidad = seleccion?.unidad_medida || 'und';
  const restante = seleccion ? Math.max(0, disponibleEntero(seleccion) - yaAgregado) : 0;
  const textoCantidad = cantidad.trim();
  const numeroCantidad = /^\d+$/.test(textoCantidad) ? Number(textoCantidad) : NaN;

  let errorCantidad = '';
  if (seleccion && textoCantidad !== '') {
    if (!Number.isInteger(numeroCantidad) || numeroCantidad < 1) {
      errorCantidad = 'La cantidad debe ser un número entero mayor o igual a 1.';
    } else if (numeroCantidad > restante) {
      errorCantidad = restante <= 0
        ? `Ya agregó todo el disponible de ${seleccion.codigo_sku} (${yaAgregado} ${unidad}).`
        : `Cantidad mayor al disponible para venta. Máximo: ${restante} ${unidad}. Reduzca la cantidad o consulte a Almacén.${yaAgregado > 0 ? ` (ya en posiciones: ${yaAgregado})` : ''}`;
    }
  }
  const puedeAgregar = !!seleccion && textoCantidad !== '' && !errorCantidad && !agregando;
  const motivoDeshabilitado = !seleccion
    ? 'Seleccione un ítem de la tabla.'
    : textoCantidad === '' ? 'Ingrese la cantidad.'
    : errorCantidad ? 'Corrija la cantidad para continuar.' : '';

  const indicesSeleccionables = items.reduce((acc, it, i) => (disponibleEntero(it) > 0 ? [...acc, i] : acc), []);

  const seleccionarItem = (item) => {
    if (disponibleEntero(item) <= 0) return;
    setSeleccion(item);
    setCantidad('1');
    setMensajeOk('');
    setErrorAgregar('');
    setSaldoCambio(null);
  };

  const moverFoco = (direccion) => {
    if (indicesSeleccionables.length === 0) return;
    const pos = indicesSeleccionables.indexOf(focoIdx);
    const destino = indicesSeleccionables[Math.min(indicesSeleccionables.length - 1, Math.max(0, pos < 0 ? 0 : pos + direccion))];
    setFocoIdx(destino);
    filasRef.current[destino]?.focus();
  };

  const alTeclearFila = (e, item) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); moverFoco(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moverFoco(-1); }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); seleccionarItem(item); }
  };

  const cargarMas = async () => {
    setCargandoMas(true);
    try {
      const respuesta = await consultarStockPT({ q: busquedaDebounce, soloConSaldo, limit: LIMITE_PAGINA, offset: items.length });
      const siguiente = normalizarRespuesta(respuesta.data);
      setItems(prev => [...prev, ...siguiente.items]);
    } catch (err) {
      setEstado(err?.response?.status === 403 ? 'sinpermiso' : 'error');
    } finally {
      setCargandoMas(false);
    }
  };

  // Antes de agregar se vuelve a consultar el saldo: puede haber cambiado con el modal abierto.
  const agregar = async () => {
    if (!puedeAgregar) return;
    setAgregando(true);
    setErrorAgregar('');
    setSaldoCambio(null);
    setMensajeOk('');
    try {
      const respuesta = await consultarStockPT({ q: seleccion.codigo_sku, soloConSaldo: false, limit: 10, offset: 0 });
      const fresco = normalizarRespuesta(respuesta.data).items.find(i => i.id_articulo === seleccion.id_articulo);
      if (!fresco) {
        setErrorAgregar(`${seleccion.codigo_sku} ya no figura en el catálogo de stock PT. No se agregó ninguna línea.`);
        return;
      }
      setSeleccion(fresco);
      setItems(prev => prev.map(i => (i.id_articulo === fresco.id_articulo ? fresco : i)));
      const restanteFresco = Math.max(0, disponibleEntero(fresco) - yaAgregado);
      if (numeroCantidad > restanteFresco) {
        setSaldoCambio({ sku: fresco.codigo_sku, restante: restanteFresco, unidad: fresco.unidad_medida || 'und' });
        return;
      }
      const resultado = onAgregar({
        id_articulo: fresco.id_articulo,
        codigo_sku: fresco.codigo_sku,
        nombre: fresco.nombre,
        unidad_medida: fresco.unidad_medida || 'UND',
        ubicacion: fresco.ubicacion || '',
        precio_unitario_valorado: Number(fresco.precio_unitario_valorado) || 0,
        stock_disponible: disponibleEntero(fresco),
        cantidad: numeroCantidad
      }) || {};
      const numeroLinea = resultado.numeroLinea ?? '';
      setMensajeOk(
        resultado.consolidada
          ? `${fresco.codigo_sku} ya estaba en la línea ${numeroLinea}. Cantidad actualizada a ${resultado.cantidadTotal}.`
          : `✅ ${fresco.codigo_sku} agregado a la línea ${numeroLinea}.`
      );
      setCantidad('1');
    } catch (err) {
      setErrorAgregar('No fue posible consultar el stock. No se agregó ninguna línea. Intente de nuevo.');
    } finally {
      setAgregando(false);
    }
  };

  // Tab atrapado dentro del panel; el resto de teclas no sube a los ancestros.
  const alTeclearOverlay = (e) => {
    if (e.key === 'Tab' && panelRef.current) {
      const enfocables = Array.from(
        panelRef.current.querySelectorAll('button, input, [tabindex="0"]')
      ).filter(el => !el.disabled && el.getAttribute('tabindex') !== '-1');
      if (enfocables.length > 0) {
        const primero = enfocables[0];
        const ultimo = enfocables[enfocables.length - 1];
        if (e.shiftKey && document.activeElement === primero) { e.preventDefault(); ultimo.focus(); }
        else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primero.focus(); }
      }
    }
    e.stopPropagation();
  };

  const textoContador = estado === 'ok'
    ? `${total ?? items.length} ${(total ?? items.length) === 1 ? 'ítem' : 'ítems'}`
    : '';

  return createPortal(
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/40 p-3 backdrop-blur-sm"
      onKeyDown={alTeclearOverlay}
      onClick={(e) => e.stopPropagation()}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        aria-describedby={idAyuda}
        className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-xl border border-slate-300 bg-white p-4 text-xs text-slate-800 shadow-2xl space-y-3"
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 id={idTitulo} className="text-base font-bold text-slate-800">
              <span aria-hidden="true">📦</span> Catálogo de stock PT
            </h2>
            <p id={idAyuda} className="text-slate-600">
              Consulta de solo lectura. Consultar no reserva unidades. El precio es una referencia (costo valorado) y se puede editar en la posición.
            </p>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            aria-label="Cerrar catálogo de stock PT"
            className={`h-8 w-8 rounded text-lg font-bold text-slate-700 hover:bg-slate-100 cursor-pointer ${FOCO}`}
          >
            <span aria-hidden="true">✕</span>
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex-1 min-w-[240px]">
            <label htmlFor={`${idTitulo}-buscar`} className="sr-only">Buscar en catálogo de stock PT</label>
            <input
              id={`${idTitulo}-buscar`}
              ref={buscadorRef}
              type="text"
              autoComplete="off"
              placeholder="Buscar por SKU, descripción o ubicación"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') e.preventDefault();
                if (e.key === 'ArrowDown') { e.preventDefault(); moverFoco(0); }
              }}
              className={`h-8 w-full rounded border border-slate-500 bg-white px-2 text-slate-800 placeholder:text-slate-500 ${FOCO}`}
            />
          </div>
          <label className="flex items-center gap-1.5 font-bold text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={soloConSaldo}
              onChange={(e) => setSoloConSaldo(e.target.checked)}
              className={`h-4 w-4 ${FOCO}`}
            />
            Solo con saldo
          </label>
          <div aria-live="polite" className="flex items-center gap-3 text-slate-600">
            <span className="font-bold">{textoContador}</span>
            {soloConSaldo && estado === 'ok' && ocultos !== null && ocultos > 0 && (
              <span>Sin saldo ocultos: {ocultos}</span>
            )}
          </div>
        </div>

        <div className="min-h-[120px] flex-1 overflow-auto rounded-lg border border-slate-200 max-h-[50vh]" aria-busy={estado === 'cargando'}>
          {estado === 'cargando' && (
            <div className="p-3 space-y-2">
              <p role="status" className="font-bold text-slate-600">Buscando…</p>
              {[0, 1, 2, 3, 4].map(n => (
                <div key={n} className="h-4 rounded bg-slate-200 animate-pulse motion-reduce:animate-none" />
              ))}
            </div>
          )}

          {estado === 'error' && (
            <div role="alert" className="m-3 flex items-center justify-between rounded border border-red-300 bg-red-50 p-3 text-red-800">
              <span>No fue posible consultar el stock. No se agregó ninguna línea.</span>
              <button
                type="button"
                onClick={() => setRecarga(n => n + 1)}
                className={`rounded border border-slate-500 bg-white px-3 py-1 font-bold text-slate-800 hover:bg-slate-100 cursor-pointer ${FOCO}`}
              >
                Reintentar
              </button>
            </div>
          )}

          {estado === 'sinpermiso' && (
            <div role="alert" className="m-3 rounded border border-amber-300 bg-amber-50 p-3 text-amber-900">
              Su perfil no tiene acceso a la consulta de stock.
            </div>
          )}

          {estado === 'ok' && items.length === 0 && (
            <div className="p-4 text-slate-700 space-y-2">
              {busquedaDebounce ? (
                <>
                  <p>No hay productos terminados con saldo que coincidan con &apos;{busquedaDebounce}&apos;. Revise el código o use Fabricación sobre plano.</p>
                  <button
                    type="button"
                    onClick={() => { setBusqueda(''); setBusquedaDebounce(''); buscadorRef.current?.focus(); }}
                    className={`rounded border border-slate-500 bg-white px-3 py-1 font-bold text-slate-800 hover:bg-slate-100 cursor-pointer ${FOCO}`}
                  >
                    Limpiar búsqueda
                  </button>
                </>
              ) : (
                <p>No hay productos terminados con saldo para venta.</p>
              )}
            </div>
          )}

          {estado === 'ok' && items.length > 0 && (
            <table role="grid" aria-label="Productos terminados disponibles" className="w-full border-collapse text-left text-xs">
              <thead className="sticky top-0 bg-slate-100 font-bold uppercase text-slate-700 border-b border-slate-200">
                <tr>
                  <th scope="col" className="py-2 px-3">SKU</th>
                  <th scope="col" className="py-2 px-3">Descripción</th>
                  <th scope="col" className="py-2 px-3">Ubicación</th>
                  <th scope="col" className="py-2 px-3 text-right">Disponible</th>
                  <th scope="col" className="py-2 px-3 text-right">Precio catálogo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {items.map((item, i) => {
                  const disponible = disponibleEntero(item);
                  const agotado = disponible <= 0;
                  const elegido = seleccion?.id_articulo === item.id_articulo;
                  const indiceTab = indicesSeleccionables.includes(focoIdx) ? focoIdx : indicesSeleccionables[0];
                  return (
                    <tr
                      key={item.id_articulo || item.codigo_sku}
                      ref={(el) => { filasRef.current[i] = el; }}
                      role="row"
                      aria-selected={elegido}
                      aria-disabled={agotado ? 'true' : undefined}
                      tabIndex={!agotado && i === indiceTab ? 0 : -1}
                      onClick={() => seleccionarItem(item)}
                      onFocus={() => { if (!agotado) setFocoIdx(i); }}
                      onKeyDown={(e) => { if (!agotado) alTeclearFila(e, item); }}
                      className={
                        agotado
                          ? `bg-slate-50 text-slate-600 cursor-not-allowed ${FOCO}`
                          : elegido
                            ? `bg-blue-50 ring-2 ring-inset ring-blue-600 cursor-pointer ${FOCO}`
                            : `hover:bg-slate-50 cursor-pointer ${FOCO}`
                      }
                    >
                      <td role="gridcell" className="py-2 px-3 font-mono font-bold tabular-nums">{item.codigo_sku}</td>
                      <td role="gridcell" className="py-2 px-3">{item.nombre}</td>
                      <td role="gridcell" className="py-2 px-3">{item.ubicacion || 'Sin ubicación'}</td>
                      <td role="gridcell" className="py-2 px-3 text-right font-mono tabular-nums">
                        {agotado ? (
                          <span>
                            <span className={`${CLASE_BADGE} bg-slate-200 text-slate-700 border-slate-300`}>Agotado</span>
                            <span className="ml-2 block text-slate-600 font-sans">Sin saldo para venta.</span>
                          </span>
                        ) : (
                          <span className="font-bold">{disponible} {item.unidad_medida || 'und'}</span>
                        )}
                      </td>
                      <td role="gridcell" className="py-2 px-3 text-right font-mono tabular-nums">{formatoPrecio(item.precio_unitario_valorado)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {estado === 'ok' && total !== null && items.length < total && (
            <div className="p-2 text-center">
              <button
                type="button"
                onClick={cargarMas}
                disabled={cargandoMas}
                className={`rounded border border-slate-500 bg-white px-3 py-1 font-bold text-slate-800 hover:bg-slate-100 cursor-pointer disabled:opacity-60 ${FOCO}`}
              >
                {cargandoMas ? 'Cargando…' : `Cargar más (${items.length} de ${total})`}
              </button>
            </div>
          )}
        </div>

        <div aria-live="polite" role="status">
          {mensajeOk && (
            <div className="rounded border border-emerald-300 bg-emerald-50 p-2 font-bold text-emerald-800">{mensajeOk}</div>
          )}
        </div>
        {errorAgregar && (
          <div role="alert" className="rounded border border-red-300 bg-red-50 p-2 font-bold text-red-800">{errorAgregar}</div>
        )}
        {saldoCambio && (
          <div role="alert" className="flex items-center justify-between rounded border border-amber-300 bg-amber-50 p-2 text-amber-900">
            <span>
              El saldo de {saldoCambio.sku} cambió. Disponible ahora: {saldoCambio.restante} {saldoCambio.unidad}. Ajuste la cantidad para continuar.
            </span>
            {saldoCambio.restante >= 1 && (
              <button
                type="button"
                onClick={() => { setCantidad(String(saldoCambio.restante)); setSaldoCambio(null); }}
                className={`rounded border border-amber-700 bg-white px-3 py-1 font-bold text-amber-900 hover:bg-amber-100 cursor-pointer ${FOCO}`}
              >
                Usar {saldoCambio.restante}
              </button>
            )}
          </div>
        )}

        <div className="flex flex-wrap items-start justify-between gap-3 border-t border-slate-200 bg-white pt-3">
          <div className="space-y-1">
            <p className="text-slate-700">
              Seleccionado:{' '}
              {seleccion
                ? <span className="font-bold"><span className="font-mono">{seleccion.codigo_sku}</span> · {seleccion.nombre}</span>
                : <span className="text-slate-600">Ninguno</span>}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor={`${idTitulo}-cantidad`} className="text-[11px] font-bold uppercase tracking-wide text-slate-600">
                Cantidad ({unidad})
              </label>
              <input
                id={`${idTitulo}-cantidad`}
                type="number"
                inputMode="numeric"
                min="1"
                max={seleccion ? restante : undefined}
                step="1"
                value={cantidad}
                disabled={!seleccion}
                onChange={(e) => { setCantidad(e.target.value); setSaldoCambio(null); }}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); agregar(); } }}
                aria-invalid={errorCantidad ? 'true' : undefined}
                aria-describedby={errorCantidad ? `${idCantidadAyuda} ${idCantidadError}` : idCantidadAyuda}
                className={`h-8 w-24 rounded border px-2 text-center font-mono font-bold tabular-nums disabled:bg-slate-100 disabled:text-slate-600 ${
                  errorCantidad
                    ? 'border-red-600 bg-red-50 text-red-900 focus-visible:ring-red-600'
                    : 'border-slate-500 bg-white text-slate-800'
                } ${FOCO}`}
              />
              <span id={idCantidadAyuda} className="text-slate-600">
                {seleccion ? `Mín. 1 · Máx. ${restante} ${unidad}` : 'Mín. 1'}
              </span>
            </div>
            {errorCantidad && (
              <p id={idCantidadError} className="font-bold text-red-700">
                <span aria-hidden="true">⚠ </span>{errorCantidad}
              </p>
            )}
          </div>

          <div className="flex flex-col items-end gap-1">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onCerrar}
                className={`h-8 rounded border border-slate-500 bg-white px-4 font-bold text-slate-800 hover:bg-slate-100 cursor-pointer ${FOCO}`}
              >
                Listo
              </button>
              <button
                type="button"
                onClick={agregar}
                aria-disabled={puedeAgregar ? undefined : 'true'}
                aria-describedby={puedeAgregar ? undefined : idMotivo}
                className={`h-8 rounded border px-4 font-bold ${
                  puedeAgregar
                    ? 'border-emerald-800 bg-emerald-700 text-white hover:bg-emerald-800 cursor-pointer'
                    : 'border-slate-300 bg-slate-200 text-slate-600 cursor-not-allowed'
                } ${FOCO}`}
              >
                <span aria-hidden="true">➕</span> Agregar a {modo === 'pedido' ? 'Posiciones del pedido' : 'Posiciones'}
              </button>
            </div>
            {!puedeAgregar && (
              <p id={idMotivo} className="text-slate-600">{agregando ? 'Verificando saldo…' : motivoDeshabilitado}</p>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
