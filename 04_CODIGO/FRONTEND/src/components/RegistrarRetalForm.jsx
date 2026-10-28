// src/components/RegistrarRetalForm.jsx
import React, { useState } from 'react';

export default function RegistrarRetalForm({ onRegistroExitoso, onCancelar }) {
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });
  const [fotoPreview, setFotoPreview] = useState(null);

  const [form, setForm] = useState({
    material_clasificacion: 'Acero Inoxidable 304',
    forma_geometria: 'Lámina / Placa',
    espesor_seccion: '3 mm',
    // Campos dimensionales dinámicos
    largo_mm: '',
    ancho_mm: '',
    diametro_mm: '',
    diametro_exterior_mm: '',
    diametro_interior_mm: '',
    longitud_mm: '',
    peso_kg: '',
    unidad_medida: 'kg',
    procedencia: 'Corte Guillotina / Láser (Producción)',
    codigo_op_origen: '',
    numero_colada_lote: '',
    ubicacion_almacen: 'RACK-RETAZOS-A1',
    observaciones: '',
    fotografia_url: ''
  });

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setFotoPreview(reader.result);
        setForm(prev => ({ ...prev, fotografia_url: reader.result }));
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.codigo_op_origen) {
      return setMensaje({ tipo: 'error', texto: '⚠️ Debe especificar la Orden de Producción (OP / OT) de origen.' });
    }

    try {
      setLoading(true);
      // Mapeo o envío de datos según la geometría seleccionada
      const payload = {
        ...form,
        largo_mm: Number(form.largo_mm) || Number(form.longitud_mm) || 0,
        ancho_mm: Number(form.ancho_mm) || Number(form.diametro_mm) || Number(form.diametro_exterior_mm) || 0,
        peso_kg: Number(form.peso_kg) || 0,
      };

      // Llamada a la API (Ejemplo)
      // await API.post('/almacen/retales/nuevo', payload);

      setMensaje({
        tipo: 'exito',
        texto: `✅ Retal registrado con éxito. Estado: PENDIENTE DE EVALUACIÓN METROLÓGICA.`
      });

      if (onRegistroExitoso) onRegistroExitoso(payload);
    } catch (err) {
      setMensaje({ tipo: 'error', texto: `❌ Error al guardar el retal.` });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-5xl mx-auto space-y-5 font-sans text-xs">
      <div className="flex justify-between items-center border-b pb-3">
        <div>
          <h2 className="text-base font-extrabold text-slate-800 flex items-center gap-2">
            <span>✂️</span> Registrar Retal / Sobrante de Materia Prima
          </h2>
        </div>
      </div>

      {mensaje.texto && (
        <div className={`p-3 rounded-lg font-bold border ${mensaje.tipo === 'exito' ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : 'bg-red-50 text-red-800 border-red-300'}`}>
          {mensaje.texto}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* COLUMNA 1 & 2: INFORMACIÓN GENERAL Y MATERIAL */}
          <div className="md:col-span-2 space-y-4">
            <h3 className="font-extrabold text-slate-800 text-xs border-b pb-1.5 uppercase tracking-wider">
              📋 Especificación Técnica
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Material / Aleación *</label>
                <select
                  name="material_clasificacion"
                  value={form.material_clasificacion}
                  onChange={handleChange}
                  className="w-full p-2 border border-slate-300 rounded font-semibold bg-slate-50"
                  required
                >
                  <option value="Acero Inoxidable 304">Acero Inoxidable 304</option>
                  <option value="Acero Inoxidable 316L">Acero Inoxidable 316L</option>
                  <option value="AISI 1045">AISI 1045 (Acero al Carbono)</option>
                  <option value="AISI 4140 Bonificado">AISI 4140 Bonificado</option>
                  <option value="Bronce SAE 65">Bronce SAE 65</option>
                  <option value="Aluminio 6061-T6">Aluminio 6061-T6</option>
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Geometría / Forma *</label>
                <select
                  name="forma_geometria"
                  value={form.forma_geometria}
                  onChange={handleChange}
                  className="w-full p-2 border border-slate-300 rounded font-semibold bg-slate-50"
                  required
                >
                  <option value="Lámina / Placa">Lámina / Placa</option>
                  <option value="Barra Maciza Redonda">Barra Maciza Redonda</option>
                  <option value="Anillo / Tubo Mecánico">Anillo / Tubo Mecánico</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-bold text-slate-700 mb-1">Espesor / Sección *</label>
                <input
                  type="text"
                  name="espesor_seccion"
                  placeholder="Ej. 3 mm"
                  value={form.espesor_seccion}
                  onChange={handleChange}
                  className="w-full p-2 border border-slate-300 rounded font-bold text-slate-800"
                  required
                />
              </div>

              <div>
                <label className="block font-bold text-blue-900 mb-1">OT / OP de Origen *</label>
                <input
                  type="text"
                  name="codigo_op_origen"
                  placeholder="Ej. OP-4001234"
                  value={form.codigo_op_origen}
                  onChange={handleChange}
                  className="w-full p-2 border border-blue-300 rounded font-mono font-bold text-blue-900 bg-blue-50/40 uppercase"
                  required
                />
              </div>
            </div>
          </div>

          {/* COLUMNA 3: DIMENSIONES DINÁMICAS SEGÚN GEOMETRÍA */}
          <div className="space-y-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
            <h3 className="font-extrabold text-slate-800 text-xs border-b pb-1.5 uppercase tracking-wider">
              📏 Dimensiones y Masa
            </h3>

            {/* OPCIÓN 1: LÁMINA / PLACA */}
            {form.forma_geometria === 'Lámina / Placa' && (
              <>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Largo Útil (mm) *</label>
                  <input
                    type="number"
                    name="largo_mm"
                    placeholder="Ej. 1200"
                    value={form.largo_mm}
                    onChange={handleChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold"
                    required
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Ancho (mm) *</label>
                  <input
                    type="number"
                    name="ancho_mm"
                    placeholder="Ej. 400"
                    value={form.ancho_mm}
                    onChange={handleChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold"
                    required
                  />
                </div>
              </>
            )}

            {/* OPCIÓN 2: BARRA MACIZA REDONDA */}
            {form.forma_geometria === 'Barra Maciza Redonda' && (
              <>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Diámetro (mm) *</label>
                  <input
                    type="number"
                    name="diametro_mm"
                    placeholder="Ej. 50"
                    value={form.diametro_mm}
                    onChange={handleChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold"
                    required
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Longitud (mm) *</label>
                  <input
                    type="number"
                    name="longitud_mm"
                    placeholder="Ej. 800"
                    value={form.longitud_mm}
                    onChange={handleChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold"
                    required
                  />
                </div>
              </>
            )}

            {/* OPCIÓN 3: ANILLO / TUBO MECÁNICO */}
            {form.forma_geometria === 'Anillo / Tubo Mecánico' && (
              <>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Diámetro Exterior (mm) *</label>
                  <input
                    type="number"
                    name="diametro_exterior_mm"
                    placeholder="Ej. 100"
                    value={form.diametro_exterior_mm}
                    onChange={handleChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold"
                    required
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Diámetro Interior (mm) *</label>
                  <input
                    type="number"
                    name="diametro_interior_mm"
                    placeholder="Ej. 80"
                    value={form.diametro_interior_mm}
                    onChange={handleChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold"
                    required
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Longitud (mm) *</label>
                  <input
                    type="number"
                    name="longitud_mm"
                    placeholder="Ej. 300"
                    value={form.longitud_mm}
                    onChange={handleChange}
                    className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold"
                    required
                  />
                </div>
              </>
            )}

            {/* CAMPO COMÚN: PESO */}
            <div>
              <label className="block font-bold text-slate-700 mb-1">Peso (kg)</label>
              <input
                type="number"
                step="0.01"
                name="peso_kg"
                placeholder="Ej. 11.5"
                value={form.peso_kg}
                onChange={handleChange}
                className="w-full p-2 border border-slate-300 rounded bg-white font-mono font-bold"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t pt-3">
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded shadow-sm"
          >
            {loading ? 'Registrando...' : 'Registrar Retal'}
          </button>
        </div>
      </form>
    </div>
  );
}