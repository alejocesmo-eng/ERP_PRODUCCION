# Pantalla: Recepción e Ingreso de Materiales (Almacén)

##  Objetivo
Registrar el ingreso físico de materia prima, insumos y herramientas provenientes de proveedores o compras directas, actualizando el stock disponible en tiempo real.

##  Campos del Formulario
- `ID_Recepcion`: Consecutivo generado automáticamente.
- `Orden_Compra`: Número de OC / Factura del proveedor.
- `Proveedor`: Selección desde el Catálogo Maestro de Proveedores.
- `Tabla de Ítems Recibidos`:
  - `Material / Inserto`: Selector con búsqueda y ficha visual.
  - `Cantidad_Recibida`: Cifra de unidades / kilogramos / metros.
  - `Ubicación_Destino`: Selección de estante, nivel o zona de almacenaje.
- `Documentos Adjuntos`: Subida de certificado de calidad de materia prima / remisión (PDF/Foto).

##  Reglas de Negocio
- Al guardar el formulario, el sistema incrementa de forma automática el `Stock_Actual` de los artículos relacionados.
- Si el material recibido cubre una reserva de OP bloqueada por falta de stock, envía una notificación al usuario de Almacén y Producción.