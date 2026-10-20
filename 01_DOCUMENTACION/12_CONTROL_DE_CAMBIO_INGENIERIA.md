# 12 — PROCEDIMIENTO DE CONTROL DE CAMBIOS DE INGENIERÍA (ISO 9001:2026)

**Código:** PR-SGI-ING-002  
**Versión:** 1.0  
**Estado:** Procedimiento Aprobado  
**Prioridad:** P1 — Alta (AC-013)  

---

## 1. OBJETIVO Y ALCANCE

Definir el flujo de solicitud, análisis de impacto, aprobación, congelamiento e implementación de modificaciones técnicas a planos o listas de materiales (BOM) cuando la Orden de Producción ya ha sido creada o liberada[cite: 8, 12].

---

## 2. FLUJO CONTROLADO DE CAMBIO DE INGENIERÍA (ECN - Engineering Change Notice)

```text
 SOLICITUD DE CAMBIO (Cliente / Diseño / Producción)
                        │
                        ▼
ANÁLISIS DE IMPACTO TÉCNICO Y ECONÓMICO (Diseño + Calidad + Costos)
                        │
                        ▼
      ¿AFECTA ÓRDENES DE PRODUCCIÓN ACTIVAS?
            │                           │
           SÍ                           NO
            │                           │
            ▼                           ▼
  CONGELAR FABRICACIÓN         CREAR NUEVA REVISIÓN
 (Estado: EN_PAUSA_CAMBIO)     (Ej: REV-01 -> REV-02)
            │                           │
            └───────────────┬───────────┘
                            │
                            ▼
           APROBACIÓN DE NUEVA REVISIÓN (REV-02)
                            │
                            ▼
   REGULARIZAR BOM Y RE-EVALUAR STOCK EN ALMACÉN (RN-OP-004)
                            │
                            ▼
RE-LIBERACIÓN DE OP / NOTIFICACIÓN AUTOMÁTICA EN TERMINAL
```[cite: 8, 12, 14, 15]

---

## 3. REGLAS DE NEGOCIO EN EL ERP (`RN-DS-001` / `RN-ING-002`)

1. **Inmutabilidad de Versiones Obsoletas (`RN-DS-001`):** Al aprobarse `REV-02`, la versión `REV-01` pasa automáticamente a estado `OBSOLETO`[cite: 1, 12, 14].
2. **Terminal de Planta (`RN-PRO-001`):** La vista de Producción bloquea la apertura de planos en estado `OBSOLETO` o `BORRADOR`[cite: 14, 15].
3. **Evaluación de Impacto en Stock:** Si el cambio de ingeniería modifica la materia prima en el BOM, la OP activa revoca su estado de reserva 100% y solicita verificación de Almacén antes de reanudar la fabricación[cite: 8, 12, 15].