// src/components/DimensionesGeometriaFields.jsx
import React from 'react';

/**
 * Componente dinámico para capturar dimensiones según la geometría del material
 * Soporta: Lámina / Placa, Barra Maciza Redonda, Tubo / Anillo Mecánico y Perfiles
 */
export default function DimensionesGeometriaFields({ formaGeometria, form, onChange }) {
  const geo = (formaGeometria || '').toLowerCase();

  // 1. LÁMINA / PLACA / CHAPA
  if (geo.includes('lámina') || geo.includes('lamina') || geo.includes('placa') || geo.includes('chapa')) {
    return (
      <>
        <div>
          <label className="block font-bold text-slate-700 mb-1">Largo Útil (mm) *</label>
          <input
            type="number"
            name="largo_mm"
            placeholder="Ej. 1200"
            value={form.largo_mm || ''}
            onChange={onChange}
            className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
            required
          />
        </div>

        <div>
          <label className="block font-bold text-slate-700 mb-1">Ancho (mm) *</label>
          <input
            type="number"
            name="ancho_mm"
            placeholder="Ej. 400"
            value={form.ancho_mm || ''}
            onChange={onChange}
            className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
            required
          />
        </div>
      </>
    );
  }

  // 2. BARRA MACIZA REDONDA
  if (geo.includes('barra') || geo.includes('maciza')) {
    return (
      <>
        <div>
          <label className="block font-bold text-slate-700 mb-1">Diámetro (mm) *</label>
          <input
            type="number"
            name="diametro_mm"
            placeholder="Ej. 50"
            value={form.diametro_mm || ''}
            onChange={onChange}
            className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
            required
          />
        </div>

        <div>
          <label className="block font-bold text-slate-700 mb-1">Longitud (mm) *</label>
          <input
            type="number"
            name="longitud_mm"
            placeholder="Ej. 800"
            value={form.longitud_mm || form.largo_mm || ''}
            onChange={onChange}
            className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
            required
          />
        </div>
      </>
    );
  }

  // 3. ANILLO / TUBO MECÁNICO / HUECO
  if (geo.includes('tubo') || geo.includes('anillo') || geo.includes('hueco')) {
    return (
      <>
        <div>
          <label className="block font-bold text-slate-700 mb-1">Diámetro Exterior (mm) *</label>
          <input
            type="number"
            name="diametro_exterior_mm"
            placeholder="Ej. 100"
            value={form.diametro_exterior_mm || ''}
            onChange={onChange}
            className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
            required
          />
        </div>

        <div>
          <label className="block font-bold text-slate-700 mb-1">Diámetro Interior (mm) *</label>
          <input
            type="number"
            name="diametro_interior_mm"
            placeholder="Ej. 80"
            value={form.diametro_interior_mm || ''}
            onChange={onChange}
            className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
            required
          />
        </div>

        <div>
          <label className="block font-bold text-slate-700 mb-1">Longitud (mm) *</label>
          <input
            type="number"
            name="longitud_mm"
            placeholder="Ej. 300"
            value={form.longitud_mm || form.largo_mm || ''}
            onChange={onChange}
            className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
            required
          />
        </div>
      </>
    );
  }

  // OPCIÓN DEFAULT / GENÉRICA (POR SI NO COINCIDE)
  return (
    <>
      <div>
        <label className="block font-bold text-slate-700 mb-1">Largo / Longitud (mm)</label>
        <input
          type="number"
          name="largo_mm"
          placeholder="Ej. 1000"
          value={form.largo_mm || ''}
          onChange={onChange}
          className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
        />
      </div>

      <div>
        <label className="block font-bold text-slate-700 mb-1">Ancho / Diámetro (mm)</label>
        <input
          type="number"
          name="ancho_mm"
          placeholder="Ej. 200"
          value={form.ancho_mm || ''}
          onChange={onChange}
          className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold text-slate-800"
        />
      </div>
    </>
  );
}