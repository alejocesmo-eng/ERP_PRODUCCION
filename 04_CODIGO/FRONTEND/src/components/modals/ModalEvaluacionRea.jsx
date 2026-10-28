import React, { useState } from 'react';
import API from '../../services/api';

const ModalEvaluacionRea = ({ abierto, cerrar, idCotizacion, onActualizar }) => {
  const [datos, setDatos] = useState({
    viabilidad_tecnica: false,
    capacidad_maquinaria: false,
    disponibilidad_materiales: false,
    cumplimiento_normativo: false,
    riesgos_identificados: '',
    estado: 'PENDIENTE',
    observaciones_tecnicas: '',
    evaluador_id: '',
  });
  const [cargando, setCargando] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });

  React.useEffect(() => {
    if (abierto && idCotizacion) {
      cargarDatos();
    }
  }, [abierto, idCotizacion]);

  const cargarDatos = async () => {
    try {
      setCargando(true);
      const res = await API.get(`/rea/evaluacion/${idCotizacion}`);
      setDatos(res.data);
    } catch (err) {
      console.error("Error cargando REA:", err);
    } finally {
      setCargando(false);
    }
  };

  const handleCambio = (campo, valor) => {
    setDatos(prev => ({ ...prev, [campo]: valor }));
  };

  const handleGuardar = async () => {
    setMensaje({ tipo: '', texto: '' });
    try {
      setCargando(true);
      await API.patch(`/rea/evaluacion/${idCotizacion}`, datos);
      setMensaje({ tipo: 'exito', texto: '✅ Evaluación REA actualizada correctamente.' });
      if (onActualizar) onActualizar();
      setTimeout(() => setMensaje({ tipo: '', texto: '' }), 3000);
    } catch (err) {
      setMensaje({ tipo: 'error', texto: '❌ Error al guardar la evaluación.' });
    } finally {
      setCargando(false);
    }
  };

  if (!abierto) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in duration-200">
        <header className="bg-slate-800 p-4 text-white flex justify-between items-center">
          <div>
            <h2 className="text-lg font-bold flex items-center gap-2">
              <span>🛡️</span> Evaluación Técnica REA
            </h2>
            <p className="text-xs text-slate-300">Revisión de Especificaciones Técnicas y Acuerdos</p>
          </div>
          <button onClick={cerrar} className="text-slate-400 hover:text-white text-2xl leading-none">&times;</button>
        </header>

        <div className="p-6 space-y-6">
          {mensaje.texto && (
            <div className={`p-3 rounded-lg text-xs font-bold border ${mensaje.tipo === 'exito' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-red-50 text-red-800 border-red-200'}`}>
              {mensaje.texto}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <h3 className="text-sm font-black text-slate-500 uppercase tracking-wider border-b pb-1">Criterios de Viabilidad</h3>

              {[
                { id: 'viabilidad_tecnica', label: 'Viabilidad Técnica General' },
                { id: 'capacidad_maquinaria', label: 'Capacidad de Maquinaria Instalada' },
                { id: 'disponibilidad_materiales', label: 'Disponibilidad de Materiales' },
                { id: 'cumplimiento_normativo', label: 'Cumplimiento de Normas/Estándares' },
              ].map(item => (
                <label key={item.id} className="flex items-center gap-3 p-3 rounded-lg border border-slate-100 hover:bg-slate-50 cursor-pointer transition">
                  <input
                    type="checkbox"
                    className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
                    checked={datos[item.id]}
                    onChange={(e) => handleCambio(item.id, e.target.checked)}
                  />
                  <span className="text-sm font-medium text-slate-700">{item.label}</span>
                </label>
              ))}
            </div>

            <div className="space-y-4">
              <h3 className="text-sm font-black text-slate-500 uppercase tracking-wider border-b pb-1">Dictamen Técnico</h3>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1 uppercase">Estado de la Evaluación</label>
                <select
                  value={datos.estado}
                  onChange={(e) => handleCambio('estado', e.target.value)}
                  className="w-full p-2 border border-slate-300 rounded-lg text-sm bg-slate-50 focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="PENDIENTE">PENDIENTE</option>
                  <option value="EN_REVISION">EN REVISIÓN</option>
                  <option value="APROBADO">APROBADO ✅</option>
                  <option value="RECHAZADO">RECHAZADO ❌</option>
                  <option value="OBSERVADO">OBSERVADO ⚠️</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1 uppercase">Observaciones Técnicas</label>
                <textarea
                  className="w-full p-2 border border-slate-300 rounded-lg text-sm h-24 bg-slate-50 focus:ring-2 focus:ring-blue-500 outline-none"
                  value={datos.observaciones_tecnicas}
                  onChange={(e) => handleCambio('observaciones_tecnicas', e.target.value)}
                  placeholder="Detalles técnicos, limitaciones o requerimientos adicionales..."
                />
              </div>
            </div>
          </div>

          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
            <label className="block text-xs font-bold text-slate-500 mb-1 uppercase">Riesgos Identificados</label>
            <textarea
              className="w-full p-2 border border-slate-300 rounded-lg text-sm h-20 bg-white focus:ring-2 focus:ring-blue-500 outline-none"
              value={datos.riesgos_identificados}
              onChange={(e) => handleCambio('riesgos_identificados', e.target.value)}
              placeholder="Describa posibles riesgos técnicos o comerciales..."
            />
          </div>
        </div>

        <footer className="p-4 bg-slate-50 border-t border-slate-200 flex justify-end gap-3">
          <button
            onClick={cerrar}
            className="px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-200 rounded-lg transition"
          >
            Cancelar
          </button>
          <button
            onClick={handleGuardar}
            disabled={cargando}
            className={`px-6 py-2 text-sm font-bold text-white rounded-lg transition shadow-sm ${cargando ? 'bg-slate-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}`}
          >
            {cargando ? 'Guardando...' : 'Guardar Evaluación'}
          </button>
        </footer>
      </div>
    </div>
  );
};

export default ModalEvaluacionRea;
