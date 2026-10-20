# REGLAS DE NEGOCIO Y VALIDACIONES DEL SGI (ISO 9001:2026)

**Versión:** 1.0  
**Estado:** Requisitos del Sistema / Backend  
**Documento:** 09_REGLAS_DE_NEGOCIO_SGI.md  

---

## 1. PRINCIPIOS GENERALES
El software opera bajo el principio de **Gestión Transversal de Calidad**. Las reglas impiden la continuidad de cualquier proceso que carezca de documentación activa, firmas de aprobación o disponibilidad de insumos.

---

## 2. REGLAS MAESTRAS POR MÓDULO

### A. Ventas y Clientes (PM-01)
* **RN-VEN-001 (Integridad Comercial):** Un proyecto no puede pasar a estado `CONFIRMADO` si falta el cliente, fecha prometida o la documentación técnica inicial adjunta.
* **RN-VEN-002 (Control de Cambios):** Toda modificación a los requisitos del cliente sobre un proyecto verificado genera una alerta automática a Diseño y la creación de un registro en la trazabilidad[cite: 1].

### B. Diseño e Ingeniería (PM-02)
* **RN-DIS-001 (Control de Versión Vigente):** Cuando un plano pasa a estado `APROBADO` en una nueva revisión (ej. REV-02), la versión anterior (REV-01) pasa automáticamente a `OBSOLETO` y no puede asociarse a nuevas OPs[cite: 1].
* **RN-DIS-002 (Paquete Técnico Completo):** El sistema bloquea el envío de la documentación hacia Calidad si el BOM (Lista de Materiales) no tiene definidas las cantidades exactas o los códigos de material[cite: 1].

### C. Generación y Control de OPs (PM-03)
* **RN-OP-001 (Exclusividad de Control):** Únicamente usuarios con **Rol de Calidad** pueden cambiar una OP de estado `BORRADOR/REVISIÓN` a `APROBADA`[cite: 1].
* **RN-OP-002 (Validación Automática Pre-OP):** El backend rechazará la generación de la OP si no detecta: (1) Proyecto Confirmado, (2) Plano Aprobado y Vigente, (3) BOM definido[cite: 1].
* **RN-OP-004 (Bloqueo de Liberación por Stock):** La OP **no puede cambiar a estado `LIBERADA_A_PRODUCCION`** si el Almacén no ha registrado una disponibilidad o reserva del 100% de la materia prima requerida en la BOM[cite: 1].
* **RN-OP-005 (Entregas Parciales):** Se permiten vales de salida de almacén parciales, manteniendo la OP en estado `MATERIAL_EN_GESTION` hasta completar el total asignado[cite: 1].

### D. Almacén e Inventarios (PM-04)
* **RN-ALM-001 (Trazabilidad de Lotes):** Todo despacho de material hacia producción exige asociar el código de lote/entrada del proveedor[cite: 1].
* **RN-ALM-002 (Insumos Bloqueados):** No se permite despachar material que se encuentre en estado "Bloqueado / No Conforme" en Almacén[cite: 1].

### E. Producción (PM-05)
* **RN-PROD-001 (Visualización Única):** La pantalla de los operadores de piso sólo mostrará el plano activo en revisión oficial `APROBADO`[cite: 1].

### F. Metrología y Calidad de Producto (PM-06)
* **RN-MET-001 (Vencimiento de Calibración):** El sistema impide seleccionar e ingresar datos de medición usando un equipo o instrumento cuya fecha de calibración esté vencida[cite: 1].

### G. No Conformidades y Mejora (PC-03 / PC-04)
* **RN-NC-001 (Evidencia Obligatoria):** Una No Conformidad no puede pasar al estado `CERRADA` si no adjunta el análisis de causa (ej. 5 Porqués) y la firma del responsable de Calidad[cite: 1].
* **RN-NC-002 (Verificación de Eficacia):** Toda Acción Correctiva asociada exige un período de prueba/seguimiento verificado por Calidad antes de formalizar el cierre[cite: 1].