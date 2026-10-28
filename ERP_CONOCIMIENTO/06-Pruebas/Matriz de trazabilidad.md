---
tipo: matriz-pruebas
estado: borrador
---
---
tipo: trazabilidad
codigo: TRZ-SIST-001
nombre: Matriz General de Trazabilidad Requisitos - Módulos - SQL - QA
fase: F1-F3
estado: aprobado
version: 1.0
autor: Analista Funcional / Arquitecto de Software
sistema_destino: ERP FastAPI + PostgreSQL
---

# TRZ-SIST-001: Matriz General de Trazabilidad Requisitos - Módulos - SQL - QA

## 1. Propósito
Garantizar la cobertura integral de la solución conectando cada Requisito de Negocio con su Proceso asociado, la tabla en la Base de Datos PostgreSQL, el Endpoint API en FastAPI y el Caso de Prueba (QA).

---

## 2. Matriz de Trazabilidad Cruzada

| ID Requisito | Proceso | Descripción Funcional | Tabla PostgreSQL | Endpoint API (FastAPI) | Caso de Prueba |
| :---: | :---: | :--- | :--- | :--- | :---: |
| **REQ-DIS-001** | `PROC-PROD-001` | Estimación de tiempo por Líder y medición cronometrada al pasar a `EN_DISENO`. | `tiempos_diseno`, `ordenes_produccion` | `POST /api/v1/diseno/asignar`<br>`PUT /api/v1/diseno/iniciar` | `TC-DIS-001` |
| **REQ-PROD-001** | `PROC-PROD-001` | Visualización de OP y cronómetro de Setup/Mecanizado en Puesto CNC. | `registro_tiempos_produccion` | `WS /api/v1/ws/puesto-trabajo/{estacion_id}` | `TC-01` |
| **REQ-PROD-002** | `PROC-PROD-001` | Visor temporal de planos PDF con tokens de acceso expirable (TTL). | `planos_op` | `GET /api/v1/planos/token/{id}` | `TC-02` |
| **REQ-PROD-003** | `PROC-PROD-001` | Excepción por desviación de tiempo en Setup (>50%) con modal de justificación. | `registro_tiempos_produccion` | `POST /api/v1/produccion/mecanizado/iniciar` | `TC-03` |
| **REQ-CAL-001** | `PRO-CAL-001` | Control metrológico con micrómetros, calibradores pie de rey y patrones. | `inspecciones_calidad` | `POST /api/v1/calidad/inspeccion` | `TC-04` |
| **REQ-CAL-002** | `PRO-CAL-001` | Registro fotográfico obligatorio y envío de email para Tratamiento Térmico. | `informes_tratamiento_termico` | `POST /api/v1/calidad/tratamiento-termico` | `TC-04` |
| **REQ-CAL-003** | `PRO-CAL-001` | Generación de No Conformidades (NC) y solicitud automática de nuevo material. | `no_conformidades` | `POST /api/v1/calidad/no-conformidad` | `TC-05` |

---

## 3. Preguntas por Validar

### Responsables y suplencias:
- [PENDIENTE: Definir si se requerirá un módulo de auditoría de logs que registre cuando una orden cambie de estado manualmente por un Administrador.]

### Aprobaciones:
- [PENDIENTE: Confirmar si las pruebas unitarias de trazabilidad se ejecutarán de forma automatizada en el pipeline de CI/CD.]

---
# Matriz de trazabilidad requisito-prueba

| ID requisito | Proceso/módulo | Criterio de aceptación | Prueba | Evidencia/resultado | Estado |
|---|---|---|---|---|---|
| REQ-XXX | Por definir | Por definir | Por definir | Pendiente | Borrador |


---
## Enlaces Transversales
- [[Inicio]]
- [[Mapeo_Modulos_SGI_vs_SAP]]
- [[Controles de calidad]]



## 1. Expediente Maestro Unificado de Órdenes de Producción (`ExpedienteOpModal.jsx`) Todas las áreas de la compañía (Ventas, Diseño, Almacén, Producción y Calidad) consumen la misma estructura gráfica de alta densidad (`py-1.5`, `text-xs`), garantizando que la información técnica sea homogénea en toda la organización[cite: 5, 8].

┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │ EXPEDIENTE MAESTRO DE PEDIDOS & ÓRDENES DE PRODUCCIÓN (OP) │ │ Vista Multimodal Unificada (Misma maquetación de alta densidad py-1.5, text-xs para 400+ OPs) │ └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │ ┌──────────────────────┬──────────────────────────────┼──────────────────────────────┬──────────────────────┐ ▼ ▼ ▼ ▼ ▼ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ │ VENTAS │ │ DISEÑO │ │ ALMACÉN │ │ PRODUCCIÓN │ │ CALIDAD │ ├───────────────┤ ├───────────────┤ ├───────────────┤ ├───────────────┤ ├───────────────┤ │ • Consulta │ │ • Abre OPs │ │ • Asigna BOM │ │ • Revisa │ │ • Inspección │ │ Avance % │ │ • Carga Planos│ │ e Insumos │ │ Piezas/Kit │ │ Metrológica │ │ • Pedidos │ │ PDF │ │ • Despacha a │ │ • Captura │ │ • Certif 3.1 │ │ Abiertos / │ │ • Define BOM │ │ Planta │ │ Tiempos MES │ │ • Tratamiento │ │ Cerrados │ │ • Gate RN-OP4 │ │ • Imputa OP │ │ • Sub-lotes │ │ Térmico │ └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘

```

---

## 2. Matriz de Permisos y Edición por Rol SGI

| Área / Rol SGI | Alcance de Visibilidad | Permisos de Lectura | Acciones y Edición Autorizadas | Quality Gates / Reglas Bloqueantes |
| :--- | :--- | :--- | :--- | :--- |
| **Ventas & Proyectos** | Pedidos Comerciales (Abiertos y Cerrados). | Expediente global, OPs vinculadas, avance % y fechas prometidas[cite: 5, 11]. | Crear/Abrir Pedidos (`proyectos`), confirmar cotización, autorizar cierres[cite: 5, 10]. | Inmutabilidad comercial tras estado `CONFIRMADO`[cite: 5]. |
| **Diseño e Ingeniería** | OPs asignadas y Pedidos en estructuración. | Despiece de piezas, especificaciones técnicas de aleación, planos PDF[cite: 5, 11, 14]. | **Crear / Abrir OPs**, cargar/congelar plano PDF (`archivo_url`), generar PR de BOM[cite: 5, 10, 14]. | **RN-OP-004:** Bloquea la liberación si falta el PDF o el BOM no está en Almacén[cite: 5, 8, 14]. |
| **Almacén & Compras** | Requisiciones (PR) y OPs activas. | BOM por pieza, lote de colada 3.1, stock disponible y retales reutilizables[cite: 5, 11, 13]. | Asignar material desde Kárdex, recibir mercancía con factura, imputar consumibles[cite: 5, 11, 12, 13]. | No puede modificar planos ni tiempos MES[cite: 5]. |
| **Producción MES** | OPs con estado `LIBERADA` (Quality Gate aprobado)[cite: 5, 11]. | Expediente de OP, desglose de piezas, visor de planos PDF, materiales asignados[cite: 6, 11, 14]. | Asignar Centros de Trabajo/CNC, iniciar cronómetros MES, registrar piezas OK/Scrap[cite: 5, 6, 10]. | Bloqueo automático si la OP no ha superado la regla RN-OP-004[cite: 8, 14]. |
| **Calidad & Metrología** | OPs en estado `TERMINADA` o `INSPECCION_CALIDAD`[cite: 6, 9, 12]. | Tolerancias de plano PDF, histórico de mediciones cota a cota, evidencia fotográfica[cite: 6, 9, 12, 15]. | Aprobación para Despacho, emisión de informe de Tratamiento Térmico, registro RNC[cite: 6, 9]. | Registro fotográfico obligatorio de piezas salientes[cite: 9]. |

---

## 3. Módulos Estratégicos Integrados
1. **Mantenimiento de Planta & Activos (`MantenimientoPlantaView.jsx`):** Hojas de vida de equipos (`equipos_planta`), registro de horas acumuladas de uso desde Tablets MES y Órdenes de Mantenimiento (`ordenes_mantenimiento`).
2. **Capacidad Finita y Carga de Máquinas (`GanttCargaMaquinasView.jsx`):** Nivelación de carga en Centros de Trabajo CNC por tiempo estimado de Setup y Mecanizado.
3. **No Conformidades y CAPA (`CalidadRncCapaView.jsx`):** Gestión de RNCs (`no_conformidades`) y acciones correctivas/preventivas (`acciones_capa`) con análisis de causa raíz.
4. **OEE & Costeo Real por OP (`CostosLiquidacionOpView.jsx`):** Cálculo del costo real acumulado (ADR-004) comparado contra la cotización comercial.
```

### 📌

| Requisito SGI / ISO | Regla ERP | Pantalla / Vista (UI) | Endpoint FastAPI | Tabla PostgreSQL | Estado Evidencia |
| --- | --- | --- | --- | --- | --- |
| **8.2 Preventa / Compromiso** | `RN-LOG-002` | `VentasProyectosView.jsx` | `POST /api/v1/logistica/reservas` | `public.reservas_stock_temporal` | **DOCUMENTADO** |
| **8.5.4 Preservación / Picking** | `RN-LOG-001` | `LogisticaDespachoView.jsx` | `POST /api/v1/logistica/picking` | `public.ordenes_picking` | **DOCUMENTADO** |
| **8.5.3 Custodia de Propiedad del Cliente** | `RN-LOG-003` | `LogisticaCustodiaView.jsx` | `POST /api/v1/logistica/custodia` | `public.equipos_custodia_mantenimiento` | **DOCUMENTADO** |
| **8.5.1 Reposición de Stock** | `RN-LOG-004` | `InventarioGeneralView.jsx` | `POST /api/v1/logistica/reposicion-op` | `public.ordenes_produccion` | **DOCUMENTADO** |