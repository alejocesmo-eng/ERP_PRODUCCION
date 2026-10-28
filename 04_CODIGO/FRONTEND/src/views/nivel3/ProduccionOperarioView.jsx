import React, { useState, useEffect } from 'react';
import API from '../../services/api';

export default function ProduccionOperarioView() {
  // =========================================================================
  // BLOQUE 1: ESTADOS DE SESIÓN DE OPERARIO Y ORDEN ACTIVA
  // =========================================================================
  const [operarioLogueado, setOperarioLogueado] = useState('Carlos Ruiz');
  const [estacionMaquina, setEstacionMaquina] = useState('TORN-CNC-01');
  const [colaOrdenes, setColaOrdenes] = useState([]);
  const [ordenEnCurso, setOrdenEnCurso] = useState(null);
  const [errorCola, setErrorCola] = useState('');
  
  // Estado del proceso en tablet: 'COLA' | 'SETUP' | 'PRODUCCION' | 'PAUSA' | 'REPORTE'
  const [faseTrabajo, setFaseTrabajo] = useState('COLA');
  
  // Control de Zoom para el Visor de Planos PDF
  const [nivelZoom, setNivelZoom] = useState(100);
  
  // Timers Ocultos en Segundo Plano (Costeo MES)
  const [tiempoSetup, setTiempoSetup] = useState(0);
  const [tiempoProduccion, setTiempoProduccion] = useState(0);
  const [tiempoPausa, setTiempoPausa] = useState(0);

  // Control de Pausas
  const [modalPausaAbierto, setModalPausaAbierto] = useState(false);
  const [motivoPausa, setMotivoPausa] = useState('Almuerzo / Descanso de Horario');

  // Formulario de Reporte de Cierre
  const [piezasOk, setPiezasOk] = useState(0);
  const [piezasScrap, setPiezasScrap] = useState(0);
  const [novedades, setNovedades] = useState('');

  // =========================================================================
  // BLOQUE 2: CARGA DE LA COLA Y CRONÓMETROS OCULTOS EN TIEMPO REAL
  // =========================================================================
  useEffect(() => {
    cargarColaOperario();
    const actualizacion = window.setInterval(cargarColaOperario, 2000);
    return () => window.clearInterval(actualizacion);
  }, [operarioLogueado, estacionMaquina, ordenEnCurso?.id_sublote]);

  useEffect(() => {
    let timer = null;
    if (faseTrabajo === 'SETUP') {
      timer = setInterval(() => setTiempoSetup(prev => prev + 1), 1000);
    } else if (faseTrabajo === 'PRODUCCION') {
      timer = setInterval(() => setTiempoProduccion(prev => prev + 1), 1000);
    } else if (faseTrabajo === 'PAUSA') {
      timer = setInterval(() => setTiempoPausa(prev => prev + 1), 1000);
    } else {
      clearInterval(timer);
    }
    return () => clearInterval(timer);
  }, [faseTrabajo]);

  const cargarColaOperario = async () => {
    try {
      const params = new URLSearchParams({ maquina: estacionMaquina, operario_nombre: operarioLogueado });
      const res = await API.get(`/operaciones/sublotes?${params.toString()}`);
      if (!Array.isArray(res.data)) throw new Error('La respuesta de cola no tiene un formato válido.');
      const estadosEnCola = ['PENDIENTE', 'PENDIENTE_ASIGNACION', 'EN_COLA'];
      setColaOrdenes(res.data.filter((item) =>
        item.id_sublote !== ordenEnCurso?.id_sublote
        && estadosEnCola.includes(item.estado_sublote)
      ));
      setErrorCola('');
    } catch (error) {
      setErrorCola(error.response?.data?.detail || error.message || 'No fue posible actualizar la cola de trabajo.');
    }
  };

  const actualizarEstadoSublote = async (sublote, estado_sublote) => {
    try {
      await API.patch(`/operaciones/sublotes/${sublote.id_sublote}/estado`, { estado_sublote });
      setErrorCola('');
      return true;
    } catch (error) {
      setErrorCola(error.response?.data?.detail || error.message || 'No se pudo sincronizar el estado del trabajo.');
      return false;
    }
  };

  // =========================================================================
  // BLOQUE 3: CONTROL DE ZOOM
  // =========================================================================
  const handleZoomIn = () => setNivelZoom(prev => Math.min(prev + 25, 250));
  const handleZoomOut = () => setNivelZoom(prev => Math.max(prev - 25, 75));
  const handleResetZoom = () => setNivelZoom(100);

  // =========================================================================
  // BLOQUE 4: ACCIONES DE TRANSICIÓN
  // =========================================================================
  const handleAbrirOrdenSetup = async (orden) => {
    if (!await actualizarEstadoSublote(orden, 'EN_SETUP')) return;
    setOrdenEnCurso(orden);
    setPiezasOk(orden.cantidad_asignada);
    setPiezasScrap(0);
    setNovedades('');
    setNivelZoom(100);
    setTiempoSetup(0);
    setTiempoProduccion(0);
    setTiempoPausa(0);
    setFaseTrabajo('SETUP');
  };

  const handleIniciarTrabajoMaquina = async () => {
    if (!await actualizarEstadoSublote(ordenEnCurso, 'EN_PRODUCCION')) return;
    setFaseTrabajo('PRODUCCION');
  };

  const handleConfirmarPausa = async (motivo) => {
    if (!await actualizarEstadoSublote(ordenEnCurso, 'PAUSADA')) return;
    setMotivoPausa(motivo);
    setFaseTrabajo('PAUSA');
    setModalPausaAbierto(false);
  };

  const handleReanudarProduccion = async () => {
    if (!await actualizarEstadoSublote(ordenEnCurso, 'EN_PRODUCCION')) return;
    setFaseTrabajo('PRODUCCION');
  };

  const handleIrAReporte = () => {
    setFaseTrabajo('REPORTE');
  };

  const handleFinalizarOrdenCompleta = async (e) => {
    e.preventDefault();

    if (piezasOk < 0 || piezasScrap < 0) {
      return;
    }

    try {
      const payloadReporte = {
        id_sublote: ordenEnCurso.id_sublote,
        codigo_op: ordenEnCurso.codigo_op,
        operario: operarioLogueado,
        maquina: estacionMaquina,
        piezas_ok: piezasOk,
        piezas_scrap: piezasScrap,
        segundos_setup: tiempoSetup,
        segundos_produccion: tiempoProduccion,
        segundos_pausa: tiempoPausa,
        motivo_pausa: tiempoPausa > 0 ? motivoPausa : null,
        novedades: novedades
      };

      await API.post('/operaciones/sublotes/finalizar', payloadReporte);
      setErrorCola('');
    } catch (error) {
      setErrorCola(error.response?.data?.detail || 'No se pudo registrar el cierre. La orden permanece activa.');
      return;
    }

    const colaRestante = colaOrdenes.filter(o => o.id_sublote !== ordenEnCurso.id_sublote);
    setColaOrdenes(colaRestante);
    setOrdenEnCurso(null);
    setFaseTrabajo('COLA');
  };

  // =========================================================================
  // BLOQUE 5: RENDERIZADO MODO TABLET PLANTA (100% PANTALLA)
  // =========================================================================
  return (
    <div className="p-2 bg-slate-950 min-h-screen font-sans text-slate-100 flex flex-col justify-between space-y-1.5 select-none">
      {/* CABECERA INTEGRADA: MÁQUINA + PIEZA + ACCIONES + BADGE ESTADO */}
      <header className="bg-slate-900 p-2.5 px-3 rounded-xl border border-slate-800 shadow-md flex justify-between items-center gap-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">📍</span>
          <div>
            <span className="text-xs font-black text-blue-400 block leading-none">Estación: {estacionMaquina}</span>
            <span className="text-[10px] text-slate-400">Operario: <strong className="text-white">{operarioLogueado}</strong></span>
          </div>
        </div>

        {/* INFORMACIÓN COMPLETA DE LA PIEZA ACTIVA Y PROCESO */}
        {ordenEnCurso ? (
          <div className="flex items-center gap-2 bg-slate-800 p-1 px-3 rounded-lg border border-slate-700 flex-1 max-w-2xl mx-2">
            <span className="font-mono font-bold text-xs text-blue-300 whitespace-nowrap">⚙️ OP-{ordenEnCurso.codigo_op}</span>
            <span className="text-xs text-slate-100 font-bold leading-tight">{ordenEnCurso.detalle_pieza}</span>
            <span className="text-[10px] bg-purple-900/60 text-purple-300 font-bold px-2 py-0.5 rounded border border-purple-700 whitespace-nowrap">
              {ordenEnCurso.nombre_proceso} (Paso {ordenEnCurso.secuencia_paso})
            </span>
            <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/50 text-[10px] font-extrabold px-2 py-0.5 rounded whitespace-nowrap ml-auto">
              {ordenEnCurso.cantidad_asignada} UND
            </span>
          </div>
        ) : (
          <span className="text-xs font-bold text-slate-500 bg-slate-800 px-3 py-1 rounded border border-slate-700">
            Esperando Selección de Orden
          </span>
        )}

        {/* BOTONES DE ACCIÓN REUBICADOS EN LA CABECERA + BADGE DE ESTADO */}
        <div className="flex items-center gap-2">
          {faseTrabajo === 'SETUP' && (
            <button
              type="button"
              onClick={handleIniciarTrabajoMaquina}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.99] text-slate-950 font-black text-xs rounded-lg shadow-lg transition flex items-center gap-1 cursor-pointer"
            >
              <span>🟢</span> Iniciar Trabajo
            </button>
          )}

          {faseTrabajo === 'PRODUCCION' && (
            <button
              type="button"
              onClick={() => setModalPausaAbierto(true)}
              className="px-3 py-1.5 bg-amber-900/60 hover:bg-amber-800 text-amber-200 border border-amber-700 font-extrabold text-xs rounded-lg transition flex items-center gap-1 cursor-pointer"
            >
              <span>⏸️</span> Pausa
            </button>
          )}

          {faseTrabajo === 'PAUSA' && (
            <button
              type="button"
              onClick={handleReanudarProduccion}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs rounded-lg transition flex items-center gap-1 cursor-pointer animate-pulse"
            >
              <span>▶️</span> Reanudar
            </button>
          )}

          {(faseTrabajo === 'PRODUCCION' || faseTrabajo === 'PAUSA') && (
            <button
              type="button"
              onClick={handleIrAReporte}
              disabled={faseTrabajo === 'PAUSA'}
              className={`px-3 py-1.5 rounded-lg font-extrabold text-xs transition flex items-center gap-1 cursor-pointer ${
                faseTrabajo !== 'PAUSA'
                  ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-md'
                  : 'bg-slate-800 text-slate-600 cursor-not-allowed'
              }`}
            >
              <span>🔴</span> Finalizar Lote
            </button>
          )}

          {/* BADGE ESTADO */}
          <span className={`px-3 py-1.5 rounded-full text-[11px] font-black uppercase tracking-wider border shadow-md flex items-center gap-1 ${
            faseTrabajo === 'SETUP'
              ? 'bg-purple-950/80 text-purple-300 border-purple-500 shadow-purple-900/50'
              : faseTrabajo === 'PRODUCCION'
              ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500 shadow-emerald-900/50 animate-pulse'
              : faseTrabajo === 'PAUSA'
              ? 'bg-amber-950/80 text-amber-300 border-amber-500 shadow-amber-900/50 animate-pulse'
              : 'bg-slate-800 text-slate-400 border-slate-700'
          }`}>
            {faseTrabajo === 'SETUP' && <span>🔧 EN SETUP</span>}
            {faseTrabajo === 'PRODUCCION' && <span>⚙️ EN PRODUCCIÓN</span>}
            {faseTrabajo === 'PAUSA' && <span>⏸️ EN PAUSA</span>}
            {faseTrabajo === 'COLA' && <span>🟢 EN COLA</span>}
          </span>
        </div>
      </header>
      {errorCola && (
        <div role="alert" className="rounded-lg border border-amber-700 bg-amber-950 px-3 py-2 text-[11px] font-semibold text-amber-200">
          {errorCola}
        </div>
      )}

      {/* FASE 1: VISTA DE COLA DE TRABAJO */}
      {faseTrabajo === 'COLA' && (
        <div className="flex-1 flex flex-col justify-center items-center space-y-4 max-w-2xl mx-auto w-full">
          {colaOrdenes.length === 0 ? (
            <div className="bg-slate-900 p-8 rounded-2xl border border-slate-800 text-center space-y-2 w-full shadow-2xl">
              <span className="text-3xl">🎉</span>
              <h2 className="text-xl font-bold text-emerald-400">¡Cola de Trabajo al Día!</h2>
              <p className="text-xs text-slate-400">No hay órdenes pendientes asignadas a esta estación.</p>
            </div>
          ) : (
            <div className="bg-slate-900 p-5 rounded-2xl border-2 border-blue-500 shadow-2xl space-y-4 w-full">
              <div className="flex justify-between items-start border-b border-slate-800 pb-3">
                <div>
                  <span className="px-2 py-0.5 bg-amber-500 text-slate-950 font-black rounded text-[10px] uppercase">
                    Siguiente Trabajo (FIFO)
                  </span>
                  <h2 className="text-2xl font-black text-white mt-1">OT-{colaOrdenes[0].codigo_op}</h2>
                  <p className="text-xs font-bold text-blue-400 leading-snug">{colaOrdenes[0].detalle_pieza}</p>
                </div>
                <div className="bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700 text-center">
                  <span className="text-lg font-black text-emerald-400 block">{colaOrdenes[0].cantidad_asignada} UND</span>
                  <span className="text-[9px] text-slate-400 font-bold uppercase">A Procesar</span>
                </div>
              </div>

              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-xs space-y-1 text-slate-300">
                <p><strong>N° Pedido:</strong> {colaOrdenes[0].numero_pedido}</p>
                <p><strong>Plano Técnico:</strong> <span className="font-mono text-purple-300 font-bold">{colaOrdenes[0].codigo_plano} ({colaOrdenes[0].revision})</span></p>
                <p><strong>Instrucción del Líder:</strong> {colaOrdenes[0].instrucciones || 'Procesar según plano.'}</p>
              </div>

              <button
                type="button"
                onClick={() => handleAbrirOrdenSetup(colaOrdenes[0])}
                className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 active:scale-[0.99] text-white font-black text-sm rounded-xl shadow-xl transition flex items-center justify-center gap-2 cursor-pointer"
              >
                <span>📄</span> Ver Orden y Preparar Máquina (Setup)
              </button>
            </div>
          )}
        </div>
      )}

      {/* FASE 2, 3 Y 4: SETUP, PRODUCCIÓN Y PAUSA (VISOR PDF A PANTALLA COMPLETA 100%) */}
      {(faseTrabajo === 'SETUP' || faseTrabajo === 'PRODUCCION' || faseTrabajo === 'PAUSA') && ordenEnCurso && (
        <div className="flex-1 bg-slate-900 p-2 rounded-xl border border-slate-800 flex flex-col shadow-xl space-y-1.5">
          <div className="flex justify-between items-center pb-1.5 border-b border-slate-800">
            {/* INFORMACIÓN TÉCNICA DEL PLANO */}
            <div className="flex items-center gap-2">
              <span className="text-xs">📐</span>
              <span className="text-xs font-mono font-black text-purple-300">
                {ordenEnCurso.codigo_plano}
              </span>
              <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-700 font-bold">
                {ordenEnCurso.revision}
              </span>
              {faseTrabajo === 'PAUSA' && (
                <span className="text-amber-400 font-bold text-xs ml-2 animate-pulse">
                  ⏸️ Estación Pausada por: {motivoPausa}
                </span>
              )}
            </div>

            {/* CONTROLES DE ZOOM DE ALTA PRECISIÓN (SIN BOTÓN PDF) */}
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
              <button
                type="button"
                onClick={handleZoomOut}
                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white font-bold rounded text-xs cursor-pointer"
                title="Reducir Zoom"
              >
                🔍 -
              </button>
              <span className="px-2 font-mono font-bold text-blue-400 text-xs">
                {nivelZoom}%
              </span>
              <button
                type="button"
                onClick={handleZoomIn}
                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white font-bold rounded text-xs cursor-pointer"
                title="Aumentar Zoom"
              >
                🔍 +
              </button>
              <button
                type="button"
                onClick={handleResetZoom}
                className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold rounded text-xs cursor-pointer"
                title="Restablecer Zoom"
              >
                🔄
              </button>
            </div>
          </div>

          {/* MARCO PDF MAXIMIZADO AL 100% DEL ESPACIO DE LA TABLET */}
          <div className="flex-1 bg-slate-950 rounded-xl overflow-auto min-h-[620px] h-[calc(100vh-120px)] p-1 flex items-start justify-center">
            <div 
              className="transition-transform duration-200 origin-top w-full h-full flex justify-center"
              style={{ transform: `scale(${nivelZoom / 100})`, width: `${nivelZoom}%` }}
            >
              <iframe
                src={ordenEnCurso.archivo_url}
                title={`Plano Técnico ${ordenEnCurso.codigo_plano}`}
                className="w-full h-full min-h-[640px] border-none rounded-xl"
              />
            </div>
          </div>
        </div>
      )}

      {/* MODAL 1: SELECCIÓN DE MOTIVO DE PAUSA */}
      {modalPausaAbierto && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-slate-800 rounded-xl shadow-2xl max-w-md w-full p-5 space-y-4 border border-amber-600 text-xs">
            <div className="flex justify-between items-center border-b border-slate-700 pb-2">
              <h3 className="text-sm font-bold text-amber-400 flex items-center gap-1.5">
                <span>⏸️</span> Registrar Motivo de Pausa / Parada
              </h3>
              <button onClick={() => setModalPausaAbierto(false)} className="text-slate-400 hover:text-white font-bold text-sm cursor-pointer">✕</button>
            </div>

            <p className="text-[11px] text-slate-300">
              Seleccione la causa de la parada para congelar la estación:
            </p>

            <div className="grid grid-cols-1 gap-1.5">
              {[
                'Almuerzo / Descanso de Horario',
                'Necesidad Personal',
                'Falta de materia prima o insumo requerido',
                'Falla Mecánica / Mantenimiento',
                'Ajuste o Cambio de Herramental',
                'Espera de Inspección de Calidad'
              ].map((motivo) => (
                <button
                  key={motivo}
                  type="button"
                  onClick={() => handleConfirmarPausa(motivo)}
                  className="w-full text-left p-2.5 bg-slate-900 hover:bg-amber-900/40 border border-slate-700 hover:border-amber-500 rounded-lg text-xs font-bold text-slate-200 transition cursor-pointer flex items-center justify-between"
                >
                  <span>{motivo}</span>
                  <span className="text-amber-400 text-xs">➔</span>
                </button>
              ))}
            </div>

            <div className="flex justify-end border-t border-slate-700 pt-2">
              <button
                type="button"
                onClick={() => setModalPausaAbierto(false)}
                className="px-3.5 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 font-bold rounded text-xs cursor-pointer"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: FORMULARIO DE REPORTE Y CIERRE DE TRABAJO */}
      {faseTrabajo === 'REPORTE' && ordenEnCurso && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-slate-800 p-5 rounded-2xl border border-slate-700 shadow-2xl max-w-xl w-full space-y-4 text-xs">
            <div className="border-b border-slate-700 pb-2">
              <h2 className="text-lg font-black text-white">Reporte de Cierre: OT-{ordenEnCurso.codigo_op}</h2>
              <p className="text-xs font-bold text-slate-400">{ordenEnCurso.detalle_pieza}</p>
            </div>

            <form onSubmit={handleFinalizarOrdenCompleta} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-900 p-3 rounded-xl border border-emerald-800 text-center">
                  <label className="block font-bold text-emerald-400 mb-1">Piezas Conformes (OK) *</label>
                  <input
                    type="number"
                    min="0"
                    required
                    value={piezasOk}
                    onChange={(e) => setPiezasOk(parseInt(e.target.value) || 0)}
                    className="w-full p-2 bg-slate-800 border border-emerald-500 rounded text-center text-xl font-black text-white"
                  />
                </div>

                <div className="bg-slate-900 p-3 rounded-xl border border-red-800 text-center">
                  <label className="block font-bold text-red-400 mb-1">Piezas Defectuosas (Scrap) *</label>
                  <input
                    type="number"
                    min="0"
                    required
                    value={piezasScrap}
                    onChange={(e) => setPiezasScrap(parseInt(e.target.value) || 0)}
                    className="w-full p-2 bg-slate-800 border border-red-500 rounded text-center text-xl font-black text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-300 mb-1">Novedades u Observaciones del Mecanizado</label>
                <textarea
                  rows="2"
                  placeholder="Escriba aquí si hubo desgaste de herramienta o inconvenientes..."
                  value={novedades}
                  onChange={(e) => setNovedades(e.target.value)}
                  className="w-full p-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-200"
                ></textarea>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setFaseTrabajo('PRODUCCION')}
                  className="w-1/3 py-2.5 bg-slate-700 hover:bg-slate-600 text-white font-bold rounded-xl cursor-pointer"
                >
                  Regresar
                </button>
                <button
                  type="submit"
                  className="w-2/3 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-black rounded-xl shadow-xl transition cursor-pointer"
                >
                  ✓ Confirmar y Pasar a Siguiente Orden
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* FOOTER INFORMATIVO PLANTA */}
      <footer className="text-center text-[10px] text-slate-500 pt-1 border-t border-slate-900">
        Sistema de ejecución de producción en planta [ISO 9001:2026]
      </footer>
    </div>
  );
}