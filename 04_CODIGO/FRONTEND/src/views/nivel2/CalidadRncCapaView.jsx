import React, { useCallback, useEffect, useState } from 'react';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
const blank = { codigo_op: '', descripcion: '', proceso_origen: 'INSPECCION_FINAL', causa_raiz: 'MATERIAL_DEFECTUOSO', piezas_scrap: 0, disposicion: 'REPROCESAR' };
const PROCESOS = {
  RECEPCION_COMPRAS: 'Recepción de compras',
  MECANIZADO_MES: 'Mecanizado en planta',
  INSPECCION_FINAL: 'Inspección final'
};
const CAUSAS = {
  MATERIAL_DEFECTUOSO: 'Material no conforme',
  FALLA_HERRAMIENTA: 'Falla de herramienta',
  ERROR_PLANO: 'Error en plano o especificación',
  OPERACIONAL: 'Desviación del proceso'
};
const DISPOSICIONES = {
  REPROCESAR: 'Reprocesar',
  CHATARRA_SCRAP: 'Retirar como material de descarte',
  ACEPTAR_BAJO_CONCESION: 'Aceptar bajo concesión',
  CUARENTENA: 'Mantener en cuarentena'
};
const ESTADOS_ACCION = { ABIERTA: 'Abierta', CERRADA: 'Cerrada' };
const ESTADOS_OP = {
  BORRADOR: 'Borrador',
  EN_REVISION_CALIDAD: 'En revisión de calidad',
  APROBADA: 'Aprobada',
  PENDIENTE_MATERIAL: 'Pendiente de materiales',
  LIBERADA_PRODUCCION: 'Liberada a producción',
  EN_PRODUCCION: 'En producción',
  EN_PROCESO_CNC: 'En mecanizado',
  EN_SETUP: 'En preparación de máquina',
  MECANIZADO: 'En mecanizado',
  EN_INSPECCION: 'En inspección de calidad',
  LISTA_PARA_LIBERAR: 'Lista para liberación',
  LIBERADA: 'Liberada',
  CERRADA: 'Cerrada',
  CANCELADA: 'Cancelada'
};

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('sgi_token') || ''}`, ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'No se pudo completar la solicitud de calidad.');
  return body;
}

export default function CalidadRncCapaView() {
  const [records, setRecords] = useState([]);
  const [filters, setFilters] = useState({ cliente: '', codigo_op: '', causa_raiz: '' });
  const [form, setForm] = useState(blank);
  const [capa, setCapa] = useState({ id_rnc: '', accion_correctiva: '', responsable_id: '', fecha_compromiso: '' });
  const [closing, setClosing] = useState({ id_capa: '', evidencia_cierre: '' });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value.trim()));
      setRecords(await request(`/calidad/rnc?${params}`));
      setError('');
    } catch (err) { setError(err.message); }
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const createRnc = async (event) => {
    event.preventDefault();
    try {
      const codigo_nc = `RNC-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-${Date.now().toString().slice(-6)}`;
      await request('/calidad/no-conformidades', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          codigo_nc,
          piezas_scrap: Number(form.piezas_scrap),
          gravedad: 'MAYOR',
        }),
      });
      setForm(blank);
      setSuccess(`Reporte ${codigo_nc} registrado.`);
      await load();
    } catch (err) { setError(err.message); }
  };

  const createCapa = async (event) => {
    event.preventDefault();
    try {
      await request(`/calidad/rnc/${capa.id_rnc}/acciones-capa`, {
        method: 'POST',
        body: JSON.stringify({
          accion_correctiva: capa.accion_correctiva,
          responsable_id: capa.responsable_id || null,
          fecha_compromiso: capa.fecha_compromiso,
        }),
      });
      setCapa({ id_rnc: '', accion_correctiva: '', responsable_id: '', fecha_compromiso: '' });
      setSuccess('Acción correctiva registrada.');
      await load();
    } catch (err) { setError(err.message); }
  };

  const closeCapa = async (event) => {
    event.preventDefault();
    try {
      await request(`/calidad/acciones-capa/${closing.id_capa}/cerrar`, {
        method: 'PATCH',
        body: JSON.stringify({ evidencia_cierre: closing.evidencia_cierre }),
      });
      setClosing({ id_capa: '', evidencia_cierre: '' });
      setSuccess('Cierre registrado con evidencia.');
      await load();
    } catch (err) { setError(err.message); }
  };

  return (
    <main className="space-y-4 p-4 text-xs text-slate-700">
      <header><h1 className="text-xl font-bold text-slate-800">No Conformidades y Acciones Correctivas</h1><p className="mt-1 text-slate-500">Trazabilidad por cliente, orden de producción, causa raíz y evidencia de cierre.</p></header>
      {error && <div role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700">{error}</div>}
      {success && <div role="status" className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-700">{success}</div>}

      <form onSubmit={createRnc} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-bold text-slate-800">Registrar no conformidad</h2>
        <div className="grid gap-2 md:grid-cols-3">
          <input required className="rounded border p-2" placeholder="Código OP" value={form.codigo_op} onChange={(e) => setForm({ ...form, codigo_op: e.target.value })} />
          <select aria-label="Proceso de origen" className="rounded border p-2" value={form.proceso_origen} onChange={(e) => setForm({ ...form, proceso_origen: e.target.value })}>{Object.entries(PROCESOS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <select aria-label="Causa raíz" className="rounded border p-2" value={form.causa_raiz} onChange={(e) => setForm({ ...form, causa_raiz: e.target.value })}>{Object.entries(CAUSAS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <input required min="0" type="number" className="rounded border p-2" placeholder="Piezas rechazadas" value={form.piezas_scrap} onChange={(e) => setForm({ ...form, piezas_scrap: e.target.value })} />
          <select aria-label="Disposición de las piezas" className="rounded border p-2" value={form.disposicion} onChange={(e) => setForm({ ...form, disposicion: e.target.value })}>{Object.entries(DISPOSICIONES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <input required className="rounded border p-2 md:col-span-1" placeholder="Descripción y evidencia observada" value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />
        </div>
        <button className="mt-3 rounded bg-purple-700 px-3 py-2 font-semibold text-white">Registrar reporte de no conformidad</button>
      </form>

      <form onSubmit={createCapa} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-bold text-slate-800">Definir acción correctiva o preventiva</h2>
        <div className="grid gap-2 md:grid-cols-5">
          <select required className="rounded border p-2" value={capa.id_rnc} onChange={(e) => setCapa({ ...capa, id_rnc: e.target.value })}><option value="">Seleccionar reporte</option>{records.map((item) => <option key={item.id_nc} value={item.id_nc}>{item.codigo_nc} · {item.codigo_op || 'Sin orden'}</option>)}</select>
          <input className="rounded border p-2" placeholder="Identificador de responsable (opcional)" value={capa.responsable_id} onChange={(e) => setCapa({ ...capa, responsable_id: e.target.value })} />
          <input required className="rounded border p-2 md:col-span-2" placeholder="Acción y evidencia esperada" value={capa.accion_correctiva} onChange={(e) => setCapa({ ...capa, accion_correctiva: e.target.value })} />
          <input required type="date" className="rounded border p-2" value={capa.fecha_compromiso} onChange={(e) => setCapa({ ...capa, fecha_compromiso: e.target.value })} />
        </div>
        <button className="mt-3 rounded bg-slate-700 px-3 py-2 font-semibold text-white">Guardar acción preventiva o correctiva</button>
      </form>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-bold text-slate-800">Matriz de seguimiento</h2>
        <div className="mb-3 grid gap-2 md:grid-cols-4">
          <input className="rounded border p-2" placeholder="Filtrar cliente" value={filters.cliente} onChange={(e) => setFilters({ ...filters, cliente: e.target.value })} />
          <input className="rounded border p-2" placeholder="Filtrar OP" value={filters.codigo_op} onChange={(e) => setFilters({ ...filters, codigo_op: e.target.value })} />
          <select className="rounded border p-2" value={filters.causa_raiz} onChange={(e) => setFilters({ ...filters, causa_raiz: e.target.value })}><option value="">Todas las causas</option>{Object.entries(CAUSAS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <button type="button" onClick={load} className="rounded border px-3 py-2 font-semibold hover:bg-slate-50">Aplicar filtros</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left"><thead className="bg-slate-100 text-slate-600"><tr><th className="px-2 py-1.5">Reporte / orden</th><th className="px-2 py-1.5">Cliente / proceso</th><th className="px-2 py-1.5">Causa / disposición</th><th className="px-2 py-1.5">Descripción / piezas rechazadas</th><th className="px-2 py-1.5">Acciones / estado</th></tr></thead>
            <tbody>{records.map((item) => <tr key={item.id_nc} className="border-b align-top"><td className="px-2 py-1.5 font-semibold">{item.codigo_nc}<span className="block font-normal text-slate-500">{item.codigo_op || 'Sin orden'}</span></td><td className="px-2 py-1.5">{item.cliente || '—'}<span className="block text-slate-500">{PROCESOS[item.proceso_origen || item.origen] || item.proceso_origen || item.origen}</span></td><td className="px-2 py-1.5">{CAUSAS[item.causa_raiz] || item.causa_raiz || '—'}<span className="block text-slate-500">{DISPOSICIONES[item.disposicion] || item.disposicion || '—'}</span></td><td className="px-2 py-1.5">{item.descripcion}<span className="block text-red-700">Piezas rechazadas: {item.piezas_scrap || 0}</span></td><td className="min-w-72 px-2 py-1.5">{(item.acciones_capa || []).map((action) => <div key={action.id_capa} className="mb-2 rounded bg-slate-50 p-2"><strong>{ESTADOS_ACCION[action.estado_cierre] || action.estado_cierre}</strong> · vence {action.fecha_compromiso}<div>{action.accion_correctiva}</div>{action.estado_cierre !== 'CERRADA' && <button type="button" onClick={() => setClosing({ id_capa: action.id_capa, evidencia_cierre: '' })} className="mt-1 rounded bg-emerald-700 px-2 py-1 text-white">Registrar cierre</button>}</div>)}{!item.acciones_capa?.length && 'Sin acciones registradas'}</td></tr>)}</tbody>
          </table>
        </div>
      </section>

      {closing.id_capa && <form onSubmit={closeCapa} className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
        <h2 className="mb-2 font-bold text-emerald-900">Cerrar acción con evidencia</h2>
        <div className="flex flex-wrap gap-2"><input required minLength="3" className="min-w-80 flex-1 rounded border p-2" placeholder="Resultado, registro o enlace de evidencia" value={closing.evidencia_cierre} onChange={(e) => setClosing({ ...closing, evidencia_cierre: e.target.value })} /><button className="rounded bg-emerald-700 px-3 py-2 font-semibold text-white">Confirmar cierre</button><button type="button" onClick={() => setClosing({ id_capa: '', evidencia_cierre: '' })} className="rounded border px-3 py-2">Cancelar</button></div>
      </form>}
    </main>
  );
}
