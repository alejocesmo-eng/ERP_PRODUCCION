// src/views/CalidadProductoView.jsx
import React, { useState, useEffect } from 'react';
import VisorPlanoModal from '../../components/VisorPlanoModal';

export default function CalidadProductoView() {
  const [ordenes, setOrdenes] = useState([]);
  const [ordenesAbiertas, setOrdenesAbiertas] = useState([]);
  const [cargandoAbiertas, setCargandoAbiertas] = useState(true);
  const [errorAbiertas, setErrorAbiertas] = useState('');
  const [ordenAbiertaSeleccionada, setOrdenAbiertaSeleccionada] = useState(null);
  const [planoSeleccionado, setPlanoSeleccionado] = useState(null);
  const [seccionActiva, setSeccionActiva] = useState('abiertas');
  const [loading, setLoading] = useState(true);
  const [ordenSeleccionada, setOrdenSeleccionada] = useState(null);
  const [busqueda, setBusqueda] = useState('');

  // Formularios de Inspección
  const [resultado, setResultado] = useState('APROBADO_DESPACHO');
  const [descripcionTratamiento, setDescripcionTratamiento] = useState('');
  const [piezasTratamiento, setPiezasTratamiento] = useState(0);
  const [emailProveedor, setEmailProveedor] = useState('');
  const [observaciones, setObservaciones] = useState('');
  const [fotos, setFotos] = useState([]);
  const [mensajeExito, setMensajeExito] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Cargar órdenes terminadas desde el backend
  useEffect(() => {
    cargarOrdenesTerminadas();
    cargarOrdenesAbiertas();
  }, []);

  const cargarOrdenesAbiertas = async () => {
    setCargandoAbiertas(true);
    setErrorAbiertas('');
    try {
      const response = await fetch('/api/v1/calidad/ordenes-abiertas');
      if (!response.ok) {
        throw new Error('Error al cargar las órdenes de producción.');
      }
      const data = await response.json();
      if (!Array.isArray(data)) {
        throw new Error('La respuesta de órdenes de producción no es válida.');
      }
      setOrdenesAbiertas(data.filter((op) => !['CERRADA', 'CANCELADA'].includes(op.estado_produccion)));
    } catch (err) {
      setErrorAbiertas(err.message || 'Error de conexión con el servidor backend.');
    } finally {
      setCargandoAbiertas(false);
    }
  };

  const cargarOrdenesTerminadas = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/calidad/ordenes-terminadas');
      if (response.ok) {
        const data = await response.json();
        setOrdenes(data);
      } else {
        setErrorMsg('Error al cargar órdenes de producción terminadas.');
      }
    } catch (err) {
      setErrorMsg('Error de conexión con el servidor backend.');
    } finally {
      setLoading(false);
    }
  };

  // Manejo de imágenes (Conversión a Base64)
  const handleFotoUpload = (e) => {
    const files = Array.from(e.target.files);
    files.forEach((file) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        setFotos((prev) => [...prev, reader.result]);
      };
      reader.readAsDataURL(file);
    });
  };

  const handleEliminarFoto = (index) => {
    setFotos(fotos.filter((_, i) => i !== index));
  };

  const handleSeleccionarOrden = (op) => {
    setOrdenSeleccionada(op);
    setResultado('APROBADO_DESPACHO');
    setDescripcionTratamiento('');
    setPiezasTratamiento(op.cantidad_terminada || 0);
    setEmailProveedor('');
    setObservaciones('');
    setFotos([]);
    setMensajeExito('');
    setErrorMsg('');
  };

  // Enviar formulario de inspección
  const handleSubmitInspeccion = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setMensajeExito('');

    if (fotos.length === 0) {
      setErrorMsg('Es obligatorio capturar/subir al menos un registro fotográfico de las piezas salientes.');
      return;
    }

    const payload = {
      codigo_op: ordenSeleccionada.codigo_op,
      codigo_plano: ordenSeleccionada.codigo_plano,
      inspector_nombre: "Inspector de Calidad", // Puede provenir de sesión/JWT
      resultado_inspeccion: resultado,
      requiere_tratamiento: resultado === 'APROBADO_TRATAMIENTO',
      descripcion_tratamiento: resultado === 'APROBADO_TRATAMIENTO' ? descripcionTratamiento : null,
      piezas_enviadas_tratamiento: resultado === 'APROBADO_TRATAMIENTO' ? parseInt(piezasTratamiento) : 0,
      proveedor_tratamiento_email: resultado === 'APROBADO_TRATAMIENTO' ? emailProveedor : null,
      registros_fotograficos: fotos,
      observaciones_inspector: observaciones
    };

    try {
      const response = await fetch('/api/v1/calidad/inspeccionar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        setMensajeExito('Inspección de calidad registrada correctamente.');
        setOrdenSeleccionada(null);
        cargarOrdenesTerminadas();
      } else {
        const errorData = await response.json();
        setErrorMsg(errorData.detail || 'Error al procesar la inspección.');
      }
    } catch (err) {
      setErrorMsg('Error de red al conectar con el backend.');
    }
  };

  const ordenesFiltradas = ordenes.filter(
    (item) =>
      item.codigo_op.toLowerCase().includes(busqueda.toLowerCase()) ||
      item.codigo_plano.toLowerCase().includes(busqueda.toLowerCase()) ||
      item.producto.toLowerCase().includes(busqueda.toLowerCase())
  );

  const ordenesAbiertasFiltradas = ordenesAbiertas.filter((op) => {
    const textoBusqueda = busqueda.toLowerCase();
    return [
      op.codigo_op,
      op.codigo_plano,
      op.detalle_producto,
      op.cliente_nombre,
      op.numero_pedido,
      op.estado_produccion
    ].some((valor) => String(valor || '').toLowerCase().includes(textoBusqueda));
  });

  return (
    <div className="p-6 bg-slate-50 min-h-screen space-y-6">
      {/* ENCABEZADO ESTANDARIZADO ISO 9001:2026 */}
      <header className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <span>🗜️</span> Calidad de Producto & Metrología (PM-05)
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Consulta de órdenes abiertas y recepción de órdenes terminadas para inspección.
          </p>
        </div>

        <div className="flex gap-2 bg-slate-100 p-1 rounded-xl border border-slate-200 self-stretch md:self-auto">
          <button
            type="button"
            onClick={() => setSeccionActiva('abiertas')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer ${
              seccionActiva === 'abiertas'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            📋 Órdenes abiertas ({ordenesAbiertas.length})
          </button>
          <button
            type="button"
            onClick={() => setSeccionActiva('inspeccion')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer ${
              seccionActiva === 'inspeccion'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            🔍 Inspección de producto
          </button>
        </div>
      </header>

      {seccionActiva === 'abiertas' ? (
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div>
            <h3 className="text-sm font-extrabold text-slate-800">Órdenes de producción abiertas</h3>
            <p className="mt-1 text-xs text-slate-500">Seleccione una orden para consultar sus datos y documentación técnica.</p>
          </div>
          {errorAbiertas && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-800">{errorAbiertas}</div>}
          <input
            type="text"
            placeholder="Buscar por OP, pedido, cliente, plano o producto..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          />
          {cargandoAbiertas ? (
            <p className="py-6 text-center text-xs font-semibold text-slate-500">Cargando órdenes abiertas...</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full border-collapse text-left text-xs">
                <thead className="bg-slate-100 text-[11px] font-extrabold uppercase text-slate-600">
                  <tr>
                    <th className="border-b border-slate-200 px-3 py-2.5">Código OP</th>
                    <th className="border-b border-slate-200 px-3 py-2.5">Pedido / Cliente</th>
                    <th className="border-b border-slate-200 px-3 py-2.5">Plano</th>
                    <th className="border-b border-slate-200 px-3 py-2.5">Producto</th>
                    <th className="border-b border-slate-200 px-3 py-2.5">Cantidad</th>
                    <th className="border-b border-slate-200 px-3 py-2.5">Estado / Avance</th>
                    <th className="border-b border-slate-200 px-3 py-2.5">Acción</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {ordenesAbiertasFiltradas.length > 0 ? ordenesAbiertasFiltradas.map((op) => (
                    <tr key={op.codigo_op} className="transition hover:bg-slate-50">
                      <td className="whitespace-nowrap px-3 py-2.5 font-extrabold text-slate-800">{op.codigo_op}</td>
                      <td className="px-3 py-2.5"><span className="font-bold text-slate-700">{op.numero_pedido || '-'}</span><br /><span className="text-slate-500">{op.cliente_nombre || '-'}</span></td>
                      <td className="px-3 py-2.5 font-semibold text-blue-800">{op.codigo_plano || '-'}</td>
                      <td className="px-3 py-2.5">{op.detalle_producto || '-'}</td>
                      <td className="px-3 py-2.5">{op.cantidad ?? 0} UND</td>
                      <td className="px-3 py-2.5"><span className="font-bold text-slate-700">{op.estado_produccion || '-'}</span><br /><span className="text-slate-500">{op.porcentaje_avance ?? 0}%</span></td>
                      <td className="px-3 py-2.5">
                        <button
                          type="button"
                          onClick={() => setOrdenAbiertaSeleccionada(op)}
                          className="whitespace-nowrap rounded-lg bg-blue-600 px-3 py-1.5 text-[11px] font-extrabold text-white shadow-sm transition hover:bg-blue-700"
                        >
                          Ver detalles
                        </button>
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan="7" className="px-3 py-8 text-center text-xs font-semibold text-slate-500">
                        {ordenesAbiertas.length ? 'No hay órdenes que coincidan con la búsqueda.' : 'No hay órdenes abiertas.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : (
        <>
          <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div>
              <h3 className="text-sm font-extrabold text-slate-800">Inspección y Calidad de Producto Saliente</h3>
              <p className="mt-1 text-xs text-slate-500">Recepción de Órdenes Terminadas para Aprobación, Despacho o Tratamiento Térmico.</p>
            </div>
            {mensajeExito && <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs font-semibold text-emerald-800">{mensajeExito}</div>}
            {errorMsg && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs font-semibold text-red-800">{errorMsg}</div>}

            {!ordenSeleccionada ? (
              <div className="space-y-4">
                <input
                  type="text"
                  placeholder="Buscar por # Orden, Plano o Pieza..."
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />

                {loading ? (
                  <p className="py-6 text-center text-xs font-semibold text-slate-500">Cargando órdenes terminadas...</p>
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-slate-200">
                    <table className="w-full border-collapse text-left text-xs">
                      <thead className="bg-slate-100 text-[11px] font-extrabold uppercase text-slate-600">
                        <tr>
                          <th className="border-b border-slate-200 px-3 py-2.5">Código OP</th>
                          <th className="border-b border-slate-200 px-3 py-2.5">Plano / Pieza</th>
                          <th className="border-b border-slate-200 px-3 py-2.5">Descripción</th>
                          <th className="border-b border-slate-200 px-3 py-2.5">Cant. Terminada</th>
                          <th className="border-b border-slate-200 px-3 py-2.5">Acciones</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {ordenesFiltradas.length > 0 ? (
                          ordenesFiltradas.map((op) => (
                            <tr key={op.codigo_op} className="transition hover:bg-slate-50">
                              <td className="px-3 py-2.5 font-extrabold text-slate-800">{op.codigo_op}</td>
                              <td className="px-3 py-2.5 font-semibold text-blue-800">{op.codigo_plano}</td>
                              <td className="px-3 py-2.5">{op.producto}</td>
                              <td className="px-3 py-2.5">{op.cantidad_terminada} UND</td>
                              <td className="px-3 py-2.5">
                                <button
                                  type="button"
                                  onClick={() => handleSeleccionarOrden(op)}
                                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-[11px] font-extrabold text-white shadow-sm transition hover:bg-blue-700"
                                >
                                  Inspeccionar
                                </button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="5" className="px-3 py-8 text-center text-xs font-semibold text-slate-500">No hay órdenes pendientes por inspección.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <button
                  type="button"
                  onClick={() => setOrdenSeleccionada(null)}
                  className="rounded-lg bg-slate-100 px-3 py-1.5 text-[11px] font-bold text-slate-600 transition hover:bg-slate-200"
                >
                  ← Volver a la lista
                </button>

                <h3 className="text-sm font-extrabold text-slate-800">Inspeccionando Orden: {ordenSeleccionada.codigo_op} ({ordenSeleccionada.producto})</h3>
                
                {/* Visor de Plano PDF */}
                <div className="rounded-lg border border-slate-200 bg-slate-100 p-3 text-xs">
                  <strong className="font-bold text-slate-700">Plano Técnico PDF: </strong>
                  {ordenSeleccionada.url_plano_pdf ? (
                    <a href={ordenSeleccionada.url_plano_pdf} target="_blank" rel="noopener noreferrer" className="font-bold text-blue-700 underline hover:text-blue-800">
                      Abrir Plano {ordenSeleccionada.codigo_plano} (PDF)
                    </a>
                  ) : (
                    <span>No disponible</span>
                  )}
                </div>

                <form onSubmit={handleSubmitInspeccion}>
                  <div className="mb-4">
                    <label className="mb-1.5 block text-xs font-bold text-slate-700">Resultado de la Inspección:</label>
                    <select
                      value={resultado}
                      onChange={(e) => setResultado(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    >
                      <option value="APROBADO_DESPACHO">Aprobar para Despacho al Cliente (Notifica a Jefe de Producción)</option>
                      <option value="APROBADO_TRATAMIENTO">Aprobar para Tratamiento Térmico (Envía correo a Proveedor)</option>
                      <option value="RECHAZADO">Rechazar (Generar RNC)</option>
                    </select>
                  </div>

                  {/* Campos Condicionales de Tratamiento Térmico */}
                  {resultado === 'APROBADO_TRATAMIENTO' && (
                    <div className="mb-4 space-y-3 rounded-xl border border-amber-300 bg-amber-100 p-4 text-amber-900">
                      <h4 className="text-xs font-extrabold">Detalles de Tratamiento Térmico</h4>
                      
                      <div>
                        <label className="mb-1.5 block text-xs font-bold">Descripción del Tratamiento (ej. Temple, Revenido, Cementación):</label>
                        <textarea
                          rows="3"
                          value={descripcionTratamiento}
                          onChange={(e) => setDescripcionTratamiento(e.target.value)}
                          required
                          className="w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100"
                        />
                      </div>

                      <div>
                        <label className="mb-1.5 block text-xs font-bold">Piezas Enviadas:</label>
                        <input
                          type="number"
                          value={piezasTratamiento}
                          onChange={(e) => setPiezasTratamiento(e.target.value)}
                          required
                          min="1"
                          className="w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100"
                        />
                      </div>

                      <div>
                        <label className="mb-1.5 block text-xs font-bold">Correo del Proveedor de Tratamiento Térmico:</label>
                        <input
                          type="email"
                          value={emailProveedor}
                          onChange={(e) => setEmailProveedor(e.target.value)}
                          placeholder="proveedor@tratamientos.com"
                          required
                          className="w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-100"
                        />
                      </div>
                    </div>
                  )}

                  {/* Registro Fotográfico de Salida */}
                  <div className="mb-4">
                    <label className="mb-1.5 block text-xs font-bold text-slate-700">Registro Fotográfico de Salida (Obligatorio):</label>
                    <input type="file" accept="image/*" multiple onChange={handleFotoUpload} className="block w-full cursor-pointer rounded-lg border border-slate-300 bg-white text-xs text-slate-600 file:mr-3 file:rounded-l-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-[11px] file:font-bold file:text-slate-700 hover:file:bg-slate-200" />
                    
                    <div className="mt-3 flex flex-wrap gap-3">
                      {fotos.map((img, idx) => (
                        <div key={idx} className="relative">
                          <img src={img} alt={`Salida ${idx}`} className="h-24 w-24 rounded-lg border border-slate-200 object-cover" />
                          <button
                            type="button"
                            onClick={() => handleEliminarFoto(idx)}
                            className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full bg-red-600 text-sm font-extrabold text-white shadow-sm hover:bg-red-700"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mb-4">
                    <label className="mb-1.5 block text-xs font-bold text-slate-700">Observaciones Generales:</label>
                    <textarea
                      rows="3"
                      value={observaciones}
                      onChange={(e) => setObservaciones(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                    />
                  </div>

                  <button
                    type="submit"
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-extrabold text-white shadow-sm transition hover:bg-emerald-700"
                  >
                    Guardar Inspección
                  </button>
                </form>
              </div>
            )}
          </section>
        </>
      )}

      {ordenAbiertaSeleccionada && (
        <div role="dialog" aria-modal="true" aria-labelledby="detalle-orden-titulo" className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-xl border-t-4 border-blue-600 bg-white p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 id="detalle-orden-titulo" className="text-sm font-extrabold text-slate-800">Detalle de OP {ordenAbiertaSeleccionada.codigo_op}</h3>
              <button type="button" onClick={() => setOrdenAbiertaSeleccionada(null)} aria-label="Cerrar detalles" className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-200">✕</button>
            </div>
            <div className="my-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <p><strong className="text-slate-500">Pedido:</strong> {ordenAbiertaSeleccionada.numero_pedido || '-'}</p>
              <p><strong className="text-slate-500">Cliente:</strong> {ordenAbiertaSeleccionada.cliente_nombre || '-'}</p>
              <p><strong className="text-slate-500">Ubicación:</strong> {ordenAbiertaSeleccionada.ubicacion_cliente || '-'}</p>
              <p><strong className="text-slate-500">Producto:</strong> {ordenAbiertaSeleccionada.detalle_producto || '-'}</p>
              <p><strong className="text-slate-500">Cantidad:</strong> {ordenAbiertaSeleccionada.cantidad ?? 0} UND</p>
              <p><strong className="text-slate-500">Estado:</strong> {ordenAbiertaSeleccionada.estado_produccion || '-'}</p>
              <p><strong className="text-slate-500">Avance:</strong> {ordenAbiertaSeleccionada.porcentaje_avance ?? 0}%</p>
              <p><strong className="text-slate-500">Fecha compromiso:</strong> {ordenAbiertaSeleccionada.fecha_compromiso || '-'}</p>
              <p><strong className="text-slate-500">Entrega a producción:</strong> {ordenAbiertaSeleccionada.fecha_entrega_produccion || '-'}</p>
              <p><strong className="text-slate-500">Plano / revisión:</strong> {ordenAbiertaSeleccionada.codigo_plano || '-'} / {ordenAbiertaSeleccionada.revision || '-'}</p>
              <p><strong className="text-slate-500">Estado de diseño:</strong> {ordenAbiertaSeleccionada.estado_diseno || '-'}</p>
              <p><strong className="text-slate-500">Material:</strong> {ordenAbiertaSeleccionada.material_requerido || '-'}</p>
              <p><strong className="text-slate-500">Unidad de planta:</strong> {ordenAbiertaSeleccionada.unidad_planta || '-'}</p>
              <p><strong className="text-slate-500">Dibujante:</strong> {ordenAbiertaSeleccionada.dibujante_asignado || '-'}</p>
            </div>
            <div className="space-y-2 text-xs">
              <p><strong className="text-slate-500">Requisitos del cliente:</strong> {ordenAbiertaSeleccionada.requisitos_cliente || '-'}</p>
              <p><strong className="text-slate-500">Observaciones:</strong> {ordenAbiertaSeleccionada.observaciones || '-'}</p>
            </div>
            {Array.isArray(ordenAbiertaSeleccionada.productos_componentes) && ordenAbiertaSeleccionada.productos_componentes.length > 0 && (
              <div className="mt-5 space-y-2">
                <h4 className="text-xs font-extrabold text-slate-800">Productos y componentes del pedido</h4>
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="w-full border-collapse text-left text-xs">
                    <thead className="bg-slate-100 text-[11px] font-extrabold uppercase text-slate-600"><tr>
                      <th className="border-b border-slate-200 px-3 py-2">Producto</th>
                      <th className="border-b border-slate-200 px-3 py-2">Plano</th>
                      <th className="border-b border-slate-200 px-3 py-2">Cantidad</th>
                      <th className="border-b border-slate-200 px-3 py-2">Estado</th>
                    </tr></thead>
                    <tbody className="divide-y divide-slate-100">{ordenAbiertaSeleccionada.productos_componentes.map((componente) => (
                      <tr key={componente.id_proyecto} className="hover:bg-slate-50">
                        <td className="px-3 py-2">{componente.detalle_producto || '-'}</td>
                        <td className="px-3 py-2">{componente.codigo_plano || '-'}</td>
                        <td className="px-3 py-2">{componente.cantidad ?? 0}</td>
                        <td className="px-3 py-2">{componente.estado_produccion || '-'}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              </div>
            )}
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                disabled={!ordenAbiertaSeleccionada.archivo_url}
                onClick={() => setPlanoSeleccionado(ordenAbiertaSeleccionada)}
                className="rounded-lg bg-blue-600 px-3 py-2 text-[11px] font-extrabold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
              >
                Ver plano PDF
              </button>
              <button type="button" onClick={() => setOrdenAbiertaSeleccionada(null)} className="rounded-lg bg-slate-100 px-3 py-2 text-[11px] font-bold text-slate-600 transition hover:bg-slate-200">Cerrar</button>
            </div>
            {!ordenAbiertaSeleccionada.archivo_url && <p role="status" className="mt-2 text-right text-[11px] text-slate-500">Esta orden no tiene un PDF de plano cargado.</p>}
          </div>
        </div>
      )}
      <VisorPlanoModal
        abierto={Boolean(planoSeleccionado)}
        onClose={() => setPlanoSeleccionado(null)}
        archivoUrl={planoSeleccionado?.archivo_url}
        codigoOp={planoSeleccionado?.codigo_op}
        codigoPlano={planoSeleccionado?.codigo_plano}
      />
    </div>
  );
}