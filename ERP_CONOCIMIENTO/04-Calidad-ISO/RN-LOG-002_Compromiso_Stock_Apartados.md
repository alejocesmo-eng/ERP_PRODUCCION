---
id_regla: RN-LOG-002
nombre: Reserva Temporal y Bloqueo de Stock Comprometido
proceso_asociado: PM-01 Ventas / PM-04 Almacén e Inventarios
iso_9001_2026: Cláusula 8.2 (Revisión de requisitos para los productos) / 8.5 (Control de salidas)
estado: APROBADO
---

# [[RN-LOG-002_Compromiso_Stock_Apartados]]

## 1. Declaración de la Regla de Negocio
Todo compromiso comercial de producto terminado en stock originado por canal telefónico, cotización verbal o preventa debe registrarse bajo la figura de **Reserva Temporal / Stock Comprometido**. Las unidades físicas continúan en almacén pero se descuentan inmediatamente del saldo vendible público.

## 2. Condiciones de Reserva y Vencimiento
- **Saldo Disponible Real:**
  $$\text{Stock Disponible Venta} = \text{Stock Físico} - \text{Comprometido (Preventa)} - \text{En Picking}$$
- **Vigencia Máxima (SLA):** Todo compromiso temporal tiene una caducidad parametrizable de **48 horas hábiles** (o la fecha pactada con el cliente).
- **Notificación y Recordatorio Activo:**
  - Al 50% del tiempo transcurrido (24h) y a falta de 4 horas para vencer: el sistema emite una alerta a la bandeja de notificaciones del vendedor responsable:
    > *"🔔 Atención: Tienes [N] unidades de [SKU] comprometidas para el cliente [X]. Concreta el Pedido Comercial o el stock será liberado automáticamente."*
- **Liberación o Cierre:**
  - Si se concreta: La reserva se transforma automáticamente en línea de Pedido Comercial formal (`pedidos_detalle`) y genera la Orden de Picking.
  - Si vence sin concretar: El sistema libera las unidades y las regresa a `DISPONIBLE`, notificando a Logística y al vendedor.

---
id_regla: RN-LOG-002
nombre: Reserva Temporal y Bloqueo de Stock Comprometido (Preventa Telefónica)
proceso_asociado: PM-01 Ventas / PM-06 Logística
iso_9001_2026: Cláusula 8.2 (Requisitos para productos) / 8.5.4 (Preservación)
estado: APROBADO
---

# [[RN-LOG-002_Compromiso_Stock_Apartados]]

## 1. Declaración de la Regla de Negocio
Cuando un asesor comercial formalice una promesa de entrega por llamada telefónica o preventa verbal sobre unidades físicas disponibles en bodega, debe registrar de inmediato una **Reserva Temporal**. Las piezas continuarán en su ubicación física en estantería pero se sustraerán de la visibilidad pública de inventario disponible.

## 2. Condiciones y Caducidad
- **Cálculo de Disponibilidad Pública:**
  $$\text{Stock Disponible para Venta} = \text{Stock Físico Total} - \text{Stock Comprometido (Reservas Activas)} - \text{En Picking}$$
- **Vigencia Máxima:** Por defecto **48 horas hábiles** (parametrizable al crear la reserva).
- **Sistema de Alertas y Recordatorios:**
  - Al 50% de la vigencia (24h) y a falta de 4 horas para el vencimiento, el ERP emitirá una notificación al asesor comercial responsable con el texto:
    > *"🔔 Recordatorio: Tienes [Cantidad] unidades de [SKU] en reserva para el cliente [Cliente]. Concreta el Pedido Comercial antes de su vencimiento o el stock será liberado automáticamente."*
- **Disolución de Reserva:**
  - Si el pedido se confirma: La reserva se liquida e imputa formalmente a las posiciones del Pedido Comercial (`pedidos_detalle`), liberando la orden de picking.
  - Si expira sin confirmación: El sistema devuelve las unidades a estado `DISPONIBLE` y emite aviso tanto a Logística como al asesor.