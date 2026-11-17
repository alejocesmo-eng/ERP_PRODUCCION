import React, { useEffect, useState } from 'react';
import API, { API_ORIGIN, mensajeError } from '../../services/api';

// Orden de fabricación en solo lectura, con la distribución de la pantalla de SAP.
// Datos de GET /ordenes/expediente/{op}: el backend ya quita los campos que el rol no ve
// (valor cotizado, cliente), y este modal no pide costos. Un campo que la API no trae queda vacío.
// Liberar la OP y aprobar planos siguen en ExpedienteOpModal.

const PESTANAS = [
  { id: 'componentes', etiqueta: 'Componentes' },
  { id: 'resumen', etiqueta: 'Resumen' },
  { id: 'anexos', etiqueta: 'Anexos' }
];

// Entradas del menú de opciones, sin contenido todavía
const OPCIONES = [
  { id: 'mapa', etiqueta: 'Mapa de relaciones' },
  { id: 'tiempos', etiqueta: 'Carga de tiempos' }
];

const ETIQUETAS_ARCHIVO = { PDF: 'Plano PDF', STEP: 'Modelo STEP', DXF: 'Contorno DXF' };

function texto(valor) {
  return valor === null || valor === undefined ? '' : String(valor).replaceAll('_', ' ');
}

function fecha(valor) {
  if (!valor) return '';
  const fechaValor = new Date(valor);
  return Number.isNaN(fechaValor.getTime()) ? valor : fechaValor.toLocaleDateString('es-CO');
}

function numero(valor) {
  return valor === null || valor === undefined || valor === '' ? '' : Number(valor).toLocaleString('es-CO');
}

function urlArchivo(ruta) {
  return /^https?:\/\//i.test(ruta) ? ruta : `${API_ORIGIN}${ruta}`;
}

function Campo({ etiqueta, valor }) {
  return (
    <div className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] items-center gap-2">
      <span className="truncate text-slate-600">{etiqueta}</span>
      <output className="block min-h-[1.375rem] truncate rounded-sm border border-slate-300 bg-slate-100 px-1.5 py-0.5 text-slate-900" title={valor || undefined}>
        {valor}
      </output>
    </div>
  );
}

function Tabla({ columnas, filas, vacio }) {
  return (
    <div className="overflow-x-auto border border-slate-300">
      <table className="w-full min-w-[900px] border-collapse text-left">
        <thead className="bg-slate-100 text-slate-700">
          <tr>
            {columnas.map((columna) => (
              <th key={columna.id} scope="col" className={`border-b border-r border-slate-300 px-2 py-1 font-semibold ${columna.numerica ? 'text-right' : ''}`}>
                {columna.etiqueta}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, indice) => (
            <tr key={fila.clave ?? indice} className="odd:bg-white even:bg-slate-50">
              {columnas.map((columna) => (
                <td key={columna.id} className={`border-b border-r border-slate-200 px-2 py-1 ${columna.numerica ? 'text-right font-mono' : ''}`}>
                  {fila[columna.id]}
                </td>
              ))}
            </tr>
          ))}
          {!filas.length && (
            <tr><td colSpan={columnas.length} className="px-2 py-6 text-center text-slate-500">{vacio}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

const COLUMNAS_COMPONENTES = [
  { id: 'n', etiqueta: '#', numerica: true },
  { id: 'tipo', etiqueta: 'Tipo' },
  { id: 'numero', etiqueta: 'Número' },
  { id: 'descripcion', etiqueta: 'Descripción' },
  { id: 'requerida', etiqueta: 'Cantidad requerida', numerica: true },
  { id: 'centroCosto', etiqueta: 'Centro de costo' },
  { id: 'consumido', etiqueta: 'Consumido', numerica: true },
  { id: 'enAlmacen', etiqueta: 'Cantidad en almacén', numerica: true },
  { id: 'disponible', etiqueta: 'Disponible', numerica: true },
  { id: 'unidad', etiqueta: 'Unidad de medida' }
];

// Líneas de BOM de los planos vigentes. Cantidad en almacén: suma del stock de sus lotes;
// disponible: ese stock menos lo reservado. La API no trae centro de costo ni consumido por línea.
function filasComponentes(expediente) {
  return (expediente.resumen_bom || []).map((linea, indice) => {
    const lotes = linea.lotes || [];
    const enAlmacen = lotes.reduce((suma, lote) => suma + Number(lote.stock_disponible || 0), 0);
    const reservado = lotes.reduce((suma, lote) => suma + Number(lote.stock_reservado || 0), 0);
    return {
      clave: `${linea.codigo_material}-${indice}`,
      n: indice + 1,
      tipo: 'Artículo',
      numero: linea.codigo_material,
      descripcion: linea.descripcion,
      requerida: numero(linea.cantidad_requerida),
      centroCosto: '',
      consumido: '',
      enAlmacen: lotes.length ? numero(enAlmacen) : '',
      disponible: lotes.length ? numero(Math.max(enAlmacen - reservado, 0)) : '',
      unidad: linea.unidad_medida
    };
  });
}

function filasAnexos(expediente) {
  return (expediente.planos || []).flatMap((plano) => Object.entries(plano.archivos || {}).map(([tipo, archivo]) => ({
    clave: `${plano.id_plano}-${tipo}`,
    plano: `${plano.codigo_plano} · ${plano.revision || ''}`,
    tipo: ETIQUETAS_ARCHIVO[tipo] || tipo,
    nombre: (
      <a href={urlArchivo(archivo.ruta)} target="_blank" rel="noreferrer" className="text-blue-700 underline">
        {archivo.nombre_original || archivo.ruta}
      </a>
    ),
    revision: archivo.revision,
    subido: [archivo.subido_por, fecha(archivo.subido_en)].filter(Boolean).join(' · ')
  })));
}

export default function OrdenFabricacionModal({ abierto, codigoOp, onClose }) {
  const [expediente, setExpediente] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');
  const [pestana, setPestana] = useState('componentes');
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [opcion, setOpcion] = useState(null);

  useEffect(() => {
    if (!abierto || !codigoOp) return undefined;
    let activo = true;
    setCargando(true);
    setError('');
    setExpediente(null);
    setPestana('componentes');
    setMenuAbierto(false);
    setOpcion(null);
    API.get(`/ordenes/expediente/${encodeURIComponent(codigoOp)}`)
      .then((respuesta) => {
        if (activo) setExpediente(respuesta.data);
      })
      .catch((fallo) => {
        if (activo) setError(mensajeError(fallo, 'No fue posible cargar la orden de fabricación.'));
      })
      .finally(() => {
        if (activo) setCargando(false);
      });
    return () => {
      activo = false;
    };
  }, [abierto, codigoOp]);

  useEffect(() => {
    if (!abierto) return undefined;
    const alPresionar = (evento) => {
      if (evento.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', alPresionar);
    return () => window.removeEventListener('keydown', alPresionar);
  }, [abierto, onClose]);

  if (!abierto) return null;

  const pedido = expediente?.pedido || {};
  const producto = expediente?.producto || {};
  const opcionActiva = OPCIONES.find((item) => item.id === opcion);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/60 p-3 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="orden-fabricacion-titulo"
        className="flex max-h-[94vh] w-full max-w-6xl flex-col overflow-hidden rounded-lg border border-slate-400 bg-slate-50 text-xs shadow-2xl"
      >
        <header className="flex items-center justify-between gap-2 bg-blue-900 px-3 py-1.5 text-white">
          <h2 id="orden-fabricacion-titulo" className="font-bold">Orden de fabricación {codigoOp}</h2>
          <div className="flex items-center gap-1">
            <div className="relative">
              <button
                type="button"
                aria-haspopup="menu"
                aria-expanded={menuAbierto}
                onClick={() => setMenuAbierto((valor) => !valor)}
                className="rounded border border-blue-300 bg-blue-800 px-2 py-0.5 font-semibold hover:bg-blue-700"
              >
                Opciones ▾
              </button>
              {menuAbierto && (
                <ul role="menu" className="absolute right-0 z-10 mt-1 w-48 overflow-hidden rounded border border-slate-300 bg-white text-slate-800 shadow-lg">
                  {OPCIONES.map((item) => (
                    <li key={item.id} role="none">
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setOpcion(item.id);
                          setMenuAbierto(false);
                        }}
                        className="block w-full px-3 py-1.5 text-left hover:bg-slate-100"
                      >
                        {item.etiqueta}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Cerrar orden de fabricación"
              className="rounded px-2 text-lg font-bold leading-none hover:bg-blue-700"
            >
              ×
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {cargando && <p className="rounded bg-white p-4 text-center font-semibold text-slate-600">Cargando orden de fabricación…</p>}
          {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 font-semibold text-red-800">{error}</p>}

          {opcionActiva && (
            <div role="status" className="mb-3 flex items-center justify-between gap-2 rounded border border-slate-300 bg-white p-2">
              <span><strong>{opcionActiva.etiqueta}</strong>: sin contenido todavía.</span>
              <button type="button" onClick={() => setOpcion(null)} className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100">Volver</button>
            </div>
          )}

          {expediente && (
            <>
              <div className="grid gap-x-8 gap-y-1 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
                <div className="space-y-1">
                  <Campo etiqueta="Tipo" valor="" />
                  <Campo etiqueta="Estado" valor={texto(expediente.estado_operativo)} />
                  <Campo etiqueta="Nº producto" valor={producto.codigo_rn || ''} />
                  <Campo etiqueta="Descripción producto" valor={producto.descripcion || ''} />
                  <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
                    <Campo etiqueta="Cantidad planificada" valor={numero(expediente.cantidad_programada)} />
                    <Campo etiqueta="Unidad" valor="" />
                  </div>
                  <Campo etiqueta="Almacén" valor="" />
                  <Campo etiqueta="Prioridad" valor="" />
                </div>
                <div className="space-y-1">
                  <Campo etiqueta="Nº" valor={expediente.codigo_op} />
                  <Campo etiqueta="Fecha orden de fabricación" valor="" />
                  <Campo etiqueta="Fecha de liberación" valor="" />
                  <Campo etiqueta="Fecha de entrega" valor={fecha(pedido.fecha_limite)} />
                  <Campo etiqueta="Usuario" valor="" />
                  <Campo etiqueta="Origen" valor="" />
                  <Campo etiqueta="Pedido vinculado" valor={pedido.numero_pedido || ''} />
                  <Campo etiqueta="Cliente" valor={pedido.cliente || ''} />
                  <Campo etiqueta="Norma de reparto" valor="" />
                  <Campo etiqueta="Proyecto" valor="" />
                </div>
              </div>

              <div role="tablist" aria-label="Detalle de la orden" className="mt-4 flex gap-1 border-b border-slate-300">
                {PESTANAS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    aria-selected={pestana === item.id}
                    onClick={() => setPestana(item.id)}
                    className={`rounded-t border border-b-0 px-4 py-1 font-semibold ${pestana === item.id ? 'border-slate-300 bg-white text-slate-900' : 'border-transparent text-slate-600 hover:bg-slate-200'}`}
                  >
                    {item.etiqueta}
                  </button>
                ))}
              </div>
              <div role="tabpanel" className="border border-t-0 border-slate-300 bg-white p-2">
                {pestana === 'componentes' && (
                  <Tabla columnas={COLUMNAS_COMPONENTES} filas={filasComponentes(expediente)} vacio="La OP no tiene componentes registrados." />
                )}
                {pestana === 'resumen' && (
                  <div className="grid max-w-xl gap-1">
                    <Campo etiqueta="Cantidad planificada" valor={numero(expediente.cantidad_programada)} />
                    <Campo etiqueta="Avance" valor={`${numero(expediente.porcentaje_avance || 0)} %`} />
                    <Campo etiqueta="Cantidad entregada" valor={numero(pedido.cantidad_entregada)} />
                    <Campo etiqueta="Estado de entregas" valor={texto(pedido.estado_entregas)} />
                    <Campo etiqueta="Estado de materiales" valor={texto(expediente.estado_bom)} />
                    <Campo etiqueta="Unidad actual" valor={texto(expediente.unidad_actual)} />
                  </div>
                )}
                {pestana === 'anexos' && (
                  <Tabla
                    columnas={[
                      { id: 'plano', etiqueta: 'Plano' },
                      { id: 'tipo', etiqueta: 'Tipo' },
                      { id: 'nombre', etiqueta: 'Archivo' },
                      { id: 'revision', etiqueta: 'Revisión' },
                      { id: 'subido', etiqueta: 'Cargado por' }
                    ]}
                    filas={filasAnexos(expediente)}
                    vacio="La OP no tiene anexos."
                  />
                )}
              </div>

              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-2">
                  <span className="text-slate-600">Comentarios</span>
                  <output className="block min-h-[3.5rem] whitespace-pre-wrap rounded-sm border border-slate-300 bg-slate-100 px-1.5 py-1 text-slate-900">
                    {expediente.observaciones || ''}
                  </output>
                </div>
                <div className="grid grid-cols-[8rem_minmax(0,1fr)] gap-2">
                  <span className="text-slate-600">Observaciones sobre empaque</span>
                  <output className="block min-h-[3.5rem] rounded-sm border border-slate-300 bg-slate-100 px-1.5 py-1" />
                </div>
              </div>
            </>
          )}
        </div>

        <footer className="flex justify-start border-t border-slate-300 bg-slate-100 px-3 py-2">
          <button type="button" onClick={onClose} className="rounded border border-slate-400 bg-amber-100 px-5 py-1 font-semibold text-slate-800 hover:bg-amber-200">
            Cerrar
          </button>
        </footer>
      </section>
    </div>
  );
}
