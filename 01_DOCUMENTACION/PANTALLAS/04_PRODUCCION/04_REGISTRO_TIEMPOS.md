# Pantalla: Registro de Tiempos de Producción y Paradas

##  Objetivo
Capturar en tiempo real los tiempos operativos de máquina y mano de obra asociados a una Orden de Producción (OP), incluyendo tiempos de preparación (Setup), mecanizado activo, tiempos muertos y pausas justificadas.

## ⏱ Tipos de Registro de Tiempo
- **Tiempo de Preparación / Setup**: Montaje de piezas, alineación de prensas, calibración de herramientas y carga/creación de programa de código CNC.
- **Tiempo Operativo / Maquinado Activo**: Tiempo efectivo en que la máquina (ej. `0357`) está ejecutando la fabricación.
- **Tiempo Muerto / Parada**: Detención no programada de la producción.

##  Campos del Formulario / Modal
- `ID_Registro_Tiempo`: Consecutivo generado automáticamente.
- `ID_OP`: Selección de la Orden de Producción activa.
- `Máquina`: Código identificador de 4 dígitos (ej. `0357`).
- `Operario`: Empleado responsable de la maquina o montaje.
- `Tipo_Evento`: `SETUP`, `MAQUINADO`, `PARADA_MANTENIMIENTO`, `PARADA_MATERIAL`, `PAUSA_OPERATIVA`.
- `Hora_Inicio` | `Hora_Fin`: Captura de marcas de tiempo (Timestamps).
- `Duracion_Calculada`: Diferencia en minutos/horas calculada automáticamente por el sistema.
- `Causa_Parada` (Solo si Tipo_Evento es Parada):
  - `Falta de Insumos / Insertos`
  - `Mantenimiento Preventivo / Correctivo`
  - `Ajuste de Programa CNC`
  - `Espera de Inspección de Calidad`
  - `Falla Eléctrica / Mecánica`
- `Observaciones`: Notas explicativas del evento.

##  Botones de Acción Rápida (Cronómetro en Planta)
- **Iniciar Setup / Preparación**: Activa el contador inicial antes de fabricar la primera pieza.
- **Iniciar Maquinado**: Conmuta el estado de la OP a "EN FABRICACIÓN".
- **Pausar / Registrar Parada**: Detiene el contador activo y despliega el formulario de justificación de parada.
- **Finalizar Tarea**: Registra el tiempo total acumulado del lote o turno.

##  Reglas de Negocio e Indicadores
1. **Cálculo de OEE (Efectividad Global del Equipo)**: El tiempo de maquinado activo frente al tiempo total disponible alimenta directamente los indicadores de disponibilidad del equipo.
2. **Costo Real de Mano de Obra y Máquina**: Los minutos registrados se multiplican por la tarifa/hora de la máquina y del operario para calcular el costo real de fabricación de la OP vs. el presupuesto estimado por Diseño/Ventas.