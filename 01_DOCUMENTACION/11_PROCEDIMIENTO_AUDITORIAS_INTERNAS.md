# 11 — PROCEDIMIENTO DE AUDITORÍAS INTERNAS DEL SGI (ISO 9001:2026)

**Código:** PR-SGI-AUD-001  
**Versión:** 1.0  
**Estado:** Procedimiento Aprobado  
**Prioridad:** P1 — Alta (AC-008)  

---

## 1. OBJETIVO Y ALCANCE

Establecer la metodología para planificar, ejecutar, reportar y hacer seguimiento a las auditorías internas del Sistema de Gestión Integral (SGI). Aplica a todos los procesos estratégicos, misionales (Ventas, Diseño, Calidad, Almacén, Producción, Metrología) y de apoyo[cite: 8, 12].

---

## 2. METODOLOGÍA DEL CICLO DE AUDITORÍA (PHVA)

1. **Programa Anual de Auditorías:** Calidad define la frecuencia basándose en el estado, importancia y riesgos de cada proceso (`PE-02`)[cite: 8, 12].
2. **Independencia del Auditor:** Ningún auditor evaluará su propio trabajo.
3. **Muestreo Basado en Evidencia:** Se evalúan registros reales en PostgreSQL (`trazabilidad_auditora`, firmados por usuario/fecha)[cite: 8, 12, 14].
4. **Clasificación de Hallazgos:**
   * **Conformidad:** Cumplimiento demostrado.
   * **Observación / Oportunidad de Mejora:** Riesgo potencial sin incumplimiento explícito[cite: 8, 12].
   * **No Conformidad (RNC):** Incumplimiento directo de un requisito ISO 9001:2026 o regla de negocio (`RN-*`)[cite: 8, 14, 15].

---

## 3. CAMPOS OBLIGATORIOS DEL REGISTRO EN SOFTWARE (`audit_logs` / `auditorias`)

Para cada auditoría realizada, el ERP registrará inmutablemente[cite: 12]:
* `id_auditoria`: Código único consecutivo (ej. AUD-2026-001)[cite: 12].
* `proceso_auditado`: Proceso o módulo SGI[cite: 12].
* `auditor_id`: Usuario asignado con competencia demostrada.
* `criterios_evaluados`: Requisito ISO 9001 o regla de negocio (`RN-OP-*`, `RN-DS-*`).
* `evidencia_objetiva`: Archivo, ID de registro o transacción consultada[cite: 8, 12].
* `hallazgo_clasificacion`: CONFORME | OBSERVACIÓN | NO_CONFORME[cite: 8, 12].
* `link_rnc_id`: Enlace automático con la No Conformidad generada (`PC-03`) cuando aplique[cite: 8, 12].