// src/views/nivel2/ConfiguracionUsuariosView.jsx
// Usuarios del sistema (reglas/acceso-por-usuario.md). Solo ADMIN entra (el backend responde 403 a
// los demás, con el rol leído de la base). Se entra con el usuario: el sistema sugiere
// nombre.apellido y ADMIN puede escribir otro. El correo es opcional. La contraseña la asigna ADMIN.
// "Desactivar" reemplaza a eliminar: la cuenta no se borra. Cada cambio queda en el historial.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { mensajeError } from '../../services/api';
import { listarRoles, useAccesoConfiguracion } from '../../services/configuracionRoles';
import {
  asignarClave,
  cambiarActivo,
  crearUsuario,
  editarUsuario,
  historialUsuario,
  listarUsuarios,
  sugerirUsuario
} from '../../services/configuracionUsuarios';

const FORMATO_USUARIO = /^[a-z0-9._-]{3,50}$/;
const LONGITUD_MINIMA_CLAVE = 8;
const NUEVO = { nombres: '', apellidos: '', usuario: '', email: '', id_rol: '', clave: '' };
const ACCIONES = {
  CREADO: 'Creado',
  EDITADO: 'Datos editados',
  ROL_ASIGNADO: 'Rol asignado',
  CLAVE_ASIGNADA: 'Contraseña asignada',
  DESACTIVADO: 'Desactivado',
  REACTIVADO: 'Reactivado'
};
const CONTROL = 'w-full rounded border border-slate-300 px-2 py-1 font-normal';

function fechaHora(valor) {
  if (!valor) return '—';
  const fecha = new Date(valor);
  return Number.isNaN(fecha.getTime()) ? valor : fecha.toLocaleString('es-CO');
}

function describirCambios(cambios) {
  return Object.entries(cambios || {})
    .map(([campo, valor]) => (valor && typeof valor === 'object' && 'despues' in valor
      ? `${campo}: ${valor.antes ?? '—'} → ${valor.despues ?? '—'}`
      : `${campo}: ${valor ?? '—'}`))
    .join(' · ');
}

function Campo({ etiqueta, children, ayuda }) {
  return (
    <label className="space-y-1 text-[11px] font-bold text-slate-600">
      <span>{etiqueta}</span>
      {children}
      {ayuda && <span className="block font-normal text-slate-500">{ayuda}</span>}
    </label>
  );
}

export default function ConfiguracionUsuariosView() {
  const acceso = useAccesoConfiguracion();
  const [usuarios, setUsuarios] = useState([]);
  const [roles, setRoles] = useState([]);
  const [denegado, setDenegado] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [nuevo, setNuevo] = useState(NUEVO);
  const usuarioEscrito = useRef(false);
  const [panel, setPanel] = useState(null); // { tipo: 'editar' | 'clave' | 'historial', cuenta }
  const [edicion, setEdicion] = useState({});
  const [clave, setClave] = useState('');
  const [historial, setHistorial] = useState([]);

  const cargar = useCallback(async () => {
    try {
      const [cuentas, listaRoles] = await Promise.all([listarUsuarios(), listarRoles()]);
      setUsuarios(cuentas);
      setRoles(listaRoles.data || []);
    } catch (fallo) {
      if (fallo.response?.status === 403) setDenegado(true);
      else setError(mensajeError(fallo, 'No se pudieron cargar los usuarios.'));
    }
  }, []);

  useEffect(() => {
    if (acceso) cargar();
  }, [acceso, cargar]);

  // Sugerencia nombre.apellido mientras ADMIN no escriba otro usuario
  useEffect(() => {
    if (usuarioEscrito.current || !nuevo.nombres.trim() || !nuevo.apellidos.trim()) return undefined;
    const espera = window.setTimeout(() => {
      sugerirUsuario(nuevo.nombres, nuevo.apellidos)
        .then((sugerido) => {
          if (!usuarioEscrito.current) setNuevo((actual) => ({ ...actual, usuario: sugerido }));
        })
        .catch(() => {});
    }, 300);
    return () => window.clearTimeout(espera);
  }, [nuevo.nombres, nuevo.apellidos]);

  const ejecutar = async (accion, exito, mensajeFallo) => {
    setError('');
    setAviso('');
    setGuardando(true);
    try {
      await accion();
      setAviso(exito);
      await cargar();
      return true;
    } catch (fallo) {
      setError(mensajeError(fallo, mensajeFallo));
      return false;
    } finally {
      setGuardando(false);
    }
  };

  const crear = async (evento) => {
    evento.preventDefault();
    const ok = await ejecutar(
      () => crearUsuario({ ...nuevo, email: nuevo.email.trim() || null, usuario: nuevo.usuario.trim() || null }),
      `Usuario ${nuevo.usuario} creado.`,
      'No se pudo crear el usuario.'
    );
    if (ok) {
      usuarioEscrito.current = false;
      setNuevo(NUEVO);
    }
  };

  const abrir = async (tipo, cuenta) => {
    setError('');
    setPanel({ tipo, cuenta });
    if (tipo === 'editar') {
      setEdicion({ usuario: cuenta.usuario, nombre_completo: cuenta.nombre_completo, email: cuenta.email || '', id_rol: cuenta.id_rol || '' });
    } else if (tipo === 'clave') {
      setClave('');
    } else if (tipo === 'historial') {
      setHistorial([]);
      try {
        setHistorial(await historialUsuario(cuenta.id_usuario));
      } catch (fallo) {
        setError(mensajeError(fallo, 'No se pudo cargar el historial.'));
      }
    }
  };

  const guardarEdicion = async () => {
    const { cuenta } = panel;
    const cambios = Object.fromEntries(Object.entries(edicion).filter(([campo, valor]) => (cuenta[campo] || '') !== valor));
    if (!Object.keys(cambios).length) {
      setPanel(null);
      return;
    }
    const ok = await ejecutar(() => editarUsuario(cuenta.id_usuario, cambios), `Usuario ${edicion.usuario} actualizado.`, 'No se pudo guardar el usuario.');
    if (ok) setPanel(null);
  };

  const guardarClave = async () => {
    const ok = await ejecutar(() => asignarClave(panel.cuenta.id_usuario, clave), `Contraseña asignada a ${panel.cuenta.usuario}.`, 'No se pudo asignar la contraseña.');
    if (ok) setPanel(null);
  };

  const alternarActivo = (cuenta) => ejecutar(
    () => cambiarActivo(cuenta.id_usuario, !cuenta.activo),
    `Usuario ${cuenta.usuario} ${cuenta.activo ? 'desactivado' : 'reactivado'}.`,
    'No se pudo cambiar el estado del usuario.'
  );

  if (acceso === null) return <p className="p-4 text-xs text-slate-500">Cargando…</p>;
  if (!acceso || denegado) {
    return (
      <div role="alert" className="mx-auto mt-6 max-w-lg rounded-xl border border-red-200 bg-white p-6 text-center text-xs shadow-sm">
        <p className="text-2xl font-extrabold text-red-700">403</p>
        <p className="mt-1 font-bold text-slate-900">Acceso denegado</p>
        <p className="mt-1 text-slate-500">Solo el rol ADMIN administra usuarios.</p>
      </div>
    );
  }

  const usuarioNuevoValido = FORMATO_USUARIO.test(nuevo.usuario);
  const puedeCrear = nuevo.nombres.trim() && nuevo.apellidos.trim() && usuarioNuevoValido && nuevo.id_rol
    && nuevo.clave.length >= LONGITUD_MINIMA_CLAVE && !guardando;

  return (
    <div className="min-h-screen space-y-4 bg-slate-50 p-4 text-xs text-slate-800">
      <header className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="font-bold uppercase tracking-wider text-emerald-700">Administración del sistema</p>
        <h1 className="text-xl font-extrabold text-slate-900">Usuarios</h1>
        <p className="mt-1 text-slate-500">Se entra con el usuario; el correo es solo un dato de contacto. Desactivar no borra la cuenta.</p>
      </header>

      {error && <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 font-semibold text-red-800">{error}</div>}
      {aviso && <div role="status" className="rounded border border-emerald-200 bg-emerald-50 p-3 font-semibold text-emerald-800">{aviso}</div>}

      <form onSubmit={crear} className="grid gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-3">
        <h2 className="text-sm font-extrabold text-slate-900 sm:col-span-2 lg:col-span-3">Nuevo usuario</h2>
        <Campo etiqueta="Nombres">
          <input value={nuevo.nombres} onChange={(e) => setNuevo({ ...nuevo, nombres: e.target.value })} className={CONTROL} required />
        </Campo>
        <Campo etiqueta="Apellidos">
          <input value={nuevo.apellidos} onChange={(e) => setNuevo({ ...nuevo, apellidos: e.target.value })} className={CONTROL} required />
        </Campo>
        <Campo etiqueta="Usuario" ayuda="Sugerido: nombre.apellido. 3 a 50 caracteres: minúsculas, números, punto, guion bajo o guion.">
          <input
            value={nuevo.usuario}
            onChange={(e) => {
              usuarioEscrito.current = true;
              setNuevo({ ...nuevo, usuario: e.target.value.toLowerCase() });
            }}
            className={`${CONTROL} ${nuevo.usuario && !usuarioNuevoValido ? 'border-red-300 bg-red-50' : ''}`}
            autoCapitalize="none"
            spellCheck={false}
            required
          />
        </Campo>
        <Campo etiqueta="Correo (opcional)">
          <input type="email" value={nuevo.email} onChange={(e) => setNuevo({ ...nuevo, email: e.target.value })} className={CONTROL} />
        </Campo>
        <Campo etiqueta="Rol">
          <select value={nuevo.id_rol} onChange={(e) => setNuevo({ ...nuevo, id_rol: e.target.value })} className={CONTROL} required>
            <option value="">Seleccione…</option>
            {roles.map((rol) => <option key={rol.id_rol} value={rol.id_rol}>{rol.nombre_rol}</option>)}
          </select>
        </Campo>
        <Campo etiqueta="Contraseña" ayuda={`Mínimo ${LONGITUD_MINIMA_CLAVE} caracteres. No se pide cambiarla al entrar.`}>
          <input type="password" value={nuevo.clave} onChange={(e) => setNuevo({ ...nuevo, clave: e.target.value })} className={CONTROL} autoComplete="new-password" required />
        </Campo>
        <div className="sm:col-span-2 lg:col-span-3">
          <button type="submit" disabled={!puedeCrear} className="rounded bg-emerald-700 px-4 py-1.5 font-bold text-white hover:bg-emerald-800 disabled:opacity-50">
            {guardando ? 'Guardando…' : 'Crear usuario'}
          </button>
        </div>
      </form>

      {panel && (
        <section className="space-y-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-extrabold text-slate-900">
              {panel.tipo === 'editar' && `Editar ${panel.cuenta.usuario}`}
              {panel.tipo === 'clave' && `Asignar contraseña a ${panel.cuenta.usuario}`}
              {panel.tipo === 'historial' && `Historial de ${panel.cuenta.usuario}`}
            </h2>
            <button type="button" onClick={() => setPanel(null)} className="rounded border border-slate-300 bg-white px-2 py-0.5">Cerrar</button>
          </div>
          {panel.tipo === 'editar' && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Campo etiqueta="Usuario">
                <input value={edicion.usuario} onChange={(e) => setEdicion({ ...edicion, usuario: e.target.value.toLowerCase() })} className={CONTROL} />
              </Campo>
              <Campo etiqueta="Nombre completo">
                <input value={edicion.nombre_completo} onChange={(e) => setEdicion({ ...edicion, nombre_completo: e.target.value })} className={CONTROL} />
              </Campo>
              <Campo etiqueta="Correo (opcional)">
                <input type="email" value={edicion.email} onChange={(e) => setEdicion({ ...edicion, email: e.target.value })} className={CONTROL} />
              </Campo>
              <Campo etiqueta="Rol">
                <select value={edicion.id_rol} onChange={(e) => setEdicion({ ...edicion, id_rol: e.target.value })} className={CONTROL}>
                  {roles.map((rol) => <option key={rol.id_rol} value={rol.id_rol}>{rol.nombre_rol}</option>)}
                </select>
              </Campo>
              <div className="sm:col-span-2 lg:col-span-4">
                <button type="button" onClick={guardarEdicion} disabled={guardando || !FORMATO_USUARIO.test(edicion.usuario || '')}
                  className="rounded bg-emerald-700 px-4 py-1.5 font-bold text-white hover:bg-emerald-800 disabled:opacity-50">Guardar cambios</button>
              </div>
            </div>
          )}
          {panel.tipo === 'clave' && (
            <div className="flex flex-wrap items-end gap-3">
              <Campo etiqueta="Contraseña nueva" ayuda={`Mínimo ${LONGITUD_MINIMA_CLAVE} caracteres. Reemplaza la anterior.`}>
                <input type="password" value={clave} onChange={(e) => setClave(e.target.value)} className={CONTROL} autoComplete="new-password" />
              </Campo>
              <button type="button" onClick={guardarClave} disabled={guardando || clave.length < LONGITUD_MINIMA_CLAVE}
                className="rounded bg-emerald-700 px-4 py-1.5 font-bold text-white hover:bg-emerald-800 disabled:opacity-50">Asignar contraseña</button>
            </div>
          )}
          {panel.tipo === 'historial' && (
            <ul className="space-y-1">
              {historial.map((fila, indice) => (
                <li key={`${fila.registrado_en}-${indice}`} className="rounded border border-slate-200 bg-white p-2">
                  <strong>{ACCIONES[fila.accion] || fila.accion}</strong>
                  <span className="text-slate-500"> · {fila.realizado_por} · {fechaHora(fila.registrado_en)}</span>
                  {describirCambios(fila.cambios) && <span className="block text-slate-600">{describirCambios(fila.cambios)}</span>}
                </li>
              ))}
              {!historial.length && <li className="text-slate-500">Sin cambios registrados.</li>}
            </ul>
          )}
        </section>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[800px] border-collapse text-left">
          <thead className="bg-slate-100 text-[10px] uppercase text-slate-600">
            <tr>
              <th className="p-2">Usuario</th>
              <th className="p-2">Nombre</th>
              <th className="p-2">Correo</th>
              <th className="p-2">Rol</th>
              <th className="p-2">Estado</th>
              <th className="p-2 text-right">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {usuarios.map((cuenta) => (
              <tr key={cuenta.id_usuario} className={cuenta.activo ? '' : 'bg-slate-50 text-slate-500'}>
                <td className="p-2 font-mono font-bold">{cuenta.usuario}</td>
                <td className="p-2">{cuenta.nombre_completo}</td>
                <td className="p-2">{cuenta.email || '—'}</td>
                <td className="p-2">{cuenta.nombre_rol || cuenta.id_rol || '—'}</td>
                <td className="p-2">{cuenta.activo ? 'Activo' : 'Desactivado'}</td>
                <td className="whitespace-nowrap p-2 text-right">
                  <button type="button" onClick={() => abrir('editar', cuenta)} className="mr-1 rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100">Editar</button>
                  <button type="button" onClick={() => abrir('clave', cuenta)} className="mr-1 rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100">Contraseña</button>
                  <button type="button" onClick={() => abrir('historial', cuenta)} className="mr-1 rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100">Historial</button>
                  <button type="button" disabled={guardando} onClick={() => alternarActivo(cuenta)}
                    className={`rounded border px-2 py-0.5 ${cuenta.activo ? 'border-red-200 text-red-700 hover:bg-red-50' : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50'}`}>
                    {cuenta.activo ? 'Desactivar' : 'Reactivar'}
                  </button>
                </td>
              </tr>
            ))}
            {!usuarios.length && <tr><td colSpan="6" className="p-4 text-center text-slate-500">No hay usuarios.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
