import React, { useCallback, useEffect, useState } from 'react';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
const emptyMachine = { codigo_maquina: '', nombre: '', centro_trabajo_asociado: '', estado_maquina: 'OPERATIVA' };
const card = 'rounded-lg border border-slate-200 bg-white p-4 shadow-sm';
const centrosTrabajo = [
  'CC-100-MECANIZADO',
  'CC-200-METALISTERIA',
  'CC-300-SERVICIOS',
];
const estadoMaquina = {
  OPERATIVA: 'Operativa',
  EN_MANTENIMIENTO: 'En mantenimiento',
  FUERA_DE_SERVICIO: 'Fuera de servicio'
};
const estiloEstadoMaquina = {
  OPERATIVA: 'bg-emerald-50 text-emerald-800',
  EN_MANTENIMIENTO: 'bg-amber-50 text-amber-800',
  FUERA_DE_SERVICIO: 'bg-red-50 text-red-800',
};
const estadoOrden = {
  ABIERTA: 'Abierta',
  EN_PROCESO: 'En proceso',
  CERRADA: 'Cerrada'
};
const tipoOrden = {
  PREVENTIVO: 'Mantenimiento preventivo',
  CORRECTIVO: 'Mantenimiento correctivo',
  OVERHAUL: 'Reacondicionamiento general',
};

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('sgi_token') || ''}`,
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'No se pudo completar la solicitud.');
  return body;
}

export default function MantenimientoPlantaView() {
  const [equipos, setEquipos] = useState([]);
  const [ordenes, setOrdenes] = useState([]);
  const [machine, setMachine] = useState(emptyMachine);
  const [form, setForm] = useState({ id_equipo: '', tipo: 'PREVENTIVO', descripcion_falla: '', repuestos: '', fecha_programada: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [ordenEnAccion, setOrdenEnAccion] = useState('');

  const load = useCallback(async () => {
    try {
      const [machineData, orderData] = await Promise.all([
        request('/mantenimientos/planta/equipos'),
        request('/mantenimientos/planta/ordenes'),
      ]);
      setEquipos(machineData);
      setOrdenes(orderData);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
    const refresh = window.setInterval(load, 15000);
    return () => window.clearInterval(refresh);
  }, [load]);

  const createMachine = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await request('/mantenimientos/planta/equipos', { method: 'POST', body: JSON.stringify(machine) });
      setMachine(emptyMachine);
      await load();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  const createOrder = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const parts = form.repuestos.split('\n').map((line) => line.trim()).filter(Boolean).map((line) => {
        const [nombre_item, quantityText = '1'] = line.split('|').map((item) => item.trim());
        const cantidad = Number(quantityText);
        if (!Number.isFinite(cantidad) || cantidad <= 0) throw new Error(`Cantidad inválida para: ${nombre_item}`);
        return { nombre_item, cantidad, unidad_medida: 'UND' };
      });
      await request('/mantenimientos/planta/ordenes', {
        method: 'POST',
        body: JSON.stringify({
          id_equipo: form.id_equipo,
          tipo: form.tipo,
          descripcion_falla: form.descripcion_falla,
          repuestos_solicitados_almacen: parts,
          fecha_programada: form.fecha_programada || null,
        }),
      });
      setForm({ id_equipo: '', tipo: 'PREVENTIVO', descripcion_falla: '', repuestos: '', fecha_programada: '' });
      await load();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  const changeState = async (order, estado) => {
    setOrdenEnAccion(order.id_otm);
    setError('');
    try {
      await request(`/mantenimientos/planta/ordenes/${order.id_otm}/estado`, {
        method: 'PATCH', body: JSON.stringify({ estado }),
      });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setOrdenEnAccion('');
    }
  };

  const requestParts = async (order) => {
    setOrdenEnAccion(order.id_otm);
    setError('');
    try {
      await request(`/mantenimientos/planta/ordenes/${order.id_otm}/repuestos`, { method: 'POST' });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setOrdenEnAccion('');
    }
  };

  const totalEquipos = equipos.length;
  const equiposOperativos = equipos.filter((item) => item.estado_maquina === 'OPERATIVA').length;
  const equiposEnMantenimiento = equipos.filter((item) => item.estado_maquina === 'EN_MANTENIMIENTO').length;
  const equiposFueraDeServicio = equipos.filter((item) => item.estado_maquina === 'FUERA_DE_SERVICIO').length;
  const horasAcumuladas = equipos.reduce((total, item) => total + Number(item.horas_uso_acumuladas || 0), 0);

  return (
    <main className="space-y-4 p-4 text-xs text-slate-700">
      <header>
        <h1 className="text-xl font-bold text-slate-800">Mantenimiento de Planta</h1>
        <p className="mt-1 text-slate-500">Gestión de activos, horas de uso del sistema de ejecución de manufactura y solicitudes a Almacén.</p>
      </header>
      {error && <div role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700">{error}</div>}

      <section aria-label="Indicadores de mantenimiento" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {[
          { titulo: 'Total de equipos', valor: totalEquipos, color: 'border-slate-300 text-slate-900', icono: '⚙️' },
          { titulo: 'Operativos', valor: equiposOperativos, color: 'border-emerald-300 text-emerald-800', icono: '🟢' },
          { titulo: 'En mantenimiento', valor: equiposEnMantenimiento, color: 'border-amber-300 text-amber-800', icono: '🟡' },
          { titulo: 'Fuera de servicio', valor: equiposFueraDeServicio, color: 'border-red-300 text-red-800', icono: '🔴' },
          { titulo: 'Horas acumuladas', valor: `${horasAcumuladas.toFixed(2)} h`, color: 'border-blue-300 text-blue-800', icono: '⏱️' },
        ].map((indicador) => (
          <article key={indicador.titulo} className={`rounded-lg border-l-4 bg-white p-3 shadow-sm ${indicador.color}`}>
            <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{indicador.icono} {indicador.titulo}</p>
            <strong className="mt-1 block text-xl tabular-nums">{indicador.valor}</strong>
          </article>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <form className={card} onSubmit={createMachine}>
          <h2 className="mb-3 font-bold text-slate-800">Registrar equipo de planta</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            <input required className="rounded border p-2" placeholder="Código de máquina" value={machine.codigo_maquina} onChange={(e) => setMachine({ ...machine, codigo_maquina: e.target.value })} />
            <input required className="rounded border p-2" placeholder="Nombre / modelo" value={machine.nombre} onChange={(e) => setMachine({ ...machine, nombre: e.target.value })} />
            <select required className="rounded border p-2" value={machine.centro_trabajo_asociado} onChange={(e) => setMachine({ ...machine, centro_trabajo_asociado: e.target.value })}>
              <option value="">Seleccionar centro de trabajo</option>
              {centrosTrabajo.map((centro) => <option key={centro} value={centro}>{centro}</option>)}
            </select>
            <select className="rounded border p-2" value={machine.estado_maquina} onChange={(e) => setMachine({ ...machine, estado_maquina: e.target.value })}>
              {Object.entries(estadoMaquina).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <button disabled={busy} className="mt-3 rounded bg-emerald-700 px-3 py-2 font-semibold text-white disabled:opacity-50">Guardar equipo</button>
        </form>

        <form className={card} onSubmit={createOrder}>
          <h2 className="mb-3 font-bold text-slate-800">Crear orden y solicitar repuestos</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            <select required className="rounded border p-2" value={form.id_equipo} onChange={(e) => setForm({ ...form, id_equipo: e.target.value })}>
              <option value="">Seleccionar equipo</option>{equipos.map((item) => <option key={item.id_equipo} value={item.id_equipo}>{item.codigo_maquina} — {item.nombre}</option>)}
            </select>
            <select className="rounded border p-2" value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>{Object.entries(tipoOrden).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
            <input type="date" className="rounded border p-2" value={form.fecha_programada} onChange={(e) => setForm({ ...form, fecha_programada: e.target.value })} />
            <input required className="rounded border p-2" placeholder="Descripción de falla / tarea" value={form.descripcion_falla} onChange={(e) => setForm({ ...form, descripcion_falla: e.target.value })} />
          </div>
          <textarea className="mt-2 w-full rounded border p-2" rows={2} placeholder={'Repuestos, uno por línea: nombre | cantidad'} value={form.repuestos} onChange={(e) => setForm({ ...form, repuestos: e.target.value })} />
          <button disabled={busy || equipos.length === 0} className="mt-2 rounded bg-amber-600 px-3 py-2 font-semibold text-white disabled:opacity-50">Crear orden / enviar repuestos a Almacén</button>
        </form>
      </section>

      <section className={card}>
        <h2 className="mb-2 font-bold text-slate-800">Hoja de vida de equipos <span className="font-normal text-slate-500">· actualización cada 15 s</span></h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs"><thead className="bg-slate-100 text-slate-600"><tr><th className="px-2 py-1.5">Máquina</th><th className="px-2 py-1.5">Centro de trabajo</th><th className="px-2 py-1.5">Horas acumuladas</th><th className="px-2 py-1.5">Estado</th></tr></thead>
            <tbody>{equipos.map((item) => <tr key={item.id_equipo} className="border-b"><td className="px-2 py-1.5 font-semibold">{item.codigo_maquina}<span className="block font-normal text-slate-500">{item.nombre}</span></td><td className="px-2 py-1.5">{item.centro_trabajo_asociado || '—'}</td><td className="px-2 py-1.5 tabular-nums">{Number(item.horas_uso_acumuladas || 0).toFixed(2)} h {item.cronometro_activo && <span className="font-semibold text-emerald-700">● En uso</span>}</td><td className="px-2 py-1.5"><span className={`rounded-full px-2 py-1 ${estiloEstadoMaquina[item.estado_maquina] || 'bg-slate-100 text-slate-700'}`}>{estadoMaquina[item.estado_maquina] || item.estado_maquina}</span></td></tr>)}</tbody>
          </table>
        </div>
      </section>

      <section className={card}>
        <h2 className="mb-2 font-bold text-slate-800">Órdenes de mantenimiento</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs"><thead className="bg-slate-100 text-slate-600"><tr><th className="px-2 py-1.5">Orden / Equipo</th><th className="px-2 py-1.5">Tipo / Tarea</th><th className="px-2 py-1.5">Repuestos requeridos</th><th className="px-2 py-1.5">Fecha programada</th><th className="px-2 py-1.5">Estado</th><th className="px-2 py-1.5">Acciones</th></tr></thead>
            <tbody>{ordenes.map((item) => {
              const repuestos = item.repuestos_solicitados_almacen || [];
              const enAccion = ordenEnAccion === item.id_otm;
              return (
                <tr key={item.id_otm} className="border-b align-top">
                  <td className="px-2 py-1.5">{item.codigo_otm}<span className="block text-slate-500">{item.codigo_maquina} · {item.nombre_equipo}</span></td>
                  <td className="px-2 py-1.5">{tipoOrden[item.tipo] || item.tipo}<span className="block">{item.descripcion_falla}</span></td>
                  <td className="px-2 py-1.5">{repuestos.map((part) => `${part.nombre_item} (${part.cantidad})`).join(', ') || 'Sin repuestos'}</td>
                  <td className="px-2 py-1.5">{item.fecha_programada || '—'}</td>
                  <td className="px-2 py-1.5"><span className={`rounded-full px-2 py-1 ${item.estado === 'CERRADA' ? 'bg-emerald-50 text-emerald-800' : item.estado === 'EN_PROCESO' ? 'bg-amber-50 text-amber-800' : 'bg-slate-100 text-slate-700'}`}>{estadoOrden[item.estado] || item.estado}</span></td>
                  <td className="space-y-1.5 px-2 py-1.5">
                    {repuestos.length > 0 && (
                      <button
                        type="button"
                        disabled={enAccion}
                        onClick={() => requestParts(item)}
                        className="block whitespace-nowrap rounded bg-blue-700 px-2 py-1.5 font-semibold text-white disabled:opacity-50"
                      >
                        📦 Solicitar Repuestos a Almacén
                      </button>
                    )}
                    {item.estado === 'ABIERTA' && (
                      <button
                        type="button"
                        disabled={enAccion}
                        onClick={() => changeState(item, 'EN_PROCESO')}
                        className="block whitespace-nowrap rounded bg-amber-600 px-2 py-1.5 font-semibold text-white disabled:opacity-50"
                      >
                        ▶️ Iniciar Mantenimiento
                      </button>
                    )}
                    {item.estado === 'EN_PROCESO' && (
                      <button
                        type="button"
                        disabled={enAccion}
                        onClick={() => changeState(item, 'CERRADA')}
                        className="block whitespace-nowrap rounded bg-emerald-700 px-2 py-1.5 font-semibold text-white disabled:opacity-50"
                      >
                        ✅ Finalizar y Liberar Equipo
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
