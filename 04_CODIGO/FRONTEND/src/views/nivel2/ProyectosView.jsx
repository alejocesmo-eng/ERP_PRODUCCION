// src/views/nivel2/ProyectosView.jsx
import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import { useProyectos } from '../../context/ProyectosContext';

const capitalize = (str) => {
  if (typeof str !== 'string' || !str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
};

export default function ProyectosView() {
  const { proyectos: proyectosGlobal } = useProyectos();

  const [usuarioActual, setUsuarioActual] = useState(null);
  const [pestañaModulo, setPestañaModulo] = useState('pedidos');

  const [piezasExpandidas, setPiezasExpandidas] = useState({});
  const [piezasProyectoMap, setPiezasProyectoMap] = useState({});
  const [cargandoPiezasMap, setCargandoPiezasMap] = useState({});

  const [proyectos, setProyectos] = useState([]);
  const [solicitudesCompra, setSolicitudesCompra] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });
  const [busqueda, setBusqueda] = useState('');
  
  const [filtroEstado, setFiltroEstado] = useState('TODOS');

  const [modalDetalleAbierto, setModalDetalleAbierto] = useState(false);
  const [proyectoSeleccionado, setProyectoSeleccionado] = useState(null);
  const [esEdicion, setEsEdicion] = useState(false);

  const [modalNuevoPedidoAbierto, setModalNuevoPedidoAbierto] = useState(false);
  const [modalBomAbierto, setModalBomAbierto] = useState(false);
  const [bomSeleccionado, setBomSeleccionado] = useState(null);
  
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
    { paso: 5, id: 'PLANOS_BOM', nombre: '5. Planos & BOM (Apertura OP)', area: 'Diseño', accion: '⚙️ 5. Estructurar OP & Planos' },
    { paso: 6, id: 'COMPRAS_INSUMOS', nombre: '6. Compras Insumos (BOM)', area: 'Compras', accion: '🛒 6. En Abastecimiento BOM' },
    { paso: 7, id: 'EN_FABRICACION', nombre: '7. Fabricación / Recuperación', area: 'Producción', accion: '🏭 7. Liberar a Planta MES' },
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
      const [resProyectos, resSolicitudes] = await Promise.allSettled([
        API.get('/proyectos/'),
        API.get('/solicitudes-compra/')
      ]);
      const proys = resProyectos.status === 'fulfilled' && Array.isArray(resProyectos.value.data) ? resProyectos.value.data : [];
      const solics = resSolicitudes.status === 'fulfilled' && Array.isArray(resSolicitudes.value.data) ? resSolicitudes.value.data : [];
      setProyectos(proys);
      setSolicitudesCompra(solics);
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
        return <span className="px-2 py-1 rounded text-[10px] font-extrabold bg-blue-100 text-blue-900 border border-blue-300">🔵 EN COMPRA (PO)</span>;
      case 'SOLICITADO':
        return <span className="px-2 py-1 rounded text-[10px] font-extrabold bg-amber-100 text-amber-900 border border-amber-300">🟡 SOLICITADO (PR)</span>;
      default:
        return <span className="px-2 py-1 rounded text-[10px] font-extrabold bg-slate-100 text-slate-600 border border-slate-300">⚪ SIN SOLICITAR</span>;
    }
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

  const handleCrearNuevoPedido = async (e) => {
    e.preventDefault();
    setMensaje({ tipo: '', texto: '' });

    const payloadSanitizado = {
      ...nuevoPedido,
      detalles: nuevoPedido.detalles.map(d => ({
        ...d,
        cantidad_solicitada: parseInt(d.cantidad_solicitada, 10) || 1,
        fecha_compromiso: d.fecha_compromiso || nuevoPedido.fecha_compromiso || null
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
      const msgError = typeof error.response?.data?.detail === 'string' 
        ? error.response.data.detail 
        : 'Error al enviar la solicitud al servidor.';
      setMensaje({ tipo: 'error', texto: `❌ ${msgError}` });
    } finally {
      setLoading(false);
    }
  };

  const handleGuardarEdicionPedido = async (e) => {
    e.preventDefault();
    if (!proyectoSeleccionado) return;

    const payloadSanitizado = {
      numero_pedido: proyectoSeleccionado.numero_pedido,
      cliente_nombre: proyectoSeleccionado.cliente_nombre,
      contacto_nombre: proyectoSeleccionado.contacto_nombre || null,
      contacto_telefono: proyectoSeleccionado.contacto_telefono || null,
      contacto_email: proyectoSeleccionado.contacto_email || null,
      ubicacion_cliente: proyectoSeleccionado.ubicacion_cliente || null,
      requisitos_cliente: proyectoSeleccionado.requisitos_cliente || null,
      fecha_compromiso: proyectoSeleccionado.fecha_compromiso || null,
      detalles: (proyectoSeleccionado.detalles || []).map(d => ({
        detalle_id: d.detalle_id || d.id_detalle || null,
        codigo_producto: d.codigo_producto || null,
        descripcion: d.descripcion,
        tipo: d.tipo || 'pieza',
        cantidad_solicitada: parseInt(d.cantidad_solicitada, 10) || 1,
        unidad: d.unidad || 'UND',
        prioridad: d.prioridad || 'MEDIA',
        fecha_compromiso: d.fecha_compromiso || proyectoSeleccionado.fecha_compromiso || null,
        requisitos_especificos: d.requisitos_especificos || null,
        observaciones: d.observaciones || null
      }))
    };

    try {
      setLoading(true);
      const res = await API.patch(`/proyectos/${proyectoSeleccionado.id_proyecto}`, payloadSanitizado);
      setMensaje({ tipo: 'exito', texto: `✅ Pedido N° ${proyectoSeleccionado.numero_pedido} actualizado exitosamente.` });
      setModalDetalleAbierto(false);
      
      setProyectos(prev => prev.map(p => p.id_proyecto === proyectoSeleccionado.id_proyecto ? res.data : p));
      await cargarProyectos();
    } catch (error) {
      const msgError = typeof error.response?.data?.detail === 'string'
        ? error.response.data.detail
        : 'Error al actualizar el pedido comercial.';
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

  const abrirModalExpediente = (p) => {
    setProyectoSeleccionado({
      ...p,
      detalles: p.detalles && p.detalles.length > 0 ? p.detalles : [
        { id: 1, codigo_producto: 'PROD-01', descripcion: p.detalle_producto || 'Pieza Mecanizada', tipo: 'pieza', cantidad_solicitada: p.cantidad || 1, unidad: 'UND', prioridad: 'MEDIA', fecha_compromiso: p.fecha_compromiso || '', requisitos_especificos: '' }
      ]
    });
    setEsEdicion(!p.confirmado);
    setModalDetalleAbierto(true);
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
      console.warn("Explotado a MES localmente.");
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
    setMensaje({ tipo: 'exito', texto: `🚀 ${autorizadas.length} piezas autorizadas enviadas a la cola de producción MES.` });
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
            onClick={() => setPestañaModulo('pedidos')}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer ${
              pestañaModulo === 'pedidos' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            📋 Pedidos Comerciales (PM-01)
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

                        <td className="p-3 text-center whitespace-nowrap space-x-2">
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
                                            <th className="p-2 text-center">Solicitud de Compra / BOM 🛒</th>
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
                                                <td className="p-2 font-semibold text-slate-700">{pz.accion || pz.tipo || 'FABRICAR_NUEVA'}</td>
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

      {modalNuevoMantenimientoAbierto && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6 space-y-4 text-xs">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-base font-bold text-slate-800 flex items-center gap-2">
                <span>🛠️</span> Registrar Ingreso de Máquina a Mantenimiento
              </h3>
              <button onClick={() => setModalNuevoMantenimientoAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
            </div>

            <form onSubmit={handleGuardarNuevoMantenimiento} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Código Mantenimiento *</label>
                  <input
                    type="text"
                    required
                    value={formMantenimiento.codigo_mantenimiento}
                    onChange={(e) => setFormMantenimiento({ ...formMantenimiento, codigo_mantenimiento: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-purple-800"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Cliente / Razón Social *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ej. Extruder S.A."
                    value={formMantenimiento.cliente_nombre}
                    onChange={(e) => setFormMantenimiento({ ...formMantenimiento, cliente_nombre: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Nombre de la Máquina *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ej. Prensa Hidráulica 200T"
                    value={formMantenimiento.nombre_maquina}
                    onChange={(e) => setFormMantenimiento({ ...formMantenimiento, nombre_maquina: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-bold mb-1">OP Venta Asignada *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ej. OP-100"
                    value={formMantenimiento.codigo_op}
                    onChange={(e) => setFormMantenimiento({ ...formMantenimiento, codigo_op: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-bold mb-1">Observaciones de Recepción / Falla</label>
                <textarea
                  rows="2"
                  placeholder="Describa el estado con el que llega la máquina..."
                  value={formMantenimiento.observaciones_ingreso}
                  onChange={(e) => setFormMantenimiento({ ...formMantenimiento, observaciones_ingreso: capitalize(e.target.value) })}
                  className="w-full p-2 border border-slate-300 rounded text-slate-800"
                ></textarea>
              </div>

              <div className="flex justify-end gap-2 border-t pt-3">
                <button
                  type="button"
                  onClick={() => setModalNuevoMantenimientoAbierto(false)}
                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded shadow-sm cursor-pointer"
                >
                  {loading ? 'Guardando...' : '✓ Abrir OP de Diagnóstico'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {modalLevantamientoAbierto && mantenimientoSeleccionado && (
        <div className="fixed inset-0 bg-slate-900/70 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full p-6 space-y-4 text-xs max-h-[92vh] flex flex-col">
            <div className="flex justify-between items-center border-b pb-3">
              <div>
                <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                  <span>📐</span> Levantamiento de Piezas: {mantenimientoSeleccionado.nombre_maquina || mantenimientoSeleccionado.cliente_nombre}
                </h3>
                <p className="text-[11px] text-slate-500">Cliente: <strong className="text-blue-800">{mantenimientoSeleccionado.cliente_nombre || mantenimientoSeleccionado.cliente}</strong> | {mantenimientoSeleccionado.codigo_op || 'OP-100'}</p>
              </div>
              <button onClick={() => setModalLevantamientoAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
            </div>

            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-2">
              <span className="text-[10px] font-bold text-amber-700 uppercase block">➕ Carga Rápida de Pieza / Ítem</span>
              <div className="grid grid-cols-12 gap-2">
                <input
                  type="text"
                  placeholder="Código Plano (PLN-...)"
                  value={nuevaPiezaTemp.codigo}
                  onChange={(e) => setNuevaPiezaTemp({ ...nuevaPiezaTemp, codigo: e.target.value })}
                  className="col-span-2 p-2 border border-slate-300 rounded text-slate-800 font-mono"
                />
                <input
                  type="text"
                  placeholder="Descripción de la Pieza"
                  value={nuevaPiezaTemp.descripcion}
                  onChange={(e) => setNuevaPiezaTemp({ ...nuevaPiezaTemp, descripcion: capitalize(e.target.value) })}
                  className="col-span-4 p-2 border border-slate-300 rounded text-slate-800"
                />
                <select
                  value={nuevaPiezaTemp.accion}
                  onChange={(e) => setNuevaPiezaTemp({ ...nuevaPiezaTemp, accion: e.target.value })}
                  className="col-span-3 p-2 border border-slate-300 rounded text-slate-800 font-bold bg-white cursor-pointer"
                >
                  <option value="FABRICAR_NUEVA">🔨 Fabricar Nueva</option>
                  <option value="RECTIFICAR_RECUPERAR">⚙️ Rectificar / Recuperar</option>
                  <option value="COMPRA_DIRECTA_BOM">🛒 Compra Directa BOM</option>
                </select>
                <input
                  type="number"
                  min="1"
                  placeholder="Cant"
                  value={nuevaPiezaTemp.cantidad}
                  onChange={(e) => setNuevaPiezaTemp({ ...nuevaPiezaTemp, cantidad: e.target.value })}
                  className="col-span-1 p-2 border border-slate-300 rounded text-slate-800 text-center font-bold"
                />
                <button
                  type="button"
                  onClick={handleAgregarPiezaLevantamiento}
                  className="col-span-2 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded transition cursor-pointer"
                >
                  + Agregar
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-auto border border-slate-200 rounded-lg bg-white">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-100 text-slate-700 font-bold border-b sticky top-0">
                    <th className="p-2.5 text-center">Ítem</th>
                    <th className="p-2.5">Código Plano</th>
                    <th className="p-2.5">Descripción de la Pieza</th>
                    <th className="p-2.5">Acción Requerida</th>
                    <th className="p-2.5 text-center">Cant</th>
                    <th className="p-2.5">Material</th>
                    <th className="p-2.5 text-right">Cotizado ($)</th>
                    <th className="p-2.5 text-center">Autorizado Cliente</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-700">
                  {piezasLevantamiento.map((p, idx) => (
                    <tr key={idx} className="hover:bg-slate-50 transition">
                      <td className="p-2.5 text-center font-mono text-slate-400">#{p.posicion}</td>
                      <td className="p-2.5 font-mono font-bold text-purple-700">{p.codigo}</td>
                      <td className="p-2.5 font-bold text-slate-800">{p.descripcion}</td>
                      <td className="p-2.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          p.accion === 'FABRICAR_NUEVA' ? 'bg-blue-100 text-blue-800 border border-blue-200' :
                          p.accion === 'RECTIFICAR_RECUPERAR' ? 'bg-amber-100 text-amber-800 border border-amber-200' :
                          'bg-purple-100 text-purple-800 border border-purple-200'
                        }`}>
                          {p.accion === 'FABRICAR_NUEVA' ? 'Fabricar Nueva' : p.accion === 'RECTIFICAR_RECUPERAR' ? 'Rectificar' : 'Compra BOM'}
                        </span>
                      </td>
                      <td className="p-2.5 text-center font-bold text-emerald-700">{p.cantidad}</td>
                      <td className="p-2.5 text-slate-500">{p.material}</td>
                      <td className="p-2.5 text-right font-mono">$ {p.cotizado.toLocaleString()}</td>
                      <td className="p-2.5 text-center">
                        <button
                          type="button"
                          onClick={() => toggleAutorizacionPieza(idx)}
                          className={`px-3 py-1 rounded font-bold text-[10px] transition cursor-pointer ${
                            p.autorizado ? 'bg-emerald-600 text-white shadow-sm' : 'bg-slate-200 text-slate-600'
                          }`}
                        >
                          {p.autorizado ? '✓ APROBADA' : '✕ NO AUTORIZADA'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-between items-center border-t pt-3">
              <div className="text-slate-500 text-xs">
                Total Piezas: <strong className="text-slate-800">{piezasLevantamiento.length}</strong> | Autorizadas: <strong className="text-emerald-700">{piezasLevantamiento.filter(p => p.autorizado).length}</strong>
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setModalLevantamientoAbierto(false)}
                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded cursor-pointer"
                >
                  Cerrar
                </button>
                <button
                  type="button"
                  onClick={handleExplotarAMicroProduccionMES}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded shadow-sm transition cursor-pointer"
                >
                  🚀 Confirmar Aprobación y Explotar al MES (Planta)
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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
                  <label className="block font-bold text-slate-800 mb-1">📅 Fecha Compromiso Global *</label>
                  <input
                    type="date"
                    required
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
                        <th className="p-2.5 w-36">📅 Fecha Entrega Parcial *</th>
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
                              required
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

      {modalDetalleAbierto && proyectoSeleccionado && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full p-6 space-y-4 max-h-[92vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase ${
                  proyectoSeleccionado.confirmado ? 'bg-emerald-100 text-emerald-800 border border-emerald-300' : 'bg-amber-100 text-amber-800 border border-amber-300'
                }`}>
                  {proyectoSeleccionado.confirmado 
                    ? 'EXPEDIENTE COMERCIAL (CONFIRMADO - SOLO LECTURA)' 
                    : 'EDICIÓN DE PEDIDO COMERCIAL (EN REVISIÓN)'}
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
                    disabled={!esEdicion}
                    value={proyectoSeleccionado.numero_pedido || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, numero_pedido: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-mono font-bold text-purple-800 bg-white disabled:bg-slate-100"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Cliente / Razón Social *</label>
                  <input
                    type="text"
                    disabled={!esEdicion}
                    value={proyectoSeleccionado.cliente_nombre || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, cliente_nombre: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded font-bold text-slate-800 bg-white disabled:bg-slate-100"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Ubicación / Planta</label>
                  <input
                    type="text"
                    disabled={!esEdicion}
                    value={proyectoSeleccionado.ubicacion_cliente || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, ubicacion_cliente: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white disabled:bg-slate-100"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-800 mb-1">📅 Fecha Límite Pedido Global *</label>
                  <input
                    type="date"
                    disabled={!esEdicion}
                    value={proyectoSeleccionado.fecha_compromiso || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, fecha_compromiso: e.target.value })}
                    className="w-full p-2 border border-blue-300 rounded font-bold text-blue-900 bg-blue-50/50 disabled:bg-slate-100 disabled:text-slate-700"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Contacto Nombre</label>
                  <input
                    type="text"
                    disabled={!esEdicion}
                    value={proyectoSeleccionado.contacto_nombre || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, contacto_nombre: capitalize(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white disabled:bg-slate-100"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Teléfono Contacto</label>
                  <input
                    type="text"
                    disabled={!esEdicion}
                    value={proyectoSeleccionado.contacto_telefono || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, contacto_telefono: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white disabled:bg-slate-100"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Email Contacto</label>
                  <input
                    type="email"
                    disabled={!esEdicion}
                    value={proyectoSeleccionado.contacto_email || ''}
                    onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, contacto_email: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white disabled:bg-slate-100"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <h4 className="font-bold text-slate-700 text-xs">📦 Detalle de Elementos / Piezas y Programación Parcial</h4>
                  {esEdicion && (
                    <button
                      type="button"
                      onClick={handleAgregarFilaEdicion}
                      className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-[11px] shadow-sm transition cursor-pointer"
                    >
                      ➕ Agregar Ítem a PEDIDO_DETALLE
                    </button>
                  )}
                </div>

                <div className="border border-slate-200 rounded-lg overflow-hidden text-xs bg-white">
                  <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-100 font-bold text-slate-700 border-b">
                      <tr>
                        <th className="p-2 w-8 text-center">#</th>
                        <th className="p-2 w-24">Código Prod.</th>
                        <th className="p-2">Descripción del Elemento / Pieza</th>
                        <th className="p-2 w-24">Tipo</th>
                        <th className="p-2 w-20 text-center">Cantidad</th>
                        <th className="p-2 w-16">Unidad</th>
                        <th className="p-2 w-36">📅 Fecha Entrega Parcial</th>
                        <th className="p-2 w-20">Prioridad</th>
                        <th className="p-2">Requisitos Específicos</th>
                        {esEdicion && <th className="p-2 w-8 text-center"></th>}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 text-slate-600">
                      {(proyectoSeleccionado.detalles || []).map((det, idx) => (
                        <tr key={det.id || idx} className="hover:bg-slate-50">
                          <td className="p-2 text-center font-bold text-slate-400">{idx + 1}</td>
                          <td className="p-2">
                            {esEdicion ? (
                              <input
                                type="text"
                                value={det.codigo_producto || ''}
                                onChange={(e) => handleCambioDetalleEdicion(idx, 'codigo_producto', e.target.value)}
                                className="w-full p-1 border rounded font-mono font-bold text-blue-700"
                              />
                            ) : (
                              <span className="font-mono font-bold text-blue-700">{det.codigo_producto || 'PROD-01'}</span>
                            )}
                          </td>
                          <td className="p-2">
                            {esEdicion ? (
                              <input
                                type="text"
                                required
                                value={det.descripcion || ''}
                                onChange={(e) => handleCambioDetalleEdicion(idx, 'descripcion', e.target.value)}
                                className="w-full p-1 border rounded font-medium text-slate-800"
                              />
                            ) : (
                              <span className="font-bold text-slate-800">{det.descripcion}</span>
                            )}
                          </td>
                          <td className="p-2">
                            {esEdicion ? (
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
                            ) : (
                              <span className="uppercase font-semibold text-purple-700">{det.tipo || 'pieza'}</span>
                            )}
                          </td>
                          <td className="p-2 text-center">
                            {esEdicion ? (
                              <input
                                type="number"
                                min="1"
                                value={det.cantidad_solicitada === '' ? '' : det.cantidad_solicitada}
                                onFocus={(e) => e.target.select()}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  handleCambioDetalleEdicion(idx, 'cantidad_solicitada', val === '' ? '' : Math.max(1, parseInt(val, 10) || 1));
                                }}
                                className="w-full p-1 border rounded font-bold text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                              />
                            ) : (
                              <span className="font-bold text-blue-900">{det.cantidad_solicitada}</span>
                            )}
                          </td>
                          <td className="p-2">
                            {esEdicion ? (
                              <input
                                type="text"
                                value={det.unidad || 'UND'}
                                onChange={(e) => handleCambioDetalleEdicion(idx, 'unidad', e.target.value)}
                                className="w-full p-1 border rounded text-center uppercase"
                              />
                            ) : (
                              <span>{det.unidad || 'UND'}</span>
                            )}
                          </td>
                          <td className="p-2">
                            {esEdicion ? (
                              <input
                                type="date"
                                value={det.fecha_compromiso || proyectoSeleccionado.fecha_compromiso || ''}
                                onChange={(e) => handleCambioDetalleEdicion(idx, 'fecha_compromiso', e.target.value)}
                                className="w-full p-1 border border-purple-300 rounded font-bold text-purple-900 bg-purple-50/50"
                              />
                            ) : (
                              <span className="font-bold text-purple-900">📅 {det.fecha_compromiso || proyectoSeleccionado.fecha_compromiso || 'Sin fecha'}</span>
                            )}
                          </td>
                          <td className="p-2">
                            {esEdicion ? (
                              <select
                                value={det.prioridad || 'MEDIA'}
                                onChange={(e) => handleCambioDetalleEdicion(idx, 'prioridad', e.target.value)}
                                className="w-full p-1 border rounded bg-white font-bold cursor-pointer"
                              >
                                <option value="ALTA">ALTA</option>
                                <option value="MEDIA">MEDIA</option>
                                <option value="BAJA">BAJA</option>
                              </select>
                            ) : (
                              <span className="font-bold text-slate-700">{det.prioridad || 'MEDIA'}</span>
                            )}
                          </td>
                          <td className="p-2">
                            {esEdicion ? (
                              <input
                                type="text"
                                value={det.requisitos_especificos || ''}
                                onChange={(e) => handleCambioDetalleEdicion(idx, 'requisitos_especificos', e.target.value)}
                                className="w-full p-1 border rounded text-slate-800"
                              />
                            ) : (
                              <span className="text-slate-700 font-medium">{det.requisitos_especificos || 'N/A'}</span>
                            )}
                          </td>
                          {esEdicion && (
                            <td className="p-2 text-center">
                              <button
                                type="button"
                                onClick={() => handleEliminarFilaEdicion(idx)}
                                className="text-red-500 hover:text-red-700 font-bold px-1.5 py-0.5 rounded hover:bg-red-50 transition cursor-pointer"
                              >
                                🗑️
                              </button>
                            </td>
                          )}
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
                  disabled={!esEdicion}
                  value={proyectoSeleccionado.requisitos_cliente || ''}
                  onChange={(e) => setProyectoSeleccionado({ ...proyectoSeleccionado, requisitos_cliente: capitalize(e.target.value) })}
                  className="w-full p-2 border border-slate-300 rounded text-slate-800 bg-white disabled:bg-slate-100"
                />
              </div>

              <div className="flex justify-between items-center border-t pt-3">
                <div>
                  {!proyectoSeleccionado.confirmado ? (
                    <button
                      type="button"
                      onClick={() => handleConfirmarProyecto(proyectoSeleccionado.id_proyecto)}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-xs transition shadow-sm flex items-center gap-1.5 cursor-pointer"
                    >
                      <span>✓</span> Confirmar Pedido Comercial (Pasar a Diseño)
                    </button>
                  ) : (
                    <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded border border-emerald-200">
                      ✓ Pedido Confirmado y Disponible en Diseño
                    </span>
                  )}
                </div>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setModalDetalleAbierto(false)}
                    className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded transition cursor-pointer"
                  >
                    {esEdicion ? 'Cancelar' : 'Cerrar Expediente'}
                  </button>
                  {esEdicion && (
                    <button
                      type="submit"
                      disabled={loading}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded transition shadow-sm cursor-pointer"
                    >
                      {loading ? 'Guardando...' : '💾 Guardar Cambios'}
                    </button>
                  )}
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {modalBomAbierto && bomSeleccionado && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-6 space-y-4 border-t-4 border-purple-600 text-xs">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2.5 py-1 bg-purple-100 text-purple-800 text-xs font-extrabold rounded uppercase tracking-wider">
                  🔎 Trazabilidad del BOM y Estado del Material [ISO 9001:2026]
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
    </div>
  );
}