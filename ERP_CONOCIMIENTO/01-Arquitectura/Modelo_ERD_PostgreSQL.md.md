---
id: ARCH-ERD-001
titulo: Modelo de Datos Relacional PostgreSQL (ERD Canonical)
estado: APROBADO
fecha: 2026-10-22
iso_9001_2026: Cláusula 7.5 (Información Documentada), 8.5.2 (Trazabilidad)
---
---
````
---
id: ARCH-ERD-001
titulo: Modelo Entidad-Relación Canónico PostgreSQL (SGI-ERP)
estado: APROBADO
version: 2.0.0
fecha: 2026-10-24
iso_9001_2026: Cláusula 7.5 (Información Documentada), 8.2, 8.4, 8.5.2, 8.5.4, 8.6, 9.1
---

# [[Modelo_ERD_PostgreSQL|Modelo de Datos Relacional PostgreSQL (SGI-ERP)]]

> **Regla de Inmutabilidad:** Este documento es la Única Fuente de Verdad (SSOT) del esquema relacional de PostgreSQL. Toda tabla, clave foránea y restricción aquí descrita gobierna los modelos de SQLAlchemy (`app/db/models.py`, `app/db/models_produccion.py`) y las migraciones de Alembic.

---

## 1. Arquitectura Relacional Inmutable ($N:M$)
El modelo garantiza la estricta separación relacional entre las entidades comerciales agrupadoras (`proyectos`), el desglose de piezas cotizadas (`pedido_detalles`) y las entidades autónomas de ejecución técnica en piso de planta (`planos` / `ordenes_produccion`), utilizando la entidad intermedia de enlace `ot_detalles`.

```text
┌─────────────────────────┐          ┌─────────────────────────┐          ┌─────────────────────────┐
│        proyectos        │ 1      N │     pedido_detalles     │ 1      N │       ot_detalles       │
│  (Cabecera Comercial)   ├─────────►│  (Desglose de Piezas)   ├─────────►│  (Matriz N:M de OPs)    │
└─────────────────────────┘          └─────────────────────────┘          └────────────┬────────────┘
                                                                                       │
                                                                                       │ N
                                                                          ┌────────────▼────────────┐
                                                                          │   planos / ordenes_op   │
                                                                          │  (Ejecución en Planta)  │
                                                                          └─────────────────────────┘
````

## 2. Datos Maestros y Estructura Financiera

### A. Estructura Financiera y Organizativa (`estructura_financiera`)

- **Regla de Integridad:** `codigo` posee restricción `unique=True` y se encuentra indexado para autorizar la clave foránea autorreferencial del campo `cuenta_padre`.
    
    - `id_elemento` (UUID, PK)
        
    - `tipo` (ENUM: `'CUENTA_CONTABLE'`, `'CENTRO_COSTO'`, `'UNIDAD_NEGOCIO'`)
        
    - `codigo` (VARCHAR(50), UNIQUE, INDEX)
        
    - `nombre` (VARCHAR(150), NOT NULL)
        
    - `descripcion` (TEXT, Nullable)
        
    - `cuenta_padre` (VARCHAR(50), FK autorreferencial a `estructura_financiera.codigo`, Nullable)
        
    - `activo` (BOOLEAN, DEFAULT True)
        

### B. Socios de Negocio Unificados (`socios_negocio`)

- Unifica Clientes y Proveedores bajo una misma entidad relacional:
    
    - `id_socio` (UUID, PK)
        
    - `nit_cedula` (VARCHAR(30), UNIQUE, INDEX)
        
    - `razon_social` (VARCHAR(200), NOT NULL)
        
    - `es_cliente` (BOOLEAN, DEFAULT False)
        
    - `es_proveedor` (BOOLEAN, DEFAULT False)
        
    - `direccion` (VARCHAR(255), Nullable)
        
    - `telefono` (VARCHAR(50), Nullable)
        
    - `email` (VARCHAR(100), Nullable)
        
    - `condiciones_pago_dias` (INTEGER, CHECK: `condiciones_pago_dias BETWEEN 0 AND 365`)
        
    - `cuenta_contable_por_cobrar` (VARCHAR(50), Nullable)
        
    - `cuenta_contable_por_pagar` (VARCHAR(50), Nullable)
        
    - `estado_activo` (BOOLEAN, DEFAULT True)
        

### C. Personal, Trabajadores y Seguridad RBAC (`trabajadores_usuarios`, `usuarios`, `roles`)

- **`roles`:** `id_rol` (VARCHAR(30), PK: `'ADMIN'`, `'VENTAS'`, `'DISENO'`, `'ALMACEN'`, `'PRODUCCION'`, `'CALIDAD'`, `'MANTENIMIENTO'`), `nombre_rol` (VARCHAR), `descripcion` (TEXT).
    
- **`usuarios`:** `id_usuario` (UUID, PK), `email` (VARCHAR, UNIQUE), `password_hash` (VARCHAR), `nombre_completo` (VARCHAR), `id_rol` (VARCHAR, FK -> `roles.id_rol`), `activo` (BOOLEAN).
    
- **`trabajadores_usuarios`:** `id_trabajador` (UUID, PK), `cedula` (VARCHAR(30), UNIQUE, INDEX), `nombre_completo` (VARCHAR(150)), `area` (ENUM: `'VENTAS'`, `'DISENO'`, `'ALMACEN'`, `'PRODUCCION'`, `'CALIDAD'`, `'ADMINISTRACION'`), `cargo` (VARCHAR(100)), `tarifa_hora_mano_obra` (NUMERIC(14,4), DEFAULT 0), `id_usuario_sistema` (UUID, UNIQUE, FK -> `usuarios.id_usuario`, Nullable).
    

## 3. Cadena Comercial, Diseño e Ingeniería

### A. Cabecera Comercial (`proyectos`)

- `id_proyecto` (UUID, PK)
    
- `numero_pedido` (VARCHAR(50), UNIQUE, INDEX)
    
- `codigo_proyecto` (VARCHAR(50), INDEX)
    
- `cliente_nombre` (VARCHAR(200), NOT NULL)
    
- `contacto_nombre` / `contacto_telefono` / `contacto_email` (VARCHAR, Nullable)
    
- `ubicacion_cliente` (VARCHAR(255), Nullable)
    
- `detalle_producto` (TEXT, NOT NULL)
    
- `cantidad` (INTEGER, NOT NULL)
    
- `requisitos_cliente` (TEXT, Nullable)
    
- `confirmado` (BOOLEAN, DEFAULT False) $\rightarrow$ _Bloqueo de edición comercial_
    
- `fecha_compromiso` (DATE, Nullable)
    
- `creado_en` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW())
    

### B. Desglose de Pedido Comercial (`pedido_detalles`)

- `detalle_id` (UUID, PK)
    
- `pedido_id` (UUID, FK -> `proyectos.id_proyecto`)
    
- `codigo_producto` (VARCHAR(50), NOT NULL)
    
- `descripcion` (TEXT, NOT NULL)
    
- `tipo` (ENUM: `'pieza'`, `'conjunto'`, `'servicio'`)
    
- `cantidad_solicitada` (NUMERIC(12,2), NOT NULL)
    
- `unidad` (VARCHAR(20), DEFAULT 'UND')
    
- `cantidad_asignada` (NUMERIC(12,2), DEFAULT 0)
    
- `cantidad_pendiente` (NUMERIC(12,2), DEFAULT 0)
    
- `fecha_requerida` (DATE, Nullable)
    
- `prioridad` (VARCHAR(20), DEFAULT 'MEDIA')
    

### C. Órdenes Técnicas y Planos (`planos` / `ordenes_produccion`)

- `id_plano` (UUID, PK)
    
- `id_proyecto` (UUID, FK -> `proyectos.id_proyecto`, Nullable)
    
- `codigo_op` (VARCHAR(50), UNIQUE, INDEX) $\rightarrow$ _Series: 4xxxxxx Mecanizado, 1xxxxxx Metalistería, 3xxxxxx Servicios_
    
- `codigo_plano` (VARCHAR(50), NOT NULL)
    
- `revision` (VARCHAR(10), DEFAULT 'REV-00')
    
- `dibujante_asignado` (VARCHAR(150), Nullable)
    
- `unidad_planta` (ENUM: `'Mecanizados'`, `'Metalistería'`, `'Servicios'`)
    
- `estado_diseno` (ENUM: `'EN_DISENO'`, `'CONGELADA'`, `'LIBERADA'`, `'TERMINADA'`)
    
- `material_requerido` (TEXT, Nullable)
    
- `tiempo_estimado_valor` (NUMERIC(10,2), DEFAULT 0)
    
- `tiempo_estimado_unidad` (VARCHAR(20), DEFAULT 'HORAS')
    
- `fecha_inicio_programada` / `fecha_entrega_produccion` (DATE, Nullable)
    
- `archivo_url` (VARCHAR(255), Nullable) $\rightarrow$ _Requisito obligatorio para RN-OP-004_
    

### D. Enlace Relacional $N:M$ (`ot_detalles`)

- `ot_detalle_id` (UUID, PK)
    
- `detalle_pedido_id` (UUID, FK -> `pedido_detalles.detalle_id`)
    
- `ot_id` (UUID, FK -> `planos.id_plano`)
    
- `cantidad_asignada` (NUMERIC(12,2), NOT NULL)
    

## 4. Almacén, Kárdex, Materiales y Compras (MRP)

### A. Catálogo Maestro de Materiales e Insumos (`catalogo_materiales`)

- `id_material` (UUID, PK)
    
- `codigo_material` (VARCHAR(50), UNIQUE, INDEX)
    
- `descripcion` (VARCHAR(255), NOT NULL)
    
- `categoria` (ENUM: `'MATERIA_PRIMA'`, `'CONSUMIBLE'`, `'HERRAMENTAL'`, `'PRODUCTO_TERMINADO'`, `'EPP'`)
    
- `unidad_medida` (VARCHAR(20), NOT NULL)
    
- `stock_minimo` (NUMERIC(12,2), DEFAULT 0)
    
- `punto_reorden` (NUMERIC(12,2), DEFAULT 0)
    
- `stock_maximo` (NUMERIC(12,2), DEFAULT 0)
    
- `lote_estandar_moq` (NUMERIC(12,2), DEFAULT 1)
    
- `activo` (BOOLEAN, DEFAULT True)
    

### B. Saldos y Kárdex Operativo de Almacén (`stock_almacen`, `movimientos_kardex`)

- **`stock_almacen`:** `id_stock` (UUID, PK), `codigo_material` (VARCHAR(50), FK -> `catalogo_materiales.codigo_material`), `ubicacion` (VARCHAR(50)), `stock_fisico` (NUMERIC(12,2), DEFAULT 0), `stock_comprometido` (NUMERIC(12,2), DEFAULT 0), `stock_disponible` (NUMERIC(12,2), GENERATED ALWAYS AS (`stock_fisico` - `stock_comprometido`) STORED).
    
- **`movimientos_kardex`:** `id_movimiento` (UUID, PK), `codigo_material` (VARCHAR(50)), `tipo_movimiento` (ENUM: `'ENTRADA_COMPRA'`, `'ENTRADA_PRODUCCION'`, `'CONSUMO_OP'`, `'SALIDA_DESPACHO'`, `'AJUSTE_INVENTARIO'`), `cantidad` (NUMERIC(12,2)), `codigo_op` (VARCHAR(50), Nullable), `costo_unitario` (NUMERIC(14,4)), `fecha_movimiento` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW()).
    

### C. Gestión de Lotes y Trazabilidad Metalúrgica (`lotes`, `retales_sobrantes`)

- **`lotes`:** `id_lote` (UUID, PK), `numero_colada` (VARCHAR(100), UNIQUE, INDEX), `codigo_material` (VARCHAR(50)), `certificado_31_url` (VARCHAR(255)), `estado_calidad` (ENUM: `'CUARENTENA'`, `'LIBERADO'`, `'RECHAZADO'`).
    
- **`retales_sobrantes`:** `id_retal` (UUID, PK), `codigo_material` (VARCHAR(50)), `dimensiones_texto` (VARCHAR(100)), `peso_kg` (NUMERIC(10,2)), `origen_op` (VARCHAR(50)), `disponible` (BOOLEAN, DEFAULT True).
    

### D. Requisiciones de Compra (`solicitudes_compra`)

- `id_solicitud` (UUID, PK)
    
- `codigo_pr` (VARCHAR(50), UNIQUE)
    
- `codigo_op` (VARCHAR(50), Nullable, FK -> `planos.codigo_op`)
    
- `codigo_material` (VARCHAR(50), FK -> `catalogo_materiales.codigo_material`)
    
- `cantidad_requerida` (NUMERIC(12,2), NOT NULL)
    
- `justificacion` (TEXT)
    
- `estado` (ENUM: `'PENDIENTE'`, `'APROBADA'`, `'ORDENADA'`, `'RECIBIDA'`)
    
- `fecha_creacion` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW())
    

## 5. Producción en Piso (MES), Máquinas y Tiempos

### A. Operaciones de Hoja de Ruta (`operaciones_ot`)

- `id_operacion` (UUID, PK)
    
- `id_plano` (UUID, FK -> `planos.id_plano`)
    
- `codigo_op` (VARCHAR(50))
    
- `secuencia_paso` (INTEGER, NOT NULL)
    
- `unidad_planta` (VARCHAR(50))
    
- `nombre_proceso` (VARCHAR(150), NOT NULL)
    
- `cantidad_total_orden` (INTEGER, NOT NULL)
    
- `cantidad_acumulada_ok` (INTEGER, DEFAULT 0)
    
- `cantidad_acumulada_scrap` (INTEGER, DEFAULT 0)
    
- `estado_operacion` (VARCHAR(30), DEFAULT 'PENDIENTE')
    

### B. Sublotes y Control de Cronómetros MES (`sublotes_operacion`, `registros_tiempo_operario`)

- **`sublotes_operacion`:** `id_sublote` (UUID, PK), `id_operacion` (UUID, FK -> `operaciones_ot.id_operacion`), `numero_sublote` (INTEGER), `cantidad_piezas` (INTEGER), `operario_nombre` (VARCHAR(150)), `maquina_codigo` (VARCHAR(50)), `estado_sublote` (VARCHAR(30)), `fecha_inicio` (TIMESTAMP), `fecha_fin` (TIMESTAMP, Nullable).
    
- **`registros_tiempo_operario`:** `id_registro` (UUID, PK), `id_sublote` (UUID, FK -> `sublotes_operacion.id_sublote`), `operario_id` (VARCHAR(50)), `operario_nombre` (VARCHAR(150)), `tipo_tiempo` (ENUM: `'SETUP'`, `'PRODUCCION'`, `'PAUSA_TECNICA'`), `segundos_acumulados` (INTEGER, DEFAULT 0), `fecha_inicio` (TIMESTAMP).
    

### C. Máquinas y Mantenimiento de Planta (`maquinas`, `ordenes_mantenimiento`)

- **`maquinas`:** `id_maquina` (UUID, PK), `codigo_maquina` (VARCHAR(50), UNIQUE, INDEX), `nombre_maquina` (VARCHAR(150)), `centro_costo_codigo` (VARCHAR(50), FK -> `estructura_financiera.codigo`), `unidad_planta` (VARCHAR(50)), `horas_uso_acumuladas` (NUMERIC(10,2), DEFAULT 0), `estado` (ENUM: `'OPERATIVA'`, `'EN_MANTENIMIENTO'`, `'FUERA_SERVICIO'`).
    
- **`ordenes_mantenimiento`:** `id_otm` (UUID, PK), `codigo_otm` (VARCHAR(50), UNIQUE), `id_maquina` (UUID, FK -> `maquinas.id_maquina`), `tipo` (ENUM: `'PREVENTIVO'`, `'CORRECTIVO'`), `descripcion_falla` (TEXT), `repuestos_solicitados` (JSONB, Nullable), `estado` (ENUM: `'ABIERTA'`, `'EN_PROCESO'`, `'CERRADA'`).
    

## 6. Logística, Picking, Despacho y Reservas Temporales

### A. Reservas Telefónicas / Preventa (`reservas_stock_temporal`)

- Permite comprometer unidades físicas de stock sin emitir factura, descontándolas de la vista pública de ventas:
    
    - `id_reserva` (UUID, PK)
        
    - `codigo_material` (VARCHAR(50), FK -> `catalogo_materiales.codigo_material`)
        
    - `cantidad_comprometida` (NUMERIC(12,2), NOT NULL)
        
    - `cliente_referencia` (VARCHAR(200), NOT NULL)
        
    - `vendedor_id` (UUID, FK -> `usuarios.id_usuario`)
        
    - `fecha_registro` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW())
        
    - `fecha_vencimiento` (TIMESTAMP WITH TIME ZONE, NOT NULL) $\rightarrow$ _Caducidad (ej. 48h)_
        
    - `alerta_enviada` (BOOLEAN, DEFAULT False)
        
    - `estado` (ENUM: `'ACTIVA'`, `'CONCRETADA'`, `'EXPIRADA'`, `'CANCELADA'`)
        

### B. Órdenes de Picking y Despacho (`ordenes_picking`)

- Controla la extracción física de bodega y la salida definitiva de mercancía:
    
    - `id_picking` (UUID, PK)
        
    - `codigo_picking` (VARCHAR(50), UNIQUE, INDEX)
        
    - `id_proyecto` (UUID, FK -> `proyectos.id_proyecto`)
        
    - `operario_asignado_id` (UUID, FK -> `usuarios.id_usuario`, Nullable)
        
    - `fecha_emision` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW())
        
    - `fecha_despacho` (TIMESTAMP WITH TIME ZONE, Nullable)
        
    - `transportador_nombre` (VARCHAR(150), Nullable)
        
    - `numero_guia_remision` (VARCHAR(50), Nullable)
        
    - `estado` (ENUM: `'PENDIENTE'`, `'EN_PICKING'`, `'EMPACADO'`, `'DESPACHADO'`, `'ENTREGADO'`)
        

### C. Custodia de Equipos para Mantenimiento Externo (`equipos_custodia_mantenimiento`)

- Registro de máquinas de terceros recibidas para servicio técnico (no comercializables):
    
    - `id_custodia` (UUID, PK)
        
    - `numero_serial` (VARCHAR(100), INDEX)
        
    - `marca_modelo` (VARCHAR(150), NOT NULL)
        
    - `cliente_propietario_id` (UUID, FK -> `socios_negocio.id_socio`)
        
    - `accesorios_recibidos` (TEXT, Nullable)
        
    - `registro_fotografico_url` (VARCHAR(255), Nullable)
        
    - `ubicacion_bodega` (VARCHAR(50), DEFAULT 'TALLER_CUSTODIA')
        
    - `fecha_ingreso` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW())
        
    - `fecha_devolucion` (TIMESTAMP WITH TIME ZONE, Nullable)
        
    - `estado` (ENUM: `'RECIBIDO'`, `'EN_DIAGNOSTICO'`, `'EN_REPARACION'`, `'LISTO_ENTREGA'`, `'DEVUELTO'`)
        

## 7. Calidad (ISO 9001:2026), RNC y Auditoría

### A. No Conformidades y Acciones Correctivas (`reportes_no_conformidad`, `acciones_capa`)

- **`reportes_no_conformidad`:** `id_rnc` (UUID, PK), `codigo_rnc` (VARCHAR(50), UNIQUE), `codigo_op` (VARCHAR(50), Nullable), `proceso_origen` (ENUM: `'RECEPCION_COMPRAS'`, `'MECANIZADO_MES'`, `'INSPECCION_FINAL'`), `causa_raiz` (ENUM: `'MATERIAL_DEFECTUOSO'`, `'FALLA_HERRAMIENTA'`, `'ERROR_PLANO'`, `'OPERACIONAL'`), `piezas_scrap` (INTEGER, DEFAULT 0), `disposicion` (ENUM: `'REPROCESAR'`, `'CHATARRA_SCRAP'`, `'ACEPTAR_BAJO_CONCESION'`), `fecha_registro` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW()).
    
- **`acciones_capa`:** `id_capa` (UUID, PK), `id_rnc` (UUID, FK -> `reportes_no_conformidad.id_rnc`), `accion_correctiva` (TEXT, NOT NULL), `responsable_id` (UUID, FK -> `usuarios.id_usuario`), `fecha_compromiso` (DATE), `cerrado` (BOOLEAN, DEFAULT False).
    

### B. Registro Inmutable de Auditoría del Sistema (`auditoria_sistema`)

- `id_auditoria` (UUID, PK)
    
- `tabla_afectada` (VARCHAR(100), NOT NULL)
    
- `id_registro` (VARCHAR(100), NOT NULL)
    
- `operacion` (VARCHAR(20), CHECK: `operacion IN ('INSERT', 'UPDATE', 'DELETE')`)
    
- `estado_anterior` (JSONB, Nullable)
    
- `estado_nuevo` (JSONB, Nullable)
    
- `usuario_id` (UUID, FK -> `usuarios.id_usuario`, Nullable)
    
- `fecha_hora` (TIMESTAMP WITH TIME ZONE, DEFAULT NOW())
    

## 8. Enlaces Relacionados en el Vault

- [[Mapa de procesos]] - Flujo macro transversal ISO 9001:2026.
    
- [[Mapeo_Modulos_SGI_vs_SAP]] - Homologación de entidades con SAP S/4HANA.
    
- [[PM-04_Separacion_Inventario_Almacen]] - Procedimiento de almacén y kárdex.
    
- [[PM-06_Logistica_Custodia_Despacho]] - Circuito de picking, despacho y custodia.
    
- [[RN-OP-004_Bloqueo_Liberacion_OP]] - Quality Gate de liberación a planta.
    
- [[RN-LOG-002_Compromiso_Stock_Apartados]] - Regla de reservas temporales.