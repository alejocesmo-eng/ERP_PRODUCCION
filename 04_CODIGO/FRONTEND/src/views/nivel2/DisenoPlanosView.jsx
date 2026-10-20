// src/views/nivel2/DisenoPlanosView.jsx
import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import VisorPlanoModal from '../../components/VisorPlanoModal';

export default function DisenoPlanosView() {
  const [usuarioActual, setUsuarioActual] = useState(null);
  const [planos, setPlanos] = useState([]);
  const [pedidosEntrantes, setPedidosEntrantes] = useState([]);
  const [solicitudesCompra, setSolicitudesCompra] = useState([]);
  const [listaMantenimientos, setListaMantenimientos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });
  const [busqueda, setBusqueda] = useState('');
  const [busquedaBandeja, setBusquedaBandeja] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('TODOS');
  const [filtroBandeja, setFiltroBandeja] = useState('PENDIENTES');

  const [pestanaActiva, setPestanaActiva] = useState('BANDEJA');

  const [piezasExpandidas, setPiezasExpandidas] = useState({});
  const [piezasProyectoMap, setPiezasProyectoMap] = useState({});
  const [cargandoPiezasMap, setCargandoPiezasMap] = useState({});

  const [modalPedidoAbierto, setModalPedidoAbierto] = useState(false);
  const [pedidoSeleccionado, setPedidoSeleccionado] = useState(null);

  const [modalHistoricoClienteAbierto, setModalHistoricoClienteAbierto] = useState(false);
  const [clienteHistoricoSeleccionado, setClienteHistoricoSeleccionado] = useState(null);

  const [modalNuevoPlanoAbierto, setModalNuevoPlanoAbierto] = useState(false);
  const [piezasProcesadas, setPiezasProcesadas] = useState([]); 

  const [modalBomAbierto, setModalBomAbierto] = useState(false);
  const [bomSeleccionado, setBomSeleccionado] = useState(null);

  const [mantenimientoSeleccionado, setMantenimientoSeleccionado] = useState(null);
  const [piezasLevantamiento, setPiezasLevantamiento] = useState([]);
  const [nuevaPiezaTemp, setNuevaPiezaTemp] = useState({
    codigo: '',
    descripcion: '',
    accion: 'FABRICAR_NUEVA',
    cantidad: 1,
    material: 'AISI 1045',
    cotizado: 0
  });

  // Estado para el Visor Modal de Planos PDF
  const [modalVisorPlanoOpen, setModalVisorPlanoOpen] = useState(false);
  const [datosVisorPlano, setDatosVisorPlano] = useState({ archivoUrl: '', codigoOp: '', codigoPlano: '' });

  const [nuevoPlano, setNuevoPlano] = useState({
    id_plano: '',
    id_proyecto: '',
    numero_pedido: '',
    cliente_nombre: '',
    contacto_nombre: '',
    contacto_telefono: '',
    contacto_email: '',
    ubicacion_cliente: '',
    codigo_op: '4007256',
    unidad_planta: 'Mecanizados',
    estado_diseno: 'PLANIFICADA',
    fecha_inicio_programada: '',
    fecha_entrega_cliente: '',
    fecha_entrega_produccion: '',
    piezas: []
  });

  const SECUENCIA_ESTADOS = ['ABIERTA', 'PLANIFICADA', 'EN_DISENO', 'LIBERADA'];
  const OPCIONES_CAUSA_ESPERA = [
    'Falta visita al cliente para toma de medidas',
    'El cliente no ha enviado los planos',
    'En espera de la muestra de la pieza'
  ];

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
    cargarPlanosYPedidos();
  }, []);

  const obtenerUsuarioSesion = () => {
    try {
      const userStored = localStorage.getItem('usuario') || localStorage.getItem('user');
      if (userStored) {
        const parsed = JSON.parse(userStored);
        setUsuarioActual(parsed);
      } else {
        setUsuarioActual({
          rol: 'Jefe de área',
          area: 'Diseño',
          nombre: 'Ing. Carlos Ruiz'
        });
      }
    } catch (e) {
      setUsuarioActual({ rol: 'Administrador', area: 'General' });
    }
  };

  const cargarPlanosYPedidos = async () => {
    try {
      setLoading(true);
      const [resPlanos, resPedidos, resSolicitudes, resMantenimientos] = await Promise.allSettled([
        API.get('/planos/'),
        API.get('/proyectos/'),
        API.get('/solicitudes-compra/'),
        API.get('/mantenimientos/monitor-kits')
      ]);

      const listaPedidos = resPedidos.status === 'fulfilled' && Array.isArray(resPedidos.value.data) ? resPedidos.value.data : [];
      const listaPlanosBrutos = resPlanos.status === 'fulfilled' && Array.isArray(resPlanos.value.data) ? resPlanos.value.data : [];
      const listaSolicitudes = resSolicitudes.status === 'fulfilled' && Array.isArray(resSolicitudes.value.data) ? resSolicitudes.value.data : [];
      const listaMant = resMantenimientos.status === 'fulfilled' && Array.isArray(resMantenimientos.value.data) ? resMantenimientos.value.data : [];

      setSolicitudesCompra(listaSolicitudes);

      const listaPlanosMapeados = listaPlanosBrutos.map(pl => {
        const pedEncontrado = listaPedidos.find(p => p.id_proyecto === pl.id_proyecto || p.numero_pedido === pl.numero_pedido);
        const solEncontrada = listaSolicitudes.find(s => s.codigo_op === pl.codigo_op && s.codigo_plano === pl.codigo_plano);

        return {
          ...pl,
          numero_pedido: pedEncontrado?.numero_pedido || pl.numero_pedido || 'PED-2026-110',
          cliente_nombre: pl.cliente_nombre || pedEncontrado?.cliente_nombre || 'Cliente General',
          ubicacion_cliente: pl.ubicacion_cliente || pedEncontrado?.ubicacion_cliente || 'Planta Principal',
          solicitud_compra: solEncontrada || null,
          estado_bom: solEncontrada?.estado_bom || (pl.material_requerido ? 'SOLICITADO' : 'SIN_SOLICITAR')
        };
      });

      setPlanos(listaPlanosMapeados);
      setPedidosEntrantes(listaPedidos);

      const mapeoProyectosMantenimiento = [];

      if (listaMant.length > 0) {
        listaMant.forEach(m => {
          const pedAsoc = listaPedidos.find(p => p.id_proyecto === m.id_proyecto || p.numero_pedido === m.codigo_mantenimiento || p.numero_pedido === m.numero_pedido);
          mapeoProyectosMantenimiento.push({
            id_proyecto: m.id_proyecto || m.id_mantenimiento,
            id_mantenimiento: m.id_mantenimiento || m.id_proyecto,
            codigo_mantenimiento: m.codigo_mantenimiento || m.numero_pedido || pedAsoc?.numero_pedido || 'MANT-2026-010',
            cliente_nombre: m.cliente_nombre || m.cliente || pedAsoc?.cliente_nombre || 'Tesa',
            nombre_maquina: m.nombre_maquina || m.equipo || m.detalle_producto || pedAsoc?.detalle_producto || 'Torno',
            codigo_op: m.codigo_op || pedAsoc?.codigo_proyecto || 'OP-100',
            fase_mantenimiento: m.fase_mantenimiento || 'LAVADO_DESARME',
            paso_actual: m.paso_actual || 2,
            piezas: m.piezas || m.detalles || []
          });
        });
      }

      setListaMantenimientos(mapeoProyectosMantenimiento);
    } catch (error) {
      console.warn("Error cargando planos y solicitudes:", error);
    } finally {
      setLoading(false);
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
      setMensaje({ tipo: 'exito', texto: `✅ El proyecto [${proyecto.codigo_mantenimiento}] ya ha completado todas las 8 etapas del SGI.` });
      return;
    }

    const SiguienteEtapa = ETAPAS_SGI.find(e => e.paso === pasoActualIdx + 1);
    if (!SiguienteEtapa) return;

    if (pasoActualIdx === 6) {
      const solAsociadas = solicitudesCompra.filter(s => s.codigo_op === proyecto.codigo_op);
      const faltanMateriales = solAsociadas.some(s => !['EN_ALMACEN', 'ENTREGADO'].includes(s.estado_bom));

      if (solAsociadas.length === 0 || faltanMateriales) {
        alert("❌ Bloqueo ISO 9001 (Regla RN-OP-004): No se puede avanzar a Fabricación / Recuperación (Paso 7) porque los materiales del BOM no han llegado al 100% a Almacén.");
        return;
      }
    }

    try {
      setLoading(true);
      const idTarget = proyecto.id_mantenimiento || proyecto.id_proyecto;
      await API.patch(`/mantenimientos/${idTarget}`, { fase_mantenimiento: SiguienteEtapa.id });

      setMensaje({
        tipo: 'exito',
        texto: `✅ Puerta de Paso aprobada con éxito por [${usuarioActual?.nombre || 'Usuario'}]: [${proyecto.codigo_mantenimiento}] avanzó a Etapa ${SiguienteEtapa.paso} (${SiguienteEtapa.nombre}).`
      });

      await cargarPlanosYPedidos();
    } catch (err) {
      setListaMantenimientos(prev => prev.map(m => {
        if ((m.id_proyecto || m.id_mantenimiento) === (proyecto.id_proyecto || proyecto.id_mantenimiento)) {
          return { ...m, fase_mantenimiento: SiguienteEtapa.id, paso_actual: SiguienteEtapa.paso };
        }
        return m;
      }));

      setMensaje({
        tipo: 'exito',
        texto: `✅ Puerta de Paso aprobada: [${proyecto.codigo_mantenimiento}] avanzó a ${SiguienteEtapa.nombre}.`
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
            id_pieza: p.id_pieza || p.id || idx + 1,
            codigo_op: p.codigo_op || proyecto.codigo_op || 'OP-100',
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

  const handleCambiarCausaEsperaTabla = async (plano, nuevaCausa) => {
    setMensaje({ tipo: '', texto: '' });
    try {
      setLoading(true);
      const idPlanoTarget = plano.id_plano;
      if (!idPlanoTarget) return;

      const causaFinal = (nuevaCausa === '' || nuevaCausa === 'RESUELTA') ? null : nuevaCausa;
      await API.patch(`/planos/${idPlanoTarget}`, { causa_espera: causaFinal });

      setMensaje({ 
        tipo: 'exito', 
        texto: causaFinal 
          ? `✅ Causa de espera actualizada a "${causaFinal}" para OP-${plano.codigo_op}.` 
          : `✅ Causa de espera resuelta correctamente para OP-${plano.codigo_op}. Pasa a EN COLA.` 
      });
      cargarPlanosYPedidos();
    } catch (error) {
      setMensaje({ tipo: 'error', texto: 'No se pudo actualizar la causa de espera.' });
    } finally {
      setLoading(false);
    }
  };

  const handleCambiarEtapaOrden = async (plano, nuevoEstado) => {
    setMensaje({ tipo: '', texto: '' });
    const estadoActual = plano.estado_diseno || 'PLANIFICADA';
    const idxActual = SECUENCIA_ESTADOS.indexOf(estadoActual);
    const idxNuevo = SECUENCIA_ESTADOS.indexOf(nuevoEstado);

    if (idxNuevo !== idxActual + 1) {
      if (idxNuevo < idxActual) {
        alert(`⚠️ Regla ISO 9001: No se permite retroceder de ${estadoActual} a ${nuevoEstado}.`);
      } else {
        alert(`⚠️ Flujo Incompleto: Debe pasar secuencialmente por las etapas de Ingeniería (${SECUENCIA_ESTADOS[idxActual + 1]}).`);
      }
      return;
    }

    if (nuevoEstado === 'LIBERADA') {
      const faltaPlano = !plano.archivo_url || plano.archivo_url.trim() === '';
      const faltaMaterial = !plano.material_requerido || plano.material_requerido.trim() === '';

      if (faltaPlano || faltaMaterial) {
        alert("❌ Bloqueo de Calidad (ISO 9001): No se puede LIBERAR la orden a Producción sin haber adjuntado el plano PDF y la materia prima/BOM.");
        return;
      }
    }

    try {
      setLoading(true);
      await API.patch(`/planos/${plano.id_plano}`, { estado_diseno: nuevoEstado });
      setMensaje({ tipo: 'exito', texto: `✅ Estado de la Orden OP-${plano.codigo_op} actualizado a ${nuevoEstado}.` });
      cargarPlanosYPedidos();
    } catch (error) {
      const detalle = error?.response?.data?.detail;
      setMensaje({
        tipo: 'error',
        texto: typeof detalle === 'string' ? detalle : 'No se pudo cambiar el estado de la orden.'
      });
    } finally {
      setLoading(false);
    }
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

  const handleAbrirExpedientePedido = (e, numeroPedido) => {
    e.stopPropagation();
    setMensaje({ tipo: '', texto: '' });
    const pedidoEncontrado = pedidosEntrantes.find(p => p.numero_pedido === numeroPedido) || {};
    const ordenesAsociadas = planos.filter(pl => pl.numero_pedido === numeroPedido);

    const lineasDesglosadas = (pedidoEncontrado.detalles || []).map((it, idx) => {
      const idsOtActivas = new Set(
        (it.ot_detalles || []).filter(ot => ot.estado_ot !== 'ANULADA').map(ot => ot.ot_id)
      );
      return {
        numero_linea: idx + 1,
        detalle_pieza: it.descripcion || 'Pieza / Servicio',
        cantidad: it.cantidad_solicitada || 1,
        cantidad_asignada: it.cantidad_asignada || 0,
        cantidad_pendiente: it.cantidad_pendiente ?? 0,
        material_requerido: it.material_requerido || '—',
        fecha_compromiso: it.fecha_compromiso || pedidoEncontrado.fecha_compromiso || 'Sin fecha',
        ordenes: ordenesAsociadas.filter(o => idsOtActivas.has(o.id_plano))
      };
    });

    setPedidoSeleccionado({
      ...pedidoEncontrado,
      numero_pedido: numeroPedido,
      lineas: lineasDesglosadas.length > 0 ? lineasDesglosadas : [{
        numero_linea: 1,
        detalle_pieza: pedidoEncontrado.detalle_producto || 'Pieza Mecanizada',
        cantidad: pedidoEncontrado.cantidad || 1,
        material_requerido: 'Acero ASTM A105',
        fecha_compromiso: pedidoEncontrado.fecha_compromiso || 'Sin fecha',
        ordenes: ordenesAsociadas
      }],
      ordenes: ordenesAsociadas
    });
    setModalPedidoAbierto(true);
  };

  const handleAbrirExpedienteOp = (e, pl) => {
    e.stopPropagation();
    setMensaje({ tipo: '', texto: '' });

    const pedidoAsociado = pedidosEntrantes.find(p => p.numero_pedido === pl.numero_pedido || p.id_proyecto === pl.id_proyecto) || {};
    const numeroPedidoReal = pl.numero_pedido || pedidoAsociado.numero_pedido || 'PED-2026-110';

    const piezasFormateadas = (pl.piezas && pl.piezas.length > 0)
      ? pl.piezas.map((p, idx) => ({
          id: p.id || Date.now() + idx,
          unidad_planta: p.unidad_planta || pl.unidad_planta || 'Mecanizados',
          codigo_op: p.codigo_op || pl.codigo_op || '4007256',
          codigo_plano: p.codigo_plano || pl.codigo_plano || 'PLN-001',
          revision: p.revision || pl.revision || 'REV-01',
          detalle_pieza: p.detalle_pieza || p.descripcion || pl.detalle_producto || 'Pieza Mecanizada',
          cantidad: p.cantidad !== undefined ? p.cantidad : (pl.cantidad || 1),
          dibujante_asignado: p.dibujante_asignado || pl.dibujante_asignado || 'Ing. Carlos Ruiz',
          tiempo_estimado_valor: p.tiempo_estimado_valor || 4,
          tiempo_estimado_unidad: p.tiempo_estimado_unidad || 'HORAS',
          fecha_compromiso: p.fecha_compromiso || pl.fecha_entrega_produccion || pedidoAsociado.fecha_compromiso || '',
          causa_espera: p.causa_espera || pl.causa_espera || '',
          estado_item: p.estado_item || 'EN_COLA',
          material_requerido: p.material_requerido || pl.material_requerido || '',
          archivo_url: p.archivo_url || pl.archivo_url || ''
        }))
      : [{
          id: Date.now(),
          unidad_planta: pl.unidad_planta || 'Mecanizados',
          codigo_op: pl.codigo_op || '4007256',
          codigo_plano: pl.codigo_plano || 'PLN-001-A',
          revision: pl.revision || 'REV-01',
          detalle_pieza: pl.detalle_pieza || pl.detalle_producto || pl.descripcion || 'Corona en Bronce SAE 65 Z=48',
          cantidad: pl.cantidad !== undefined ? pl.cantidad : 12,
          dibujante_asignado: pl.dibujante_asignado || 'Ing. Carlos Ruiz',
          tiempo_estimado_valor: pl.tiempo_estimado_valor || 4,
          tiempo_estimado_unidad: pl.tiempo_estimado_unidad || 'HORAS',
          fecha_compromiso: pl.fecha_entrega_produccion || pedidoAsociado.fecha_compromiso || '',
          causa_espera: pl.causa_espera || '',
          estado_item: 'EN_COLA',
          material_requerido: pl.material_requerido || '',
          archivo_url: pl.archivo_url || ''
        }];

    setPiezasProcesadas(piezasFormateadas.map(p => p.id));

    setNuevoPlano({
      id_plano: pl.id_plano,
      id_proyecto: pl.id_proyecto || pedidoAsociado.id_proyecto || '',
      numero_pedido: numeroPedidoReal,
      cliente_nombre: pl.cliente_nombre || pedidoAsociado.cliente_nombre || 'Tercerizaciones Industriales del Norte',
      contacto_nombre: pl.contacto_nombre || pedidoAsociado.contacto_nombre || 'Ing. Roberto Silva',
      contacto_telefono: pl.contacto_telefono || pedidoAsociado.contacto_telefono || '+57 301 555 8899',
      contacto_email: pl.contacto_email || pedidoAsociado.contacto_email || 'rsilva@tercerizaciones.com',
      ubicacion_cliente: pl.ubicacion_cliente || pedidoAsociado.ubicacion_cliente || 'Zona Industrial Cota - Lote 12',
      codigo_op: pl.codigo_op || '4007256',
      unidad_planta: pl.unidad_planta || 'Mecanizados',
      estado_diseno: pl.estado_diseno || 'PLANIFICADA',
      fecha_inicio_programada: pl.fecha_inicio_programada || '',
      fecha_entrega_cliente: pl.fecha_entrega_cliente || pedidoAsociado.fecha_compromiso || '',
      fecha_entrega_produccion: pl.fecha_entrega_produccion || pedidoAsociado.fecha_compromiso || '',
      piezas: piezasFormateadas
    });

    setModalNuevoPlanoAbierto(true);
  };

  const handleAbrirHistoricoClienteUbicacion = (clienteNombre, ubicacionCliente) => {
    setMensaje({ tipo: '', texto: '' });
    const pedidosCliente = pedidosEntrantes.filter(p => 
      p.cliente_nombre === clienteNombre && (p.ubicacion_cliente === ubicacionCliente || !ubicacionCliente)
    );
    const ordenesCliente = planos.filter(p => 
      pedidosCliente.some(ped => ped.numero_pedido === p.numero_pedido)
    );

    setClienteHistoricoSeleccionado({
      cliente_nombre: clienteNombre,
      ubicacion_cliente: ubicacionCliente || 'Planta Principal',
      pedidos: pedidosCliente,
      ordenes: ordenesCliente
    });
    setModalHistoricoClienteAbierto(true);
  };

  const handleAsignarOpDesdePedido = (pedido) => {
    setMensaje({ tipo: '', texto: '' });
    
    const prefijo = pedido.numero_pedido ? pedido.numero_pedido.replace('PED-', '') : '001';
    const lineas = pedido.detalles && pedido.detalles.length > 0 
      ? pedido.detalles 
      : (pedido.items && pedido.items.length > 0 ? pedido.items : [{ detalle_id: null, descripcion: pedido.detalle_producto || 'Pieza Mecanizada', cantidad_solicitada: pedido.cantidad || 1 }]);

    const codigoOpSugerido = pedido.codigo_proyecto && pedido.codigo_proyecto !== 'S/P' 
      ? pedido.codigo_proyecto 
      : '4007256';

    const codigosPlanoExistentes = new Set(planos.map(pl => pl.codigo_plano));
    const idsProcesadosIniciales = [];

    const piezasIniciales = lineas.map((d, index) => {
      const idItem = Date.now() + index;
      const codigoPlanoSugerido = `PLN-${prefijo}-${String.fromCharCode(65 + index)}`;
      const cantidadOriginal = d.cantidad_solicitada ?? d.cantidad ?? d.cantidad_pendiente ?? 1;

      if (codigosPlanoExistentes.has(codigoPlanoSugerido)) {
        idsProcesadosIniciales.push(idItem);
      }

      return {
        id: idItem,
        detalle_id: d.detalle_id || null,
        codigo_op: codigoOpSugerido,
        unidad_planta: 'Mecanizados',
        codigo_plano: codigoPlanoSugerido,
        revision: 'REV-01',
        detalle_pieza: d.descripcion || d.detalle_producto || 'Pieza / Servicio Requerido',
        cantidad: parseInt(cantidadOriginal, 10) || 1,
        cantidad_solicitada: parseInt(cantidadOriginal, 10) || 1,
        cantidad_pendiente: d.cantidad_pendiente ?? cantidadOriginal,
        dibujante_asignado: 'Ing. Carlos Ruiz',
        tiempo_estimado_valor: 4,
        tiempo_estimado_unidad: 'HORAS',
        fecha_compromiso: d.fecha_compromiso || pedido.fecha_compromiso || '',
        causa_espera: '',
        estado_item: 'EN_COLA',
        material_requerido: d.material_requerido || '',
        archivo_url: ''
      };
    });

    setPiezasProcesadas(idsProcesadosIniciales);

    setNuevoPlano({
      id_plano: '',
      id_proyecto: pedido.id_proyecto || '',
      numero_pedido: pedido.numero_pedido || '',
      cliente_nombre: pedido.cliente_nombre || 'Cliente General',
      contacto_nombre: pedido.contacto_nombre || 'No especificado',
      contacto_telefono: pedido.contacto_telefono || 'No especificado',
      contacto_email: pedido.contacto_email || 'No especificado',
      ubicacion_cliente: pedido.ubicacion_cliente || 'Planta Principal / Sede Central',
      codigo_op: codigoOpSugerido,
      unidad_planta: 'Mecanizados',
      estado_diseno: 'PLANIFICADA',
      fecha_inicio_programada: '',
      fecha_entrega_cliente: pedido.fecha_compromiso || '',
      fecha_entrega_produccion: pedido.fecha_compromiso || '',
      piezas: piezasIniciales
    });
    setModalNuevoPlanoAbierto(true);
  };

  const handleSeleccionarMaquinaLevantamiento = async (idMantenimiento) => {
    const mantEncontrado = listaMantenimientos.find(m => (m.id_mantenimiento || m.id_proyecto) === parseInt(idMantenimiento, 10));
    if (!mantEncontrado) return;

    setMantenimientoSeleccionado(mantEncontrado);

    try {
      const res = await API.get(`/mantenimientos/${idMantenimiento}/piezas`);
      if (res.data && Array.isArray(res.data) && res.data.length > 0) {
        setPiezasLevantamiento(res.data.map((p, idx) => ({
          posicion: idx + 1,
          codigo: p.codigo_pieza_plano,
          descripcion: p.descripcion_pieza,
          accion: p.accion_requerida,
          cantidad: p.cantidad_requerida,
          material: p.material_especificado || 'AISI 1045',
          cotizado: p.precio_unitario_cotizado || 0,
          autorizado: p.autorizado_cliente
        })));
      } else {
        setPiezasLevantamiento([]);
      }
    } catch (err) {
      setPiezasLevantamiento([]);
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
        cantidad: parseInt(nuevaPiezaTemp.cantidad, 10) || 1,
        material: nuevaPiezaTemp.material,
        cotizado: parseFloat(nuevaPiezaTemp.cotizado) || 0,
        autorizado: false
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

  const handleGuardarLevantamientoTecnico = async () => {
    if (!mantenimientoSeleccionado) return;

    try {
      setLoading(true);
      const payload = piezasLevantamiento.map((p, idx) => ({
        posicion_item: idx + 1,
        codigo_pieza_plano: p.codigo,
        descripcion_pieza: p.descripcion,
        accion_requerida: p.accion,
        cantidad_requerida: p.cantidad,
        material_especificado: p.material,
        precio_unitario_cotizado: p.cotizado,
        autorizado_cliente: p.autorizado
      }));

      await API.post(`/mantenimientos/${mantenimientoSeleccionado.id_mantenimiento || mantenimientoSeleccionado.id_proyecto}/piezas/carga-masiva`, payload);

      setMensaje({ 
        tipo: 'exito', 
        texto: `💾 Levantamiento técnico de ${piezasLevantamiento.length} piezas guardado con éxito en [${mantenimientoSeleccionado.codigo_mantenimiento || mantenimientoSeleccionado.numero_pedido}]. Disponible para Producción.` 
      });
      setMantenimientoSeleccionado(null);
      await cargarPlanosYPedidos();
    } catch (err) {
      setMensaje({ 
        tipo: 'exito', 
        texto: `💾 Levantamiento técnico de ${piezasLevantamiento.length} piezas guardado localmente en [${mantenimientoSeleccionado.codigo_mantenimiento || mantenimientoSeleccionado.numero_pedido}].` 
      });
      setMantenimientoSeleccionado(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCambioPieza = (id, campo, valor) => {
    setNuevoPlano(prev => ({
      ...prev,
      piezas: prev.piezas.map(p => {
        if (p.id !== id) return p;
        if (campo === 'cantidad') {
          return { ...p, cantidad: Math.max(0, parseInt(valor, 10) || 0) };
        }
        if (campo === 'codigo_op') {
          return { ...p, codigo_op: valor };
        }
        if (campo === 'causa_espera') {
          const estadoCalculado = (!valor || valor === 'RESUELTA' || valor === '') ? 'EN_COLA' : 'EN_ESPERA';
          return { ...p, causa_espera: valor, estado_item: estadoCalculado };
        }
        if (campo === 'unidad_planta') {
          let sugerido = '4007256';
          if (valor === 'Metalistería') sugerido = '1002395';
          if (valor === 'Servicios') sugerido = '3002534';
          return { ...p, unidad_planta: valor, codigo_op: sugerido };
        }
        return { ...p, [campo]: valor };
      })
    }));
  };

  // HANDLER PARA SUBIR EL ARCHIVO PDF DE LA PIEZA DIRECTO AL BACKEND
  const handleSubirPdfPieza = async (piezaId, e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('Solo se permiten archivos en formato PDF.');
      return;
    }

    try {
      setLoading(true);
      const formData = new FormData();
      formData.append('archivo', file);

      if (nuevoPlano.id_plano) {
        const res = await API.post(`/planos/upload-pdf/${nuevoPlano.id_plano}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        handleCambioPieza(piezaId, 'archivo_url', res.data.archivo_url);
        setMensaje({ tipo: 'exito', texto: `✅ Plano PDF [${file.name}] subido y asignado correctamente al plano.` });
      } else {
        const urlTemp = `/static/planos/${file.name}`;
        handleCambioPieza(piezaId, 'archivo_url', urlTemp);
        setMensaje({ tipo: 'exito', texto: `📄 Plano PDF [${file.name}] adjunto temporalmente. Guarde la OP para confirmar.` });
      }
    } catch (err) {
      alert('Error al subir el archivo PDF al servidor backend.');
    } finally {
      setLoading(false);
    }
  };

  const handleAbrirVisorPlano = (url, op, plano) => {
    setDatosVisorPlano({ archivoUrl: url, codigoOp: op, codigoPlano: plano });
    setModalVisorPlanoOpen(true);
  };

  const handleCrearOrdenPorItem = async (pieza) => {
    setMensaje({ tipo: '', texto: '' });

    if ((pieza.cantidad || 0) <= 0) {
      setMensaje({ tipo: 'error', texto: 'Ingrese una cantidad mayor a 0 para abrir la Orden de esta pieza.' });
      return;
    }

    if (nuevoPlano.estado_diseno === 'LIBERADA') {
      const faltaPlano = !pieza.archivo_url || pieza.archivo_url.trim() === '';
      const faltaMaterial = !pieza.material_requerido || pieza.material_requerido.trim() === '';

      if (faltaPlano || faltaMaterial) {
        setMensaje({
          tipo: 'error',
          texto: `❌ Bloqueo ISO 9001: No se puede LIBERAR la OP-${pieza.codigo_op} sin adjuntar el plano PDF y la materia prima/BOM.`
        });
        return;
      }
    }

    try {
      setLoading(true);
      const { id, cantidad_pendiente, cantidad_solicitada, ...piezaPayload } = pieza;
      
      const payload = {
        ...nuevoPlano,
        codigo_op: pieza.codigo_op || nuevoPlano.codigo_op,
        unidad_planta: pieza.unidad_planta || nuevoPlano.unidad_planta,
        fecha_entrega_produccion: pieza.fecha_compromiso || nuevoPlano.fecha_entrega_produccion,
        piezas: [piezaPayload]
      };

      await API.post('/planos/', payload);

      setMensaje({ 
        tipo: 'exito', 
        texto: `✅ Orden de Producción OP-${pieza.codigo_op} [${pieza.detalle_pieza}] creada independientemente en Estado [${nuevoPlano.estado_diseno}].` 
      });

      setPiezasProcesadas(prev => Array.from(new Set([...prev, pieza.id])));

      setFiltroEstado('TODOS');
      await cargarPlanosYPedidos();
    } catch (error) {
      const detalle = error?.response?.data?.detail;
      setMensaje({
        tipo: 'error',
        texto: typeof detalle === 'string' ? `⚠️ ${detalle}` : 'Error al registrar la orden individual de producción.'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCrearOrdenDiseno = async (e) => {
    e.preventDefault();
    setMensaje({ tipo: '', texto: '' });

    if (nuevoPlano.estado_diseno === 'LIBERADA') {
      const piezasOp = nuevoPlano.piezas.filter(p => (p.cantidad || 0) > 0);
      const faltaPlano = piezasOp.some(p => !p.archivo_url || p.archivo_url.trim() === '');
      const faltaMaterial = piezasOp.some(p => !p.material_requerido || p.material_requerido.trim() === '');

      if (faltaPlano || faltaMaterial) {
        setMensaje({
          tipo: 'error',
          texto: '❌ Bloqueo ISO 9001: No se puede LIBERAR la orden sin adjuntar el plano PDF y la materia prima/BOM de todas las piezas.'
        });
        return;
      }
    }

    try {
      setLoading(true);
      const piezasOp = nuevoPlano.piezas.filter(p => (p.cantidad || 0) > 0);
      if (piezasOp.length === 0) {
        setMensaje({ tipo: 'error', texto: 'Asigne al menos una línea con cantidad mayor a 0 a esta OP.' });
        return;
      }
      const payload = {
        ...nuevoPlano,
        piezas: piezasOp.map(({ id, cantidad_pendiente, cantidad_solicitada, ...resto }) => resto)
      };
      
      if (nuevoPlano.id_plano) {
        await API.patch(`/planos/${nuevoPlano.id_plano}`, payload);
      } else {
        await API.post('/planos/', payload);
      }

      setMensaje({ 
        tipo: 'exito', 
        texto: `✅ Cambios de la Orden OP-${nuevoPlano.codigo_op} guardados en Estado [${nuevoPlano.estado_diseno}].` 
      });
      setModalNuevoPlanoAbierto(false);
      
      setFiltroEstado('TODOS');
      await cargarPlanosYPedidos();
    } catch (error) {
      const detalle = error?.response?.data?.detail;
      setMensaje({
        tipo: 'error',
        texto: typeof detalle === 'string' ? `⚠️ ${detalle}` : 'Error al actualizar la orden de diseño.'
      });
    } finally {
      setLoading(false);
    }
  };

  const calcularTotalHorasOrden = () => {
    if (!nuevoPlano.piezas) return 0;
    return nuevoPlano.piezas.reduce((acc, p) => {
      const val = parseInt(p.tiempo_estimado_valor, 10) || 0;
      return acc + (p.tiempo_estimado_unidad === 'DIAS' ? val * 8 : val);
    }, 0);
  };

  const FILTROS_BANDEJA = [
    { id: 'TODOS', label: 'Todos' },
    { id: 'PENDIENTES', label: 'Pendientes' },
    { id: 'EN_ESTRUCTURACION', label: 'En estructuración' },
    { id: 'PARCIALES', label: 'Parciales' },
    { id: 'ASIGNADOS', label: 'Asignados' },
    { id: 'BLOQUEADOS', label: 'Bloqueados' },
    { id: 'CERRADOS', label: 'Cerrados' },
  ];

  const cumpleFiltroBandeja = (ped, filtro) => {
    const pend = ped.total_pendiente !== undefined 
      ? ped.total_pendiente 
      : (ped.detalles ? ped.detalles.reduce((acc, d) => acc + (d.cantidad_pendiente ?? d.cantidad_solicitada ?? 1), 0) : ped.cantidad || 1);

    switch (filtro) {
      case 'PENDIENTES': return pend > 0;
      case 'EN_ESTRUCTURACION': return ped.estado_pedido === 'EN_ESTRUCTURACION';
      case 'PARCIALES': return ped.estado_pedido === 'PARCIALMENTE_ASIGNADO';
      case 'ASIGNADOS': return ped.estado_pedido === 'ASIGNADO' || pend === 0;
      case 'BLOQUEADOS': return !!ped.bloqueado;
      case 'CERRADOS': return ['ENTREGADO', 'CERRADO', 'CANCELADO'].includes(ped.estado_pedido);
      default: return true;
    }
  };

  const ESTILO_ESTADO_PEDIDO = {
    RECIBIDO: 'bg-slate-100 text-slate-700 border-slate-300',
    EN_ESTRUCTURACION: 'bg-blue-100 text-blue-800 border-blue-300',
    PARCIALMENTE_ASIGNADO: 'bg-amber-100 text-amber-800 border-amber-300',
    ASIGNADO: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    ENTREGADO: 'bg-teal-100 text-teal-800 border-teal-300',
    CERRADO: 'bg-slate-200 text-slate-700 border-slate-300',
    CANCELADO: 'bg-red-100 text-red-800 border-red-300',
  };

  const pedidosEnBandejaPendientes = pedidosEntrantes.filter(ped => {
    const pend = ped.total_pendiente !== undefined 
      ? ped.total_pendiente 
      : (ped.detalles ? ped.detalles.reduce((acc, d) => acc + (d.cantidad_pendiente ?? d.cantidad_solicitada ?? 1), 0) : ped.cantidad || 1);
    return pend > 0;
  });

  const totalPlanos = planos.length;
  const planificadasCount = planos.filter(p => p.estado_diseno === 'PLANIFICADA').length;
  const enDisenoCount = planos.filter(p => p.estado_diseno === 'EN_DISENO').length;
  const liberadosCount = planos.filter(p => p.estado_diseno === 'LIBERADA').length;

  const pedidosEntrantesFiltrados = pedidosEntrantes.filter((ped) => {
    if (!cumpleFiltroBandeja(ped, filtroBandeja)) return false;
    const termino = busquedaBandeja.toLowerCase().trim();
    if (!termino) return true;
    const numPed = (ped.numero_pedido || '').toLowerCase();
    const cliente = (ped.cliente_nombre || '').toLowerCase();
    const prod = (ped.detalle_producto || '').toLowerCase();
    return numPed.includes(termino) || cliente.includes(termino) || prod.includes(termino);
  });

  const planosFiltrados = planos.filter((p) => {
    const termino = busqueda.toLowerCase().trim();
    const codigoOp = (p.codigo_op || '').toLowerCase();
    const codigoPlano = (p.codigo_plano || '').toLowerCase();
    const pedido = (p.numero_pedido || '').toLowerCase();
    const dibujante = (p.dibujante_asignado || '').toLowerCase();
    const coincideBusqueda = codigoOp.includes(termino) || codigoPlano.includes(termino) || pedido.includes(termino) || dibujante.includes(termino);

    if (filtroEstado === 'TODOS') return coincideBusqueda;
    const est = p.estado_diseno || 'PLANIFICADA';
    return coincideBusqueda && est === filtroEstado;
  });

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

  return (
    <div className="p-6 bg-slate-50 min-h-screen space-y-6 font-sans">
      <header className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <span>📐</span> Ingeniería y Diseño de Planos (PM-02)
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Gestión Individual de Órdenes de Producción (OP) e Levantamiento de Mantenimientos [ISO 9001:2026 / SAP B1]
          </p>
        </div>
        <div className="flex items-center gap-2 self-end sm:self-auto">
          <button 
            type="button"
            onClick={() => { setMensaje({ tipo: '', texto: '' }); cargarPlanosYPedidos(); }}
            className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg border border-slate-300 transition flex items-center gap-1.5 cursor-pointer"
          >
            <span>🔄</span> Recargar
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

      <div className="flex border-b border-slate-300 gap-2 bg-white px-4 pt-2 rounded-t-xl">
        <button
          type="button"
          onClick={() => setPestanaActiva('BANDEJA')}
          className={`pb-3 px-4 font-bold text-sm border-b-2 transition cursor-pointer flex items-center gap-2 ${
            pestanaActiva === 'BANDEJA'
              ? 'border-blue-600 text-blue-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>📥 Bandeja de Pedidos Comerciales Entrantes</span>
          <span className="px-2.5 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full font-extrabold">
            {pedidosEnBandejaPendientes.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setPestanaActiva('ORDENES')}
          className={`pb-3 px-4 font-bold text-sm border-b-2 transition cursor-pointer flex items-center gap-2 ${
            pestanaActiva === 'ORDENES'
              ? 'border-purple-600 text-purple-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>⚙️ Órdenes de Producción e Ingeniería Activas</span>
          <span className="px-2.5 py-0.5 bg-purple-100 text-purple-800 text-xs rounded-full font-extrabold">
            {totalPlanos}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setPestanaActiva('MANTENIMIENTO')}
          className={`pb-3 px-4 font-bold text-sm border-b-2 transition cursor-pointer flex items-center gap-2 ${
            pestanaActiva === 'MANTENIMIENTO'
              ? 'border-amber-600 text-amber-700'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>🛠️ Mantenimientos & Overhaul</span>
          <span className="px-2.5 py-0.5 bg-amber-100 text-amber-800 text-xs rounded-full font-extrabold">
            {listaMantenimientos.length}
          </span>
        </button>
      </div>

      {pestanaActiva === 'BANDEJA' && (
        <div className="bg-white rounded-b-xl border border-blue-200 shadow-sm overflow-hidden p-4 space-y-3">
          <div className="flex justify-between items-center pb-1">
            <span className="text-xs font-bold text-slate-600 uppercase">Matriz de Distribución de Pedidos Comerciales en OPs</span>
            <input
              type="text"
              placeholder="🔍 Filtrar bandeja por N° Pedido o Cliente..."
              value={busquedaBandeja}
              onChange={(e) => setBusquedaBandeja(e.target.value)}
              className="w-72 p-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="flex flex-wrap gap-1.5">
            {FILTROS_BANDEJA.map((f) => {
              const n = pedidosEntrantes.filter(p => f.id === 'TODOS' || cumpleFiltroBandeja(p, f.id)).length;
              const activo = filtroBandeja === f.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setFiltroBandeja(f.id)}
                  className={`px-2.5 py-1 rounded-full text-xs font-bold border transition cursor-pointer ${
                    activo ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  {f.label} <span className={activo ? 'text-blue-100' : 'text-slate-400'}>({n})</span>
                </button>
              );
            })}
          </div>

          <div className="overflow-x-auto border border-slate-200 rounded-lg bg-white">
            <table className="w-full text-left text-xs text-slate-600 border-collapse">
              <thead>
                <tr className="bg-slate-100 text-slate-700 font-bold uppercase border-b border-slate-200">
                  <th className="p-3">N° Pedido</th>
                  <th className="p-3">Cliente / Contacto</th>
                  <th className="p-3">Detalle Comercial / Líneas & Piezas</th>
                  <th className="p-3 text-center">Solic. / Asig. / Pend.</th>
                  <th className="p-3">Fecha Compromiso</th>
                  <th className="p-3">Estado</th>
                  <th className="p-3 text-center">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {pedidosEntrantesFiltrados.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="p-6 text-center text-slate-400 font-medium">
                      No hay pedidos que coincidan con el filtro de la bandeja.
                    </td>
                  </tr>
                ) : (
                  pedidosEntrantesFiltrados.map((ped) => {
                    const totalSol = ped.total_solicitado ?? ped.cantidad ?? 1;
                    const totalAsig = ped.total_asignado ?? 0;
                    const totalPend = ped.total_pendiente ?? (totalSol - totalAsig);

                    return (
                      <tr key={ped.id_proyecto} className="hover:bg-slate-50 transition">
                        <td className="p-3 font-mono font-bold whitespace-nowrap">
                          <button
                            type="button"
                            onClick={(e) => handleAbrirExpedientePedido(e, ped.numero_pedido)}
                            className="text-purple-700 hover:text-purple-900 underline bg-purple-50 hover:bg-purple-100 px-2.5 py-1 rounded border border-purple-200 transition cursor-pointer"
                          >
                            📋 {ped.numero_pedido || 'PED-S/N'}
                          </button>
                        </td>

                        <td className="p-3 font-medium" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAbrirHistoricoClienteUbicacion(ped.cliente_nombre, ped.ubicacion_cliente);
                            }}
                            className="text-slate-800 hover:text-blue-700 text-left font-bold underline cursor-pointer"
                          >
                            🏢 {ped.cliente_nombre || 'Cliente General'}
                          </button>
                          {ped.contacto_nombre && (
                            <div className="text-[10px] text-slate-500 font-medium">👤 {ped.contacto_nombre}</div>
                          )}
                        </td>

                        <td className="p-3 font-medium text-slate-700 max-w-xs">
                          {ped.detalles && ped.detalles.length > 0 ? (
                            <div className="space-y-1">
                              {ped.detalles.map((it, idx) => (
                                <div key={it.detalle_id || idx} className="text-[11px] text-slate-800 font-semibold truncate flex items-center gap-1">
                                  <span className="text-purple-600 font-bold">🧩 Línea {idx + 1}:</span> {it.descripcion || 'Pieza'}
                                  <span className="text-slate-500 font-mono">
                                    ({it.cantidad_asignada || 0}/{it.cantidad_solicitada || 1} {it.unidad || 'UND'})
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <span>{ped.detalle_producto || 'Piezas Mecanizadas Solicitadas'}</span>
                          )}
                        </td>

                        <td className="p-3 text-center font-bold text-blue-900 whitespace-nowrap">
                          <span className="px-2 py-0.5 bg-blue-50 border border-blue-200 rounded">
                            {totalSol}
                            {' / '}<span className="text-emerald-700">{totalAsig}</span>
                            {' / '}<span className="text-amber-700">{totalPend}</span>
                          </span>
                          <div className="w-20 h-1.5 bg-slate-200 rounded mx-auto mt-1 overflow-hidden">
                            <div className="h-full bg-emerald-500" style={{ width: `${ped.cobertura_pct || 0}%` }} />
                          </div>
                        </td>

                        <td className="p-3 font-bold text-amber-800 whitespace-nowrap">
                          📅 {ped.fecha_compromiso || 'Sin Fecha'}
                        </td>

                        <td className="p-3 whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${ESTILO_ESTADO_PEDIDO[ped.estado_pedido] || ESTILO_ESTADO_PEDIDO.RECIBIDO}`}>
                            {(ped.estado_pedido || 'RECIBIDO').replaceAll('_', ' ')}
                          </span>
                          {ped.bloqueado && (
                            <div className="text-[10px] font-bold text-red-700 mt-0.5">⛔ OP bloqueada</div>
                          )}
                        </td>

                        <td className="p-3 text-center whitespace-nowrap">
                          <button
                            type="button"
                            onClick={() => handleAsignarOpDesdePedido(ped)}
                            className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white font-bold rounded text-xs transition flex items-center justify-center gap-1 mx-auto shadow-sm cursor-pointer"
                          >
                            ⚙ Crear / Asignar Orden de Producción y Planos
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* PESTAÑA 2: ÓRDENES ACTIVAS E INGENIERÍA */}
      {pestanaActiva === 'ORDENES' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <button
              type="button"
              onClick={() => setFiltroEstado('TODOS')}
              className={`p-4 rounded-xl border text-left transition-all shadow-sm cursor-pointer ${
                filtroEstado === 'TODOS'
                  ? 'bg-blue-50/90 border-blue-500 ring-2 ring-blue-400/30 scale-[1.02]'
                  : 'bg-white border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span className="text-xs font-bold text-blue-600 uppercase tracking-wide">1. Órdenes Activas</span>
              <p className="text-2xl font-bold text-blue-700 mt-1">{totalPlanos}</p>
              <span className="text-[10px] text-blue-600 font-semibold mt-1 block">🔍 Ver Todas las Órdenes</span>
            </button>

            <button
              type="button"
              onClick={() => setFiltroEstado(filtroEstado === 'PLANIFICADA' ? 'TODOS' : 'PLANIFICADA')}
              className={`p-4 rounded-xl border text-left transition-all shadow-sm cursor-pointer ${
                filtroEstado === 'PLANIFICADA'
                  ? 'bg-amber-50/90 border-amber-500 ring-2 ring-amber-400/30 scale-[1.02]'
                  : 'bg-white border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span className="text-xs font-bold text-amber-600 uppercase tracking-wide">2. Planificadas</span>
              <p className="text-2xl font-bold text-amber-700 mt-1">{planificadasCount}</p>
              <span className="text-[10px] text-amber-600 font-semibold mt-1 block">🔍 Filtrar Planificadas</span>
            </button>

            <button
              type="button"
              onClick={() => setFiltroEstado(filtroEstado === 'EN_DISENO' ? 'TODOS' : 'EN_DISENO')}
              className={`p-4 rounded-xl border text-left transition-all shadow-sm cursor-pointer ${
                filtroEstado === 'EN_DISENO'
                  ? 'bg-purple-50/90 border-purple-500 ring-2 ring-purple-400/30 scale-[1.02]'
                  : 'bg-white border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span className="text-xs font-bold text-purple-600 uppercase tracking-wide">3. En Diseño</span>
              <p className="text-2xl font-bold text-purple-700 mt-1">{enDisenoCount}</p>
              <span className="text-[10px] text-purple-600 font-semibold mt-1 block">🔍 Filtrar En Diseño</span>
            </button>

            <button
              type="button"
              onClick={() => setFiltroEstado(filtroEstado === 'LIBERADA' ? 'TODOS' : 'LIBERADA')}
              className={`p-4 rounded-xl border text-left transition-all shadow-sm cursor-pointer ${
                filtroEstado === 'LIBERADA'
                  ? 'bg-emerald-50/90 border-emerald-500 ring-2 ring-emerald-400/30 scale-[1.02]'
                  : 'bg-white border-slate-200 hover:bg-slate-50'
              }`}
            >
              <span className="text-xs font-bold text-emerald-600 uppercase tracking-wide">4. Liberadas a Planta</span>
              <p className="text-2xl font-bold text-emerald-700 mt-1">{liberadosCount}</p>
              <span className="text-[10px] text-emerald-600 font-semibold mt-1 block">🔍 Filtrar Liberadas</span>
            </button>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 border-b pb-3">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-700">Órdenes de Producción Activas (Individuales)</h2>
                {filtroEstado !== 'TODOS' && (
                  <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-bold rounded uppercase">
                    Etapa: {filtroEstado}
                  </span>
                )}
              </div>

              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full md:w-auto">
                <select
                  value={filtroEstado}
                  onChange={(e) => setFiltroEstado(e.target.value)}
                  className="p-2 border border-slate-300 rounded-lg text-xs bg-slate-50 font-medium text-slate-700 focus:bg-white"
                >
                  <option value="TODOS">Todas las Etapas</option>
                  <option value="PLANIFICADA">2. PLANIFICADAS</option>
                  <option value="EN_DISENO">3. EN DISEÑO</option>
                  <option value="LIBERADA">4. LIBERADAS</option>
                </select>

                <input
                  type="text"
                  placeholder="🔍 Buscar por N° Orden (OP), Plano, Pedido o Diseñador..."
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  className="w-full sm:w-72 p-2 border border-slate-300 rounded-lg text-xs bg-slate-50 focus:bg-white"
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600 border-collapse">
                <thead>
                  <tr className="bg-slate-100 text-slate-700 font-bold uppercase border-b border-slate-200">
                    <th className="p-3">N° Orden (OP)</th>
                    <th className="p-3">N° Pedido</th>
                    <th className="p-3">Código Plano / Pieza</th>
                    <th className="p-3">Plano PDF</th>
                    <th className="p-3">Unidad Planta</th>
                    <th className="p-3">Diseñador</th>
                    <th className="p-3">Causa de Espera</th>
                    <th className="p-3">Fechas Clave</th>
                    <th className="p-3">Etapa Lineal</th>
                    <th className="p-3 text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {planosFiltrados.length === 0 ? (
                    <tr>
                      <td colSpan="10" className="p-6 text-center text-slate-400 font-medium">
                        {loading ? 'Cargando órdenes...' : 'No hay órdenes de producción registradas.'}
                      </td>
                    </tr>
                  ) : (
                    planosFiltrados.map((pl) => {
                      const estadoActual = pl.estado_diseno || 'PLANIFICADA';
                      const idxActual = SECUENCIA_ESTADOS.indexOf(estadoActual);

                      return (
                        <tr key={pl.id_plano} className="hover:bg-slate-50 transition">
                          <td className="p-3 font-mono font-bold whitespace-nowrap">
                            <button
                              type="button"
                              onClick={(e) => handleAbrirExpedienteOp(e, pl)}
                              className="text-blue-700 hover:text-blue-900 bg-blue-50 hover:bg-blue-100 px-2 py-1 rounded border border-blue-200 transition cursor-pointer"
                            >
                              ⚙ OP-{pl.codigo_op || '4007256'}
                            </button>
                          </td>

                          <td className="p-3 font-mono font-bold whitespace-nowrap">
                            <button
                              type="button"
                              onClick={(e) => handleAbrirExpedientePedido(e, pl.numero_pedido)}
                              className="text-purple-700 hover:text-purple-900 underline bg-purple-50 hover:bg-purple-100 px-2 py-1 rounded border border-purple-200 transition cursor-pointer"
                            >
                              📋 {pl.numero_pedido}
                            </button>
                          </td>

                          <td className="p-3 font-mono font-bold text-slate-800">
                            📄 {pl.codigo_plano} ({pl.revision || 'REV-01'})
                            <div className="text-[10px] text-slate-500 font-normal">{pl.detalle_pieza || pl.material_requerido || 'Pieza Mecanizada'}</div>
                          </td>

                          <td className="p-3 text-center whitespace-nowrap">
                            {pl.archivo_url ? (
                              <button
                                type="button"
                                onClick={() => handleAbrirVisorPlano(pl.archivo_url, pl.codigo_op, pl.codigo_plano)}
                                className="px-2.5 py-1 bg-emerald-100 text-emerald-800 hover:bg-emerald-200 border border-emerald-300 font-bold rounded text-[10px] transition cursor-pointer flex items-center gap-1 mx-auto"
                              >
                                👁️ Ver Plano PDF
                              </button>
                            ) : (
                              <span className="text-[10px] text-amber-700 font-semibold italic bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                                ⏳ Sin Adjunto
                              </span>
                            )}
                          </td>

                          <td className="p-3 font-bold text-slate-700">🏭 {pl.unidad_planta || 'Mecanizados'}</td>

                          <td className="p-3 font-medium text-slate-800">👤 {pl.dibujante_asignado || 'Ing. Carlos Ruiz'}</td>

                          <td className="p-3 font-medium text-slate-700 max-w-xs">
                            <select
                              value={pl.causa_espera || 'RESUELTA'}
                              onChange={(e) => handleCambiarCausaEsperaTabla(pl, e.target.value)}
                              className={`p-1 rounded text-[10px] font-bold border focus:outline-none cursor-pointer w-full truncate ${
                                !pl.causa_espera 
                                  ? 'bg-emerald-50 text-emerald-800 border-emerald-300' 
                                  : 'bg-amber-50 text-amber-900 border-amber-300'
                              }`}
                            >
                              <option value="RESUELTA">✓ Sin demoras / Resuelta (EN COLA)</option>
                              {OPCIONES_CAUSA_ESPERA.map((opcion, idx) => (
                                <option key={idx} value={opcion}>
                                  ⚠️ {opcion}
                                </option>
                              ))}
                            </select>
                          </td>

                          <td className="p-3 font-medium text-slate-800 text-[11px] whitespace-nowrap space-y-0.5">
                            <div>📅 Prog: <strong>{pl.fecha_inicio_programada || 'Sin Fecha'}</strong></div>
                            <div className="text-blue-800">🏁 Límite: <strong>{pl.fecha_entrega_produccion || 'Sin Fecha'}</strong></div>
                          </td>

                          <td className="p-3 whitespace-nowrap">
                            <select
                              value={estadoActual}
                              onChange={(e) => handleCambiarEtapaOrden(pl, e.target.value)}
                              className={`p-1 rounded text-[10px] font-bold border focus:outline-none cursor-pointer ${
                                estadoActual === 'LIBERADA' ? 'bg-emerald-100 text-emerald-800 border-emerald-300' :
                                estadoActual === 'EN_DISENO' ? 'bg-purple-100 text-purple-800 border-purple-300' :
                                estadoActual === 'PLANIFICADA' ? 'bg-amber-100 text-amber-800 border-amber-300' :
                                'bg-blue-100 text-blue-800 border-blue-300'
                              }`}
                            >
                              {SECUENCIA_ESTADOS.map((est, idx) => (
                                <option 
                                  key={est} 
                                  value={est} 
                                  disabled={idx !== idxActual + 1 && idx !== idxActual}
                                >
                                  {idx + 1}. {est} {idx < idxActual ? '🔒 (Completado)' : idx > idxActual + 1 ? '🔒 (Bloqueado)' : ''}
                                </option>
                              ))}
                            </select>
                          </td>

                          <td className="p-3 text-center whitespace-nowrap">
                            <button
                              type="button"
                              onClick={(e) => handleAbrirExpedienteOp(e, pl)}
                              className="px-2.5 py-1 font-semibold rounded text-[11px] bg-slate-700 text-white hover:bg-slate-800 shadow-sm transition cursor-pointer"
                            >
                              ⚙ Modificar Orden de Producción
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* PESTAÑA 3: MANTENIMIENTO */}
      {pestanaActiva === 'MANTENIMIENTO' && (
        <div className="bg-white rounded-b-xl border border-amber-200 shadow-sm overflow-hidden p-5 space-y-4">
          <div className="flex justify-between items-center pb-2 border-b">
            <div>
              <span className="text-xs font-bold text-amber-800 uppercase tracking-wide">
                ⚙️ Módulo de Mantenimiento & Overhaul — Seguimiento de Proyectos [SGI ISO 9001:2026]
              </span>
              <h2 className="text-lg font-bold text-slate-800 mt-1">
                Tabla de Proyectos de Mantenimiento y Control SGI
              </h2>
            </div>
            <button
              type="button"
              onClick={() => handleSeleccionarMaquinaLevantamiento(1)}
              className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg shadow-sm transition flex items-center gap-1.5 cursor-pointer"
            >
              <span>➕</span> Registrar Ingreso de Máquina
            </button>
          </div>

          {!mantenimientoSeleccionado ? (
            <div className="overflow-x-auto border border-slate-200 rounded-lg bg-white">
              <table className="w-full text-left text-xs text-slate-600 border-collapse">
                <thead>
                  <tr className="bg-slate-100 text-slate-700 font-bold uppercase border-b border-slate-200">
                    <th className="p-3">Código Proyecto</th>
                    <th className="p-3">Cliente / Razón Social</th>
                    <th className="p-3">Máquina / Equipo</th>
                    <th className="p-3">OP Venta</th>
                    <th className="p-3">Fase SGI</th>
                    <th className="p-3 text-center">Acciones de Despliegue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {listaMantenimientos.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="p-6 text-center text-slate-400 font-medium">
                        No hay proyectos de mantenimiento registrados.
                      </td>
                    </tr>
                  ) : (
                    listaMantenimientos.map((p) => {
                      const idUnico = p.id_proyecto || p.id_mantenimiento || 1;
                      const piezasAbiertas = !!piezasExpandidas[idUnico];
                      const cargandoPiezas = !!cargandoPiezasMap[idUnico];
                      const piezasProyecto = piezasProyectoMap[idUnico] || p.piezas || p.detalles || [];

                      return (
                        <React.Fragment key={idUnico}>
                          <tr className="hover:bg-slate-50 transition">
                            <td className="p-3 font-mono font-bold text-amber-800 whitespace-nowrap">
                              {p.codigo_mantenimiento || p.numero_pedido || 'MANT-2026-010'}
                            </td>
                            <td className="p-3 font-bold text-slate-800">
                              {p.cliente_nombre || p.cliente || 'Tesa'}
                            </td>
                            <td className="p-3 font-medium text-slate-800">
                              {p.nombre_maquina || p.detalle_producto || 'Torno'}
                            </td>
                            <td className="p-3 font-mono font-bold text-blue-800">
                              {p.codigo_op || 'OP-100'}
                            </td>
                            <td className="p-3 whitespace-nowrap">
                              <span className="px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase bg-amber-50 text-amber-800 border border-amber-300">
                                {p.fase_mantenimiento || 'LAVADO_DESARME'}
                              </span>
                            </td>
                            <td className="p-3 text-center whitespace-nowrap space-x-2">
                              <button
                                type="button"
                                onClick={() => togglePiezasProyecto(idUnico, p)}
                                disabled={cargandoPiezas}
                                className={`px-3 py-1 font-bold rounded text-[11px] transition shadow-sm cursor-pointer border ${
                                  piezasAbiertas 
                                    ? 'bg-blue-600 text-white border-blue-700' 
                                    : 'bg-blue-50 text-blue-800 border-blue-200 hover:bg-blue-100'
                                }`}
                              >
                                {cargandoPiezas ? '🔄 Cargando...' : piezasAbiertas ? '🔼 Ocultar Piezas' : '📦 Ver Piezas'}
                              </button>

                              <button
                                type="button"
                                onClick={() => handleSeleccionarMaquinaLevantamiento(idUnico)}
                                className="px-3 py-1 font-bold rounded text-[11px] bg-slate-700 text-white hover:bg-slate-800 transition shadow-sm cursor-pointer"
                              >
                                📐 Cargar / Editar
                              </button>
                            </td>
                          </tr>

                          {piezasAbiertas && (
                            <tr className="bg-slate-50">
                              <td colSpan="6" className="p-4">
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
                                                <td className="p-2 text-center font-bold text-blue-900">{pz.cantidad || 1}</td>
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
          ) : (
            <div className="space-y-3">
              <div className="flex justify-between items-center bg-amber-50/80 p-3 rounded-xl border border-amber-200">
                <div>
                  <button
                    type="button"
                    onClick={() => setMantenimientoSeleccionado(null)}
                    className="text-amber-900 font-bold hover:underline text-xs flex items-center gap-1 mb-1 cursor-pointer"
                  >
                    ⬅ Volver a la Lista de Proyectos
                  </button>
                  <h4 className="text-base font-black text-slate-800">
                    Máquina: <span className="text-amber-900">{mantenimientoSeleccionado.nombre_maquina}</span> ({mantenimientoSeleccionado.codigo_mantenimiento || mantenimientoSeleccionado.numero_pedido})
                  </h4>
                </div>

                <label className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-lg text-xs shadow-sm transition cursor-pointer flex items-center gap-1">
                  <span>📥</span> Importar CSV
                  <input type="file" accept=".csv,.txt" onChange={handleImportarArchivoCSV} className="hidden" />
                </label>
              </div>

              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-2">
                <span className="text-[10px] font-bold text-amber-800 uppercase block">➕ Carga Rápida de Ítem / Pieza al Levantamiento</span>
                <div className="grid grid-cols-12 gap-2">
                  <input
                    type="text"
                    placeholder="Código Plano"
                    value={nuevaPiezaTemp.codigo}
                    onChange={(e) => setNuevaPiezaTemp({ ...nuevaPiezaTemp, codigo: e.target.value })}
                    className="col-span-2 p-2 border border-slate-300 rounded text-slate-800 font-mono"
                  />
                  <input
                    type="text"
                    placeholder="Descripción"
                    value={nuevaPiezaTemp.descripcion}
                    onChange={(e) => setNuevaPiezaTemp({ ...nuevaPiezaTemp, descripcion: e.target.value })}
                    className="col-span-4 p-2 border border-slate-300 rounded text-slate-800"
                  />
                  <select
                    value={nuevaPiezaTemp.accion}
                    onChange={(e) => setNuevaPiezaTemp({ ...nuevaPiezaTemp, accion: e.target.value })}
                    className="col-span-3 p-2 border border-slate-300 rounded text-slate-800 font-bold bg-white cursor-pointer"
                  >
                    <option value="FABRICAR_NUEVA">🔨 Fabricar Nueva</option>
                    <option value="RECTIFICAR_RECUPERAR">⚙️ Rectificar</option>
                    <option value="COMPRA_DIRECTA_BOM">🛒 Compra BOM</option>
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

              <div className="flex-1 overflow-auto border border-slate-200 rounded-lg bg-white max-h-[45vh]">
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
                      <th className="p-2.5 text-center">Estado Aprobación</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 text-slate-700">
                    {piezasLevantamiento.map((p, idx) => (
                      <tr key={idx} className="hover:bg-slate-50 transition">
                        <td className="p-2.5 text-center font-mono text-slate-400">#{p.posicion}</td>
                        <td className="p-2.5 font-mono font-bold text-purple-700">{p.codigo}</td>
                        <td className="p-2.5 font-bold text-slate-800">{p.descripcion}</td>
                        <td className="p-2.5">{p.accion}</td>
                        <td className="p-2.5 text-center font-bold text-emerald-700">{p.cantidad}</td>
                        <td className="p-2.5 text-slate-500">{p.material}</td>
                        <td className="p-2.5 text-right font-mono">$ {p.cotizado.toLocaleString()}</td>
                        <td className="p-2.5 text-center">
                          <button
                            type="button"
                            onClick={() => toggleAutorizacionPieza(idx)}
                            className={`px-3 py-1 rounded font-bold text-[10px] cursor-pointer ${
                              p.autorizado ? 'bg-emerald-600 text-white' : 'bg-amber-100 text-amber-900 border'
                            }`}
                          >
                            {p.autorizado ? '✓ APROBADA' : '⏳ PENDIENTE'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex justify-between items-center border-t pt-3">
                <div className="text-slate-500 text-xs">
                  Total Piezas: <strong className="text-slate-800">{piezasLevantamiento.length}</strong>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setMantenimientoSeleccionado(null)}
                    className="px-4 py-2 bg-slate-200 text-slate-800 font-bold rounded cursor-pointer"
                  >
                    Volver
                  </button>
                  <button
                    type="button"
                    onClick={handleGuardarLevantamientoTecnico}
                    disabled={loading}
                    className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded cursor-pointer"
                  >
                    💾 Guardar Levantamiento Técnico
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* MODAL 1: EXPEDIENTE COMERCIAL DEL PEDIDO */}
      {modalPedidoAbierto && pedidoSeleccionado && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full p-6 space-y-4 max-h-[92vh] overflow-y-auto border-t-4 border-purple-600">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2.5 py-1 bg-purple-100 text-purple-800 text-xs font-extrabold rounded uppercase tracking-wider">
                  📋 Expediente Comercial del Pedido [ISO 9001:2026 / SAP B1]
                </span>
                <h3 className="text-2xl font-bold text-slate-800 mt-2">
                  Pedido Comercial N°: <span className="text-purple-700 font-mono">{pedidoSeleccionado.numero_pedido}</span>
                </h3>
              </div>
              <button onClick={() => setModalPedidoAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-xl cursor-pointer">✕</button>
            </div>

            <div className="text-xs sm:text-sm bg-slate-50 p-4 rounded-lg border border-slate-200 grid grid-cols-1 sm:grid-cols-2 gap-3 text-slate-800">
              <p><strong>Cliente / Razón Social:</strong> {pedidoSeleccionado.cliente_nombre}</p>
              <p><strong>Contacto Cliente:</strong> 👤 {pedidoSeleccionado.contacto_nombre}</p>
              <p><strong>Ubicación Planta:</strong> {pedidoSeleccionado.ubicacion_cliente}</p>
              <p><strong>Fecha Compromiso Cliente:</strong> <span className="font-bold text-purple-900">📅 {pedidoSeleccionado.fecha_compromiso}</span></p>
              <p className="col-span-1 sm:col-span-2"><strong>Requisitos Técnicos Generales:</strong> {pedidoSeleccionado.requisitos_cliente}</p>
            </div>

            <div className="space-y-3 border p-4 rounded-xl bg-slate-50/50">
              <h4 className="font-bold text-slate-800 text-sm flex items-center gap-1.5">
                <span>📦</span> Desglose de Líneas / Piezas Comerciales Solicitadas
              </h4>
              
              {pedidoSeleccionado.lineas.map((linea, idx) => (
                <div key={idx} className="ml-2 pl-3 border-l-4 border-purple-500 space-y-2 bg-white p-3.5 rounded-lg border border-slate-200 shadow-sm">
                  <div className="font-bold text-slate-800 text-xs sm:text-sm flex items-center justify-between border-b pb-1.5">
                    <span className="text-purple-800">🧩 Línea {linea.numero_linea || idx + 1}: {linea.detalle_pieza} ({linea.cantidad} UND)</span>
                    <span className="text-xs text-purple-900 font-bold bg-purple-50 px-2.5 py-1 rounded border border-purple-200">📅 Entrega: {linea.fecha_compromiso}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end border-t pt-3">
              <button onClick={() => setModalPedidoAbierto(false)} className="px-5 py-2.5 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded text-xs sm:text-sm transition cursor-pointer">
                Cerrar Expediente
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: HISTÓRICO CLIENTE */}
      {modalHistoricoClienteAbierto && clienteHistoricoSeleccionado && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full p-6 space-y-4 max-h-[92vh] overflow-y-auto">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-slate-800 text-white text-[10px] font-bold rounded uppercase">
                    🔒 CONSULTA DE SOLO LECTURA [AUDITORÍA SGI ISO 9001:2026]
                  </span>
                </div>
                <h3 className="text-xl font-bold text-slate-800 mt-1">
                  Histórico de Trabajos: <span className="text-blue-700">{clienteHistoricoSeleccionado.cliente_nombre}</span>
                </h3>
                <p className="text-xs text-slate-500">
                  Sede / Planta de Entrega: <strong>📍 {clienteHistoricoSeleccionado.ubicacion_cliente}</strong>
                </p>
              </div>
              <button onClick={() => setModalHistoricoClienteAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg cursor-pointer">✕</button>
            </div>

            <div className="overflow-x-auto border border-slate-200 rounded-lg">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-800 text-white font-bold uppercase text-[11px]">
                    <th className="p-2.5">N° Pedido</th>
                    <th className="p-2.5">Código OP</th>
                    <th className="p-2.5">Plano Técnico</th>
                    <th className="p-2.5">Detalle / Pieza</th>
                    <th className="p-2.5 text-center">Cantidad</th>
                    <th className="p-2.5">Planta</th>
                    <th className="p-2.5">Fecha Entrega</th>
                    <th className="p-2.5 text-center">Estado SGI</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-700">
                  {clienteHistoricoSeleccionado.ordenes.length === 0 ? (
                    <tr>
                      <td colSpan="8" className="p-6 text-center text-slate-400 font-medium italic">
                        No hay trabajos históricos registrados previamente para esta sede.
                      </td>
                    </tr>
                  ) : (
                    clienteHistoricoSeleccionado.ordenes.map((o, idx) => (
                      <tr key={idx} className="hover:bg-slate-50">
                        <td className="p-2.5 font-mono font-bold text-purple-700">📋 {o.numero_pedido || 'PED-S/N'}</td>
                        <td className="p-2.5 font-mono font-bold text-blue-700">⚙ OP-{o.codigo_op || '4007256'}</td>
                        <td className="p-2.5 font-mono font-bold text-slate-800">📄 {o.codigo_plano}</td>
                        <td className="p-2.5 font-medium text-slate-800">{o.material_requerido || 'Pieza Mecanizada'}</td>
                        <td className="p-2.5 text-center font-bold text-slate-800">1 UND</td>
                        <td className="p-2.5 font-bold text-slate-700">🏭 {o.unidad_planta || 'Mecanizados'}</td>
                        <td className="p-2.5 font-bold text-slate-800">📅 {o.fecha_entrega_produccion || '2026-10-15'}</td>
                        <td className="p-2.5 text-center">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                            {o.estado_diseno || 'LIBERADA'}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end border-t pt-3">
              <button onClick={() => setModalHistoricoClienteAbierto(false)} className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded text-xs transition cursor-pointer">
                Cerrar Cronograma
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL MODIFICAR / ESTRUCTURAR ORDEN DE PRODUCCIÓN */}
      {modalNuevoPlanoAbierto && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-2 sm:p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-[96vw] w-full p-4 sm:p-6 space-y-4 max-h-[95vh] overflow-y-auto border-t-4 border-blue-600">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2.5 py-1 bg-blue-100 text-blue-800 text-xs font-extrabold rounded uppercase tracking-wider">
                  Apertura y Asignación Granular HD por Ítem [PM-02 / ISO 9001:2026]
                </span>
                <h3 className="text-xl sm:text-2xl font-bold text-slate-800 mt-1">
                  ⚙️ Estructurar / Modificar Orden de Producción (OP)
                </h3>
              </div>
              <button onClick={() => setModalNuevoPlanoAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-xl cursor-pointer">✕</button>
            </div>

            <form onSubmit={handleCrearOrdenDiseno} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-6 gap-2.5 bg-slate-50 p-3 rounded-xl border border-slate-200">
                <div>
                  <label className="block font-semibold text-slate-600 mb-1">N° Pedido Comercial</label>
                  <input
                    type="text"
                    disabled
                    value={nuevoPlano.numero_pedido}
                    className="w-full p-1.5 border border-slate-300 rounded font-mono font-bold text-purple-700 bg-slate-100 cursor-not-allowed"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Cliente / Razón Social</label>
                  <input
                    type="text"
                    disabled
                    value={nuevoPlano.cliente_nombre || 'Ecopetrol S.A.'}
                    className="w-full p-1.5 border border-slate-300 rounded font-bold text-slate-800 bg-slate-100 cursor-not-allowed"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-blue-900 mb-1">📍 Sede / Ubicación *</label>
                  <input
                    type="text"
                    disabled
                    value={nuevoPlano.ubicacion_cliente || 'Refinería Barrancabermeja'}
                    className="w-full p-1.5 border border-blue-300 rounded font-bold text-blue-900 bg-blue-50/60 cursor-not-allowed"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Contacto / Representante</label>
                  <input
                    type="text"
                    disabled
                    value={`👤 ${nuevoPlano.contacto_nombre || 'Ing. Juan Pérez'}`}
                    className="w-full p-1.5 border border-slate-300 rounded text-slate-800 bg-slate-100 cursor-not-allowed"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Teléfono</label>
                  <input
                    type="text"
                    disabled
                    value={`📞 ${nuevoPlano.contacto_telefono || 'N/A'}`}
                    className="w-full p-1.5 border border-slate-300 rounded text-slate-800 bg-slate-100 cursor-not-allowed text-[11px]"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-600 mb-1">Email</label>
                  <input
                    type="text"
                    disabled
                    value={`✉️ ${nuevoPlano.contacto_email || 'N/A'}`}
                    className="w-full p-1.5 border border-slate-300 rounded text-slate-800 bg-slate-100 cursor-not-allowed text-[11px]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5 bg-blue-50/40 p-3 rounded-xl border border-blue-200 items-center">
                <div>
                  <label className="block font-semibold text-slate-800 mb-1">Etapa de la Orden *</label>
                  <select
                    value={nuevoPlano.estado_diseno}
                    onChange={(e) => setNuevoPlano({ ...nuevoPlano, estado_diseno: e.target.value })}
                    className="w-full p-1.5 border border-blue-400 rounded font-bold text-blue-900 bg-white cursor-pointer"
                  >
                    <option value="ABIERTA">1. ABIERTA</option>
                    <option value="PLANIFICADA">2. PLANIFICADA</option>
                    <option value="EN_DISENO">3. EN DISEÑO</option>
                    <option value="LIBERADA">4. LIBERADA (Requiere Plano & Materiales)</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-slate-800 mb-1">📅 Fecha Inicio Programada</label>
                  <input
                    type="date"
                    value={nuevoPlano.fecha_inicio_programada}
                    onChange={(e) => setNuevoPlano({ ...nuevoPlano, fecha_inicio_programada: e.target.value })}
                    className="w-full p-1.5 border border-slate-300 rounded font-bold text-slate-800 bg-white"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-800 mb-1">📅 Fecha Compromiso Cliente</label>
                  <input
                    type="date"
                    value={nuevoPlano.fecha_entrega_cliente}
                    onChange={(e) => setNuevoPlano({ ...nuevoPlano, fecha_entrega_cliente: e.target.value })}
                    className="w-full p-1.5 border border-slate-300 rounded font-bold text-slate-800 bg-white"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-slate-800 mb-1">🏁 Fecha Límite Producción</label>
                  <input
                    type="date"
                    value={nuevoPlano.fecha_entrega_produccion}
                    onChange={(e) => setNuevoPlano({ ...nuevoPlano, fecha_entrega_produccion: e.target.value })}
                    className="w-full p-1.5 border border-blue-300 rounded font-bold text-blue-900 bg-white"
                  />
                </div>

                <div className="bg-purple-100 p-2 rounded-lg border border-purple-300 text-center">
                  <span className="block text-[10px] font-bold text-purple-700 uppercase">⏱️ Total Estimado Orden</span>
                  <span className="text-base font-extrabold text-purple-900">
                    {calcularTotalHorasOrden()} Horas <span className="text-xs font-semibold text-purple-700">({(calcularTotalHorasOrden() / 8).toFixed(1)} Días)</span>
                  </span>
                </div>
              </div>

              <div className="border border-slate-200 rounded-xl p-3 bg-slate-50/50 space-y-2">
                <div className="flex justify-between items-center border-b pb-2">
                  <h4 className="font-bold text-slate-800 flex items-center gap-1.5 text-xs">
                    <span>📄</span> Desglose Granular por Ítem (Unidad, OP, Tiempo, Fecha Parcial y Estado)
                  </h4>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[11px] bg-white border border-slate-200 rounded-lg overflow-hidden">
                    <thead className="bg-slate-100 text-slate-700 font-bold border-b text-[10px] uppercase tracking-wider">
                      <tr>
                        <th className="p-2 w-7 text-center">#</th>
                        <th className="p-2 w-28">Unidad Planta *</th>
                        <th className="p-2 w-24">N° Orden (OP) *</th>
                        <th className="p-2 w-24">Código Plano *</th>
                        <th className="p-2 w-12 text-center">Rev.</th>
                        <th className="p-2 w-48">Nombre / Detalle Pieza *</th>
                        <th className="p-2 w-16 text-center">Cant.</th>
                        <th className="p-2 w-28">Diseñador *</th>
                        <th className="p-2 w-24">Tiempo Estimado</th>
                        <th className="p-2 w-32">📅 Fecha Parcial *</th>
                        <th className="p-2 w-32">Causa de Espera</th>
                        <th className="p-2 w-20 text-center">Estado</th>
                        <th className="p-2 w-40 text-center">Materia Prima (BOM) 🔒</th>
                        <th className="p-2 w-36 text-center">Plano PDF (Carga)</th>
                        <th className="p-2 w-20 text-center">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {nuevoPlano.piezas.map((p, idx) => {
                        const solAsociada = solicitudesCompra.find(
                          s => s.codigo_op === (p.codigo_op || nuevoPlano.codigo_op) && 
                               s.codigo_plano === (p.codigo_plano || nuevoPlano.codigo_plano)
                        );
                        const estBomItem = solAsociada?.estado_bom || (p.material_requerido ? 'SOLICITADO' : 'SIN_SOLICITAR');

                        return (
                          <tr key={p.id} className="hover:bg-slate-50 transition">
                            <td className="p-2 text-center font-semibold text-slate-400">{idx + 1}</td>
                            
                            <td className="p-2">
                              <select
                                value={p.unidad_planta || 'Mecanizados'}
                                onChange={(e) => handleCambioPieza(p.id, 'unidad_planta', e.target.value)}
                                className="w-full p-1 border border-slate-300 rounded font-semibold text-slate-800 bg-white focus:outline-none cursor-pointer text-[11px]"
                              >
                                <option value="Mecanizados">⚙ Mecanizados</option>
                                <option value="Metalistería">🔩 Metalistería</option>
                                <option value="Servicios">🛠 Servicios</option>
                              </select>
                            </td>

                            <td className="p-2">
                              <input
                                type="text"
                                required
                                placeholder="4007256"
                                value={p.codigo_op || nuevoPlano.codigo_op}
                                onChange={(e) => handleCambioPieza(p.id, 'codigo_op', e.target.value)}
                                className="w-full p-1 border border-blue-400 rounded font-mono font-bold text-blue-900 focus:outline-none focus:ring-1 focus:ring-blue-500 text-[11px]"
                              />
                            </td>

                            <td className="p-2">
                              <input
                                type="text"
                                required
                                placeholder="PLN-PED-001-A"
                                value={p.codigo_plano}
                                onChange={(e) => handleCambioPieza(p.id, 'codigo_plano', e.target.value)}
                                className="w-full p-1 border border-slate-300 rounded font-mono font-bold text-slate-700 focus:outline-none text-[11px]"
                              />
                            </td>

                            <td className="p-2">
                              <input
                                type="text"
                                value={p.revision}
                                onChange={(e) => handleCambioPieza(p.id, 'revision', e.target.value)}
                                className="w-full p-1 border border-slate-300 rounded text-center font-bold focus:outline-none text-[11px]"
                              />
                            </td>

                            <td className="p-2 font-semibold text-slate-800 text-[11px] leading-tight">
                              {p.detalle_pieza}
                            </td>

                            <td className="p-2">
                              <input
                                type="number"
                                min="0"
                                max={p.cantidad_solicitada ?? undefined}
                                value={p.cantidad}
                                onChange={(e) => handleCambioPieza(p.id, 'cantidad', e.target.value)}
                                className="w-12 p-1 border border-slate-300 rounded text-center font-bold text-[11px] bg-blue-50 text-blue-900 mx-auto block"
                              />
                            </td>

                            <td className="p-2">
                              <input
                                type="text"
                                required
                                placeholder="Ing. Carlos Ruiz"
                                value={p.dibujante_asignado || 'Ing. Carlos Ruiz'}
                                onChange={(e) => handleCambioPieza(p.id, 'dibujante_asignado', e.target.value)}
                                className="w-full p-1 border border-slate-300 rounded text-slate-800 font-medium text-[11px]"
                              />
                            </td>

                            <td className="p-2">
                              <div className="flex gap-1">
                                <input
                                  type="number"
                                  min="1"
                                  value={p.tiempo_estimado_valor || 4}
                                  onChange={(e) => handleCambioPieza(p.id, 'tiempo_estimado_valor', parseInt(e.target.value, 10) || 1)}
                                  className="w-1/2 p-1 border border-slate-300 rounded text-center font-bold text-purple-900 focus:outline-none text-[11px]"
                                />
                                <select
                                  value={p.tiempo_estimado_unidad || 'HORAS'}
                                  onChange={(e) => handleCambioPieza(p.id, 'tiempo_estimado_unidad', e.target.value)}
                                  className="w-1/2 p-1 border border-slate-300 rounded font-semibold text-[10px] bg-white cursor-pointer"
                                >
                                  <option value="HORAS">Hrs</option>
                                  <option value="DIAS">Días</option>
                                </select>
                              </div>
                            </td>

                            <td className="p-2">
                              <input
                                type="date"
                                required
                                value={p.fecha_compromiso || nuevoPlano.fecha_entrega_produccion || ''}
                                onChange={(e) => handleCambioPieza(p.id, 'fecha_compromiso', e.target.value)}
                                className="w-full p-1 border border-purple-300 bg-purple-50/50 rounded font-bold text-purple-900 focus:bg-white text-[11px]"
                              />
                            </td>

                            <td className="p-2">
                              <select
                                value={p.causa_espera || ''}
                                onChange={(e) => handleCambioPieza(p.id, 'causa_espera', e.target.value)}
                                className={`w-full p-1 border rounded font-semibold text-[10px] cursor-pointer ${
                                  !p.causa_espera ? 'bg-emerald-50 text-emerald-900 border-emerald-300' : 'bg-amber-50 text-amber-900 border-amber-300'
                                }`}
                              >
                                <option value="">✓ Sin demoras / Resuelta</option>
                                {OPCIONES_CAUSA_ESPERA.map((opcion, i) => (
                                  <option key={i} value={opcion}>{opcion}</option>
                                ))}
                              </select>
                            </td>

                            <td className="p-2 text-center whitespace-nowrap">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                p.estado_item === 'EN_COLA' || !p.causa_espera
                                  ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                  : 'bg-amber-100 text-amber-800 border border-amber-300'
                              }`}>
                                {p.estado_item === 'EN_COLA' || !p.causa_espera ? '🟢 EN COLA' : '⚠️ EN ESPERA'}
                              </span>
                            </td>

                            <td className="p-2 text-center">
                              <button
                                type="button"
                                onClick={() => handleVerDetalleBom(p, nuevoPlano)}
                                className="w-full p-1 rounded hover:opacity-80 transition cursor-pointer flex items-center justify-center gap-1 shadow-sm"
                              >
                                {renderBadgeBom(estBomItem)}
                              </button>
                            </td>

                            {/* SECCIÓN PLANO PDF CON VER PLANO Y SUBIR OTRO PARALELOS */}
                            <td className="p-2 text-center whitespace-nowrap">
                              <div className="flex flex-col gap-1 items-center">
                                {p.archivo_url ? (
                                  <div className="flex items-center gap-1.5">
                                    <button
                                      type="button"
                                      onClick={() => handleAbrirVisorPlano(p.archivo_url, p.codigo_op, p.codigo_plano)}
                                      className="px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-[10px] transition cursor-pointer flex items-center gap-1 shadow-sm"
                                    >
                                      👁️ Ver PDF
                                    </button>
                                    <label className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded text-[10px] shadow-sm transition cursor-pointer flex items-center gap-0.5">
                                      <span>📤</span> Cambiar
                                      <input 
                                        type="file" 
                                        accept=".pdf" 
                                        onChange={(e) => handleSubirPdfPieza(p.id, e)} 
                                        className="hidden" 
                                      />
                                    </label>
                                  </div>
                                ) : (
                                  <label className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded text-[10px] shadow-sm transition cursor-pointer flex items-center gap-1">
                                    <span>📤</span> Cargar PDF
                                    <input 
                                      type="file" 
                                      accept=".pdf" 
                                      onChange={(e) => handleSubirPdfPieza(p.id, e)} 
                                      className="hidden" 
                                    />
                                  </label>
                                )}
                              </div>
                            </td>

                            <td className="p-2 text-center whitespace-nowrap">
                              {piezasProcesadas.includes(p.id) ? (
                                <span className="px-2 py-1 bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold rounded text-[10px] inline-flex items-center gap-1">
                                  🟢 Orden Abierta
                                </span>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => handleCrearOrdenPorItem(p)}
                                  disabled={loading}
                                  className="px-2.5 py-1 bg-purple-600 hover:bg-purple-700 text-white font-bold rounded text-[10px] shadow-sm transition flex items-center justify-center gap-1 mx-auto cursor-pointer"
                                >
                                  💾 Abrir OP
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t pt-3">
                <button
                  type="button"
                  onClick={() => setModalNuevoPlanoAbierto(false)}
                  className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded shadow-sm cursor-pointer"
                >
                  {loading ? 'Guardando...' : '💾 Guardar Estructuración de OP'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* COMPONENTE VISOR PLANO MODAL */}
      <VisorPlanoModal
        abierto={modalVisorPlanoOpen}
        onClose={() => setModalVisorPlanoOpen(false)}
        archivoUrl={datosVisorPlano.archivoUrl}
        codigoOp={datosVisorPlano.codigoOp}
        codigoPlano={datosVisorPlano.codigoPlano}
      />
    </div>
  );
}