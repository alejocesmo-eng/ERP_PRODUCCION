import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';

const formularioArticuloInicial = {
  codigo_sku: '',
  nombre: '',
  descripcion: '',
  categoria: 'MATERIA_PRIMA',
  tipo_material_sap: 'ROH',
  unidad_medida: 'UND',
  clase_valoracion: '3000-MP',
  cuenta_contable_activo: '143505 - Inventario Materia Prima',
  cuenta_contable_gasto: '710505 - Consumo de Materia Prima',
  cuenta_contable_transitoria: '220505 - Recepción de facturas por conciliar',
  centro_costo_defecto: 'CC-100-PLANTA',
  metodo_valoracion: 'CPP',
  precio_unitario_valorado: '0',
  stock_seguridad: '0',
  punto_reorden: '0',
  codigo_centro: 'CENTRO-01-FUNZA',
  almacen_fisico: 'BOD-MP-01',
  stock_minimo: '0',
  ubicacion: ''
};

const formularioCentroInicial = {
  codigo_centro: '',
  nombre_centro: '',
  almacenes: ''
};

const formularioCategoriaInicial = {
  codigo: '',
  nombre: '',
  icono: '📦',
  descripcion: ''
};

const estadoBadge = {
  CUARENTENA: 'bg-amber-100 text-amber-800 border-amber-300',
  LIBERADO: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  RECHAZADO: 'bg-red-100 text-red-800 border-red-300'
};

const ETIQUETAS_MATERIAL = {
  ROH: { nombre: 'Materia Prima Directa', color: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  HALB: { nombre: 'Producto Semielaborado', color: 'bg-amber-100 text-amber-800 border-amber-200' },
  FERT: { nombre: 'Producto Terminado', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  VERB: { nombre: 'Consumible de Planta', color: 'bg-purple-100 text-purple-800 border-purple-200' },
  ERSA: { nombre: 'Repuesto de Mantenimiento', color: 'bg-slate-100 text-slate-800 border-slate-200' }
};
const ETIQUETAS_MOVIMIENTO = {
  '101': 'Entrada por compra',
  '201': 'Consumo imputado a centro de costos',
  '261': 'Consumo para orden de producción',
  '311': 'Traslado entre almacenes',
  '551': 'Baja por rechazo o descarte'
};
const ETIQUETAS_VALORACION = {
  CPP: 'Costo promedio ponderado',
  FIFO: 'Primero en entrar, primero en salir',
  PRECIO_ESTANDAR: 'Precio estándar'
};

const mostrarFecha = (fecha) => {
  if (!fecha) return '—';
  return new Date(fecha).toLocaleString();
};

const mensajeError = (error, predeterminado) =>
  error.response?.data?.detail || error.message || predeterminado;

export default function InventarioGeneralView() {
  const [pestañaActiva, setPestañaActiva] = useState('articulos');
  const [articulos, setArticulos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [lotes, setLotes] = useState([]);
  const [movimientos, setMovimientos] = useState([]);
  const [centros, setCentros] = useState([]);
  const [busqueda, setBusqueda] = useState('');
  const [loading, setLoading] = useState(false);
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [modalArticulo, setModalArticulo] = useState(false);
  const [modalCategoria, setModalCategoria] = useState(false);
  const [modalCentro, setModalCentro] = useState(false);
  const [formArticulo, setFormArticulo] = useState(formularioArticuloInicial);
  const [formCategoria, setFormCategoria] = useState(formularioCategoriaInicial);
  const [formCentro, setFormCentro] = useState(formularioCentroInicial);
  const [calidadDrafts, setCalidadDrafts] = useState({});
  const [requisicionesMRP, setRequisicionesMRP] = useState([]);
  const [auditoriaLote, setAuditoriaLote] = useState(null);

  const cargarDatos = async () => {
    setLoading(true);
    setError('');
    try {
      const [resArticulos, resCategorias, resLotes, resKardex, resCentros] = await Promise.all([
        API.get('/inventario/articulos'),
        API.get('/inventario/categorias'),
        API.get('/inventario/lotes'),
        API.get('/inventario/kardex-sap?limite=300'),
        API.get('/inventario/centros')
      ]);
      setArticulos(Array.isArray(resArticulos.data) ? resArticulos.data : []);
      setCategorias(Array.isArray(resCategorias.data) ? resCategorias.data : []);
      setLotes(Array.isArray(resLotes.data) ? resLotes.data : []);
      setMovimientos(Array.isArray(resKardex.data) ? resKardex.data : []);
      setCentros(Array.isArray(resCentros.data) ? resCentros.data : []);
    } catch (requestError) {
      setError(mensajeError(requestError, 'No fue posible cargar Inventario General.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargarDatos();
  }, []);

  const articulosFiltrados = useMemo(() => {
    const texto = busqueda.trim().toLocaleLowerCase();
    if (!texto) return articulos;
    return articulos.filter((articulo) =>
      `${articulo.codigo_sku} ${articulo.nombre} ${articulo.categoria} ${ETIQUETAS_MATERIAL[articulo.tipo_material_sap]?.nombre || ''}`.toLocaleLowerCase().includes(texto)
    );
  }, [articulos, busqueda]);

  const kpis = useMemo(() => ({
    referencias: articulos.length,
    valorCOP: articulos.reduce((total, articulo) => total + Number(articulo.valor_inventario || 0), 0),
    cuarentena: articulos.reduce((total, articulo) => total + Number(articulo.stock_cuarentena || 0), 0),
    criticos: articulos.filter((articulo) =>
      Number(articulo.punto_reorden || 0) > 0
      && Number(articulo.stock_actual || 0) <= Number(articulo.punto_reorden || 0)
    ).length,
    tipos: ['ROH', 'HALB', 'FERT', 'VERB', 'ERSA'].reduce((conteo, tipo) => ({
      ...conteo,
      [tipo]: articulos.filter((articulo) => articulo.tipo_material_sap === tipo).length
    }), {})
  }), [articulos]);

  const guardarArticulo = async (event) => {
    event.preventDefault();
    setProcesando(true);
    setError('');
    setMensaje('');
    try {
      await API.post('/inventario/articulos', {
        ...formArticulo,
        stock_minimo: Number(formArticulo.stock_minimo || 0),
        precio_unitario_valorado: Number(formArticulo.precio_unitario_valorado || 0),
        stock_seguridad: Number(formArticulo.stock_seguridad || 0),
        punto_reorden: Number(formArticulo.punto_reorden || 0)
      });
      setMensaje(`Código ${formArticulo.codigo_sku} registrado en el catálogo maestro.`);
      setFormArticulo(formularioArticuloInicial);
      setModalArticulo(false);
      await cargarDatos();
    } catch (requestError) {
      setError(mensajeError(requestError, 'No fue posible registrar el insumo.'));
    } finally {
      setProcesando(false);
    }
  };

  const guardarCategoria = async (event) => {
    event.preventDefault();
    setProcesando(true);
    setError('');
    setMensaje('');
    try {
      const respuesta = await API.post('/inventario/categorias', formCategoria);
      setCategorias((actuales) => [...actuales, respuesta.data].sort((a, b) => a.nombre.localeCompare(b.nombre)));
      setMensaje(`Categoría ${respuesta.data.nombre} registrada.`);
      setFormCategoria(formularioCategoriaInicial);
      setModalCategoria(false);
    } catch (requestError) {
      setError(mensajeError(requestError, 'No fue posible registrar la categoría.'));
    } finally {
      setProcesando(false);
    }
  };

  const guardarCentro = async (event) => {
    event.preventDefault();
    setProcesando(true);
    setError('');
    setMensaje('');
    try {
      const respuesta = await API.post('/inventario/centros', {
        ...formCentro,
        almacenes: formCentro.almacenes.split(',').map((almacen) => almacen.trim()).filter(Boolean)
      });
      setCentros((actuales) => [...actuales, respuesta.data].sort((a, b) => a.codigo_centro.localeCompare(b.codigo_centro)));
      setMensaje(`Centro ${respuesta.data.codigo_centro} registrado con ${respuesta.data.almacenes.length} almacén(es).`);
      setFormCentro(formularioCentroInicial);
      setModalCentro(false);
    } catch (requestError) {
      setError(mensajeError(requestError, 'No fue posible registrar el centro y sus almacenes.'));
    } finally {
      setProcesando(false);
    }
  };

  const actualizarCalidad = async (lote) => {
    const draft = calidadDrafts[lote.id] || {};
    if (!draft.estado_calidad || !draft.motivo?.trim()) {
      setError('Seleccione el nuevo estado e indique el motivo de la decisión de Calidad.');
      return;
    }
    setProcesando(true);
    setError('');
    setMensaje('');
    try {
      await API.patch(`/inventario/lotes/${lote.id}/calidad`, {
        estado_calidad: draft.estado_calidad,
        motivo: draft.motivo
      });
      setMensaje(`Lote ${lote.codigo_lote} actualizado a ${draft.estado_calidad}.`);
      setCalidadDrafts((actuales) => ({ ...actuales, [lote.id]: { ...draft, motivo: '' } }));
      await cargarDatos();
    } catch (requestError) {
      setError(mensajeError(requestError, 'No fue posible actualizar la calidad del lote.'));
    } finally {
      setProcesando(false);
    }
  };

  const consultarAuditoria = async (lote) => {
    setError('');
    try {
      const respuesta = await API.get(`/inventario/lotes/${lote.id}/auditoria`);
      setAuditoriaLote({ codigo_lote: lote.codigo_lote, registros: respuesta.data });
    } catch (requestError) {
      setError(mensajeError(requestError, 'No fue posible consultar la auditoría del lote.'));
    }
  };

  const ejecutarMRP = async () => {
    setProcesando(true);
    setError('');
    setMensaje('');
    try {
      const respuesta = await API.post('/solicitudes-compra/mrp/ejecutar');
      setRequisicionesMRP(Array.isArray(respuesta.data) ? respuesta.data : []);
      setMensaje(`Cálculo de necesidades netas ejecutado: ${respuesta.data.length} requerimiento(s) calculado(s).`);
      setPestañaActiva('mrp');
      await cargarDatos();
    } catch (requestError) {
      setError(mensajeError(requestError, 'No fue posible calcular las necesidades netas.'));
    } finally {
      setProcesando(false);
    }
  };

  const cambiarDraftCalidad = (idLote, campo, valor) => {
    setCalidadDrafts((actuales) => ({
      ...actuales,
      [idLote]: { ...actuales[idLote], [campo]: valor }
    }));
  };

  const seleccionarCentro = (codigoCentro) => {
    const centro = centros.find((item) => item.codigo_centro === codigoCentro);
    setFormArticulo((actual) => ({
      ...actual,
      codigo_centro: codigoCentro,
      almacen_fisico: centro?.almacenes?.[0] || ''
    }));
  };

  return (
    <main className="min-h-screen space-y-5 bg-slate-50 p-5 text-xs text-slate-700">
      <header className="flex flex-col justify-between gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">🧾 Inventario General</h1>
          <p className="mt-1 text-xs text-slate-500">
            Catálogo maestro, valoración financiera, trazabilidad de lotes y control de calidad.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={cargarDatos}
            disabled={loading}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-bold text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            {loading ? 'Cargando…' : '↻ Actualizar'}
          </button>
          <button
            type="button"
            onClick={ejecutarMRP}
            disabled={procesando}
            className="rounded-lg bg-amber-600 px-3 py-2 font-bold text-white hover:bg-amber-700 disabled:opacity-50"
          >
            Calcular necesidades netas
          </button>
          <button
            type="button"
            onClick={() => setModalCentro(true)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-bold text-slate-700 hover:bg-slate-50"
          >
            Centros / Almacenes
          </button>
          <Link
            to="/almacen/inventario"
            className="rounded-lg bg-slate-800 px-3 py-2 font-bold text-white hover:bg-slate-900"
          >
            Abrir Almacén Operativo →
          </Link>
        </div>
      </header>

      {error && (
        <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 font-semibold text-red-800">
          {error}
        </div>
      )}
      {mensaje && (
        <div role="status" className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 font-semibold text-emerald-800">
          {mensaje}
        </div>
      )}

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ['Valor total del inventario · COP', `$ ${kpis.valorCOP.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, 'text-slate-800'],
          ['Materia prima directa', kpis.tipos.ROH, 'text-emerald-700'],
          ['Productos semielaborados', kpis.tipos.HALB, 'text-amber-700'],
          ['Productos terminados', kpis.tipos.FERT, 'text-blue-700'],
          ['Consumibles de planta', kpis.tipos.VERB, 'text-purple-700'],
          ['Repuestos de mantenimiento', kpis.tipos.ERSA, 'text-slate-700'],
          ['Unidades en cuarentena', kpis.cuarentena.toLocaleString('es-CO'), 'text-amber-700'],
          ['Materiales bajo punto de reposición', kpis.criticos, 'text-red-700']
        ].map(([titulo, valor, color]) => (
          <article key={titulo} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">{titulo}</p>
            <p className={`mt-1 text-xl font-extrabold ${color}`}>{valor}</p>
          </article>
        ))}
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-3">
          <nav className="flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1" aria-label="Secciones de inventario">
            {[
              ['articulos', 'Catálogo de insumos'],
              ['lotes', 'Lotes y control de calidad'],
              ['kardex', 'Historial de movimientos'],
              ['mrp', 'Requerimientos de compra']
            ].map(([id, nombre]) => (
              <button
                type="button"
                key={id}
                onClick={() => setPestañaActiva(id)}
                className={`rounded-md px-3 py-2 font-bold transition ${
                  pestañaActiva === id ? 'bg-emerald-700 text-white shadow-sm' : 'text-slate-600 hover:bg-white'
                }`}
              >
                {nombre}
              </button>
            ))}
          </nav>
          {pestañaActiva === 'articulos' && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setModalCategoria(true)}
                className="rounded-lg border border-slate-300 px-3 py-2 font-bold text-slate-700 hover:bg-slate-50"
              >
                + Categoría
              </button>
              <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-semibold text-slate-600">
                {kpis.referencias} referencias
              </span>
              <button
                type="button"
                onClick={() => setModalArticulo(true)}
                className="rounded-lg bg-emerald-700 px-3 py-2 font-bold text-white hover:bg-emerald-800"
              >
                + Nuevo insumo
              </button>
            </div>
          )}
        </div>

        {pestañaActiva === 'articulos' && (
          <div className="space-y-3 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-extrabold text-slate-800">Catálogo maestro de materiales e insumos</h2>
              <input
                type="search"
                value={busqueda}
                onChange={(event) => setBusqueda(event.target.value)}
                placeholder="Buscar código, nombre o categoría…"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 sm:max-w-xs"
              />
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[1250px] text-left text-xs">
                <thead className="bg-slate-100 text-slate-700">
                  <tr>
                    <th className="p-2.5">Código de insumo</th>
                    <th className="p-2.5">Descripción técnica</th>
                    <th className="p-2.5">Categoría de insumo</th>
                    <th className="p-2.5">Centro / almacén</th>
                    <th className="p-2.5 text-right">Existencia libre / reservada</th>
                    <th className="p-2.5 text-right">Costo unitario valorado</th>
                    <th className="p-2.5">Cuenta contable de activo</th>
                    <th className="p-2.5">Centro de costos</th>
                    <th className="p-2.5">Reposición / estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {articulosFiltrados.map((articulo) => (
                    <tr key={articulo.id_articulo} className="hover:bg-slate-50">
                      <td className="p-2.5 font-mono font-bold text-slate-800">{articulo.codigo_sku}</td>
                      <td className="p-2.5">
                        <div className="font-semibold text-slate-800">{articulo.nombre}</div>
                        <div className="text-[10px] text-slate-500">{categorias.find((item) => item.codigo === articulo.categoria)?.nombre || articulo.categoria || 'Sin categoría'} · {articulo.unidad_medida}</div>
                      </td>
                      <td className="p-2.5">
                        <span className={`rounded-full border px-2 py-1 font-extrabold ${ETIQUETAS_MATERIAL[articulo.tipo_material_sap]?.color || 'border-slate-300 bg-slate-100 text-slate-700'}`}>
                          {ETIQUETAS_MATERIAL[articulo.tipo_material_sap]?.nombre || 'Categoría general'}
                        </span>
                      </td>
                      <td className="p-2.5">
                        <div className="font-semibold">{articulo.codigo_centro || '—'}</div>
                        <div className="text-[10px] text-slate-500">{articulo.almacen_fisico || '—'}</div>
                      </td>
                      <td className="p-2.5 text-right font-bold text-slate-800">
                        {Math.max(Number(articulo.stock_actual || 0) - Number(articulo.stock_reservado || 0), 0).toLocaleString('es-CO')} {articulo.unidad_medida}
                        <div className="text-[10px] font-normal text-slate-500">
                          Reservado: {Number(articulo.stock_reservado || 0).toLocaleString('es-CO')} {articulo.unidad_medida}
                        </div>
                        {Number(articulo.stock_cuarentena || 0) > 0 && (
                          <div className="text-[10px] font-semibold text-amber-700">
                            En cuarentena: {Number(articulo.stock_cuarentena).toLocaleString('es-CO')}
                          </div>
                        )}
                      </td>
                      <td className="p-2.5 text-right">
                        <div className="font-bold">$ {Number(articulo.precio_unitario_valorado || 0).toLocaleString('es-CO', { minimumFractionDigits: 2 })}</div>
                        <div className="text-[10px] text-slate-500">{ETIQUETAS_VALORACION[articulo.metodo_valoracion] || articulo.metodo_valoracion}</div>
                      </td>
                      <td className="p-2.5">{articulo.cuenta_contable_activo || '—'}</td>
                      <td className="p-2.5">{articulo.centro_costo_defecto || '—'}</td>
                      <td className="p-2.5">
                        {Number(articulo.punto_reorden || 0) > 0
                        && Number(articulo.stock_actual || 0) <= Number(articulo.punto_reorden || 0) ? (
                          <span className="rounded-full border border-amber-300 bg-amber-100 px-2 py-1 font-extrabold text-amber-800">
                            Reponer · {Number(articulo.punto_reorden || 0).toLocaleString('es-CO')}
                          </span>
                        ) : (
                          <span className="rounded-full border border-emerald-300 bg-emerald-100 px-2 py-1 font-bold text-emerald-800">Normal</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!articulosFiltrados.length && (
                    <tr><td colSpan="9" className="p-8 text-center text-slate-500">No hay insumos para mostrar.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {pestañaActiva === 'lotes' && (
          <div className="space-y-3 p-3">
            <div>
              <h2 className="font-extrabold text-slate-800">Trazabilidad de lotes y control de calidad</h2>
              <p className="mt-1 text-[11px] text-slate-500">
                Las recepciones ingresan en cuarentena; solo Calidad puede liberarlas para despacho a planta.
              </p>
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[1050px] text-left text-xs">
                <thead className="bg-slate-100 text-slate-700">
                  <tr>
                    <th className="p-2.5">Código de insumo / lote</th>
                    <th className="p-2.5">Colada / Certificado 3.1</th>
                    <th className="p-2.5 text-right">Cantidad</th>
                    <th className="p-2.5">Estado de calidad</th>
                    <th className="p-2.5">Decisión de Calidad</th>
                    <th className="p-2.5">Motivo y registro</th>
                    <th className="p-2.5">Auditoría</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {lotes.map((lote) => {
                    const draft = calidadDrafts[lote.id] || {};
                    return (
                      <tr key={lote.id} className="align-top hover:bg-slate-50">
                        <td className="p-2.5">
                          <div className="font-mono font-bold text-slate-800">{lote.codigo_material}</div>
                          <div className="text-[11px] text-slate-500">{lote.codigo_lote} · {lote.nombre_material}</div>
                        </td>
                        <td className="p-2.5">
                          <div>{lote.numero_colada || '—'}</div>
                          {lote.certificado_calidad_url && (
                            <a href={lote.certificado_calidad_url} target="_blank" rel="noreferrer" className="text-emerald-700 underline">
                              Ver certificado 3.1
                            </a>
                          )}
                        </td>
                        <td className="p-2.5 text-right font-semibold">
                          {Number(lote.stock_disponible || 0).toLocaleString()} · reserv. {Number(lote.stock_reservado || 0).toLocaleString()}
                        </td>
                        <td className="p-2.5">
                          <span className={`rounded-full border px-2 py-1 text-[10px] font-extrabold ${estadoBadge[lote.estado_calidad] || 'border-slate-300 bg-slate-100 text-slate-700'}`}>
                            {lote.estado_calidad}
                          </span>
                        </td>
                        <td className="space-y-2 p-2.5">
                          <select
                            value={draft.estado_calidad || ''}
                            onChange={(event) => cambiarDraftCalidad(lote.id, 'estado_calidad', event.target.value)}
                            className="w-full rounded border border-slate-300 p-1.5"
                          >
                            <option value="">Seleccionar estado</option>
                            <option value="CUARENTENA">CUARENTENA</option>
                            <option value="LIBERADO">LIBERADO</option>
                            <option value="RECHAZADO">RECHAZADO</option>
                          </select>
                          <button
                            type="button"
                            onClick={() => actualizarCalidad(lote)}
                            disabled={procesando}
                            className="w-full rounded bg-emerald-700 px-2 py-1.5 font-bold text-white hover:bg-emerald-800 disabled:opacity-50"
                          >
                            Registrar decisión
                          </button>
                        </td>
                        <td className="space-y-2 p-2.5">
                          <input
                            value={draft.motivo || ''}
                            onChange={(event) => cambiarDraftCalidad(lote.id, 'motivo', event.target.value)}
                            placeholder="Motivo obligatorio"
                            className="w-full rounded border border-slate-300 p-1.5"
                          />
                          <div className="text-[10px] text-slate-500">{mostrarFecha(lote.fecha_ingreso)}</div>
                        </td>
                        <td className="p-2.5">
                          <button
                            type="button"
                            onClick={() => consultarAuditoria(lote)}
                            className="rounded border border-slate-300 px-2 py-1 font-bold text-slate-700 hover:bg-slate-100"
                          >
                            Historial
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {!lotes.length && (
                    <tr><td colSpan="7" className="p-8 text-center text-slate-500">No hay lotes registrados.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {pestañaActiva === 'kardex' && (
          <div className="space-y-3 p-3">
            <div>
              <h2 className="font-extrabold text-slate-800">Documentos de inventario · Auditoría contable</h2>
              <p className="mt-1 text-[11px] text-slate-500">Valores en COP · entradas, consumos, traslados y bajas quedan registrados sin edición posterior.</p>
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[1250px] text-left text-xs">
                <thead className="bg-slate-100 text-slate-700">
                  <tr>
                    <th className="p-2.5">Fecha / documento</th>
                    <th className="p-2.5">Movimiento / código de insumo</th>
                    <th className="p-2.5">Centro / almacén</th>
                    <th className="p-2.5 text-right">Cantidad</th>
                    <th className="p-2.5 text-right">Costo unitario</th>
                    <th className="p-2.5 text-right">Costo total</th>
                    <th className="p-2.5">Cuenta débito</th>
                    <th className="p-2.5">Cuenta crédito</th>
                    <th className="p-2.5">Centro de costos / orden</th>
                    <th className="p-2.5">Responsable</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {movimientos.map((movimiento) => (
                    <tr key={movimiento.id_movimiento} className="hover:bg-slate-50">
                      <td className="whitespace-nowrap p-2.5">
                        <div>{mostrarFecha(movimiento.fecha_hora)}</div>
                        <div className="font-mono text-[10px] text-slate-500">{movimiento.numero_documento_material}</div>
                      </td>
                      <td className="p-2.5">
                        <span className="mr-1 rounded bg-slate-100 px-1.5 py-1 font-bold">
                          {ETIQUETAS_MOVIMIENTO[movimiento.clase_movimiento] || 'Movimiento de inventario'}
                        </span>
                        <span className="font-mono font-semibold">{movimiento.sku_codigo}</span>
                      </td>
                      <td className="p-2.5">
                        <div>{movimiento.codigo_centro}</div>
                        {movimiento.almacen_origen && <div className="text-[10px] text-slate-500">Origen: {movimiento.almacen_origen}</div>}
                        {movimiento.almacen_destino && <div className="text-[10px] text-emerald-700">Destino: {movimiento.almacen_destino}</div>}
                      </td>
                      <td className="p-2.5 text-right">{Number(movimiento.cantidad).toLocaleString('es-CO')}</td>
                      <td className="p-2.5 text-right">$ {Number(movimiento.costo_unitario).toLocaleString('es-CO', { minimumFractionDigits: 2 })}</td>
                      <td className="p-2.5 text-right font-semibold">$ {Number(movimiento.costo_total_movimiento).toLocaleString('es-CO', { minimumFractionDigits: 2 })}</td>
                      <td className="p-2.5">{movimiento.cuenta_debito}</td>
                      <td className="p-2.5">{movimiento.cuenta_credito}</td>
                      <td className="p-2.5">
                        <div>{movimiento.centro_costo_imputado || '—'}</div>
                        {movimiento.referencia_op && <div className="font-mono text-[10px] text-blue-700">OP: {movimiento.referencia_op}</div>}
                        {movimiento.referencia_externa && <div className="text-[10px] text-slate-500">{movimiento.referencia_externa}</div>}
                      </td>
                      <td className="p-2.5">{movimiento.registrado_por}</td>
                    </tr>
                  ))}
                  {!movimientos.length && (
                    <tr><td colSpan="10" className="p-8 text-center text-slate-500">No hay documentos  en el kárdex.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {pestañaActiva === 'mrp' && (
          <div className="space-y-3 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="font-extrabold text-slate-800">Requerimientos netos de materiales</h2>
                <p className="mt-1 text-[11px] text-slate-500">El cálculo utiliza existencias liberadas, retales y compras en tránsito.</p>
              </div>
              <button
                type="button"
                onClick={ejecutarMRP}
                disabled={procesando}
                className="rounded-lg bg-amber-600 px-3 py-2 font-bold text-white hover:bg-amber-700 disabled:opacity-50"
              >
                Ejecutar cálculo de necesidades netas
              </button>
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[850px] text-left text-xs">
                <thead className="bg-slate-100 text-slate-700">
                  <tr>
                    <th className="p-2.5">Material</th>
                    <th className="p-2.5 text-right">Demanda bruta</th>
                    <th className="p-2.5 text-right">Existencia liberada</th>
                    <th className="p-2.5 text-right">Retales</th>
                    <th className="p-2.5 text-right">En tránsito</th>
                    <th className="p-2.5 text-right">Requerimiento neto</th>
                    <th className="p-2.5">Requisición</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {requisicionesMRP.map((requisicion) => (
                    <tr key={requisicion.id_requisicion} className="hover:bg-slate-50">
                      <td className="p-2.5">
                        <div className="font-mono font-bold">{requisicion.codigo_material}</div>
                        <div className="text-[11px] text-slate-500">{requisicion.especificacion}</div>
                      </td>
                      <td className="p-2.5 text-right">{Number(requisicion.demanda_bruta).toLocaleString()}</td>
                      <td className="p-2.5 text-right">{Number(requisicion.stock_libre).toLocaleString()}</td>
                      <td className="p-2.5 text-right">{Number(requisicion.retales_disponibles).toLocaleString()}</td>
                      <td className="p-2.5 text-right">{Number(requisicion.compras_en_transito).toLocaleString()}</td>
                      <td className="p-2.5 text-right font-extrabold text-amber-700">{Number(requisicion.requerimiento_neto).toLocaleString()}</td>
                      <td className="p-2.5">{requisicion.numero_solicitud || 'Cubierto por inventario'}</td>
                    </tr>
                  ))}
                  {!requisicionesMRP.length && (
                    <tr><td colSpan="7" className="p-8 text-center text-slate-500">Ejecute el cálculo para consultar los requerimientos.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {modalArticulo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
          <form onSubmit={guardarArticulo} className="max-h-[90vh] w-full max-w-4xl space-y-4 overflow-y-auto rounded-xl border-t-4 border-emerald-600 bg-white p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h2 className="text-base font-extrabold text-slate-800">Catálogo de insumos</h2>
                <p className="mt-1 text-[11px] text-slate-500">Datos operativos, imputación contable, valoración y ubicación física.</p>
              </div>
              <button type="button" onClick={() => setModalArticulo(false)} className="text-lg font-bold text-slate-500">×</button>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="space-y-1 font-bold">Código de insumo *
                <input required maxLength="50" value={formArticulo.codigo_sku} onChange={(event) => setFormArticulo({ ...formArticulo, codigo_sku: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-mono font-normal" />
              </label>
              <label className="space-y-1 font-bold">Nombre del material *
                <input required maxLength="150" value={formArticulo.nombre} onChange={(event) => setFormArticulo({ ...formArticulo, nombre: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
              </label>
              <label className="space-y-1 font-bold">Categoría *
                <select required value={formArticulo.categoria} onChange={(event) => setFormArticulo({ ...formArticulo, categoria: event.target.value })} className="w-full rounded border border-slate-300 bg-white p-2 font-normal">
                  {categorias.map((categoria) => <option key={categoria.codigo} value={categoria.codigo}>{categoria.nombre}</option>)}
                </select>
              </label>
              <label className="space-y-1 font-bold">Categoría de insumo *
                <select
                  value={formArticulo.tipo_material_sap}
                  onChange={(event) => {
                    const presets = {
                      ROH: {
                        clase_valoracion: '3000-MP',
                        cuenta_contable_activo: '143505 - Inventario Materia Prima',
                        cuenta_contable_gasto: '710505 - Consumo de Materia Prima'
                      },
                      HALB: {
                        clase_valoracion: '3100-HALB',
                        cuenta_contable_activo: '143506 - Inventario Semielaborados',
                        cuenta_contable_gasto: '710505 - Consumo de Materia Prima'
                      },
                      FERT: {
                        clase_valoracion: '3200-FERT',
                        cuenta_contable_activo: '143515 - Inventario Producto Terminado',
                        cuenta_contable_gasto: '613595 - Costo de Ventas'
                      },
                      VERB: {
                        clase_valoracion: '4000-CONSUMIBLES',
                        cuenta_contable_activo: '143510 - Inventario Consumibles',
                        cuenta_contable_gasto: '510506 - Consumo de Insumos'
                      },
                      ERSA: {
                        clase_valoracion: '5000-REPUESTOS',
                        cuenta_contable_activo: '143520 - Inventario Repuestos',
                        cuenta_contable_gasto: '510520 - Consumo de Repuestos'
                      }
                    };
                    setFormArticulo({ ...formArticulo, tipo_material_sap: event.target.value, ...presets[event.target.value] });
                  }}
                  className="w-full rounded border border-slate-300 bg-white p-2 font-normal"
                >
                  <option value="ROH">Materia Prima Directa</option>
                  <option value="HALB">Producto Semielaborado</option>
                  <option value="FERT">Producto Terminado</option>
                  <option value="VERB">Consumible de Planta</option>
                  <option value="ERSA">Repuesto de Mantenimiento</option>
                </select>
              </label>
              <label className="space-y-1 font-bold">Unidad de medida *
                <select required value={formArticulo.unidad_medida} onChange={(event) => setFormArticulo({ ...formArticulo, unidad_medida: event.target.value })} className="w-full rounded border border-slate-300 bg-white p-2 font-normal">
                  <option value="kg">kg</option><option value="m">m</option><option value="mm">mm</option>
                  <option value="und">und</option><option value="L">L</option><option value="UND">Unidad (compatibilidad)</option>
                </select>
              </label>
              <label className="space-y-1 font-bold">Clase de valoración *
                <input required maxLength="50" value={formArticulo.clase_valoracion} onChange={(event) => setFormArticulo({ ...formArticulo, clase_valoracion: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
              </label>
              <label className="space-y-1 font-bold">Método de valoración *
                <select value={formArticulo.metodo_valoracion} onChange={(event) => setFormArticulo({ ...formArticulo, metodo_valoracion: event.target.value })} className="w-full rounded border border-slate-300 bg-white p-2 font-normal">
                  <option value="CPP">Costo promedio ponderado</option>
                  <option value="FIFO">Primero en entrar, primero en salir</option>
                  <option value="PRECIO_ESTANDAR">Precio estándar</option>
                </select>
              </label>
              <label className="space-y-1 font-bold">Precio estándar unitario (COP)
                <input type="number" min="0" step="0.0001" value={formArticulo.precio_unitario_valorado} onChange={(event) => setFormArticulo({ ...formArticulo, precio_unitario_valorado: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
              </label>
              <label className="space-y-1 font-bold">Cuenta de activo *
                <input required maxLength="100" value={formArticulo.cuenta_contable_activo} onChange={(event) => setFormArticulo({ ...formArticulo, cuenta_contable_activo: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
              </label>
              <label className="space-y-1 font-bold">Cuenta de gasto / variación *
                <input required maxLength="100" value={formArticulo.cuenta_contable_gasto} onChange={(event) => setFormArticulo({ ...formArticulo, cuenta_contable_gasto: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
              </label>
              <label className="space-y-1 font-bold">Cuenta transitoria de recepción *
                <input required maxLength="100" value={formArticulo.cuenta_contable_transitoria} onChange={(event) => setFormArticulo({ ...formArticulo, cuenta_contable_transitoria: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
              </label>
              <label className="space-y-1 font-bold">Centro de costo por defecto *
                <input required maxLength="50" value={formArticulo.centro_costo_defecto} onChange={(event) => setFormArticulo({ ...formArticulo, centro_costo_defecto: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-mono font-normal" />
              </label>
              <label className="space-y-1 font-bold">Centro operativo *
                <select required value={formArticulo.codigo_centro} onChange={(event) => seleccionarCentro(event.target.value)} className="w-full rounded border border-slate-300 bg-white p-2 font-normal">
                  <option value="">Seleccione centro</option>
                  {centros.map((centro) => <option key={centro.id_centro} value={centro.codigo_centro}>{centro.codigo_centro} · {centro.nombre_centro}</option>)}
                </select>
              </label>
              <label className="space-y-1 font-bold">Almacén asignado *
                <select required value={formArticulo.almacen_fisico} onChange={(event) => setFormArticulo({ ...formArticulo, almacen_fisico: event.target.value })} className="w-full rounded border border-slate-300 bg-white p-2 font-normal">
                  <option value="">Seleccione almacén</option>
                  {(centros.find((centro) => centro.codigo_centro === formArticulo.codigo_centro)?.almacenes || []).map((almacen) => (
                    <option key={almacen} value={almacen}>{almacen}</option>
                  ))}
                </select>
              </label>
              <label className="space-y-1 font-bold">Existencia de seguridad
                <input type="number" min="0" step="any" value={formArticulo.stock_seguridad} onChange={(event) => setFormArticulo({ ...formArticulo, stock_seguridad: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
              </label>
              <label className="space-y-1 font-bold">Punto de reorden
                <input type="number" min="0" step="any" value={formArticulo.punto_reorden} onChange={(event) => setFormArticulo({ ...formArticulo, punto_reorden: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
              </label>
              <label className="space-y-1 font-bold sm:col-span-2">Descripción técnica
                <textarea value={formArticulo.descripcion} onChange={(event) => setFormArticulo({ ...formArticulo, descripcion: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" rows="2" />
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t pt-3">
              <button type="button" onClick={() => setModalArticulo(false)} className="rounded bg-slate-100 px-4 py-2 font-bold text-slate-700">Cancelar</button>
              <button type="submit" disabled={procesando} className="rounded bg-emerald-700 px-4 py-2 font-bold text-white disabled:opacity-50">Guardar insumo</button>
            </div>
          </form>
        </div>
      )}

      {modalCategoria && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
          <form onSubmit={guardarCategoria} className="w-full max-w-md space-y-4 rounded-xl border-t-4 border-slate-700 bg-white p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b pb-3">
              <h2 className="text-base font-extrabold text-slate-800">Nueva categoría maestra</h2>
              <button type="button" onClick={() => setModalCategoria(false)} className="text-lg font-bold text-slate-500">×</button>
            </div>
            <label className="block space-y-1 font-bold">Código *
              <input required maxLength="50" value={formCategoria.codigo} onChange={(event) => setFormCategoria({ ...formCategoria, codigo: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-mono font-normal" />
            </label>
            <label className="block space-y-1 font-bold">Nombre *
              <input required maxLength="100" value={formCategoria.nombre} onChange={(event) => setFormCategoria({ ...formCategoria, nombre: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
            </label>
            <label className="block space-y-1 font-bold">Descripción
              <textarea value={formCategoria.descripcion} onChange={(event) => setFormCategoria({ ...formCategoria, descripcion: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" rows="2" />
            </label>
            <div className="flex justify-end gap-2 border-t pt-3">
              <button type="button" onClick={() => setModalCategoria(false)} className="rounded bg-slate-100 px-4 py-2 font-bold text-slate-700">Cancelar</button>
              <button type="submit" disabled={procesando} className="rounded bg-slate-800 px-4 py-2 font-bold text-white disabled:opacity-50">Guardar categoría</button>
            </div>
          </form>
        </div>
      )}

      {modalCentro && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
          <form onSubmit={guardarCentro} className="w-full max-w-lg space-y-4 rounded-xl border-t-4 border-amber-500 bg-white p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h2 className="text-base font-extrabold text-slate-800">Estructura de centros y almacenes</h2>
                <p className="mt-1 text-[11px] text-slate-500">Los códigos de almacén se separan por coma.</p>
              </div>
              <button type="button" onClick={() => setModalCentro(false)} className="text-lg font-bold text-slate-500">×</button>
            </div>
            <label className="block space-y-1 font-bold">Código de centro *
              <input required maxLength="50" value={formCentro.codigo_centro} onChange={(event) => setFormCentro({ ...formCentro, codigo_centro: event.target.value })} placeholder="CENTRO-02-PLANTA" className="w-full rounded border border-slate-300 p-2 font-mono font-normal" />
            </label>
            <label className="block space-y-1 font-bold">Nombre *
              <input required maxLength="150" value={formCentro.nombre_centro} onChange={(event) => setFormCentro({ ...formCentro, nombre_centro: event.target.value })} className="w-full rounded border border-slate-300 p-2 font-normal" />
            </label>
            <label className="block space-y-1 font-bold">Almacenes físicos *
              <textarea required value={formCentro.almacenes} onChange={(event) => setFormCentro({ ...formCentro, almacenes: event.target.value })} placeholder="BOD-MP-01, BOD-HERR-02, BOD-CUARENTENA-QM" className="w-full rounded border border-slate-300 p-2 font-mono font-normal" rows="3" />
            </label>
            <div className="flex justify-end gap-2 border-t pt-3">
              <button type="button" onClick={() => setModalCentro(false)} className="rounded bg-slate-100 px-4 py-2 font-bold text-slate-700">Cancelar</button>
              <button type="submit" disabled={procesando} className="rounded bg-amber-600 px-4 py-2 font-bold text-white disabled:opacity-50">Guardar centro</button>
            </div>
          </form>
        </div>
      )}

      {auditoriaLote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4">
          <section className="max-h-[85vh] w-full max-w-2xl space-y-3 overflow-y-auto rounded-xl border-t-4 border-amber-500 bg-white p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h2 className="text-base font-extrabold text-slate-800">Auditoría de calidad</h2>
                <p className="font-mono text-slate-500">{auditoriaLote.codigo_lote}</p>
              </div>
              <button type="button" onClick={() => setAuditoriaLote(null)} className="text-lg font-bold text-slate-500">×</button>
            </div>
            {auditoriaLote.registros.length ? auditoriaLote.registros.map((registro, indice) => (
              <article key={`${registro.creado_en}-${indice}`} className="rounded-lg border border-slate-200 p-3">
                <div className="flex flex-wrap justify-between gap-2 font-bold text-slate-800">
                  <span>{registro.estado_anterior || 'SIN ESTADO'} → {registro.estado_nuevo}</span>
                  <span className="text-[10px] font-normal text-slate-500">{mostrarFecha(registro.creado_en)}</span>
                </div>
                <p className="mt-1 text-slate-600">{registro.motivo}</p>
                <p className="mt-1 text-[10px] text-slate-500">Registrado por {registro.registrado_por}</p>
              </article>
            )) : (
              <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-slate-500">
                El lote no tiene cambios de calidad auditados.
              </p>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
