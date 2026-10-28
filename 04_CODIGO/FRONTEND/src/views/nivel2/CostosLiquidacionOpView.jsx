import React, { useEffect, useState } from 'react';
import VistaGrafoCostos from './VistaGrafoCostos';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';
const money = (value) => value == null ? '—' : new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(value);

async function request(path) {
  const response = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${localStorage.getItem('sgi_token') || ''}` },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'No se pudo consultar la liquidación.');
  return body;
}

function Kpi({ label, value, tone = 'slate' }) {
  const tones = {
    slate: 'border-slate-200 bg-white text-slate-800',
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    amber: 'border-amber-200 bg-amber-50 text-amber-800',
    purple: 'border-purple-200 bg-purple-50 text-purple-800',
  };
  return <div className={`rounded-lg border p-4 shadow-sm ${tones[tone]}`}><div className="text-[11px] font-semibold uppercase tracking-wide opacity-70">{label}</div><div className="mt-1 text-xl font-bold">{value}</div></div>;
}

export default function CostosLiquidacionOpView() {
  const [codigo, setCodigo] = useState('');
  const [liquidacion, setLiquidacion] = useState(null);
  const [oee, setOee] = useState(null);
  const [vista, setVista] = useState('matriz');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    request('/costos/oee').then(setOee).catch((err) => setError(err.message));
  }, []);

  const liquidar = async (event) => {
    event.preventDefault();
    if (!codigo.trim()) return;
    setLoading(true);
    try {
      setLiquidacion(await request(`/costos/liquidar/${encodeURIComponent(codigo.trim())}`));
      setError('');
    } catch (err) { setError(err.message); setLiquidacion(null); } finally { setLoading(false); }
  };

  return (
    <main className="space-y-4 p-4 text-xs text-slate-700">
      <header><h1 className="text-xl font-bold text-slate-800">Costos y Liquidación por OP</h1><p className="mt-1 text-slate-500">Costo real trazable de materiales, tiempos registrados y servicios externos; indicador de eficiencia de planta.</p></header>
      {error && <div role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700">{error}</div>}

      {oee && <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Eficiencia global de los equipos · últimos 7 días" value={`${(oee.oee * 100).toFixed(1)}%`} tone="purple" />
        <Kpi label="Disponibilidad operativa" value={`${(oee.disponibilidad * 100).toFixed(1)}%`} tone="emerald" />
        <Kpi label="Rendimiento estimado" value={`${(oee.rendimiento * 100).toFixed(1)}%`} tone="amber" />
        <Kpi label="Calidad de producción" value={`${(oee.calidad * 100).toFixed(1)}%`} />
      </section>}
      {oee && <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">{oee.criterio} La disponibilidad usa el tiempo registrado de preparación y producción; aún no se registran formalmente las paradas no planificadas.</p>}

      <form onSubmit={liquidar} className="flex flex-wrap items-end gap-2 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <label className="min-w-64 flex-1 font-semibold text-slate-700">Código de Orden de Producción<input className="mt-1 block w-full rounded border p-2 font-normal" value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="Ej. 4001234" /></label>
        <button disabled={loading} className="rounded bg-slate-800 px-4 py-2 font-semibold text-white disabled:opacity-50">{loading ? 'Calculando…' : 'Calcular liquidación'}</button>
      </form>

      {liquidacion && <>
        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi label="Cotización comercial" value={money(liquidacion.cotizacion_comercial)} />
          <Kpi label="Costo real total" value={money(liquidacion.costos.real_total)} tone="amber" />
          <Kpi label="Margen real" value={money(liquidacion.margen_real_valor)} tone={liquidacion.margen_real_valor >= 0 ? 'emerald' : 'amber'} />
          <Kpi label="Margen sobre cotización" value={liquidacion.margen_real_porcentaje == null ? '—' : `${liquidacion.margen_real_porcentaje.toFixed(1)}%`} tone="purple" />
        </section>

        <div className="flex flex-wrap gap-2" role="group" aria-label="Tipo de visualización de costos">
          <button type="button" aria-pressed={vista === 'matriz'} onClick={() => setVista('matriz')} className={`rounded border px-3 py-2 font-semibold ${vista === 'matriz' ? 'border-slate-800 bg-slate-800 text-white' : 'border-slate-300 bg-white text-slate-700'}`}>Vista matriz tabular</button>
          <button type="button" aria-pressed={vista === 'red'} onClick={() => setVista('red')} className={`rounded border px-3 py-2 font-semibold ${vista === 'red' ? 'border-slate-800 bg-slate-800 text-white' : 'border-slate-300 bg-white text-slate-700'}`}>Red de costos</button>
        </div>

        {vista === 'red' ? <VistaGrafoCostos datos={liquidacion} /> : (
          <div className="grid gap-4 xl:grid-cols-3">
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"><h2 className="mb-2 font-bold">Materiales consumidos</h2><table className="w-full text-left"><thead className="bg-slate-100"><tr><th className="px-2 py-1.5">Material / lote</th><th className="px-2 py-1.5">Cantidad</th><th className="px-2 py-1.5">Costo</th></tr></thead><tbody>{liquidacion.detalle_materiales.map((row, index) => <tr key={`${row.codigo_material}-${index}`} className="border-b"><td className="px-2 py-1.5">{row.codigo_material}<span className="block text-slate-500">{row.descripcion}</span>{row.lote_codigo && <span className="block text-emerald-700">Lote {row.lote_codigo}{row.numero_colada ? ` · Colada ${row.numero_colada}` : ''}</span>}</td><td className="px-2 py-1.5">{row.cantidad} {row.unidad_medida}</td><td className="px-2 py-1.5">{money(row.costo_total)}</td></tr>)}</tbody></table></section>
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"><h2 className="mb-2 font-bold">Horas reales y costo de mano de obra</h2><table className="w-full text-left"><thead className="bg-slate-100"><tr><th className="px-2 py-1.5">Centro de trabajo / actividad</th><th className="px-2 py-1.5">Horas</th><th className="px-2 py-1.5">Costo</th></tr></thead><tbody>{liquidacion.detalle_tiempos.map((row, index) => <tr key={`${row.centro_trabajo}-${row.tipo}-${index}`} className="border-b"><td className="px-2 py-1.5">{row.centro_trabajo}<span className="block text-slate-500">{({ SETUP: 'Preparación de máquina', MECANIZADO: 'Mecanizado', PRODUCCION: 'Producción' })[row.tipo] || row.tipo}</span></td><td className="px-2 py-1.5">{row.horas.toFixed(2)}</td><td className="px-2 py-1.5">{money(row.costo_total)}</td></tr>)}</tbody></table></section>
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"><h2 className="mb-2 font-bold">Servicios de terceros</h2><table className="w-full text-left"><thead className="bg-slate-100"><tr><th className="px-2 py-1.5">Proveedor / Servicio</th><th className="px-2 py-1.5">Factura</th><th className="px-2 py-1.5">Costo</th></tr></thead><tbody>{liquidacion.detalle_servicios_terceros.map((row, index) => <tr key={`${row.numero_factura}-${index}`} className="border-b"><td className="px-2 py-1.5">{row.proveedor}<span className="block text-slate-500">{row.descripcion}</span></td><td className="px-2 py-1.5">{row.numero_factura}</td><td className="px-2 py-1.5">{money(row.costo)}</td></tr>)}</tbody></table></section>
          </div>
        )}
        {liquidacion.alertas?.length > 0 && <section className="rounded border border-amber-200 bg-amber-50 p-3 text-amber-900"><h2 className="font-bold">Observaciones de costeo</h2><ul className="mt-1 list-inside list-disc">{liquidacion.alertas.map((item) => <li key={item}>{item}</li>)}</ul></section>}
      </>}
    </main>
  );
}
