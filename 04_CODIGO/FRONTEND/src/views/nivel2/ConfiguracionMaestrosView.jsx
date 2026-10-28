import React, { useCallback, useEffect, useMemo, useState } from 'react';
import API from '../../services/api';

const PESTANAS = [
  { id: 'socios', nombre: '🏢 Socios de Negocio' },
  { id: 'personal', nombre: '👥 Personal & Usuarios' },
  { id: 'finanzas', nombre: '🏦 Cuentas y Centros de Costo' },
  { id: 'catalogos', nombre: '📦 Catálogos Base' }
];

const FORMULARIO_SOCIO = {
  nit_cedula: '',
  razon_social: '',
  es_cliente: true,
  es_proveedor: false,
  direccion: '',
  telefono: '',
  email: '',
  condiciones_pago_dias: 30,
  cuenta_contable_por_cobrar: '',
  cuenta_contable_por_pagar: '',
  estado_activo: true
};
const FORMULARIO_PERSONAL = {
  cedula: '',
  nombre_completo: '',
  area: 'PRODUCCION',
  cargo: '',
  tarifa_hora_mano_obra: 0,
  id_usuario_sistema: ''
};
const FORMULARIO_FINANCIERO = {
  tipo: 'CUENTA_CONTABLE',
  codigo: '',
  nombre: '',
  descripcion: '',
  cuenta_padre: '',
  activo: true
};
const FORMULARIO_CATEGORIA = { codigo: '', nombre: '', icono: '📦', descripcion: '' };
const FORMULARIO_UNIDAD = { codigo: '', nombre: '', simbolo: '', activo: true };
const ETIQUETAS_AREA = {
  VENTAS: 'Ventas',
  DISENO: 'Diseño e ingeniería',
  ALMACEN: 'Almacén',
  PRODUCCION: 'Producción',
  CALIDAD: 'Calidad',
  ADMINISTRACION: 'Administración'
};

function obtenerRol() {
  const token = localStorage.getItem('sgi_token');
  if (!token) return '';
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const datos = JSON.parse(window.atob(payload + '='.repeat((4 - payload.length % 4) % 4)));
    return String(datos.rol || '').toUpperCase();
  } catch {
    return '';
  }
}

function Campo({ etiqueta, children }) {
  return (
    <label className="block space-y-1 text-[11px] font-bold text-slate-600">
      <span>{etiqueta}</span>
      {children}
    </label>
  );
}

function Entrada({ className = '', ...props }) {
  return <input {...props} className={`w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs font-normal text-slate-800 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 ${className}`} />;
}

function Select({ children, ...props }) {
  return <select {...props} className="w-full rounded border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-normal text-slate-800 outline-none focus:border-emerald-500">{children}</select>;
}

export default function ConfiguracionMaestrosView() {
  const [pestana, setPestana] = useState('socios');
  const [socios, setSocios] = useState([]);
  const [personal, setPersonal] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [estructura, setEstructura] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [filtroSocio, setFiltroSocio] = useState('');
  const [subpestanaCatalogo, setSubpestanaCatalogo] = useState('categorias');
  const [modal, setModal] = useState(null);
  const [formulario, setFormulario] = useState({});
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const rol = useMemo(() => obtenerRol(), []);
  const admin = rol === 'ADMIN';
  const puedeGestionarCatalogo = admin || rol === 'ALMACEN';

  const cargarDatos = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      const solicitudes = [
        API.get('/maestros/socios'),
        API.get('/maestros/personal'),
        API.get('/maestros/cuentas-costos'),
        API.get('/maestros/catalogos')
      ];
      if (admin) solicitudes.push(API.get('/maestros/personal/usuarios-disponibles'));
      const [resSocios, resPersonal, resEstructura, resCatalogos, resUsuarios] = await Promise.all(solicitudes);
      setSocios(resSocios.data);
      setPersonal(resPersonal.data);
      setEstructura(resEstructura.data);
      setCategorias(resCatalogos.data.categorias);
      setUnidades(resCatalogos.data.unidades_medida);
      setUsuarios(resUsuarios?.data || []);
    } catch (fallo) {
      setError(fallo.response?.data?.detail || 'No fue posible cargar los datos maestros.');
    } finally {
      setCargando(false);
    }
  }, [admin]);

  useEffect(() => {
    cargarDatos();
  }, [cargarDatos]);

  const abrirNuevo = (tipo, valores) => {
    setError('');
    setAviso('');
    setModal({ tipo, id: null });
    setFormulario({ ...valores });
  };

  const abrirEdicion = (tipo, registro, id) => {
    setError('');
    setAviso('');
    setModal({ tipo, id });
    setFormulario({ ...registro });
  };

  const cambiar = (campo, valor) => setFormulario((actual) => ({ ...actual, [campo]: valor }));

  const guardar = async (evento) => {
    evento.preventDefault();
    if (!modal) return;
    setGuardando(true);
    setError('');
    try {
      const configuracion = {
        socio: { ruta: '/maestros/socios', normalizar: (f) => ({ ...f, condiciones_pago_dias: Number(f.condiciones_pago_dias) }) },
        personal: { ruta: '/maestros/personal', normalizar: (f) => ({ ...f, tarifa_hora_mano_obra: Number(f.tarifa_hora_mano_obra), id_usuario_sistema: f.id_usuario_sistema || null }) },
        financiero: { ruta: '/maestros/cuentas-costos', normalizar: (f) => ({ ...f, cuenta_padre: f.cuenta_padre || null }) },
        categoria: { ruta: '/maestros/catalogos/categorias' },
        unidad: { ruta: '/maestros/catalogos/unidades' }
      }[modal.tipo];
      const payload = configuracion.normalizar ? configuracion.normalizar(formulario) : formulario;
      if (modal.id) await API.put(`${configuracion.ruta}/${modal.id}`, payload);
      else await API.post(configuracion.ruta, payload);
      setModal(null);
      setAviso('Los datos se guardaron correctamente.');
      await cargarDatos();
    } catch (fallo) {
      setError(fallo.response?.data?.detail || 'No fue posible guardar los datos.');
    } finally {
      setGuardando(false);
    }
  };

  const desactivar = async (tipo, registro) => {
    const configuracion = {
      socio: { ruta: `/maestros/socios/${registro.id_socio}`, mensaje: '¿Desactivar este socio de negocio?' },
      personal: { ruta: `/maestros/personal/${registro.id_trabajador}`, mensaje: '¿Eliminar este registro de personal?' },
      financiero: { ruta: `/maestros/cuentas-costos/${registro.id_elemento}`, mensaje: '¿Desactivar este elemento financiero?' },
      categoria: { ruta: `/maestros/catalogos/categorias/${registro.id_categoria}`, mensaje: '¿Eliminar esta categoría?' },
      unidad: { ruta: `/maestros/catalogos/unidades/${registro.id_unidad}`, mensaje: '¿Desactivar esta unidad de medida?' }
    }[tipo];
    if (!window.confirm(configuracion.mensaje)) return;
    setError('');
    setAviso('');
    try {
      await API.delete(configuracion.ruta);
      setAviso('El cambio se guardó correctamente.');
      await cargarDatos();
    } catch (fallo) {
      setError(fallo.response?.data?.detail || 'No fue posible completar la operación.');
    }
  };

  const sociosFiltrados = socios.filter((socio) => (
    `${socio.nit_cedula} ${socio.razon_social} ${socio.email || ''}`
      .toLowerCase().includes(filtroSocio.toLowerCase())
  ));
  const cuentasContables = estructura.filter((item) => item.tipo === 'CUENTA_CONTABLE');
  const centrosCosto = estructura.filter((item) => item.tipo === 'CENTRO_COSTO');
  const unidadesNegocio = estructura.filter((item) => item.tipo === 'UNIDAD_NEGOCIO');
  const iconoEstado = (activo) => activo
    ? 'bg-emerald-100 text-emerald-800'
    : 'bg-slate-100 text-slate-500';

  return (
    <div className="min-h-screen space-y-4 bg-slate-50 p-4 text-xs text-slate-800">
      <header className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div>
          <p className="font-bold uppercase tracking-wider text-emerald-700">Administración del sistema</p>
          <h1 className="text-xl font-extrabold text-slate-900">Datos Maestros</h1>
          <p className="mt-1 text-slate-500">Socios, personal, estructura financiera y catálogos compartidos.</p>
        </div>
        <span className="rounded border border-slate-200 bg-slate-50 px-3 py-1.5 font-bold text-slate-600">
          {socios.length} socios · {personal.length} trabajadores · {estructura.length} elementos financieros
        </span>
      </header>

      <nav className="flex flex-wrap gap-1 rounded-lg border border-slate-200 bg-white p-1">
        {PESTANAS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setPestana(item.id)}
            className={`rounded px-3 py-2 font-bold transition ${pestana === item.id ? 'bg-emerald-700 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
          >
            {item.nombre}
          </button>
        ))}
      </nav>

      {error && <div role="alert" className="rounded border border-red-200 bg-red-50 p-3 font-semibold text-red-800">{error}</div>}
      {aviso && <div role="status" className="rounded border border-emerald-200 bg-emerald-50 p-3 font-semibold text-emerald-800">{aviso}</div>}
      {cargando ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center font-semibold text-slate-500">Cargando datos maestros…</div>
      ) : (
        <>
          {pestana === 'socios' && (
            <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-end justify-between gap-2">
                <label className="min-w-60 flex-1 font-bold text-slate-600">
                  Buscar socio
                  <Entrada value={filtroSocio} onChange={(evento) => setFiltroSocio(evento.target.value)} placeholder="NIT, razón social o correo" className="mt-1 max-w-lg" />
                </label>
                {admin && <button type="button" onClick={() => abrirNuevo('socio', FORMULARIO_SOCIO)} className="rounded bg-emerald-700 px-3 py-2 font-bold text-white hover:bg-emerald-800">＋ Nuevo socio</button>}
              </div>
              <div className="overflow-x-auto rounded border border-slate-200">
                <table className="w-full min-w-[800px] border-collapse text-left">
                  <thead className="bg-slate-100 text-[10px] uppercase text-slate-600"><tr><th className="px-3 py-2">NIT / Cédula</th><th className="px-3 py-2">Razón social</th><th className="px-3 py-2">Clasificación</th><th className="px-3 py-2">Contacto</th><th className="px-3 py-2">Condición de pago</th><th className="px-3 py-2">Cuentas asociadas</th><th className="px-3 py-2">Estado</th>{admin && <th className="px-3 py-2">Acciones</th>}</tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {sociosFiltrados.map((socio) => {
                      const tipo = socio.es_cliente && socio.es_proveedor ? 'Cliente y proveedor' : socio.es_cliente ? 'Cliente' : 'Proveedor';
                      return (
                        <tr key={socio.id_socio} className="hover:bg-slate-50">
                          <td className="px-3 py-1.5 font-mono font-bold">{socio.nit_cedula}</td>
                          <td className="px-3 py-1.5 font-semibold">{socio.razon_social}</td>
                          <td className="px-3 py-1.5"><span className="rounded bg-purple-100 px-2 py-0.5 font-extrabold text-purple-800">{tipo}</span></td>
                          <td className="px-3 py-1.5">{socio.email || socio.telefono || '—'}</td>
                          <td className="px-3 py-1.5">{socio.condiciones_pago_dias} días</td>
                          <td className="px-3 py-1.5 text-[10px]"><span className="block">Cobrar: {socio.cuenta_contable_por_cobrar || '—'}</span><span className="block text-slate-500">Pagar: {socio.cuenta_contable_por_pagar || '—'}</span></td>
                          <td className="px-3 py-1.5"><span className={`rounded px-2 py-0.5 font-bold ${iconoEstado(socio.estado_activo)}`}>{socio.estado_activo ? 'Activo' : 'Inactivo'}</span></td>
                          {admin && <td className="space-x-2 px-3 py-1.5"><button type="button" onClick={() => abrirEdicion('socio', socio, socio.id_socio)} className="font-bold text-blue-700">Editar</button>{socio.estado_activo && <button type="button" onClick={() => desactivar('socio', socio)} className="font-bold text-red-700">Desactivar</button>}</td>}
                        </tr>
                      );
                    })}
                    {!sociosFiltrados.length && <tr><td colSpan={admin ? 8 : 7} className="p-6 text-center text-slate-500">No hay socios que coincidan con la búsqueda.</td></tr>}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {pestana === 'personal' && (
            <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-extrabold text-slate-800">Personal & Usuarios</h2><p className="text-slate-500">Vinculación de colaboradores con las cuentas de acceso al sistema.</p></div>{admin && <button type="button" onClick={() => abrirNuevo('personal', FORMULARIO_PERSONAL)} className="rounded bg-emerald-700 px-3 py-2 font-bold text-white hover:bg-emerald-800">＋ Nuevo trabajador</button>}</div>
              <div className="overflow-x-auto rounded border border-slate-200">
                <table className="w-full min-w-[800px] border-collapse text-left">
                  <thead className="bg-slate-100 text-[10px] uppercase text-slate-600"><tr><th className="px-3 py-2">Cédula</th><th className="px-3 py-2">Nombre completo</th><th className="px-3 py-2">Área / Cargo</th><th className="px-3 py-2">Tarifa por hora</th><th className="px-3 py-2">Usuario vinculado</th>{admin && <th className="px-3 py-2">Acciones</th>}</tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {personal.map((trabajador) => (
                      <tr key={trabajador.id_trabajador} className="hover:bg-slate-50">
                        <td className="px-3 py-1.5 font-mono">{trabajador.cedula}</td><td className="px-3 py-1.5 font-semibold">{trabajador.nombre_completo}</td>
                        <td className="px-3 py-1.5"><span className="font-bold">{ETIQUETAS_AREA[trabajador.area] || trabajador.area}</span><span className="ml-2 text-slate-500">{trabajador.cargo}</span></td>
                        <td className="px-3 py-1.5">{Number(trabajador.tarifa_hora_mano_obra || 0).toLocaleString('es-CO', { style: 'currency', currency: 'COP' })}</td>
                        <td className="px-3 py-1.5">{trabajador.usuario || 'Sin vincular'}</td>
                        {admin && <td className="space-x-2 px-3 py-1.5"><button type="button" onClick={() => abrirEdicion('personal', { ...trabajador, id_usuario_sistema: trabajador.id_usuario_sistema || '' }, trabajador.id_trabajador)} className="font-bold text-blue-700">Editar</button><button type="button" onClick={() => desactivar('personal', trabajador)} className="font-bold text-red-700">Eliminar</button></td>}
                      </tr>
                    ))}
                    {!personal.length && <tr><td colSpan={admin ? 6 : 5} className="p-6 text-center text-slate-500">No hay personal registrado.</td></tr>}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {pestana === 'finanzas' && (
            <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-extrabold text-slate-800">Cuentas y Centros de Costo</h2><p className="text-slate-500">Plan contable, centros operativos y unidades de negocio.</p></div>{admin && <button type="button" onClick={() => abrirNuevo('financiero', FORMULARIO_FINANCIERO)} className="rounded bg-emerald-700 px-3 py-2 font-bold text-white hover:bg-emerald-800">＋ Nuevo elemento</button>}</div>
              <div className="grid gap-3 lg:grid-cols-3">
                {[
                  { tipo: 'CUENTA_CONTABLE', titulo: 'Cuentas Contables', elementos: cuentasContables, color: 'border-emerald-200' },
                  { tipo: 'CENTRO_COSTO', titulo: 'Centros de Costo', elementos: centrosCosto, color: 'border-amber-200' },
                  { tipo: 'UNIDAD_NEGOCIO', titulo: 'Unidades de Negocio', elementos: unidadesNegocio, color: 'border-purple-200' }
                ].map((grupo) => (
                  <article key={grupo.tipo} className={`rounded-lg border ${grupo.color}`}>
                    <h3 className="border-b border-slate-200 bg-slate-50 px-3 py-2 font-extrabold">{grupo.titulo} <span className="text-slate-400">({grupo.elementos.length})</span></h3>
                    <div className="max-h-[55vh] divide-y divide-slate-100 overflow-y-auto">
                      {grupo.elementos.map((item) => (
                        <div key={item.id_elemento} className="flex items-start justify-between gap-2 px-3 py-2">
                          <div><strong className="font-mono text-slate-800">{item.codigo}</strong><p className="text-slate-600">{item.nombre}</p>{item.cuenta_padre && <p className="text-[10px] text-slate-400">Cuenta superior: {item.cuenta_padre}</p>}</div>
                          {admin && <div className="shrink-0 space-x-2"><button type="button" onClick={() => abrirEdicion('financiero', item, item.id_elemento)} className="font-bold text-blue-700">Editar</button>{item.activo && <button type="button" onClick={() => desactivar('financiero', item)} className="font-bold text-red-700">×</button>}</div>}
                        </div>
                      ))}
                      {!grupo.elementos.length && <p className="p-4 text-center text-slate-400">Sin registros.</p>}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {pestana === 'catalogos' && (
            <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-extrabold text-slate-800">Catálogos Base</h2><p className="text-slate-500">Unidades de medida y categorías comunes del catálogo de insumos.</p></div>{puedeGestionarCatalogo && <button type="button" onClick={() => abrirNuevo(subpestanaCatalogo === 'categorias' ? 'categoria' : 'unidad', subpestanaCatalogo === 'categorias' ? FORMULARIO_CATEGORIA : FORMULARIO_UNIDAD)} className="rounded bg-emerald-700 px-3 py-2 font-bold text-white hover:bg-emerald-800">＋ Nuevo registro</button>}</div>
              <div className="flex gap-1 border-b border-slate-200">
                <button type="button" onClick={() => setSubpestanaCatalogo('categorias')} className={`px-3 py-2 font-bold ${subpestanaCatalogo === 'categorias' ? 'border-b-2 border-emerald-600 text-emerald-800' : 'text-slate-500'}`}>Categorías de Insumos</button>
                <button type="button" onClick={() => setSubpestanaCatalogo('unidades')} className={`px-3 py-2 font-bold ${subpestanaCatalogo === 'unidades' ? 'border-b-2 border-emerald-600 text-emerald-800' : 'text-slate-500'}`}>Unidades de Medida</button>
              </div>
              {subpestanaCatalogo === 'categorias' ? (
                <div className="overflow-x-auto rounded border border-slate-200"><table className="w-full border-collapse text-left"><thead className="bg-slate-100 text-[10px] uppercase text-slate-600"><tr><th className="px-3 py-2">Código</th><th className="px-3 py-2">Categoría</th><th className="px-3 py-2">Descripción</th>{puedeGestionarCatalogo && <th className="px-3 py-2">Acciones</th>}</tr></thead><tbody className="divide-y divide-slate-100">{categorias.map((categoria) => <tr key={categoria.id_categoria}><td className="px-3 py-1.5 font-mono font-bold">{categoria.codigo}</td><td className="px-3 py-1.5">{categoria.icono} {categoria.nombre}</td><td className="px-3 py-1.5 text-slate-500">{categoria.descripcion || '—'}</td>{puedeGestionarCatalogo && <td className="space-x-2 px-3 py-1.5"><button type="button" onClick={() => abrirEdicion('categoria', categoria, categoria.id_categoria)} className="font-bold text-blue-700">Editar</button><button type="button" onClick={() => desactivar('categoria', categoria)} className="font-bold text-red-700">Eliminar</button></td>}</tr>)}{!categorias.length && <tr><td colSpan={puedeGestionarCatalogo ? 4 : 3} className="p-5 text-center text-slate-500">No hay categorías configuradas.</td></tr>}</tbody></table></div>
              ) : (
                <div className="overflow-x-auto rounded border border-slate-200"><table className="w-full border-collapse text-left"><thead className="bg-slate-100 text-[10px] uppercase text-slate-600"><tr><th className="px-3 py-2">Código</th><th className="px-3 py-2">Unidad</th><th className="px-3 py-2">Símbolo</th><th className="px-3 py-2">Estado</th>{admin && <th className="px-3 py-2">Acciones</th>}</tr></thead><tbody className="divide-y divide-slate-100">{unidades.map((unidad) => <tr key={unidad.id_unidad}><td className="px-3 py-1.5 font-mono font-bold">{unidad.codigo}</td><td className="px-3 py-1.5">{unidad.nombre}</td><td className="px-3 py-1.5">{unidad.simbolo}</td><td className="px-3 py-1.5"><span className={`rounded px-2 py-0.5 font-bold ${iconoEstado(unidad.activo)}`}>{unidad.activo ? 'ACTIVA' : 'INACTIVA'}</span></td>{admin && <td className="space-x-2 px-3 py-1.5"><button type="button" onClick={() => abrirEdicion('unidad', unidad, unidad.id_unidad)} className="font-bold text-blue-700">Editar</button>{unidad.activo && <button type="button" onClick={() => desactivar('unidad', unidad)} className="font-bold text-red-700">Desactivar</button>}</td>}</tr>)}{!unidades.length && <tr><td colSpan={admin ? 5 : 4} className="p-5 text-center text-slate-500">No hay unidades configuradas.</td></tr>}</tbody></table></div>
              )}
            </section>
          )}
        </>
      )}

      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <form onSubmit={guardar} className="max-h-[90vh] w-full max-w-2xl space-y-4 overflow-y-auto rounded-xl border-t-4 border-emerald-600 bg-white p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2">
              <h2 className="font-extrabold text-slate-900">{modal.id ? 'Editar' : 'Crear'} {({ socio: 'Socio de Negocio', personal: 'Trabajador', financiero: 'Elemento Financiero', categoria: 'Categoría de Insumos', unidad: 'Unidad de Medida' })[modal.tipo]}</h2>
              <button type="button" onClick={() => setModal(null)} aria-label="Cerrar formulario" className="text-xl font-bold text-slate-400 hover:text-slate-700">×</button>
            </div>
            {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-red-800">{error}</p>}
            {modal.tipo === 'socio' && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Campo etiqueta="NIT / Cédula *"><Entrada required minLength={5} maxLength={30} value={formulario.nit_cedula || ''} onChange={(e) => cambiar('nit_cedula', e.target.value)} /></Campo>
                <Campo etiqueta="Razón social *"><Entrada required minLength={2} maxLength={200} value={formulario.razon_social || ''} onChange={(e) => cambiar('razon_social', e.target.value)} /></Campo>
                <Campo etiqueta="Correo electrónico"><Entrada type="email" value={formulario.email || ''} onChange={(e) => cambiar('email', e.target.value)} /></Campo>
                <Campo etiqueta="Teléfono"><Entrada value={formulario.telefono || ''} onChange={(e) => cambiar('telefono', e.target.value)} /></Campo>
                <Campo etiqueta="Dirección"><Entrada value={formulario.direccion || ''} onChange={(e) => cambiar('direccion', e.target.value)} /></Campo>
                <Campo etiqueta="Condiciones de pago (días)"><Entrada type="number" min="0" max="365" value={formulario.condiciones_pago_dias ?? 30} onChange={(e) => cambiar('condiciones_pago_dias', e.target.value)} /></Campo>
                <div className="flex gap-4 sm:col-span-2"><label className="flex items-center gap-2 font-bold"><input type="checkbox" checked={Boolean(formulario.es_cliente)} onChange={(e) => cambiar('es_cliente', e.target.checked)} /> Cliente</label><label className="flex items-center gap-2 font-bold"><input type="checkbox" checked={Boolean(formulario.es_proveedor)} onChange={(e) => cambiar('es_proveedor', e.target.checked)} /> Proveedor</label></div>
                {formulario.es_cliente && <Campo etiqueta="Cuenta contable por cobrar *"><Entrada required value={formulario.cuenta_contable_por_cobrar || ''} onChange={(e) => cambiar('cuenta_contable_por_cobrar', e.target.value)} placeholder="Código y nombre de cuenta" /></Campo>}
                {formulario.es_proveedor && <Campo etiqueta="Cuenta contable por pagar *"><Entrada required value={formulario.cuenta_contable_por_pagar || ''} onChange={(e) => cambiar('cuenta_contable_por_pagar', e.target.value)} placeholder="Código y nombre de cuenta" /></Campo>}
                {modal.id && <label className="flex items-center gap-2 font-bold"><input type="checkbox" checked={Boolean(formulario.estado_activo)} onChange={(e) => cambiar('estado_activo', e.target.checked)} /> Socio activo</label>}
              </div>
            )}
            {modal.tipo === 'personal' && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Campo etiqueta="Cédula *"><Entrada required minLength={5} value={formulario.cedula || ''} onChange={(e) => cambiar('cedula', e.target.value)} /></Campo>
                <Campo etiqueta="Nombre completo *"><Entrada required minLength={2} value={formulario.nombre_completo || ''} onChange={(e) => cambiar('nombre_completo', e.target.value)} /></Campo>
                <Campo etiqueta="Área"><Select value={formulario.area || 'PRODUCCION'} onChange={(e) => cambiar('area', e.target.value)}>{Object.entries(ETIQUETAS_AREA).map(([area, etiqueta]) => <option key={area} value={area}>{etiqueta}</option>)}</Select></Campo>
                <Campo etiqueta="Cargo *"><Entrada required value={formulario.cargo || ''} onChange={(e) => cambiar('cargo', e.target.value)} /></Campo>
                <Campo etiqueta="Tarifa por hora (COP)"><Entrada type="number" min="0" step="0.0001" value={formulario.tarifa_hora_mano_obra ?? 0} onChange={(e) => cambiar('tarifa_hora_mano_obra', e.target.value)} /></Campo>
                <Campo etiqueta="Usuario de sistema"><Select value={formulario.id_usuario_sistema || ''} onChange={(e) => cambiar('id_usuario_sistema', e.target.value)}><option value="">Sin vincular</option>{usuarios.map((cuenta) => <option key={cuenta.id_usuario} value={cuenta.id_usuario}>{cuenta.nombre} · {cuenta.email}</option>)}{formulario.id_usuario_sistema && !usuarios.some((u) => u.id_usuario === formulario.id_usuario_sistema) && <option value={formulario.id_usuario_sistema}>{formulario.usuario || 'Vínculo actual'}</option>}</Select></Campo>
              </div>
            )}
            {modal.tipo === 'financiero' && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Campo etiqueta="Tipo de elemento"><Select value={formulario.tipo || 'CUENTA_CONTABLE'} onChange={(e) => cambiar('tipo', e.target.value)}>{[['CUENTA_CONTABLE', 'Cuenta contable'], ['CENTRO_COSTO', 'Centro de costo'], ['UNIDAD_NEGOCIO', 'Unidad de negocio']].map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}</Select></Campo>
                <Campo etiqueta="Código único *"><Entrada required value={formulario.codigo || ''} onChange={(e) => cambiar('codigo', e.target.value)} /></Campo>
                <Campo etiqueta="Nombre *"><Entrada required value={formulario.nombre || ''} onChange={(e) => cambiar('nombre', e.target.value)} /></Campo>
                {formulario.tipo === 'CUENTA_CONTABLE' && <Campo etiqueta="Cuenta padre"><Select value={formulario.cuenta_padre || ''} onChange={(e) => cambiar('cuenta_padre', e.target.value)}><option value="">Sin cuenta superior</option>{cuentasContables.filter((cuenta) => cuenta.id_elemento !== modal.id).map((cuenta) => <option key={cuenta.id_elemento} value={cuenta.codigo}>{cuenta.codigo} · {cuenta.nombre}</option>)}</Select></Campo>}
                <Campo etiqueta="Descripción"><textarea rows="3" value={formulario.descripcion || ''} onChange={(e) => cambiar('descripcion', e.target.value)} className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-xs font-normal outline-none focus:border-emerald-500" /></Campo>
                {modal.id && <label className="flex items-center gap-2 font-bold"><input type="checkbox" checked={Boolean(formulario.activo)} onChange={(e) => cambiar('activo', e.target.checked)} /> Elemento activo</label>}
              </div>
            )}
            {modal.tipo === 'categoria' && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Campo etiqueta="Código *"><Entrada required value={formulario.codigo || ''} onChange={(e) => cambiar('codigo', e.target.value)} /></Campo>
                <Campo etiqueta="Nombre *"><Entrada required value={formulario.nombre || ''} onChange={(e) => cambiar('nombre', e.target.value)} /></Campo>
                <Campo etiqueta="Icono"><Entrada value={formulario.icono || '📦'} onChange={(e) => cambiar('icono', e.target.value)} /></Campo>
                <Campo etiqueta="Descripción"><Entrada value={formulario.descripcion || ''} onChange={(e) => cambiar('descripcion', e.target.value)} /></Campo>
              </div>
            )}
            {modal.tipo === 'unidad' && (
              <div className="grid gap-3 sm:grid-cols-2">
                <Campo etiqueta="Código *"><Entrada required value={formulario.codigo || ''} onChange={(e) => cambiar('codigo', e.target.value)} /></Campo>
                <Campo etiqueta="Nombre *"><Entrada required value={formulario.nombre || ''} onChange={(e) => cambiar('nombre', e.target.value)} /></Campo>
                <Campo etiqueta="Símbolo *"><Entrada required value={formulario.simbolo || ''} onChange={(e) => cambiar('simbolo', e.target.value)} /></Campo>
                {modal.id && <label className="flex items-center gap-2 font-bold"><input type="checkbox" checked={Boolean(formulario.activo)} onChange={(e) => cambiar('activo', e.target.checked)} /> Unidad activa</label>}
              </div>
            )}
            <div className="flex justify-end gap-2 border-t border-slate-200 pt-3">
              <button type="button" onClick={() => setModal(null)} className="rounded border border-slate-300 px-4 py-2 font-bold text-slate-600 hover:bg-slate-50">Cancelar</button>
              <button type="submit" disabled={guardando} className="rounded bg-emerald-700 px-4 py-2 font-bold text-white hover:bg-emerald-800 disabled:opacity-50">{guardando ? 'Guardando…' : 'Guardar'}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
