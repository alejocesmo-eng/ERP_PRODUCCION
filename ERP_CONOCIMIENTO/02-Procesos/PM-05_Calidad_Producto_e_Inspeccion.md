---
id: PROC-QUAL-001
titulo: Inspección de Calidad de Producto Terminado y Tratamiento Térmico
estado: APROBADO
fecha: 2026-10-21
iso_9001_2026: Clausulas 8.5.1, 8.6 (Liberación de Productos y Servicios)
modulo_equivalente_sap: SAP QM (Quality Management)
---

# [[PM-05_Calidad_Producto_e_Inspeccion|Control de Calidad de Producto Terminado]]

## 1. Reglas de Negocio del Quality Gate de Inspección
1. **Bandeja de órdenes para inspección:** Calidad consulta las órdenes con estado `TERMINADA`, `INSPECCION_CALIDAD` o `EN_INSPECCION`. Las órdenes ya aprobadas para cierre no permanecen en la bandeja.
2. **Revisión Técnica de Planos:** El auditor/inspector consulta el plano vectorial PDF congelado (`archivo_url`) antes de emitir cualquier dictamen de liberación dimensional o metrológica.
3. **Fotografía obligatoria de salida:** No se permite guardar el dictamen sin al menos una fotografía JPG o PNG válida de las piezas salientes. La carga admite hasta diez imágenes de máximo 5 MB cada una.
4. **Flujo de Tratamiento Térmico:**
   - Si la pieza requiere tratamiento externo (ej. Temple, Cementación, Nitruración, Galvanizado), el inspector especifica la descripción técnica y la cantidad de piezas enviadas.
   - Genera un informe técnico HTML descargable, simula el envío de correo al proveedor y registra el servicio en `servicios_terceros_op`.
5. **Flujo de Aprobación para Despacho:**
   - Si las piezas son aprobadas para despacho, el sistema registra una notificación para el **Jefe de Producción** y cambia la orden a `LISTA_PARA_LIBERAR`. Producción realiza el cierre definitivo posteriormente.

---

## 2. Matriz de Estados de Liberación

| Dictamen Calidad | Acción ERP | Impacto en Producción / Almacén |
| :--- | :--- | :--- |
| `APROBADO_TRATAMIENTO` | Genera informe HTML y simula el correo al proveedor. | Registra el tratamiento como servicio de tercero asociado a la orden. |
| `APROBADO_DESPACHO` | Registra notificación al Jefe de Producción. | Cambia la orden a `LISTA_PARA_LIBERAR`, pendiente de cierre por Producción. |
| `RECHAZADO` | Registra el dictamen y sus evidencias. | La disposición posterior se gestiona mediante el flujo de no conformidades. |

---

## 3. Enlaces Relacionados
- [[Mapa de procesos]] - Flujo de Procesos del SGI.
- [[Controles de calidad]] - Puntos de Control y Quality Gates.
- [[Mapeo_Modulos_SGI_vs_SAP]] - Equivalencias SAP QM.