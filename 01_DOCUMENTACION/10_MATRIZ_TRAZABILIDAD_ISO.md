# 10 — MATRIZ DE TRAZABILIDAD DE REQUISITOS ISO 9001:2026 / SGI

**Versión:** 1.0  
**Estado:** Documento base de gobierno  
**Propósito:** Mapear cada requisito de la norma ISO 9001:2026 con el proceso, control, documento, registro, indicador y prueba en el ERP.

---

## 1. MATRIZ DE TRAZABILIDAD Y CONTROL AUTOMÁTICO

| Requisito ISO 9001:2026 | Proceso SGI | Control de Calidad | Documento / Registro | Indicador / KPI | Regla / Módulo ERP |
|---|---|---|---|---|---|
| **4. Contexto y Alcance** | PE-01 Dirección | Aprobación del alcance y partes interesadas. | `00_OBJETIVO_Y_ALCANCE.md` | Cumplimiento del Plan SGI | Módulo Dashboard Gerencial |
| **5. Liderazgo y Roles** | PE-01 / PA-01 | Matriz RACI y perfiles de perfil autorizados. | `02_MATRIZ_RESPONSABILIDADES.md` | Eficacia de competencias | Control de Roles (RBAC) |
| **6. Planificación / Riesgos** | PE-02 Riesgos | Evaluación de impactos y controles automáticos. | `06_MATRIZ_DE_RIESGOS.md` | % Riesgos Mitigados | Reglas bloqueantes (`RN-*`) |
| **7.5 Información Documentada** | PC-06 Doc. | Control de versiones, estados e inmutabilidad. | `09_REGLAS_DE_NEGOCIO_SGI.md` | % Documentos Vigentes | Inmutabilidad de Planos PDF |
| **8.2 Requisitos Cliente** | PM-01 Ventas | Confirmación de requisitos antes de ofertar. | Registro de Proyecto / Pedido | % Entregas a Tiempo (OTD) | `RN-VT-001` (FastAPI) |
| **8.3 Diseño y Desarrollo** | PM-02 Diseño | Revisiones técnicas y congelamiento de planos. | Expediente de Plano / BOM | Revisiones por Plano | `RN-DS-001` / Módulo Planos |
| **8.4 Proveedores / Compras** | PA-05 Compras | Evaluación y recepción física auditada. | Factura y Cotejo de Compras | % Cumplimiento Proveedor | Módulo Almacén / Compras |
| **8.5 Producción / Servicio** | PM-05 Planta | Liberación con stock 100% y plano vigente. | Orden de Producción (OP) | % Reprocesos / Desperdicio | `RN-OP-004` (Reserva Stock) |
| **8.6 Liberación de Producto** | PM-06 Metrología | Inspección dimensional con equipos calibrados. | Reporte Metrológico | % Conformidad Producto | Módulo Metrología / Liberación |
| **8.7 Producto No Conforme** | PC-03 RNC | Bloqueo de lote, contención y disposición. | Registro RNC / CAPA | # No Conformidades Abiertas | Módulo Calidad / RNC |
| **9.2 Auditoría Interna** | PC-02 Audit. | Programa anual, hallazgos y seguimiento. | Informe de Auditoría | % Hallazgos Cerrados | Trazabilidad de Auditoría |
| **10. Mejora Continua** | PC-05 Mejora | Análisis de causa raíz y evaluación de eficacia. | Ficha de Acción Correctiva | Eficacia de Acciones CAPA | Módulo Mejora Continua |