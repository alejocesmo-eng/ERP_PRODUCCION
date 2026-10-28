// src/components/modals/ModalNuevaCotizacion.jsx
import React, { useState, useEffect } from 'react';
import API from '../../services/api';

const TIPOS_FABRICACION = [
  { valor: 'BAJO_PLANO', etiqueta: '📐 Bajo Plano' },
  { valor: 'MUESTRA_FISICA', etiqueta: '📏 Bajo Muestra' },
  { valor: 'ESTANDAR', etiqueta: '📦 Estándar' },
  { valor: 'POR_DEFINIR', etiqueta: '🔍 Por Definir (Visita Técnica)' }
];

const NOTA_VISITA_TECNICA =
  '📌 NOTA TÉCNICA: El tiempo de fabricación comenzará a regir únicamente una vez se cuente con la información técnica completa y validada. Se requiere agendar visita técnica en las instalaciones del cliente para el respectivo levantamiento dimensional y diagnóstico por parte de nuestro personal y la confirmación explicita del cliente.';

export default function ModalNuevaCotizacion({ isOpen, onClose, onCotizacionGuardada, onAbrirCrearSocio }) {
  if (!isOpen) return null;

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [listaSocios, setListaSocios] = useState([]);
  const [modoVistaPrevia, setModoVistaPrevia] = useState(false);

  const fechaHoyStr = new Date().toISOString().split('T')[0];
  const anioActual = new Date().getFullYear();
  const fechaCompromisoInicial = new Date(Date.now() + 15 * 86400000).toISOString().split('T')[0];

  const [cabecera, setCabecera] = useState({
    id_socio: null,
    numero_cotizacion: `COT-${anioActual}-0001`,
    codigo_cliente: '',
    razon_social: '',
    nit: '',
    contacto: '',
    telefono: '',
    email: '',
    direccion: '',
    ciudad: 'Medellín / Funza',
    referencia_global: '',
    fecha_emision: fechaHoyStr,
    fecha_vigencia: new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0],
    fecha_compromiso: fechaCompromisoInicial,
    condiciones_pago: '30 Días',
    moneda: 'COP',
    condiciones_comerciales: 'Puesto en planta cliente. Forma de pago según acuerdo...'
  });

  const [posiciones, setPosiciones] = useState([
    {
      id: 1,
      numero_producto: 'A-01',
      descripcion: '',
      especificaciones: '*Incluye:\n- Fabricación y mecanizado de precisión\n*No Incluye:\n- Montaje en sitio',
      expandirNota: false,
      tipo_fabricacion: 'BAJO_PLANO',
      cantidad: 1,
      unidad: 'UND',
      precio_unitario: 0,
      descuento_pct: 0,
      tipo_impuesto: 'IVA_19',
      vinculo_plano_catalogo: ''
    }
  ]);

  // Obtener consecutivo y lista de clientes
  useEffect(() => {
    const cargarDatosIniciales = async () => {
      try {
        const resSocios = await API.get('/socios-negocio/?tipo=CLIENTE');
        if (Array.isArray(resSocios.data)) {
          setListaSocios(resSocios.data);
        }
      } catch (e) {
        console.warn('Carga remota de socios omitida, operando en modo local.');
      }

      try {
        const resConsecutivo = await API.get('/ventas/cotizaciones/siguiente-consecutivo');
        if (resConsecutivo.data?.siguiente_numero) {
          setCabecera(prev => ({ ...prev, numero_cotizacion: resConsecutivo.data.siguiente_numero }));
        }
      } catch (e) {
        try {
          const resCot = await API.get('/ventas/cotizaciones/');
          if (Array.isArray(resCot.data)) {
            const total = resCot.data.length + 1;
            const nuevoConsecutivo = `COT-${anioActual}-${String(total).padStart(4, '0')}`;
            setCabecera(prev => ({ ...prev, numero_cotizacion: nuevoConsecutivo }));
          }
        } catch (errList) {
          console.warn('Operando con consecutivo local sugerido.');
        }
      }
    };

    cargarDatosIniciales();
  }, [anioActual]);

  const handleSeleccionarSocio = (codigoSeleccionado) => {
    const socioEncontrado = listaSocios.find(
      s => (s.codigo_socio || s.codigo_cliente) === codigoSeleccionado
    );
    if (socioEncontrado) {
      setCabecera(prev => ({
        ...prev,
        id_socio: socioEncontrado.id_socio || null,
        codigo_cliente: socioEncontrado.codigo_socio || socioEncontrado.codigo_cliente,
        razon_social: socioEncontrado.razon_social || socioEncontrado.nombre,
        nit: socioEncontrado.nit_rut || socioEncontrado.nit || '',
        contacto: socioEncontrado.contacto_nombre || '',
        telefono: socioEncontrado.telefono || '',
        email: socioEncontrado.email || '',
        direccion: socioEncontrado.direccion || '',
        ciudad: socioEncontrado.ciudad || prev.ciudad,
        condiciones_pago: socioEncontrado.condiciones_pago || prev.condiciones_pago
      }));
    } else {
      setCabecera(prev => ({ ...prev, id_socio: null, codigo_cliente: codigoSeleccionado }));
    }
  };

  const handleCambioCabecera = (campo, valor) => {
    setCabecera(prev => ({ ...prev, [campo]: valor }));
  };

  const toggleExpandirNota = (id) => {
    setPosiciones(prev =>
      prev.map(item => (item.id === id ? { ...item, expandirNota: !item.expandirNota } : item))
    );
  };

  const handleCambioPosicion = (id, campo, valor) => {
    setPosiciones(prev => {
      const nuevasPosiciones = prev.map(item => {
        if (item.id !== id) return item;
        return { ...item, [campo]: valor };
      });

      const requiereVisita = nuevasPosiciones.some(p => p.tipo_fabricacion === 'POR_DEFINIR');
      setCabecera(prevCab => {
        let textoObs = prevCab.condiciones_comerciales || '';
        if (requiereVisita) {
          if (!textoObs.includes('📌 NOTA TÉCNICA')) {
            textoObs = textoObs ? `${textoObs}\n\n${NOTA_VISITA_TECNICA}` : NOTA_VISITA_TECNICA;
          }
        }
        return { ...prevCab, condiciones_comerciales: textoObs };
      });

      return nuevasPosiciones;
    });
  };

  const handleAgregarPosicion = () => {
    setPosiciones(prev => [
      ...prev,
      {
        id: Date.now(),
        numero_producto: '',
        descripcion: '',
        especificaciones: '',
        expandirNota: false,
        tipo_fabricacion: 'BAJO_PLANO',
        cantidad: 1,
        unidad: 'UND',
        precio_unitario: 0,
        descuento_pct: 0,
        tipo_impuesto: 'IVA_19',
        vinculo_plano_catalogo: ''
      }
    ]);
  };

  const handleEliminarPosicion = (id) => {
    if (posiciones.length === 1) {
      alert('La cotización debe tener al menos una posición.');
      return;
    }
    const nuevas = posiciones.filter(item => item.id !== id);
    setPosiciones(nuevas);

    const quedaAlgunaPorDefinir = nuevas.some(p => p.tipo_fabricacion === 'POR_DEFINIR');
    if (!quedaAlgunaPorDefinir) {
      setCabecera(prevCab => ({
        ...prevCab,
        condiciones_comerciales: (prevCab.condiciones_comerciales || '')
          .replace(NOTA_VISITA_TECNICA, '')
          .trim()
      }));
    }
  };

  const calcularSubtotalLinea = (item) => {
    const cant = Number(item.cantidad) || 0;
    const precio = Number(item.precio_unitario) || 0;
    const desc = Number(item.descuento_pct) || 0;
    return cant * precio * (1 - desc / 100);
  };

  const totalesLiquidacion = posiciones.reduce(
    (acc, item) => {
      const subLinea = calcularSubtotalLinea(item);
      acc.subtotalNeto += subLinea;

      let tasa = 0;
      if (item.tipo_impuesto === 'IVA_19') tasa = 0.19;
      if (item.tipo_impuesto === 'IVA_5') tasa = 0.05;

      acc.totalImpuestos += subLinea * tasa;
      return acc;
    },
    { subtotalNeto: 0, totalImpuestos: 0 }
  );

  const totalCotizacion = totalesLiquidacion.subtotalNeto + totalesLiquidacion.totalImpuestos;

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setErrorMsg('');

    if (!cabecera.codigo_cliente) {
      setErrorMsg('El Código de Cliente es obligatorio.');
      return;
    }

    if (!cabecera.fecha_compromiso) {
      setErrorMsg('La Fecha de Compromiso de Entrega es obligatoria.');
      return;
    }

    // 1. Armar payload base sin id_socio por defecto
    const payload = {
      codigo_cliente: cabecera.codigo_cliente,
      razon_social: cabecera.razon_social || 'Cliente Comercial',
      nit: cabecera.nit || '',
      contacto_nombre: cabecera.contacto || '',
      contacto_telefono: cabecera.telefono || '',
      contacto_email: cabecera.email || '',
      direccion_cliente: cabecera.direccion || '',
      ciudad: cabecera.ciudad || '',
      referencia_global: cabecera.referencia_global || '',
      numero_cotizacion: cabecera.numero_cotizacion,
      fecha_emision: cabecera.fecha_emision,
      fecha_vigencia: cabecera.fecha_vigencia || null,
      fecha_compromiso: cabecera.fecha_compromiso || null,
      condiciones_pago: cabecera.condiciones_pago || '30 Días',
      condiciones_comerciales: cabecera.condiciones_comerciales || '',
      subtotal: Math.round(totalesLiquidacion.subtotalNeto),
      impuesto_total: Math.round(totalesLiquidacion.totalImpuestos),
      total_general: Math.round(totalCotizacion),
      posiciones: posiciones.map(p => ({
        numero_producto: p.numero_producto || 'REF-COT',
        descripcion: p.descripcion,
        cantidad: Number(p.cantidad) || 1,
        precio_unitario: Number(p.precio_unitario) || 0,
        descuento_pct: Number(p.descuento_pct) || 0,
        unidad: p.unidad || 'UND',
        tipo_impuesto: p.tipo_impuesto || 'IVA_19',
        vinculo_plano_catalogo: p.tipo_fabricacion || null
      }))
    };

    // 2. SOLO adjuntar id_socio si es un UUID estricto de 36 caracteres (ej. de la base de datos)
    if (cabecera.id_socio && typeof cabecera.id_socio === 'string' && cabecera.id_socio.length === 36) {
      payload.id_socio = cabecera.id_socio;
    }

    try {
      setLoading(true);
      const res = await API.post('/ventas/cotizaciones/', payload);

      if (onCotizacionGuardada) {
        onCotizacionGuardada(res.data || {
          id_cotizacion: Date.now().toString(),
          numero_cotizacion: cabecera.numero_cotizacion,
          id_socio: cabecera.razon_social || cabecera.codigo_cliente,
          fecha_emision: cabecera.fecha_emision,
          valor_total: Math.round(totalCotizacion),
          estado: 'BORRADOR'
        });
      }

      onClose();
    } catch (err) {
      let detalleError = 'Error al registrar la cotización en el servidor.';
      if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          detalleError = err.response.data.detail.map(d => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(' | ');
        } else if (typeof err.response.data.detail === 'string') {
          detalleError = err.response.data.detail;
        }
      }
      setErrorMsg(detalleError);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-3 backdrop-blur-sm">
      <div className="flex max-h-[96vh] w-full max-w-7xl flex-col rounded-xl border border-slate-300 bg-white text-xs shadow-2xl">
        
        {/* Cabecera Superior con Consecutivo Destacado */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-100 px-4 py-2">
          <div className="flex items-center gap-3">
            <span className="text-base font-bold text-slate-800">📋 Cotización y Oferta Comercial</span>
            <div className="flex items-center bg-white px-2.5 py-0.5 rounded border border-blue-300 shadow-xs">
              <span className="text-[10px] font-bold text-slate-500 mr-1.5 uppercase tracking-wider">Consecutivo:</span>
              <span className="font-mono font-black text-blue-900 text-xs">{cabecera.numero_cotizacion}</span>
            </div>
            <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-extrabold text-blue-800">
              {modoVistaPrevia ? 'DOCUMENTO FORMAL' : 'INDUSTRIAS HD'}
            </span>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="text-lg font-bold text-slate-400 hover:text-slate-600 cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* MODAL EN MODO VISTA PREVIA */}
        {modoVistaPrevia ? (
          <div className="flex flex-1 flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto p-6 bg-slate-200">
              <div className="max-w-4xl mx-auto bg-white p-8 rounded shadow-lg border border-slate-300 font-sans text-slate-900 text-xs space-y-5">
                
                <div className="flex justify-between items-start border-b pb-4">
                  <div>
                    <h1 className="text-2xl font-black tracking-tight text-blue-900">HD Precision &amp; Technology</h1>
                    <p className="text-[10px] text-slate-500">Mecanizado de Precisión · Fabricación &amp; Overhaul Industrial</p>
                  </div>
                  <div className="text-right">
                    <span className="font-extrabold text-sm text-slate-800">COTIZACIÓN Nº</span>
                    <div className="text-lg font-mono font-black text-blue-800">{cabecera.numero_cotizacion}</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 bg-slate-50 p-4 rounded border border-slate-200">
                  <div className="space-y-1">
                    <div><span className="font-bold text-slate-600">Fecha Emisión:</span> {cabecera.fecha_emision}</div>
                    <div><span className="font-bold text-blue-900">Fecha Compromiso Entrega:</span> <strong className="text-blue-900">{cabecera.fecha_compromiso}</strong></div>
                    <div><span className="font-bold text-slate-600">Cliente:</span> {cabecera.razon_social || 'Sin razón social'}</div>
                    <div><span className="font-bold text-slate-600">Contacto:</span> {cabecera.contacto || 'Sin contacto'}</div>
                    <div><span className="font-bold text-slate-600">Dirección:</span> {cabecera.direccion || 'No especificada'}</div>
                  </div>
                  <div className="space-y-1 text-right sm:text-left">
                    <div><span className="font-bold text-slate-600">NIT:</span> {cabecera.nit || 'Sin NIT'}</div>
                    <div><span className="font-bold text-slate-600">E-mail:</span> {cabecera.email || 'Sin correo'}</div>
                    <div><span className="font-bold text-slate-600">Teléfono:</span> {cabecera.telefono || 'Sin teléfono'}</div>
                    <div><span className="font-bold text-slate-600">Condición de Pago:</span> {cabecera.condiciones_pago}</div>
                    <div><span className="font-bold text-slate-600">Ciudad:</span> {cabecera.ciudad}</div>
                  </div>
                </div>

                {cabecera.referencia_global && (
                  <div className="text-xs font-bold bg-blue-50 p-2 rounded border border-blue-200">
                    REFERENCIA: <span className="uppercase text-blue-900">{cabecera.referencia_global}</span>
                  </div>
                )}

                <table className="w-full border-collapse border border-slate-300 text-left text-xs">
                  <thead>
                    <tr className="bg-slate-100 font-bold border-b border-slate-300">
                      <th className="p-2 border-r w-12 text-center">Ítem</th>
                      <th className="p-2 border-r w-32">Código</th>
                      <th className="p-2 border-r w-20 text-center">Cant.</th>
                      <th className="p-2 border-r">Descripción y Alcance Técnico</th>
                      <th className="p-2 border-r w-24 text-right">Valor Unit.</th>
                      <th className="p-2 border-r w-20 text-center">Impuesto</th>
                      <th className="p-2 w-28 text-right">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {posiciones.map((p, idx) => (
                      <tr key={p.id}>
                        <td className="p-2 border-r text-center font-bold text-slate-400">{idx + 1}</td>
                        <td className="p-2 border-r font-mono font-bold text-purple-800">{p.numero_producto}</td>
                        <td className="p-2 border-r text-center font-bold">{p.cantidad} {p.unidad}</td>
                        <td className="p-2 border-r">
                          <div className="font-bold text-slate-900 uppercase">{p.descripcion || 'Sin descripción'}</div>
                          {p.especificaciones && (
                            <pre className="font-sans whitespace-pre-wrap text-[11px] text-slate-600 mt-1 pl-2 border-l-2 border-slate-300">
                              {p.especificaciones}
                            </pre>
                          )}
                          <div className="text-[10px] text-slate-400 mt-1">
                            Fabricación: <strong>{p.tipo_fabricacion}</strong>
                          </div>
                        </td>
                        <td className="p-2 border-r text-right font-mono">$ {Number(p.precio_unitario).toLocaleString('es-CO')}</td>
                        <td className="p-2 border-r text-center font-bold text-[10px] text-slate-600">
                          {p.tipo_impuesto === 'IVA_19' ? '19%' : p.tipo_impuesto === 'IVA_5' ? '5%' : '0%'}
                        </td>
                        <td className="p-2 text-right font-mono font-bold">$ {Math.round(calcularSubtotalLinea(p)).toLocaleString('es-CO')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="flex justify-end pt-3">
                  <div className="w-72 space-y-1 text-right font-mono text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-600">Subtotal Posiciones:</span>
                      <span>$ {Math.round(totalesLiquidacion.subtotalNeto).toLocaleString('es-CO')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-600">IVA Discriminado:</span>
                      <span>$ {Math.round(totalesLiquidacion.totalImpuestos).toLocaleString('es-CO')}</span>
                    </div>
                    <div className="flex justify-between border-t border-slate-400 pt-1 font-bold text-sm text-blue-900">
                      <span>Total Oferta (COP):</span>
                      <span>$ {Math.round(totalCotizacion).toLocaleString('es-CO')}</span>
                    </div>
                  </div>
                </div>

                {cabecera.condiciones_comerciales && (
                  <div className="p-3 bg-slate-50 border rounded text-[11px] leading-relaxed">
                    <strong className="block font-bold text-slate-700 mb-1">CONDICIONES COMERCIALES Y PLAZOS:</strong>
                    <p className="whitespace-pre-line text-slate-600">{cabecera.condiciones_comerciales}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-between items-center border-t border-slate-200 bg-white p-3">
              <button
                type="button"
                onClick={() => setModoVistaPrevia(false)}
                className="rounded bg-slate-200 px-4 py-1.5 font-bold text-slate-700 hover:bg-slate-300 cursor-pointer"
              >
                ✏️ Volver a Edición
              </button>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="rounded bg-slate-800 px-4 py-1.5 font-bold text-white hover:bg-slate-900 cursor-pointer"
                >
                  🖨️ Imprimir / Guardar PDF
                </button>
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={loading}
                  className="rounded bg-blue-600 px-5 py-1.5 font-bold text-white shadow hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
                >
                  {loading ? 'Guardando...' : '💾 Confirmar y Emitir'}
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* MODO EDICIÓN COMPACTO */
          <form onSubmit={handleSubmit} className="flex flex-1 flex-col overflow-hidden p-4 space-y-3">
            {errorMsg && (
              <div className="rounded border border-red-200 bg-red-50 p-2 font-bold text-red-700">
                ❌ {errorMsg}
              </div>
            )}

            {/* Cabecera Datos Maestros del Cliente */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
              <div className="flex items-center justify-between border-b border-slate-200 pb-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-extrabold uppercase tracking-wide text-slate-600">
                    1. Datos Maestros del Cliente &amp; Contacto Técnico
                  </span>
                </div>
                {onAbrirCrearSocio && (
                  <button
                    type="button"
                    onClick={onAbrirCrearSocio}
                    className="rounded bg-emerald-600 px-2 py-0.5 text-[10px] font-bold text-white shadow-sm hover:bg-emerald-700 cursor-pointer"
                  >
                    ➕ Crear Nuevo Socio
                  </button>
                )}
              </div>

              {/* Fila 1 de Datos Maestros */}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
                <div>
                  <label className="block text-[10px] font-bold text-blue-900">Cód. Cliente *</label>
                  <input
                    type="text"
                    required
                    placeholder="CLI-1001"
                    value={cabecera.codigo_cliente}
                    onChange={e => handleSeleccionarSocio(e.target.value.toUpperCase())}
                    className="w-full rounded border border-blue-400 bg-blue-50/50 p-1.5 font-mono font-bold text-blue-900 focus:bg-white"
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-[10px] font-bold text-slate-700">Razón Social *</label>
                  <input
                    type="text"
                    required
                    placeholder="CONTEGRAL SAS"
                    value={cabecera.razon_social}
                    onChange={e => handleCambioCabecera('razon_social', e.target.value)}
                    className="w-full rounded border border-slate-300 bg-white p-1.5 font-bold text-slate-800"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-600">NIT / Identificación</label>
                  <input
                    type="text"
                    placeholder="890900123"
                    value={cabecera.nit}
                    onChange={e => handleCambioCabecera('nit', e.target.value)}
                    className="w-full rounded border border-slate-300 bg-white p-1.5 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-600">Contacto Técnico</label>
                  <input
                    type="text"
                    placeholder="ANDRES MONTOYA"
                    value={cabecera.contacto}
                    onChange={e => handleCambioCabecera('contacto', e.target.value)}
                    className="w-full rounded border border-slate-300 bg-white p-1.5"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-600">Teléfono Contacto</label>
                  <input
                    type="text"
                    placeholder="(004) 300..."
                    value={cabecera.telefono}
                    onChange={e => handleCambioCabecera('telefono', e.target.value)}
                    className="w-full rounded border border-slate-300 bg-white p-1.5"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-600">E-mail Contacto</label>
                  <input
                    type="email"
                    placeholder="andres@contegral.com"
                    value={cabecera.email}
                    onChange={e => handleCambioCabecera('email', e.target.value)}
                    className="w-full rounded border border-slate-300 bg-white p-1.5"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-600">Condición Pago</label>
                  <select
                    value={cabecera.condiciones_pago}
                    onChange={e => handleCambioCabecera('condiciones_pago', e.target.value)}
                    className="w-full rounded border border-slate-300 bg-white p-1.5 font-semibold"
                  >
                    <option value="Contado">Contado</option>
                    <option value="15 Días">15 Días</option>
                    <option value="30 Días">30 Días</option>
                    <option value="60 Días">60 Días</option>
                  </select>
                </div>
              </div>

              {/* Fila 2 de Datos Maestros */}
              <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 pt-1 border-t border-slate-200">
                <div>
                  <label className="block text-[10px] font-bold text-blue-900">N° Cotización (Consecutivo) *</label>
                  <input
                    type="text"
                    required
                    value={cabecera.numero_cotizacion}
                    onChange={e => handleCambioCabecera('numero_cotizacion', e.target.value)}
                    className="w-full rounded border border-blue-400 bg-white p-1.5 font-mono font-black text-blue-900 uppercase"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-[10px] font-bold text-slate-600">Dirección y Planta de Entrega</label>
                  <input
                    type="text"
                    placeholder="CR 60 47 96 SUR, Principal Belén"
                    value={cabecera.direccion}
                    onChange={e => handleCambioCabecera('direccion', e.target.value)}
                    className="w-full rounded border border-slate-300 bg-white p-1.5"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-600">Referencia del Proyecto / Solicitud</label>
                  <input
                    type="text"
                    placeholder="AMPLIACION PELLET MUYANG 1610"
                    value={cabecera.referencia_global}
                    onChange={e => handleCambioCabecera('referencia_global', e.target.value)}
                    className="w-full rounded border border-slate-300 bg-white p-1.5 font-bold uppercase text-blue-900"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-blue-900">📅 Fecha Compromiso Entrega *</label>
                  <input
                    type="date"
                    required
                    value={cabecera.fecha_compromiso}
                    onChange={e => handleCambioCabecera('fecha_compromiso', e.target.value)}
                    className="w-full rounded border border-blue-400 bg-blue-50/60 p-1.5 font-bold text-blue-950 focus:bg-white"
                  />
                </div>
              </div>
            </div>

            {/* Grilla de Posiciones */}
            <div className="flex-1 overflow-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[980px] border-collapse text-left text-[11px]">
                <thead className="sticky top-0 border-b border-slate-200 bg-slate-100 font-extrabold uppercase text-slate-700">
                  <tr>
                    <th className="p-2 text-center w-10">#</th>
                    <th className="p-2 w-28">Código / Pieza</th>
                    <th className="p-2">Descripción del Artículo / Pieza</th>
                    <th className="p-2 w-44">Fabricación</th>
                    <th className="p-2 w-16 text-center">Cant.</th>
                    <th className="p-2 w-16 text-center">Und.</th>
                    <th className="p-2 w-28 text-right">Precio Unit. ($)</th>
                    <th className="p-2 w-16 text-center">% Desc</th>
                    <th className="p-2 w-28 text-center">Impuesto</th>
                    <th className="p-2 w-28 text-right">Subtotal ($)</th>
                    <th className="p-2 text-center w-14">Alcance</th>
                    <th className="p-2 text-center w-8"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-800">
                  {posiciones.map((pos, idx) => {
                    const esPorDefinir = pos.tipo_fabricacion === 'POR_DEFINIR';
                    return (
                      <React.Fragment key={pos.id}>
                        <tr className="hover:bg-slate-50">
                          <td className="p-1.5 text-center font-mono text-slate-400">{(idx + 1) * 10}</td>
                          <td className="p-1.5">
                            <input
                              type="text"
                              placeholder="A-01"
                              value={pos.numero_producto}
                              onChange={e => handleCambioPosicion(pos.id, 'numero_producto', e.target.value)}
                              className="w-full rounded border border-slate-300 p-1 font-mono font-bold text-blue-700"
                            />
                          </td>
                          <td className="p-1.5">
                            <input
                              type="text"
                              required
                              placeholder="BUJE Ø 50 X Ø 25 X 20 MM..."
                              value={pos.descripcion}
                              onChange={e => handleCambioPosicion(pos.id, 'descripcion', e.target.value)}
                              className="w-full rounded border border-slate-300 p-1 font-semibold text-slate-800 uppercase"
                            />
                          </td>
                          <td className="p-1.5">
                            <select
                              value={pos.tipo_fabricacion}
                              onChange={e => handleCambioPosicion(pos.id, 'tipo_fabricacion', e.target.value)}
                              className={`w-full rounded border p-1 font-bold ${
                                esPorDefinir
                                  ? 'border-amber-400 bg-amber-50 text-amber-900'
                                  : 'border-slate-300 bg-white text-slate-800'
                              }`}
                            >
                              {TIPOS_FABRICACION.map(t => (
                                <option key={t.valor} value={t.valor}>{t.etiqueta}</option>
                              ))}
                            </select>
                          </td>
                          <td className="p-1.5">
                            <input
                              type="number"
                              min="1"
                              required
                              value={pos.cantidad}
                              onChange={e => handleCambioPosicion(pos.id, 'cantidad', e.target.value)}
                              className="w-full rounded border border-slate-300 p-1 text-center font-bold text-slate-900"
                            />
                          </td>
                          <td className="p-1.5">
                            <input
                              type="text"
                              value={pos.unidad}
                              onChange={e => handleCambioPosicion(pos.id, 'unidad', e.target.value)}
                              className="w-full rounded border border-slate-300 p-1 text-center uppercase"
                            />
                          </td>
                          <td className="p-1.5">
                            <input
                              type="number"
                              min="0"
                              step="100"
                              required
                              value={pos.precio_unitario}
                              onChange={e => handleCambioPosicion(pos.id, 'precio_unitario', e.target.value)}
                              className="w-full rounded border border-slate-300 p-1 text-right font-mono font-bold text-emerald-700"
                            />
                          </td>
                          <td className="p-1.5">
                            <input
                              type="number"
                              min="0"
                              max="100"
                              value={pos.descuento_pct}
                              onChange={e => handleCambioPosicion(pos.id, 'descuento_pct', e.target.value)}
                              className="w-full rounded border border-slate-300 p-1 text-center font-mono"
                            />
                          </td>
                          <td className="p-1.5">
                            <select
                              value={pos.tipo_impuesto}
                              onChange={e => handleCambioPosicion(pos.id, 'tipo_impuesto', e.target.value)}
                              className="w-full rounded border border-slate-300 bg-white p-1 text-center font-bold text-slate-700"
                            >
                              <option value="IVA_19">IVA 19%</option>
                              <option value="IVA_5">IVA 5%</option>
                              <option value="EXENTO">Exento (0%)</option>
                            </select>
                          </td>
                          <td className="p-1.5 text-right font-mono font-bold text-slate-900">
                            $ {Math.round(calcularSubtotalLinea(pos)).toLocaleString('es-CO')}
                          </td>
                          <td className="p-1.5 text-center">
                            <button
                              type="button"
                              onClick={() => toggleExpandirNota(pos.id)}
                              title="Especificar *Incluye, *No Incluye o Recomendaciones"
                              className={`rounded px-1.5 py-0.5 text-[10px] font-bold border transition cursor-pointer ${
                                pos.especificaciones
                                  ? 'bg-blue-100 text-blue-900 border-blue-300'
                                  : 'bg-slate-100 text-slate-600 border-slate-300'
                              }`}
                            >
                              {pos.especificaciones ? '📝 Nota' : ' 📝Nota'}
                            </button>
                          </td>
                          <td className="p-1.5 text-center">
                            <button
                              type="button"
                              onClick={() => handleEliminarPosicion(pos.id)}
                              className="font-bold text-red-500 hover:text-red-700 cursor-pointer"
                            >
                              ✕
                            </button>
                          </td>
                        </tr>

                        {pos.expandirNota && (
                          <tr className="bg-blue-50/50">
                            <td colSpan="12" className="p-3">
                              <div className="rounded border border-blue-200 bg-white p-2 space-y-1">
                                <div className="flex justify-between items-center text-[10px] font-bold text-blue-900">
                                  <span>Especificaciones Técnicas / Inclusiones / Exclusiones de la Posición</span>
                                  <button
                                    type="button"
                                    onClick={() => toggleExpandirNota(pos.id)}
                                    className="text-slate-400 hover:text-slate-600 cursor-pointer"
                                  >
                                    Cerrar ✕
                                  </button>
                                </div>
                                <textarea
                                  rows="3"
                                  placeholder="*Incluye: Tapa Principal en Ac Inox, Montaje...&#10;*No Incluye: Rodamientos, Motores..."
                                  value={pos.especificaciones}
                                  onChange={e => handleCambioPosicion(pos.id, 'especificaciones', e.target.value)}
                                  className="w-full rounded border border-slate-300 p-2 text-xs font-mono text-slate-800 leading-relaxed"
                                />
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="flex justify-between items-center">
              <button
                type="button"
                onClick={handleAgregarPosicion}
                className="rounded bg-slate-100 border border-slate-300 px-3 py-1 font-bold text-slate-700 hover:bg-slate-200 cursor-pointer"
              >
                ➕ Agregar Línea de Artículo
              </button>
            </div>

            {/* Pie de Página y Liquidación de Totales */}
            <div className="grid grid-cols-1 gap-3 border-t border-slate-200 pt-3 sm:grid-cols-2">
              <div>
                <label className="block text-[10px] font-bold text-slate-600 mb-1">
                  Condiciones Comerciales y Observaciones Generales
                </label>
                <textarea
                  rows="3"
                  placeholder="Puesto en planta cliente. Forma de pago según acuerdo..."
                  value={cabecera.condiciones_comerciales}
                  onChange={e => handleCambioCabecera('condiciones_comerciales', e.target.value)}
                  className="w-full rounded border border-slate-300 p-2 text-slate-800 leading-relaxed font-sans"
                />
              </div>

              <div className="space-y-1 rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-right font-mono">
                <div className="flex justify-between text-slate-600">
                  <span>Subtotal Posiciones:</span>
                  <span className="font-bold">$ {Math.round(totalesLiquidacion.subtotalNeto).toLocaleString('es-CO')}</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Impuestos (IVA Discriminado):</span>
                  <span className="font-bold">$ {Math.round(totalesLiquidacion.totalImpuestos).toLocaleString('es-CO')}</span>
                </div>
                <div className="flex justify-between border-t border-slate-300 pt-1 text-sm font-extrabold text-emerald-800">
                  <span>Total Oferta (COP):</span>
                  <span>$ {Math.round(totalCotizacion).toLocaleString('es-CO')}</span>
                </div>
              </div>
            </div>

            {/* Botonera de Acción */}
            <div className="flex justify-between items-center border-t border-slate-200 pt-2">
              <button
                type="button"
                onClick={() => setModoVistaPrevia(true)}
                className="rounded border border-blue-600 bg-blue-50 px-4 py-1.5 font-bold text-blue-700 hover:bg-blue-100 cursor-pointer"
              >
                👁️ Vista Previa de la Oferta
              </button>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded bg-slate-200 px-4 py-1.5 font-bold text-slate-700 hover:bg-slate-300 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="rounded bg-blue-600 px-5 py-1.5 font-bold text-white shadow hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
                >
                  {loading ? 'Guardando...' : '💾 Crear y Emitir Cotización'}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}