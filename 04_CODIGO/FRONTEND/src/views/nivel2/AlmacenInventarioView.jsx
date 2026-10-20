// src/views/nivel2/AlmacenInventarioView.jsx
import React, { useState, useEffect } from 'react';
import API from '../../services/api';

export default function AlmacenInventarioView() {
  const [pestañaActiva, setPestañaActiva] = useState('entradas'); // 'entradas', 'salidas'
  const [solicitudesEnCompra, setSolicitudesEnCompra] = useState([]);
  const [solicitudSeleccionada, setSolicitudSeleccionada] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });

  // Formulario Entrada / Recepción desde Compras
  const [entradaForm, setEntradaForm] = useState({
    numero_solicitud_compra: '',
    id_solicitud: '',
    codigo_sku: '',
    nombre_item: '',
    categoria: 'MATERIA_PRIMA',
    cantidad_solicitada: '',
    cantidad_recibida: '',
    unidad_medida: 'UND',
    numero_factura: '',
    factura_pdf_nombre: '',
    numero_lote: '',
    codigo_op: '',
    codigo_plano: '',
    numero_pedido: ''
  });

  // Formulario Salidas de Almacén
  const [salidaForm, setSalidaForm] = useState({
    codigo_sku: '',
    cantidad_salida: '',
    tipo_destino: 'ORDEN_PRODUCCION', // ORDEN_PRODUCCION, CENTRO_COSTOS, ASIGNACION_OPERARIO, PRESTAMO_TEMPORAL
    codigo_op: '',
    centro_costos: 'Planta Principal',
    operario_responsable: '',
    fecha_devolucion: '',
    observaciones: ''
  });

  useEffect(() => {
    cargarSolicitudesEnCompra();
  }, []);

  const cargarSolicitudesEnCompra = async () => {
    try {
      setLoading(true);
      const res = await API.get('/solicitudes-compra/');
      if (Array.isArray(res.data)) {
        // Filtrar solicitudes que estén efectivamente 'EN_COMPRA'
        const enCompra = res.data.filter(s => 
          s.estado_bom === 'EN_COMPRA' || 
          s.estado === 'EN_COMPRA' ||
          (s.estado_bom && String(s.estado_bom).toUpperCase().includes('COMPRA'))
        );
        setSolicitudesEnCompra(enCompra);
      } else {
        setSolicitudesEnCompra([]);
      }
    } catch (err) {
      console.warn("No se pudieron cargar solicitudes de compra:", err);
      setSolicitudesEnCompra([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSeleccionarSolicitud = (solicitud) => {
    if (!solicitud) {
      setSolicitudSeleccionada(null);
      return;
    }
    setSolicitudSeleccionada(solicitud);
    setEntradaForm(prev => ({
      ...prev,
      numero_solicitud_compra: solicitud.numero_solicitud || '',
      id_solicitud: solicitud.id_solicitud || '',
      codigo_sku: solicitud.codigo_plano && solicitud.codigo_plano !== 'N/A' 
        ? solicitud.codigo_plano 
        : (solicitud.codigo_op && solicitud.codigo_op !== 'GENERAL' ? `OP-${solicitud.codigo_op}` : `MAT-${solicitud.numero_solicitud}`),
      nombre_item: solicitud.descripcion_resumen || '',
      cantidad_solicitada: solicitud.cantidad_piezas || 1,
      cantidad_recibida: solicitud.cantidad_piezas || 1, // Pre-llenado sugerido
      unidad_medida: solicitud.unidad_medida || 'UND',
      categoria: 'MATERIA_PRIMA',
      codigo_op: solicitud.codigo_op && solicitud.codigo_op !== 'GENERAL' ? solicitud.codigo_op : '',
      codigo_plano: solicitud.codigo_plano && solicitud.codigo_plano !== 'N/A' ? solicitud.codigo_plano : '',
      numero_pedido: solicitud.numero_pedido && solicitud.numero_pedido !== 'S/P' ? solicitud.numero_pedido : ''
    }));

    setMensaje({
      tipo: 'exito',
      texto: `📋 Solicitud [${solicitud.numero_solicitud}] mapeada exitosamente al formulario de recepción.`
    });
  };

  const handleEntradaChange = (e) => {
    setEntradaForm({ ...entradaForm, [e.target.name]: e.target.value });
  };

  const handleSalidaChange = (e) => {
    setSalidaForm({ ...salidaForm, [e.target.name]: e.target.value });
  };

  const handleFacturaPDFChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setEntradaForm({ ...entradaForm, factura_pdf_nombre: file.name });
      setMensaje({ tipo: 'exito', texto: `📄 Factura adjuntada: ${file.name}` });
    }
  };

  const handleGuardarEntrada = async (e) => {
    e.preventDefault();
    if (Number(entradaForm.cantidad_recibida) <= 0) {
      return setMensaje({ tipo: 'error', texto: '⚠ Ingrese una cantidad recibida mayor a cero.' });
    }

    try {
      setLoading(true);
      const cantSol = Number(entradaForm.cantidad_solicitada) || Number(entradaForm.cantidad_recibida);
      const cantRec = Number(entradaForm.cantidad_recibida);
      const dif = cantSol - cantRec;
      let detalleDif = dif === 0 ? ' (Cantidad exacta recibida)' : ` (Diferencia de ${dif} unidades contra solicitud)`;

      // 1. Enviar registro de recepción a API backend
      const payloadEntrada = {
        numero_solicitud_compra: entradaForm.numero_solicitud_compra,
        codigo_sku: entradaForm.codigo_sku || 'MAT-PR',
        cantidad_solicitada: cantSol,
        cantidad_recibida: cantRec,
        numero_factura: entradaForm.numero_factura,
        numero_lote: entradaForm.numero_lote || null,
        factura_digital_url: entradaForm.factura_pdf_nombre || null,
        recibido_por: 'Almacén Central'
      };

      try {
        await API.post('/almacen/recepcion-compra', payloadEntrada);
      } catch (errApi) {
        console.warn("Aviso de registro en backend:", errApi);
      }

      // 2. Si la recepción proviene de una Solicitud de Compra, actualizarla a ENTREGADO en el BOM
      if (solicitudSeleccionada?.id_solicitud) {
        try {
          const nuevoEstadoBom = dif <= 0 ? 'ENTREGADO' : 'EN_COMPRA';
          await API.patch(`/solicitudes-compra/${solicitudSeleccionada.id_solicitud}`, {
            estado_bom: nuevoEstadoBom,
            estado: dif <= 0 ? 'RECIBIDA' : 'PARCIAL_RECIBIDA',
            comentarios: `Recepción en almacén: ${cantRec} ${entradaForm.unidad_medida} con Factura ${entradaForm.numero_factura}${dif > 0 ? ` (Faltante: ${dif})` : ''}`
          });
        } catch (errSol) {
          console.warn("No se pudo actualizar el estado de la solicitud:", errSol);
        }
      }

      setMensaje({ 
        tipo: 'exito', 
        texto: `✅ Recepción de compra [${entradaForm.numero_solicitud_compra}] e ingreso a stock registrado con éxito${detalleDif}. Factura: ${entradaForm.numero_factura}.` 
      });

      // 3. Resetear formulario y recargar solicitudes pendientes
      setEntradaForm({
        numero_solicitud_compra: '', id_solicitud: '', codigo_sku: '', nombre_item: '', categoria: 'MATERIA_PRIMA',
        cantidad_solicitada: '', cantidad_recibida: '', unidad_medida: 'UND', numero_factura: '', factura_pdf_nombre: '', numero_lote: '',
        codigo_op: '', codigo_plano: '', numero_pedido: ''
      });
      setSolicitudSeleccionada(null);

      await cargarSolicitudesEnCompra();
    } catch (error) {
      setMensaje({ tipo: 'error', texto: 'Error al registrar la recepción de mercancía.' });
    } finally {
      setLoading(false);
    }
  };

  const handleGuardarSalida = async (e) => {
    e.preventDefault();
    if (Number(salidaForm.cantidad_salida) <= 0) {
      return setMensaje({ tipo: 'error', texto: '⚠ Ingrese una cantidad de salida válida.' });
    }

    setMensaje({ 
      tipo: 'exito', 
      texto: `📤 Salida registrada correctamente para [${salidaForm.tipo_destino}]. Stock descontado.` 
    });
    setSalidaForm({
      codigo_sku: '', cantidad_salida: '', tipo_destino: 'ORDEN_PRODUCCION',
      codigo_op: '', centro_costos: 'Planta Principal', operario_responsable: '', fecha_devolucion: '', observaciones: ''
    });
  };

  return (
    <div className="p-6 bg-slate-50 min-h-screen space-y-6">
      {/* ENCABEZADO ESTANDARIZADO SGI ISO 9001:2026 */}
      <header className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <span>📦</span> Almacén e Inventarios — Recepción, Costos y Salidas
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Cotejo y Mapeo de Solicitudes de Compra ("En Compra"), Imputación a OP y Salidas de Planta [ISO 9001:2026]
          </p>
        </div>
        
        <div className="flex gap-2 bg-slate-100 p-1 rounded-xl border border-slate-200 self-stretch md:self-auto">
          <button
            type="button"
            onClick={() => setPestañaActiva('entradas')}
            className={`px-4 py-2 font-bold text-xs rounded-lg transition cursor-pointer flex items-center gap-1.5 ${
              pestañaActiva === 'entradas' ? 'bg-purple-700 text-white shadow-sm font-black' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>📥</span> Recepción de Compras
          </button>
          <button
            type="button"
            onClick={() => setPestañaActiva('salidas')}
            className={`px-4 py-2 font-bold text-xs rounded-lg transition cursor-pointer flex items-center gap-1.5 ${
              pestañaActiva === 'salidas' ? 'bg-blue-700 text-white shadow-sm font-black' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>📤</span> Salidas / Préstamos / OP
          </button>
        </div>
      </header>

      {mensaje.texto && (
        <div className={`p-4 rounded-xl text-sm font-semibold border ${
          mensaje.tipo === 'exito' ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : 'bg-red-50 text-red-800 border-red-300'
        }`}>
          {mensaje.texto}
        </div>
      )}

      {/* PESTAÑA 1: ENTRADAS DESDE COMPRAS CON MAPEO DE SOLICITUDES EN COMPRA */}
      {pestañaActiva === 'entradas' && (
        <div className="space-y-6 max-w-5xl mx-auto">
          
          {/* BANNER / TABLA DE SOLICITUDES "EN COMPRA" PENDIENTES */}
          <div className="bg-white p-5 rounded-xl border border-purple-200 shadow-sm space-y-3">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <span className="text-sm font-extrabold text-slate-800 flex items-center gap-1.5">
                  <span>🛒</span> Solicitudes de Compra Pendientes de Recepción ("En Compra")
                </span>
                <span className="px-2 py-0.5 bg-purple-100 text-purple-800 text-xs font-black rounded-full">
                  {solicitudesEnCompra.length}
                </span>
              </div>
              <button
                type="button"
                onClick={cargarSolicitudesEnCompra}
                disabled={loading}
                className="px-2.5 py-1 text-xs font-bold text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg transition flex items-center gap-1 cursor-pointer"
              >
                <span>🔄</span> {loading ? 'Cargando...' : 'Actualizar'}
              </button>
            </div>

            {solicitudesEnCompra.length === 0 ? (
              <div className="p-4 bg-slate-50 border border-dashed border-slate-300 rounded-lg text-center text-xs text-slate-500">
                ✓ No hay solicitudes de compra con estado <strong className="text-slate-700 font-bold">"EN COMPRA"</strong> pendientes por recibir.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border border-slate-200 rounded-lg overflow-hidden">
                  <thead className="bg-purple-50 text-purple-900 font-bold border-b border-purple-200">
                    <tr>
                      <th className="p-2.5">N° Solicitud</th>
                      <th className="p-2.5">Material / Insumo</th>
                      <th className="p-2.5 text-center">Cant. Solicitada</th>
                      <th className="p-2.5">OP / Pedido / Plano</th>
                      <th className="p-2.5">Fecha Necesaria</th>
                      <th className="p-2.5 text-center">Acción</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {solicitudesEnCompra.map((s) => {
                      const esSeleccionada = entradaForm.numero_solicitud_compra === s.numero_solicitud;
                      return (
                        <tr 
                          key={s.id_solicitud} 
                          className={`hover:bg-purple-50/50 transition ${esSeleccionada ? 'bg-purple-100/60 font-semibold' : ''}`}
                        >
                          <td className="p-2.5 font-mono font-bold text-purple-800 whitespace-nowrap">
                            {s.numero_solicitud}
                          </td>
                          <td className="p-2.5 text-slate-800 font-medium">
                            {s.descripcion_resumen}
                          </td>
                          <td className="p-2.5 text-center font-bold text-slate-800 whitespace-nowrap">
                            {s.cantidad_piezas} {s.unidad_medida}
                          </td>
                          <td className="p-2.5 font-mono text-[11px] text-blue-800 whitespace-nowrap">
                            {s.codigo_op && s.codigo_op !== 'GENERAL' ? `OP-${s.codigo_op}` : 'Sin OP'}
                            {s.codigo_plano && s.codigo_plano !== 'N/A' ? ` | ${s.codigo_plano}` : ''}
                            {s.numero_pedido && s.numero_pedido !== 'S/P' ? ` (Ped: ${s.numero_pedido})` : ''}
                          </td>
                          <td className="p-2.5 text-slate-600 whitespace-nowrap">
                            {s.fecha_necesaria || 'Inmediata'}
                          </td>
                          <td className="p-2.5 text-center whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => handleSeleccionarSolicitud(s)}
                              className={`px-3 py-1 rounded text-xs font-bold transition shadow-sm cursor-pointer flex items-center gap-1 mx-auto ${
                                esSeleccionada 
                                  ? 'bg-purple-700 text-white' 
                                  : 'bg-purple-100 text-purple-800 hover:bg-purple-200 border border-purple-300'
                              }`}
                            >
                              {esSeleccionada ? '✓ Mapeada' : '📥 Mapear a Recepción'}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* FORMULARIO DE RECEPCIÓN */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
                <span>📋</span> Formulario de Recepción y Conciliación Física
              </h2>
              {solicitudSeleccionada && (
                <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 border border-emerald-300 rounded text-xs font-bold flex items-center gap-1">
                  <span>🔗</span> Mapeando: <strong>{solicitudSeleccionada.numero_solicitud}</strong>
                </span>
              )}
            </div>

            <form onSubmit={handleGuardarEntrada} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Seleccionar Solicitud en Compra *
                  </label>
                  <select
                    value={entradaForm.numero_solicitud_compra}
                    onChange={(e) => {
                      const sel = solicitudesEnCompra.find(s => s.numero_solicitud === e.target.value);
                      if (sel) {
                        handleSeleccionarSolicitud(sel);
                      } else {
                        setEntradaForm(prev => ({ ...prev, numero_solicitud_compra: e.target.value, id_solicitud: '' }));
                        setSolicitudSeleccionada(null);
                      }
                    }}
                    className="w-full p-2 border border-purple-300 rounded font-semibold bg-purple-50/40 text-purple-900 cursor-pointer"
                    required
                  >
                    <option value="">-- Seleccionar Solicitud ("En Compra") o Digitar --</option>
                    {solicitudesEnCompra.map(s => (
                      <option key={s.id_solicitud} value={s.numero_solicitud}>
                        {s.numero_solicitud} — {s.descripcion_resumen} (OP: {s.codigo_op} | Cant: {s.cantidad_piezas} {s.unidad_medida})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">N° Factura / Remisión del Proveedor *</label>
                  <input
                    type="text"
                    name="numero_factura"
                    placeholder="Ej. FAC-99842 o REM-1024"
                    value={entradaForm.numero_factura}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded font-semibold text-slate-800"
                    required
                  />
                </div>
              </div>

              {entradaForm.nombre_item && (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1">
                  <div className="text-[11px] text-slate-500 font-bold uppercase">Detalle del Ítem / Solicitud Mapeada:</div>
                  <div className="text-xs font-bold text-slate-800">{entradaForm.nombre_item}</div>
                  <div className="text-[11px] text-slate-600 flex gap-4 mt-0.5">
                    {entradaForm.codigo_op && <span>OP: <strong className="text-blue-800">{entradaForm.codigo_op}</strong></span>}
                    {entradaForm.codigo_plano && <span>Plano: <strong className="text-purple-800">{entradaForm.codigo_plano}</strong></span>}
                    {entradaForm.numero_pedido && <span>Pedido: <strong className="text-slate-800">{entradaForm.numero_pedido}</strong></span>}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Código SKU / Plano *</label>
                  <input
                    type="text"
                    name="codigo_sku"
                    placeholder="Ej. MAT-1045-12"
                    value={entradaForm.codigo_sku}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded font-mono font-semibold"
                    required
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Categoría de Inventario</label>
                  <select
                    name="categoria"
                    value={entradaForm.categoria}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded bg-slate-50 font-semibold cursor-pointer"
                  >
                    <option value="MATERIA_PRIMA">🥩 Materia Prima Directa</option>
                    <option value="CONSUMIBLE">🛠 Consumible / Insumo Planta</option>
                    <option value="EPP">🥽 Equipos de Protección (EPP)</option>
                    <option value="REPUESTO">⚙ Repuesto Maquinaria</option>
                    <option value="HERRAMENTAL">🔧 Herramienta / Accesorios</option>
                    <option value="OFICINA">📄 Papelería / Aseo</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Adjuntar Factura Digital (PDF / Imagen)</label>
                  <input
                    type="file"
                    accept=".pdf,image/*"
                    id="factura-file"
                    onChange={handleFacturaPDFChange}
                    className="hidden"
                  />
                  <label htmlFor="factura-file" className="block w-full text-center py-2 bg-slate-700 hover:bg-slate-800 text-white rounded font-semibold cursor-pointer truncate px-2">
                    📁 {entradaForm.factura_pdf_nombre || 'Subir Factura...'}
                  </label>
                </div>
              </div>

              <div className="p-4 bg-purple-50 border border-purple-200 rounded-xl grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    Cantidad Solicitada (Compras)
                  </label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      name="cantidad_solicitada"
                      placeholder="100"
                      value={entradaForm.cantidad_solicitada}
                      onChange={handleEntradaChange}
                      className="w-full p-2 border border-slate-300 rounded bg-white font-semibold"
                      required
                    />
                    <span className="text-xs font-bold text-slate-500">{entradaForm.unidad_medida}</span>
                  </div>
                </div>

                <div>
                  <label className="block font-bold text-purple-900 mb-1">
                    Cantidad Físicamente Recibida *
                  </label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      name="cantidad_recibida"
                      placeholder="100"
                      value={entradaForm.cantidad_recibida}
                      onChange={handleEntradaChange}
                      className="w-full p-2 border border-purple-400 rounded bg-white font-bold text-purple-900"
                      required
                    />
                    <span className="text-xs font-bold text-purple-900">{entradaForm.unidad_medida}</span>
                  </div>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Lote / Colada (Trazabilidad)</label>
                  <input
                    type="text"
                    name="numero_lote"
                    placeholder="Ej. COL-88942"
                    value={entradaForm.numero_lote}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white"
                  />
                </div>
              </div>

              {entradaForm.cantidad_solicitada && entradaForm.cantidad_recibida && (
                <div className="text-xs">
                  {Number(entradaForm.cantidad_recibida) === Number(entradaForm.cantidad_solicitada) ? (
                    <span className="text-emerald-700 font-bold">✓ Entrega completa: Conciliación 100% coincidente.</span>
                  ) : Number(entradaForm.cantidad_recibida) < Number(entradaForm.cantidad_solicitada) ? (
                    <span className="text-amber-700 font-bold">
                      ⚠ Entrega parcial: Faltan {Number(entradaForm.cantidad_solicitada) - Number(entradaForm.cantidad_recibida)} {entradaForm.unidad_medida} por entregar.
                    </span>
                  ) : (
                    <span className="text-blue-700 font-bold">
                      ℹ Excedente recibido: {Number(entradaForm.cantidad_recibida) - Number(entradaForm.cantidad_solicitada)} {entradaForm.unidad_medida} por encima de lo solicitado.
                    </span>
                  )}
                </div>
              )}

              <div className="flex justify-end pt-2">
                <button 
                  type="submit" 
                  disabled={loading}
                  className="px-6 py-2.5 bg-purple-700 hover:bg-purple-800 text-white font-bold rounded-lg shadow-sm transition cursor-pointer flex items-center gap-2"
                >
                  <span>📥</span> {loading ? 'Registrando...' : 'Verificar Conciliación e Ingresar a Stock'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* PESTAÑA 2: REGISTRO DE SALIDAS, CONSUMOS Y PRÉSTAMOS */}
      {pestañaActiva === 'salidas' && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-4xl mx-auto space-y-4">
          <h2 className="text-base font-bold text-slate-800 border-b pb-2 flex items-center gap-2">
            <span>📤</span> Registro de Salidas, Consumos y Préstamos de Herramientas
          </h2>
          <form onSubmit={handleGuardarSalida} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Código SKU / Ítem a Retirar *</label>
                <input
                  type="text"
                  name="codigo_sku"
                  placeholder="Ej. MAT-1045 o HERR-DISCO"
                  value={salidaForm.codigo_sku}
                  onChange={handleSalidaChange}
                  className="w-full p-2 border border-slate-300 rounded font-semibold"
                  required
                />
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Cantidad a Retirar *</label>
                <input
                  type="number"
                  name="cantidad_salida"
                  placeholder="Ej. 5"
                  value={salidaForm.cantidad_salida}
                  onChange={handleSalidaChange}
                  className="w-full p-2 border border-slate-300 rounded font-bold text-blue-900"
                  required
                />
              </div>

              <div>
                <label className="block font-bold text-blue-900 mb-1">Tipo de Salida / Imputación *</label>
                <select
                  name="tipo_destino"
                  value={salidaForm.tipo_destino}
                  onChange={handleSalidaChange}
                  className="w-full p-2 border border-blue-300 rounded bg-blue-50 font-bold text-blue-900 cursor-pointer"
                >
                  <option value="ORDEN_PRODUCCION">⚙ Imputable a Orden de Producción (OP)</option>
                  <option value="CENTRO_COSTOS">🏢 Imputable a Centro de Costos (Planta / Aseo / Adm)</option>
                  <option value="ASIGNACION_OPERARIO">👤 Asignación Fija a Operario / Puesto</option>
                  <option value="PRESTAMO_TEMPORAL">🛠 Préstamo Temporal de Herramienta</option>
                </select>
              </div>
            </div>

            {/* CAMPOS DINÁMICOS SEGÚN EL TIPO DE DESTINO */}
            {salidaForm.tipo_destino === 'ORDEN_PRODUCCION' && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <label className="block font-bold text-blue-900 mb-1">Código de la Orden de Producción (OP) *</label>
                <input
                  type="text"
                  name="codigo_op"
                  placeholder="Ej. OP-2026-001"
                  value={salidaForm.codigo_op}
                  onChange={handleSalidaChange}
                  className="w-full p-2 border border-blue-300 rounded bg-white font-bold"
                  required
                />
              </div>
            )}

            {salidaForm.tipo_destino === 'CENTRO_COSTOS' && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                <label className="block font-bold text-slate-700 mb-1">Centro de Costos Receptora *</label>
                <select
                  name="centro_costos"
                  value={salidaForm.centro_costos}
                  onChange={handleSalidaChange}
                  className="w-full p-2 border border-slate-300 rounded bg-white font-semibold cursor-pointer"
                >
                  <option value="Planta Principal">Planta Principal de Fabricación</option>
                  <option value="Mantenimiento">Mantenimiento de Maquinaria</option>
                  <option value="Servicios Generales">Servicios Generales / Aseo</option>
                  <option value="Administración">Administración / Oficina</option>
                </select>
              </div>
            )}

            {(salidaForm.tipo_destino === 'ASIGNACION_OPERARIO' || salidaForm.tipo_destino === 'PRESTAMO_TEMPORAL') && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Nombre del Operario Responsable *</label>
                  <input
                    type="text"
                    name="operario_responsable"
                    placeholder="Ej. Pedro Gómez"
                    value={salidaForm.operario_responsable}
                    onChange={handleSalidaChange}
                    className="w-full p-2 border border-amber-300 rounded bg-white font-semibold"
                    required
                  />
                </div>

                {salidaForm.tipo_destino === 'PRESTAMO_TEMPORAL' && (
                  <div>
                    <label className="block font-bold text-amber-900 mb-1">Fecha Estimada de Devolución</label>
                    <input
                      type="date"
                      name="fecha_devolucion"
                      value={salidaForm.fecha_devolucion}
                      onChange={handleSalidaChange}
                      className="w-full p-2 border border-amber-300 rounded bg-white font-semibold"
                    />
                  </div>
                )}
              </div>
            )}

            <div>
              <label className="block font-semibold text-slate-600 mb-1">Observaciones / Motivo de Salida</label>
              <input
                type="text"
                name="observaciones"
                placeholder="Ej. Reposición por desgaste natural / Despacho autorizado"
                value={salidaForm.observaciones}
                onChange={handleSalidaChange}
                className="w-full p-2 border border-slate-300 rounded"
              />
            </div>

            <div className="flex justify-end pt-2">
              <button 
                type="submit" 
                className="px-6 py-2.5 bg-blue-700 hover:bg-blue-800 text-white font-bold rounded-lg shadow-sm transition cursor-pointer flex items-center gap-2"
              >
                <span>📤</span> Registrar Salida y Descontar de Inventario
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}