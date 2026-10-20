# Pantalla: Despacho y Entrega de Material a Producción

##  Objetivo
Formalizar la salida de inventario hacia la planta de producción, registrando el receptor, fecha y confirmación de entrega completa o parcial de insumos para la OP.

##  Flujo de Despacho
1. **Selección de OP / Solicitud**: Búsqueda por número de OP liberada o en proceso.
2. **Checklist de Verificación de Insumos**:
  - Verificación ítem por ítem del material preparado (Materia prima, herramientas, insertos, planos impresos/digitales).
3. **Firma / Confirmación de Recepción**:
  - `Receptor_Planta`: Selector/búsqueda del operario o supervisor que recibe.
  - `Tipo_Entrega`: `TOTAL` o `PARCIAL`.
  - `Observaciones`: Notas sobre faltantes o entregas pendientes.

##  Regla de Liberación
- La entrega de material completada habilita en el módulo de Producción el estatus de la OP a **"LISTO EN MÁQUINA / EN FABRICACIÓN"**.