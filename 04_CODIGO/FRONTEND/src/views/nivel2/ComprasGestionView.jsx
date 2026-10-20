import React, { useState, useEffect } from 'react';
import API from '../../services/api';

export default function ComprasGestionView() {
  // =========================================================================
  // BLOQUE 1: ESTADOS PRINCIPALES Y BÚSQUEDA
  // =========================================================================
  const [pestanaActiva, setPestanaActiva] = useState('SOLICITUDES');

  const [solicitudes, setSolicitudes] = useState([]);
  const [pedidos, setPedidos] = useState([]);
  const [ordenesPlanos, setOrdenesPlanos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });

  const [busqueda, setBusqueda] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('TODOS');

  const [modalSolicitudAbierto, setModalSolicitudAbierto] = useState(false);
  const [solicitudSeleccionada, setSolicitudSeleccionada] = useState(null);

  // FORMULARIO SOLICITUD DE COMPRA (PR)
  const [formPR, setFormPR] = useState({
    numero_solicitud: `PR-${Math.floor(1000 + Math.random() * 9000)}`,
    solicitante_nombre: 'Ing. Carlos Ruiz',
    departamento_area: 'Diseño e Ingeniería',
    id_proyecto: '',
    numero_pedido: '',
    codigo_op: '',
    codigo_plano: '',
    fecha_necesaria: '',
    comentarios: '',
    items: [
      { descripcion_material: '', cantidad: 1, unidad_medida: 'UND', codigo_plano: '' }
    ]
  });

  // =========================================================================
  // BLOQUE 2: CARGA DE DATOS DESDE EL BACKEND
  // =========================================================================
  useEffect(() => {
    cargarDatos();
  }, []);

  const cargarDatos = async () => {
    try {
      setLoading(true);
      const [resSol, resProj, resPlanos] = await Promise.allSettled([
        API.get('/solicitudes-compra/'),
        API.get('/proyectos/'),
        API.get('/planos/')
      ]);

      if (resSol.status === 'fulfilled') {
        setSolicitudes(Array.isArray(resSol.value.data) ? resSol.value.data : []);
      }
      if (resProj.status === 'fulfilled') {
        setPedidos(Array.isArray(resProj.value.data) ? resProj.value.data : []);
      }
      if (resPlanos.status === 'fulfilled') {
        setOrdenesPlanos(Array.isArray(resPlanos.value.data) ? resPlanos.value.data : []);
      }
    } catch (error) {
      console.warn("Error cargando datos de compras:", error);
    } finally {
      setLoading(false);
    }
  };

  // =========================================================================
  // BLOQUE 3: SELECCIÓN EN CASCADA (PEDIDO -> OP -> PLANO)
  // =========================================================================
  const ordenesDisponibles = ordenesPlanos.filter(op => {
    if (!formPR.numero_pedido) return true;
    const pedRelacionado = pedidos.find(p => p.numero_pedido === formPR.numero_pedido);
    return op.numero_pedido === formPR.numero_pedido || 
           (pedRelacionado && op.id_proyecto === pedRelacionado.id_proyecto);
  });

  const handleSeleccionarPedido = (numPedido) => {
    if (!numPedido) {
      setFormPR(prev => ({
        ...prev,
        id_proyecto: '',
        numero_pedido: '',
        codigo_op: '',
        codigo_plano: ''
      }));
      return;
    }

    const ped = pedidos.find(p => p.numero_pedido === numPedido);
    setFormPR(prev => ({
      ...prev,
      id_proyecto: ped?.id_proyecto || '',
      numero_pedido: numPedido,
      codigo_op: '',
      codigo_plano: ''
    }));
  };

  const handleSeleccionarOP = (codOp) => {
    if (!codOp) {
      setFormPR(prev => ({ ...prev, codigo_op: '', codigo_plano: '' }));
      return;
    }

    const planoAsociado = ordenesPlanos.find(p => p.codigo_op === codOp);
    const pedRelacionado = pedidos.find(p => p.id_proyecto === planoAsociado?.id_proyecto);

    const codigoPlanoDetectado = planoAsociado?.codigo_plano || '';
    const numPedidoDetectado = planoAsociado?.numero_pedido || pedRelacionado?.numero_pedido || formPR.numero_pedido;

    setFormPR(prev => ({
      ...prev,
      codigo_op: codOp,
      numero_pedido: numPedidoDetectado,
      codigo_plano: codigoPlanoDetectado,
      items: prev.items.map(item => ({
        ...item,
        codigo_plano: codigoPlanoDetectado
      }))
    }));
  };

  const handleAgregarItem = () => {
    setFormPR({
      ...formPR,
      items: [...formPR.items, { descripcion_material: '', cantidad: 1, unidad_medida: 'UND', codigo_plano: formPR.codigo_plano }]
    });
  };

  const handleRemoveItem = (index) => {
    const nuevosItems = formPR.items.filter((_, idx) => idx !== index);
    setFormPR({ ...formPR, items: nuevosItems });
  };

  const handleItemChange = (index, field, value) => {
    const nuevosItems = [...formPR.items];
    nuevosItems[index][field] = value;
    setFormPR({ ...formPR, items: nuevosItems });
  };

  // =========================================================================
  // BLOQUE 4: RADICACIÓN Y ASIGNACIÓN AL BOM DE DISEÑO (ENVÍO SANITIZADO)
  // =========================================================================
  const handleSubmitPR = async (e) => {
    e.preventDefault();
    setMensaje({ tipo: '', texto: '' });

    if (formPR.departamento_area === 'Diseño e Ingeniería' && (!formPR.numero_pedido || !formPR.codigo_op || !formPR.codigo_plano)) {
      setMensaje({ tipo: 'error', texto: 'Para requerimientos de Diseño e Ingeniería se exige vincular N° Pedido, OP y Código de Plano.' });
      return;
    }

    if (!formPR.items || formPR.items.length === 0 || !formPR.items[0].descripcion_material) {
      setMensaje({ tipo: 'error', texto: 'Especifique al menos un insumo o material requerido.' });
      return;
    }

    try {
      setLoading(true);

      // SANITIZACIÓN DE PAYLOAD
      const payload = {
        numero_solicitud: formPR.numero_solicitud,
        solicitante_nombre: formPR.solicitante_nombre,
        departamento_area: formPR.departamento_area,
        // Si no hay UUID de proyecto válido, se envía null para no romper Pydantic
        id_proyecto: formPR.id_proyecto && formPR.id_proyecto.length === 36 ? formPR.id_proyecto : null,
        numero_pedido: formPR.numero_pedido || null,
        codigo_op: formPR.codigo_op || null,
        codigo_plano: formPR.codigo_plano || null,
        fecha_necesaria: formPR.fecha_necesaria || null,
        comentarios: formPR.comentarios || null,
        items: formPR.items.map(it => ({
          descripcion_material: it.descripcion_material,
          cantidad: parseFloat(it.cantidad) || 1.0,
          unidad_medida: it.unidad_medida || 'UND',
          codigo_plano: formPR.codigo_plano || null
        }))
      };

      await API.post('/solicitudes-compra/', payload);

      setMensaje({ 
        tipo: 'exito', 
        texto: formPR.codigo_op 
          ? `✅ Solicitud ${formPR.numero_solicitud} radicada y asignada al BOM de OP-${formPR.codigo_op} en Diseño.`
          : `✅ Solicitud Interna ${formPR.numero_solicitud} radicada exitosamente.`
      });

      // REINICIO DE FORMULARIO
      setFormPR({
        numero_solicitud: `PR-${Math.floor(1000 + Math.random() * 9000)}`,
        solicitante_nombre: 'Ing. Carlos Ruiz',
        departamento_area: 'Diseño e Ingeniería',
        id_proyecto: '',
        numero_pedido: '',
        codigo_op: '',
        codigo_plano: '',
        fecha_necesaria: '',
        comentarios: '',
        items: [{ descripcion_material: '', cantidad: 1, unidad_medida: 'UND', codigo_plano: '' }]
      });

      cargarDatos();
    } catch (error) {
      console.error("Error al radicar solicitud:", error.response?.data || error);
      const detalleError = error.response?.data?.detail 
        ? (typeof error.response.data.detail === 'string' ? error.response.data.detail : JSON.stringify(error.response.data.detail))
        : 'Error al radicar la Solicitud de Compra.';
      setMensaje({ tipo: 'error', texto: `❌ ${detalleError}` });
    } finally {
      setLoading(false);
    }
  };

  const handleCambiarEstadoSolicitud = async (id, nuevoEstado, nuevoEstadoBom) => {
    try {
      setLoading(true);
      const payload = { estado: nuevoEstado };
      if (nuevoEstadoBom) payload.estado_bom = nuevoEstadoBom;

      await API.patch(`/solicitudes-compra/${id}`, payload);
      setMensaje({ tipo: 'exito', texto: `✅ Solicitud actualizada a estado [${nuevoEstado}].` });
      setModalSolicitudAbierto(false);
      cargarDatos();
    } catch (error) {
      setMensaje({ tipo: 'error', texto: 'No se pudo actualizar la solicitud.' });
    } finally {
      setLoading(false);
    }
  };

  const solicitudesFiltradas = solicitudes.filter((s) => {
    const termino = busqueda.toLowerCase().trim();
    const coincideSol = (s.numero_solicitud || '').toLowerCase().includes(termino);
    const coincideSolicitante = (s.solicitante_nombre || '').toLowerCase().includes(termino);
    const coincideDetalle = (s.descripcion_resumen || '').toLowerCase().includes(termino);
    const coincidePedido = (s.numero_pedido || '').toLowerCase().includes(termino);
    const coincideOP = (s.codigo_op || '').toLowerCase().includes(termino);
    const coincidePlano = (s.codigo_plano || '').toLowerCase().includes(termino);

    const coincideTexto = coincideSol || coincideSolicitante || coincideDetalle || coincidePedido || coincideOP || coincidePlano;
    const coincideEstado = filtroEstado === 'TODOS' || s.estado === filtroEstado;

    return coincideTexto && coincideEstado;
  });

  // =========================================================================
  // BLOQUE 5: RENDERIZADO VISUAL DEL COMPONENTE
  // =========================================================================
  return (
    <div className="p-6 bg-slate-50 min-h-screen space-y-6">
      <header className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">🛒 Módulo Compras — Proveedores (PM-04)</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Gestión de Insumos del BOM para OPs y Solicitudes Internas de Planta [ISO 9001:2026 / SAP B1]
          </p>
        </div>
      </header>

      {/* PESTAÑAS HORIZONTALES */}
      <div className="flex border-b border-slate-300 space-x-1 bg-white px-3 pt-2 rounded-t-xl border-x border-t">
        <button
          onClick={() => setPestanaActiva('SOLICITUDES')}
          className={`px-4 py-2.5 font-bold text-xs rounded-t-lg transition flex items-center gap-2 border-t-2 cursor-pointer ${
            pestanaActiva === 'SOLICITUDES'
              ? 'bg-slate-50 border-blue-600 text-blue-900 shadow-sm border-x border-slate-200'
              : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-100'
          }`}
        >
          📋 1. Solicitudes de Compra (PR / BOM)
        </button>

        <button
          onClick={() => setPestanaActiva('COTIZACIONES_OC')}
          className={`px-4 py-2.5 font-bold text-xs rounded-t-lg transition flex items-center gap-2 border-t-2 cursor-pointer ${
            pestanaActiva === 'COTIZACIONES_OC'
              ? 'bg-slate-50 border-blue-600 text-blue-900 shadow-sm border-x border-slate-200'
              : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-100'
          }`}
        >
          ⚖ 2. Cotizaciones & Orden de Compra (PO)
        </button>

        <button
          onClick={() => setPestanaActiva('ENTRADAS_FACTURAS')}
          className={`px-4 py-2.5 font-bold text-xs rounded-t-lg transition flex items-center gap-2 border-t-2 cursor-pointer ${
            pestanaActiva === 'ENTRADAS_FACTURAS'
              ? 'bg-slate-50 border-blue-600 text-blue-900 shadow-sm border-x border-slate-200'
              : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-100'
          }`}
        >
          📦 3. Entradas, Facturación & Costos (GR/AP)
        </button>

        <button
          onClick={() => setPestanaActiva('DEVOLUCIONES_NC')}
          className={`px-4 py-2.5 font-bold text-xs rounded-t-lg transition flex items-center gap-2 border-t-2 cursor-pointer ${
            pestanaActiva === 'DEVOLUCIONES_NC'
              ? 'bg-slate-50 border-blue-600 text-blue-900 shadow-sm border-x border-slate-200'
              : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-100'
          }`}
        >
          🔄 4. Devoluciones & No Conformidades
        </button>
      </div>

      {mensaje.texto && (
        <div className={`p-4 rounded-lg text-sm font-semibold border ${
          mensaje.tipo === 'exito' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-red-50 text-red-800 border-red-200'
        }`}>
          {mensaje.texto}
        </div>
      )}

      {pestanaActiva === 'SOLICITUDES' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* FORMULARIO DE SOLICITUD DE COMPRA */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm lg:col-span-1">
              <h2 className="text-lg font-bold text-slate-700 mb-3 border-b pb-2 flex items-center justify-between">
                <span>Solicitud de Compra (PR)</span>
                <span className="font-mono text-xs bg-blue-50 text-blue-800 px-2 py-0.5 rounded border border-blue-200">
                  {formPR.numero_solicitud}
                </span>
              </h2>

              <form onSubmit={handleSubmitPR} className="space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Solicitante *</label>
                    <select
                      value={formPR.solicitante_nombre}
                      onChange={(e) => setFormPR({ ...formPR, solicitante_nombre: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded font-semibold bg-white cursor-pointer"
                      required
                    >
                      <option value="Ing. Carlos Ruiz">Carlos Ruiz (Diseño)</option>
                      <option value="Laura Gómez">Laura Gómez (Ventas)</option>
                      <option value="Pedro Martínez">Pedro Martínez (Almacén)</option>
                      <option value="Juan Pérez">Juan Pérez (Producción)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Departamento *</label>
                    <select
                      value={formPR.departamento_area}
                      onChange={(e) => setFormPR({ ...formPR, departamento_area: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded bg-white cursor-pointer"
                      required
                    >
                      <option value="Diseño e Ingeniería">Diseño e Ingeniería</option>
                      <option value="Almacén e Inventario">Almacén e Inventario</option>
                      <option value="Producción y Planta">Producción y Planta</option>
                      <option value="Mantenimiento">Mantenimiento</option>
                      <option value="Administración">Administración</option>
                    </select>
                  </div>
                </div>

                {/* VINCULACIÓN OPCIONAL A PEDIDO COMERCIAL */}
                <div>
                  <label className="block font-bold text-slate-700 mb-1">
                    N° Pedido Comercial {formPR.departamento_area === 'Diseño e Ingeniería' ? '*' : '(Opcional)'}
                  </label>
                  <select
                    value={formPR.numero_pedido}
                    onChange={(e) => handleSeleccionarPedido(e.target.value)}
                    className="w-full p-2 border border-purple-300 rounded font-mono font-bold text-purple-900 bg-purple-50/50 cursor-pointer"
                    required={formPR.departamento_area === 'Diseño e Ingeniería'}
                  >
                    <option value="">-- Sin Pedido / Solicitud Interna --</option>
                    {pedidos.map(p => (
                      <option key={p.id_proyecto} value={p.numero_pedido}>
                        📋 {p.numero_pedido} - {p.cliente_nombre}
                      </option>
                    ))}
                  </select>
                </div>

                {/* CAMPOS CON DESPLEGABLE MAPEADO DE OT Y PLANO */}
                <div className="grid grid-cols-2 gap-2 bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                  <div>
                    <label className="block font-bold text-blue-900 mb-1">N° Orden (OP)</label>
                    <select
                      value={formPR.codigo_op}
                      onChange={(e) => handleSeleccionarOP(e.target.value)}
                      className="w-full p-2 border border-blue-400 rounded font-mono font-bold text-blue-900 bg-white cursor-pointer"
                    >
                      <option value="">-- Sin OP --</option>
                      {ordenesDisponibles.map((op, idx) => (
                        <option key={op.id_plano || idx} value={op.codigo_op}>
                          ⚙ OP-{op.codigo_op} ({op.unidad_planta || 'Mecanizados'})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block font-bold text-purple-900 mb-1">Código Plano / Pieza</label>
                    <input
                      type="text"
                      placeholder="Ej. PLN-001-A"
                      value={formPR.codigo_plano}
                      onChange={(e) => setFormPR({ ...formPR, codigo_plano: e.target.value })}
                      className="w-full p-2 border border-purple-300 rounded font-mono font-bold text-purple-900 bg-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Fecha Necesaria de Entrega</label>
                  <input
                    type="date"
                    value={formPR.fecha_necesaria}
                    onChange={(e) => setFormPR({ ...formPR, fecha_necesaria: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded bg-white"
                  />
                </div>

                {/* TABLA DE INSUMOS Y MATERIALES BOM */}
                <div className="border border-slate-200 rounded-lg p-2.5 bg-slate-50 space-y-2">
                  <div className="flex justify-between items-center border-b pb-1">
                    <span className="font-bold text-slate-700">Insumos / Materiales Requeridos</span>
                    <button
                      type="button"
                      onClick={handleAgregarItem}
                      className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-[10px] font-bold cursor-pointer"
                    >
                      + Agregar Fila
                    </button>
                  </div>

                  {formPR.items.map((item, index) => (
                    <div key={index} className="grid grid-cols-12 gap-1.5 items-center">
                      <div className="col-span-6">
                        <input
                          type="text"
                          placeholder="Ej. Rodamiento SKF 6205 / Barra ASTM A105"
                          value={item.descripcion_material}
                          onChange={(e) => handleItemChange(index, 'descripcion_material', e.target.value)}
                          className="w-full p-1.5 border border-slate-300 rounded text-[11px] bg-white font-medium"
                          required
                        />
                      </div>
                      <div className="col-span-3">
                        <input
                          type="number"
                          step="0.1"
                          min="0.1"
                          placeholder="Cant."
                          value={item.cantidad}
                          onChange={(e) => handleItemChange(index, 'cantidad', e.target.value)}
                          className="w-full p-1.5 border border-slate-300 rounded text-[11px] bg-white font-bold"
                          required
                        />
                      </div>
                      <div className="col-span-2">
                        <select
                          value={item.unidad_medida}
                          onChange={(e) => handleItemChange(index, 'unidad_medida', e.target.value)}
                          className="w-full p-1.5 border border-slate-300 rounded text-[10px] bg-white font-semibold cursor-pointer"
                        >
                          <option value="UND">UND</option>
                          <option value="KG">KG</option>
                          <option value="MTR">MTR</option>
                          <option value="PLACA">PLACA</option>
                          <option value="JGO">JGO</option>
                        </select>
                      </div>
                      <div className="col-span-1 text-center">
                        {formPR.items.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveItem(index)}
                            className="text-red-500 hover:text-red-700 font-bold text-xs cursor-pointer"
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Comentarios / Justificación</label>
                  <textarea
                    rows="2"
                    placeholder="Justificación del pedido..."
                    value={formPR.comentarios}
                    onChange={(e) => setFormPR({ ...formPR, comentarios: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded bg-white"
                  ></textarea>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded text-xs transition shadow-sm cursor-pointer"
                >
                  {loading ? 'Guardando...' : '💾 Radicar Solicitud y Asignar BOM'}
                </button>
              </form>
            </div>

            {/* TABLA DE HISTORIAL DE SOLICITUDES */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm lg:col-span-2 space-y-4">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b pb-3">
                <div>
                  <h2 className="text-lg font-bold text-slate-700">Historial de Solicitudes y Estado de BOM</h2>
                  <p className="text-xs text-slate-400">Control por Pedido, OP, Plano o Requerimiento Interno</p>
                </div>

                <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
                  <div className="relative w-full sm:w-72">
                    <input
                      type="text"
                      placeholder="🔍 Buscar por N° PR, Pedido, OP, Plano o Material..."
                      value={busqueda}
                      onChange={(e) => setBusqueda(e.target.value)}
                      className="w-full pl-3 pr-8 py-2 border border-blue-300 rounded-lg text-xs bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none font-medium"
                    />
                    {busqueda && (
                      <button
                        onClick={() => setBusqueda('')}
                        className="absolute right-2 top-2 text-slate-400 hover:text-slate-600 text-xs font-bold cursor-pointer"
                      >
                        ✕
                      </button>
                    )}
                  </div>

                  <select
                    value={filtroEstado}
                    onChange={(e) => setFiltroEstado(e.target.value)}
                    className="p-2 border border-slate-300 rounded-lg text-xs font-bold bg-slate-50 text-slate-700 cursor-pointer"
                  >
                    <option value="TODOS">Todos los Estados</option>
                    <option value="RADICADA">RADICADA</option>
                    <option value="EN_VERIFICACION">EN VERIFICACIÓN</option>
                    <option value="APROBADA">APROBADA</option>
                    <option value="RECHAZADA">RECHAZADA</option>
                  </select>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-600 border-collapse">
                  <thead>
                    <tr className="bg-slate-100 text-slate-700 font-bold uppercase border-b border-slate-200">
                      <th className="p-3">N° Solicitud</th>
                      <th className="p-3">N° Pedido</th>
                      <th className="p-3">N° Orden (OP)</th>
                      <th className="p-3">Código Plano</th>
                      <th className="p-3">Insumos Requeridos</th>
                      <th className="p-3 text-center">Estado BOM</th>
                      <th className="p-3 text-center">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {solicitudesFiltradas.length === 0 ? (
                      <tr>
                        <td colSpan="7" className="p-6 text-center text-slate-400 font-medium">
                          No hay solicitudes de compra registradas.
                        </td>
                      </tr>
                    ) : (
                      solicitudesFiltradas.map((s) => (
                        <tr key={s.id_solicitud} className="hover:bg-slate-50 transition">
                          <td className="p-3 font-bold font-mono text-blue-700">
                            {s.numero_solicitud}
                          </td>
                          <td className="p-3 font-mono font-bold text-purple-700">
                            📋 {s.numero_pedido || 'S/P'}
                          </td>
                          <td className="p-3 font-mono font-bold text-blue-900">
                            ⚙ OP-{s.codigo_op || 'GENERAL'}
                          </td>
                          <td className="p-3 font-mono font-bold text-slate-800">
                            📄 {s.codigo_plano || 'N/A'}
                          </td>
                          <td className="p-3 font-semibold text-slate-700">
                            {s.descripcion_resumen}
                          </td>
                          <td className="p-3 text-center whitespace-nowrap">
                            <span className={`px-2 py-1 rounded text-[10px] font-bold border ${
                              s.estado_bom === 'ENTREGADO' ? 'bg-emerald-100 text-emerald-800 border-emerald-300' :
                              s.estado_bom === 'EN_COMPRA' ? 'bg-blue-100 text-blue-800 border-blue-300' :
                              'bg-amber-100 text-amber-800 border-amber-300'
                            }`}>
                              {s.estado_bom === 'ENTREGADO' && '🟢 ENTREGADO'}
                              {s.estado_bom === 'EN_COMPRA' && '🔵 EN COMPRA'}
                              {(!s.estado_bom || s.estado_bom === 'SOLICITADO') && '🟡 SOLICITADO (PR)'}
                            </span>
                          </td>
                          <td className="p-3 text-center space-x-1 whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => {
                                setSolicitudSeleccionada(s);
                                setModalSolicitudAbierto(true);
                              }}
                              className="px-2.5 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded text-[11px] shadow-sm transition cursor-pointer"
                            >
                              👁 Verificar
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL VERIFICACIÓN DE SOLICITUD */}
      {modalSolicitudAbierto && solicitudSeleccionada && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-6 space-y-4">
            <div className="flex justify-between items-start border-b pb-3">
              <h3 className="text-xl font-bold text-slate-800">
                Verificación de Solicitud N°: <span className="text-blue-700 font-mono">{solicitudSeleccionada.numero_solicitud}</span>
              </h3>
              <button onClick={() => setModalSolicitudAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
            </div>

            <div className="bg-slate-50 p-3 rounded-lg border text-xs space-y-1">
              <p><strong>Solicitante:</strong> {solicitudSeleccionada.solicitante_nombre} ({solicitudSeleccionada.departamento_area})</p>
              <p><strong>Pedido / OP / Plano:</strong> Pedido {solicitudSeleccionada.numero_pedido || 'S/P'} / OP-{solicitudSeleccionada.codigo_op || 'GENERAL'} / Plano {solicitudSeleccionada.codigo_plano || 'N/A'}</p>
              <p><strong>Resumen de Insumos BOM:</strong> {solicitudSeleccionada.descripcion_resumen}</p>
              <p><strong>Estado Casilla BOM:</strong> <span className="font-bold text-emerald-700">{solicitudSeleccionada.estado_bom || 'SOLICITADO'}</span></p>
            </div>

            <div className="flex justify-end gap-2 border-t pt-3">
              <button
                type="button"
                onClick={() => handleCambiarEstadoSolicitud(solicitudSeleccionada.id_solicitud, 'RECHAZADA', 'SIN_SOLICITAR')}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-bold rounded text-xs cursor-pointer"
              >
                ✕ Rechazar
              </button>
              <button
                type="button"
                onClick={() => handleCambiarEstadoSolicitud(solicitudSeleccionada.id_solicitud, 'EN_VERIFICACION', 'SOLICITADO')}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded text-xs cursor-pointer"
              >
                ⏳ En Verificación
              </button>
              <button
                type="button"
                onClick={() => handleCambiarEstadoSolicitud(solicitudSeleccionada.id_solicitud, 'APROBADA', 'EN_COMPRA')}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-xs cursor-pointer"
              >
                ✓ Aprobar Solicitud
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}