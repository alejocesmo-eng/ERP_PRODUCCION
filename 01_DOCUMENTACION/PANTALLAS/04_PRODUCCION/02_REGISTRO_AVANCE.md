# Pantalla: Registro de Avance de Fabricación y Mermas

##  Objetivo
Permitir al operario o supervisor de producción capturar las cantidades de piezas conformes producidas, piezas rechazadas/mermas y tiempos de máquina acumulados por turno.

##  Campos del Formulario
- `ID_Registro`: Consecutivo automático.
- `ID_OP`: Selección de la OP en proceso.
- `Operario`: Selección del empleado responsable.
- `Turno`: `MAÑANA`, `TARDE`.
- `Piezas_Buenas`: Cantidad de unidades fabricadas con conformidad.
- `Piezas_Rechazadas`: Cantidad de piezas defectuosas o con desviación.
- `Motivo_Rechazo`: Selección desplegable (`Error de Cero`, `Ruptura de Herramienta`, `Falla de Material`, `Medida fuera de Tolerancia`).
- `Observaciones`: Comentarios técnicos del turno.

##  Reglas de Negocio
- Al acumular la cantidad total de piezas requeridas por la OP, el sistema cambia automáticamente el estado de la OP a **"PRODUCCIÓN TERMINADA / PENDIENTE DE CALIDAD"** y envía notificación a Inspección de Calidad.