// src/components/CargaTiemposOp.jsx
// Carga manual de tiempos de la OP (GET/POST /tiempos-manuales, reglas/carga-tiempos-manual.md).
// El backend decide quién registra (PERM_TIEMPOS_REGISTRAR, sin OPERARIO) y quién ve costos
// (COSTOS y JEFE_PRODUCCION): la parrilla solo muestra la columna de costo si la respuesta la trae.
// Las filas no se borran; una corrección pide motivo. No se validan solapamientos.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import API, { mensajeError } from '../services/api';

const RUTA = '/tiempos-manuales';

function hoy() {
  const fecha = new Date();
  const dos = (valor) => String(valor).padStart(2, '0');
  return `${fecha.getFullYear()}-${dos(fecha.getMonth() + 1)}-${dos(fecha.getDate())}`;
}

const FILA_NUEVA = () => ({
  id_operacion: '', codigo_maquina: '', operario: '', minutos_operacion: '', minutos_setup: '', fecha: hoy()
});

function cuerpo(fila) {
  return {
    id_operacion: fila.id_operacion,
    codigo_maquina: fila.codigo_maquina,
    operario: fila.operario,
    minutos_operacion: Number(fila.minutos_operacion),
    minutos_setup: fila.minutos_setup === '' || fila.minutos_setup === null ? null : Number(fila.minutos_setup),
    fecha: fila.fecha || null
  };
}

function moneda(valor) {
  return valor === null || valor === undefined ? '' : Number(valor).toLocaleString('es-CO', { style: 'currency', currency: 'COP' });
}

function fechaHora(valor) {
  if (!valor) return '';
  const fecha = new Date(valor);
  return Number.isNaN(fecha.getTime()) ? valor : fecha.toLocaleString('es-CO');
}

const CELDA = 'border-b border-r border-slate-200 px-1.5 py-1';
const CONTROL = 'w-full rounded-sm border border-slate-300 bg-white px-1 py-0.5';

function CamposFila({ fila, cambiar, procesos, maquinas }) {
  const operarios = maquinas.find((maquina) => maquina.codigo_maquina === fila.codigo_maquina)?.operarios || [];
  return (
    <>
      <td className={CELDA}>
        <select aria-label="Proceso" value={fila.id_operacion} onChange={(e) => cambiar({ id_operacion: e.target.value })} className={CONTROL}>
          <option value="">Seleccione…</option>
          {procesos.map((proceso) => (
            <option key={proceso.id_operacion} value={proceso.id_operacion}>{proceso.secuencia} · {proceso.nombre_proceso}</option>
          ))}
        </select>
      </td>
      <td className={CELDA}>
        <select
          aria-label="Estación"
          value={fila.codigo_maquina}
          onChange={(e) => cambiar({ codigo_maquina: e.target.value, operario: '' })}
          className={CONTROL}
        >
          <option value="">Seleccione…</option>
          {maquinas.map((maquina) => (
            <option key={maquina.codigo_maquina} value={maquina.codigo_maquina}>{maquina.codigo_maquina} · {maquina.nombre}</option>
          ))}
        </select>
      </td>
      <td className={CELDA}>
        <select
          aria-label="Operario"
          value={fila.operario}
          onChange={(e) => cambiar({ operario: e.target.value })}
          disabled={!fila.codigo_maquina}
          className={CONTROL}
        >
          <option value="">{fila.codigo_maquina && !operarios.length ? 'Sin operarios asignados' : 'Seleccione…'}</option>
          {operarios.map((operario) => <option key={operario.usuario} value={operario.usuario}>{operario.nombre}</option>)}
        </select>
      </td>
      <td className={CELDA}>
        <input aria-label="Tiempo de operación (min)" type="number" min="0" step="any" value={fila.minutos_operacion}
          onChange={(e) => cambiar({ minutos_operacion: e.target.value })} className={`${CONTROL} text-right`} />
      </td>
      <td className={CELDA}>
        <input aria-label="Setup (min)" type="number" min="0" step="any" value={fila.minutos_setup ?? ''}
          onChange={(e) => cambiar({ minutos_setup: e.target.value })} className={`${CONTROL} text-right`} />
      </td>
      <td className={CELDA}>
        <input aria-label="Fecha" type="date" value={fila.fecha || ''} onChange={(e) => cambiar({ fecha: e.target.value })} className={CONTROL} />
      </td>
    </>
  );
}

export default function CargaTiemposOp({ codigoOp }) {
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [nueva, setNueva] = useState(FILA_NUEVA);
  const [edicion, setEdicion] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [historial, setHistorial] = useState(null);

  const cargar = useCallback(async () => {
    try {
      const { data } = await API.get(RUTA, { params: { codigo_op: codigoOp } });
      setDatos(data);
      setError('');
    } catch (fallo) {
      setError(mensajeError(fallo, 'No fue posible cargar los tiempos de la OP.'));
    } finally {
      setCargando(false);
    }
  }, [codigoOp]);

  useEffect(() => {
    setCargando(true);
    setDatos(null);
    setNueva(FILA_NUEVA());
    setEdicion(null);
    cargar();
  }, [cargar]);

  const editable = Boolean(datos?.puede_registrar && !datos?.op_cerrada);
  const veCostos = Boolean(datos?.ve_costos);
  const columnas = useMemo(() => [
    'Proceso', 'Estación', 'Operario', 'Tiempo de operación (min)', 'Setup (min)', 'Fecha', 'Registrado por',
    ...(veCostos ? ['Costo'] : []), ''
  ], [veCostos]);

  const enviar = async (accion, mensajeExito, mensajeFallo) => {
    setError('');
    setAviso('');
    setEnviando(true);
    try {
      await accion();
      setAviso(mensajeExito);
      await cargar();
      return true;
    } catch (fallo) {
      setError(mensajeError(fallo, mensajeFallo));
      return false;
    } finally {
      setEnviando(false);
    }
  };

  const agregar = async () => {
    const ok = await enviar(
      () => API.post(RUTA, { codigo_op: codigoOp, ...cuerpo(nueva) }),
      'Tiempo agregado.',
      'No se pudo agregar el tiempo.'
    );
    if (ok) setNueva((actual) => ({ ...FILA_NUEVA(), fecha: actual.fecha }));
  };

  const guardarCorreccion = async () => {
    const ok = await enviar(
      () => API.post(`${RUTA}/corregir`, { id_registro: edicion.id_registro, motivo: edicion.motivo, ...cuerpo(edicion) }),
      'Corrección guardada.',
      'No se pudo guardar la corrección.'
    );
    if (ok) setEdicion(null);
  };

  if (cargando) return <p className="rounded bg-white p-4 text-center font-semibold text-slate-600">Cargando tiempos…</p>;
  if (!datos) return <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 font-semibold text-red-800">{error}</p>;

  const procesos = datos.procesos || [];
  const maquinas = datos.maquinas || [];

  return (
    <div className="space-y-2">
      {datos.op_cerrada && <p className="rounded border border-slate-300 bg-slate-100 p-2 text-slate-700">La OP está cerrada: los tiempos ya no se agregan ni se corrigen.</p>}
      {!datos.puede_registrar && <p className="rounded border border-slate-300 bg-slate-100 p-2 text-slate-700">Su rol consulta los tiempos pero no los registra.</p>}
      {!procesos.length && <p className="rounded border border-amber-200 bg-amber-50 p-2 text-amber-900">La OP no tiene procesos en su ruta: no hay a qué cargar tiempos.</p>}
      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 font-semibold text-red-800">{error}</p>}
      {aviso && <p role="status" className="rounded border border-emerald-200 bg-emerald-50 p-2 font-semibold text-emerald-800">{aviso}</p>}

      <div className="overflow-x-auto border border-slate-300 bg-white">
        <table className="w-full min-w-[1000px] border-collapse text-left">
          <thead className="bg-slate-100 text-slate-700">
            <tr>{columnas.map((columna, indice) => <th key={`${columna}-${indice}`} scope="col" className="border-b border-r border-slate-300 px-1.5 py-1 font-semibold">{columna}</th>)}</tr>
          </thead>
          <tbody>
            {datos.registros.map((registro) => {
              const enEdicion = edicion?.id_registro === registro.id_registro;
              return (
                <React.Fragment key={registro.id_registro}>
                  <tr className="odd:bg-white even:bg-slate-50">
                    {enEdicion ? (
                      <CamposFila fila={edicion} cambiar={(cambio) => setEdicion((actual) => ({ ...actual, ...cambio }))} procesos={procesos} maquinas={maquinas} />
                    ) : (
                      <>
                        <td className={CELDA}>{registro.proceso}</td>
                        <td className={CELDA}>{registro.codigo_maquina}</td>
                        <td className={CELDA}>{registro.operario_nombre || registro.operario}</td>
                        <td className={`${CELDA} text-right font-mono`}>{registro.minutos_operacion}</td>
                        <td className={`${CELDA} text-right font-mono`}>{registro.minutos_setup ?? ''}</td>
                        <td className={CELDA}>{registro.fecha}</td>
                      </>
                    )}
                    <td className={CELDA}>{registro.registrado_por}</td>
                    {veCostos && <td className={`${CELDA} text-right font-mono`}>{moneda(registro.costo)}</td>}
                    <td className={`${CELDA} whitespace-nowrap`}>
                        {editable && !enEdicion && (
                          <button type="button" disabled={enviando} onClick={() => setEdicion({ ...registro, minutos_setup: registro.minutos_setup ?? '', motivo: '' })}
                            className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100">Corregir</button>
                        )}
                        {!!registro.correcciones.length && (
                          <button type="button" onClick={() => setHistorial(historial === registro.id_registro ? null : registro.id_registro)}
                            className="ml-1 rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100">
                            Correcciones ({registro.correcciones.length})
                          </button>
                        )}
                    </td>
                  </tr>
                  {enEdicion && (
                    <tr className="bg-amber-50">
                      <td colSpan={columnas.length} className={CELDA}>
                        <div className="flex flex-wrap items-center gap-2">
                          <label className="flex flex-1 items-center gap-2 font-semibold">
                            Motivo de la corrección
                            <input type="text" value={edicion.motivo} onChange={(e) => setEdicion((actual) => ({ ...actual, motivo: e.target.value }))}
                              className={`${CONTROL} flex-1 font-normal`} placeholder="Obligatorio" />
                          </label>
                          <button type="button" disabled={enviando || !edicion.motivo.trim()} onClick={guardarCorreccion}
                            className="rounded bg-emerald-700 px-3 py-1 font-bold text-white hover:bg-emerald-800 disabled:opacity-50">Guardar corrección</button>
                          <button type="button" onClick={() => setEdicion(null)} className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100">Cancelar</button>
                        </div>
                      </td>
                    </tr>
                  )}
                  {historial === registro.id_registro && (
                    <tr className="bg-slate-50">
                      <td colSpan={columnas.length} className={CELDA}>
                        <ul className="space-y-1">
                          {registro.correcciones.map((correccion, indice) => (
                            <li key={`${correccion.corregido_en}-${indice}`}>
                              <strong>{fechaHora(correccion.corregido_en)}</strong> · {correccion.corregido_por} · {correccion.motivo}
                              <span className="text-slate-500"> (antes: {correccion.valores_anteriores?.minutos_operacion} min, setup {correccion.valores_anteriores?.minutos_setup ?? '—'} min, {correccion.valores_anteriores?.fecha})</span>
                            </li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
            {!datos.registros.length && (
              <tr><td colSpan={columnas.length} className="px-2 py-4 text-center text-slate-500">La OP no tiene tiempos cargados.</td></tr>
            )}
            {editable && !!procesos.length && (
              <tr className="bg-emerald-50/50">
                <CamposFila fila={nueva} cambiar={(cambio) => setNueva((actual) => ({ ...actual, ...cambio }))} procesos={procesos} maquinas={maquinas} />
                <td className={CELDA} />
                {veCostos && <td className={CELDA} />}
                <td className={CELDA}>
                  <button
                    type="button"
                    onClick={agregar}
                    disabled={enviando || !nueva.id_operacion || !nueva.codigo_maquina || !nueva.operario || !(Number(nueva.minutos_operacion) > 0)}
                    className="rounded bg-emerald-700 px-3 py-0.5 font-bold text-white hover:bg-emerald-800 disabled:opacity-50"
                  >
                    Agregar
                  </button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
