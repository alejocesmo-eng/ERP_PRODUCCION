// src/views/nivel2/ConfiguracionRolesView.jsx
// Configuración de roles y permisos. Solo ADMIN entra (el backend responde 403 a los demás roles,
// con el rol leído de la base). Los permisos se eligen del catálogo; aquí no se crean permisos.
// Cada cambio queda registrado en el historial del rol con quién y cuándo.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { mensajeError } from '../../services/api';
import { limpiarCachePermisos } from '../../services/permisos';
import OperariosPorMaquina from '../../components/OperariosPorMaquina';
import {
  crearRol,
  editarRol,
  eliminarRol,
  guardarPermisosRol,
  historialPermisosRol,
  listarCatalogoPermisos,
  listarRoles,
  useAccesoConfiguracion
} from '../../services/configuracionRoles';

const ROL_ADMIN = 'ADMIN';
// Permiso técnico de acceso a esta pantalla (migración 31): solo ADMIN y no se lo quita
const PERMISO_CONFIGURACION = 'PERM_CONFIGURACION_ROLES';
const CODIGO_VALIDO = /^[A-Z][A-Z0-9_]{1,49}$/;
const FORMULARIO_ROL = { id_rol: '', nombre_rol: '', descripcion: '' };

function igualesConjuntos(a, b) {
  return a.size === b.size && [...a].every((valor) => b.has(valor));
}

function fechaHora(valor) {
  if (!valor) return '—';
  const fecha = new Date(valor);
  return Number.isNaN(fecha.getTime()) ? valor : fecha.toLocaleString('es-CO');
}

function AccesoDenegado() {
  return (
    <div className="min-h-screen bg-slate-50 p-4 text-xs text-slate-800">
      <div role="alert" className="mx-auto max-w-lg rounded-xl border border-red-200 bg-white p-6 text-center shadow-sm">
        <p className="text-2xl font-extrabold text-red-700">403</p>
        <p className="mt-1 font-bold text-slate-900">Acceso denegado</p>
        <p className="mt-1 text-slate-500">Solo el rol ADMIN entra a Configuración de roles y permisos.</p>
      </div>
    </div>
  );
}

export default function ConfiguracionRolesView() {
  const acceso = useAccesoConfiguracion();
  const [roles, setRoles] = useState([]);
  const [catalogo, setCatalogo] = useState([]);
  const [borrador, setBorrador] = useState({});
  const [cargando, setCargando] = useState(true);
  const [denegado, setDenegado] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [formulario, setFormulario] = useState(FORMULARIO_ROL);
  const [seleccionado, setSeleccionado] = useState('');
  const [edicion, setEdicion] = useState({ nombre_rol: '', descripcion: '' });
  const [historial, setHistorial] = useState([]);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      const [respuestaRoles, respuestaPermisos] = await Promise.all([listarRoles(), listarCatalogoPermisos()]);
      setRoles(respuestaRoles.data);
      setCatalogo(respuestaPermisos.data);
      setBorrador(Object.fromEntries(respuestaRoles.data.map((rol) => [rol.id_rol, new Set(rol.permisos)])));
    } catch (fallo) {
      if (fallo?.response?.status === 403) setDenegado(true);
      else setError(mensajeError(fallo, 'No se pudieron cargar los roles y permisos.'));
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    if (acceso) cargar();
  }, [acceso, cargar]);

  const rolSeleccionado = roles.find((rol) => rol.id_rol === seleccionado) || null;

  useEffect(() => {
    if (!rolSeleccionado) {
      setHistorial([]);
      return;
    }
    setEdicion({ nombre_rol: rolSeleccionado.nombre_rol || '', descripcion: rolSeleccionado.descripcion || '' });
    historialPermisosRol(rolSeleccionado.id_rol)
      .then((respuesta) => setHistorial(respuesta.data))
      .catch(() => setHistorial([]));
  }, [rolSeleccionado]);

  const modulos = useMemo(() => {
    const grupos = {};
    catalogo.forEach((permiso) => {
      (grupos[permiso.modulo] = grupos[permiso.modulo] || []).push(permiso);
    });
    return Object.entries(grupos);
  }, [catalogo]);

  const rolesCambiados = useMemo(
    () => roles.filter((rol) => borrador[rol.id_rol] && !igualesConjuntos(borrador[rol.id_rol], new Set(rol.permisos))),
    [roles, borrador]
  );

  if (acceso === null) {
    return <div className="min-h-screen bg-slate-50 p-8 text-center text-xs font-semibold text-slate-500">Verificando acceso…</div>;
  }
  if (!acceso || denegado) return <AccesoDenegado />;

  const alternar = (idRol, idPermiso) => {
    setBorrador((previo) => {
      const permisos = new Set(previo[idRol]);
      if (permisos.has(idPermiso)) permisos.delete(idPermiso);
      else permisos.add(idPermiso);
      return { ...previo, [idRol]: permisos };
    });
  };

  // El acceso a Configuración solo es de ADMIN, y ADMIN no se lo quita a sí mismo
  const bloqueado = (idPermiso) => idPermiso === PERMISO_CONFIGURACION;

  const guardarMatriz = async () => {
    setGuardando(true);
    setError('');
    setAviso('');
    try {
      for (const rol of rolesCambiados) {
        await guardarPermisosRol(rol.id_rol, [...borrador[rol.id_rol]].sort());
      }
      limpiarCachePermisos();
      setAviso(`Permisos actualizados en ${rolesCambiados.length} rol(es). Aplican desde la siguiente consulta.`);
      await cargar();
    } catch (fallo) {
      setError(mensajeError(fallo, 'No se pudieron guardar los permisos.'));
      await cargar();
    } finally {
      setGuardando(false);
    }
  };

  const enviarRol = async (evento) => {
    evento.preventDefault();
    setError('');
    setAviso('');
    if (!CODIGO_VALIDO.test(formulario.id_rol)) {
      setError('El código va en mayúsculas, sin espacios, con letras, dígitos o guion bajo (2 a 50).');
      return;
    }
    try {
      await crearRol({
        id_rol: formulario.id_rol,
        nombre_rol: formulario.nombre_rol.trim(),
        descripcion: formulario.descripcion.trim() || null
      });
      setAviso(`Rol ${formulario.id_rol} creado.`);
      setFormulario(FORMULARIO_ROL);
      await cargar();
    } catch (fallo) {
      setError(mensajeError(fallo, 'No se pudo crear el rol.'));
    }
  };

  const guardarEdicion = async () => {
    setError('');
    setAviso('');
    try {
      await editarRol(rolSeleccionado.id_rol, {
        nombre_rol: edicion.nombre_rol.trim(),
        descripcion: edicion.descripcion.trim() || null
      });
      setAviso(`Rol ${rolSeleccionado.id_rol} actualizado.`);
      await cargar();
    } catch (fallo) {
      setError(mensajeError(fallo, 'No se pudo actualizar el rol.'));
    }
  };

  const borrarRol = async () => {
    setError('');
    setAviso('');
    try {
      await eliminarRol(rolSeleccionado.id_rol);
      setAviso(`Rol ${rolSeleccionado.id_rol} eliminado.`);
      setSeleccionado('');
      await cargar();
    } catch (fallo) {
      setError(mensajeError(fallo, 'No se pudo eliminar el rol.'));
    }
  };

  return (
    <div className="min-h-screen space-y-4 bg-slate-50 p-4 text-xs text-slate-800">
      <header className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div>
          <p className="font-bold uppercase tracking-wider text-emerald-700">Administración del sistema</p>
          <h1 className="text-xl font-extrabold text-slate-900">Roles y Permisos</h1>
          <p className="mt-1 text-slate-500">Cree roles y asigne permisos del catálogo. Los cambios aplican sin reiniciar la aplicación.</p>
        </div>
        <span className="rounded border border-slate-200 bg-slate-50 px-3 py-1.5 font-bold text-slate-600">
          {roles.length} roles · {catalogo.length} permisos
        </span>
      </header>

      {error && <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 font-semibold text-red-800">{error}</div>}
      {aviso && <div role="status" className="rounded border border-emerald-200 bg-emerald-50 p-3 font-semibold text-emerald-800">{aviso}</div>}

      <form onSubmit={enviarRol} className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="space-y-1 text-[11px] font-bold text-slate-600">
          <span>Código técnico</span>
          <input
            required
            value={formulario.id_rol}
            onChange={(evento) => setFormulario({ ...formulario, id_rol: evento.target.value.toUpperCase().replace(/\s/g, '') })}
            placeholder="CODIGO_ROL"
            maxLength={50}
            className="block w-48 rounded border border-slate-300 px-2.5 py-1.5 font-mono text-xs font-normal outline-none focus:border-emerald-500"
          />
        </label>
        <label className="space-y-1 text-[11px] font-bold text-slate-600">
          <span>Nombre de negocio</span>
          <input
            required
            value={formulario.nombre_rol}
            onChange={(evento) => setFormulario({ ...formulario, nombre_rol: evento.target.value })}
            maxLength={100}
            className="block w-56 rounded border border-slate-300 px-2.5 py-1.5 text-xs font-normal outline-none focus:border-emerald-500"
          />
        </label>
        <label className="min-w-60 flex-1 space-y-1 text-[11px] font-bold text-slate-600">
          <span>Descripción (opcional)</span>
          <input
            value={formulario.descripcion}
            onChange={(evento) => setFormulario({ ...formulario, descripcion: evento.target.value })}
            className="block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs font-normal outline-none focus:border-emerald-500"
          />
        </label>
        <button type="submit" className="rounded bg-emerald-700 px-3 py-2 font-bold text-white hover:bg-emerald-800">＋ Crear rol</button>
        <p className="w-full text-[10px] text-slate-500">El código no se puede repetir ni cambiar después de crearlo.</p>
      </form>

      {cargando ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center font-semibold text-slate-500">Cargando roles y permisos…</div>
      ) : (
        <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-extrabold text-slate-900">Matriz de permisos</h2>
            <button
              type="button"
              disabled={!rolesCambiados.length || guardando}
              onClick={guardarMatriz}
              className="rounded bg-blue-700 px-3 py-2 font-bold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {guardando ? 'Guardando…' : `Guardar cambios${rolesCambiados.length ? ` (${rolesCambiados.length} rol(es))` : ''}`}
            </button>
          </div>
          <div className="overflow-x-auto rounded border border-slate-200">
            <table className="border-collapse text-left">
              <thead className="bg-slate-100 text-[10px] uppercase text-slate-600">
                <tr>
                  <th className="sticky left-0 z-10 min-w-64 bg-slate-100 px-3 py-2">Permiso</th>
                  {roles.map((rol) => (
                    <th key={rol.id_rol} className="px-2 py-2 text-center align-bottom">
                      <button
                        type="button"
                        onClick={() => setSeleccionado(rol.id_rol)}
                        title={rol.nombre_rol}
                        className={`rounded px-1.5 py-0.5 font-mono font-bold hover:bg-blue-100 ${seleccionado === rol.id_rol ? 'bg-blue-600 text-white' : ''}`}
                      >
                        {rol.id_rol}
                      </button>
                      <div className="mt-0.5 font-normal normal-case text-slate-500">{rol.usuarios} usuario(s)</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {modulos.map(([modulo, permisos]) => (
                  <React.Fragment key={modulo}>
                    <tr className="bg-slate-50">
                      <td colSpan={roles.length + 1} className="sticky left-0 px-3 py-1 text-[10px] font-extrabold uppercase text-purple-800">{modulo}</td>
                    </tr>
                    {permisos.map((permiso) => (
                      <tr key={permiso.id_permiso} className="hover:bg-slate-50">
                        <td className="sticky left-0 bg-white px-3 py-1.5">
                          <div className="font-mono font-bold">{permiso.id_permiso}</div>
                          {permiso.descripcion && <div className="text-[10px] text-slate-500">{permiso.descripcion}</div>}
                        </td>
                        {roles.map((rol) => (
                          <td key={rol.id_rol} className="px-2 py-1.5 text-center">
                            <input
                              type="checkbox"
                              aria-label={`${permiso.id_permiso} en ${rol.id_rol}`}
                              checked={borrador[rol.id_rol]?.has(permiso.id_permiso) || false}
                              disabled={bloqueado(permiso.id_permiso) || guardando}
                              onChange={() => alternar(rol.id_rol, permiso.id_permiso)}
                              className="h-3.5 w-3.5 accent-emerald-600"
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-slate-500">
            {PERMISO_CONFIGURACION} es el acceso a esta pantalla: solo lo tiene {ROL_ADMIN} y no se puede quitar desde aquí.
          </p>
        </section>
      )}

      {rolSeleccionado && (
        <section className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-2">
          <div className="space-y-3">
            <h2 className="text-sm font-extrabold text-slate-900">
              Rol <span className="font-mono">{rolSeleccionado.id_rol}</span>
            </h2>
            <label className="block space-y-1 text-[11px] font-bold text-slate-600">
              <span>Nombre de negocio</span>
              <input
                value={edicion.nombre_rol}
                onChange={(evento) => setEdicion({ ...edicion, nombre_rol: evento.target.value })}
                maxLength={100}
                className="block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs font-normal outline-none focus:border-emerald-500"
              />
            </label>
            <label className="block space-y-1 text-[11px] font-bold text-slate-600">
              <span>Descripción</span>
              <input
                value={edicion.descripcion}
                onChange={(evento) => setEdicion({ ...edicion, descripcion: evento.target.value })}
                className="block w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs font-normal outline-none focus:border-emerald-500"
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={guardarEdicion} disabled={!edicion.nombre_rol.trim()} className="rounded bg-emerald-700 px-3 py-2 font-bold text-white hover:bg-emerald-800 disabled:bg-slate-300">
                Guardar rol
              </button>
              <button
                type="button"
                onClick={borrarRol}
                disabled={rolSeleccionado.usuarios > 0}
                title={rolSeleccionado.usuarios > 0 ? 'Un rol con usuarios asignados no se puede eliminar' : 'Eliminar rol'}
                className="rounded border border-red-300 bg-red-50 px-3 py-2 font-bold text-red-800 hover:bg-red-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
              >
                Eliminar rol
              </button>
            </div>
            {rolSeleccionado.usuarios > 0 && (
              <p className="text-[10px] text-amber-700">Tiene {rolSeleccionado.usuarios} usuario(s) asignado(s): reasígnelos antes de eliminarlo.</p>
            )}
          </div>
          <div className="space-y-2">
            <h3 className="font-extrabold text-slate-900">Historial de permisos</h3>
            {historial.length === 0 ? (
              <p className="text-slate-500">Sin cambios registrados.</p>
            ) : (
              <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto rounded border border-slate-200">
                {historial.map((cambio, indice) => (
                  <li key={`${cambio.id_permiso}-${cambio.registrado_en}-${indice}`} className="flex flex-wrap items-center gap-2 px-3 py-1.5">
                    <span className={`rounded px-2 py-0.5 font-extrabold ${cambio.accion === 'ASIGNADO' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                      {cambio.accion === 'ASIGNADO' ? 'Asignado' : 'Retirado'}
                    </span>
                    <span className="font-mono font-bold">{cambio.id_permiso}</span>
                    <span className="text-slate-500">{cambio.usuario_email} · {fechaHora(cambio.registrado_en)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      )}

      <OperariosPorMaquina />
    </div>
  );
}
