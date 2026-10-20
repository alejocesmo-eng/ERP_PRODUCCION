# MATRIZ DE CONTROLES DE CALIDAD OPERATIVOS

**Versión:** 1.0  
**Estado:** Documento base de diseño  
**Documento:** 08_MATRIZ_DE_CONTROLES_CALIDAD.md  

---

## 1. PUNTOS DE INSPECCIÓN Y VERIFICACIÓN (Puntos de Control)

| Punto de Control | Etapa del Flujo | Elemento a Inspeccionar | Criterio de Aceptación | Registro en Software | Acción en Desviación |
|---|---|---|---|---|---|
| **PC-REC-01** | Recepción Almacén | Materia Prima / Insumos | Certificado de calidad y dimensiones según PO | Ficha de Recepción Lote | Generar Marcación "Bloqueado" / RNC |
| **PC-DIS-01** | Pre-Generación OP | Paquete Técnico de Diseño | Plano con firma digital/estado Aprobado y BOM | Checklist de Calidad OP | Devolución a Diseño (OP Rechazada) |
| **PC-ALM-01** | Despacho a Planta | Material asignado a la OP | Trazabilidad por código de lote y cantidad 100% | Vale de Salida / Remisión | Bloqueo de liberación a producción |
| **PC-PROD-01** | Piso de Producción | Primera Pieza / Ensamble | Cotejo visual y dimensional contra plano activo | Registro de Control en Proceso | Detención de máquina y ajuste |
| **PC-MET-01** | Producto Terminado | Dimensiones y Acabado | Tolerancias especificadas en plano técnico | Reporte Dimensional Metrología | Apertura de No Conformidad (RNC) |
| **PC-CAL-02** | Equipos / Instrumentos | Estado de Calibración | Certificado vigente sin fecha de vencimiento superada | Hoja de Vida Instrumentos | Bloqueo de uso del instrumento en el sistema |

---

## 2. FLUJO DE TRATAMIENTO DE NO CONFORMIDADES (PC-03)

```text
DETECCIÓN ──► REGISTRO (Bloqueo) ──► ANÁLISIS CAUSA (5 Porqués/Ishikawa)
                                             │
                                             ▼
ACCION CORRECTIVA ◄── CORRECCIÓN / REPROCESO ┘
       │
       ▼
VERIFICACIÓN DE EFICACIA ──► CIERRE DE NC
