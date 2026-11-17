// src/components/OperariosPorMaquina.jsx
// Operarios asignados a cada máquina (Configuración, solo ADMIN). La carga manual de tiempos de la
// orden de fabricación ofrece, para cada máquina, solo los operarios asignados aquí.
import React, { useCallback, useEffect, useState } from 'react';
import API, { mensajeError } from '../services/api';

const RUTA = '/configuracion/maquinas';

export default function OperariosPorMaquina() {
  const [maquinas, setMaquinas] = useState([]);
  const [disponibles, setDisponibles] = useState([]);
  const [borrador, setBorrador] = useState({});
  const [guardando, setGuardando] = useState('');
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');

  const cargar = useCallback(async () => {
    try {
      const { data } = await API.get(RUTA);
      setMaquinas(data.maquinas || []);
      setDisponibles(data.operarios_disponibles || []);
      setBorrador(Object.fromEntries((data.maquinas || []).map((maquina) => [
        maquina.codigo_maquina, new Set(maquina.operarios.map((operario) => operario.usuario))
      ])));
    } catch (fallo) {
      setError(mensajeError(fallo, 'No se pudieron cargar las máquinas.'));
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const alternar = (codigo, email) => setBorrador((actual) => {
    const seleccion = new Set(actual[codigo] || []);
    if (seleccion.has(email)) seleccion.delete(email);
    else seleccion.add(email);
    return { ...actual, [codigo]: seleccion };
  });

  const guardar = async (codigo) => {
    setError('');
    setAviso('');
    setGuardando(codigo);
    try {
      await API.put(`${RUTA}/${encodeURIComponent(codigo)}/operarios`, { usuarios: [...(borrador[codigo] || [])] });
      setAviso(`Operarios de ${codigo} guardados.`);
      await cargar();
    } catch (fallo) {
      setError(mensajeError(fallo, `No se pudieron guardar los operarios de ${codigo}.`));
    } finally {
      setGuardando('');
    }
  };

  return (
    <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div>
        <h2 className="text-sm font-extrabold text-slate-900">Operarios por máquina</h2>
        <p className="text-slate-500">La carga manual de tiempos ofrece, para cada máquina, solo los operarios asignados aquí.</p>
      </div>
      {error && <div role="alert" className="rounded border border-red-200 bg-red-50 p-2 font-semibold text-red-800">{error}</div>}
      {aviso && <div role="status" className="rounded border border-emerald-200 bg-emerald-50 p-2 font-semibold text-emerald-800">{aviso}</div>}
      {!maquinas.length && !error && <p className="text-slate-500">No hay máquinas en el catálogo.</p>}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {maquinas.map((maquina) => (
          <fieldset key={maquina.codigo_maquina} className="rounded border border-slate-200 p-3">
            <legend className="px-1 font-bold text-slate-800">{maquina.codigo_maquina} · {maquina.nombre}</legend>
            <div className="max-h-40 space-y-1 overflow-y-auto">
              {disponibles.map((operario) => (
                <label key={operario.usuario} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={borrador[maquina.codigo_maquina]?.has(operario.usuario) || false}
                    onChange={() => alternar(maquina.codigo_maquina, operario.usuario)}
                  />
                  <span>{operario.nombre} <span className="text-slate-500">({operario.usuario})</span></span>
                </label>
              ))}
              {!disponibles.length && <p className="text-slate-500">No hay usuarios activos con rol OPERARIO.</p>}
            </div>
            <button
              type="button"
              onClick={() => guardar(maquina.codigo_maquina)}
              disabled={Boolean(guardando)}
              className="mt-2 rounded bg-emerald-700 px-3 py-1 font-bold text-white hover:bg-emerald-800 disabled:opacity-50"
            >
              {guardando === maquina.codigo_maquina ? 'Guardando…' : 'Guardar'}
            </button>
          </fieldset>
        ))}
      </div>
    </section>
  );
}
