---
id: PROC-INV-002
titulo: Desacoplamiento Arquitectónico: Inventario General vs. Almacén Operativo
estado: APROBADO
fecha: 2026-10-22
iso_9001_2026: Cláusula 8.4 (Control de Procesos Externos), 8.5.2 (Trazabilidad)
modulo_equivalente_sap: SAP MM-IM (Inventory Management) vs. SAP MM-WM (Warehouse Management)
---

# [[PM-04_Separacion_Inventario_Almacen|Desacoplamiento: Inventario General vs. Almacén Operativo]]

## 1. Desacoplamiento de Responsabilidades Operativas

Para optimizar el rendimiento del sistema y evitar cargas innecesarias de datos, la plataforma separa técnicamente la administración del catálogo maestro y la valoración contable de las transacciones físicas en bodega:

┌─────────────────────────────────────────────────────────────────────────────────────────┐ │ MÓDULO 1: INVENTARIO GENERAL (SISTEMA CENTRAL) │ │ `InventarioGeneralView.jsx` / `/api/v1/inventario` │ │ │ │ - Catálogo Maestro de SKUs (Materia Prima Directa, Herramental CNC, Consumibles, EPPs) │ │ - Kárdex Valorizado Auditado (Costo Promedio Ponderado / FIFO) │ │ - Control de Lotes / Coladas 3.1 & Cuarentena (Quality Gates ISO) │ │ - Motor MRP de Requerimientos Netos │ └────────────────────────────────────────────┬────────────────────────────────────────────┘ │ Consumo Modular mediante Servicios API │ ┌────────────────────────────────────────────▼────────────────────────────────────────────┐ │ MÓDULO 2: ALMACÉN OPERATIVO (PISO DE PLANTA) │ │ `AlmacenInventarioView.jsx` / `/api/v1/almacen` │ │ │ │ 1. Sub-vista Recepción Compras ──► Consume Requisiciones (PR) en estado 'EN_COMPRA' │ │ 2. Sub-vista Salidas / Despachos ──► Consume ítems 'LIBERADOS' e imputa a OPs/Planta │ │ 3. Sub-vista Remanentes / Retales ──► Integradó con `RemanentesSobrantesView.jsx` │ └─────────────────────────────────────────────────────────────────────────────────────────┘

--- ## 2. Regla Directiva de Interfaz y Gobernanza (NO SAP LABELS) > **REGLA DE ETIQUETADO E INTERFAZ USUARIO:** > Queda estrictamente prohibido colocar marcas, nombres o etiquetas explícitas de 'SAP' (ej. 'SAP MM', 'SAP QM', 'Tipo SAP', 'SAP Material Master') en las interfaces de usuario (React), botones, pestañas, modales o mensajes visuales del ERP. > > Las metodologías de SAP (como Kárdex, Lotes, MRP, Quality Gates o Centros de Costo) deben emplearse ÚNICAMENTE como modelo conceptual e interno de referencia arquitectónica, pero la interfaz gráfica debe utilizar exclusivamente terminología limpia, ejecutiva y natural en español adaptada al SGI-ERP (*Catálogo Maestro*, *Maestro de Insumos*, *Kárdex Valorizado*, *Lotes y Calidad*, *Requerimientos Netos / MRP*, *Centro de Costos*). --- ## 3. Enlaces Relacionados - [[Modelo_ERD_PostgreSQL]] - Esquema de base de datos de kárdex y lotes. - [[RN-OP-004_Bloqueo_Liberacion_OP]] - Quality Gate de liberación de insumos a planta.

---
## Submódulo: Reposición de Producto Terminado para Stock (Mínimos y Máximos)

### 1. Parámetros Maestros por SKU de Producto Terminado
- **Stock Mínimo (Piso de Seguridad):** Nivel crítico que dispara advertencia roja en Almacén.
- **Punto de Reorden (ROP):** Momento sugerido de pedido considerando tiempo de fabricación.
- **Stock Máximo:** Límite superior de custodia física.
- **Lote Estándar (MOQ):** Múltiplos técnicos de producción en planta.

### 2. Tablero de Decisiones para Almacén (No Automatismo a Ciegas)
- El sistema **no emite la OP directamente**, sino que proyecta la necesidad en el **Panel de Logística/Almacén**:
  $$\text{Stock Proyectado} = \text{Stock Físico} + \text{OPs en curso} - \text{Comprometido} - \text{Picking}$$
- Si $\text{Stock Proyectado} \le \text{Punto de Reorden}$, se enciende la alarma amarilla o roja.
- **Intervención Humana Obligatoria:** El responsable de Almacén/Logística analiza el tablero (verificando si las alertas son por compromisos reales de preventa o estacionalidad) y presiona el botón:
  `[ 🏭 Radicar Solicitud de Fabricación para Stock ]`
- Esta acción crea la OP formal (serie $4xxxxxx$ mecanizado o $1xxxxxx$ metalistería) con origen `REPOSICION_STOCK` para que Ingeniería y Planta la programen en el ERP.