import React, { useState, useEffect } from 'react';
import API from '../../services/api';

export default function GeneracionOPView() {
  const [proyectos, setProyectos] = useState([]);
  const [ordenes, setOrdenes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });

  const [nuevaOrden, setNuevaOrden] = useState({
    codigo_op: '',
    id_proyecto: '',
    id_plano: '',
    cantidad_programada: 1
  });

  useEffect(() => {
    cargarDatos();
  }, []);

  const cargarDatos = async () => {
    try {
      setLoading(true);
      const [resProj, resOrd] = await Promise.allSettled([
        API.get('/proyectos/'),
        API.get('/ordenes/')
      ]);

      if (resProj.status === 'fulfilled') {
        const confirmados = (Array.isArray(resProj.value.data) ? resProj.value.data : [])
          .filter(p => p.confirmado || p.estado === 'CONFIRMADO');
        setProyectos(confirmados);
      }

      if (resOrd.status === 'fulfilled') {
        setOrdenes(Array.isArray(resOrd.value.data) ? resOrd.value.data : []);
      }
    } catch (error) {
      console.warn("Error consultando datos de OP:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    setNuevaOrden({ ...nuevaOrden, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMensaje({ tipo: '', texto: '' });

    if (!nuevaOrden.codigo_op || !nuevaOrden.id_proyecto) {
      setMensaje({ tipo: 'error', texto: 'Por favor seleccione un proyecto e ingrese el código de OP.' });
      return;
    }

    const payload = {
      codigo_op: nuevaOrden.codigo_op,
      id_proyecto: nuevaOrden.id_proyecto,
      id_plano: nuevaOrden.id_plano || nuevaOrden.id_proyecto,
      cantidad_programada: parseInt(nuevaOrden.cantidad_programada, 10) || 1
    };

    try {
      setLoading(true);
      await API.post('/ordenes/', payload);
      setMensaje({ tipo: 'exito', texto: '✅ Orden de Producción emitida y liberada correctamente.' });
      setNuevaOrden({
        codigo_op: '',
        id_proyecto: '',
        id_plano: '',
        cantidad_programada: 1
      });
      cargarDatos();
    } catch (error) {
      console.error("Error al registrar OP:", error.response?.data);
      const detalle = error.response?.data?.detail;
      const msg = Array.isArray(detalle)
        ? detalle.map(d => `${d.loc ? d.loc.join('->') : 'Campo'}: ${d.msg}`).join(', ')
        : (typeof detalle === 'string' ? detalle : 'Error de comunicación con la API (verifique que el Backend en el puerto 8000 esté activo).');

      setMensaje({ tipo: 'error', texto: `Error al registrar: ${msg}` });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-slate-50 min-h-screen">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Centro de Control de Calidad — Emisión de OP</h1>
        <p className="text-sm text-slate-600">Validación técnica y emisión oficial de Órdenes de Producción [ISO 9001:2026]</p>
      </header>

      {mensaje.texto && (
        <div className={`p-4 mb-6 rounded text-sm font-medium ${
          mensaje.tipo === 'exito' ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-red-100 text-red-800 border border-red-300'
        }`}>
          {mensaje.texto}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white p-5 rounded border border-slate-200 shadow-sm lg:col-span-1">
          <h2 className="text-lg font-semibold text-slate-700 mb-4">Generar Nueva OP</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Código de OP *</label>
              <input
                type="text"
                name="codigo_op"
                placeholder="Ej. OP-2026-001"
                value={nuevaOrden.codigo_op}
                onChange={handleChange}
                className="w-full p-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Proyecto Confirmado *</label>
              <select
                name="id_proyecto"
                value={nuevaOrden.id_proyecto}
                onChange={handleChange}
                className="w-full p-2 border border-slate-300 rounded text-sm bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="">-- Seleccionar Proyecto --</option>
                {proyectos.map((p) => (
                  <option key={p.id_proyecto || p.id} value={p.id_proyecto || p.id}>
                    {p.codigo_proyecto || p.codigo} - {p.cliente_nombre || p.cliente}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1">Cantidad Programada *</label>
              <input
                type="number"
                name="cantidad_programada"
                min="1"
                value={nuevaOrden.cantidad_programada}
                onChange={handleChange}
                className="w-full p-2 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded text-sm transition"
            >
              {loading ? 'Procesando...' : 'Emitir y Liberar OP'}
            </button>
          </form>
        </div>

        <div className="bg-white p-5 rounded border border-slate-200 shadow-sm lg:col-span-2 flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-700 mb-4">Órdenes de Producción en Sistema</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600">
                <thead className="bg-slate-100 text-slate-700 font-semibold uppercase border-b border-slate-200">
                  <tr>
                    <th className="p-2.5">Código OP</th>
                    <th className="p-2.5">Cantidad</th>
                    <th className="p-2.5">Stock Reservado</th>
                    <th className="p-2.5">Estado SGI</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {ordenes.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="p-4 text-center text-slate-400">No hay órdenes de producción generadas aún.</td>
                    </tr>
                  ) : (
                    ordenes.map((op) => (
                      <tr key={op.id_op} className="hover:bg-slate-50">
                        <td className="p-2.5 font-bold text-slate-800">{op.codigo_op}</td>
                        <td className="p-2.5">{op.cantidad_programada} UND</td>
                        <td className="p-2.5">
                          <span className={op.stock_disponible_100 ? "text-emerald-600 font-bold" : "text-amber-600 font-bold"}>
                            {op.stock_disponible_100 ? "✓ 100%" : "⚠ Incompleto"}
                          </span>
                        </td>
                        <td className="p-2.5">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                            {op.estado}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 text-blue-900 rounded text-xs">
            <strong>Supervisión de Calidad:</strong> Las OPs en estado LIBERADA_A_PRODUCCION se reflejan automáticamente en el piso de planta para su fabricación.
          </div>
        </div>
      </div>
    </div>
  );
}