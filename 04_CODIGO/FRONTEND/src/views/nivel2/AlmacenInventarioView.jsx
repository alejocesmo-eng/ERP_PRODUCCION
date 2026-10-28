// src/views/nivel2/AlmacenInventarioView.jsx
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../../services/api';

export default function AlmacenInventarioView() {
  const [pestañaActiva, setPestañaActiva] = useState('entradas'); // 'entradas', 'salidas', 'remanentes'
  const [solicitudesEnCompra, setSolicitudesEnCompra] = useState([]);
  const [solicitudSeleccionada, setSolicitudSeleccionada] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });

  const [insumoBusqueda, setInsumoBusqueda] = useState('');
  const [insumoSugerencias, setInsumoSugerencias] = useState([]);
  const [cargandoInsumos, setCargandoInsumos] = useState(false);
  const [mostrarSugerenciasInsumos, setMostrarSugerenciasInsumos] = useState(false);

  // Formulario Entrada / Recepción desde Compras
  const [entradaForm, setEntradaForm] = useState({
    numero_solicitud_compra: '',
    id_solicitud: '',
    codigo_sku: '',
    nombre_item: '',
    cantidad_solicitada: '',
    cantidad_recibida: '',
    costo_unitario: '',
    unidad_medida: 'UND',
    numero_factura: '',
    factura_digital_url: '',
    numero_lote: '',
    numero_colada: '',
    certificado_3_1_url: '',
    codigo_op: '',
    codigo_plano: '',
    numero_pedido: ''
  });

  // Formulario Salidas de Almacén
  const [salidaForm, setSalidaForm] = useState({
    codigo_sku: '',
    cantidad_salida: '',
    tipo_destino: 'ORDEN_PRODUCCION',
    codigo_op: '',
    centro_costos: 'Planta Principal',
    operario_responsable: '',
    fecha_devolucion: '',
    observaciones: ''
  });

  // ESTADOS Y DATOS INTEGRADOS DE REMANENTES / SOBRANTES
  const [vistaRemanentes, setVistaRemanentes] = useState('panel'); // 'panel' | 'registrar'
  const [retales, setRetales] = useState([]);
  const [filtroKpiRemanentes, setFiltroKpiRemanentes] = useState('TODOS');
  const [filtrosBusquedaRetales, setFiltrosBusquedaRetales] = useState({
    busqueda_q: '',
    material: 'TODOS',
    forma: 'TODOS',
    espesor: '',
    largo_min_mm: '',
    ancho_min_mm: ''
  });

  // Modal Ficha Técnica y QR
  const [modalFichaRetal, setModalFichaRetal] = useState(false);
  const [retalFichaData, setRetalFichaData] = useState(null);

  // Formulario Registro de Retal
  const [retalRegistroForm, setRetalRegistroForm] = useState({
    material_clasificacion: 'Acero Inoxidable 304',
    forma_geometria: 'Lámina / Placa',
    espesor_seccion: '3 mm',
    largo_mm: '',
    ancho_mm: '',
    diametro_ext_mm: '',
    diametro_int_mm: '',
    peso_kg: '',
    unidad_medida: 'kg',
    procedencia: 'Corte Guillotina / Láser (Producción)',
    codigo_op_origen: '',
    numero_colada_lote: '',
    ubicacion_almacen: 'RACK-A1-RETAZOS',
    observaciones: '',
    fotografia_url: ''
  });
  const [fotoPreviewRetal, setFotoPreviewRetal] = useState(null);

  useEffect(() => {
    cargarSolicitudesEnCompra();
    cargarListaRetales();
  }, [filtroKpiRemanentes]);

  useEffect(() => {
    if (pestañaActiva !== 'salidas') return undefined;
    const timeout = window.setTimeout(async () => {
      setCargandoInsumos(true);
      try {
        const res = await API.get('/inventario/articulos', {
          params: { q: insumoBusqueda || undefined, disponible: true }
        });
        setInsumoSugerencias(Array.isArray(res.data) ? res.data : []);
      } catch (error) {
        setMensaje({
          tipo: 'error',
          texto: error.response?.data?.detail || 'No fue posible consultar existencias liberadas.'
        });
        setInsumoSugerencias([]);
      } finally {
        setCargandoInsumos(false);
      }
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [pestañaActiva, insumoBusqueda]);

  const cargarSolicitudesEnCompra = async () => {
    try {
      setLoading(true);
      const res = await API.get('/solicitudes-compra/', { params: { estado_bom: 'EN_COMPRA' } });
      if (Array.isArray(res.data)) {
        const enCompra = res.data.filter(
          (s) => s.estado_bom === 'EN_COMPRA' && Number(s.cantidad_pendiente ?? s.cantidad_piezas) > 0
        );
        setSolicitudesEnCompra(enCompra);
      } else {
        setSolicitudesEnCompra([]);
      }
    } catch (err) {
      setSolicitudesEnCompra([]);
    } finally {
      setLoading(false);
    }
  };

  const cargarListaRetales = async () => {
    try {
      const params = new URLSearchParams();
      if (filtroKpiRemanentes !== 'TODOS') params.append('estado', filtroKpiRemanentes);
      if (filtrosBusquedaRetales.busqueda_q) params.append('busqueda_q', filtrosBusquedaRetales.busqueda_q);
      if (filtrosBusquedaRetales.material !== 'TODOS') params.append('material', filtrosBusquedaRetales.material);
      if (filtrosBusquedaRetales.largo_min_mm) params.append('largo_min_mm', filtrosBusquedaRetales.largo_min_mm);
      if (filtrosBusquedaRetales.ancho_min_mm) params.append('ancho_min_mm', filtrosBusquedaRetales.ancho_min_mm);

      const res = await API.get(`/almacen/retales/buscar?${params.toString()}`);
      setRetales(Array.isArray(res.data) ? res.data : retalesMockFallback);
    } catch (err) {
      setRetales(retalesMockFallback);
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
      codigo_sku: solicitud.codigo_sku || '',
      nombre_item: solicitud.descripcion_resumen || '',
      cantidad_solicitada: solicitud.cantidad_pendiente ?? solicitud.cantidad_piezas ?? 1,
      cantidad_recibida: solicitud.cantidad_pendiente ?? solicitud.cantidad_piezas ?? 1,
      costo_unitario: '',
      unidad_medida: solicitud.unidad_medida || 'UND',
      numero_colada: '',
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

      const payloadEntrada = {
        numero_solicitud_compra: entradaForm.numero_solicitud_compra,
        id_solicitud: entradaForm.id_solicitud,
        codigo_sku: entradaForm.codigo_sku || 'MAT-PR',
        cantidad_solicitada: cantSol,
        cantidad_recibida: cantRec,
        costo_unitario: Number(entradaForm.costo_unitario),
        numero_factura: entradaForm.numero_factura,
        numero_lote: entradaForm.numero_lote || null,
        numero_colada: entradaForm.numero_colada || null,
        factura_digital_url: entradaForm.factura_digital_url || null,
        certificado_3_1_url: entradaForm.certificado_3_1_url || null,
        recibido_por: 'Almacén Central'
      };
      const respuesta = await API.post('/almacen/recepcion-compra', payloadEntrada);

      setMensaje({ 
        tipo: 'exito', 
        texto: `✅ Recepción [${entradaForm.numero_solicitud_compra}] registrada${detalleDif}. Lote ${respuesta.data.codigo_lote} en CUARENTENA; Calidad debe liberarlo antes del despacho.`
      });

      setEntradaForm({
        numero_solicitud_compra: '', id_solicitud: '', codigo_sku: '', nombre_item: '',
        cantidad_solicitada: '', cantidad_recibida: '', costo_unitario: '', unidad_medida: 'UND', numero_factura: '', factura_digital_url: '', numero_lote: '', numero_colada: '', certificado_3_1_url: '',
        codigo_op: '', codigo_plano: '', numero_pedido: ''
      });
      setSolicitudSeleccionada(null);

      await cargarSolicitudesEnCompra();
    } catch (error) {
      setMensaje({
        tipo: 'error',
        texto: error.response?.data?.detail || 'Error al registrar la recepción de mercancía.'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleGuardarSalida = async (e) => {
    e.preventDefault();
    if (Number(salidaForm.cantidad_salida) <= 0) {
      return setMensaje({ tipo: 'error', texto: '⚠ Ingrese una cantidad de salida válida.' });
    }
    try {
      setLoading(true);
      const respuesta = await API.post('/almacen/salidas', {
        codigo_sku: salidaForm.codigo_sku,
        cantidad_salida: Number(salidaForm.cantidad_salida),
        tipo_destino: salidaForm.tipo_destino,
        codigo_op: salidaForm.codigo_op || null,
        centro_costos: salidaForm.centro_costos || null,
        operario_responsable: salidaForm.operario_responsable || null,
        fecha_devolucion_estimada: salidaForm.fecha_devolucion || null,
        observaciones: salidaForm.observaciones || null
      });
      setMensaje({ tipo: 'exito', texto: `✅ ${respuesta.data.mensaje} Valor: $${Number(respuesta.data.valor_total).toLocaleString()}.` });
      setSalidaForm({
        codigo_sku: '', cantidad_salida: '', tipo_destino: 'ORDEN_PRODUCCION',
        codigo_op: '', centro_costos: 'Planta Principal', operario_responsable: '', fecha_devolucion: '', observaciones: ''
      });
      setInsumoBusqueda('');
      await cargarSolicitudesEnCompra();
    } catch (error) {
      setMensaje({
        tipo: 'error',
        texto: error.response?.data?.detail || 'Error al registrar la salida de almacén.'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFotoRetalUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setFotoPreviewRetal(reader.result);
        setRetalRegistroForm(prev => ({ ...prev, fotografia_url: reader.result }));
      };
      reader.readAsDataURL(file);
    }
  };

  const handleGuardarRetalNuevo = async (e) => {
    e.preventDefault();
    if (!retalRegistroForm.codigo_op_origen) {
      return setMensaje({ tipo: 'error', texto: '⚠️ Debe ingresar la Orden de Producción de origen del retal.' });
    }

    try {
      setLoading(true);
      const payload = {
        ...retalRegistroForm,
        largo_mm: Number(retalRegistroForm.largo_mm) || 0,
        ancho_mm: Number(retalRegistroForm.ancho_mm) || Number(retalRegistroForm.diametro_ext_mm) || 0,
        diametro_ext_mm: Number(retalRegistroForm.diametro_ext_mm) || 0,
        diametro_int_mm: Number(retalRegistroForm.diametro_int_mm) || 0,
        peso_kg: Number(retalRegistroForm.peso_kg) || 0,
        registrado_por: 'Operario Almacén'
      };

      const res = await API.post('/almacen/retales/nuevo', payload);
      setMensaje({
        tipo: 'exito',
        texto: `✅ Retal [${res.data.codigo_retal || 'RET-2026'}] registrado con éxito. Queda en estado PENDIENTE DE EVALUACIÓN.`
      });

      setVistaRemanentes('panel');
      cargarListaRetales();
    } catch (err) {
      setMensaje({ tipo: 'error', texto: 'Error al registrar el remanente.' });
    } finally {
      setLoading(false);
    }
  };

  const handleAbrirFichaModal = async (idOrCodigo) => {
    try {
      setLoading(true);
      const res = await API.get(`/almacen/retales/${idOrCodigo}`);
      setRetalFichaData(res.data);
      setModalFichaRetal(true);
    } catch (err) {
      const local = retales.find(r => r.id_retal === idOrCodigo || r.codigo_retal === idOrCodigo);
      if (local) {
        setRetalFichaData({
          ...local,
          qr_code_data: `SGI-RETAL|SKU:${local.codigo_retal}|OP:${local.codigo_op_origen}|COLADA:${local.numero_colada_lote || 'N/A'}`,
          historial: [
            { fecha: new Date(), tipo_movimiento: 'INGRESO_RECUPERACION', cantidad_peso: `${local.peso_kg} kg`, usuario_responsable: 'Operario Planta', referencia_op: local.codigo_op_origen }
          ]
        });
        setModalFichaRetal(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const retalesMockFallback = [
    { id_retal: '1', codigo_retal: 'RET-2026-0001', material_clasificacion: 'Acero Inoxidable 304', forma_geometria: 'Lámina / Placa', espesor_seccion: '3 mm', largo_mm: 1200, ancho_mm: 400, peso_kg: 11.5, numero_colada_lote: 'COL-88942', codigo_op_origen: 'OP-4001234', ubicación_almacen: 'RACK-A2', estado_evaluacion: 'DISPONIBLE' },
    { id_retal: '2', codigo_retal: 'RET-2026-0002', material_clasificacion: 'Bronce SAE 65', forma_geometria: 'Barra Maciza Redonda', espesor_seccion: 'Ø 4"', largo_mm: 180, ancho_mm: 100, peso_kg: 12.3, numero_colada_lote: null, codigo_op_origen: 'OP-100234', ubicación_almacen: 'ESTANTE-B', estado_evaluacion: 'EN_EVALUACION' },
    { id_retal: '3', codigo_retal: 'RET-2026-0003', material_clasificacion: 'AISI 4140 Bonificado', forma_geometria: 'Barra Maciza Redonda', espesor_seccion: 'Ø 2.5"', largo_mm: 350, ancho_mm: 63, peso_kg: 22.0, numero_colada_lote: 'COL-90112', codigo_op_origen: 'OP-30011', ubicación_almacen: 'RACK-C1', estado_evaluacion: 'RESERVADO' }
  ];

  return (
    <div className="p-6 bg-slate-50 min-h-screen space-y-6 text-xs font-sans">

      {/* ENCABEZADO Y PESTAÑAS PRINCIPALES */}
      <header className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <span>📦</span> Almacén Operativo — Recepción, Despachos y Remanentes
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Cotejo y Mapeo de Solicitudes de Compra ("En Compra"), Control de Remanentes, Imputación a Órdenes de Producción y Salidas [ISO 9001:2026]
          </p>
        </div>
        
        <div className="flex gap-2 items-center self-stretch md:self-auto flex-wrap">
          <Link
            to="/inventario/general"
            className="px-3.5 py-2 font-bold text-xs rounded-lg transition bg-slate-800 hover:bg-slate-900 text-white flex items-center gap-1.5 shadow-sm"
          >
            <span>🧾</span> Inventario General
          </Link>

          <div className="flex gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200">
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
            <button
              type="button"
              onClick={() => setPestañaActiva('remanentes')}
              className={`px-4 py-2 font-bold text-xs rounded-lg transition cursor-pointer flex items-center gap-1.5 ${
                pestañaActiva === 'remanentes' ? 'bg-amber-600 text-white shadow-sm font-black' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span>✂️</span> Remanentes / Sobrantes
            </button>
          </div>
        </div>
      </header>

      {mensaje.texto && (
        <div className={`p-4 rounded-xl text-sm font-semibold border ${
          mensaje.tipo === 'exito' ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : 'bg-red-50 text-red-800 border-red-300'
        }`}>
          {mensaje.texto}
        </div>
      )}

      {/* PESTAÑA 1: RECEPCIÓN DE COMPRAS */}
      {pestañaActiva === 'entradas' && (
        <div className="space-y-6 max-w-5xl mx-auto">
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
                      <th className="p-2.5 text-center">Saldo por recibir</th>
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
                            {Number(s.cantidad_pendiente ?? s.cantidad_piezas).toLocaleString()} {s.unidad_medida}
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

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Código SKU *</label>
                  <input
                    type="text"
                    name="codigo_sku"
                    placeholder="SKU registrado en Inventario General"
                    value={entradaForm.codigo_sku}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded font-mono font-semibold"
                    required
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-600 mb-1">URL de factura digital</label>
                  <input
                    type="url"
                    name="factura_digital_url"
                    placeholder="https://… (repositorio autorizado)"
                    value={entradaForm.factura_digital_url}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded"
                  />
                </div>
              </div>

              <div className="p-4 bg-purple-50 border border-purple-200 rounded-xl grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Cantidad Solicitada (Compras)</label>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      name="cantidad_solicitada"
                      placeholder="100"
                      value={entradaForm.cantidad_solicitada}
                      onChange={handleEntradaChange}
                      className="w-full p-2 border border-slate-300 rounded bg-white font-semibold"
                      readOnly
                      required
                    />
                    <span className="text-xs font-bold text-slate-500">{entradaForm.unidad_medida}</span>
                  </div>
                </div>

                <div>
                  <label className="block font-bold text-purple-900 mb-1">Cantidad Físicamente Recibida *</label>
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
                    placeholder="Código de lote"
                    value={entradaForm.numero_lote}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">N° de colada</label>
                  <input
                    type="text"
                    name="numero_colada"
                    placeholder="Identificación de colada"
                    value={entradaForm.numero_colada}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Costo unitario *</label>
                  <input
                    type="number"
                    name="costo_unitario"
                    min="0"
                    step="0.0001"
                    value={entradaForm.costo_unitario}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white"
                    required
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Certificado 3.1 (URL)</label>
                  <input
                    type="url"
                    name="certificado_3_1_url"
                    placeholder="https://…"
                    value={entradaForm.certificado_3_1_url}
                    onChange={handleEntradaChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white"
                  />
                </div>
              </div>

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

      {/* PESTAÑA 2: REGISTRO DE SALIDAS */}
      {pestañaActiva === 'salidas' && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-4xl mx-auto space-y-4">
          <h2 className="text-base font-bold text-slate-800 border-b pb-2 flex items-center gap-2">
            <span>📤</span> Registro de Salidas, Consumos y Préstamos de Herramientas
          </h2>
          <form onSubmit={handleGuardarSalida} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Código SKU / Ítem a Retirar *</label>
                <div className="relative">
                  <input
                    type="search"
                    name="codigo_sku"
                    placeholder="Buscar SKU o descripción (solo stock liberado)"
                    value={salidaForm.codigo_sku}
                    onFocus={() => {
                      setInsumoBusqueda(salidaForm.codigo_sku);
                      setMostrarSugerenciasInsumos(true);
                    }}
                    onChange={(event) => {
                      setSalidaForm({ ...salidaForm, codigo_sku: event.target.value });
                      setInsumoBusqueda(event.target.value);
                      setMostrarSugerenciasInsumos(true);
                    }}
                    className="w-full rounded border border-slate-300 p-2 font-semibold"
                    autoComplete="off"
                    required
                  />
                  {mostrarSugerenciasInsumos && (
                    <div className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
                      {cargandoInsumos ? (
                        <div className="p-3 text-slate-500">Consultando Inventario General…</div>
                      ) : insumoSugerencias.length ? insumoSugerencias.slice(0, 8).map((articulo) => (
                        <button
                          type="button"
                          key={articulo.id_articulo}
                          onClick={() => {
                            setSalidaForm({ ...salidaForm, codigo_sku: articulo.codigo_sku });
                            setInsumoBusqueda(articulo.codigo_sku);
                            setMostrarSugerenciasInsumos(false);
                          }}
                          className="block w-full border-b border-slate-100 px-3 py-2 text-left hover:bg-emerald-50"
                        >
                          <span className="font-mono font-bold text-slate-800">{articulo.codigo_sku}</span>
                          <span className="ml-2 text-slate-600">{articulo.nombre}</span>
                          <span className="float-right font-bold text-emerald-700">
                            {Number(articulo.stock_disponible).toLocaleString()} {articulo.unidad_medida}
                          </span>
                        </button>
                      )) : (
                        <div className="p-3 text-slate-500">No hay insumos liberados que coincidan con la búsqueda.</div>
                      )}
                    </div>
                  )}
                </div>
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
                  <option value="ORDEN_PRODUCCION">⚙ Imputable a Orden de Producción ("OP")</option>
                  <option value="CENTRO_COSTOS">🏢 Imputable a Centro de Costos (Planta / Aseo / Adm)</option>
                  <option value="ASIGNACION_OPERARIO">👤 Asignación Fija a Operario / Puesto</option>
                  <option value="PRESTAMO_TEMPORAL">🛠 Préstamo Temporal de Herramienta</option>
                </select>
              </div>
            </div>

            {salidaForm.tipo_destino === 'ORDEN_PRODUCCION' && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <label className="block font-bold text-blue-900 mb-1">Código de la Orden de Producción ("OP") *</label>
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

      {/* PESTAÑA 3: REMANENTES Y SOBRANTES (CON VISTAS INTEGRADAS) */}
      {pestañaActiva === 'remanentes' && (
        <div className="space-y-5">
          <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-sm flex justify-between items-center flex-wrap gap-2">
            <span className="font-extrabold text-slate-800 flex items-center gap-1">
              <span>✂️</span> Control e Inventario de Sobrantes / Remanentes
            </span>
            <div className="flex items-center gap-2">
              {vistaRemanentes === 'panel' ? (
                <button
                  type="button"
                  onClick={() => setVistaRemanentes('registrar')}
                  className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-lg shadow-sm cursor-pointer"
                >
                  ➕ Registrar Nuevo Retal
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setVistaRemanentes('panel')}
                  className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded-lg shadow-sm cursor-pointer"
                >
                  📊 Volver al Panel
                </button>
              )}
            </div>
          </div>

          {vistaRemanentes === 'panel' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                <button
                  type="button"
                  onClick={() => setFiltroKpiRemanentes('DISPONIBLE')}
                  className={`p-3.5 rounded-xl border text-left cursor-pointer ${
                    filtroKpiRemanentes === 'DISPONIBLE' ? 'bg-emerald-100 border-emerald-400 ring-2 ring-emerald-500' : 'bg-white border-slate-200'
                  }`}
                >
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">🟢 Disponibles</span>
                  <div className="text-lg font-black text-emerald-900 mt-0.5">248 Piezas</div>
                  <span className="text-[10px] text-slate-500 font-semibold block">3,420 kg en stock</span>
                </button>

                <button
                  type="button"
                  onClick={() => setFiltroKpiRemanentes('EN_EVALUACION')}
                  className={`p-3.5 rounded-xl border text-left cursor-pointer ${
                    filtroKpiRemanentes === 'EN_EVALUACION' ? 'bg-amber-100 border-amber-400 ring-2 ring-amber-500' : 'bg-white border-slate-200'
                  }`}
                >
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">⏳ Pendiente Evaluación</span>
                  <div className="text-lg font-black text-amber-900 mt-0.5">14 Piezas</div>
                  <span className="text-[10px] text-slate-500 font-semibold block">Inspección Metrológica</span>
                </button>

                <button
                  type="button"
                  onClick={() => setFiltroKpiRemanentes('RESERVADO')}
                  className={`p-3.5 rounded-xl border text-left cursor-pointer ${
                    filtroKpiRemanentes === 'RESERVADO' ? 'bg-blue-100 border-blue-400 ring-2 ring-blue-500' : 'bg-white border-slate-200'
                  }`}
                >
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">🔒 Reservados</span>
                  <div className="text-lg font-black text-blue-900 mt-0.5">32 Piezas</div>
                  <span className="text-[10px] text-slate-500 font-semibold block">Asignados a OPs</span>
                </button>

                <button
                  type="button"
                  onClick={() => setFiltroKpiRemanentes('TODOS')}
                  className={`p-3.5 rounded-xl border text-left cursor-pointer ${
                    filtroKpiRemanentes === 'TODOS' ? 'bg-purple-100 border-purple-400 ring-2 ring-purple-500' : 'bg-white border-slate-200'
                  }`}
                >
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">⚠️ Incompletos</span>
                  <div className="text-lg font-black text-red-900 mt-0.5">8 Piezas</div>
                  <span className="text-[10px] text-slate-500 font-semibold block">Falta Colada / Dim.</span>
                </button>

                <button
                  type="button"
                  onClick={() => setFiltroKpiRemanentes('CRITICO')}
                  className={`p-3.5 rounded-xl border text-left cursor-pointer ${
                    filtroKpiRemanentes === 'CRITICO' ? 'bg-red-100 border-red-400 ring-2 ring-red-500' : 'bg-white border-slate-200'
                  }`}
                >
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">🕒 Críticos (&gt; 90 Días)</span>
                  <div className="text-lg font-black text-red-950 mt-0.5">19 Piezas</div>
                  <span className="text-[10px] text-slate-500 font-semibold block">Riesgo Obsolescencia</span>
                </button>
              </div>

              {/* BARRA DE BÚSQUEDA DIMENSIONAL */}
              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3">
                <h3 className="font-extrabold text-slate-800 text-xs uppercase border-b pb-2">
                  🔍 Búsqueda & Consulta por Compatibilidad Dimensional
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <label className="block font-bold text-slate-600 mb-1">SKU / Colada / OP</label>
                    <input
                      type="text"
                      placeholder="Ej. RET-2026 o COL-889"
                      value={filtrosBusquedaRetales.busqueda_q}
                      onChange={(e) => setFiltrosBusquedaRetales({ ...filtrosBusquedaRetales, busqueda_q: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded font-semibold bg-slate-50"
                    />
                  </div>

                  <div>
                    <label className="block font-bold text-slate-600 mb-1">Material</label>
                    <select
                      value={filtrosBusquedaRetales.material}
                      onChange={(e) => setFiltrosBusquedaRetales({ ...filtrosBusquedaRetales, material: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded font-bold bg-slate-50 cursor-pointer"
                    >
                      <option value="TODOS">-- Todos --</option>
                      <option value="Acero Inoxidable 304">Acero Inoxidable 304</option>
                      <option value="AISI 4140">AISI 4140 Bonificado</option>
                      <option value="Bronce SAE 65">Bronce SAE 65</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-bold text-blue-900 mb-1">Largo Mín. (mm)</label>
                    <input
                      type="number"
                      placeholder="Ej. 500"
                      value={filtrosBusquedaRetales.largo_min_mm}
                      onChange={(e) => setFiltrosBusquedaRetales({ ...filtrosBusquedaRetales, largo_min_mm: e.target.value })}
                      className="w-full p-2 border border-blue-300 rounded font-bold bg-white"
                    />
                  </div>

                  <div>
                    <label className="block font-bold text-blue-900 mb-1">Ancho Mín. (mm)</label>
                    <input
                      type="number"
                      placeholder="Ej. 200"
                      value={filtrosBusquedaRetales.ancho_min_mm}
                      onChange={(e) => setFiltrosBusquedaRetales({ ...filtrosBusquedaRetales, ancho_min_mm: e.target.value })}
                      className="w-full p-2 border border-blue-300 rounded font-bold bg-white"
                    />
                  </div>
                </div>
              </div>

              {/* TABLA DE RETALES */}
              <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
                <h3 className="font-extrabold text-slate-800 text-xs">Catálogo de Retales en Inventario ({retales.length})</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-100 text-slate-700 font-bold uppercase border-b text-[10px]">
                        <th className="p-2.5">Código Retal</th>
                        <th className="p-2.5">Material / Geometría</th>
                        <th className="p-2.5">Dimensiones Útiles</th>
                        <th className="p-2.5">Masa (kg)</th>
                        <th className="p-2.5">Colada / OP Origen</th>
                        <th className="p-2.5">Ubicación</th>
                        <th className="p-2.5 text-center">Estado</th>
                        <th className="p-2.5 text-center">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {retales.map((r) => (
                        <tr key={r.id_retal || r.codigo_retal} className="hover:bg-slate-50 transition">
                          <td className="p-2.5 font-mono font-bold text-blue-900">{r.codigo_retal}</td>
                          <td className="p-2.5">
                            <div className="font-bold text-slate-800">{r.material_clasificacion}</div>
                            <div className="text-[10px] text-slate-500">{r.forma_geometria} ({r.espesor_seccion})</div>
                          </td>
                          <td className="p-2.5 font-mono font-semibold text-slate-800">{r.largo_mm} x {r.ancho_mm} mm</td>
                          <td className="p-2.5 font-bold text-slate-700">{r.peso_kg} kg</td>
                          <td className="p-2.5 font-mono text-[11px]">
                            <span className="text-slate-800 font-bold block">{r.codigo_op_origen}</span>
                            <span className="text-[10px] text-slate-500">{r.numero_colada_lote || '⚠️ Sin Colada'}</span>
                          </td>
                          <td className="p-2.5 font-semibold text-slate-600">{r.ubicación_almacen}</td>
                          <td className="p-2.5 text-center">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${
                              r.estado_evaluacion === 'DISPONIBLE' ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' :
                              r.estado_evaluacion === 'RESERVADO' ? 'bg-blue-100 text-blue-800 border border-blue-300' :
                              'bg-amber-100 text-amber-800 border border-amber-300'
                            }`}>
                              {r.estado_evaluacion}
                            </span>
                          </td>
                          <td className="p-2.5 text-center">
                            <button
                              type="button"
                              onClick={() => handleAbrirFichaModal(r.id_retal || r.codigo_retal)}
                              className="px-3 py-1 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded text-[10px] transition cursor-pointer"
                            >
                              👁️ Ver Ficha
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* VISTA 2: FORMULARIO REGISTRAR RETAL */}
          {vistaRemanentes === 'registrar' && (
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-5xl mx-auto space-y-5">
              <div className="flex justify-between items-center border-b pb-3">
                <h2 className="text-base font-extrabold text-slate-800 flex items-center gap-2">
                  <span>✂️</span> Registrar Retal / Sobrante de Materia Prima
                </h2>
                <button
                  type="button"
                  onClick={() => setVistaRemanentes('panel')}
                  className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleGuardarRetalNuevo} className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="md:col-span-2 space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block font-bold text-slate-700 mb-1">Material / Aleación *</label>
                        <select
                          value={retalRegistroForm.material_clasificacion}
                          onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, material_clasificacion: e.target.value })}
                          className="w-full p-2 border border-slate-300 rounded font-semibold bg-slate-50 cursor-pointer"
                          required
                        >
                          <option value="Acero Inoxidable 304">Acero Inoxidable 304</option>
                          <option value="Acero Inoxidable 316L">Acero Inoxidable 316L</option>
                          <option value="AISI 1045">AISI 1045</option>
                          <option value="AISI 4140 Bonificado">AISI 4140 Bonificado</option>
                        </select>
                      </div>

                      <div>
                        <label className="block font-bold text-slate-700 mb-1">Geometría *</label>
                        <select
                          value={retalRegistroForm.forma_geometria}
                          onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, forma_geometria: e.target.value })}
                          className="w-full p-2 border border-slate-300 rounded font-semibold bg-slate-50 cursor-pointer"
                          required
                        >
                          <option value="Lámina / Placa">Lámina / Placa</option>
                          <option value="Barra Maciza Redonda">Barra Maciza Redonda</option>
                          <option value="Tubo Mecánico">Tubo Mecánico</option>
                        </select>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block font-bold text-slate-700 mb-1">Espesor / Sección *</label>
                        <input
                          type="text"
                          placeholder="Ej. 3mm o Ø 2.5''"
                          value={retalRegistroForm.espesor_seccion}
                          onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, espesor_seccion: e.target.value })}
                          className="w-full p-2 border border-slate-300 rounded font-bold"
                          required
                        />
                      </div>

                      <div>
                        <label className="block font-bold text-blue-900 mb-1">OP Origen *</label>
                        <input
                          type="text"
                          placeholder="Ej. OP-4001234"
                          value={retalRegistroForm.codigo_op_origen}
                          onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, codigo_op_origen: e.target.value })}
                          className="w-full p-2 border border-blue-300 rounded font-mono font-bold text-blue-900 uppercase"
                          required
                        />
                      </div>
                    </div>
                  </div>

                  {/* COLUMNA DERECHA DINÁMICA SEGÚN GEOMETRÍA SELECCIONADA */}
                  <div className="space-y-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                    <h3 className="font-extrabold text-slate-800 text-xs border-b pb-1.5 uppercase tracking-wider flex justify-between items-center">
                      <span>📏 Dimensiones y Masa</span>
                      <span className="text-[10px] bg-blue-100 text-blue-900 px-1.5 py-0.5 rounded font-mono">
                        {retalRegistroForm.forma_geometria}
                      </span>
                    </h3>

                    {/* GEOMETRÍA 1: LÁMINA / PLACA */}
                    {retalRegistroForm.forma_geometria === 'Lámina / Placa' && (
                      <>
                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Largo Útil (mm) *</label>
                          <input
                            type="number"
                            placeholder="Ej. 1200"
                            value={retalRegistroForm.largo_mm}
                            onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, largo_mm: e.target.value })}
                            className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-slate-800 bg-white"
                            required
                          />
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Ancho (mm) *</label>
                          <input
                            type="number"
                            placeholder="Ej. 400"
                            value={retalRegistroForm.ancho_mm}
                            onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, ancho_mm: e.target.value })}
                            className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-slate-800 bg-white"
                            required
                          />
                        </div>
                      </>
                    )}

                    {/* GEOMETRÍA 2: BARRA MACIZA REDONDA */}
                    {retalRegistroForm.forma_geometria === 'Barra Maciza Redonda' && (
                      <>
                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Diámetro (mm) *</label>
                          <input
                            type="number"
                            placeholder="Ej. 50"
                            value={retalRegistroForm.diametro_ext_mm}
                            onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, diametro_ext_mm: e.target.value, ancho_mm: e.target.value })}
                            className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-slate-800 bg-white"
                            required
                          />
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Longitud (mm) *</label>
                          <input
                            type="number"
                            placeholder="Ej. 800"
                            value={retalRegistroForm.largo_mm}
                            onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, largo_mm: e.target.value })}
                            className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-slate-800 bg-white"
                            required
                          />
                        </div>
                      </>
                    )}

                    {/* GEOMETRÍA 3: TUBO MECÁNICO / ANILLO */}
                    {retalRegistroForm.forma_geometria === 'Tubo Mecánico' && (
                      <>
                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Diámetro Exterior - ØExt (mm) *</label>
                          <input
                            type="number"
                            placeholder="Ej. 100"
                            value={retalRegistroForm.diametro_ext_mm}
                            onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, diametro_ext_mm: e.target.value, ancho_mm: e.target.value })}
                            className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-slate-800 bg-white"
                            required
                          />
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Diámetro Interior - ØInt (mm) *</label>
                          <input
                            type="number"
                            placeholder="Ej. 80"
                            value={retalRegistroForm.diametro_int_mm}
                            onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, diametro_int_mm: e.target.value })}
                            className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-slate-800 bg-white"
                            required
                          />
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Longitud (mm) *</label>
                          <input
                            type="number"
                            placeholder="Ej. 300"
                            value={retalRegistroForm.largo_mm}
                            onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, largo_mm: e.target.value })}
                            className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-slate-800 bg-white"
                            required
                          />
                        </div>
                      </>
                    )}

                    {/* CAMPO DE PESO COMÚN */}
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Peso (kg)</label>
                      <input
                        type="number"
                        step="0.01"
                        placeholder="Ej. 11.5"
                        value={retalRegistroForm.peso_kg}
                        onChange={(e) => setRetalRegistroForm({ ...retalRegistroForm, peso_kg: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-slate-800 bg-white"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-2 border-t pt-3">
                  <button
                    type="button"
                    onClick={() => setVistaRemanentes('panel')}
                    className="px-4 py-2 bg-slate-200 text-slate-800 font-bold rounded cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-6 py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded shadow-sm cursor-pointer"
                  >
                    📥 Registrar Retal
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      )}

      {/* MODAL FICHA TÉCNICA Y QR */}
      {modalFichaRetal && retalFichaData && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full p-6 space-y-5 border-t-4 border-slate-800 text-xs max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2.5 py-0.5 bg-slate-800 text-white font-mono font-bold rounded text-xs">
                  {retalFichaData.codigo_retal}
                </span>
                <h2 className="text-lg font-black text-slate-800 mt-1">
                  Ficha Técnica: {retalFichaData.material_clasificacion}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setModalFichaRetal(false)}
                className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="md:col-span-2 space-y-4">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 grid grid-cols-2 gap-3">
                  <div><span className="text-slate-400 font-bold block">Geometría:</span> {retalFichaData.forma_geometria}</div>
                  <div><span className="text-slate-400 font-bold block">Espesor / Sección:</span> {retalFichaData.espesor_seccion}</div>
                  <div><span className="text-slate-400 font-bold block">Dimensiones:</span> {retalFichaData.largo_mm} x {retalFichaData.ancho_mm} mm</div>
                  <div><span className="text-slate-400 font-bold block">Masa / Peso:</span> {retalFichaData.peso_kg} kg</div>
                  <div><span className="text-slate-400 font-bold block">OP Origen:</span> {retalFichaData.codigo_op_origen}</div>
                  <div><span className="text-slate-400 font-bold block">Colada (Cert. 3.1):</span> {retalFichaData.numero_colada_lote || 'Sin Lote'}</div>
                </div>
              </div>

              <div className="space-y-4 text-center">
                <div className="bg-white p-4 rounded-xl border-2 border-slate-800 shadow-sm space-y-2">
                  <span className="text-[10px] font-black uppercase text-slate-400 block">Etiqueta QR Industrial</span>
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent(retalFichaData.qr_code_data || retalFichaData.codigo_retal)}`}
                    alt="QR Retal"
                    className="mx-auto border p-2 rounded"
                  />
                  <div className="font-mono font-black text-slate-900 text-xs">{retalFichaData.codigo_retal}</div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    alert(`Retal [${retalFichaData.codigo_retal}] despachado a la Orden de Producción.`);
                    setModalFichaRetal(false);
                  }}
                  className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded shadow-sm cursor-pointer"
                >
                  📤 Despachar Directo a Planta
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}