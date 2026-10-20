# 07 — MATRIZ DE INDICADORES DE GESTIÓN Y CALIDAD (KPI - ISO 9001:2026)

**Versión:** 1.0  
**Estado:** Documento de Control Aprobado  
**Propósito:** Definir los Indicadores Clave de Desempeño (KPI) para la evaluación de los procesos misionales, operacionales y de mejora continua del SGI.

---

## 1. ESTRUCTURA GENERAL DE INDICADORES

| Código KPI | Proceso SGI | Nombre del Indicador | Objetivo Metodológico | Fórmula de Cálculo | Meta SGI | Frecuencia | Responsable |
|---|---|---|---|---|---|---|---|
| **KPI-VEN-01** | PM-01 Ventas | Cumplimiento de Entregas (OTD) | Evaluar la puntualidad de proyectos respecto a la fecha comprometida. | `(Proyectos Entregados a Tiempo / Total Proyectos) * 100` | $\ge 95\%$ | Mensual | Comercial / Ventas |
| **KPI-DSN-01** | PM-02 Diseño | Eficiencia en Paquete Técnico | Medir el % de planos aprobados en primera revisión sin correcciones. | `(Planos Aprobados Rev-00 / Total Planos Generados) * 100` | $\ge 90\%$ | Mensual | Ingeniería / Diseño |
| **KPI-ALM-01** | PM-04 Almacén | Exactitud del Inventario (IRA) | Medir el grado de coincidencia entre el stock físico y el Kardex ERP. | `(Ítems Conciliados Exactos / Total Ítems Auditados) * 100` | $\ge 98\%$ | Mensual | Jefe de Almacén |
| **KPI-OP-01** | PM-03 Calidad | Eficacia de Liberación OP | Porcentaje de OPs liberadas sin bloqueos por falta de stock (`RN-OP-004`). | `(OPs Liberadas con Stock 100% / Total OPs Emitidas) * 100` | $100\%$ | Semanal | Líder de Calidad |
| **KPI-PRD-01** | PM-05 Planta | Rendimiento de Fabricación | Medir la proporción de piezas producidas conformes en estación. | `(Piezas Conformes Fabricadas / Total Piezas Programadas) * 100` | $\ge 97\%$ | Semanal | Supervisor Planta |
| **KPI-MET-01** | PM-06 Metrología| Cobertura de Calibración | Garantizar que el 100% de los instrumentos mantengan calibración vigente (`RN-MT-001`). | `(Instrumentos Calibrados Vigentes / Total Instrumentos) * 100` | $100\%$ | Trimestral | Metrología / Calidad |
| **KPI-NC-01** | PC-03 Calidad | Eficacia de Acciones Correctivas | Verificar la no reincidencia de fallas tras el cierre de RNCs (CAPA). | `(CAPAs Eficaces Sin Reincidencia / Total CAPAs Cerradas) * 100` | $\ge 90\%$ | Semestral | Calidad / SGI |

---

## 2. NIVELES DE ALERTA Y SEMÁFOROS EN DASHBOARD

* 🟢 **Verde (Conforme):** KPI dentro de la meta o superándola.
* 🟡 **Amarillo (Preventivo):** Desviación menor ($\le 5\%$ por debajo de la meta). Requiere análisis de causa en comité mensual.
* 🔴 **Rojo (Crítico / No Conforme):** Desviación mayor ($> 5\%$ por debajo de la meta). **Detona la apertura obligatoria de una RNC (`PC-03`)**.

---

## 3. INTEGRACIÓN Y TRAZABILIDAD AUTOMÁTICA EN EL ERP

1. Los datos base para calcular los KPIs provienen directamente de los registros inmutables de PostgreSQL (`ordenes_produccion`, `trazabilidad_auditora`, `no_conformidades`, `almacen`).
2. El Dashboard Gerencial (`Level 1`) consumirá la API `/api/v1/indicadores/` para renderizar en tiempo real el estado de los semáforos sin cálculos manuales.