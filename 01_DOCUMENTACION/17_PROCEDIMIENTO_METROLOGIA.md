# 17 — PROCEDIMIENTO DE GESTIÓN METROLÓGICA (ISO 9001:2026)

**Código:** PR-SGI-MET-001  
**Versión:** 1.0  
**Estado:** Procedimiento Aprobado  
**Prioridad:** P2 — Media (AC-015)  

---

## 1. OBJETIVO Y CRITERIOS DE ACEPACIÓN

Garantizar la confiabilidad de las mediciones dimensionales y pruebas de producto en planta mediante el control, calibración, mantenimiento y trazabilidad de los instrumentos de medición[cite: 8].

---

## 2. REGLA DE NEGOCIO BLOQUEANTE EN SOFTWARE (`RN-MT-001`)

1. **Hoja de Vida de Instrumentos (`instrumentos_medicion`):** Cada pie de rey, micrómetro, galga o durómetro cuenta con fecha de última calibración y fecha de vencimiento registrada[cite: 3].
2. **Bloqueo Automático en Ficha Metrológica:** El módulo de Metrología inhabilita la selección de cualquier instrumento cuya fecha de calibración esté vencida o cuyo estado sea "FUERA_DE_SERVICIO"[cite: 3].
3. **Tratamiento de Equipos Fuera de Tolerancia (OOT - Out of Tolerance):** Cuando un equipo resulta descalibrado durante su verificación, se genera una RNC inmediata (`PC-03`) y se audita el impacto en los lotes de producción inspeccionados con ese instrumento desde la última calibración válida[cite: 8].