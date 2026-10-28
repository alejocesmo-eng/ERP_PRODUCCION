---
id: ADR-004
titulo: Arquitectura del Motor de Costeo Real y Liquidación de OPs (SAP CO)
estado: APROBADO
fecha: 2026-10-21
iso_9001_2026: Clausulas 8.5.1, 9.1.3
modulo_equivalente_sap: SAP CO-PC (Product Cost Controlling)
---

# [[ADR-004_Costeo_Real_vs_Estandar_OP|Costeo Real vs. Estándar por Orden de Producción]]

## 1. Ecuación Maestra de Acumulación de Costo Real
Para cada `codigo_op`, el SGI-ERP calcula en tiempo real el costo total acumulado sumando tres vectores de costo directos:

$$\text{Costo Total Real OP} = \text{Costo Materia Prima (BOM/Kárdex)} + \text{Costo Mano de Obra / Máquina (MES)} + \text{Servicios Externos (Terceros)}$$

### Componentes de la Fórmula:
1. **Materia Prima e Insumos ($\text{MM}$):** 
   $$\sum \left( \text{Cantidad Consumida} \times \text{Costo Promedio Ponderado / FIFO Kárdex} \right)$$
   *Descuenta stock directo de `lotes` o retales reutilizables.*
2. **Tiempo de Mecanizado y Setup ($\text{MES}$):**
   $$\sum \left( \text{Horas Registradas en Tablet MES} \times \text{Tarifa Horaria Centro de Trabajo (CNC)} \right)$$
   *Calculado automáticamente por el cronómetro del sub-lote (`segundos_setup` + `segundos_produccion`).*
3. **Servicios Externos / Tratamientos ($\text{Terceros}$):**
   $$\sum \left( \text{Factura / Orden de Compra (PO) de Galvánico / Tratamiento Térmico} \right)$$

---

## 2. Análisis de Desviación de Margen (Variance Analysis)

Al cerrar la OP (Paso 8 - Ensamble & Cierre / Calidad), el sistema compara el presupuesto cotizado por Ventas en `proyectos` vs. el costo real liquidado:

$$\text{Desviación (\%)} = \left( \frac{\text{Precio Cotizado (Ventas)} - \text{Costo Real (MES/Kárdex)}}{\text{Precio Cotizado (Ventas)}} \right) \times 100$$

- **Si Margen Real < Margen Mínimo Tolerado (ej. 25%):** El ERP dispara un evento automático en `Capas / RNC` para analizar la causa raíz (exceso de horas machine, scrap o reproceso).

---

## 3. Matriz de Mapeo de Datos en PostgreSQL

| Componente de Costo | Fuente de Datos (Tabla) | Evento Disparador |
| :--- | :--- | :--- |
| **Materia Prima** | `solicitudes_compra` / `lotes` | Almacén marca `ENTREGADO` a planta. |
| **Mano de Obra / Máquina** | `sub_lotes_operacion` / `operaciones_ot` | Operario detiene cronómetro en Tablet MES. |
| **Servicio Externo** | `compras_detalles` | Recepción de factura de proveedor externo. |

---

## 4. Enlaces Relacionados
- [[Mapeo_Modulos_SGI_vs_SAP]] - Matriz general SAP.
- [[PM-04_Compras_MRP_Kardex]] - Consumo de inventarios y retales.
- [[Controles de calidad]] - Impacto del Scrap en el costo real.