---
tipo: kpi
estado: borrador
responsable: por-confirmar
---
---
tipo: kpi
codigo: KPI-TAL-001
nombre: Cuadro de Mando e Indicadores de Gestión de Taller CNC y Calidad
fase: F1-F5
estado: aprobado
version: 1.0
autor: Analista Funcional / Jefe de Operaciones
sistema_destino: ERP FastAPI + PostgreSQL
---

# KPI-TAL-001: Cuadro de Mando e Indicadores de Gestión de Taller CNC y Calidad

## 1. Propósito
Definir las fórmulas, fuentes de datos SQL y umbrales de aceptación para la medición de desempeño en Diseño, Taller CNC, Calidad Metrológica y Tratamiento Térmico.

---

## 2. Indicadores Clave de Desempeño (KPIs)

### 2.1. Eficiencia de Tiempo de Diseño (ETD)
- **Objetivo**: Evaluar la precisión de la estimación del Líder de Diseño vs. el tiempo real invertido por el dibujante.
- **Fórmula**: 
  $$\text{ETD} = \left( \frac{\text{Horas Reales de Diseño}}{\text{Horas Estimadas por Líder}} \right) \times 100$$
- **Fuente SQL**: Tabla `tiempos_diseno` (`segundos_reales_acumulados` / (`tiempo_estimado_horas` * 3600)).
- **Meta / Umbral**: $85\% - 105\%$ (Verde: Cumplido, Rojo: $>120\%$ de desviación).

### 2.2. Ratio de Desviación de Setup CNC (RDS)
- **Objetivo**: Controlar los cuellos de botella en el alistamiento de máquinas CNC.
- **Fórmula**: 
  $$\text{RDS} = \left( \frac{\text{Tiempo Setup Real}}{\text{Tiempo Setup Estándar}} \right) \times 100$$
- **Fuente SQL**: Tabla `registro_tiempos_produccion` filtrada por `tipo_tiempo = 'SETUP'`.
- **Meta / Umbral**: $<110\%$. Si excede el $150\%$, el ERP solicita justificación obligatoria (ADR-001).

### 2.3. Tasa de Scrap y No Conformidad (NC)
- **Objetivo**: Medir la calidad del mecanizado y el porcentaje de re-solicitudes de materia prima.
- **Fórmula**: 
  $$\text{Tasa NC} = \left( \frac{\text{Piezas Defectuosas (Scrap)}}{\text{Piezas Totales Producidas}} \right) \times 100$$
- **Fuente SQL**: Conteo de filas en `no_conformidades` vs. suma de `cantidad` en `ordenes_produccion`.
- **Meta / Umbral**: $< 2.5\%$ del total producido.

---

## 3. Preguntas por Validar

### Responsables y suplencias:
- [PENDIENTE: Especificar la periodicidad de corte de los indicadores (mensual vs. semanal).]

### Aprobaciones:
- [PENDIENTE: Confirmar si los dashboards de KPI de la Fase 5 se visualizarán en Grafana, Metabase o un dashboard integrado en React/FastAPI.]

---
# Nombre del KPI

- Objetivo:
- Proceso:
- Definición:
- Fórmula exacta:
- Unidad:
- Fuente de datos:
- Frecuencia:
- Responsable:
- Línea base:
- Meta:
- Umbrales y criterio de interpretación:
- Exclusiones:
- Riesgos de interpretación:
- Acción si se desvía:
- Fecha de revisión:


---
## Enlaces de Métricas y Costos
- [[ADR-004_Costeo_Real_vs_Estandar_OP]]
- [[Mapa de procesos]]
- [[Inicio]]