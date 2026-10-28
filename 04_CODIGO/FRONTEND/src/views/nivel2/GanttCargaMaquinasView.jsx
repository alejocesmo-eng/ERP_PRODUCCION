import React, { useCallback, useEffect, useState } from 'react';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
const ESTADOS_OPERACION = {
  PENDIENTE: 'Pendiente',
  PENDIENTE_ASIGNACION: 'Pendiente de asignación',
  EN_COLA: 'En cola',
  EN_SETUP: 'En preparación de máquina',
  EN_PRODUCCION: 'En producción',
  PAUSADA: 'Pausada',
  PARCIALMENTE_COMPLETADA: 'Entrega parcial',
  COMPLETADA: 'Completada'
};

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('sgi_token') || ''}`, ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Error al consultar la carga de planta.');
  return body;
}

export default function GanttCargaMaquinasView() {
  const [data, setData] = useState({ centros: [], maquinas_disponibles: [] });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState('');

  const load = useCallback(async () => {
    try {
      setData(await request('/produccion/carga-maquinas'));
      setError('');
    } catch (err) { setError(err.message); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const reassign = async (id, maquina_codigo) => {
    if (!maquina_codigo) return;
    setSaving(id);
    try {
      await request(`/produccion/carga-maquinas/sublotes/${id}/maquina`, {
        method: 'PATCH',
        body: JSON.stringify({ maquina_codigo }),
      });
      await load();
    } catch (err) { setError(err.message); } finally { setSaving(''); }
  };

  return (
    <main className="space-y-4 p-4 text-xs text-slate-700">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div><h1 className="text-xl font-bold text-slate-800">Programación de carga y capacidad de planta</h1><p className="mt-1 text-slate-500">Carga estimada por centro de trabajo, tiempos de Ingeniería y fecha comprometida de Ventas.</p></div>
        <button onClick={load} className="rounded border border-slate-300 px-3 py-2 font-semibold hover:bg-slate-50">Actualizar tablero</button>
      </header>
      {error && <div role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700">{error}</div>}
      {data.centros.length === 0 && !error && <div className="rounded border border-amber-200 bg-amber-50 p-3 text-amber-800">No hay sublotes abiertos asignados; las operaciones sin máquina permanecen pendientes de asignación.</div>}

      <div className="space-y-4">
        {data.centros.map((center) => {
          return (
            <section key={center.centro_trabajo} className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-slate-50 px-4 py-3">
                <h2 className="font-bold text-slate-800">{center.centro_trabajo}</h2>
                <span className="font-semibold text-slate-700">{center.horas_ocupadas} h de carga pendiente acumulada</span>
              </div>
              <div className="grid gap-3 border-b p-3 sm:grid-cols-2 xl:grid-cols-4">
                {center.carga_por_fecha.map((day) => {
                  const pct = Math.min(day.porcentaje_carga, 100);
                  const overload = day.porcentaje_carga > 100;
                  return <div key={day.fecha} className="rounded border border-slate-200 p-2"><div className="flex justify-between gap-2"><strong>{day.fecha === 'SIN_FECHA' ? 'Sin fecha prometida' : day.fecha}</strong><span className={overload ? 'text-red-700' : 'text-emerald-700'}>{day.horas_ocupadas} / {day.capacidad_turno_horas} h</span></div><div className="mt-2 h-2 bg-slate-100"><div className={`h-2 ${overload ? 'bg-red-500' : 'bg-emerald-500'}`} style={{ width: `${pct}%` }} /></div><span className="mt-1 block text-right text-slate-500">{day.porcentaje_carga}% de un turno</span></div>;
                })}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left"><thead className="text-slate-500"><tr><th className="px-3 py-1.5">Orden / Plano / Proceso</th><th className="px-3 py-1.5">Máquina</th><th className="px-3 py-1.5">Carga estimada</th><th className="px-3 py-1.5">Entrega prometida</th><th className="px-3 py-1.5">Estado</th><th className="px-3 py-1.5">Reasignar máquina</th></tr></thead>
                  <tbody>{center.ordenes.map((order) => <tr key={order.id_sublote || order.codigo_op} className="border-t"><td className="px-3 py-1.5"><strong>{order.codigo_op}</strong><span className="block text-slate-500">{order.codigo_plano} · {order.proceso}</span></td><td className="px-3 py-1.5">{order.maquina_codigo || 'Sin asignar'}</td><td className="px-3 py-1.5">{order.horas_setup_estimadas} h de preparación + {order.horas_mecanizado_estimadas} h de mecanizado</td><td className="px-3 py-1.5">{order.fecha_entrega || 'Sin fecha'}</td><td className="px-3 py-1.5">{ESTADOS_OPERACION[order.estado] || order.estado}</td><td className="px-3 py-1.5">{order.id_sublote ? <select disabled={saving === order.id_sublote} aria-label={`Reasignar máquina para ${order.codigo_op}`} className="rounded border p-1" value="" onChange={(event) => reassign(order.id_sublote, event.target.value)}><option value="">Seleccionar máquina</option>{data.maquinas_disponibles.map((machine) => <option key={machine.codigo_maquina} value={machine.codigo_maquina}>{machine.codigo_maquina} · {machine.centro_trabajo || 'Sin centro'}</option>)}</select> : <span className="text-slate-500">Crear sublote desde Producción</span>}</td></tr>)}</tbody>
                </table>
              </div>
            </section>
          );
        })}
      </div>
    </main>
  );
}
