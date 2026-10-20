import React, { useState, useEffect } from 'react';
import API from '../../services/api';

export default function ProduccionView() {
  const [ordenesPlanta, setOrdenesPlanta] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });
  const [busqueda, setBusqueda] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('TODOS');

  // Modal 1: Registro de Avance de OP + Desglose Multi-Pieza / Multi-Plano
  const [modalEjecucionAbierto, setModalEjecucionAbierto] = useState(false);
  const [opSeleccionada, setOpSeleccionada] = useState(null);

  // Modal 2: Expediente Completo del Pedido Agrupador (SAP B1)
  const [modalPedidoAbierto, setModalPedidoAbierto] = useState(false);
  const [pedidoSeleccionado, setPedidoSeleccionado] = useState(null);

  // Modal 3: Hoja de Vida e Histórico del Cliente
  const [modalClienteAbierto, setModalClienteAbierto] = useState(false);
  const [clienteSeleccionado, setClienteSeleccionado] = useState(null);

  const [formEjecucion, setFormEjecucion] = useState({
    estado: 'EN_PRODUCCION',
    porcentaje_avance: 0,
    observaciones: ''
  });

  useEffect(() => {
    cargarOrdenesPlanta();
  }, []);

  const cargarOrdenesPlanta = async () => {
    try {
      setLoading(true);
      const res = await API.get('/ordenes/');
      setOrdenesPlanta(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      try {
        const fetchRes = await fetch('http://127.0.0.1:8000/api/v1/ordenes/');
        const data = await fetchRes.json();
        setOrdenesPlanta(Array.isArray(data) ? data : []);
      } catch (err) {
        setMensaje({ tipo: 'error', texto: 'No se pudo conectar con la API de Producción.' });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAbrirEjecucion = (op) => {
    setOpSeleccionada(op);
    setFormEjecucion({
      estado: op.estado_produccion || op.estado || 'LIBERADA_PRODUCCION',
      porcentaje_avance: op.porcentaje_avance || 0,
      observaciones: op.observaciones || ''
    });
    setModalEjecucionAbierto(true);
  };

  const handleAbrirExpedientePedido = (e, numeroPedido) => {
    e.stopPropagation();
    const ordenesDelPedido = ordenesPlanta.filter(o => o.numero_pedido === numeroPedido);
    const principal = ordenesDelPedido[0] || {};
    
    setPedidoSeleccionado({
      numero_pedido: numeroPedido,
      ordenes: ordenesDelPedido.length > 0 ? ordenesDelPedido : [ordenesPlanta.find(o => o.numero_pedido === numeroPedido) || {}],
      principal: principal
    });
    setModalPedidoAbierto(true);
  };

  const handleAbrirHistoricoCliente = (e, clienteNombre) => {
    e.stopPropagation();
    const trabajosCliente = ordenesPlanta.filter(o => (o.cliente_nombre || '').toLowerCase() === (clienteNombre || '').toLowerCase());
    const primerRegistro = trabajosCliente[0] || {};

    setClienteSeleccionado({
      nombre: clienteNombre,
      contacto: primerRegistro.contacto_nombre || 'Ing. Encargado de Compras',
      telefono: primerRegistro.contacto_telefono || '+57 (601) 800-0000',
      email: primerRegistro.contacto_email || 'contacto@cliente.com',
      ubicacion: primerRegistro.ubicacion_cliente || 'Planta Principal',
      historial: trabajosCliente
    });
    setModalClienteAbierto(true);
  };

  const handleGuardarCambioEstado = async (e) => {
    e.preventDefault();
    setMensaje({ tipo: '', texto: '' });

    try {
      setLoading(true);
      const payload = {
        estado: formEjecucion.estado,
        estado_produccion: formEjecucion.estado,
        porcentaje_avance: parseFloat(formEjecucion.porcentaje_avance),
        observaciones: formEjecucion.observaciones
      };

      await API.patch(`/ordenes/${opSeleccionada.id_proyecto}`, payload);
      setMensaje({ tipo: 'exito', texto: `✅ Orden N° OP-${opSeleccionada.codigo_op} actualizada.` });
      setModalEjecucionAbierto(false);
      cargarOrdenesPlanta();
    } catch (error) {
      setMensaje({ tipo: 'error', texto: 'Error al actualizar el estado de la OP.' });
    } finally {
      setLoading(false);
    }
  };

  const liberadas = ordenesPlanta.filter(o => (o.estado_produccion || o.estado) === 'LIBERADA_PRODUCCION').length;
  const enProduccion = ordenesPlanta.filter(o => (o.estado_produccion || o.estado) === 'EN_PRODUCCION').length;
  const enInspeccion = ordenesPlanta.filter(o => (o.estado_produccion || o.estado) === 'EN_INSPECCION').length;
  const cerradas = ordenesPlanta.filter(o => (o.estado_produccion || o.estado) === 'CERRADA').length;

  const ordenesFiltradas = ordenesPlanta.filter((op) => {
    const termino = busqueda.toLowerCase().trim();
    const codigoOP = (op.codigo_op || '').toLowerCase();
    const pedido = (op.numero_pedido || '').toLowerCase();
    const cliente = (op.cliente_nombre || '').toLowerCase();
    const coincideBusqueda = codigoOP.includes(termino) || pedido.includes(termino) || cliente.includes(termino);

    if (filtroEstado === 'TODOS') return coincideBusqueda;
    const est = op.estado_produccion || op.estado;
    return coincideBusqueda && est === filtroEstado;
  });

  return (
    <div className="p-6 bg-slate-50 min-h-screen space-y-6">
      {/* HEADER PRINCIPAL */}
      <header className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <span>🏭</span> Producción y Planta (PM-03)
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Control de Órdenes de Producción (OP), Verificación de Planos Técnicos y Trazabilidad de Piezas [ISO 9001:2026 / SAP B1]
          </p>
        </div>
        <button 
          onClick={cargarOrdenesPlanta}
          className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg border border-slate-300 transition flex items-center gap-1.5"
        >
          <span>🔄</span> Recargar Planta
        </button>
      </header>

      {/* NOTIFICACIONES */}
      {mensaje.texto && (
        <div className={`p-4 rounded-lg text-sm font-semibold border ${
          mensaje.tipo === 'exito' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-red-50 text-red-800 border-red-200'
        }`}>
          {mensaje.texto}
        </div>
      )}

      {/* TARJETAS DE INDICADORES CLICKEABLES (FILTROS) */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <button
          type="button"
          onClick={() => setFiltroEstado(filtroEstado === 'LIBERADA_PRODUCCION' ? 'TODOS' : 'LIBERADA_PRODUCCION')}
          className={`p-4 rounded-xl border text-left transition-all shadow-sm ${
            filtroEstado === 'LIBERADA_PRODUCCION'
              ? 'bg-blue-50/90 border-blue-500 ring-2 ring-blue-400/30 scale-[1.02]'
              : 'bg-white border-slate-200 hover:bg-slate-50'
          }`}
        >
          <span className="text-xs font-bold text-blue-600 uppercase tracking-wide">Liberadas a Planta</span>
          <p className="text-2xl font-bold text-blue-700 mt-1">{liberadas}</p>
          <span className="text-[10px] text-blue-600 font-semibold mt-1 block">🔍 Haz clic para filtrar</span>
        </button>

        <button
          type="button"
          onClick={() => setFiltroEstado(filtroEstado === 'EN_PRODUCCION' ? 'TODOS' : 'EN_PRODUCCION')}
          className={`p-4 rounded-xl border text-left transition-all shadow-sm ${
            filtroEstado === 'EN_PRODUCCION'
              ? 'bg-purple-50/90 border-purple-500 ring-2 ring-purple-400/30 scale-[1.02]'
              : 'bg-white border-slate-200 hover:bg-slate-50'
          }`}
        >
          <span className="text-xs font-bold text-purple-600 uppercase tracking-wide">En Mecanizado / Fabricación</span>
          <p className="text-2xl font-bold text-purple-700 mt-1">{enProduccion}</p>
          <span className="text-[10px] text-purple-600 font-semibold mt-1 block">🔍 Haz clic para filtrar</span>
        </button>

        <button
          type="button"
          onClick={() => setFiltroEstado(filtroEstado === 'EN_INSPECCION' ? 'TODOS' : 'EN_INSPECCION')}
          className={`p-4 rounded-xl border text-left transition-all shadow-sm ${
            filtroEstado === 'EN_INSPECCION'
              ? 'bg-amber-50/90 border-amber-500 ring-2 ring-amber-400/30 scale-[1.02]'
              : 'bg-white border-slate-200 hover:bg-slate-50'
          }`}
        >
          <span className="text-xs font-bold text-amber-600 uppercase tracking-wide">En Inspección Calidad</span>
          <p className="text-2xl font-bold text-amber-700 mt-1">{enInspeccion}</p>
          <span className="text-[10px] text-amber-600 font-semibold mt-1 block">🔍 Haz clic para filtrar</span>
        </button>

        <button
          type="button"
          onClick={() => setFiltroEstado(filtroEstado === 'CERRADA' ? 'TODOS' : 'CERRADA')}
          className={`p-4 rounded-xl border text-left transition-all shadow-sm ${
            filtroEstado === 'CERRADA'
              ? 'bg-emerald-50/90 border-emerald-500 ring-2 ring-emerald-400/30 scale-[1.02]'
              : 'bg-white border-slate-200 hover:bg-slate-50'
          }`}
        >
          <span className="text-xs font-bold text-emerald-600 uppercase tracking-wide">Cerradas / Listas</span>
          <p className="text-2xl font-bold text-emerald-700 mt-1">{cerradas}</p>
          <span className="text-[10px] text-emerald-600 font-semibold mt-1 block">🔍 Haz clic para filtrar</span>
        </button>
      </div>

      {/* TABLA PRINCIPAL DE PRODUCCIÓN */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 border-b pb-3">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-700">Tablero de Control de Planta (OP)</h2>
            {filtroEstado !== 'TODOS' && (
              <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-bold rounded uppercase">
                Filtro Activo: {filtroEstado}
              </span>
            )}
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full md:w-auto">
            <select
              value={filtroEstado}
              onChange={(e) => setFiltroEstado(e.target.value)}
              className="p-2 border border-slate-300 rounded-lg text-xs bg-slate-50 font-medium text-slate-700 focus:bg-white focus:outline-none"
            >
              <option value="TODOS">Todos los Estados</option>
              <option value="LIBERADA_PRODUCCION">LIBERADAS</option>
              <option value="EN_PRODUCCION">EN PRODUCCIÓN</option>
              <option value="EN_INSPECCION">EN INSPECCIÓN</option>
              <option value="CERRADA">CERRADAS</option>
            </select>

            <input
              type="text"
              placeholder="🔍 Buscar por OP, Pedido o Cliente..."
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              className="w-full sm:w-72 p-2 border border-slate-300 rounded-lg text-xs bg-slate-50 focus:bg-white focus:outline-none"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-600 border-collapse">
            <thead>
              <tr className="bg-slate-100 text-slate-700 font-bold uppercase border-b border-slate-200">
                <th className="p-3">Código OP</th>
                <th className="p-3">N° Pedido Agrupador</th>
                <th className="p-3">Cliente / Producto</th>
                <th className="p-3">Fecha Compromiso</th>
                <th className="p-3">Planos Técnicos & Adjuntos</th>
                <th className="p-3">Unidad & Insumos BOM</th>
                <th className="p-3">Avance (%)</th>
                <th className="p-3">Estado Ejecución</th>
                <th className="p-3 text-center">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {ordenesFiltradas.length === 0 ? (
                <tr>
                  <td colSpan="9" className="p-6 text-center text-slate-400 font-medium">
                    {loading ? 'Cargando órdenes de producción...' : 'No hay órdenes en planta que coincidan con la búsqueda.'}
                  </td>
                </tr>
              ) : (
                ordenesFiltradas.map((op) => (
                  <tr key={op.id_proyecto || op.codigo_op} className="hover:bg-slate-50 transition">
                    <td className="p-3 font-bold whitespace-nowrap">
                      <span className="text-blue-700 font-mono text-sm bg-blue-50 px-2 py-1 rounded border border-blue-200 inline-block">
                        ⚙ OP-{op.codigo_op}
                      </span>
                    </td>

                    <td className="p-3 font-bold whitespace-nowrap">
                      <button
                        type="button"
                        onClick={(e) => handleAbrirExpedientePedido(e, op.numero_pedido || 'PED-2026-088')}
                        className="text-purple-700 hover:text-purple-900 underline bg-purple-50 hover:bg-purple-100 px-2 py-1 rounded font-mono border border-purple-200 transition"
                      >
                        📋 {op.numero_pedido || 'STOCK'}
                      </button>
                    </td>

                    <td className="p-3">
                      <button
                        type="button"
                        onClick={(e) => handleAbrirHistoricoCliente(e, op.cliente_nombre || 'Ecopetrol S.A.')}
                        className="font-bold text-blue-800 hover:text-blue-900 hover:underline text-left block"
                      >
                        🏢 {op.cliente_nombre || 'Cliente General'}
                      </button>
                      <div className="text-[10px] text-slate-500 font-medium">{op.detalle_producto || op.nombre_proyecto || 'Pieza Mecanizada'} ({op.cantidad || 1} UND)</div>
                    </td>

                    <td className="p-3 font-semibold text-slate-700 whitespace-nowrap bg-amber-50/40 px-2 rounded border border-amber-200/40">
                      📅 {op.fecha_compromiso || '2026-11-15'}
                    </td>

                    {/* COLUMNA MULTI-PLANO CON ENLACES A PDFS */}
                    <td className="p-3 font-mono text-slate-700 whitespace-nowrap">
                      <div className="font-bold">📄 {op.codigo_plano || 'PLN-MEC-001'} ({op.revision || 'REV-01'})</div>
                      {op.archivo_url ? (
                        <a 
                          href={op.archivo_url} 
                          target="_blank" 
                          rel="noreferrer" 
                          className="text-[10px] text-blue-600 hover:text-blue-800 underline font-semibold flex items-center gap-1 mt-0.5"
                        >
                          🔗 Ver PDF Adjunto
                        </a>
                      ) : (
                        <span className="text-[10px] text-slate-400 italic block mt-0.5">Sin PDF subido</span>
                      )}
                    </td>

                    <td className="p-3">
                      <div className="font-bold text-blue-900">🏭 {op.unidad_planta || 'Mecanizados'}</div>
                      <div className="text-[10px] text-slate-600 font-semibold">{op.material_requerido || 'Acero ASTM A105'}</div>
                      <div className="mt-1">
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                          op.estado_compra === 'ENTREGADO_ALMACEN' || op.codigo_op === '3002534' ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' :
                          op.estado_compra === 'COMPRADO' || op.codigo_op === '1002395' ? 'bg-purple-100 text-purple-800 border border-purple-300' :
                          'bg-amber-100 text-amber-800 border border-amber-300'
                        }`}>
                          📦 {op.estado_compra || (op.codigo_op === '3002534' ? 'DISPONIBLE EN ALMACÉN' : op.codigo_op === '1002395' ? 'ORDEN COMPRA EMITIDA' : 'SOLICITUD COMPRA (PR)')}
                        </span>
                      </div>
                    </td>

                    <td className="p-3">
                      <div className="w-24 bg-slate-200 rounded-full h-2 overflow-hidden">
                        <div 
                          className="bg-blue-600 h-full rounded-full transition-all"
                          style={{ width: `${op.porcentaje_avance || 0}%` }}
                        ></div>
                      </div>
                      <span className="text-[10px] font-bold text-slate-500 mt-1 block">
                        {op.porcentaje_avance || 0}%
                      </span>
                    </td>

                    <td className="p-3 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        (op.estado_produccion || op.estado) === 'EN_PRODUCCION' ? 'bg-purple-100 text-purple-900 border border-purple-300' :
                        (op.estado_produccion || op.estado) === 'EN_INSPECCION' ? 'bg-amber-100 text-amber-900 border border-amber-300' :
                        (op.estado_produccion || op.estado) === 'CERRADA' ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-blue-100 text-blue-800 border border-blue-300'
                      }`}>
                        {op.estado_produccion || op.estado || 'LIBERADA_PRODUCCION'}
                      </span>
                    </td>

                    <td className="p-3 text-center whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => handleAbrirEjecucion(op)}
                        className="px-3 py-1.5 font-semibold rounded text-[11px] bg-slate-800 text-white hover:bg-slate-900 transition shadow-sm"
                      >
                        ⚙ Ver OP y Avance
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* MODAL 1: REGISTRO DE AVANCE Y MATRIZ MULTI-PIEZA / MULTI-PLANO DE LA OP */}
      {modalEjecucionAbierto && opSeleccionada && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full p-6 space-y-4 max-h-[92vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-bold rounded uppercase">
                  Control de Ejecución e Inspección de OP [ISO 9001:2026 / SAP B1]
                </span>
                <h3 className="text-xl font-bold text-slate-800 mt-1">
                  Orden de Producción: <span className="text-blue-700 font-mono">OP-{opSeleccionada.codigo_op}</span>
                </h3>
              </div>
              <button onClick={() => setModalEjecucionAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg">✕</button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div className="space-y-1">
                <p><strong>Cliente:</strong> {opSeleccionada.cliente_nombre || 'General'}</p>
                <p><strong>N° Pedido Agrupador:</strong> <span className="font-mono text-purple-700 font-bold">{opSeleccionada.numero_pedido || 'STOCK'}</span></p>
                <p><strong>Fecha Compromiso Cliente:</strong> <span className="font-bold text-slate-800">📅 {opSeleccionada.fecha_compromiso || '2026-11-15'}</span></p>
                <p><strong>Unidad de Planta:</strong> 🏭 {opSeleccionada.unidad_planta || 'Mecanizados'}</p>
              </div>

              <div className="space-y-1 sm:border-l sm:pl-3 border-slate-200">
                <p><strong>Dibujante Encargado:</strong> 👤 {opSeleccionada.dibujante_asignado || 'Ing. Carlos Ruiz'}</p>
                <p><strong>Material Principal (BOM):</strong> {opSeleccionada.material_requerido || 'Acero ASTM A105'}</p>
                <p><strong>Estado Insumos:</strong> <span className="font-bold text-emerald-700">📦 {opSeleccionada.estado_compra || 'DISPONIBLE EN ALMACÉN'}</span></p>
              </div>
            </div>

            {/* SECCIÓN MULTI-PIEZA: LISTA DE PLANOS Y COMPONENTES EN ESTA OP */}
            <div className="space-y-2">
              <h4 className="font-bold text-slate-700 text-xs flex items-center gap-1.5">
                <span>📄</span> Desglose de Piezas, Planos Técnicos y Archivos Adjuntos
              </h4>
              <div className="border border-slate-200 rounded-lg overflow-hidden text-xs">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-slate-100 font-bold text-slate-700 border-b">
                    <tr>
                      <th className="p-2.5">Código Plano</th>
                      <th className="p-2.5 w-20">Revisión</th>
                      <th className="p-2.5">Detalle Pieza / Componente</th>
                      <th className="p-2.5 w-20 text-center">Cantidad</th>
                      <th className="p-2.5">Materia Prima (BOM)</th>
                      <th className="p-2.5 text-center">Plano PDF</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 text-slate-600">
                    {(opSeleccionada.productos_componentes || [
                      {
                        codigo_plano: opSeleccionada.codigo_plano || 'PLN-MEC-001',
                        revision: opSeleccionada.revision || 'REV-01',
                        detalle_producto: opSeleccionada.detalle_producto || 'Pieza Mecanizada',
                        cantidad: opSeleccionada.cantidad || 1,
                        material_requerido: opSeleccionada.material_requerido || 'Acero ASTM A105',
                        archivo_url: opSeleccionada.archivo_url
                      }
                    ]).map((comp, idx) => (
                      <tr key={idx} className="hover:bg-slate-50 transition">
                        <td className="p-2.5 font-mono font-bold text-blue-700">{comp.codigo_plano || 'PLN-MEC-001'}</td>
                        <td className="p-2.5 font-bold text-slate-700">{comp.revision || 'REV-01'}</td>
                        <td className="p-2.5 font-medium text-slate-800">{comp.detalle_producto || comp.nombre_proyecto || 'Pieza'}</td>
                        <td className="p-2.5 text-center font-bold text-slate-800">{comp.cantidad || 1} UND</td>
                        <td className="p-2.5 text-slate-700">{comp.material_requerido || 'Acero ASTM A105'}</td>
                        <td className="p-2.5 text-center">
                          {comp.archivo_url || opSeleccionada.archivo_url ? (
                            <a 
                              href={comp.archivo_url || opSeleccionada.archivo_url} 
                              target="_blank" 
                              rel="noreferrer" 
                              className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded text-[10px] transition inline-block"
                            >
                              📄 Ver PDF
                            </a>
                          ) : (
                            <span className="text-slate-400 italic text-[10px]">Sin PDF</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* FORMULARIO DE CAMBIO DE ESTADO Y REGISTRO DE AVANCE */}
            <form onSubmit={handleGuardarCambioEstado} className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-3 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Estado de Avance en Planta *</label>
                  <select
                    value={formEjecucion.estado}
                    onChange={(e) => setFormEjecucion({ ...formEjecucion, estado: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-bold text-slate-800 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                    required
                  >
                    <option value="LIBERADA_PRODUCCION">LIBERADA PRODUCCIÓN</option>
                    <option value="EN_PRODUCCION">EN PRODUCCIÓN / MECANIZADO</option>
                    <option value="EN_INSPECCION">EN INSPECCIÓN DE CALIDAD</option>
                    <option value="CERRADA">CERRADA / PRODUCTO TERMINADO</option>
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Porcentaje de Avance Físico (%) *</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={formEjecucion.porcentaje_avance}
                    onChange={(e) => setFormEjecucion({ ...formEjecucion, porcentaje_avance: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-bold text-slate-800 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Observaciones / Registro de Avance de Fabricación</label>
                <textarea
                  rows="3"
                  value={formEjecucion.observaciones}
                  onChange={(e) => setFormEjecucion({ ...formEjecucion, observaciones: e.target.value })}
                  placeholder="Escriba novedades de mecanizado, tolerancias o tiempos de entrega..."
                  className="w-full p-2 border border-slate-300 rounded bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                ></textarea>
              </div>

              <div className="flex justify-end gap-2 border-t pt-3">
                <button
                  type="button"
                  onClick={() => setModalEjecucionAbierto(false)}
                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded transition"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded transition shadow-sm"
                >
                  {loading ? 'Guardando...' : '💾 Guardar Estado OP'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: EXPEDIENTE PEDIDO AGRUPADOR */}
      {modalPedidoAbierto && pedidoSeleccionado && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2 py-0.5 bg-purple-100 text-purple-800 text-[10px] font-bold rounded uppercase">
                  Expediente Agrupador Comercial [SAP B1]
                </span>
                <h3 className="text-xl font-bold text-slate-800 mt-1">
                  Pedido Comercial N°: <span className="text-purple-700 font-mono">{pedidoSeleccionado.numero_pedido}</span>
                </h3>
              </div>
              <button onClick={() => setModalPedidoAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg">✕</button>
            </div>

            <div className="text-xs bg-slate-50 p-3 rounded border border-slate-200 grid grid-cols-2 gap-2">
              <p><strong>Cliente:</strong> {pedidoSeleccionado.principal?.cliente_nombre || 'Ecopetrol S.A.'}</p>
              <p><strong>Ubicación:</strong> {pedidoSeleccionado.principal?.ubicacion_cliente || 'Refinería Barrancabermeja'}</p>
              <p><strong>Fecha Compromiso:</strong> <span className="font-bold text-slate-800">📅 {pedidoSeleccionado.principal?.fecha_compromiso || '2026-11-15'}</span></p>
              <p><strong>Requisitos Cliente:</strong> {pedidoSeleccionado.principal?.requisitos_cliente || 'Norma ASME B16.5'}</p>
            </div>

            <h4 className="font-bold text-slate-700 text-xs">Órdenes de Producción (OP) Emitidas para este Pedido</h4>
            <div className="border border-slate-200 rounded overflow-hidden text-xs">
              <table className="w-full text-left border-collapse">
                <thead className="bg-slate-100 font-bold text-slate-700 border-b">
                  <tr>
                    <th className="p-2">Código OP</th>
                    <th className="p-2">Unidad Planta</th>
                    <th className="p-2">Detalle Producto</th>
                    <th className="p-2 text-center">Cantidad</th>
                    <th className="p-2 text-center">Avance (%)</th>
                    <th className="p-2">Estado Planta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-600">
                  {pedidoSeleccionado.ordenes.map((o, idx) => (
                    <tr key={idx}>
                      <td className="p-2 font-mono font-bold text-blue-700">⚙ OP-{o.codigo_op}</td>
                      <td className="p-2 font-bold text-slate-800">🏭 {o.unidad_planta || 'Mecanizados'}</td>
                      <td className="p-2">{o.detalle_producto || o.nombre_proyecto || 'Pieza'}</td>
                      <td className="p-2 text-center font-bold">{o.cantidad || 1} UND</td>
                      <td className="p-2 text-center font-bold text-blue-800">{o.porcentaje_avance || 0}%</td>
                      <td className="p-2 font-bold text-purple-700">{o.estado_produccion || o.estado || 'LIBERADA_PRODUCCION'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end border-t pt-3">
              <button onClick={() => setModalPedidoAbierto(false)} className="px-4 py-2 bg-slate-800 text-white font-bold rounded text-xs">
                Cerrar Expediente
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: HISTÓRICO Y HOJA DE VIDA DEL CLIENTE */}
      {modalClienteAbierto && clienteSeleccionado && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-bold rounded uppercase">
                  Hoja de Vida de Cliente [ISO 9001:2026 / Requisitos del Cliente]
                </span>
                <h3 className="text-xl font-bold text-slate-800 mt-1 flex items-center gap-2">
                  <span>🏢</span> {clienteSeleccionado.nombre}
                </h3>
              </div>
              <button onClick={() => setModalClienteAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg">✕</button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs bg-slate-50 p-4 rounded-lg border border-slate-200">
              <p><strong>Persona de Contacto:</strong> {clienteSeleccionado.contacto}</p>
              <p><strong>Teléfono Directo:</strong> {clienteSeleccionado.telefono}</p>
              <p><strong>Correo Electrónico:</strong> {clienteSeleccionado.email}</p>
              <p className="sm:col-span-3"><strong>Sede Principal / Entrega:</strong> {clienteSeleccionado.ubicacion}</p>
            </div>

            <div className="space-y-2">
              <h4 className="font-bold text-slate-700 text-xs flex items-center gap-1">
                📜 Histórico de Proyectos, Trabajos y Entregas Realizadas
              </h4>
              
              <div className="border border-slate-200 rounded-lg overflow-hidden text-xs">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-slate-100 font-bold text-slate-700 border-b">
                    <tr>
                      <th className="p-3">N° Pedido</th>
                      <th className="p-3">Código OP</th>
                      <th className="p-3">Descripción Producto / Trabajo</th>
                      <th className="p-3 text-center">Cantidad</th>
                      <th className="p-3">Fecha Compromiso</th>
                      <th className="p-3">Estado de Entrega</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 text-slate-600">
                    {clienteSeleccionado.historial.map((trabajo, idx) => (
                      <tr key={idx} className="hover:bg-slate-50 transition">
                        <td className="p-3 font-mono font-bold text-purple-700">📋 {trabajo.numero_pedido || 'PED-S/N'}</td>
                        <td className="p-3 font-mono font-bold text-blue-700">⚙ OP-{trabajo.codigo_op}</td>
                        <td className="p-3 font-bold text-slate-800">{trabajo.detalle_producto || trabajo.nombre_proyecto || 'Servicio Mecanizado'}</td>
                        <td className="p-3 text-center font-bold">{trabajo.cantidad || 1} UND</td>
                        <td className="p-3 font-bold text-slate-700">📅 {trabajo.fecha_compromiso || '2026-11-15'}</td>
                        <td className="p-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            (trabajo.estado_produccion || trabajo.estado) === 'CERRADA' ? 'bg-emerald-100 text-emerald-800' : 'bg-blue-100 text-blue-800'
                          }`}>
                            {(trabajo.estado_produccion || trabajo.estado) === 'CERRADA' ? 'ENTREGADO / CONFORME' : 'EN EJECUCIÓN'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex justify-end border-t pt-3">
              <button onClick={() => setModalClienteAbierto(false)} className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded text-xs transition">
                Cerrar Histórico
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}