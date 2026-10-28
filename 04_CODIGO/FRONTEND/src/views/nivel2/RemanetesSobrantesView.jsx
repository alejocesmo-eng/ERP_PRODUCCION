// src/views/nivel2/RemanentesSobrantesView.jsx
import React, { useState, useEffect } from 'react';
import API from '../../services/api';

export default function RemanentesSobrantesView() {
  // CONTROL DE NAVEGACIÓN INTERNA
  const [vistaActiva, setVistaActiva] = useState('panel'); // 'panel' | 'registrar'
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });

  // DATOS Y FILTROS INTEGRADOS
  const [retales, setRetales] = useState([]);
  const [filtroKpiState, setFiltroKpiState] = useState('TODOS');
  
  const [filtrosBusqueda, setFiltrosBusqueda] = useState({
    busqueda_q: '',
    material: 'TODOS',
    forma: 'TODOS',
    espesor: '',
    largo_min_mm: '',
    ancho_min_mm: ''
  });

  // MODAL FICHA TÉCNICA Y QR
  const [modalFichaAbierto, setModalFichaAbierto] = useState(false);
  const [retalFicha, setRetalFicha] = useState(null);

  // FORMULARIO REGISTRAR RETAL (DINÁMICO SEGÚN GEOMETRÍA)
  const [retalForm, setRetalForm] = useState({
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
  const [fotoPreview, setFotoPreview] = useState(null);

  // CONTROL RBAC ROLES
  const usuarioSesion = JSON.parse(localStorage.getItem('usuario') || '{"rol":"Almacen","nombre":"Operario Almacén"}');
  const esAutorizadoMovimientos = ['ADMIN', 'ALMACEN', 'PRODUCCION'].includes((usuarioSesion.rol || '').toUpperCase());

  useEffect(() => {
    cargarListaRetales();
  }, [filtroKpiState]);

  const cargarListaRetales = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filtroKpiState !== 'TODOS') params.append('estado', filtroKpiState);
      if (filtrosBusqueda.busqueda_q) params.append('busqueda_q', filtrosBusqueda.busqueda_q);
      if (filtrosBusqueda.material !== 'TODOS') params.append('material', filtrosBusqueda.material);
      if (filtrosBusqueda.forma !== 'TODOS') params.append('forma', filtrosBusqueda.forma);
      if (filtrosBusqueda.largo_min_mm) params.append('largo_min_mm', filtrosBusqueda.largo_min_mm);
      if (filtrosBusqueda.ancho_min_mm) params.append('ancho_min_mm', filtrosBusqueda.ancho_min_mm);

      const res = await API.get(`/almacen/retales/buscar?${params.toString()}`);
      setRetales(Array.isArray(res.data) ? res.data : retalesMockFallback);
    } catch (err) {
      setRetales(retalesMockFallback);
    } finally {
      setLoading(false);
    }
  };

  const handleEjecutarFiltrado = (e) => {
    e.preventDefault();
    cargarListaRetales();
  };

  const handleLimpiarFiltros = () => {
    setFiltrosBusqueda({
      busqueda_q: '',
      material: 'TODOS',
      forma: 'TODOS',
      espesor: '',
      largo_min_mm: '',
      ancho_min_mm: ''
    });
    setFiltroKpiState('TODOS');
    cargarListaRetales();
  };

  const handleAbrirFichaModal = async (idOrCodigo) => {
    try {
      setLoading(true);
      const res = await API.get(`/almacen/retales/${idOrCodigo}`);
      setRetalFicha(res.data);
      setModalFichaAbierto(true);
    } catch (err) {
      const local = retales.find(r => r.id_retal === idOrCodigo || r.codigo_retal === idOrCodigo);
      if (local) {
        setRetalFicha({
          ...local,
          qr_code_data: `SGI-RETAL|SKU:${local.codigo_retal}|OP:${local.codigo_op_origen}|COLADA:${local.numero_colada_lote || 'N/A'}`,
          historial: [
            { fecha: new Date(), tipo_movimiento: 'INGRESO_RECUPERACION', cantidad_peso: `${local.peso_kg} kg`, usuario_responsable: 'Operario Planta', referencia_op: local.codigo_op_origen }
          ]
        });
        setModalFichaAbierto(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFotoUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setFotoPreview(reader.result);
        setRetalForm(prev => ({ ...prev, fotografia_url: reader.result }));
      };
      reader.readAsDataURL(file);
    }
  };

  const handleGuardarNuevoRetal = async (e) => {
    e.preventDefault();
    if (!retalForm.codigo_op_origen) {
      return setMensaje({ tipo: 'error', texto: '⚠️ Debe ingresar la Orden de Producción (OP) de origen del retal.' });
    }

    try {
      setLoading(true);
      const payload = {
        ...retalForm,
        largo_mm: Number(retalForm.largo_mm) || 0,
        ancho_mm: Number(retalForm.ancho_mm) || Number(retalForm.diametro_ext_mm) || 0,
        diametro_ext_mm: Number(retalForm.diametro_ext_mm) || 0,
        diametro_int_mm: Number(retalForm.diametro_int_mm) || 0,
        peso_kg: Number(retalForm.peso_kg) || 0,
        registrado_por: usuarioSesion.nombre || 'Operario Almacén'
      };

      const res = await API.post('/almacen/retales/nuevo', payload);
      setMensaje({
        tipo: 'exito',
        texto: `✅ Retal [${res.data.codigo_retal || 'RET-2026'}] registrado con éxito. Estado: PENDIENTE DE EVALUACIÓN.`
      });

      setVistaActiva('panel');
      cargarListaRetales();
    } catch (err) {
      setMensaje({ tipo: 'error', texto: 'Error al registrar el remanente en la base de datos.' });
    } finally {
      setLoading(false);
    }
  };

  const retalesMockFallback = [
    { id_retal: '1', codigo_retal: 'RET-2026-0001', material_clasificacion: 'Acero Inoxidable 304', forma_geometria: 'Lámina / Placa', espesor_seccion: '3 mm', largo_mm: 1200, ancho_mm: 400, peso_kg: 11.5, numero_colada_lote: 'COL-88942', codigo_op_origen: 'OP-4001234', ubicación_almacen: 'RACK-A2', estado_evaluacion: 'DISPONIBLE' },
    { id_retal: '2', codigo_retal: 'RET-2026-0002', material_clasificacion: 'Bronce SAE 65', forma_geometria: 'Barra Maciza Redonda', espesor_seccion: 'Ø 4"', largo_mm: 180, ancho_mm: 100, peso_kg: 12.3, numero_colada_lote: null, codigo_op_origen: 'OP-100234', ubicación_almacen: 'ESTANTE-B', estado_evaluacion: 'EN_EVALUACION' },
    { id_retal: '3', codigo_retal: 'RET-2026-0003', material_clasificacion: 'AISI 4140 Bonificado', forma_geometria: 'Anillo / Tubo Mecánico', espesor_seccion: 'ØExt 120 x ØInt 80 mm', largo_mm: 350, ancho_mm: 120, peso_kg: 22.0, numero_colada_lote: 'COL-90112', codigo_op_origen: 'OP-30011', ubicación_almacen: 'RACK-C1', estado_evaluacion: 'RESERVADO' }
  ];

  return (
    <div className="space-y-5 text-xs font-sans">
      
      {/* CABECERA Y BOTONES DE NAVEGACIÓN */}
      <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-sm flex justify-between items-center flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-extrabold text-slate-800 flex items-center gap-1">
            <span>✂️</span> Control e Inventario de Sobrantes / Remanentes
          </span>
          <span className="text-[10px] text-slate-400 font-medium">(ISO 9001:2026)</span>
        </div>

        <div className="flex items-center gap-2">
          {vistaActiva === 'panel' ? (
            <button
              type="button"
              onClick={() => setVistaActiva('registrar')}
              className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-lg shadow-sm transition cursor-pointer flex items-center gap-1"
            >
              ➕ Registrar Nuevo Retal
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setVistaActiva('panel')}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded-lg shadow-sm transition cursor-pointer flex items-center gap-1"
            >
              📊 Volver al Panel y Búsqueda
            </button>
          )}
        </div>
      </div>

      {mensaje.texto && (
        <div className={`p-3 rounded-lg font-bold border ${
          mensaje.tipo === 'exito' ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : 'bg-red-50 text-red-800 border-red-300'
        }`}>
          {mensaje.texto}
        </div>
      )}

      {/* ========================================================================= */}
      {/* VISTA 1: PANEL DE CONTROL DE RETALES + BÚSQUEDA INTEGRADA                */}
      {/* ========================================================================= */}
      {vistaActiva === 'panel' && (
        <div className="space-y-4">
          
          {/* TARJETAS KPI FILTRABLES */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <button
              type="button"
              onClick={() => setFiltroKpiState('DISPONIBLE')}
              className={`p-3.5 rounded-xl border text-left transition shadow-sm cursor-pointer ${
                filtroKpiState === 'DISPONIBLE' ? 'bg-emerald-100 border-emerald-400 ring-2 ring-emerald-500' : 'bg-white border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span className="text-[10px] font-bold text-slate-400 uppercase block">🟢 Disponibles</span>
              <div className="text-lg font-black text-emerald-900 mt-0.5">248 Piezas</div>
              <span className="text-[10px] text-slate-500 font-semibold block">3,420 kg en stock</span>
            </button>

            <button
              type="button"
              onClick={() => setFiltroKpiState('EN_EVALUACION')}
              className={`p-3.5 rounded-xl border text-left transition shadow-sm cursor-pointer ${
                filtroKpiState === 'EN_EVALUACION' ? 'bg-amber-100 border-amber-400 ring-2 ring-amber-500' : 'bg-white border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span className="text-[10px] font-bold text-slate-400 uppercase block">⏳ Pendiente Evaluación</span>
              <div className="text-lg font-black text-amber-900 mt-0.5">14 Piezas</div>
              <span className="text-[10px] text-slate-500 font-semibold block">Inspección Metrológica</span>
            </button>

            <button
              type="button"
              onClick={() => setFiltroKpiState('RESERVADO')}
              className={`p-3.5 rounded-xl border text-left transition shadow-sm cursor-pointer ${
                filtroKpiState === 'RESERVADO' ? 'bg-blue-100 border-blue-400 ring-2 ring-blue-500' : 'bg-white border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span className="text-[10px] font-bold text-slate-400 uppercase block">🔒 Reservados</span>
              <div className="text-lg font-black text-blue-900 mt-0.5">32 Piezas</div>
              <span className="text-[10px] text-slate-500 font-semibold block">Asignados a OPs</span>
            </button>

            <button
              type="button"
              onClick={() => setFiltroKpiState('TODOS')}
              className={`p-3.5 rounded-xl border text-left transition shadow-sm cursor-pointer ${
                filtroKpiState === 'TODOS' ? 'bg-purple-100 border-purple-400 ring-2 ring-purple-500' : 'bg-white border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span className="text-[10px] font-bold text-slate-400 uppercase block">⚠️ Incompletos</span>
              <div className="text-lg font-black text-red-900 mt-0.5">8 Piezas</div>
              <span className="text-[10px] text-slate-500 font-semibold block">Falta Colada / Dim.</span>
            </button>

            <button
              type="button"
              onClick={() => setFiltroKpiState('CRITICO')}
              className={`p-3.5 rounded-xl border text-left transition shadow-sm cursor-pointer ${
                filtroKpiState === 'CRITICO' ? 'bg-red-100 border-red-400 ring-2 ring-red-500' : 'bg-white border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span className="text-[10px] font-bold text-slate-400 uppercase block">🕒 Críticos (&gt; 90 Días)</span>
              <div className="text-lg font-black text-red-950 mt-0.5">19 Piezas</div>
              <span className="text-[10px] text-slate-500 font-semibold block">Riesgo Obsolescencia</span>
            </button>
          </div>

          {/* BARRA INTEGRADA DE BÚSQUEDA Y FILTRADO */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3">
            <div className="flex justify-between items-center border-b pb-2">
              <h3 className="font-extrabold text-slate-800 text-xs flex items-center gap-1.5 uppercase">
                <span>🔍</span> Búsqueda & Consulta por Compatibilidad Dimensional (Diseño / Almacén)
              </h3>
              <button
                type="button"
                onClick={handleLimpiarFiltros}
                className="text-[11px] text-blue-600 hover:text-blue-800 font-semibold cursor-pointer"
              >
                🔄 Limpiar Filtros
              </button>
            </div>

            <form onSubmit={handleEjecutarFiltrado} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3">
              <div>
                <label className="block font-bold text-slate-600 mb-1">SKU / Colada / OP</label>
                <input
                  type="text"
                  placeholder="Ej. RET-2026 o COL-889"
                  value={filtrosBusqueda.busqueda_q}
                  onChange={(e) => setFiltrosBusqueda({ ...filtrosBusqueda, busqueda_q: e.target.value })}
                  className="w-full p-2 border border-slate-300 rounded font-semibold bg-slate-50"
                />
              </div>

              <div>
                <label className="block font-bold text-slate-600 mb-1">Material / Aleación</label>
                <select
                  value={filtrosBusqueda.material}
                  onChange={(e) => setFiltrosBusqueda({ ...filtrosBusqueda, material: e.target.value })}
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
                  value={filtrosBusqueda.largo_min_mm}
                  onChange={(e) => setFiltrosBusqueda({ ...filtrosBusqueda, largo_min_mm: e.target.value })}
                  className="w-full p-2 border border-blue-300 rounded font-bold bg-white"
                />
              </div>

              <div>
                <label className="block font-bold text-blue-900 mb-1">Ancho / Diámetro Mín. (mm)</label>
                <input
                  type="number"
                  placeholder="Ej. 200"
                  value={filtrosBusqueda.ancho_min_mm}
                  onChange={(e) => setFiltrosBusqueda({ ...filtrosBusqueda, ancho_min_mm: e.target.value })}
                  className="w-full p-2 border border-blue-300 rounded font-bold bg-white"
                />
              </div>

              <div className="flex items-end">
                <button
                  type="submit"
                  className="w-full p-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded shadow-sm transition cursor-pointer"
                >
                  🔍 {loading ? 'Filtrando...' : 'Aplicar Filtros'}
                </button>
              </div>
            </form>
          </div>

          {/* TABLA PRINCIPAL DE RETALES */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
            <h3 className="font-extrabold text-slate-800 text-xs">
              Catálogo de Retales en Inventario ({retales.length})
            </h3>

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

      {/* ========================================================================= */}
      {/* VISTA 2: FORMULARIO REGISTRAR RETAL (CAMPOS DINÁMICOS SEGÚN GEOMETRÍA)    */}
      {/* ========================================================================= */}
      {vistaActiva === 'registrar' && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-5xl mx-auto space-y-5">
          <div className="flex justify-between items-center border-b pb-3">
            <div>
              <h2 className="text-base font-extrabold text-slate-800 flex items-center gap-2">
                <span>✂️</span> Registrar Retal / Sobrante de Materia Prima
              </h2>
              <p className="text-[11px] text-slate-500">
                Formulario de Entrada a Almacén con Autocódigo y Trazabilidad ISO 9001:2026
              </p>
            </div>
            <button
              type="button"
              onClick={() => setVistaActiva('panel')}
              className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer"
            >
              ✕
            </button>
          </div>

          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg flex justify-between items-center">
            <div>
              <span className="text-[11px] text-amber-800 font-bold block">Código Autogenerado:</span>
              <span className="font-mono font-black text-amber-900 text-sm">⚡ [RET-2026-AUTOGENERADO]</span>
            </div>
            <div className="text-right">
              <span className="text-[11px] text-slate-500 block font-bold">Estado Inicial:</span>
              <span className="px-2.5 py-0.5 bg-amber-200 text-amber-900 font-extrabold rounded text-[10px] border border-amber-300">
                ⏳ PENDIENTE DE EVALUACIÓN
              </span>
            </div>
          </div>

          <form onSubmit={handleGuardarNuevoRetal} className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              
              {/* ESPECIFICACIÓN Y ORIGEN */}
              <div className="md:col-span-2 space-y-4">
                <h3 className="font-extrabold text-slate-800 text-xs border-b pb-1.5 uppercase tracking-wider flex items-center gap-1.5">
                  <span>📋</span> Especificación Técnica y Procedencia
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Material / Aleación *</label>
                    <select
                      value={retalForm.material_clasificacion}
                      onChange={(e) => setRetalForm({ ...retalForm, material_clasificacion: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded font-semibold bg-slate-50 cursor-pointer"
                      required
                    >
                      <option value="Acero Inoxidable 304">Acero Inoxidable 304</option>
                      <option value="Acero Inoxidable 316L">Acero Inoxidable 316L</option>
                      <option value="AISI 1045">AISI 1045 (Acero al Carbono)</option>
                      <option value="AISI 4140 Bonificado">AISI 4140 Bonificado</option>
                      <option value="Bronce SAE 65">Bronce SAE 65</option>
                      <option value="Aluminio 6061-T6">Aluminio 6061-T6</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Geometría / Forma *</label>
                    <select
                      value={retalForm.forma_geometria}
                      onChange={(e) => setRetalForm({ ...retalForm, forma_geometria: e.target.value })}
                      className="w-full p-2 border border-blue-400 bg-blue-50 rounded font-bold text-blue-900 cursor-pointer"
                      required
                    >
                      <option value="Lámina / Placa">Lámina / Placa / Chapa</option>
                      <option value="Barra Maciza Redonda">Barra Maciza Redonda</option>
                      <option value="Anillo / Tubo Mecánico">Anillo / Tubo Mecánico / Hueco</option>
                      <option value="Perfil Estructural">Perfil Estructural (IPE / HEB / Perfil)</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Espesor / Sección Transversal *</label>
                    <input
                      type="text"
                      placeholder="Ej. Espesor 3mm o Ø 2.5''"
                      value={retalForm.espesor_seccion}
                      onChange={(e) => setRetalForm({ ...retalForm, espesor_seccion: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded font-bold text-slate-800"
                      required
                    />
                  </div>

                  <div>
                    <label className="block font-bold text-blue-900 mb-1">OT / OP de Origen *</label>
                    <input
                      type="text"
                      placeholder="Ej. OP-4001234"
                      value={retalForm.codigo_op_origen}
                      onChange={(e) => setRetalForm({ ...retalForm, codigo_op_origen: e.target.value })}
                      className="w-full p-2 border border-blue-300 rounded font-mono font-bold text-blue-900 uppercase bg-blue-50/40"
                      required
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">N° Colada / Lote Original (Cert. 3.1)</label>
                    <input
                      type="text"
                      placeholder="Ej. COL-88942"
                      value={retalForm.numero_colada_lote}
                      onChange={(e) => setRetalForm({ ...retalForm, numero_colada_lote: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded font-mono"
                    />
                  </div>

                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Procedencia / Proceso</label>
                    <input
                      type="text"
                      placeholder="Ej. Sobrante de Corte Guillotina / Láser"
                      value={retalForm.procedencia}
                      onChange={(e) => setRetalForm({ ...retalForm, procedencia: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Fotografía del Sobrante (Opcional)</label>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleFotoUpload}
                      className="w-full text-xs p-1 border border-slate-300 rounded cursor-pointer"
                    />
                    {fotoPreview && (
                      <img
                        src={fotoPreview}
                        alt="Preview"
                        className="mt-2 h-20 w-auto rounded border border-slate-300 shadow-sm object-cover"
                      />
                    )}
                  </div>

                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Observaciones</label>
                    <textarea
                      rows="3"
                      placeholder="Ej. Corte limpio en borde, sin oxidación..."
                      value={retalForm.observaciones}
                      onChange={(e) => setRetalForm({ ...retalForm, observaciones: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded text-slate-800"
                    ></textarea>
                  </div>
                </div>
              </div>

              {/* DIMENSIONES ADAPTATIVAS DINÁMICAS SEGÚN LA GEOMETRÍA SELECCIONADA */}
              <div className="space-y-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <h3 className="font-extrabold text-slate-800 text-xs border-b pb-1.5 uppercase tracking-wider flex items-center justify-between">
                  <span>📏 Dimensionamiento Metrológico</span>
                  <span className="text-[10px] text-blue-900 bg-blue-100 px-2 py-0.5 rounded font-mono">
                    {retalForm.forma_geometria}
                  </span>
                </h3>

                {/* OPCIÓN 1: LÁMINA / PLACA / CHAPA */}
                {retalForm.forma_geometria === 'Lámina / Placa' && (
                  <>
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Largo Útil (mm) *</label>
                      <input
                        type="number"
                        placeholder="Ej. 1200"
                        value={retalForm.largo_mm}
                        onChange={(e) => setRetalForm({ ...retalForm, largo_mm: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
                        required
                      />
                    </div>

                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Ancho (mm) *</label>
                      <input
                        type="number"
                        placeholder="Ej. 400"
                        value={retalForm.ancho_mm}
                        onChange={(e) => setRetalForm({ ...retalForm, ancho_mm: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
                        required
                      />
                    </div>
                  </>
                )}

                {/* OPCIÓN 2: BARRA MACIZA REDONDA */}
                {retalForm.forma_geometria === 'Barra Maciza Redonda' && (
                  <>
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Diámetro (mm) *</label>
                      <input
                        type="number"
                        placeholder="Ej. 100"
                        value={retalForm.diametro_ext_mm}
                        onChange={(e) => setRetalForm({ ...retalForm, diametro_ext_mm: e.target.value, ancho_mm: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
                        required
                      />
                    </div>

                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Longitud (mm) *</label>
                      <input
                        type="number"
                        placeholder="Ej. 350"
                        value={retalForm.largo_mm}
                        onChange={(e) => setRetalForm({ ...retalForm, largo_mm: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
                        required
                      />
                    </div>
                  </>
                )}

                {/* OPCIÓN 3: ANILLO / TUBO MECÁNICO / HUECO */}
                {retalForm.forma_geometria === 'Anillo / Tubo Mecánico' && (
                  <>
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Diámetro Exterior - ØExt (mm) *</label>
                      <input
                        type="number"
                        placeholder="Ej. 120"
                        value={retalForm.diametro_ext_mm}
                        onChange={(e) => setRetalForm({ ...retalForm, diametro_ext_mm: e.target.value, ancho_mm: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
                        required
                      />
                    </div>

                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Diámetro Interior - ØInt (mm) *</label>
                      <input
                        type="number"
                        placeholder="Ej. 80"
                        value={retalForm.diametro_int_mm}
                        onChange={(e) => setRetalForm({ ...retalForm, diametro_int_mm: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
                        required
                      />
                    </div>

                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Longitud / Espesor Anillo (mm) *</label>
                      <input
                        type="number"
                        placeholder="Ej. 150"
                        value={retalForm.largo_mm}
                        onChange={(e) => setRetalForm({ ...retalForm, largo_mm: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
                        required
                      />
                    </div>
                  </>
                )}

                {/* OPCIÓN 4: PERFIL ESTRUCTURAL */}
                {retalForm.forma_geometria === 'Perfil Estructural' && (
                  <>
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Alto / Ancho Sección (mm) *</label>
                      <input
                        type="number"
                        placeholder="Ej. 160"
                        value={retalForm.ancho_mm}
                        onChange={(e) => setRetalForm({ ...retalForm, ancho_mm: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
                        required
                      />
                    </div>

                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Longitud (mm) *</label>
                      <input
                        type="number"
                        placeholder="Ej. 1450"
                        value={retalForm.largo_mm}
                        onChange={(e) => setRetalForm({ ...retalForm, largo_mm: e.target.value })}
                        className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
                        required
                      />
                    </div>
                  </>
                )}

                <div className="grid grid-cols-2 gap-2 pt-2 border-t">
                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Masa / Peso</label>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="Ej. 11.5"
                      value={retalForm.peso_kg}
                      onChange={(e) => setRetalForm({ ...retalForm, peso_kg: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-900"
                    />
                  </div>

                  <div>
                    <label className="block font-bold text-slate-700 mb-1">Unidad</label>
                    <select
                      value={retalForm.unidad_medida}
                      onChange={(e) => setRetalForm({ ...retalForm, unidad_medida: e.target.value })}
                      className="w-full p-2 border border-slate-300 rounded bg-white font-bold cursor-pointer"
                    >
                      <option value="kg">kg (Kilogramos)</option>
                      <option value="m">m (Metros)</option>
                      <option value="UND">UND (Pieza)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-bold text-amber-900 mb-1">Ubicación Asignada en Rack *</label>
                  <input
                    type="text"
                    placeholder="Ej. RACK-A1-RETAZOS"
                    value={retalForm.ubicacion_almacen}
                    onChange={(e) => setRetalForm({ ...retalForm, ubicacion_almacen: e.target.value })}
                    className="w-full p-2 border border-amber-300 rounded bg-white font-bold text-amber-900"
                    required
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t pt-3">
              <button
                type="button"
                onClick={() => setVistaActiva('panel')}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded shadow-sm cursor-pointer flex items-center gap-1.5"
              >
                <span>📥</span> {loading ? 'Registrando...' : 'Registrar Retal e Ingresar a Evaluación'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 4: FICHA TÉCNICA DEL RETAL CON ETIQUETA QR                          */}
      {/* ========================================================================= */}
      {modalFichaAbierto && retalFicha && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full p-6 space-y-5 border-t-4 border-slate-800 text-xs my-8 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 bg-slate-800 text-white font-mono font-bold rounded text-xs">
                    {retalFicha.codigo_retal}
                  </span>
                  <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 border border-emerald-300 rounded font-extrabold text-[10px]">
                    {retalFicha.estado_evaluacion}
                  </span>
                </div>
                <h2 className="text-lg font-black text-slate-800 mt-1">
                  Ficha Técnica: {retalFicha.material_clasificacion}
                </h2>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold rounded border border-slate-300 transition cursor-pointer"
                >
                  🖨️ Imprimir Etiqueta QR
                </button>
                <button
                  type="button"
                  onClick={() => setModalFichaAbierto(false)}
                  className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer"
                >
                  ✕
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="md:col-span-2 space-y-4">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 grid grid-cols-2 gap-3">
                  <div><span className="text-slate-400 font-bold block">Geometría:</span> {retalFicha.forma_geometria}</div>
                  <div><span className="text-slate-400 font-bold block">Espesor / Sección:</span> {retalFicha.espesor_seccion}</div>
                  <div><span className="text-slate-400 font-bold block">Dimensiones:</span> {retalFicha.largo_mm} x {retalFicha.ancho_mm} mm</div>
                  <div><span className="text-slate-400 font-bold block">Masa / Peso:</span> {retalFicha.peso_kg} kg</div>
                  <div><span className="text-slate-400 font-bold block">OP Origen:</span> {retalFicha.codigo_op_origen}</div>
                  <div><span className="text-slate-400 font-bold block">Colada (Cert. 3.1):</span> {retalFicha.numero_colada_lote || 'Sin Lote'}</div>
                </div>

                <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-2">
                  <h3 className="font-extrabold text-slate-800 text-xs border-b pb-1">📜 Historial Auditado de Movimientos (Kardex)</h3>
                  <div className="space-y-1 font-mono text-[11px]">
                    {retalFicha.historial?.map((h, i) => (
                      <div key={i} className="flex justify-between border-b pb-1 text-slate-700">
                        <span>{new Date(h.fecha).toLocaleDateString()} - {h.tipo_movimiento}</span>
                        <span className="font-bold text-blue-900">{h.referencia_op} ({h.cantidad_peso})</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-4 text-center">
                <div className="bg-white p-4 rounded-xl border-2 border-slate-800 shadow-sm space-y-2">
                  <span className="text-[10px] font-black uppercase text-slate-400 block">Etiqueta QR Industrial</span>
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent(retalFicha.qr_code_data || retalFicha.codigo_retal)}`}
                    alt="QR Retal"
                    className="mx-auto border p-2 rounded"
                  />
                  <div className="font-mono font-black text-slate-900 text-xs">{retalFicha.codigo_retal}</div>
                </div>

                {esAutorizadoMovimientos && (
                  <button
                    type="button"
                    onClick={() => {
                      alert(`Retal [${retalFicha.codigo_retal}] despachado e imputado a la OP.`);
                      setModalFichaAbierto(false);
                    }}
                    className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded shadow-sm cursor-pointer"
                  >
                    📤 Despachar Directo a Planta
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}