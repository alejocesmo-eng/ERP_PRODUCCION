// src/views/nivel2/ProyectosView.jsx
import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import { useProyectos } from '../../context/ProyectosContext';
import ModalNuevaCotizacion from '../../components/modals/ModalNuevaCotizacion';
import HistorialTimelineModal from '../../components/modals/HistorialTimelineModal';

const capitalize = (str) => {
  if (typeof str !== 'string' || !str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
};

const ETIQUETAS_TIPO_MATERIAL = {
  ROH: 'Materia Prima Directa',
  HALB: 'Producto Semielaborado',
  FERT: 'Producto Terminado',
  VERB: 'Consumible de Planta',
  ERSA: 'Repuesto de Mantenimiento',
};

const ETIQUETAS_ACCION_PIEZA = {
  FABRICAR_NUEVA: 'Fabricar nueva',
  RECTIFICAR_RECUPERAR: 'Rectificar o recuperar',
  COMPRA_DIRECTA_BOM: 'Compra directa de materiales',
};

const CATEGORIAS_PRESUPUESTO = [
  { valor: 'MATERIA_PRIMA', etiqueta: 'Materia prima directa' },
  { valor: 'HORAS_MES', etiqueta: 'Horas MES' },
  { valor: 'SERVICIO_EXTERNO', etiqueta: 'Servicio externo' },
];

const PLACEHOLDERS_REFERENCIA_PRESUPUESTO = {
  MATERIA_PRIMA: 'Código de material / SKU',
  HORAS_MES: 'Código de centro|SETUP o MECANIZADO',
  SERVICIO_EXTERNO: 'Proveedor|Descripción del servicio',
};

export default function ProyectosView() {
  const { proyectos: proyectosGlobal } = useProyectos();

  const [usuarioActual, setUsuarioActual] = useState(null);
  const [pestañaModulo, setPestañaModulo] = useState('pedidos');

  const [piezasExpandidas, setPiezasExpandidas] = useState({});
  const [piezasProyectoMap, setPiezasProyectoMap] = useState({});
  const [cargandoPiezasMap, setCargandoPiezasMap] = useState({});

  const [proyectos, setProyectos] = useState([]);
  const [cotizaciones, setCotizaciones] = useState([]);
  const [solicitudesCompra, setSolicitudesCompra] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });
  const [busqueda, setBusqueda] = useState('');
  
  const [filtroEstado, setFiltroEstado] = useState('TODOS');

  const [modalDetalleAbierto, setModalDetalleAbierto] = useState(false);
  const [proyectoSeleccionado, setProyectoSeleccionado] = useState(null);
  const [esEdicion, setEsEdicion] = useState(false);
  const [expedienteCargando, setExpedienteCargando] = useState(false);
  const [expedienteError, setExpedienteError] = useState('');

  const [modalNuevoPedidoAbierto, setModalNuevoPedidoAbierto] = useState(false);
  const [modalNuevoCotizacionAbierto, setModalNuevoCotizacionAbierto] = useState(false);
  const [modalBomAbierto, setModalBomAbierto] = useState(false);
  const [bomSeleccionado, setBomSeleccionado] = useState(null);

  // ESTADO PARA VISOR, DESCARGA E IMPRESIÓN DE COTIZACIÓN
  const [modalVisorCotizacionAbierto, setModalVisorCotizacionAbierto] = useState(false);
  const [cotizacionDetalle, setCotizacionDetalle] = useState(null);
  const [mostrarModalEmail, setMostrarModalEmail] = useState(false);
  const [emailDestino, setEmailDestino] = useState('');
  const [asuntoEmail, setAsuntoEmail] = useState('');
  const [mensajeEmail, setMensajeEmail] = useState('');
  const [enviandoEmail, setEnviandoEmail] = useState(false);

  // ESTADO PARA EL MODAL DE HISTORIAL Y TRAZABILIDAD
  const [modalHistorial, setModalHistorial] = useState({
    abierto: false,
    tipoEntidad: 'PEDIDO',
    identificador: '',
    tituloDoc: ''
  });

  const [nuevoPedido, setNuevoPedido] = useState({
    numero_pedido: '',
    cliente_nombre: '',
    contacto_nombre: '',
    contacto_telefono: '',
    contacto_email: '',
    ubicacion_cliente: '',
    fecha_compromiso: '',
    requisitos_cliente: '',
    detalles: [
      { id: 1, codigo_producto: '', descripcion: '', tipo: 'pieza', cantidad_solicitada: 1, unidad: 'UND', prioridad: 'MEDIA', fecha_compromiso: '', requisitos_especificos: '', observaciones: '' }
    ]
  });

  const [listaMantenimientos, setListaMantenimientos] = useState([]);
  const [mantenimientoSeleccionado, setMantenimientoSeleccionado] = useState(null);
  
  const [modalNuevoMantenimientoAbierto, setModalNuevoMantenimientoAbierto] = useState(false);
  const [modalLevantamientoAbierto, setModalLevantamientoAbierto] = useState(false);

  const [formMantenimiento, setFormMantenimiento] = useState({
    codigo_mantenimiento: 'MANT-2026-010',
    cliente_nombre: '',
    codigo_op: '',
    nombre_maquina: '',
    marca_modelo: '',
    serie_maquina: '',
    observaciones_ingreso: ''
  });

  const [piezasLevantamiento, setPiezasLevantamiento] = useState([]);
  const [nuevaPiezaTemp, setNuevaPiezaTemp] = useState({
    codigo: '',
    descripcion: '',
    accion: 'FABRICAR_NUEVA',
    cantidad: 1,
    material: 'AISI 1045',
    cotizado: 0
  });

  const ETAPAS_SGI = [
    { paso: 1, id: 'RECEPCION_REGISTRO', nombre: '1. Recepción & Registro', area: 'Ventas', accion: '📋 1. Confirmar Pedido' },
    { paso: 2, id: 'LAVADO_DESARME', nombre: '2. Lavado & Desarme', area: 'Producción', accion: '🧽 2. Validar Desarme' },
    { paso: 3, id: 'DIAGNOSTICO_DISENO', nombre: '3. Levantamiento & Diagnóstico', area: 'Diseño', accion: '📐 3. Completar Levantamiento' },
    { paso: 4, id: 'COTIZACION_APROBACION', nombre: '4. Cotización & Aprobación', area: 'Ventas', accion: '💰 4. Aprobar Cotización' },
    { paso: 5, id: 'PLANOS_BOM', nombre: '5. Planos y lista de materiales (apertura de órdenes)', area: 'Diseño', accion: '⚙️ 5. Estructurar órdenes y planos' },
    { paso: 6, id: 'COMPRAS_INSUMOS', nombre: '6. Compra de insumos', area: 'Compras', accion: '🛒 6. Abastecimiento de materiales' },
    { paso: 7, id: 'EN_FABRICACION', nombre: '7. Fabricación / Recuperación', area: 'Producción', accion: '🏭 7. Liberar a producción' },
    { paso: 8, id: 'KIT_COMPLETO', nombre: '8. Ensamble & Pruebas', area: 'Producción', accion: '🏁 8. Aprobar Ensamble & Cierre' }
  ];

  useEffect(() => {
    obtenerUsuarioSesion();
    cargarProyectos();
    cargarMantenimientos();
  }, []);

  const obtenerUsuarioSesion = () => {
    try {
      const userStored = localStorage.getItem('usuario') || localStorage.getItem('user');
      if (userStored) {
        setUsuarioActual(JSON.parse(userStored));
      } else {
        setUsuarioActual({ rol: 'Jefe de área', area: 'Ventas', nombre: 'Ing. Área Ventas' });
      }
    } catch (e) {
      setUsuarioActual({ rol: 'Administrador', area: 'General' });
    }
  };

  const cargarProyectos = async () => {
    try {
      setLoading(true);
      const [resProyectos, resSolicitudes, resCotizaciones] = await Promise.allSettled([
        API.get('/proyectos/'),
        API.get('/solicitudes-compra/'),
        API.get('/ventas/cotizaciones/')
      ]);
      const proys = resProyectos.status === 'fulfilled' && Array.isArray(resProyectos.value.data) ? resProyectos.value.data : [];
      const solics = resSolicitudes.status === 'fulfilled' && Array.isArray(resSolicitudes.value.data) ? resSolicitudes.value.data : [];

      let cots = [];
      if (resCotizaciones.status === 'fulfilled') {
        if (Array.isArray(resCotizaciones.value.data)) {
          cots = resCotizaciones.value.data;
        } else if (resCotizaciones.value.data && Array.isArray(resCotizaciones.value.data.items)) {
          cots = resCotizaciones.value.data.items;
        }
      }

      setProyectos(proys);
      setSolicitudesCompra(solics);
      setCotizaciones(cots);
      await cargarMantenimientos(proys);
    } catch (error) {
      console.error("Error al cargar proyectos:", error);
    } finally {
      setLoading(false);
    }
  };

  const cargarMantenimientos = async (proyectosActuales = null) => {
    try {
      const res = await API.get('/mantenimientos/monitor-kits');
      const listaMant = Array.isArray(res.data) ? res.data : [];
      const listaProyectos = proyectosActuales || proyectos || [];
      const mapeo = [...listaMant];

      listaProyectos.forEach(p => {
        const yaExiste = mapeo.some(m => m.id_mantenimiento === p.id_proyecto || m.codigo_mantenimiento === p.numero_pedido);
        if (!yaExiste && (p.tipo_proyecto === 'MANTENIMIENTO' || p.numero_pedido?.includes('MANT') || p.codigo_proyecto?.includes('MANT'))) {
          mapeo.push({
            id_mantenimiento: p.id_proyecto,
            id_proyecto: p.id_proyecto,
            codigo_mantenimiento: p.numero_pedido,
            cliente_nombre: p.cliente_nombre,
            nombre_maquina: p.detalle_producto || 'Equipo General',
            codigo_op: p.codigo_proyecto || 'OP-100',
            fase_mantenimiento: p.fase_mantenimiento || 'LAVADO_DESARME',
            piezas: p.detalles || []
          });
        }
      });

      setListaMantenimientos(mapeo);
    } catch (error) {
      console.warn("No se pudieron cargar mantenimientos desde el servidor:", error);
      setListaMantenimientos([]);
    }
  };

  const handleAbrirVisorCotizacion = async (cot) => {
    try {
      setLoading(true);
      const res = await API.get(`/ventas/cotizaciones/${cot.id_cotizacion}`);
      setCotizacionDetalle(res.data);
      setEmailDestino(res.data.cliente?.email || '');
      setAsuntoEmail(`Cotización Comercial ${res.data.numero_cotizacion} - HD Precision & Technology`);
      setMensajeEmail(`Estimado/a cliente,\n\nAdjuntamos la cotización comercial formal ${res.data.numero_cotizacion} para su revisión y aprobación.\n\nQuedamos atentos a cualquier inquietud técnica o comercial.`);
    } catch (e) {
      setCotizacionDetalle({
        id_cotizacion: cot.id_cotizacion,
        numero_cotizacion: cot.numero_cotizacion,
        fecha_emision: cot.fecha_emision,
        valor_total: cot.valor_total,
        estado: cot.estado,
        cliente: {
          razon_social: cot.id_socio || 'Cliente Comercial',
          email: '',
          direccion: 'Planta Principal',
          condiciones_pago: '30 Días'
        },
        posiciones: []
      });
      setEmailDestino('');
      setAsuntoEmail(`Cotización ${cot.numero_cotizacion}`);
      setMensajeEmail('Adjuntamos cotización formal.');
    } finally {
      setLoading(false);
      setMostrarModalEmail(false);
      setModalVisorCotizacionAbierto(true);
    }
  };

  const handleEnviarCotizacionPorCorreo = async (e) => {
    e.preventDefault();
    if (!emailDestino.trim()) {
      alert("Por favor ingrese el correo electrónico de destino.");
      return;
    }
    setEnviandoEmail(true);
    try {
      await API.post(`/ventas/cotizaciones/${cotizacionDetalle.id_cotizacion}/enviar-cliente`, {
        destinatario: emailDestino,
        asunto: asuntoEmail,
        mensaje: mensajeEmail
      });
      setMensaje({ tipo: 'exito', texto: `✅ Cotización enviada exitosamente a ${emailDestino}.` });
      setMostrarModalEmail(false);
      await cargarProyectos();
    } catch (err) {
      setMensaje({ tipo: 'error', texto: 'No fue posible registrar el envío por correo electrónico.' });
    } finally {
      setEnviandoEmail(false);
    }
  };

  const esAreaAutorizadaParaPaso = (areaRequerida) => {
    if (!usuarioActual) return true;
    const rol = (usuarioActual.rol || '').toLowerCase();
    const area = (usuarioActual.area || '').toLowerCase();

    if (rol.includes('admin') || rol.includes('administrador')) return true;

    const areaReqLower = areaRequerida.toLowerCase();
    return area.includes(areaReqLower) || areaReqLower.includes(area);
  };

  const handleAvanzarPuertaPasoSGI = async (proyecto) => {
    setMensaje({ tipo: '', texto: '' });
    const faseActualStr = proyecto.fase_mantenimiento || 'LAVADO_DESARME';
    const etapaObjActual = ETAPAS_SGI.find(e => e.id === faseActualStr) || ETAPAS_SGI[1];
    const pasoActualIdx = etapaObjActual.paso;

    if (!esAreaAutorizadaParaPaso(etapaObjActual.area)) {
      alert(`⛔ Permiso Denegado: La aprobación de la Etapa ${pasoActualIdx} (${etapaObjActual.nombre}) debe ser realizada por el área de [${etapaObjActual.area.toUpperCase()}]. Tu usuario actual es de [${(usuarioActual?.area || 'Sin Área').toUpperCase()}].`);
      return;
    }

    if (pasoActualIdx >= 8) {
      setMensaje({ tipo: 'exito', texto: `✅ El proyecto [${proyecto.codigo_mantenimiento || proyecto.numero_pedido}] ya ha completado todas las 8 etapas del SGI.` });
      return;
    }

    const SiguienteEtapa = ETAPAS_SGI.find(e => e.paso === pasoActualIdx + 1);
    if (!SiguienteEtapa) return;

    try {
      setLoading(true);
      const idTarget = proyecto.id_mantenimiento || proyecto.id_proyecto;
      await API.patch(`/mantenimientos/${idTarget}`, { fase_mantenimiento: SiguienteEtapa.id });

      setMensaje({
        tipo: 'exito',
        texto: `✅ Puerta de Paso aprobada con éxito: [${proyecto.codigo_mantenimiento || proyecto.numero_pedido}] avanzó a Etapa ${SiguienteEtapa.paso} (${SiguienteEtapa.nombre}).`
      });

      await cargarMantenimientos();
    } catch (err) {
      setListaMantenimientos(prev => prev.map(m => {
        if ((m.id_proyecto || m.id_mantenimiento) === (proyecto.id_proyecto || proyecto.id_mantenimiento)) {
          return { ...m, fase_mantenimiento: SiguienteEtapa.id };
        }
        return m;
      }));

      setMensaje({
        tipo: 'exito',
        texto: `✅ Puerta de Paso aprobada: [${proyecto.codigo_mantenimiento || proyecto.numero_pedido}] avanzó a ${SiguienteEtapa.nombre}.`
      });
    } finally {
      setLoading(false);
    }
  };

  const togglePiezasProyecto = async (id, proyecto) => {
    const estaAbierto = !!piezasExpandidas[id];

    if (!estaAbierto) {
      setCargandoPiezasMap(prev => ({ ...prev, [id]: true }));
      try {
        const idConsulta = proyecto.id_mantenimiento || proyecto.id_proyecto || id;
        const res = await API.get(`/mantenimientos/${idConsulta}/piezas`);
        
        let piezasNormalizadas = [];
        if (Array.isArray(res.data) && res.data.length > 0) {
          piezasNormalizadas = res.data.map((p, idx) => ({
            codigo: p.codigo_pieza_plano || p.codigo || `PLN-${idx + 1}`,
            descripcion: p.descripcion_pieza || p.descripcion || 'Pieza Mecanizada',
            accion: p.accion_requerida || p.accion || 'FABRICAR_NUEVA',
            cantidad: p.cantidad_requerida || p.cantidad || 1,
            material: p.material_especificado || p.material || 'AISI 1045',
            autorizado: p.autorizado_cliente ?? p.autorizado ?? true
          }));
        } else {
          piezasNormalizadas = proyecto.piezas || proyecto.detalles || [];
        }

        setPiezasProyectoMap(prev => ({ ...prev, [id]: piezasNormalizadas }));
      } catch (err) {
        setPiezasProyectoMap(prev => ({ ...prev, [id]: proyecto.piezas || proyecto.detalles || [] }));
      } finally {
        setCargandoPiezasMap(prev => ({ ...prev, [id]: false }));
      }
    }

    setPiezasExpandidas(prev => ({ ...prev, [id]: !estaAbierto }));
  };

  const handleVerDetalleBom = (pieza, planoPadre) => {
    const solAsociada = solicitudesCompra.find(
      s => s.codigo_op === (pieza.codigo_op || planoPadre?.codigo_op) && 
           s.codigo_plano === (pieza.codigo_plano || pieza.codigo || planoPadre?.codigo_plano)
    );

    setBomSeleccionado({
      codigo_op: pieza.codigo_op || planoPadre?.codigo_op || 'OP-100',
      codigo_plano: pieza.codigo_plano || pieza.codigo || planoPadre?.codigo_plano || 'PLN-001',
      detalle_pieza: pieza.detalle_pieza || pieza.descripcion || planoPadre?.detalle_pieza || 'Pieza Mecanizada',
      material_requerido: pieza.material_requerido || pieza.material || planoPadre?.material_requerido || 'Sin especificar',
      solicitud: solAsociada || null,
      estado_bom: solAsociada?.estado_bom || (solAsociada ? 'SOLICITADO' : 'SIN_SOLICITAR')
    });
    setModalBomAbierto(true);
  };

  const renderBadgeBom = (estadoBom) => {
    switch (estadoBom) {
      case 'ENTREGADO':
        return <span className="px-2 py-1 rounded text-[10px] font-extrabold bg-emerald-100 text-emerald-800 border border-emerald-300">🟢 ENTREGADO A PLANTA</span>;
      case 'EN_ALMACEN':
        return <span className="px-2 py-1 rounded text-[10px] font-extrabold bg-purple-100 text-purple-900 border border-purple-300">🟣 EN ALMACÉN</span>;
      case 'EN_COMPRA':
        return <span className="px-2 py-1 rounded text-[10px] font-extrabold bg-blue-100 text-blue-900 border border-blue-300">🔵 EN COMPRA</span>;
      case 'SOLICITADO':
        return <span className="px-2 py-1 rounded text-[10px] font-extrabold bg-amber-100 text-amber-900 border border-amber-300">🟡 SOLICITADO</span>;
      default:
        return <span className="px-2 py-1 rounded text-[10px] font-extrabold bg-slate-100 text-slate-600 border border-slate-300">⚪ SIN SOLICITAR</span>;
    }
  };

  const handleAbrirHistorial = (pedido) => {
    setModalHistorial({
      abierto: true,
      tipoEntidad: 'PEDIDO',
      identificador: pedido.numero_pedido || pedido.codigo_proyecto,
      tituloDoc: `${pedido.numero_pedido || 'PED'} - ${pedido.cliente_nombre || 'Cliente'}`
    });
  };

  const handleAgregarFilaDetalle = () => {
    setNuevoPedido(prev => ({
      ...prev,
      detalles: [
        ...prev.detalles,
        { id: Date.now(), codigo_producto: '', descripcion: '', tipo: 'pieza', cantidad_solicitada: 1, unidad: 'UND', prioridad: 'MEDIA', fecha_compromiso: prev.fecha_compromiso || '', requisitos_especificos: '', observaciones: '' }
      ]
    }));
  };

  const handleEliminarFilaDetalle = (id) => {
    if (nuevoPedido.detalles.length === 1) {
      alert("El pedido comercial debe tener al menos una pieza, servicio o trabajo registrado.");
      return;
    }
    setNuevoPedido(prev => ({
      ...prev,
      detalles: prev.detalles.filter(item => item.id !== id)
    }));
  };

  const handleCambioDetalle = (id, campo, valor) => {
    const valorProcesado = (typeof valor === 'string' && campo !== 'codigo_producto' && campo !== 'contacto_email')
      ? capitalize(valor)
      : valor;

    setNuevoPedido(prev => ({
      ...prev,
      detalles: prev.detalles.map(item =>
        item.id === id ? { ...item, [campo]: valorProcesado } : item
      )
    }));
  };

  const handleAgregarFilaEdicion = () => {
    setProyectoSeleccionado(prev => ({
      ...prev,
      detalles: [
        ...(prev.detalles || []),
        { id: Date.now(), codigo_producto: '', descripcion: '', tipo: 'pieza', cantidad_solicitada: 1, unidad: 'UND', prioridad: 'MEDIA', fecha_compromiso: prev.fecha_compromiso || '', requisitos_especificos: '', observaciones: '' }
      ]
    }));
  };

  const handleEliminarFilaEdicion = (idxEliminar) => {
    if (proyectoSeleccionado.detalles && proyectoSeleccionado.detalles.length === 1) {
      alert("El pedido comercial debe tener al menos un ítem registrado.");
      return;
    }
    setProyectoSeleccionado(prev => ({
      ...prev,
      detalles: prev.detalles.filter((_, idx) => idx !== idxEliminar)
    }));
  };

  const handleCambioDetalleEdicion = (index, campo, valor) => {
    const valorProcesado = (typeof valor === 'string' && campo !== 'codigo_producto' && campo !== 'contacto_email') 
      ? capitalize(valor) 
      : valor;

    setProyectoSeleccionado(prev => {
      const nuevosDetalles = [...(prev.detalles || [])];
      nuevosDetalles[index] = { ...nuevosDetalles[index], [campo]: valorProcesado };
      return { ...prev, detalles: nuevosDetalles };
    });
  };

  const handleAgregarPresupuestoComponente = () => {
    setProyectoSeleccionado(prev => ({
      ...prev,
      presupuestos_componentes: [
        ...(prev.presupuestos_componentes || []),
        {
          categoria: 'MATERIA_PRIMA',
          referencia: '',
          monto_presupuestado: ''
        }
      ]
    }));
  };

  const handleCambioPresupuestoComponente = (indice, campo, valor) => {
    setProyectoSeleccionado(prev => {
      const presupuestos = [...(prev.presupuestos_componentes || [])];
      presupuestos[indice] = { ...presupuestos[indice], [campo]: valor };
      return { ...prev, presupuestos_componentes: presupuestos };
    });
  };

  const handleEliminarPresupuestoComponente = (indiceEliminar) => {
    setProyectoSeleccionado(prev => ({
      ...prev,
      presupuestos_componentes: (prev.presupuestos_componentes || [])
        .filter((_, indice) => indice !== indiceEliminar)
    }));
  };

  const handleCrearNuevoPedido = async (e) => {
    e.preventDefault();
    setMensaje({ tipo: '', texto: '' });

    const payloadSanitizado = {
      numero_pedido: (nuevoPedido.numero_pedido || '').trim(),
      cliente_nombre: (nuevoPedido.cliente_nombre || '').trim(),
      contacto_nombre: nuevoPedido.contacto_nombre ? nuevoPedido.contacto_nombre.trim() : null,
      contacto_telefono: nuevoPedido.contacto_telefono ? nuevoPedido.contacto_telefono.trim() : null,
      contacto_email: nuevoPedido.contacto_email ? nuevoPedido.contacto_email.trim() : null,
      ubicacion_cliente: nuevoPedido.ubicacion_cliente ? nuevoPedido.ubicacion_cliente.trim() : null,
      fecha_compromiso: nuevoPedido.fecha_compromiso ? nuevoPedido.fecha_compromiso : null,
      requisitos_cliente: nuevoPedido.requisitos_cliente ? nuevoPedido.requisitos_cliente.trim() : null,
      detalles: (nuevoPedido.detalles || []).map(d => ({
        codigo_producto: d.codigo_producto ? d.codigo_producto.trim() : `PROD-${Date.now().toString().slice(-4)}`,
        descripcion: (d.descripcion || '').trim(),
        tipo: d.tipo || 'pieza',
        cantidad_solicitada: parseInt(d.cantidad_solicitada, 10) || 1,
        unidad: d.unidad ? d.unidad.trim().toUpperCase() : 'UND',
        prioridad: d.prioridad || 'MEDIA',
        fecha_compromiso: d.fecha_compromiso ? d.fecha_compromiso : (nuevoPedido.fecha_compromiso || null),
        requisitos_especificos: d.requisitos_especificos ? d.requisitos_especificos.trim() : null,
        observaciones: d.observaciones ? d.observaciones.trim() : null
      }))
    };

    try {
      setLoading(true);
      const res = await API.post('/proyectos/', payloadSanitizado);
      setMensaje({ tipo: 'exito', texto: `✅ Pedido Comercial N° ${nuevoPedido.numero_pedido} registrado exitosamente.` });
      setModalNuevoPedidoAbierto(false);
      resetFormularioNuevo();
      if (res.data) {
        setProyectos(prev => [res.data, ...prev]);
      }
      await cargarProyectos();
    } catch (error) {
      let msgError = 'Error al enviar la solicitud al servidor.';
      if (error.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          msgError = error.response.data.detail
            .map(err => `${err.loc ? err.loc.join('->') : ''}: ${err.msg}`)
            .join(' | ');
        } else if (typeof error.response.data.detail === 'string') {
          msgError = error.response.data.detail;
        }
      }
      setMensaje({ tipo: 'error', texto: `❌ ${msgError}` });
    } finally {
      setLoading(false);
    }
  };

  const handleGuardarEdicionPedido = async (e) => {
    e.preventDefault();
    if (!proyectoSeleccionado) return;

    // Normalización de fecha compromiso de cabecera (evitar "" que causa 422 en FastAPI)
    const fechaGlobalLimpia = (proyectoSeleccionado.fecha_compromiso && proyectoSeleccionado.fecha_compromiso.trim() !== '')
      ? proyectoSeleccionado.fecha_compromiso
      : null;

    // Sanitización y normalización del desglose de piezas
    const listaDetallesMapeada = (proyectoSeleccionado.detalles || []).map((d, idx) => {
      const fechaDetalle = (d.fecha_compromiso && d.fecha_compromiso.trim() !== '')
        ? d.fecha_compromiso
        : fechaGlobalLimpia;

      return {
        detalle_id: (typeof d.detalle_id === 'number' || typeof d.id_detalle === 'number') 
          ? (d.detalle_id || d.id_detalle) 
          : null,
        posicion: d.posicion || `POS-${(idx + 1) * 10}`,
        codigo_producto: d.codigo_producto ? d.codigo_producto.trim() : null,
        descripcion: (d.descripcion || 'Pieza de Fabricación').trim(),
        tipo: d.tipo || 'pieza',
        cantidad_solicitada: parseInt(d.cantidad_solicitada, 10) || 1,
        unidad: (d.unidad || 'UND').trim().toUpperCase(),
        prioridad: d.prioridad || 'MEDIA',
        fecha_compromiso: fechaDetalle,
        requisitos_especificos: d.requisitos_especificos ? d.requisitos_especificos.trim() : null,
        observaciones: d.observaciones ? d.observaciones.trim() : null
      };
    });

    const presupuestosMapeados = (proyectoSeleccionado.presupuestos_componentes || [])
      .filter(item => item.referencia && item.referencia.trim() !== '')
      .map(item => ({
        categoria: item.categoria,
        referencia: item.referencia.trim(),
        monto_presupuestado: Number(item.monto_presupuestado) || 0
      }));

    const payloadSanitizado = {
      numero_pedido: (proyectoSeleccionado.numero_pedido || '').trim(),
      cliente_nombre: (proyectoSeleccionado.cliente_nombre || '').trim(),
      contacto_nombre: proyectoSeleccionado.contacto_nombre ? proyectoSeleccionado.contacto_nombre.trim() : null,
      contacto_telefono: proyectoSeleccionado.contacto_telefono ? proyectoSeleccionado.contacto_telefono.trim() : null,
      contacto_email: proyectoSeleccionado.contacto_email ? proyectoSeleccionado.contacto_email.trim() : null,
      ubicacion_cliente: proyectoSeleccionado.ubicacion_cliente ? proyectoSeleccionado.ubicacion_cliente.trim() : null,
      requisitos_cliente: proyectoSeleccionado.requisitos_cliente ? proyectoSeleccionado.requisitos_cliente.trim() : null,
      fecha_compromiso: fechaGlobalLimpia,
      detalles: listaDetallesMapeada,
      pedido_detalles: listaDetallesMapeada,
      presupuestos_componentes: presupuestosMapeados
    };

    try {
      setLoading(true);
      const res = await API.patch(`/proyectos/${proyectoSeleccionado.id_proyecto}`, payloadSanitizado);
      setMensaje({ tipo: 'exito', texto: `✅ Pedido N° ${proyectoSeleccionado.numero_pedido} actualizado exitosamente.` });
      setModalDetalleAbierto(false);
      
      setProyectos(prev => prev.map(p => p.id_proyecto === proyectoSeleccionado.id_proyecto ? res.data : p));
      await cargarProyectos();
    } catch (error) {
      let msgError = 'Error al actualizar el pedido comercial.';
      if (error.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          msgError = error.response.data.detail
            .map(err => `${err.loc ? err.loc.join('->') : ''}: ${err.msg}`)
            .join(' | ');
        } else if (typeof error.response.data.detail === 'string') {
          msgError = error.response.data.detail;
        }
      }
      setMensaje({ tipo: 'error', texto: `❌ ${msgError}` });
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmarProyecto = async (idProyecto) => {
    try {
      setLoading(true);
      await API.patch(`/proyectos/${idProyecto}/confirmar`);
      setMensaje({ tipo: 'exito', texto: '✅ Pedido comercial confirmado correctamente y disponible en la Bandeja de Recepción de Diseño.' });
      setModalDetalleAbierto(false);
      await cargarProyectos();
    } catch (error) {
      const msgError = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : 'Error al confirmar el pedido comercial.';
      setMensaje({ tipo: 'error', texto: `❌ ${msgError}` });
    } finally {
      setLoading(false);
    }
  };

  const handleConvertirCotizacionAPedido = async (idCotizacion) => {
    setMensaje({ tipo: '', texto: '' });
    try {
      setLoading(true);
      await API.patch(`/ventas/cotizaciones/${idCotizacion}/aprobar-y-generar-pedido`);
      setMensaje({ tipo: 'exito', texto: `✅ Cotización aprobada. Pedido Comercial generado exitosamente.` });
      setPestañaModulo('pedidos');
      await cargarProyectos();
    } catch (error) {
      const msgError = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : 'Error al convertir la cotización en pedido.';
      setMensaje({ tipo: 'error', texto: `❌ ${msgError}` });
    } finally {
      setLoading(false);
    }
  };

  const resetFormularioNuevo = () => {
    setNuevoPedido({
      numero_pedido: '',
      cliente_nombre: '',
      contacto_nombre: '',
      contacto_telefono: '',
      contacto_email: '',
      ubicacion_cliente: '',
      fecha_compromiso: '',
      requisitos_cliente: '',
      detalles: [
        { id: 1, codigo_producto: '', descripcion: '', tipo: 'pieza', cantidad_solicitada: 1, unidad: 'UND', prioridad: 'MEDIA', fecha_compromiso: '', requisitos_especificos: '', observaciones: '' }
      ]
    });
  };

  const abrirModalExpediente = async (p) => {
    const esConfirmado = !!p.confirmado;
    setEsEdicion(!esConfirmado);
    setExpedienteError('');

    const detallesIniciales = p.detalles && p.detalles.length > 0
      ? p.detalles
      : esConfirmado
        ? []
        : [
            { id: 1, codigo_producto: 'A-01', descripcion: p.detalle_producto || 'Pieza Mecanizada', tipo: 'pieza', cantidad_solicitada: p.cantidad || 1, unidad: 'UND', prioridad: 'MEDIA', fecha_compromiso: p.fecha_compromiso || '', requisitos_especificos: '' }
          ];

    setProyectoSeleccionado({
      ...p,
      presupuestos_componentes: p.presupuestos_componentes || [],
      detalles: detallesIniciales
    });
    setModalDetalleAbierto(true);

    if (esConfirmado) {
      setExpedienteCargando(true);
      try {
        const respuesta = await API.get(`/proyectos/${p.id_proyecto}/expediente`);
        setProyectoSeleccionado({
          ...respuesta.data,
          presupuestos_componentes: respuesta.data.presupuestos_componentes || [],
          detalles: respuesta.data.pedido_detalles || respuesta.data.detalles || []
        });
      } catch (error) {
        setExpedienteError(
          typeof error.response?.data?.detail === 'string'
            ? error.response.data.detail
            : 'No fue posible cargar el expediente comercial del pedido.'
        );
      } finally {
        setExpedienteCargando(false);
      }
    }
  };

  const handleGuardarNuevoMantenimiento = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMensaje({ tipo: '', texto: '' });

    try {
      const res = await API.post('/mantenimientos/nuevo', formMantenimiento);
      const nuevoReg = res.data;

      setMensaje({ 
        tipo: 'exito', 
        texto: `✅ Mantenimiento [${nuevoReg.codigo_mantenimiento}] registrado y guardado exitosamente en PostgreSQL.` 
      });
      
      setModalNuevoMantenimientoAbierto(false);
      setListaMantenimientos(prev => [res.data, ...prev]);

      setFormMantenimiento({
        codigo_mantenimiento: `MANT-2026-${Math.floor(100 + Math.random() * 900)}`,
        cliente_nombre: '',
        codigo_op: '',
        nombre_maquina: '',
        marca_modelo: '',
        serie_maquina: '',
        observaciones_ingreso: ''
      });

      await cargarMantenimientos();
    } catch (err) {
      const msgError = typeof err.response?.data?.detail === 'string'
        ? err.response.data.detail
        : 'No se pudo guardar la máquina en la base de datos.';
      setMensaje({ tipo: 'error', texto: `❌ Error al guardar mantenimiento: ${msgError}` });
    } finally {
      setLoading(false);
    }
  };

  const handleAgregarPiezaLevantamiento = () => {
    if (!nuevaPiezaTemp.codigo || !nuevaPiezaTemp.descripcion) return;

    const nuevaPos = piezasLevantamiento.length + 1;
    setPiezasLevantamiento([
      ...piezasLevantamiento,
      {
        posicion: nuevaPos,
        codigo: nuevaPiezaTemp.codigo,
        descripcion: nuevaPiezaTemp.descripcion,
        accion: nuevaPiezaTemp.accion,
        cantidad: parseInt(nuevaPiezaTemp.cantidad) || 1,
        material: nuevaPiezaTemp.material,
        cotizado: parseFloat(nuevaPiezaTemp.cotizado) || 0,
        autorizado: true
      }
    ]);

    setNuevaPiezaTemp({
      codigo: '',
      descripcion: '',
      accion: 'FABRICAR_NUEVA',
      cantidad: 1,
      material: 'AISI 1045',
      cotizado: 0
    });
  };

  const toggleAutorizacionPieza = (index) => {
    const copia = [...piezasLevantamiento];
    copia[index].autorizado = !copia[index].autorizado;
    setPiezasLevantamiento(copia);
  };

  const handleExplotarAMicroProduccionMES = async () => {
    const autorizadas = piezasLevantamiento.filter(p => p.autorizado);
    try {
      await API.post(`/mantenimientos/${mantenimientoSeleccionado.id_mantenimiento}/explotar-mes`);
    } catch (err) {
      console.warn("Las piezas se conservaron en la cola local de producción.");
    }

    const listaActualizada = listaMantenimientos.map(m => {
      if (m.id_mantenimiento === mantenimientoSeleccionado.id_mantenimiento) {
        return {
          ...m,
          fase_mantenimiento: 'EN_FABRICACION',
          total_piezas_autorizadas: autorizadas.length,
          porcentaje_kit_listo: 0.0
        };
      }
      return m;
    });

    setListaMantenimientos(listaActualizada);
    setModalLevantamientoAbierto(false);
    setMensaje({ tipo: 'exito', texto: `🚀 ${autorizadas.length} piezas autorizadas enviadas a la cola de producción.` });
  };

  const abrirLevantamientoModal = async (mant) => {
    setMantenimientoSeleccionado(mant);
    try {
      const res = await API.get(`/mantenimientos/${mant.id_mantenimiento || 1}/piezas`);
      if (Array.isArray(res.data) && res.data.length > 0) {
        setPiezasLevantamiento(res.data.map((p, idx) => ({
          posicion: idx + 1,
          codigo: p.codigo_pieza_plano || p.codigo,
          descripcion: p.descripcion_pieza || p.descripcion,
          accion: p.accion_requerida || p.accion,
          cantidad: p.cantidad_requerida || p.cantidad,
          material: p.material_especificado || p.material,
          cotizado: p.precio_unitario_cotizado || 0,
          autorizado: p.autorizado_cliente ?? true
        })));
      } else {
        setPiezasLevantamiento(mant.piezas || []);
      }
    } catch (err) {
      setPiezasLevantamiento(mant.piezas || []);
    }
    setModalLevantamientoAbierto(true);
  };

  const ESTILO_ESTADO_PEDIDO = {
    RECIBIDO: 'bg-slate-100 text-slate-700 border-slate-300',
    EN_ESTRUCTURACION: 'bg-blue-100 text-blue-800 border-blue-300',
    PARCIALMENTE_ASIGNADO: 'bg-amber-100 text-amber-800 border-amber-300',
    ASIGNADO: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    EN_PRODUCCION: 'bg-indigo-100 text-indigo-800 border-indigo-300',
    ENTREGADO: 'bg-teal-100 text-teal-800 border-teal-300',
    CERRADO: 'bg-slate-200 text-slate-700 border-slate-300',
    CANCELADO: 'bg-red-100 text-red-800 border-red-300',
  };
  const ETIQUETA_ESTADO_PEDIDO = (e) => (e || 'RECIBIDO').replaceAll('_', ' ');

  const cumpleFiltro = (p, filtro) => {
    switch (filtro) {
      case 'TODOS': return true;
      case 'CONFIRMADO': return !!p.confirmado;
      case 'PENDIENTE': return !p.confirmado;
      default: return true;
    }
  };

  const totalProyectos = proyectos.length;
  const confirmados = proyectos.filter(p => p.confirmado).length;
  const pendientes = proyectos.filter(p => !p.confirmado).length;

  const proyectosFiltrados = proyectos.filter((p) => {
    const termino = busqueda.toLowerCase().trim();
    const pedido = (p.numero_pedido || '').toLowerCase();
    const cliente = (p.cliente_nombre || '').toLowerCase();
    const coincideBusqueda = pedido.includes(termino) || cliente.includes(termino);

    return coincideBusqueda && cumpleFiltro(p, filtroEstado);
  });

  const listaMantenimientosFinal = (listaMantenimientos || []).filter((m) => {
    const termino = busqueda.toLowerCase().trim();
    if (!termino) return true;
    const cod = (m.codigo_mantenimiento || m.numero_pedido || '').toLowerCase();
    const cli = (m.cliente_nombre || m.cliente || '').toLowerCase();
    const maq = (m.nombre_maquina || m.detalle_producto || '').toLowerCase();
    const op = (m.codigo_op || '').toLowerCase();
    return cod.includes(termino) || cli.includes(termino) || maq.includes(termino) || op.includes(termino);
  });

  return (
    <div className="p-6 bg-slate-50 min-h-screen space-y-6">
      <header className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <span>💼</span> Ventas, Pedidos Comercial & Proyectos (PM-01)
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Gestión Integral de Órdenes de Producción (OP) y Pedidos [ISO 9001:2026]
          </p>
        </div>

        <div className="flex gap-2 bg-slate-100 p-1 rounded-xl border border-slate-200 self-stretch md:self-auto">
          <button
            type="button"
            onClick={() => setPestañaModulo('cotizaciones')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer ${
              pestañaModulo === 'cotizaciones' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            📝 Cotizaciones y Ofertas
          </button>
          <button
            type="button"
            onClick={() => setPestañaModulo('pedidos')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer ${
              pestañaModulo === 'pedidos' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            📋 Pedidos Comerciales
          </button>
          <button
            type="button"
            onClick={() => {
              setPestañaModulo('mantenimientos');
              cargarMantenimientos();
            }}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer flex items-center gap-1.5 ${
              pestañaModulo === 'mantenimientos' ? 'bg-amber-600 text-white shadow-sm font-black' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span>🛠️</span> Mantenimientos & Overhaul
          </button>
        </div>
      </header>

      {mensaje.texto && (
        <div className={`p-4 rounded-lg text-sm font-semibold border ${
          mensaje.tipo === 'exito' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-red-50 text-red-800 border-red-200'
        }`}>
          {mensaje.texto}
        </div>
      )}

      {pestañaModulo === 'cotizaciones' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs font-bold text-slate-600">Gestión de Cotizaciones y Ofertas Comerciales</span>
            <div className="flex gap-2">
              <button
                onClick={() => setModalNuevoCotizacionAbierto(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center gap-1.5 cursor-pointer"
              >
                <span>➕</span> Nueva Cotización
              </button>
              <button
                onClick={cargarProyectos}
                className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg border border-slate-300 transition flex items-center gap-1.5 cursor-pointer"
              >
                <span>🔄</span> Recargar
              </button>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 border-b pb-3">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-700">Listado de Cotizaciones Emitidas</h2>
              </div>

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full md:w-auto">
                <input
                  type="text"
                  placeholder="🔍 Buscar por N° Cotización o Cliente..."
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  className="w-full sm:w-72 p-2 border border-slate-300 rounded-lg text-xs bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600 border-collapse">
                <thead>
                  <tr className="bg-slate-100 text-slate-700 font-bold uppercase border-b border-slate-200">
                    <th className="p-3">N° Cotización</th>
                    <th className="p-3">Socio de Negocio</th>
                    <th className="p-3">Fecha Emisión</th>
                    <th className="p-3">Valor Total</th>
                    <th className="p-3">Estado</th>
                    <th className="p-3 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {cotizaciones.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="p-6 text-center text-slate-400 font-medium">
                        {loading ? 'Cargando cotizaciones...' : 'No hay cotizaciones registradas.'}
                      </td>
                    </tr>
                  ) : (
                    cotizaciones
                      .filter(c =>
                        (c.numero_cotizacion || '').toLowerCase().includes(busqueda.toLowerCase()) ||
                        (c.id_socio || '').toLowerCase().includes(busqueda.toLowerCase())
                      )
                      .map((c) => (
                        <tr key={c.id_cotizacion} className="hover:bg-slate-50 transition">
                          <td className="p-3 font-bold font-mono text-blue-700 text-sm">
                            📝 {c.numero_cotizacion}
                          </td>
                          <td className="p-3 font-bold text-slate-800">
                            {c.id_socio}
                          </td>
                          <td className="p-3 whitespace-nowrap">
                            {c.fecha_emision || 'S/F'}
                          </td>
                          <td className="p-3 font-bold text-emerald-700">
                            $ {Number(c.valor_total).toLocaleString('es-CO')}
                          </td>
                          <td className="p-3 whitespace-nowrap">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              c.estado === 'APROBADA'
                                ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                                : c.estado === 'EMITIDA'
                                ? 'bg-blue-100 text-blue-800 border-blue-300'
                                : 'bg-amber-100 text-amber-800 border-amber-300'
                            }`}>
                              {c.estado}
                            </span>
                          </td>
                          <td className="p-3 text-right whitespace-nowrap">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                type="button"
                                onClick={() => handleAbrirVisorCotizacion(c)}
                                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold rounded text-[11px] border border-slate-300 transition shadow-xs flex items-center gap-1 cursor-pointer"
                                title="Ver documento membretado, imprimir/PDF y enviar"
                              >
                                👁️ Ver / PDF / ✉️
                              </button>

                              {c.estado !== 'APROBADA' && (
                                <button
                                  type="button"
                                  onClick={() => handleConvertirCotizacionAPedido(c.id_cotizacion)}
                                  className="px-3 py-1 font-semibold rounded text-[11px] bg-blue-600 text-white hover:bg-blue-700 transition shadow-sm cursor-pointer"
                                >
                                  🚀 Convertir a Pedido
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {pestañaModulo === 'pedidos' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs font-bold text-slate-600">Radicación y Registro de Órdenes de Fabricación Directa</span>
            <div className="flex gap-2">
              <button
                onClick={() => setModalNuevoPedidoAbierto(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center gap-1.5 cursor-pointer"
              >
                <span>➕</span> Nuevo Pedido Comercial
              </button>
              <button
                onClick={cargarProyectos}
                className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg border border-slate-300 transition flex items-center gap-1.5 cursor-pointer"
              >
                <span>🔄</span> Recargar
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <button
              type="button"
              onClick={() => setFiltroEstado('TODOS')}
              className={`p-4 rounded-xl border text-left transition-all shadow-sm cursor-pointer ${
                filtroEstado === 'TODOS'
                  ? 'bg-blue-50/80 border-blue-500 ring-2 ring-blue-400/30'
                  : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wide">Total Pedidos Registrados</span>
              <p className="text-2xl font-bold text-slate-800 mt-1">{totalProyectos}</p>
              <span className="text-[10px] text-blue-600 font-semibold mt-1 block">🔍 Haz clic para ver todos</span>
            </button>

            <button
              type="button"
              onClick={() => setFiltroEstado('CONFIRMADO')}
              className={`p-4 rounded-xl border text-left transition-all shadow-sm cursor-pointer ${
                filtroEstado === 'CONFIRMADO'
                  ? 'bg-emerald-50/80 border-emerald-500 ring-2 ring-emerald-400/30'
                  : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <span className="text-xs font-bold text-emerald-600 uppercase tracking-wide">Pedidos Confirmados</span>
              <p className="text-2xl font-bold text-emerald-700 mt-1">{confirmados}</p>
              <span className="text-[10px] text-emerald-600 font-semibold mt-1 block">🔍 Filtrar por Confirmados</span>
            </button>

            <button
              type="button"
              onClick={() => setFiltroEstado('PENDIENTE')}
              className={`p-4 rounded-xl border text-left transition-all shadow-sm cursor-pointer ${
                filtroEstado === 'PENDIENTE'
                  ? 'bg-amber-50/80 border-amber-500 ring-2 ring-amber-400/30'
                  : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <span className="text-xs font-bold text-amber-600 uppercase tracking-wide">En Revisión / Pendientes</span>
              <p className="text-2xl font-bold text-amber-700 mt-1">{pendientes}</p>
              <span className="text-[10px] text-amber-600 font-semibold mt-1 block">🔍 Filtrar por Pendientes</span>
            </button>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 border-b pb-3">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-700">Listado de Pedidos Comerciales</h2>
                {filtroEstado !== 'TODOS' && (
                  <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-bold rounded uppercase">
                    Filtro Activo: {filtroEstado}
                  </span>
                )}
              </div>

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full md:w-auto">
                <select
                  value={filtroEstado}
                  onChange={(e) => setFiltroEstado(e.target.value)}
                  className="p-2 border border-slate-300 rounded-lg text-xs bg-slate-50 font-medium text-slate-700 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="TODOS">Todos los Estados</option>
                  <option value="CONFIRMADO">CONFIRMADOS (comercial)</option>
                  <option value="PENDIENTE">POR CONFIRMAR (comercial)</option>
                </select>

                <input
                  type="text"
                  placeholder="🔍 Buscar por N° Pedido o Cliente..."
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  className="w-full sm:w-72 p-2 border border-slate-300 rounded-lg text-xs bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600 border-collapse">
                <thead>
                  <tr className="bg-slate-100 text-slate-700 font-bold uppercase border-b border-slate-200">
                    <th className="p-3">N° Pedido</th>
                    <th className="p-3">Cliente</th>
                    <th className="p-3">Resumen de Piezas / Trabajos Solicitados</th>
                    <th className="p-3 text-center">Solicitada / Asignada / Pendiente</th>
                    <th className="p-3">Fecha Compromiso Cliente</th>
                    <th className="p-3">Estado del Pedido</th>
                    <th className="p-3 text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {proyectosFiltrados.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="p-6 text-center text-slate-400 font-medium">
                        {loading ? 'Cargando pedidos comerciales...' : 'No hay pedidos comerciales que coincidan con el filtro seleccionado.'}
                      </td>
                    </tr>
                  ) : (
                    proyectosFiltrados.map((p) => (
                      <tr key={p.id_proyecto} className="hover:bg-slate-50 transition">
                        <td className="p-3 font-bold font-mono text-purple-700 text-sm">
                          📋 {p.numero_pedido || 'PED-S/N'}
                        </td>
                        <td className="p-3 font-bold text-slate-800">
                          {p.cliente_nombre}
                          {p.contacto_nombre && <div className="text-[10px] text-slate-400 font-medium">👤 {p.contacto_nombre}</div>}
                        </td>
                        <td className="p-3 font-medium text-slate-800">{p.detalle_producto || 'Pieza Mecanizada'}</td>
                        <td className="p-3 text-center whitespace-nowrap">
                          <div className="font-bold">
                            <span className="text-blue-900">{p.total_solicitado ?? p.cantidad ?? 0}</span>
                            {' / '}<span className="text-emerald-700">{p.total_asignado ?? 0}</span>
                            {' / '}<span className="text-amber-700">{p.total_pendiente ?? 0}</span>
                          </div>
                          <div className="w-24 h-1.5 bg-slate-200 rounded mx-auto mt-1 overflow-hidden">
                            <div className="h-full bg-emerald-500" style={{ width: `${p.cobertura_pct || 0}%` }} />
                          </div>
                          <div className="text-[10px] text-slate-500 mt-0.5">{p.cobertura_pct || 0}% cubierto por OTs</div>
                        </td>
                        <td className="p-3 font-bold text-slate-800 whitespace-nowrap bg-amber-50/40 px-2 rounded border border-amber-200/50">
                          📅 {p.fecha_compromiso || 'Sin fecha de entrega'}
                        </td>
                        <td className="p-3 whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${ESTILO_ESTADO_PEDIDO[p.estado_pedido] || ESTILO_ESTADO_PEDIDO.RECIBIDO}`}>
                            {ETIQUETA_ESTADO_PEDIDO(p.estado_pedido)}
                          </span>
                          {p.bloqueado && (
                            <span className="ml-1 px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 border border-red-300">⛔ BLOQUEADO</span>
                          )}
                          {!p.confirmado && (
                            <div className="text-[10px] text-amber-700 font-semibold mt-0.5">Sin confirmar</div>
                          )}
                        </td>
                        <td className="p-3 text-center whitespace-nowrap space-x-1.5">
                          <button
                            type="button"
                            onClick={() => abrirModalExpediente(p)}
                            className={`px-2.5 py-1 font-semibold rounded text-[11px] transition shadow-sm cursor-pointer ${
                              p.confirmado
                                ? 'bg-slate-700 text-white hover:bg-slate-800'
                                : 'bg-blue-600 text-white hover:bg-blue-700'
                            }`}
                          >
                            {p.confirmado ? '👁️ Ver Expediente' : '✏️ Abrir y Editar'}
                          </button>
                          
                          <button
                            type="button"
                            onClick={() => handleAbrirHistorial(p)}
                            title="Consultar Historial y Suspender/Reactivar"
                            className="px-2 py-1 bg-amber-50 hover:bg-amber-100 border border-amber-300 text-amber-900 font-bold rounded text-[11px] transition shadow-xs cursor-pointer"
                          >
                            📜 Historial
                          </button>

                          {!p.confirmado && (
                            <button
                              type="button"
                              onClick={() => handleConfirmarProyecto(p.id_proyecto)}
                              className="px-2.5 py-1 font-semibold rounded text-[11px] bg-emerald-600 text-white hover:bg-emerald-700 transition shadow-sm cursor-pointer"
                            >
                              ✓ Confirmar
                            </button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {pestañaModulo === 'mantenimientos' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center bg-white p-3.5 rounded-xl border border-slate-200 shadow-sm">
            <span className="text-xs font-bold text-slate-700 flex items-center gap-2">
              <span>⚙️</span> Tabla de Proyectos de Mantenimiento y Control SGI
            </span>

            <button
              type="button"
              onClick={() => setModalNuevoMantenimientoAbierto(true)}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg text-xs shadow-sm transition flex items-center gap-1.5 cursor-pointer"
            >
              <span>➕</span> Registrar Ingreso de Máquina
            </button>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden p-4">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600 border-collapse">
                <thead>
                  <tr className="bg-slate-100 text-slate-700 font-bold uppercase border-b border-slate-200">
                    <th className="p-3">Código Proyecto</th>
                    <th className="p-3">Cliente / Razón Social</th>
                    <th className="p-3">Máquina / Equipo</th>
                    <th className="p-3">OP Venta</th>
                    <th className="p-3">Fase SGI / Validación</th>
                    <th className="p-3 text-center">Acción de Puerta de Paso (Quality Gate)</th>
                    <th className="p-3 text-center">Acciones de Despliegue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {listaMantenimientosFinal.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="p-6 text-center text-slate-400 font-medium">
                        No hay proyectos de mantenimiento registrados en la base de datos.
                      </td>
                    </tr>
                  ) : (
                    listaMantenimientosFinal.map((p) => {
                      const idUnico = p.id_proyecto || p.id_mantenimiento || 1;
                      const piezasAbiertas = !!piezasExpandidas[idUnico];
                      const cargandoPiezas = !!cargandoPiezasMap[idUnico];
                      const piezasProyecto = piezasProyectoMap[idUnico] || p.piezas || p.detalles || [];

                      const faseActualStr = p.fase_mantenimiento || 'LAVADO_DESARME';
                      const etapaObjActual = ETAPAS_SGI.find(e => e.id === faseActualStr) || ETAPAS_SGI[1];
                      const tienePermisoArea = esAreaAutorizadaParaPaso(etapaObjActual.area);

                      return (
                        <React.Fragment key={idUnico}>
                          <tr className="hover:bg-slate-50 transition">
                            <td className="p-3 font-mono font-bold text-amber-800 whitespace-nowrap">
                              {p.codigo_mantenimiento || p.numero_pedido || 'MANT-2026-010'}
                            </td>
                            <td className="p-3 font-bold text-slate-800">
                              {p.cliente_nombre || p.cliente || 'Sin Cliente'}
                            </td>
                            <td className="p-3 font-medium text-slate-800">
                              {p.nombre_maquina || p.detalle_producto || 'Equipo General'}
                            </td>
                            <td className="p-3 font-mono font-bold text-blue-800">
                              {p.codigo_op || 'OP-100'}
                            </td>
                            <td className="p-3 whitespace-nowrap">
                              <span className="px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase bg-amber-50 text-amber-800 border border-amber-300">
                                {etapaObjActual.nombre}
                              </span>
                            </td>

                            <td className="p-3 text-center whitespace-nowrap">
                              {tienePermisoArea ? (
                                <button
                                  type="button"
                                  onClick={() => handleAvanzarPuertaPasoSGI(p)}
                                  disabled={loading}
                                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-extrabold rounded text-[11px] shadow-sm transition cursor-pointer flex items-center justify-center gap-1 mx-auto"
                                >
                                  {etapaObjActual.accion}
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  disabled
                                  title={`Solo el área de ${etapaObjActual.area} puede aprobar esta etapa.`}
                                  className="px-3 py-1.5 bg-slate-100 text-slate-400 border border-slate-300 font-bold rounded text-[10px] cursor-not-allowed flex items-center justify-center gap-1 mx-auto"
                                >
                                  🔒 Requiere {etapaObjActual.area}
                                </button>
                              )}
                            </td>

                            <td className="p-3 text-center whitespace-nowrap space-x-2">
                              <button
                                type="button"
                                onClick={() => togglePiezasProyecto(idUnico, p)}
                                disabled={cargandoPiezas}
                                className={`px-2.5 py-1 font-bold rounded text-[11px] transition shadow-sm cursor-pointer border ${
                                  piezasAbiertas 
                                    ? 'bg-blue-600 text-white border-blue-700' 
                                    : 'bg-blue-50 text-blue-800 border-blue-200 hover:bg-blue-100'
                                }`}
                              >
                                {cargandoPiezas ? '🔄 Cargando...' : piezasAbiertas ? '🔼 Ocultar Piezas' : '📦 Ver Piezas'}
                              </button>

                              <button
                                type="button"
                                onClick={() => abrirLevantamientoModal(p)}
                                className="px-2.5 py-1 font-bold rounded text-[11px] bg-slate-700 text-white hover:bg-slate-800 transition shadow-sm cursor-pointer"
                              >
                                ✏️ Cargar / Editar
                              </button>
                            </td>
                          </tr>

                          {piezasAbiertas && (
                            <tr className="bg-slate-50">
                              <td colSpan="7" className="p-4">
                                <div className="p-3 bg-white rounded-lg border border-slate-300 space-y-2 shadow-inner">
                                  <div className="flex justify-between items-center text-xs font-bold text-slate-700 border-b pb-1.5">
                                    <span>📦 Piezas e Ítems del Proyecto ({piezasProyecto.length})</span>
                                    <span className="text-[10px] text-emerald-700 font-mono font-bold">🟢 Consulta dinámicamente conectada a PostgreSQL</span>
                                  </div>

                                  {cargandoPiezas ? (
                                    <div className="p-4 text-center text-xs text-blue-700 font-semibold">
                                      🔄 Obteniendo piezas desde el servidor...
                                    </div>
                                  ) : piezasProyecto.length === 0 ? (
                                    <p className="text-slate-400 italic text-center py-2 text-xs">No hay piezas o detalles registrados para este mantenimiento.</p>
                                  ) : (
                                    <div className="overflow-x-auto">
                                      <table className="w-full text-left text-[11px]">
                                        <thead>
                                          <tr className="bg-slate-100 text-slate-700 font-bold border-b">
                                            <th className="p-2 text-center w-10">#</th>
                                            <th className="p-2">Código / Plano</th>
                                            <th className="p-2">Descripción de la Pieza</th>
                                            <th className="p-2">Acción Requerida</th>
                                            <th className="p-2 text-center">Cant.</th>
                                            <th className="p-2">Material</th>
                                            <th className="p-2 text-center">Estado Aprobación</th>
                                            <th className="p-2 text-center">Solicitud de compra / Lista de materiales 🛒</th>
                                          </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-200 text-slate-600">
                                          {piezasProyecto.map((pz, idx) => {
                                            const solAsociada = solicitudesCompra.find(
                                              s => s.codigo_op === (pz.codigo_op || p.codigo_op) && 
                                                   s.codigo_plano === (pz.codigo || pz.codigo_pieza_plano)
                                            );
                                            const estadoBomItem = solAsociada?.estado_bom || (solAsociada ? 'SOLICITADO' : 'SIN_SOLICITAR');

                                            return (
                                              <tr key={idx} className="hover:bg-slate-50">
                                                <td className="p-2 text-center font-mono text-slate-400">{idx + 1}</td>
                                                <td className="p-2 font-mono font-bold text-purple-700">{pz.codigo || pz.codigo_producto || 'PLN-001'}</td>
                                                <td className="p-2 font-bold text-slate-800">{pz.descripcion || pz.detalle_pieza}</td>
                                                <td className="p-2 font-semibold text-slate-700">
                                                  {ETIQUETAS_ACCION_PIEZA[pz.accion] || ETIQUETAS_ACCION_PIEZA[pz.tipo] || pz.accion || pz.tipo || 'Fabricar nueva'}
                                                </td>
                                                <td className="p-2 text-center font-bold text-blue-900">{pz.cantidad || pz.cantidad_solicitada || 1}</td>
                                                <td className="p-2 text-slate-500">{pz.material || 'AISI 1045'}</td>
                                                <td className="p-2 text-center">
                                                  <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                                                    pz.autorizado ?? true ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-amber-100 text-amber-800 border border-amber-300'
                                                  }`}>
                                                    {pz.autorizado ?? true ? '✓ APROBADA' : '⏳ PENDIENTE'}
                                                  </span>
                                                </td>
                                                <td className="p-2 text-center">
                                                  <button
                                                    type="button"
                                                    onClick={() => handleVerDetalleBom(pz, p)}
                                                    className="p-1 hover:opacity-80 transition cursor-pointer"
                                                  >
                                                    {renderBadgeBom(estadoBomItem)}
                                                  </button>
                                                </td>
                                              </tr>
                                            );
                                          })}
                                        </tbody>
                                      </table>
                                    </div>
                                  )}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* MODAL NUEVO PEDIDO COMERCIAL */}
      {modalNuevoPedidoAbierto && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full p-6 space-y-4 max-h-[92vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-bold rounded uppercase">
                  Radicación de Pedido Comercial e Ítems con Entregas Parciales [PM-01 / ISO 9001:2026]
                </span>
                <h3 className="text-xl font-bold text-slate-800 mt-1">
                  Registrar Nuevo Pedido Comercial
                </h3>
              </div>
              <button onClick={() => setModalNuevoPedidoAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
            </div>

            <form onSubmit={handleCrearNuevoPedido} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">N° Pedido Comercial *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ej. PED-2026-105"
                    value={nuevoPedido.numero_pedido}
                    onChange={(e) => setNuevoPedido({ ...nuevoPedido, numero_pedido: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-purple-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Cliente / Razón Social *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ej. Ecopetrol S.A."
                    value={nuevoPedido.cliente_nombre}
                    onChange={(e) => setNuevoPedido({ ...nuevoPedido, cliente_nombre: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded font-bold text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Ubicación / Planta de Entrega</label>
                  <input
                    type="text"
                    placeholder="Ej. Refinería Barrancabermeja"
                    value={nuevoPedido.ubicacion_cliente}
                    onChange={(e) => setNuevoPedido({ ...nuevoPedido, ubicacion_cliente: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-800 mb-1">📅 Fecha Compromiso Global</label>
                  <input
                    type="date"
                    value={nuevoPedido.fecha_compromiso}
                    onChange={(e) => setNuevoPedido({ ...nuevoPedido, fecha_compromiso: e.target.value })}
                    className="w-full p-2 border border-blue-300 rounded font-bold text-blue-900 bg-blue-50/50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Contacto Cliente</label>
                  <input
                    type="text"
                    placeholder="Ing. Juan Pérez"
                    value={nuevoPedido.contacto_nombre}
                    onChange={(e) => setNuevoPedido({ ...nuevoPedido, contacto_nombre: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Teléfono Contacto</label>
                  <input
                    type="text"
                    placeholder="+57 300 000 0000"
                    value={nuevoPedido.contacto_telefono}
                    onChange={(e) => setNuevoPedido({ ...nuevoPedido, contacto_telefono: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Correo Electrónico</label>
                  <input
                    type="email"
                    placeholder="compras@cliente.com"
                    value={nuevoPedido.contacto_email}
                    onChange={(e) => setNuevoPedido({ ...nuevoPedido, contacto_email: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="border border-slate-200 rounded-xl p-3 bg-slate-50/50 space-y-3">
                <div className="flex justify-between items-center border-b pb-2">
                  <h4 className="font-bold text-slate-800 flex items-center gap-1.5 text-xs">
                    <span>📦</span> Estructuración de PEDIDO_DETALLE (Fechas de Entrega Parcial por Ítem)
                  </h4>
                  <button
                    type="button"
                    onClick={handleAgregarFilaDetalle}
                    className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-[11px] flex items-center gap-1 shadow-sm transition cursor-pointer"
                  >
                    ➕ Agregar Ítem a PEDIDO_DETALLE
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs bg-white border border-slate-200 rounded-lg overflow-hidden">
                    <thead className="bg-slate-100 text-slate-700 font-bold border-b">
                      <tr>
                        <th className="p-2.5 w-8 text-center">#</th>
                        <th className="p-2.5 w-24">Código Prod.</th>
                        <th className="p-2.5">Descripción del Elemento / Pieza / Servicio *</th>
                        <th className="p-2.5 w-24">Tipo *</th>
                        <th className="p-2.5 w-20 text-center">Cantidad *</th>
                        <th className="p-2.5 w-16">Unidad</th>
                        <th className="p-2.5 w-36">📅 Fecha Entrega Parcial</th>
                        <th className="p-2.5 w-20">Prioridad</th>
                        <th className="p-2.5">Requisitos Técnicos Específicos del Ítem</th>
                        <th className="p-2.5 w-8 text-center"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {nuevoPedido.detalles.map((det, index) => (
                        <tr key={det.id} className="hover:bg-slate-50">
                          <td className="p-2 text-center font-bold text-slate-400">{index + 1}</td>
                          <td className="p-2">
                            <input
                              type="text"
                              placeholder="PROD-01"
                              value={det.codigo_producto}
                              onChange={(e) => handleCambioDetalle(det.id, 'codigo_producto', e.target.value)}
                              className="w-full p-1.5 border border-slate-300 rounded font-mono font-bold text-blue-700 focus:outline-none"
                            />
                          </td>
                          <td className="p-2">
                            <input
                              type="text"
                              required
                              placeholder="Brida Forjada 12 ANSI / Serv. Metrología"
                              value={det.descripcion}
                              onChange={(e) => handleCambioDetalle(det.id, 'descripcion', e.target.value)}
                              className="w-full p-1.5 border border-slate-300 rounded font-medium text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            />
                          </td>
                          <td className="p-2">
                            <select
                              value={det.tipo}
                              onChange={(e) => handleCambioDetalle(det.id, 'tipo', e.target.value)}
                              className="w-full p-1.5 border border-slate-300 rounded bg-white font-medium cursor-pointer"
                            >
                              <option value="pieza">Pieza</option>
                              <option value="conjunto">Conjunto</option>
                              <option value="servicio">Servicio</option>
                              <option value="trabajo">Trabajo</option>
                              <option value="producto">Producto</option>
                            </select>
                          </td>
                          <td className="p-2">
                            <input
                              type="number"
                              min="1"
                              required
                              value={det.cantidad_solicitada === '' ? '' : det.cantidad_solicitada}
                              onFocus={(e) => e.target.select()}
                              onChange={(e) => {
                                const val = e.target.value;
                                handleCambioDetalle(det.id, 'cantidad_solicitada', val === '' ? '' : Math.max(1, parseInt(val, 10) || 1));
                              }}
                              className="w-full p-1.5 border border-slate-300 rounded font-bold text-center text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                          </td>
                          <td className="p-2">
                            <input
                              type="text"
                              value={det.unidad}
                              onChange={(e) => handleCambioDetalle(det.id, 'unidad', e.target.value)}
                              className="w-full p-1.5 border border-slate-300 rounded text-center text-slate-700 uppercase"
                            />
                          </td>
                          <td className="p-2">
                            <input
                              type="date"
                              value={det.fecha_compromiso || nuevoPedido.fecha_compromiso}
                              onChange={(e) => handleCambioDetalle(det.id, 'fecha_compromiso', e.target.value)}
                              className="w-full p-1.5 border border-purple-300 rounded font-bold text-purple-900 bg-purple-50/60 focus:outline-none focus:bg-white"
                            />
                          </td>
                          <td className="p-2">
                            <select
                              value={det.prioridad}
                              onChange={(e) => handleCambioDetalle(det.id, 'prioridad', e.target.value)}
                              className="w-full p-1.5 border border-slate-300 rounded bg-white font-bold text-slate-700 cursor-pointer"
                            >
                              <option value="ALTA">ALTA</option>
                              <option value="MEDIA">MEDIA</option>
                              <option value="BAJA">BAJA</option>
                            </select>
                          </td>
                          <td className="p-2">
                            <input
                              type="text"
                              placeholder="Ej. Tolerancia ±0.02mm, Dureza 30 HRC..."
                              value={det.requisitos_especificos || ''}
                              onChange={(e) => handleCambioDetalle(det.id, 'requisitos_especificos', e.target.value)}
                              className="w-full p-2 border border-slate-300 rounded text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            />
                          </td>
                          <td className="p-2 text-center">
                            <button
                              type="button"
                              onClick={() => handleEliminarFilaDetalle(det.id)}
                              className="text-red-500 hover:text-red-700 font-bold px-1.5 py-0.5 rounded hover:bg-red-50 transition cursor-pointer"
                            >
                              🗑️
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">
                  Requisitos Técnicos Generales del Pedido <span className="text-slate-400 font-normal">(Opcional)</span>
                </label>
                <input
                  type="text"
                  placeholder="Norma ASME B16.5, Certificado de Calidad 3.1..."
                  value={nuevoPedido.requisitos_cliente}
                  onChange={(e) => setNuevoPedido({ ...nuevoPedido, requisitos_cliente: capitalize(e.target.value) })}
                  className="w-full p-2 border border-slate-300 rounded text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-2 border-t pt-3">
                <button
                  type="button"
                  onClick={() => setModalNuevoPedidoAbierto(false)}
                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded transition cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded transition shadow-sm cursor-pointer"
                >
                  {loading ? 'Guardando...' : '💾 Radicar Pedido Comercial'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 1: EXPEDIENTE DE PEDIDO (CONFIRMADO - SOLO LECTURA) */}
      {modalDetalleAbierto && proyectoSeleccionado && !esEdicion && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-3 backdrop-blur-sm">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="expediente-pedido-titulo"
            className="flex max-h-[94vh] w-full max-w-7xl flex-col overflow-hidden rounded-xl border-t-4 border-emerald-600 bg-white text-xs shadow-2xl"
          >
            <header className="border-b border-slate-200 bg-white px-4 py-1.5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold uppercase tracking-wide text-slate-500">Expediente Comercial del Pedido</span>
                    <span className="rounded border border-emerald-300 bg-emerald-100 px-2 py-0.5 text-[10px] font-extrabold text-emerald-800">
                      CONFIRMADO
                    </span>
                  </div>
                  <h2 id="expediente-pedido-titulo" className="mt-0.5 font-mono text-lg font-extrabold text-slate-900">
                    {proyectoSeleccionado.numero_pedido || 'Pedido sin número'}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleAbrirHistorial(proyectoSeleccionado)}
                    className="rounded border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-[10px] font-bold text-amber-900 hover:bg-amber-100 flex items-center gap-1 cursor-pointer"
                  >
                    📜 Historial & Trazabilidad
                  </button>

                  <button
                    type="button"
                    onClick={() => abrirModalExpediente(proyectoSeleccionado)}
                    disabled={expedienteCargando}
                    className="rounded border border-slate-300 bg-slate-50 px-2.5 py-1.5 text-[10px] font-bold text-slate-700 hover:bg-slate-100 disabled:opacity-50 cursor-pointer"
                  >
                    {expedienteCargando ? 'Actualizando…' : 'Actualizar avance'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setModalDetalleAbierto(false)}
                    aria-label="Cerrar expediente comercial"
                    className="rounded px-2 py-1 text-lg font-bold text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
                  >
                    ×
                  </button>
                </div>
              </div>
            </header>

            <div className="overflow-y-auto p-3 sm:p-4">
              {expedienteError && (
                <div role="alert" className="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 font-semibold text-red-800">
                  {expedienteError}
                </div>
              )}
              {expedienteCargando ? (
                <div className="rounded border border-slate-200 bg-slate-50 py-10 text-center font-semibold text-slate-500">
                  Cargando posiciones, imputaciones y cobertura en planta…
                </div>
              ) : (
                <div className="space-y-3">
                  <section aria-label="Cabecera comercial" className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-2 font-bold uppercase tracking-wide text-slate-700">Cabecera Comercial</div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3 lg:grid-cols-6">
                      <div className="col-span-2 sm:col-span-2">
                        <span className="text-slate-500">Razón Social</span>
                        <strong className="block text-slate-900">{proyectoSeleccionado.cliente_nombre || 'No registrado'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">NIT / RUT</span>
                        <strong className="block text-slate-800">{proyectoSeleccionado.nit_rut || 'No registrado'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Persona de Contacto</span>
                        <strong className="block text-slate-800">{proyectoSeleccionado.contacto_nombre || 'No registrada'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Teléfono</span>
                        <strong className="block text-slate-800">{proyectoSeleccionado.contacto_telefono || 'No registrado'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Email</span>
                        <strong className="block break-all text-slate-800">{proyectoSeleccionado.contacto_email || 'No registrado'}</strong>
                      </div>
                      <div className="col-span-2 sm:col-span-2">
                        <span className="text-slate-500">Ubicación de Planta / Entrega</span>
                        <strong className="block text-slate-800">{proyectoSeleccionado.ubicacion_cliente || 'No registrada'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Compromiso Global</span>
                        <strong className="block text-blue-800">{proyectoSeleccionado.fecha_compromiso || 'Sin fecha'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Condición de Pago</span>
                        <strong className="block text-slate-800">
                          {proyectoSeleccionado.condiciones_pago_dias == null ? 'No registrada' : `${proyectoSeleccionado.condiciones_pago_dias} días`}
                        </strong>
                      </div>
                      <div>
                        <span className="text-slate-500">Valor Total Cotizado</span>
                        <strong className="block text-emerald-800">
                          {proyectoSeleccionado.valor_total_cotizado == null
                            ? 'No registrado'
                            : `$ ${Number(proyectoSeleccionado.valor_total_cotizado).toLocaleString('es-CO')}`}
                        </strong>
                      </div>
                      <div className="col-span-2">
                        <span className="text-slate-500">Centro de Costos Imputado</span>
                        <strong className="block text-purple-800">{proyectoSeleccionado.centro_costo_imputado || 'No registrado'}</strong>
                      </div>
                    </div>
                  </section>

                  <section aria-label="Posiciones solicitadas" className="overflow-hidden rounded-lg border border-slate-200">
                    <div className="flex items-center justify-between border-b border-slate-200 bg-white px-3 py-1.5">
                      <h3 className="font-bold text-slate-800">Posiciones Solicitadas</h3>
                      <span className="text-[10px] font-semibold text-slate-500">
                        {(proyectoSeleccionado.detalles || []).length} posiciones
                      </span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[900px] border-collapse text-left text-[11px]">
                        <thead className="bg-slate-100 text-[10px] font-extrabold uppercase text-slate-600">
                          <tr>
                            <th className="px-2 py-1.5">Posición</th>
                            <th className="px-2 py-1.5">Código / Pieza</th>
                            <th className="px-2 py-1.5">Descripción Técnica</th>
                            <th className="px-2 py-1.5 text-right">Cantidad &amp; Unidad</th>
                            <th className="px-2 py-1.5">Fecha de Entrega</th>
                            <th className="px-2 py-1.5">Estado de Cobertura (OP)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {(proyectoSeleccionado.detalles || []).map((detalle, indice) => {
                            const solicitado = Number(detalle.cantidad_solicitada || 0);
                            const asignado = Number(detalle.cantidad_asignada || 0);
                            const cobertura = detalle.estado_cobertura || (
                              asignado <= 0 ? 'SIN_ASIGNAR' : asignado < solicitado ? 'PARCIAL' : 'ASIGNADO'
                            );
                            const cantidadOrdenes = new Set(
                              (detalle.ot_detalles || [])
                                .map(relacion => relacion.orden_produccion?.codigo_op)
                                .filter(Boolean)
                            ).size;
                            const estilosCobertura = {
                              ASIGNADO: 'border-emerald-200 bg-emerald-50 text-emerald-800',
                              PARCIAL: 'border-amber-200 bg-amber-50 text-amber-800',
                              SIN_ASIGNAR: 'border-slate-200 bg-slate-100 text-slate-600'
                            };
                            const etiquetaCobertura = cobertura === 'ASIGNADO'
                              ? '100% ASIGNADO'
                              : cobertura === 'PARCIAL' ? 'PARCIAL' : 'SIN ASIGNAR';
                            return (
                              <tr key={detalle.detalle_id || detalle.id || indice} className="hover:bg-slate-50">
                                <td className="whitespace-nowrap px-2 py-1.5 font-mono font-bold text-slate-700">
                                  {detalle.posicion || `POS-${(indice + 1) * 10}`}
                                </td>
                                <td className="px-2 py-1.5 font-mono font-bold text-blue-800">
                                  {detalle.codigo_producto || 'Sin código'}
                                </td>
                                <td className="max-w-sm px-2 py-1.5 font-semibold text-slate-800">
                                  {detalle.descripcion || 'Sin descripción'}
                                  {detalle.tipo && <span className="ml-1 text-[9px] font-medium uppercase text-slate-400">{ETIQUETAS_TIPO_MATERIAL[detalle.tipo] || detalle.tipo}</span>}
                                </td>
                                <td className="whitespace-nowrap px-2 py-1.5 text-right font-bold text-slate-800">
                                  {solicitado} {detalle.unidad || 'UND'}
                                </td>
                                <td className="whitespace-nowrap px-2 py-1.5 text-slate-700">
                                  {detalle.fecha_compromiso || proyectoSeleccionado.fecha_compromiso || 'Sin fecha'}
                                </td>
                                <td className="whitespace-nowrap px-2 py-1.5">
                                  <span className={`inline-flex rounded border px-2 py-0.5 text-[9px] font-extrabold ${estilosCobertura[cobertura] || estilosCobertura.SIN_ASIGNAR}`}>
                                    {etiquetaCobertura} · {cantidadOrdenes} órdenes
                                  </span>
                                  <span className="ml-1 text-[9px] text-slate-500">{asignado}/{solicitado}</span>
                                </td>
                              </tr>
                            );
                          })}
                          {(proyectoSeleccionado.detalles || []).length === 0 && (
                            <tr>
                              <td colSpan="6" className="px-3 py-6 text-center text-slate-400">No hay posiciones asociadas al pedido.</td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {/* MODAL 2: EDICIÓN DE PEDIDO COMERCIAL (EN REVISIÓN - EDITABLE) */}
      {modalDetalleAbierto && proyectoSeleccionado && esEdicion && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full p-6 space-y-4 max-h-[92vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded uppercase bg-amber-100 text-amber-800 border border-amber-300">
                  EDICIÓN DE PEDIDO COMERCIAL (EN REVISIÓN)
                </span>
                <h3 className="text-xl font-bold text-slate-800 mt-1">
                  Pedido Comercial N°: <span className="text-purple-700 font-mono">{proyectoSeleccionado.numero_pedido}</span>
                </h3>
              </div>
              <button onClick={() => setModalDetalleAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
            </div>

            <form onSubmit={handleGuardarEdicionPedido} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">N° Pedido *</label>
                  <input
                    type="text"
                    required
                    value={proyectoSeleccionado.numero_pedido || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, numero_pedido: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-purple-800 bg-white"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Cliente / Razón Social *</label>
                  <input
                    type="text"
                    required
                    value={proyectoSeleccionado.cliente_nombre || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, cliente_nombre: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded font-bold text-slate-800 bg-white"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Ubicación / Planta</label>
                  <input
                    type="text"
                    value={proyectoSeleccionado.ubicacion_cliente || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, ubicacion_cliente: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-800 mb-1">📅 Fecha Límite Pedido Global</label>
                  <input
                    type="date"
                    value={proyectoSeleccionado.fecha_compromiso || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, fecha_compromiso: e.target.value })}
                    className="w-full p-2 border border-blue-300 rounded font-bold text-blue-900 bg-blue-50/50"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Contacto Nombre</label>
                  <input
                    type="text"
                    value={proyectoSeleccionado.contacto_nombre || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, contacto_nombre: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Teléfono Contacto</label>
                  <input
                    type="text"
                    value={proyectoSeleccionado.contacto_telefono || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, contacto_telefono: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Email Contacto</label>
                  <input
                    type="email"
                    value={proyectoSeleccionado.contacto_email || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, contacto_email: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <h4 className="font-bold text-slate-700 text-xs">📦 Detalle de Elementos / Piezas y Programación Parcial</h4>
                  <button
                    type="button"
                    onClick={handleAgregarFilaEdicion}
                    className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-[11px] shadow-sm transition cursor-pointer"
                  >
                    ➕ Agregar Ítem a PEDIDO_DETALLE
                  </button>
                </div>

                <div className="border border-slate-200 rounded-lg overflow-hidden text-xs bg-white">
                  <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-100 font-bold text-slate-700 border-b">
                      <tr>
                        <th className="p-2 w-8 text-center">#</th>
                        <th className="p-2 w-24">Código Prod.</th>
                        <th className="p-2">Descripción del Elemento / Pieza *</th>
                        <th className="p-2 w-24">Tipo</th>
                        <th className="p-2 w-20 text-center">Cantidad *</th>
                        <th className="p-2 w-16">Unidad</th>
                        <th className="p-2 w-36">📅 Fecha Entrega Parcial</th>
                        <th className="p-2 w-20">Prioridad</th>
                        <th className="p-2">Requisitos Específicos</th>
                        <th className="p-2 w-8 text-center"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 text-slate-600">
                      {(proyectoSeleccionado.detalles || []).map((det, idx) => (
                        <tr key={det.id || idx} className="hover:bg-slate-50">
                          <td className="p-2 text-center font-bold text-slate-400">{idx + 1}</td>
                          <td className="p-2">
                            <input
                              type="text"
                              value={det.codigo_producto || ''}
                              onChange={(e) => handleCambioDetalleEdicion(idx, 'codigo_producto', e.target.value)}
                              className="w-full p-1 border rounded font-mono font-bold text-blue-700"
                            />
                          </td>
                          <td className="p-2">
                            <input
                              type="text"
                              required
                              value={det.descripcion || ''}
                              onChange={(e) => handleCambioDetalleEdicion(idx, 'descripcion', e.target.value)}
                              className="w-full p-1 border rounded font-medium text-slate-800"
                            />
                          </td>
                          <td className="p-2">
                            <select
                              value={det.tipo || 'pieza'}
                              onChange={(e) => handleCambioDetalleEdicion(idx, 'tipo', e.target.value)}
                              className="w-full p-1 border rounded bg-white cursor-pointer"
                            >
                              <option value="pieza">Pieza</option>
                              <option value="conjunto">Conjunto</option>
                              <option value="servicio">Servicio</option>
                              <option value="trabajo">Trabajo</option>
                              <option value="producto">Producto</option>
                            </select>
                          </td>
                          <td className="p-2 text-center">
                            <input
                              type="number"
                              min="1"
                              required
                              value={det.cantidad_solicitada === '' ? '' : det.cantidad_solicitada}
                              onFocus={(e) => e.target.select()}
                              onChange={(e) => {
                                const val = e.target.value;
                                handleCambioDetalleEdicion(idx, 'cantidad_solicitada', val === '' ? '' : Math.max(1, parseInt(val, 10) || 1));
                              }}
                              className="w-full p-1 border rounded font-bold text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                          </td>
                          <td className="p-2">
                            <input
                              type="text"
                              value={det.unidad || 'UND'}
                              onChange={(e) => handleCambioDetalleEdicion(idx, 'unidad', e.target.value)}
                              className="w-full p-1 border rounded text-center uppercase"
                            />
                          </td>
                          <td className="p-2">
                            <input
                              type="date"
                              value={det.fecha_compromiso || ''}
                              onChange={(e) => handleCambioDetalleEdicion(idx, 'fecha_compromiso', e.target.value)}
                              className="w-full p-1 border border-purple-300 rounded font-bold text-purple-900 bg-purple-50/50"
                            />
                          </td>
                          <td className="p-2">
                            <select
                              value={det.prioridad || 'MEDIA'}
                              onChange={(e) => handleCambioDetalleEdicion(idx, 'prioridad', e.target.value)}
                              className="w-full p-1 border rounded bg-white font-bold cursor-pointer"
                            >
                              <option value="ALTA">ALTA</option>
                              <option value="MEDIA">MEDIA</option>
                              <option value="BAJA">BAJA</option>
                            </select>
                          </td>
                          <td className="p-2">
                            <input
                              type="text"
                              value={det.requisitos_especificos || ''}
                              onChange={(e) => handleCambioDetalleEdicion(idx, 'requisitos_especificos', e.target.value)}
                              className="w-full p-1 border rounded text-slate-800"
                            />
                          </td>
                          <td className="p-2 text-center">
                            <button
                              type="button"
                              onClick={() => handleEliminarFilaEdicion(idx)}
                              className="text-red-500 hover:text-red-700 font-bold px-1.5 py-0.5 rounded hover:bg-red-50 transition cursor-pointer"
                            >
                              🗑️
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">
                  Requisitos Técnicos Generales <span className="text-slate-400 font-normal">(Opcional)</span>
                </label>
                <input
                  type="text"
                  value={proyectoSeleccionado.requisitos_cliente || ''}
                  onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, requisitos_cliente: capitalize(e.target.value) })}
                  className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white"
                />
              </div>

              <section className="space-y-2 rounded-lg border border-amber-200 bg-amber-50/50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h4 className="font-bold text-slate-800">Presupuestos de costo por componente</h4>
                    <p className="mt-1 text-[11px] text-slate-600">
                      Defina los importes previstos antes de confirmar el pedido. Se comparan con el costo real liquidado de cada OP.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleAgregarPresupuestoComponente}
                    className="rounded bg-amber-600 px-2.5 py-1 font-bold text-white hover:bg-amber-700 cursor-pointer"
                  >
                    + Agregar presupuesto
                  </button>
                </div>

                {(proyectoSeleccionado.presupuestos_componentes || []).length > 0 ? (
                  <div className="space-y-2">
                    {(proyectoSeleccionado.presupuestos_componentes || []).map((item, indice) => (
                      <div
                        key={`${item.categoria}-${item.referencia}-${indice}`}
                        className="grid grid-cols-1 gap-2 rounded border border-amber-100 bg-white p-2 sm:grid-cols-[1fr_1.5fr_1fr_auto]"
                      >
                        <select
                          value={item.categoria || 'MATERIA_PRIMA'}
                          onChange={(e) => handleCambioPresupuestoComponente(indice, 'categoria', e.target.value)}
                          aria-label={`Categoría del presupuesto ${indice + 1}`}
                          className="w-full rounded border border-slate-300 p-2 bg-white cursor-pointer"
                        >
                          {CATEGORIAS_PRESUPUESTO.map(categoria => (
                            <option key={categoria.valor} value={categoria.valor}>{categoria.etiqueta}</option>
                          ))}
                        </select>
                        <input
                          type="text"
                          required
                          maxLength={200}
                          value={item.referencia || ''}
                          onChange={(e) => handleCambioPresupuestoComponente(indice, 'referencia', e.target.value)}
                          placeholder={PLACEHOLDERS_REFERENCIA_PRESUPUESTO[item.categoria] || 'Referencia del componente'}
                          aria-label={`Referencia del presupuesto ${indice + 1}`}
                          className="w-full rounded border border-slate-300 p-2 font-mono"
                        />
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          required
                          value={item.monto_presupuestado ?? ''}
                          onChange={(e) => handleCambioPresupuestoComponente(indice, 'monto_presupuestado', e.target.value)}
                          aria-label={`Monto presupuestado ${indice + 1}`}
                          placeholder="Presupuesto en COP"
                          className="w-full rounded border border-slate-300 p-2 text-right"
                        />
                        <button
                          type="button"
                          onClick={() => handleEliminarPresupuestoComponente(indice)}
                          aria-label={`Eliminar presupuesto ${indice + 1}`}
                          className="rounded px-2 font-bold text-red-600 hover:bg-red-50 cursor-pointer"
                        >
                          Eliminar
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="rounded border border-dashed border-amber-200 bg-white p-2 text-slate-500">
                    No hay presupuestos por componente configurados para este pedido.
                  </p>
                )}

                <p className="text-[10px] text-slate-500">
                  Referencias: materia prima = código/SKU; horas MES = centro|SETUP o centro|MECANIZADO; servicios = proveedor|descripción. Los importes están expresados en COP.
                </p>
              </section>

              <div className="flex justify-between items-center border-t pt-3">
                <div>
                  <button
                    type="button"
                    onClick={() => handleConfirmarProyecto(proyectoSeleccionado.id_proyecto)}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-xs transition shadow-sm flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>✓</span> Confirmar Pedido Comercial (Pasar a Diseño)
                  </button>
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setModalDetalleAbierto(false)}
                    className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded transition cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded transition shadow-sm cursor-pointer"
                  >
                    {loading ? 'Guardando...' : '💾 Guardar Cambios'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL BOM */}
      {modalBomAbierto && bomSeleccionado && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-6 space-y-4 border-t-4 border-purple-600 text-xs">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2.5 py-1 bg-purple-100 text-purple-800 text-xs font-extrabold rounded uppercase tracking-wider">
                  🔎 Trazabilidad de la lista de materiales y estado de insumos
                </span>
                <h3 className="text-xl font-bold text-slate-800 mt-2">
                  {bomSeleccionado.codigo_op} / Plano: <span className="text-purple-700 font-mono">{bomSeleccionado.codigo_plano}</span>
                </h3>
                <p className="text-xs text-slate-500 font-medium">Pieza: {bomSeleccionado.detalle_pieza}</p>
              </div>
              <button onClick={() => setModalBomAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-xl cursor-pointer">✕</button>
            </div>

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
              <span className="text-xs font-bold text-slate-600 uppercase tracking-wide">Estado de la Materia Prima / Insumos:</span>
              <div className="flex items-center justify-between text-xs gap-1 pt-1">
                <div className={`p-2 rounded text-center w-1/4 font-bold border ${
                  bomSeleccionado.estado_bom === 'SOLICITADO' ? 'bg-amber-100 text-amber-900 border-amber-400 ring-2 ring-amber-300' : 'bg-slate-100 text-slate-400'
                }`}>
                  1. SOLICITADO 🟡
                </div>
                <span className="text-slate-300 font-bold">→</span>
                <div className={`p-2 rounded text-center w-1/4 font-bold border ${
                  bomSeleccionado.estado_bom === 'EN_COMPRA' ? 'bg-blue-100 text-blue-900 border-blue-400 ring-2 ring-blue-300' : 'bg-slate-100 text-slate-400'
                }`}>
                  2. EN COMPRA 🔵
                </div>
                <span className="text-slate-300 font-bold">→</span>
                <div className={`p-2 rounded text-center w-1/4 font-bold border ${
                  bomSeleccionado.estado_bom === 'EN_ALMACEN' ? 'bg-purple-100 text-purple-900 border-purple-400 ring-2 ring-purple-300' : 'bg-slate-100 text-slate-400'
                }`}>
                  3. EN ALMACÉN 🟣
                </div>
                <span className="text-slate-300 font-bold">→</span>
                <div className={`p-2 rounded text-center w-1/4 font-bold border ${
                  bomSeleccionado.estado_bom === 'ENTREGADO' ? 'bg-emerald-100 text-emerald-800 border-emerald-400 ring-2 ring-emerald-300' : 'bg-slate-100 text-slate-400'
                }`}>
                  4. ENTREGADO 🟢
                </div>
              </div>
            </div>

            <div className="space-y-2 border p-3.5 rounded-xl bg-white text-xs">
              <h4 className="font-bold text-slate-800 flex items-center gap-1.5">
                <span>📦</span> Insumos Consolidados para esta Orden:
              </h4>
              <p className="p-3 bg-slate-50 border rounded-lg font-semibold text-slate-700 leading-relaxed">
                {bomSeleccionado.material_requerido}
              </p>
            </div>

            <div className="flex justify-end border-t pt-3">
              <button 
                onClick={() => setModalBomAbierto(false)} 
                className="px-5 py-2 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded text-xs transition cursor-pointer"
              >
                Cerrar Seguimiento
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL VISOR FORMAL DE COTIZACIÓN */}
      {modalVisorCotizacionAbierto && cotizacionDetalle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 p-3 backdrop-blur-sm">
          <div className="flex max-h-[96vh] w-full max-w-5xl flex-col rounded-xl border border-slate-300 bg-white text-xs shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 bg-slate-100 px-4 py-2.5">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-slate-800">📄 Expediente de Cotización</span>
                <span className="font-mono font-black text-blue-900 rounded bg-blue-100 px-2 py-0.5 text-xs">
                  {cotizacionDetalle.numero_cotizacion}
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  cotizacionDetalle.estado === 'APROBADA'
                    ? 'bg-emerald-100 text-emerald-800'
                    : cotizacionDetalle.estado === 'EMITIDA'
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-amber-100 text-amber-800'
                }`}>
                  {cotizacionDetalle.estado}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded font-bold flex items-center gap-1.5 cursor-pointer shadow-xs"
                >
                  🖨️ Imprimir / Guardar PDF
                </button>

                <button
                  type="button"
                  onClick={() => setMostrarModalEmail(!mostrarModalEmail)}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold flex items-center gap-1.5 cursor-pointer shadow-xs"
                >
                  ✉️ Enviar al Cliente
                </button>

                <button
                  type="button"
                  onClick={() => setModalVisorCotizacionAbierto(false)}
                  className="text-slate-400 hover:text-slate-600 text-lg font-bold ml-2 cursor-pointer"
                >
                  ✕
                </button>
              </div>
            </div>

            {mostrarModalEmail && (
              <form onSubmit={handleEnviarCotizacionPorCorreo} className="p-3 bg-emerald-50 border-b border-emerald-300 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-emerald-950 text-xs">✉️ Notificar Oferta Comercial al Cliente</span>
                  <button type="button" onClick={() => setMostrarModalEmail(false)} className="text-slate-400 hover:text-slate-600 font-bold">✕</button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[10px] font-bold text-slate-700 mb-0.5">Correo Destino (Cliente) *</label>
                    <input
                      type="email"
                      required
                      value={emailDestino}
                      onChange={e => setEmailDestino(e.target.value)}
                      placeholder="cliente@empresa.com"
                      className="w-full p-1.5 border border-slate-300 rounded bg-white text-xs font-semibold text-slate-900"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-700 mb-0.5">Asunto del Mensaje *</label>
                    <input
                      type="text"
                      required
                      value={asuntoEmail}
                      onChange={e => setAsuntoEmail(e.target.value)}
                      className="w-full p-1.5 border border-slate-300 rounded bg-white text-xs text-slate-900"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-700 mb-0.5">Cuerpo del Mensaje</label>
                  <textarea
                    rows="2"
                    value={mensajeEmail}
                    onChange={e => setMensajeEmail(e.target.value)}
                    className="w-full p-1.5 border border-slate-300 rounded bg-white text-xs text-slate-900 font-sans"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setMostrarModalEmail(false)}
                    className="px-3 py-1 bg-slate-200 hover:bg-slate-300 rounded font-semibold text-slate-700"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={enviandoEmail}
                    className="px-4 py-1 bg-emerald-700 hover:bg-emerald-800 text-white font-bold rounded shadow-xs"
                  >
                    {enviandoEmail ? 'Enviando…' : '🚀 Enviar Ahora'}
                  </button>
                </div>
              </form>
            )}

            <div className="flex-1 overflow-y-auto p-6 bg-slate-100">
              <div className="max-w-4xl mx-auto bg-white p-8 rounded-lg shadow-md border border-slate-300 font-sans text-slate-900 space-y-5">
                <div className="flex justify-between items-start border-b border-slate-300 pb-4">
                  <div>
                    <h1 className="text-xl font-black tracking-tight text-blue-900">HD Precision &amp; Technology</h1>
                    <p className="text-[10px] text-slate-500 font-medium">Mecanizado CNC de Alta Precisión · Fabricación &amp; Overhaul Industrial</p>
                    <p className="text-[10px] text-slate-400">NIT: 900.852.147-1 · Funza, Cundinamarca</p>
                  </div>
                  <div className="text-right">
                    <span className="font-extrabold text-xs text-slate-500 uppercase tracking-wider">Oferta Comercial</span>
                    <div className="text-xl font-mono font-black text-blue-900">{cotizacionDetalle.numero_cotizacion}</div>
                    <div className="text-[10px] text-slate-500 mt-0.5">Fecha Emisión: {cotizacionDetalle.fecha_emision}</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 bg-slate-50 p-3.5 rounded border border-slate-200 text-xs">
                  <div className="space-y-1">
                    <div><span className="font-bold text-slate-600">Cliente / Razón Social:</span> <strong className="text-slate-900">{cotizacionDetalle.cliente?.razon_social || cotizacionDetalle.id_socio}</strong></div>
                    <div><span className="font-bold text-slate-600">NIT / Identificación:</span> {cotizacionDetalle.cliente?.nit || 'N/A'}</div>
                    <div><span className="font-bold text-slate-600">Dirección:</span> {cotizacionDetalle.cliente?.direccion || 'Planta Principal'}</div>
                  </div>
                  <div className="space-y-1">
                    <div><span className="font-bold text-slate-600">E-mail Contacto:</span> {cotizacionDetalle.cliente?.email || 'N/A'}</div>
                    <div><span className="font-bold text-slate-600">Teléfono:</span> {cotizacionDetalle.cliente?.telefono || 'N/A'}</div>
                    <div><span className="font-bold text-slate-600">Condición de Pago:</span> {cotizacionDetalle.cliente?.condiciones_pago || '30 Días'}</div>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full border-collapse border border-slate-300 text-left text-xs">
                    <thead>
                      <tr className="bg-slate-100 font-bold border-b border-slate-300 text-slate-700">
                        <th className="p-2 border-r text-center w-12">#</th>
                        <th className="p-2 border-r w-28">Código / Ref</th>
                        <th className="p-2 border-r">Descripción del Ítem</th>
                        <th className="p-2 border-r text-center w-16">Cant.</th>
                        <th className="p-2 border-r text-right w-28">Valor Unit.</th>
                        <th className="p-2 text-right w-32">Subtotal</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {cotizacionDetalle.posiciones && cotizacionDetalle.posiciones.length > 0 ? (
                        cotizacionDetalle.posiciones.map((pos, idx) => (
                          <tr key={idx} className="hover:bg-slate-50">
                            <td className="p-2 border-r text-center font-mono text-slate-400">{(idx + 1) * 10}</td>
                            <td className="p-2 border-r font-mono font-bold text-purple-800">{pos.numero_producto}</td>
                            <td className="p-2 border-r font-semibold uppercase">{pos.descripcion}</td>
                            <td className="p-2 border-r text-center font-bold">{pos.cantidad}</td>
                            <td className="p-2 border-r text-right font-mono">$ {Number(pos.precio_unitario).toLocaleString('es-CO')}</td>
                            <td className="p-2 text-right font-mono font-bold text-slate-900">
                              $ {Number(pos.subtotal || pos.cantidad * pos.precio_unitario).toLocaleString('es-CO')}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="6" className="p-3 text-center text-slate-400">
                            Detalles incluidos en la oferta consolidada de la orden.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="flex justify-end pt-2">
                  <div className="w-72 space-y-1 text-right font-mono text-xs">
                    <div className="flex justify-between border-t-2 border-slate-800 pt-1.5 font-black text-sm text-blue-900">
                      <span>Total Oferta (COP):</span>
                      <span>$ {Number(cotizacionDetalle.valor_total).toLocaleString('es-CO')}</span>
                    </div>
                  </div>
                </div>

                {cotizacionDetalle.condiciones_comerciales && (
                  <div className="p-3 bg-slate-50 border rounded text-[11px] text-slate-600 leading-relaxed">
                    <strong className="block text-slate-800 mb-1 font-bold">CONDICIONES COMERCIALES Y PLAZOS:</strong>
                    <p className="whitespace-pre-line">{cotizacionDetalle.condiciones_comerciales}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end border-t border-slate-200 bg-slate-50 px-4 py-2.5">
              <button
                type="button"
                onClick={() => setModalVisorCotizacionAbierto(false)}
                className="rounded bg-slate-800 px-4 py-1.5 font-bold text-white hover:bg-slate-900 cursor-pointer"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL NUEVA COTIZACIÓN */}
      {modalNuevoCotizacionAbierto && (
        <ModalNuevaCotizacion
          isOpen={modalNuevoCotizacionAbierto}
          onClose={() => setModalNuevoCotizacionAbierto(false)}
          onCotizacionGuardada={(nuevaCot) => {
            setModalNuevoCotizacionAbierto(false);
            if (nuevaCot && nuevaCot.numero_cotizacion) {
              setCotizaciones(prev => [nuevaCot, ...prev]);
            }
            cargarProyectos();
          }}
        />
      )}

      {/* MODAL HISTORIAL Y TRAZABILIDAD */}
      <HistorialTimelineModal
        isOpen={modalHistorial.abierto}
        onClose={() => setModalHistorial(prev => ({ ...prev, abierto: false }))}
        tipoEntidad={modalHistorial.tipoEntidad}
        identificador={modalHistorial.identificador}
        tituloDoc={modalHistorial.tituloDoc}
      />
    </div>
  );
}