import React, { useEffect, useMemo, useState } from 'react';
import API from '../../services/api';
import VisorPlanoModal from '../VisorPlanoModal';
import VistaGrafoCostos from '../../views/nivel2/VistaGrafoCostos';

const PESTANAS = [
  { id: 'piezas', etiqueta: '📋 Despiece de Piezas / Kit' },
  { id: 'insumos', etiqueta: '📦 Insumos & Almacén' },
  { id: 'mes', etiqueta: '⏱️ Registro MES & Tiempos' },
  { id: 'calidad', etiqueta: '🗜️ Calidad & Metrología' },
  { id: 'costos', etiqueta: '💰 Costos reales' }
];

const ESTILOS_ESTADO = {
  LIBERADA: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  LIBERADA_PRODUCCION: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  EN_PRODUCCION: 'bg-blue-100 text-blue-800 border-blue-200',
  EN_PROCESO_CNC: 'bg-blue-100 text-blue-800 border-blue-200',
  TERMINADA: 'bg-purple-100 text-purple-800 border-purple-200',
  CERRADA: 'bg-slate-200 text-slate-700 border-slate-300',
  EN_ALMACEN: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  ENTREGADO: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  EN_COMPRA: 'bg-amber-100 text-amber-800 border-amber-200',
  SOLICITADO: 'bg-amber-100 text-amber-800 border-amber-200',
  SIN_SOLICITAR: 'bg-slate-100 text-slate-600 border-slate-200',
  COMPLETA: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  PARCIAL: 'bg-amber-100 text-amber-800 border-amber-200',
  SIN_DESPACHO: 'bg-slate-100 text-slate-600 border-slate-200'
};

function normalizarTexto(valor) {
  return String(valor || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]/g, '')
    .toUpperCase();
}

function obtenerRolSesion(usuario) {
  const token = localStorage.getItem('sgi_token');
  if (token) {
    try {
      const segmento = token.split('.')[1];
      const base64 = segmento.replace(/-/g, '+').replace(/_/g, '/');
      const relleno = '='.repeat((4 - (base64.length % 4)) % 4);
      const claims = JSON.parse(window.atob(base64 + relleno));
      if (claims.rol) return normalizarTexto(claims.rol);
    } catch {
      return '';
    }
  }
  const rol = normalizarTexto(usuario?.rol || usuario?.id_rol);
  if (['ADMIN', 'VENTAS', 'DISENO', 'ALMACEN', 'PRODUCCION', 'CALIDAD'].includes(rol)) return rol;
  const area = normalizarTexto(usuario?.area);
  return ({
    VENTAS: 'VENTAS',
    DISENO: 'DISENO',
    DISENOEINGENIERIA: 'DISENO',
    ALMACEN: 'ALMACEN',
    PRODUCCION: 'PRODUCCION',
    CALIDAD: 'CALIDAD'
  })[area] || (rol === 'ADMINISTRADOR' ? 'ADMIN' : '');
}

function EtiquetaEstado({ valor }) {
  const estado = valor || 'SIN_DATO';
  const estilo = ESTILOS_ESTADO[estado] || 'bg-slate-100 text-slate-700 border-slate-200';
  return (
    <span className={`inline-flex rounded border px-2 py-0.5 text-[10px] font-extrabold ${estilo}`}>
      {estado.replaceAll('_', ' ')}
    </span>
  );
}

function AccionButton({ children, onClick, disabled = false, className = '' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded border px-2.5 py-1.5 text-[10px] font-bold transition disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  );
}

export default function ExpedienteOpModal({
  abierto,
  onClose,
  codigoOp,
  usuario,
  onAction
}) {
  const [expediente, setExpediente] = useState(null);
  const [pestana, setPestana] = useState('piezas');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState('');
  const [mensajeAccion, setMensajeAccion] = useState('');
  const [liberando, setLiberando] = useState(false);
  const [planoAbierto, setPlanoAbierto] = useState(null);
  const [costos, setCostos] = useState(null);
  const [cargandoCostos, setCargandoCostos] = useState(false);
  const [errorCostos, setErrorCostos] = useState('');
  const rol = obtenerRolSesion(usuario);

  const permisos = useMemo(() => ({
    ventas: rol === 'ADMIN' || rol === 'VENTAS',
    diseno: rol === 'ADMIN' || rol === 'DISENO',
    almacen: rol === 'ADMIN' || rol === 'ALMACEN',
    produccion: rol === 'ADMIN' || rol === 'PRODUCCION',
    calidad: rol === 'ADMIN' || rol === 'CALIDAD'
  }), [rol]);

  useEffect(() => {
    if (!abierto || !codigoOp) return undefined;
    let activo = true;
    setCargando(true);
    setError('');
    setExpediente(null);
    setMensajeAccion('');
    API.get(`/ordenes/expediente/${encodeURIComponent(codigoOp)}`)
      .then((respuesta) => {
        if (activo) setExpediente(respuesta.data);
      })
      .catch((fallo) => {
        if (activo) {
          setError(fallo.response?.data?.detail || 'No fue posible cargar el expediente de la OP.');
        }
      })
      .finally(() => {
        if (activo) setCargando(false);
      });
    return () => {
      activo = false;
    };
  }, [abierto, codigoOp]);

  useEffect(() => {
    if (!abierto || pestana !== 'costos' || !codigoOp) return undefined;
    let activo = true;
    setCargandoCostos(true);
    setErrorCostos('');
    API.get(`/costos/liquidar/${encodeURIComponent(codigoOp)}`)
      .then((respuesta) => {
        if (activo) setCostos(respuesta.data);
      })
      .catch((fallo) => {
        if (activo) {
          setErrorCostos(fallo.response?.data?.detail || 'No fue posible cargar los costos reales de la OP.');
          setCostos(null);
        }
      })
      .finally(() => {
        if (activo) setCargandoCostos(false);
      });
    return () => {
      activo = false;
    };
  }, [abierto, codigoOp, pestana]);

  if (!abierto) return null;

  const ejecutarAccion = async (accion, contexto = {}) => {
    setMensajeAccion('');
    if (accion === 'LIBERAR_OP') {
      setLiberando(true);
      try {
        await API.patch(`/ordenes/liberar/${encodeURIComponent(codigoOp)}`);
        setMensajeAccion('La OP fue liberada correctamente.');
        const respuesta = await API.get(`/ordenes/expediente/${encodeURIComponent(codigoOp)}`);
        setExpediente(respuesta.data);
      } catch (fallo) {
        setMensajeAccion(fallo.response?.data?.detail || 'No se pudo liberar la OP.');
      } finally {
        setLiberando(false);
      }
      return;
    }
    const detalleAccion = { accion, codigo_op: codigoOp, expediente, ...contexto };
    if (onAction) {
      onAction(accion, detalleAccion);
    } else {
      window.dispatchEvent(new CustomEvent('sgi:expediente-action', { detail: detalleAccion }));
      setMensajeAccion('Acción enviada al módulo correspondiente.');
    }
  };

  const pedido = expediente?.pedido || {};
  const planos = expediente?.planos || [];
  const materiales = expediente?.resumen_bom || [];
  const motivosGate = expediente?.quality_gate?.motivos || [];
  const puedeLiberar = Boolean(expediente?.quality_gate?.aprobado);
  const mostrarTab = (id) => setPestana(id);

  return (
    <>
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/60 p-3 backdrop-blur-sm">
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="expediente-op-titulo"
          className="flex max-h-[94vh] w-full max-w-7xl flex-col overflow-hidden rounded-xl border-t-4 border-emerald-600 bg-white text-xs shadow-2xl"
        >
          <header className="border-b border-slate-200 bg-white px-4 py-1.5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-bold uppercase tracking-wide text-slate-500">
                  Expediente de Orden de Producción
                </p>
                <h2 id="expediente-op-titulo" className="font-mono text-lg font-extrabold text-slate-900">
                  OP {codigoOp}
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Cerrar expediente"
                className="rounded px-2 py-1 text-lg font-bold text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                ×
              </button>
            </div>
            {expediente && (
              <>
                <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3 lg:grid-cols-7">
                  <div><span className="text-slate-500">Pedido agrupador</span><strong className="block font-mono text-purple-800">{pedido.numero_pedido || '—'}</strong></div>
                  <div><span className="text-slate-500">Cliente</span><strong className="block text-slate-800">{pedido.cliente || '—'}</strong></div>
                  <div><span className="text-slate-500">Diseñador responsable</span><strong className="block text-slate-800">{expediente.disenador_responsable || '—'}</strong></div>
                  <div><span className="text-slate-500">Fecha límite</span><strong className="block text-slate-800">{pedido.fecha_limite || '—'}</strong></div>
                  <div><span className="text-slate-500">Estado operativo</span><span className="mt-0.5 block"><EtiquetaEstado valor={expediente.estado_operativo} /></span></div>
                  <div><span className="text-slate-500">Estado del BOM</span><span className="mt-0.5 block"><EtiquetaEstado valor={expediente.estado_bom} /></span></div>
                  {permisos.ventas && <div><span className="text-slate-500">Entregas del pedido</span><span className="mt-0.5 block"><EtiquetaEstado valor={pedido.estado_entregas} /> <span className="text-[10px] text-slate-500">{pedido.cantidad_entregada || 0}/{expediente.cantidad_programada} und</span></span></div>}
                </div>
                <div className={`mt-2 flex flex-wrap items-center gap-2 rounded border px-2.5 py-1.5 font-bold ${puedeLiberar ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'}`}>
                  <span>{puedeLiberar ? '🟢 RN-OP-004: Aprobado' : '🔴 RN-OP-004: Bloqueado'}</span>
                  {!puedeLiberar && <span className="font-medium">{motivosGate.join(' ') || 'Faltan planos o insumos en almacén.'}</span>}
                </div>
              </>
            )}
          </header>

          <div className="flex flex-wrap gap-1 border-b border-slate-200 bg-slate-50 px-3 pt-2">
            {PESTANAS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => mostrarTab(item.id)}
                className={`rounded-t px-3 py-2 font-bold ${pestana === item.id ? 'border border-b-white border-slate-200 bg-white text-emerald-800' : 'text-slate-600 hover:bg-slate-100'}`}
              >
                {item.etiqueta}
              </button>
            ))}
          </div>

          <main className="min-h-0 flex-1 overflow-y-auto p-3">
            {cargando && <p className="rounded bg-slate-50 p-4 text-center font-semibold text-slate-600">Cargando expediente…</p>}
            {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 font-semibold text-red-800">{error}</p>}
            {mensajeAccion && <p role="status" className="mb-3 rounded border border-amber-200 bg-amber-50 p-2 text-amber-900">{mensajeAccion}</p>}
            {pestana === 'costos' && (
              <div className="space-y-3">
                {cargandoCostos && <p className="rounded bg-slate-50 p-4 text-center font-semibold text-slate-600">Cargando costos reales…</p>}
                {errorCostos && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 font-semibold text-red-800">{errorCostos}</p>}
                {costos && !cargandoCostos && <VistaGrafoCostos datos={costos} />}
              </div>
            )}

            {expediente && pestana === 'piezas' && (
              <div className="overflow-x-auto rounded border border-slate-200">
                <table className="w-full min-w-[850px] border-collapse text-left">
                  <thead className="bg-slate-100 text-[10px] uppercase text-slate-600">
                    <tr>
                      <th className="p-2">Código de pieza</th>
                      <th className="p-2">Nombre</th>
                      <th className="p-2 text-center">Cantidad requerida / OK</th>
                      <th className="p-2">Material (BOM)</th>
                      <th className="p-2">Lote de colada</th>
                      <th className="p-2 text-center">Plano</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {planos.flatMap((plano) => {
                      const piezas = plano.piezas?.length ? plano.piezas : [{
                        codigo_pieza: plano.codigo_plano,
                        nombre: plano.codigo_plano,
                        cantidad_requerida: expediente.cantidad_programada,
                        cantidad_asignada: expediente.cantidad_programada
                      }];
                      return piezas.map((pieza, indice) => {
                        const bom = plano.resumen_bom || [];
                        const materialesTexto = bom.map((item) => `${item.codigo_material} · ${item.descripcion}`).join(', ') || plano.material_requerido || '—';
                        const coladas = bom.flatMap((item) => item.lotes || []).filter((lote) => lote.numero_colada || lote.codigo_lote);
                        return (
                          <tr key={`${plano.id_plano}-${pieza.codigo_pieza}-${indice}`} className="align-top hover:bg-slate-50">
                            <td className="p-2 font-mono font-bold text-blue-900">{pieza.codigo_pieza}</td>
                            <td className="p-2">{pieza.nombre}</td>
                            <td className="p-2 text-center font-mono">{pieza.cantidad_asignada ?? pieza.cantidad_requerida} / {plano.cantidad_ok || 0}</td>
                            <td className="p-2">{materialesTexto}</td>
                            <td className="p-2">
                              {coladas.length ? coladas.map((lote, loteIndex) => (
                                <span key={`${lote.codigo_lote}-${loteIndex}`} className="mr-2 inline-flex flex-col">
                                  <span>{lote.numero_colada || lote.codigo_lote}</span>
                                  {lote.certificado_calidad_url && <a href={lote.certificado_calidad_url} target="_blank" rel="noreferrer" className="text-[10px] text-blue-700 underline">Certificado 3.1</a>}
                                </span>
                              )) : 'Pendiente de recepción'}
                            </td>
                            <td className="p-2 text-center">
                              <button
                                type="button"
                                onClick={() => setPlanoAbierto({ ...plano, archivo_url: plano.archivo_url, codigo_op: expediente.codigo_op })}
                                disabled={!plano.archivo_url}
                                className="rounded bg-emerald-600 px-2 py-1 text-[10px] font-bold text-white hover:bg-emerald-700 disabled:bg-slate-300"
                              >
                                👁️ Visor PDF Plano
                              </button>
                            </td>
                          </tr>
                        );
                      });
                    })}
                    {!planos.length && <tr><td colSpan="6" className="p-5 text-center text-slate-500">No hay planos asociados a esta OP.</td></tr>}
                  </tbody>
                </table>
              </div>
            )}

            {expediente && pestana === 'insumos' && (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-extrabold text-slate-800">Abastecimiento de materia prima, herramientas y consumibles</h3>
                  {permisos.almacen && (
                    <div className="flex flex-wrap gap-2">
                      <AccionButton onClick={() => ejecutarAccion('IMPUTAR_MATERIAL_KARDEX')} className="border-blue-200 bg-blue-50 text-blue-800">📥 Imputar Material desde Kárdex</AccionButton>
                      <AccionButton onClick={() => ejecutarAccion('DESPACHAR_INSUMOS_PLANTA')} className="border-emerald-200 bg-emerald-50 text-emerald-800">📤 Despachar Insumos a Planta</AccionButton>
                    </div>
                  )}
                </div>
                <div className="overflow-x-auto rounded border border-slate-200">
                  <table className="w-full min-w-[700px] border-collapse text-left">
                    <thead className="bg-slate-100 text-[10px] uppercase text-slate-600"><tr><th className="p-2">Código / Material</th><th className="p-2">Cantidad requerida</th><th className="p-2">Estado de abastecimiento</th><th className="p-2">Lotes / coladas</th></tr></thead>
                    <tbody className="divide-y divide-slate-100">
                      {materiales.map((material, index) => (
                        <tr key={`${material.codigo_material}-${index}`}>
                          <td className="p-2"><strong>{material.codigo_material}</strong><span className="ml-2 text-slate-500">{material.descripcion}</span></td>
                          <td className="p-2">{material.cantidad_requerida} {material.unidad_medida}</td>
                          <td className="p-2"><EtiquetaEstado valor={material.estado_abastecimiento} /></td>
                          <td className="p-2">{(material.lotes || []).map((lote) => `${lote.numero_colada || lote.codigo_lote} (${lote.estado_calidad})`).join(', ') || 'Sin lote registrado'}</td>
                        </tr>
                      ))}
                      {!materiales.length && <tr><td colSpan="4" className="p-5 text-center text-slate-500">No hay líneas BOM registradas para esta OP.</td></tr>}
                    </tbody>
                  </table>
                </div>
                <h4 className="font-bold text-slate-700">Requisiciones de compra</h4>
                {(expediente.solicitudes_compra || []).map((solicitud) => (
                  <div key={solicitud.numero_solicitud} className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-200 p-2">
                    <span><strong>{solicitud.numero_solicitud}</strong> · {solicitud.nombre_item} · {solicitud.cantidad_solicitada} {solicitud.unidad_medida}</span>
                    <EtiquetaEstado valor={solicitud.estado_bom} />
                  </div>
                ))}
              </div>
            )}

            {expediente && pestana === 'mes' && (
              <div className="overflow-x-auto rounded border border-slate-200">
                <table className="w-full min-w-[800px] border-collapse text-left">
                  <thead className="bg-slate-100 text-[10px] uppercase text-slate-600"><tr><th className="p-2">Fecha</th><th className="p-2">Operario / Máquina</th><th className="p-2">Proceso / Sub-lote</th><th className="p-2">Setup</th><th className="p-2">Mecanizado</th><th className="p-2">Piezas OK / Rechazadas</th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {(expediente.tiempos_mes || []).map((registro, index) => (
                      <tr key={`${registro.fecha || registro.fecha_inicio}-${index}`}>
                        <td className="p-2">{registro.fecha || registro.fecha_inicio || '—'}</td>
                        <td className="p-2">{registro.operario || '—'} / {registro.maquina || '—'}</td>
                        <td className="p-2">{registro.proceso || registro.tipo_tiempo || '—'} {registro.numero_sublote ? `· ${registro.numero_sublote}` : ''}</td>
                        <td className="p-2">{Math.round((registro.setup_segundos || 0) / 60)} min</td>
                        <td className="p-2">{Math.round((registro.mecanizado_segundos || 0) / 60)} min</td>
                        <td className="p-2">{registro.piezas_ok ?? '—'} / {registro.piezas_rechazadas ?? '—'}</td>
                      </tr>
                    ))}
                    {!expediente.tiempos_mes?.length && <tr><td colSpan="6" className="p-5 text-center text-slate-500">No se han registrado tiempos ni sub-lotes.</td></tr>}
                  </tbody>
                </table>
              </div>
            )}

            {expediente && pestana === 'calidad' && (
              <div className="space-y-4">
                <div className="overflow-x-auto rounded border border-slate-200">
                  <table className="w-full min-w-[700px] border-collapse text-left">
                    <thead className="bg-slate-100 text-[10px] uppercase text-slate-600"><tr><th className="p-2">Fecha</th><th className="p-2">Instrumento</th><th className="p-2">Cota medida</th><th className="p-2">Tolerancia</th><th className="p-2">Dictamen</th></tr></thead>
                    <tbody className="divide-y divide-slate-100">
                      {(expediente.mediciones_metrologicas || []).map((medicion, index) => (
                        <tr key={`${medicion.instrumento}-${index}`}>
                          <td className="p-2">{medicion.fecha_inspeccion || '—'}</td>
                          <td className="p-2">{medicion.instrumento}</td>
                          <td className="p-2">{medicion.cota_medida}</td>
                          <td className="p-2">{medicion.tolerancia_min} – {medicion.tolerancia_max}</td>
                          <td className="p-2"><span className={medicion.resultado_conforme ? 'font-bold text-emerald-700' : 'font-bold text-red-700'}>{medicion.resultado_conforme ? 'Conforme' : 'No conforme'}</span></td>
                        </tr>
                      ))}
                      {!expediente.mediciones_metrologicas?.length && <tr><td colSpan="5" className="p-4 text-center text-slate-500">No hay mediciones dimensionales registradas.</td></tr>}
                    </tbody>
                  </table>
                </div>
                {(expediente.inspecciones_calidad || []).map((inspeccion) => (
                  <article key={inspeccion.id_inspeccion} className="rounded border border-slate-200 p-3">
                    <div className="flex flex-wrap justify-between gap-2">
                      <strong>{inspeccion.inspector_nombre} · {inspeccion.fecha_inspeccion}</strong>
                      <EtiquetaEstado valor={inspeccion.resultado_inspeccion} />
                    </div>
                    <p className="mt-1 text-slate-600">{inspeccion.observaciones_inspector || inspeccion.descripcion_tratamiento || 'Sin observaciones.'}</p>
                    {!!inspeccion.registros_fotograficos?.length && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {inspeccion.registros_fotograficos.map((foto, index) => (
                          <a key={`${foto}-${index}`} href={foto} target="_blank" rel="noreferrer" className="rounded border border-slate-200 px-2 py-1 text-blue-700 underline">Evidencia {index + 1}</a>
                        ))}
                      </div>
                    )}
                  </article>
                ))}
                {permisos.calidad && (
                  <div className="flex flex-wrap gap-2">
                    <AccionButton onClick={() => ejecutarAccion('REGISTRAR_INSPECCION_METROLOGICA')} className="border-purple-200 bg-purple-50 text-purple-800">🔍 Registrar Inspección Metrológica</AccionButton>
                    <AccionButton onClick={() => ejecutarAccion('SUBIR_EVIDENCIA_FOTOGRAFICA')} className="border-purple-200 bg-purple-50 text-purple-800">📷 Subir registro fotográfico</AccionButton>
                  </div>
                )}
              </div>
            )}
          </main>

          <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 bg-slate-50 px-3 py-2">
            <div className="flex flex-wrap gap-2">
              {permisos.ventas && (
                <AccionButton onClick={() => ejecutarAccion('CONSULTAR_PEDIDO_COMERCIAL')} className="border-purple-200 bg-purple-50 text-purple-800">Consultar Pedido Comercial · Entregas {pedido.estado_entregas || 'SIN_DESPACHO'}</AccionButton>
              )}
              {permisos.diseno && (
                <>
                  <AccionButton onClick={() => ejecutarAccion('CARGAR_REEMPLAZAR_PLANO')} className="border-blue-200 bg-blue-50 text-blue-800">📄 Cargar/Reemplazar Plano PDF</AccionButton>
                  <AccionButton onClick={() => ejecutarAccion('SOLICITAR_BOM')} className="border-amber-200 bg-amber-50 text-amber-800">🛒 Solicitar BOM</AccionButton>
                  <AccionButton onClick={() => ejecutarAccion('LIBERAR_OP')} disabled={!puedeLiberar || liberando} className="border-emerald-200 bg-emerald-600 text-white hover:bg-emerald-700">🟢 {liberando ? 'Liberando…' : 'Liberar OP'}</AccionButton>
                </>
              )}
              {permisos.produccion && (
                <>
                  <AccionButton onClick={() => ejecutarAccion('ASIGNAR_CENTRO_TRABAJO')} className="border-blue-200 bg-blue-50 text-blue-800">⚙️ Asignar Centro de Trabajo</AccionButton>
                  <AccionButton onClick={() => ejecutarAccion('MARCAR_OP_TERMINADA')} className="border-emerald-200 bg-emerald-50 text-emerald-800">✅ Marcar OP Terminada</AccionButton>
                </>
              )}
            </div>
            <button type="button" onClick={onClose} className="rounded bg-slate-800 px-4 py-2 font-bold text-white hover:bg-slate-900">Cerrar expediente</button>
          </footer>
        </section>
      </div>
      <VisorPlanoModal
        abierto={Boolean(planoAbierto)}
        onClose={() => setPlanoAbierto(null)}
        archivoUrl={planoAbierto?.archivo_url}
        codigoOp={planoAbierto?.codigo_op}
        codigoPlano={planoAbierto?.codigo_plano}
      />
    </>
  );
}
