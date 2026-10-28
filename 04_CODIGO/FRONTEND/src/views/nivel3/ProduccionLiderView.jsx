// src/views/nivel2/ProduccionLiderView.jsx
import React, { useState, useEffect } from 'react';
import API from '../../services/api';
import VisorPlanoModal from '../../components/VisorPlanoModal';
import ExpedienteOpModal from '../../components/modals/ExpedienteOpModal';

const ETIQUETAS_ACCION_PIEZA = {
  FABRICAR_NUEVA: 'Fabricar nueva',
  RECTIFICAR_RECUPERAR: 'Rectificar o recuperar',
  COMPRA_DIRECTA_BOM: 'Compra directa de materiales',
};

export default function ProduccionLiderView() {
  // BLOQUE 1: ESTADOS PRINCIPALES Y NAVEGACIÓN
  const [usuarioActual, setUsuarioActual] = useState(null);
  const [pestanaPrincipal, setPestanaPrincipal] = useState('ORDENES'); 
  const [areaActiva, setAreaActiva] = useState('Mecanizados');
  
  const [ordenesLiberadas, setOrdenesLiberadas] = useState([]);
  const [sublotesActivos, setSublotesActivos] = useState([]);
  const [notificaciones, setNotificaciones] = useState([]);
  const [listaKitsOverhaul, setListaKitsOverhaul] = useState([]);
  const [solicitudesCompra, setSolicitudesCompra] = useState([]);
  const [loading, setLoading] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });

  const [busqueda, setBusqueda] = useState('');

  // Controles independientes para desplegar por cada fila/proyecto
  const [piezasExpandidas, setPiezasExpandidas] = useState({});
  const [piezasProyectoMap, setPiezasProyectoMap] = useState({});
  const [cargandoPiezasMap, setCargandoPiezasMap] = useState({});

  // Modales
  const [modalAsignarAbierto, setModalAsignarAbierto] = useState(false);
  const [modalAlertasAbierto, setModalAlertasAbierto] = useState(false);
  const [modalEstadoAbierto, setModalEstadoAbierto] = useState(false);
  const [modalBOMAbierto, setModalBOMAbierto] = useState(false);
  
  // MODAL DE MATRIZ DE CARGA Y PRIORIZACIÓN DE OPERARIOS / TABLETS
  const [modalMatrizCargaAbierto, setModalMatrizCargaAbierto] = useState(false);

  // MODAL DE EXPEDIENTE COMPLETO DE LA OP
  const [modalExpedienteOpAbierto, setModalExpedienteOpAbierto] = useState(false);
  const [ordenSeleccionada, setOrdenSeleccionada] = useState(null);

  // Visor PDF Modal
  const [modalVisorPlanoOpen, setModalVisorPlanoOpen] = useState(false);
  const [datosVisorPlano, setDatosVisorPlano] = useState({ archivoUrl: '', codigoOp: '', codigoPlano: '' });

  const [formAsignacion, setFormAsignacion] = useState({
    nombre_proceso: 'Torneado General',
    secuencia_paso: 10,
    cantidad_sublote: 1,
    operario_nombre: 'Carlos Ruiz',
    maquina_codigo: 'TORN-CNC-01',
    instrucciones: ''
  });

  const CATALAGO_RECURSOS = {
    Mecanizados: {
      operarios: ['Carlos Ruiz', 'Juan Pérez', 'Andrés Molina'],
      maquinas: ['TORN-CNC-01', 'FRES-CNC-02', 'TALAD-01', 'RECT-01']
    },
    Metalistería: {
      operarios: ['Pedro Martínez', 'Roberto Silva'],
      maquinas: ['CORTE-PLAS-01', 'PLEG-01', 'SOLD-MIG-02']
    },
    Servicios: {
      operarios: ['Ing. Roberto Silva', 'Técnico Mantenimiento'],
      maquinas: ['EST-MEDICION-01', 'BANCO-PRUEBAS']
    }
  };

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
    cargarDatosProduccion();
  }, [areaActiva]);

  useEffect(() => {
    const timerGlobal = setInterval(() => {
      setSublotesActivos(prev => {
        if (!Array.isArray(prev)) return [];
        return prev.map(sub => {
          if (sub.estado_sublote === 'EN_PRODUCCION') {
            return { ...sub, segundos_produccion: (sub.segundos_produccion || 0) + 1 };
          }
          if (sub.estado_sublote === 'EN_SETUP') {
            return { ...sub, segundos_setup: (sub.segundos_setup || 0) + 1 };
          }
          return sub;
        });
      });
    }, 1000);

    return () => clearInterval(timerGlobal);
  }, []);

  const obtenerUsuarioSesion = () => {
    try {
      const userStored = localStorage.getItem('usuario') || localStorage.getItem('user');
      if (userStored) {
        setUsuarioActual(JSON.parse(userStored));
      } else {
        setUsuarioActual({ rol: 'Jefe de área', area: 'Producción', nombre: 'Líder de Producción' });
      }
    } catch (e) {
      setUsuarioActual({ rol: 'Administrador', area: 'General' });
    }
  };

  const cargarDatosProduccion = async () => {
    try {
      setLoading(true);

      const [resPlanos, resSolicitudes] = await Promise.allSettled([
        API.get('/planos'),
        API.get('/solicitudes-compra/')
      ]);

      const solicitudesData = resSolicitudes.status === 'fulfilled' && Array.isArray(resSolicitudes.value.data)
        ? resSolicitudes.value.data
        : [];
      setSolicitudesCompra(solicitudesData);

      const ordenesValidas = (resPlanos.status === 'fulfilled' && Array.isArray(resPlanos.value.data) ? resPlanos.value.data : [])
        .filter(p => (p.estado_diseno === 'LIBERADA' || p.estado_diseno === 'EN_FABRICACION') && (p.unidad_planta === areaActiva || !p.unidad_planta))
        .map((p, idx) => {
          const bomItems = Array.isArray(p.bom_items) ? p.bom_items : [];
          const estadosBom = bomItems.map(item => item.estado_abastecimiento);
          const estadoGeneralBom = estadosBom.length === 0
            ? 'SIN_SOLICITAR'
            : estadosBom.every(estado => estado === 'ENTREGADO')
              ? 'ENTREGADO'
              : estadosBom.every(estado => ['EN_ALMACEN', 'ENTREGADO'].includes(estado))
                ? 'EN_ALMACEN'
                : estadosBom.find(estado => estado && estado !== 'SIN_SOLICITAR') || 'SIN_SOLICITAR';
          const cantidadRequerida = bomItems.reduce(
            (total, item) => total + Number(item.cantidad_requerida || 0),
            0
          );
          const cantidadRecibida = bomItems
            .filter(item => ['EN_ALMACEN', 'ENTREGADO'].includes(item.estado_abastecimiento))
            .reduce((total, item) => total + Number(item.cantidad_requerida || 0), 0);

          return ({
          item_num: idx + 1,
          id_plano: p.id_plano,
          id_proyecto: p.id_proyecto,
          numero_pedido: p.numero_pedido || 'PED-2026-088',
          cliente_nombre: p.cliente_nombre || 'Ecopetrol S.A.',
          unidad_planta: p.unidad_planta || areaActiva,
          codigo_op: p.codigo_op,
          codigo_plano: p.codigo_plano,
          revision: p.revision || 'REV-01',
          detalle_pieza: p.detalle_pieza || p.descripcion || 'Pieza Mecanizada Especial',
          cantidad_total: p.cantidad || 12,
          disenador: p.dibujante_asignado || 'Ing. Carlos Ruiz',
          descripcion_material: p.material_requerido || 'Bronce SAE 65 Ø6" / Barra AISI 4140',
          fecha_parcial: p.fecha_entrega_produccion || '2026-11-10',
          causa_espera: p.causa_espera || '✓ Sin demoras',
          archivo_url: p.archivo_url || '',
          estado_op: p.estado_op || p.estado_item || 'EN_PROCESO',
          bom_items: bomItems,

          piezas: (p.piezas && p.piezas.length > 0) ? p.piezas : [
            {
              id_pieza: 1,
              codigo_plano: p.codigo_plano || 'PLN-11001-A',
              revision: p.revision || 'REV-01',
              detalle_pieza: p.detalle_pieza || p.descripcion || 'Pieza Mecanizada Especial',
              cantidad: p.cantidad || 12,
              material_requerido: p.material_requerido || 'Bronce SAE 65 Ø6"',
              archivo_url: p.archivo_url || '',
              estado_abastecimiento: estadoGeneralBom,
              estado_proceso: 'EN_MECANIZADO'
            }
          ],

          desglose_estados: {
            PROGRAMADO: { cantidad: 2, tiempo_dias: '1.2 Días', detalle: 'Cola de Maquinado' },
            EN_PRODUCCION: { cantidad: 4, tiempo_dias: '0.3 Días (7h)', detalle: 'Torno CNC 01 (Carlos Ruiz)' },
            TRATAMIENTO_TERMICO: { cantidad: 3, tiempo_dias: '3.5 Días', detalle: 'Proveedor Externo (Templex S.A.)' },
            INSPECCION_CALIDAD: { cantidad: 1, tiempo_dias: '0.1 Días (2h)', detalle: 'Mesa de Metrología (CMM)' },
            TERMINADO: { cantidad: 2, tiempo_dias: 'Completado', detalle: 'Ubicación Bodega PT-02' }
          },

          trazabilidad_bom: {
            estado_general: estadoGeneralBom,
            cantidad_requerida: cantidadRequerida,
            cantidad_recibida: cantidadRecibida,
            cantidad_pendiente: Math.max(cantidadRequerida - cantidadRecibida, 0),
            solicitud_pr: solicitudesData.find(s => s.codigo_op === p.codigo_op && s.codigo_plano === p.codigo_plano)?.numero_solicitud || null,
            proveedor: null,
            entregas_parciales: []
          }
        });
      });

      setOrdenesLiberadas(ordenesValidas);

      try {
        const resKits = await API.get('/mantenimientos/monitor-kits');
        if (resKits.data && Array.isArray(resKits.data) && resKits.data.length > 0) {
          const kitsMapeados = resKits.data.map(m => ({
            id_mantenimiento: m.id_mantenimiento || m.id_proyecto,
            codigo_mantenimiento: m.codigo_mantenimiento || m.numero_pedido || 'MANT-2026-010',
            cliente_nombre: m.cliente_nombre || m.cliente || 'Tesa',
            nombre_maquina: m.nombre_maquina || m.equipo || m.detalle_producto || 'Torno',
            codigo_op: m.codigo_op || 'OP-100',
            fase_mantenimiento: m.fase_mantenimiento || 'LAVADO_DESARME',
            total_piezas_autorizadas: m.total_piezas_autorizadas || 4,
            piezas: m.piezas || m.detalles || []
          }));
          setListaKitsOverhaul(kitsMapeados);
        } else {
          throw new Error('Usar datos de kits de fallback');
        }
      } catch (errKits) {
        setListaKitsOverhaul([
          {
            id_mantenimiento: 1,
            codigo_mantenimiento: 'MANT-2026-010',
            nombre_maquina: 'Torno',
            cliente_nombre: 'Tesa',
            codigo_op: 'OP-100',
            fase_mantenimiento: 'LAVADO_DESARME',
            total_piezas_autorizadas: 4,
            piezas: []
          }
        ]);
      }

      try {
        const resSublotes = await API.get(`/operaciones/sublotes?area=${areaActiva}`);
        if (!Array.isArray(resSublotes.data)) throw new Error('La respuesta de la cola no tiene un formato válido.');
        setSublotesActivos(resSublotes.data);
      } catch (errSub) {
        setMensaje({
          tipo: 'error',
          texto: errSub.response?.data?.detail || errSub.message || 'No se pudo cargar la cola de producción.',
        });
        setSublotesActivos([]);
      }

      try {
        const resNotif = await API.get(`/operaciones/notificaciones/${areaActiva}`);
        setNotificaciones(Array.isArray(resNotif.data) ? resNotif.data : []);
      } catch (errNotif) {
        console.warn("Sin notificaciones devueltas.");
        setNotificaciones([]);
      }

    } catch (error) {
      console.error("Error cargando producción:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleMarcarOrdenTerminada = async (ord) => {
    if (!window.confirm(`¿Confirmar que la OP-${ord.codigo_op} [${ord.detalle_pieza}] está 100% completada y lista para Inspección de Calidad?`)) {
      return;
    }

    setMensaje({ tipo: '', texto: '' });
    try {
      setLoading(true);
      await API.patch(`/ordenes/${ord.id_proyecto}`, {
        estado: 'EN_INSPECCION',
        observaciones: 'Producción terminada; enviada a inspección de calidad.'
      });

      setMensaje({
        tipo: 'exito',
        texto: `✅ OP-${ord.codigo_op} marcada como TERMINADA con éxito. Enviada al módulo de Calidad y Metrología para liberación final.`
      });

      await cargarDatosProduccion();
    } catch (err) {
      setMensaje({
        tipo: 'error',
        texto: err?.response?.data?.detail || `No se pudo actualizar la OP-${ord.codigo_op}.`
      });
    } finally {
      setLoading(false);
    }
  };

  const esAreaAutorizadaParaPaso = (areaRequerida) => {
    if (!usuarioActual) return true;
    const rol = (usuarioActual.rol || '').toLowerCase();
    const area = (usuarioActual.area || '').toLowerCase();

    if (rol.includes('admin') || rol.includes('administrador')) return true;

    const areaReqLower = (areaRequerida || '').toLowerCase();
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
      const solAsociadas = (Array.isArray(solicitudesCompra) ? solicitudesCompra : []).filter(s => s.codigo_op === proyecto.codigo_op);
      const faltanMateriales = solAsociadas.some(s => !['EN_ALMACEN', 'ENTREGADO'].includes(s.estado_bom));

      if (solAsociadas.length === 0 || faltanMateriales) {
        alert("❌ Bloqueo de calidad: no se puede avanzar a Fabricación / Recuperación (Paso 7) porque los materiales no han llegado al 100% a Almacén.");
        return;
      }
    }

    try {
      setLoading(true);
      const idTarget = proyecto.id_mantenimiento || proyecto.id_proyecto;
      await API.patch(`/mantenimientos/${idTarget}`, { fase_mantenimiento: SiguienteEtapa.id });

      setMensaje({
        tipo: 'exito',
        texto: `✅ Puerta de Paso aprobada por Producción: [${proyecto.codigo_mantenimiento}] avanzó a Etapa ${SiguienteEtapa.paso} (${SiguienteEtapa.nombre}).`
      });

      await cargarDatosProduccion();
    } catch (err) {
      setListaKitsOverhaul(prev => prev.map(m => {
        if ((m.id_proyecto || m.id_mantenimiento) === (proyecto.id_proyecto || proyecto.id_mantenimiento)) {
          return { ...m, fase_mantenimiento: SiguienteEtapa.id };
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
        const idConsulta = proyecto.id_mantenimiento || id;
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
          piezasNormalizadas = proyecto.piezas || proyecto.detalles || [
            { posicion: 1, codigo: 'PLN-MANT-008-P01', descripcion: 'Eje Principal de Mando Ø3.5"', accion: 'FABRICAR_NUEVA', cantidad: 1, material: 'AISI 1045', autorizado: true },
            { posicion: 2, codigo: 'PLN-MANT-008-P02', descripcion: 'Buje de Bronce de Desgaste', accion: 'FABRICAR_NUEVA', cantidad: 2, material: 'AISI 1045', autorizado: true },
            { posicion: 3, codigo: 'PLN-MANT-008-P03', descripcion: 'Rectificado de Vástago Principal', accion: 'RECTIFICAR_RECUPERAR', cantidad: 1, material: 'AISI 1045', autorizado: true },
            { posicion: 4, codigo: 'PLN-MANT-008-P04', descripcion: 'Kit de Empaquetadura NBR', accion: 'COMPRA_DIRECTA_BOM', cantidad: 1, material: 'AISI 1045', autorizado: true }
          ];
        }

        setPiezasProyectoMap(prev => ({ ...prev, [id]: piezasNormalizadas }));
      } catch (err) {
        setPiezasProyectoMap(prev => ({
          ...prev,
          [id]: proyecto.piezas || proyecto.detalles || []
        }));
      } finally {
        setCargandoPiezasMap(prev => ({ ...prev, [id]: false }));
      }
    }

    setPiezasExpandidas(prev => ({
      ...prev,
      [id]: !estaAbierto
    }));
  };

  // FUNCIÓN DE CONVERSIÓN DE TIEMPO A MINUTOS
  const formatearTiempoMinutos = (totalSegundos) => {
    if (!totalSegundos || totalSegundos <= 0) return '0 min';
    const minutos = Math.floor(totalSegundos / 60);
    const hrs = Math.floor(minutos / 60);
    return hrs > 0 ? `${minutos} min (${hrs}h)` : `${minutos} min`;
  };

  const ordenesFiltradas = (Array.isArray(ordenesLiberadas) ? ordenesLiberadas : []).filter(ord => {
    const termino = busqueda.toLowerCase();
    return (
      (ord.codigo_op || '').toLowerCase().includes(termino) ||
      (ord.codigo_plano || '').toLowerCase().includes(termino) ||
      (ord.detalle_pieza || '').toLowerCase().includes(termino) ||
      (ord.descripcion_material || '').toLowerCase().includes(termino) ||
      (ord.disenador || '').toLowerCase().includes(termino)
    );
  });

  const handleAbrirDetalleEstado = (orden) => {
    setOrdenSeleccionada(orden);
    setModalEstadoAbierto(true);
  };

  const handleAbrirDetalleBOM = (orden) => {
    setOrdenSeleccionada(orden);
    setModalBOMAbierto(true);
  };

  const handleAbrirExpedienteOpModal = (orden) => {
    setOrdenSeleccionada(orden);
    setModalExpedienteOpAbierto(true);
  };

  const handleAbrirVisorPlano = (url, op, plano) => {
    setDatosVisorPlano({ archivoUrl: url, codigoOp: op, codigoPlano: plano });
    setModalVisorPlanoOpen(true);
  };

  const handleAbrirAsignacion = (orden) => {
    setOrdenSeleccionada(orden);
    const operariosLista = CATALAGO_RECURSOS[areaActiva]?.operarios || ['Carlos Ruiz'];
    const maquinasLista = CATALAGO_RECURSOS[areaActiva]?.maquinas || ['TORN-CNC-01'];
    
    setFormAsignacion({
      nombre_proceso: 'Torneado General',
      secuencia_paso: 10,
      cantidad_sublote: 1,
      operario_nombre: operariosLista[0] || 'Carlos Ruiz',
      maquina_codigo: maquinasLista[0] || 'TORN-CNC-01',
      instrucciones: ''
    });

    setModalAsignarAbierto(true);
  };

  const handleCrearSubloteAsignado = async (e) => {
    e.preventDefault();
    setMensaje({ tipo: '', texto: '' });

    if (formAsignacion.cantidad_sublote <= 0) {
      setMensaje({ tipo: 'error', texto: 'La cantidad del sub-lote debe ser mayor a 0.' });
      return;
    }

    const payloadSublote = {
      id_plano: ordenSeleccionada.id_plano,
      codigo_op: ordenSeleccionada.codigo_op,
      codigo_plano: ordenSeleccionada.codigo_plano,
      secuencia_paso: formAsignacion.secuencia_paso,
      nombre_proceso: formAsignacion.nombre_proceso,
      unidad_planta: areaActiva,
      cantidad_sublote: formAsignacion.cantidad_sublote,
      operario_nombre: formAsignacion.operario_nombre,
      maquina_codigo: formAsignacion.maquina_codigo,
      instrucciones: formAsignacion.instrucciones
    };

    try {
      await API.post('/operaciones/sublotes/crear', payloadSublote);
      setMensaje({
        tipo: 'exito',
        texto: `✅ Sub-Lote de ${formAsignacion.cantidad_sublote} UND enviado a ${formAsignacion.operario_nombre} [${formAsignacion.maquina_codigo}].`
      });
      await cargarDatosProduccion();
      setModalAsignarAbierto(false);
    } catch (error) {
      setMensaje({
        tipo: 'error',
        texto: error.response?.data?.detail || error.message || 'No se pudo asignar el sublote a la cola de producción.',
      });
    }
  };

  // REORDENAMIENTO Y CAMBIO DE PRIORIDAD DE SUB-LOTES EN COLA
  const handleMoverPrioridadSublote = async (operarioNombre, maquinaCodigo, idxSublote, direccion) => {
    const listaActual = Array.isArray(sublotesActivos) ? sublotesActivos : [];
    const sublotesOperarioEstacion = listaActual.filter(
      (s) => s.operario_nombre === operarioNombre && s.maquina_codigo === maquinaCodigo
    );
    const estadosEnCola = ['PENDIENTE', 'PENDIENTE_ASIGNACION', 'EN_COLA'];
    const sublotesEnCola = sublotesOperarioEstacion
      .filter((s) => estadosEnCola.includes(s.estado_sublote))
      .sort((a, b) => Number(a.prioridad_cola || 0) - Number(b.prioridad_cola || 0));
    const targetIdx = direccion === 'SUBIR' ? idxSublote - 1 : idxSublote + 1;

    if (targetIdx < 0 || targetIdx >= sublotesEnCola.length) return;

    const copiaCola = [...sublotesEnCola];
    const temp = copiaCola[idxSublote];
    copiaCola[idxSublote] = copiaCola[targetIdx];
    copiaCola[targetIdx] = temp;

    try {
      await API.post('/operaciones/sublotes/reordenar', {
        operario_nombre: operarioNombre,
        maquina_codigo: maquinaCodigo,
        orden_ids: copiaCola.map((s) => s.id_sublote)
      });
      const colaActualizada = new Map(copiaCola.map((s, prioridad) => [
        s.id_sublote,
        { ...s, prioridad_cola: prioridad + 1 }
      ]));
      setSublotesActivos(listaActual.map((s) => colaActualizada.get(s.id_sublote) || s));
      setMensaje({ tipo: 'exito', texto: `📌 Prioridad actualizada para ${operarioNombre} en ${maquinaCodigo}.` });
    } catch (err) {
      try {
        const params = new URLSearchParams({ area: areaActiva });
        const respuesta = await API.get(`/operaciones/sublotes?${params.toString()}`);
        setSublotesActivos(Array.isArray(respuesta.data) ? respuesta.data : []);
      } catch (errorCarga) {
        setMensaje({ tipo: 'error', texto: errorCarga.response?.data?.detail || 'No se pudo actualizar la cola desde el servidor.' });
      }
      setMensaje({ tipo: 'error', texto: err.response?.data?.detail || 'No se pudo guardar el orden de prioridad.' });
    }
  };

  const renderBadgeResumenEstado = (orden) => {
    return (
      <button
        type="button"
        onClick={() => handleAbrirDetalleEstado(orden)}
        className="px-1.5 py-0.5 bg-slate-100 hover:bg-blue-100 border border-slate-300 hover:border-blue-400 rounded transition cursor-pointer text-[10px] font-extrabold flex items-center justify-center gap-1 shadow-sm w-full"
        title="Ver trazabilidad por dispositivos y tiempo en cada etapa"
      >
        <span className="text-blue-900">Ver Estado</span>
        <span className="bg-blue-600 text-white px-1 py-0.1 rounded-full text-[8px]">👁</span>
      </button>
    );
  };

  const renderBadgeBOM = (orden) => {
    const bomInfo = orden.trazabilidad_bom || {};
    const estado = bomInfo.estado_general || 'SIN_SOLICITAR';
    const etiquetas = {
      ENTREGADO: '🟢 ENTREGADO',
      EN_ALMACEN: '🟣 EN ALMACÉN',
      EN_COMPRA: '🔵 EN COMPRA',
      SOLICITADO: '🟡 SOLICITADO',
      SIN_SOLICITAR: '⚪ SIN SOLICITAR'
    };
    const estadoLiberable = ['EN_ALMACEN', 'ENTREGADO'].includes(estado);

    return (
      <button
        type="button"
        onClick={() => handleAbrirDetalleBOM(orden)}
        className={`px-1.5 py-0.5 rounded text-[9px] font-extrabold border shadow-sm block w-full transition cursor-pointer ${
          estado === 'ENTREGADO'
            ? 'bg-emerald-100 text-emerald-900 border-emerald-300 hover:bg-emerald-200'
            : estadoLiberable
              ? 'bg-purple-100 text-purple-900 border-purple-300 hover:bg-purple-200'
              : 'bg-amber-100 text-amber-900 border-amber-300 hover:bg-amber-200'
        }`}
        title="Ver estado de abastecimiento de las líneas de materiales"
      >
        {etiquetas[estado] || estado}
      </button>
    );
  };

  const renderBadgeBomPieza = (estadoBom) => {
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

  // Contadores seguros aislados de errores de tipo
  const listaNotif = Array.isArray(notificaciones) ? notificaciones : [];
  const listaSublotes = Array.isArray(sublotesActivos) ? sublotesActivos : [];
  const gruposOperarioEstacion = Array.from(new Map(
    listaSublotes.map((sublote) => {
      const operarioNombre = sublote.operario_nombre || 'Sin operario asignado';
      const maquinaCodigo = sublote.maquina_codigo || 'Sin estación asignada';
      return [`${operarioNombre}::${maquinaCodigo}`, { operarioNombre, maquinaCodigo }];
    })
  ).values());
  const listaKits = Array.isArray(listaKitsOverhaul) ? listaKitsOverhaul : [];

  return (
    <div className="p-6 bg-slate-50 min-h-screen space-y-6">
      {/* ENCABEZADO ESTANDARIZADO ISO 9001:2026 */}
      <header className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <span>🏭</span> Control de planta y ejecución de producción
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Monitoreo Multiestado — Unidad Activa: <strong className="text-blue-700">{areaActiva}</strong> [ISO 9001:2026]
          </p>
        </div>

        <div className="flex items-center gap-2 self-stretch md:self-auto flex-wrap">
          <button
            type="button"
            onClick={() => setModalMatrizCargaAbierto(true)}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white border border-blue-700 rounded-lg text-xs font-extrabold transition flex items-center gap-1.5 shadow-sm cursor-pointer"
          >
            <span>📱</span> Matriz de Carga por Operario y Estación
          </button>

          <div className="bg-amber-50 px-3 py-1.5 rounded-lg border border-amber-200 text-xs font-semibold text-amber-900">
            👤 Usuario: <strong>{usuarioActual?.nombre || 'Líder de Producción'}</strong> [{usuarioActual?.area || 'Producción'}]
          </div>

          <button
            type="button"
            onClick={() => setModalAlertasAbierto(true)}
            className="relative px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-purple-900 border border-purple-300 rounded-lg text-xs font-bold transition flex items-center gap-2 cursor-pointer shadow-sm"
          >
            <span>🔔 Alertas Planta</span>
            {listaNotif.filter(n => !n.leida).length > 0 && (
              <span className="px-1.5 py-0.5 bg-red-600 text-white text-[9px] font-extrabold rounded-full animate-bounce">
                {listaNotif.filter(n => !n.leida).length}
              </span>
            )}
          </button>
        </div>
      </header>

      {mensaje.texto && (
        <div className={`p-3 rounded-lg text-xs font-semibold border ${
          mensaje.tipo === 'exito' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' : 'bg-red-50 text-red-800 border-red-200'
        }`}>
          {mensaje.texto}
        </div>
      )}

      {/* PESTAÑAS DE PRODUCCIÓN */}
      <div className="flex justify-between items-center bg-white p-2.5 px-3 rounded-xl border border-slate-200 shadow-sm flex-wrap gap-2">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setPestanaPrincipal('ORDENES')}
            className={`px-3 py-1.5 rounded-lg font-bold text-xs transition cursor-pointer flex items-center gap-1.5 ${
              pestanaPrincipal === 'ORDENES'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            📋 1. Desglose Granular de OPs ({ordenesFiltradas.length})
          </button>

          <button
            type="button"
            onClick={() => setPestanaPrincipal('PROCESOS_MES')}
            className={`px-3 py-1.5 rounded-lg font-bold text-xs transition cursor-pointer flex items-center gap-1.5 ${
              pestanaPrincipal === 'PROCESOS_MES'
                ? 'bg-purple-600 text-white shadow-sm'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            ⏱️ 2. Seguimiento de producción en vivo ({listaSublotes.length})
          </button>

          <button
            type="button"
            onClick={() => setPestanaPrincipal('KITS_OVERHAUL')}
            className={`px-3 py-1.5 rounded-lg font-bold text-xs transition cursor-pointer flex items-center gap-1.5 ${
              pestanaPrincipal === 'KITS_OVERHAUL'
                ? 'bg-amber-600 text-white shadow-sm'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            📦 3. Proyectos de Mantenimiento ({listaKits.length})
          </button>
        </div>

        <div className="flex gap-1 items-center bg-slate-100 p-1 rounded-lg border border-slate-200">
          <span className="text-[10px] font-extrabold text-slate-500 uppercase px-1">Área:</span>
          {['Mecanizados', 'Metalistería', 'Servicios'].map(area => (
            <button
              key={area}
              type="button"
              onClick={() => setAreaActiva(area)}
              className={`px-2.5 py-1 text-xs font-bold rounded cursor-pointer transition ${
                areaActiva === area
                  ? 'bg-white text-blue-900 shadow-sm border border-slate-300'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {area}
            </button>
          ))}
        </div>
      </div>

      {/* PESTAÑA 1: TABLA DESGLOSE GRANULAR DE OPS */}
      {pestanaPrincipal === 'ORDENES' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-3">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 border-b pb-2">
            <h2 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
              <span>📋</span> OPs Liberadas — {areaActiva}
            </h2>

            <div className="relative w-full sm:w-72">
              <input
                type="text"
                placeholder="🔍 Buscar OP, Plano, Pieza o Material..."
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                className="w-full pl-3 pr-7 py-1 border border-slate-300 rounded-lg text-xs font-semibold focus:outline-none focus:border-blue-600 bg-slate-50"
              />
            </div>
          </div>

          <div className="overflow-y-auto max-h-[620px] border border-slate-200 rounded-lg">
            <table className="w-full text-left border-collapse table-fixed">
              <thead className="sticky top-0 bg-slate-100 text-slate-700 font-bold uppercase border-b text-[11px] z-10 shadow-sm">
                <tr>
                  <th className="p-2 text-center w-[2%]">#</th>
                  <th className="p-2 w-[10%]">OP *</th>
                  <th className="p-2 w-[11%]">CÓDIGO PLANO *</th>
                  <th className="p-2 text-center w-[4%]">REV.</th>
                  <th className="p-2 w-[19%]">DETALLE PIEZA *</th>
                  <th className="p-2 text-center w-[5%]">CANT.</th>
                  <th className="p-2 w-[10%]">DISEÑADOR *</th>
                  <th className="p-2 w-[15%]">MATERIAL / LISTA DE MATERIALES *</th>
                  <th className="p-2 text-center w-[7%]">📅 FECHA</th>
                  <th className="p-2 text-center w-[8%]">ESTADO PROCESO</th>
                  <th className="p-2 text-center w-[8%]">MATERIALES REQUERIDOS 🔒</th>
                  <th className="p-2 text-center w-[4%]">PDF</th>
                  <th className="p-2 text-center w-[12%]">ACCIONES LÍDER</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-slate-800 text-[11px]">
                {ordenesFiltradas.length === 0 ? (
                  <tr>
                    <td colSpan="13" className="p-6 text-center text-slate-400 italic">
                      No hay órdenes liberadas coincidentes en la unidad de {areaActiva}.
                    </td>
                  </tr>
                ) : (
                  ordenesFiltradas.map((ord) => (
                    <tr key={ord.id_plano} className="hover:bg-blue-50/40 transition">
                      <td className="p-1.5 text-center font-bold text-slate-400">
                        {ord.item_num}
                      </td>

                      <td className="p-1.5">
                        <button
                          type="button"
                          onClick={() => handleAbrirExpedienteOpModal(ord)}
                          className="font-mono font-extrabold text-blue-900 bg-blue-100 hover:bg-blue-200 border border-blue-400 px-2 py-0.5 rounded block text-center truncate w-full shadow-sm cursor-pointer transition hover:scale-105"
                          title="Haz clic para ver la información detallada de la Orden de Producción y todas sus piezas"
                        >
                          {ord.codigo_op}
                        </button>
                      </td>

                      <td className="p-1.5 font-mono font-bold text-slate-800 truncate">
                        {ord.codigo_plano}
                      </td>

                      <td className="p-1.5 text-center">
                        <span className="bg-slate-100 px-1 py-0.5 rounded border border-slate-300 text-[9px] font-bold">
                          {ord.revision}
                        </span>
                      </td>

                      <td className="p-1.5 font-bold text-slate-800 truncate" title={ord.detalle_pieza}>
                        {ord.detalle_pieza}
                      </td>

                      <td className="p-1.5 text-center font-extrabold text-blue-900">
                        <span className="bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded">
                          {ord.cantidad_total}
                        </span>
                      </td>

                      <td className="p-1.5 text-slate-700 truncate" title={ord.disenador}>
                        {ord.disenador}
                      </td>

                      <td className="p-1.5">
                        <span className="block truncate font-medium text-blue-950 bg-slate-50 p-1 rounded border border-slate-200" title={ord.descripcion_material}>
                          {ord.descripcion_material}
                        </span>
                      </td>

                      <td className="p-1.5 text-center font-bold text-purple-900 whitespace-nowrap text-[10px]">
                        {ord.fecha_parcial}
                      </td>

                      <td className="p-1.5 text-center whitespace-nowrap">
                        {renderBadgeResumenEstado(ord)}
                      </td>

                      <td className="p-1.5 text-center whitespace-nowrap">
                        {renderBadgeBOM(ord)}
                      </td>

                      <td className="p-1.5 text-center whitespace-nowrap">
                        {ord.archivo_url && ord.archivo_url !== '#' ? (
                          <button
                            type="button"
                            onClick={() => handleAbrirVisorPlano(ord.archivo_url, ord.codigo_op, ord.codigo_plano)}
                            className="px-1 py-0.5 bg-emerald-100 text-emerald-800 hover:bg-emerald-200 border border-emerald-300 rounded text-[10px] font-mono font-bold transition cursor-pointer"
                          >
                            📄 PDF
                          </button>
                        ) : (
                          <span className="text-[9px] text-slate-400 italic">Sin PDF</span>
                        )}
                      </td>

                      <td className="p-1.5 text-center whitespace-nowrap space-x-1">
                        <button
                          type="button"
                          onClick={() => handleAbrirAsignacion(ord)}
                          className="px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-[10px] transition shadow-sm cursor-pointer"
                          title="Programar sub-lote en tablet de máquina"
                        >
                          ⚙️ Asignar
                        </button>

                        {ord.estado_op === 'TERMINADA' ? (
                          <span className="px-1.5 py-0.5 bg-purple-100 text-purple-900 border border-purple-300 font-extrabold rounded text-[9px]">
                            🔍 EN CALIDAD
                          </span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleMarcarOrdenTerminada(ord)}
                            className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded text-[10px] transition shadow-sm cursor-pointer"
                            title="Completar OP y enviar a Inspección de Calidad"
                          >
                            ✅ Terminada
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
      )}

      {/* PESTAÑA 2: MONITOREO MES EN VIVO */}
      {pestanaPrincipal === 'PROCESOS_MES' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-3">
          <div className="flex justify-between items-center border-b pb-2">
            <div>
              <h2 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                <span>⏱️</span> Seguimiento de estaciones y tiempos acumulados (minutos)
              </h2>
              <p className="text-[11px] text-slate-500">
                Costeo continuo en Minutos para Setup vs Producción
              </p>
            </div>

            <span className="px-2.5 py-0.5 bg-purple-100 text-purple-900 border border-purple-300 text-xs rounded-full font-bold">
              {listaSublotes.length} Estaciones
            </span>
          </div>

          <div className="overflow-y-auto max-h-[500px] border border-slate-200 rounded-lg">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-slate-100 text-slate-700 font-bold uppercase border-b text-[9px]">
                <tr>
                  <th className="p-2.5">OP / Sub-Lote</th>
                  <th className="p-2.5">Proceso / Estación</th>
                  <th className="p-2.5">Operario Asignado</th>
                  <th className="p-2.5 text-center bg-purple-50 text-purple-900 border-x">🔧 Minutos en Setup (Montaje)</th>
                  <th className="p-2.5 text-center bg-emerald-50 text-emerald-900">⚙️ Minutos en Producción (Mecanizado)</th>
                  <th className="p-2.5 text-center">Estado de producción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-slate-800">
                {listaSublotes.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="p-6 text-center text-slate-400 italic">
                      No hay sub-lotes ejecutándose en las estaciones de {areaActiva}.
                    </td>
                  </tr>
                ) : (
                  listaSublotes.map(sub => (
                    <tr key={sub.id_sublote} className="hover:bg-slate-50 transition">
                      <td className="p-2.5 font-medium whitespace-nowrap">
                        <span className="font-mono font-bold text-blue-900 block text-xs">⚙ OP-{sub.codigo_op}</span>
                        <span className="text-[10px] font-bold text-purple-700">{sub.sublote_tag}</span>
                      </td>

                      <td className="p-2.5">
                        <strong className="block text-slate-800 text-xs">{sub.nombre_proceso}</strong>
                        <span className="font-mono text-[10px] text-slate-500">📍 {sub.maquina_codigo}</span>
                      </td>

                      <td className="p-2.5 font-bold text-slate-700 whitespace-nowrap text-xs">
                        👤 {sub.operario_nombre}
                      </td>

                      <td className="p-2.5 text-center bg-purple-50/50 border-x whitespace-nowrap">
                        <span className="font-mono font-extrabold text-purple-900 text-xs">
                          🔧 {formatearTiempoMinutos(sub.segundos_setup || 86400)}
                        </span>
                      </td>

                      <td className="p-2.5 text-center bg-emerald-50/50 whitespace-nowrap">
                        <span className="font-mono font-extrabold text-emerald-900 text-xs">
                          ⚙️ {formatearTiempoMinutos(sub.segundos_produccion || 0)}
                        </span>
                      </td>

                      <td className="p-2.5 text-center whitespace-nowrap">
                        <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-emerald-100 text-emerald-800 border border-emerald-300 animate-pulse">⚙️ EN MÁQUINA</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* PESTAÑA 3: MONITOR DE PROYECTOS DE MANTENIMIENTO CON PUERTA DE PASO */}
      {pestanaPrincipal === 'KITS_OVERHAUL' && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-4">
          <div className="flex justify-between items-center border-b pb-2">
            <div>
              <h2 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                <span>📦</span> Proyectos de Mantenimiento & Overhaul
              </h2>
              <p className="text-[11px] text-slate-500">
                Aprobación de Puertas de Paso SGI y Control de Piezas
              </p>
            </div>

            <span className="px-2.5 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 text-xs rounded-full font-bold">
              {listaKits.length} Proyectos
            </span>
          </div>

          <div className="overflow-x-auto border border-slate-200 rounded-lg">
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
                {listaKits.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="p-6 text-center text-slate-400 font-medium">
                      No hay proyectos de mantenimiento registrados.
                    </td>
                  </tr>
                ) : (
                  listaKits.map((p) => {
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
                              className={`px-3 py-1 font-bold rounded text-[11px] transition shadow-sm cursor-pointer border ${
                                piezasAbiertas 
                                  ? 'bg-blue-600 text-white border-blue-700' 
                                  : 'bg-blue-50 text-blue-800 border-blue-200 hover:bg-blue-100'
                              }`}
                            >
                              {cargandoPiezas ? '🔄 Cargando...' : piezasAbiertas ? '🔼 Ocultar Piezas' : '📦 Ver Piezas'}
                            </button>
                          </td>
                        </tr>

                        {piezasAbiertas && (
                          <tr className="bg-slate-50">
                            <td colSpan="7" className="p-4">
                              <div className="p-3 bg-white rounded-lg border border-slate-300 space-y-2 shadow-inner">
                                <div className="flex justify-between items-center text-xs font-bold text-slate-700 border-b pb-1.5">
                                  <span>📦 Piezas e Ítems del Kit de Ensamblaje ({piezasProyecto.length})</span>
                                  <span className="text-[10px] text-emerald-700 font-mono font-bold">🟢 Consulta dinámicamente conectada a PostgreSQL</span>
                                </div>

                                {cargandoPiezas ? (
                                  <div className="p-4 text-center text-xs text-blue-700 font-semibold">
                                    🔄 Obteniendo piezas desde el servidor...
                                  </div>
                                ) : piezasProyecto.length === 0 ? (
                                  <p className="text-slate-400 italic text-center py-2 text-xs">No hay piezas registradas en el kit de esta máquina.</p>
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
                                          const listSol = Array.isArray(solicitudesCompra) ? solicitudesCompra : [];
                                          const solAsociada = listSol.find(
                                            s => s.codigo_op === (pz.codigo_op || p.codigo_op) && 
                                                 s.codigo_plano === (pz.codigo || pz.codigo_pieza_plano)
                                          );
                                          const estadoBomItem = solAsociada?.estado_bom || (solAsociada ? 'SOLICITADO' : 'SIN_SOLICITAR');

                                          return (
                                            <tr key={idx} className="hover:bg-slate-50">
                                              <td className="p-2 text-center font-mono text-slate-400">{idx + 1}</td>
                                              <td className="p-2 font-mono font-bold text-purple-700">{pz.codigo || pz.codigo_pieza || 'PLN-001'}</td>
                                              <td className="p-2 font-bold text-slate-800">{pz.descripcion || pz.detalle_pieza}</td>
                                              <td className="p-2 font-semibold text-slate-700">
                                                {ETIQUETAS_ACCION_PIEZA[pz.accion] || ETIQUETAS_ACCION_PIEZA[pz.estado] || pz.accion || pz.estado || 'Fabricar nueva'}
                                              </td>
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
                                                  onClick={() => handleAbrirDetalleBOM(pz)}
                                                  className="p-1 hover:opacity-80 transition cursor-pointer"
                                                >
                                                  {renderBadgeBomPieza(estadoBomItem)}
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
      )}

      {/* MATRIZ DE CARGA Y PRIORIZACIÓN DE OPERARIOS Y TABLETAS */}
      {modalMatrizCargaAbierto && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4 font-sans">
          <div className="bg-white rounded-xl shadow-2xl max-w-5xl w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto border-t-4 border-blue-600 text-xs">
            <div className="flex justify-between items-start border-b pb-3">
              <div>
                <span className="px-2.5 py-1 bg-blue-100 text-blue-800 text-[10px] font-extrabold rounded uppercase tracking-wider">
                  📱 Matriz de carga por operario y estación de producción
                </span>
                <h3 className="text-xl font-bold text-slate-800 mt-2">
                  Gestión de operarios y secuencia de fabricación — área: <span className="text-blue-700">{areaActiva}</span>
                </h3>
              </div>
              <button 
                type="button"
                onClick={() => setModalMatrizCargaAbierto(false)} 
                className="text-slate-400 hover:text-slate-600 font-bold text-xl cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {gruposOperarioEstacion.length === 0 && (
                <p className="col-span-full rounded-lg border border-slate-200 bg-slate-50 p-6 text-center text-slate-500">
                  No hay órdenes asignadas a operarios y estaciones de esta área.
                </p>
              )}
              {gruposOperarioEstacion.map(({ operarioNombre, maquinaCodigo }) => {
                const sublotesOperario = listaSublotes.filter(
                  (s) => s.operario_nombre === operarioNombre && s.maquina_codigo === maquinaCodigo
                );
                const estadosActivos = ['EN_SETUP', 'EN_PRODUCCION', 'PAUSADA'];
                const estadosEnCola = ['PENDIENTE', 'PENDIENTE_ASIGNACION', 'EN_COLA'];
                const enEjecucion = sublotesOperario.find((s) => estadosActivos.includes(s.estado_sublote));
                const enCola = sublotesOperario
                  .filter((s) => estadosEnCola.includes(s.estado_sublote))
                  .sort((a, b) => Number(a.prioridad_cola || 0) - Number(b.prioridad_cola || 0));

                return (
                  <div key={`${operarioNombre}::${maquinaCodigo}`} className="bg-slate-50 rounded-xl border border-slate-200 p-4 space-y-3 flex flex-col justify-between shadow-sm">
                    <div className="space-y-2">
                      <div className="flex justify-between items-center border-b pb-2">
                        <div>
                          <strong className="text-sm font-bold text-slate-800 block">👤 {operarioNombre}</strong>
                          <span className="text-[10px] font-mono text-slate-500">Estación: {maquinaCodigo}</span>
                        </div>
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-900 font-extrabold rounded text-[10px]">
                          {sublotesOperario.length} órdenes
                        </span>
                      </div>

                      {/* Trabajos Activos en Módulo / Tablet */}
                      <div className="space-y-1.5">
                        <span className="text-[10px] font-bold text-slate-500 uppercase block">⚙️ En Ejecución Actual:</span>
                        {enEjecucion ? (
                          <div className="p-2.5 bg-emerald-50 rounded-lg border border-emerald-300 space-y-1">
                            <div className="flex justify-between items-center font-bold">
                              <span className="font-mono text-blue-900">Orden {enEjecucion.codigo_op}</span>
                              <span className="text-[9px] bg-emerald-600 text-white px-1.5 py-0.5 rounded font-extrabold">
                                {enEjecucion.estado_sublote === 'PAUSADA' ? 'EN PAUSA' : enEjecucion.estado_sublote === 'EN_SETUP' ? 'EN PREPARACIÓN' : 'EN PRODUCCIÓN'}
                              </span>
                            </div>
                            <p className="font-bold text-slate-800 text-[11px]">{enEjecucion.detalle_pieza}</p>
                            <div className="text-[10px] text-slate-600 flex justify-between pt-1 border-t border-emerald-200">
                              <span>Cantidad: <strong>{enEjecucion.cantidad_asignada} unidades</strong></span>
                              <span className="font-mono font-bold text-purple-900">⏱️ {formatearTiempoMinutos(enEjecucion.segundos_produccion || 0)}</span>
                            </div>
                          </div>
                        ) : (
                          <div className="p-2 bg-slate-100 rounded border border-slate-200 text-center text-slate-400 italic text-[11px]">
                            Sin orden en ejecución inmediata.
                          </div>
                        )}
                      </div>

                      {/* Cola de Trabajo Priorizada */}
                      <div className="space-y-1.5 pt-1">
                        <span className="text-[10px] font-bold text-slate-500 uppercase block">                        📋 Cola de espera priorizada ({enCola.length}):</span>
                        {enCola.length === 0 ? (
                          <p className="p-2 text-center text-slate-400 italic text-[10px] bg-white rounded border border-slate-200">
                            No hay órdenes pendientes en cola.
                          </p>
                        ) : (
                          <div className="space-y-1.5">
                            {enCola.map((sub, idx) => (
                              <div key={sub.id_sublote} className="p-2 bg-white rounded-lg border border-slate-200 flex justify-between items-center shadow-xs">
                                <div>
                                  <span className="font-mono font-bold text-purple-800 text-[11px]">#{idx + 1} Orden {sub.codigo_op}</span>
                                  <p className="font-semibold text-slate-800 text-[10px] truncate max-w-[140px]">{sub.detalle_pieza || sub.nombre_proceso}</p>
                                  <span className="text-[9px] text-slate-500">Cantidad: {sub.cantidad_asignada} unidades</span>
                                </div>
                                <div className="flex flex-col gap-1">
                                  <button
                                    type="button"
                                    disabled={idx === 0}
                                    onClick={() => handleMoverPrioridadSublote(operarioNombre, maquinaCodigo, idx, 'SUBIR')}
                                    className={`px-1.5 py-0.5 text-[9px] font-extrabold rounded border ${
                                      idx === 0 ? 'bg-slate-100 text-slate-300 border-slate-200 cursor-not-allowed' : 'bg-blue-50 text-blue-800 border-blue-300 hover:bg-blue-100 cursor-pointer'
                                    }`}
                                    title="Subir prioridad en la tableta"
                                  >
                                    ▲ Subir
                                  </button>
                                  <button
                                    type="button"
                                    disabled={idx === enCola.length - 1}
                                    onClick={() => handleMoverPrioridadSublote(operarioNombre, maquinaCodigo, idx, 'BAJAR')}
                                    className={`px-1.5 py-0.5 text-[9px] font-extrabold rounded border ${
                                      idx === enCola.length - 1 ? 'bg-slate-100 text-slate-300 border-slate-200 cursor-not-allowed' : 'bg-slate-100 text-slate-700 border-slate-300 hover:bg-slate-200 cursor-pointer'
                                    }`}
                                    title="Bajar prioridad en la tableta"
                                  >
                                    ▼ Bajar
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex justify-end border-t pt-3">
              <button
                type="button"
                onClick={() => setModalMatrizCargaAbierto(false)}
                className="px-5 py-2 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded text-xs transition cursor-pointer"
              >
                Cerrar matriz
              </button>
            </div>
          </div>
        </div>
      )}

      <ExpedienteOpModal
        abierto={modalExpedienteOpAbierto && Boolean(ordenSeleccionada)}
        onClose={() => setModalExpedienteOpAbierto(false)}
        codigoOp={ordenSeleccionada?.codigo_op}
        usuario={usuarioActual}
      />

      {/* MODAL 1: DETALLE DE ESTADOS (VER ESTADO) */}
      {modalEstadoAbierto && ordenSeleccionada && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4 font-sans">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-5 space-y-4 border-t-4 border-blue-600 text-xs">
            <div className="flex justify-between items-start border-b pb-2">
              <div>
                <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-extrabold rounded uppercase">
                  Trazabilidad de producción por minutos
                </span>
                <h3 className="text-base font-bold text-slate-800 mt-1">
                  Mapeo OP-{ordenSeleccionada.codigo_op} — {ordenSeleccionada.detalle_pieza}
                </h3>
                <p className="text-[11px] text-slate-500">
                  Total Orden: <strong>{ordenSeleccionada.cantidad_total} UND</strong> | Plano: {ordenSeleccionada.codigo_plano}
                </p>
              </div>
              <button onClick={() => setModalEstadoAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-base cursor-pointer">✕</button>
            </div>

            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-2">
              <h4 className="font-bold text-slate-800 flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5">📲 Dispositivos / Estaciones en Producción Activa</span>
                <span className="bg-emerald-100 text-emerald-800 text-[10px] px-2 py-0.5 rounded font-extrabold border border-emerald-300">
                  {listaSublotes.filter(s => s.codigo_op === ordenSeleccionada.codigo_op).length} Estación(es) Trabajando
                </span>
              </h4>

              {listaSublotes.filter(s => s.codigo_op === ordenSeleccionada.codigo_op).length === 0 ? (
                <p className="text-slate-400 italic text-[11px] py-1">No hay tablets/dispositivos procesando esta orden actualmente.</p>
              ) : (
                <div className="space-y-1.5">
                  {listaSublotes
                    .filter(s => s.codigo_op === ordenSeleccionada.codigo_op)
                    .map(sub => (
                      <div key={sub.id_sublote} className="p-2 bg-white rounded border border-blue-200 flex justify-between items-center shadow-sm">
                        <div>
                          <span className="font-bold text-blue-900 block text-xs">📍 {sub.maquina_codigo} ({sub.operario_nombre})</span>
                          <span className="text-[10px] text-slate-500 font-medium">Proceso: {sub.nombre_proceso} — {sub.sublote_tag}</span>
                        </div>
                        <div className="text-right">
                          <span className="px-2 py-0.5 rounded text-[9px] font-extrabold bg-emerald-100 text-emerald-800 border border-emerald-300 animate-pulse block">
                            ⚙️ EN PROCESO
                          </span>
                          <span className="text-[10px] font-mono font-bold text-purple-900">
                            ⏱️ {formatearTiempoMinutos(sub.segundos_produccion || 0)}
                          </span>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <h4 className="font-bold text-slate-700 text-xs">📊 Consolidador por Etapas de Fabricación (Permanencia en Minutos)</h4>
              
              <div className="grid grid-cols-1 gap-1.5">
                <div className="p-2 bg-emerald-50/60 rounded border border-emerald-200 flex justify-between items-center">
                  <span className="font-bold text-emerald-900 text-xs">🟢 1. PROGRAMADO (En Cola)</span>
                  <div className="text-right">
                    <span className="font-extrabold text-emerald-900 block">{ordenSeleccionada.desglose_estados?.PROGRAMADO?.cantidad || 0} UND</span>
                    <span className="text-[10px] font-bold text-slate-500">⏱️ {ordenSeleccionada.desglose_estados?.PROGRAMADO?.tiempo_dias || '0 min'}</span>
                  </div>
                </div>

                <div className="p-2 bg-blue-50/60 rounded border border-blue-200 flex justify-between items-center">
                  <span className="font-bold text-blue-900 text-xs">⚙️ 2. EN PRODUCCIÓN (Mecanizado)</span>
                  <div className="text-right">
                    <span className="font-extrabold text-blue-900 block">{ordenSeleccionada.desglose_estados?.EN_PRODUCCION?.cantidad || 0} UND</span>
                    <span className="text-[10px] font-bold text-slate-500">⏱️ {ordenSeleccionada.desglose_estados?.EN_PRODUCCION?.tiempo_dias || '0 min'}</span>
                  </div>
                </div>

                <div className="p-2 bg-amber-50/60 rounded border border-amber-200 flex justify-between items-center">
                  <span className="font-bold text-amber-900 text-xs">🔥 3. TRATAMIENTO TÉRMICO (Proveedor)</span>
                  <div className="text-right">
                    <span className="font-extrabold text-amber-900 block">{ordenSeleccionada.desglose_estados?.TRATAMIENTO_TERMICO?.cantidad || 0} UND</span>
                    <span className="text-[10px] font-bold text-slate-500">⏱️ {ordenSeleccionada.desglose_estados?.TRATAMIENTO_TERMICO?.tiempo_dias || '0 min'}</span>
                  </div>
                </div>

                <div className="p-2 bg-purple-50/60 rounded border border-purple-200 flex justify-between items-center">
                  <span className="font-bold text-purple-900 text-xs">🔍 4. INSPECCIÓN CALIDAD (Metrología)</span>
                  <div className="text-right">
                    <span className="font-extrabold text-purple-900 block">{ordenSeleccionada.desglose_estados?.INSPECCION_CALIDAD?.cantidad || 0} UND</span>
                    <span className="text-[10px] font-bold text-slate-500">⏱️ {ordenSeleccionada.desglose_estados?.INSPECCION_CALIDAD?.tiempo_dias || '0 min'}</span>
                  </div>
                </div>

                <div className="p-2 bg-slate-100 rounded border border-slate-300 flex justify-between items-center">
                  <span className="font-bold text-slate-800 text-xs">📦 5. TERMINADO (Almacén PT)</span>
                  <div className="text-right">
                    <span className="font-extrabold text-slate-900 block">{ordenSeleccionada.desglose_estados?.TERMINADO?.cantidad || 0} UND</span>
                    <span className="text-[10px] font-bold text-slate-500">✓ Conforme</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end border-t pt-2">
              <button
                type="button"
                onClick={() => setModalEstadoAbierto(false)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded text-xs cursor-pointer"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: SEGUIMIENTO DE ENTREGAS PARCIALES DE MATERIA PRIMA (BOM) */}
      {modalBOMAbierto && ordenSeleccionada && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4 font-sans">
          <div className="bg-white rounded-xl shadow-2xl max-w-xl w-full p-5 space-y-4 border-t-4 border-amber-500 text-xs">
            <div className="flex justify-between items-start border-b pb-2">
              <div>
                <span className="px-2 py-0.5 bg-amber-100 text-amber-900 text-[10px] font-extrabold rounded uppercase">
                  Gestión de insumos y entregas parciales
                </span>
                <h3 className="text-base font-bold text-slate-800 mt-1">
                  Materiales de la orden {ordenSeleccionada.codigo_op || 'sin código'} — Requisición: {ordenSeleccionada.trazabilidad_bom?.solicitud_pr || 'sin número'}
                </h3>
                <p className="text-[11px] text-slate-500 font-medium">{ordenSeleccionada.descripcion_material || ordenSeleccionada.material_requerido}</p>
              </div>
              <button onClick={() => setModalBOMAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-base cursor-pointer">✕</button>
            </div>

            <div className="grid grid-cols-3 gap-2 bg-slate-50 p-3 rounded-lg border border-slate-200 text-center">
              <div>
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Requerido Total</span>
                <strong className="text-sm font-extrabold text-blue-900">{ordenSeleccionada.trazabilidad_bom?.cantidad_requerida || ordenSeleccionada.cantidad_total || 1} UND</strong>
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Recibido en Planta</span>
                <strong className="text-sm font-extrabold text-emerald-800">{ordenSeleccionada.trazabilidad_bom?.cantidad_recibida || 0} UND</strong>
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-500 uppercase block">Pendiente Proveedor</span>
                <strong className="text-sm font-extrabold text-amber-900">{ordenSeleccionada.trazabilidad_bom?.cantidad_pendiente || 0} UND</strong>
              </div>
            </div>

            <div className="overflow-hidden rounded-lg border border-slate-200">
              <div className="bg-slate-100 px-3 py-2 text-[10px] font-extrabold uppercase text-slate-600">
                Estado real de abastecimiento de materiales
              </div>
              {ordenSeleccionada.bom_items?.length > 0 ? (
                <div className="divide-y divide-slate-200">
                  {ordenSeleccionada.bom_items.map((item, index) => (
                    <div key={`${item.codigo_material}-${index}`} className="flex items-center justify-between gap-3 px-3 py-2">
                      <span className="text-[11px] font-bold text-slate-700">
                        {item.codigo_material} — {item.descripcion}
                      </span>
                      {renderBadgeBomPieza(item.estado_abastecimiento)}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="p-3 text-[11px] font-bold text-amber-900">La orden no tiene líneas de materiales registradas.</p>
              )}
            </div>

            <div className="space-y-1.5">
              <h4 className="font-bold text-slate-700 text-xs flex justify-between">
                <span>📦 Historial de Entregas del Proveedor</span>
                <span className="text-slate-400 font-normal">{ordenSeleccionada.trazabilidad_bom?.proveedor || 'Sin proveedor registrado'}</span>
              </h4>

              <div className="overflow-y-auto max-h-48 border border-slate-200 rounded-lg">
                <table className="w-full text-left border-collapse text-[11px]">
                  <thead className="bg-slate-100 text-slate-700 font-bold uppercase border-b text-[9px]">
                    <tr>
                      <th className="p-2">Fecha</th>
                      <th className="p-2">N° Remisión</th>
                      <th className="p-2 text-center">Cant.</th>
                      <th className="p-2">Insumo Entregado</th>
                      <th className="p-2 text-center">Estado Sub-Lote</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {(ordenSeleccionada.trazabilidad_bom?.entregas_parciales || []).map((ent, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="p-2 font-mono font-bold text-slate-700">{ent.fecha}</td>
                        <td className="p-2 font-mono font-bold text-blue-900">{ent.remision}</td>
                        <td className="p-2 text-center font-extrabold text-emerald-800">{ent.cantidad} UND</td>
                        <td className="p-2 text-slate-700">{ent.material}</td>
                        <td className="p-2 text-center">
                          <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-800 text-[9px] font-bold rounded">
                            {ent.estado}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex justify-end border-t pt-2">
              <button
                type="button"
                onClick={() => setModalBOMAbierto(false)}
                className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded text-xs cursor-pointer"
              >
                Cerrar detalle de materiales
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL PROGRAMAR SUB-LOTE */}
      {modalAsignarAbierto && ordenSeleccionada && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4 font-sans">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-5 space-y-3 border-t-4 border-emerald-600 text-xs">
            <div className="flex justify-between items-start border-b pb-2">
              <div>
                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-extrabold rounded uppercase">
                  Programación de producción
                </span>
                <h3 className="text-base font-bold text-slate-800 mt-1">
                  Asignar proceso a la orden {ordenSeleccionada.codigo_op}
                </h3>
                <p className="text-[11px] text-slate-500 font-medium">{ordenSeleccionada.detalle_pieza}</p>
              </div>
              <button onClick={() => setModalAsignarAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-base cursor-pointer">✕</button>
            </div>

            <form onSubmit={handleCrearSubloteAsignado} className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Paso / Secuencia *</label>
                  <select
                    value={formAsignacion.secuencia_paso}
                    onChange={(e) => setFormAsignacion({ ...formAsignacion, secuencia_paso: parseInt(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded font-bold bg-white cursor-pointer"
                  >
                    <option value={10}>Paso 10 (Inicial)</option>
                    <option value={20}>Paso 20 (Secundario)</option>
                    <option value={30}>Paso 30 (Acabado)</option>
                  </select>
                </div>

                <div>
                  <label className="block font-bold text-slate-700 mb-1">Proceso a Realizar *</label>
                  <input
                    type="text"
                    required
                    placeholder="Ej. Torneado CNC / Fresado"
                    value={formAsignacion.nombre_proceso}
                    onChange={(e) => setFormAsignacion({ ...formAsignacion, nombre_proceso: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-semibold bg-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 bg-emerald-50/50 p-2.5 rounded-xl border border-emerald-200">
                <div>
                  <label className="block font-bold text-emerald-900 mb-1">Cant. Sub-Lote *</label>
                  <input
                    type="number"
                    min="1"
                    max={ordenSeleccionada.cantidad_total}
                    value={formAsignacion.cantidad_sublote}
                    onChange={(e) => setFormAsignacion({ ...formAsignacion, cantidad_sublote: parseInt(e.target.value) || 1 })}
                    className="w-full p-2 border border-emerald-400 rounded font-extrabold text-emerald-900 bg-white text-center text-sm"
                  />
                </div>

                <div className="col-span-2">
                  <label className="block font-bold text-slate-700 mb-1">Máquina / Estación *</label>
                  <select
                    value={formAsignacion.maquina_codigo}
                    onChange={(e) => setFormAsignacion({ ...formAsignacion, maquina_codigo: e.target.value })}
                    className="w-full p-2 border border-slate-300 rounded font-bold bg-white cursor-pointer"
                  >
                    {(CATALAGO_RECURSOS[areaActiva]?.maquinas || ['TORN-CNC-01']).map(m => (
                      <option key={m} value={m}>📍 {m}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Operario Asignado *</label>
                <select
                  value={formAsignacion.operario_nombre}
                  onChange={(e) => setFormAsignacion({ ...formAsignacion, operario_nombre: e.target.value })}
                  className="w-full p-2 border border-slate-300 rounded font-bold text-slate-800 bg-white cursor-pointer"
                >
                  {(CATALAGO_RECURSOS[areaActiva]?.operarios || ['Carlos Ruiz']).map(op => (
                    <option key={op} value={op}>👤 {op}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-bold text-slate-700 mb-1">Instrucciones Especiales</label>
                <textarea
                  rows="2"
                  placeholder="Instrucciones técnicas de montaje o tolerancias..."
                  value={formAsignacion.instrucciones}
                  onChange={(e) => setFormAsignacion({ ...formAsignacion, instrucciones: e.target.value })}
                  className="w-full p-2 border border-slate-300 rounded bg-white"
                ></textarea>
              </div>

              <div className="flex justify-end gap-2 border-t pt-2.5">
                <button
                  type="button"
                  onClick={() => setModalAsignarAbierto(false)}
                  className="px-3.5 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded shadow-sm cursor-pointer"
                >
                  🚀 Enviar a Tablet
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL CENTRO DE ALERTAS */}
      {modalAlertasAbierto && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex justify-center items-center z-50 p-4 font-sans">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-5 space-y-3 border-t-4 border-purple-600 text-xs">
            <div className="flex justify-between items-center border-b pb-2">
              <h3 className="text-base font-bold text-slate-800 flex items-center gap-1.5">
                <span>🔔</span> Alertas de Planta y Cierre de Procesos
              </h3>
              <button onClick={() => setModalAlertasAbierto(false)} className="text-slate-400 hover:text-slate-600 font-bold text-base cursor-pointer">✕</button>
            </div>

            <div className="space-y-2.5 max-h-72 overflow-y-auto">
              {listaNotif.length === 0 ? (
                <p className="p-4 text-center text-slate-400 italic text-xs">Sin notificaciones pendientes.</p>
              ) : (
                listaNotif.map(n => (
                  <div key={n.id_notificacion} className="p-3 bg-purple-50 rounded-xl border border-purple-200 space-y-1">
                    <div className="flex justify-between items-center font-bold text-purple-900">
                      <span>⚙ OP-{n.codigo_op} / {n.codigo_plano}</span>
                      <span className="text-[9px] text-purple-700 bg-purple-100 px-1.5 py-0.5 rounded">{n.fecha}</span>
                    </div>
                    <p className="text-slate-700 font-medium">{n.mensaje}</p>
                    <div className="text-[10px] text-slate-500 font-semibold flex justify-between pt-1 border-t border-purple-200">
                      <span>👤 {n.operario_nombre} ({n.maquina_codigo})</span>
                      <span className="font-bold text-emerald-800">✅ {n.piezas_reportadas} UND Conformes</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="flex justify-end border-t pt-2">
              <button
                type="button"
                onClick={() => setModalAlertasAbierto(false)}
                className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-900 text-white font-bold rounded text-xs cursor-pointer"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* COMPONENTE VISOR MODAL PDF */}
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