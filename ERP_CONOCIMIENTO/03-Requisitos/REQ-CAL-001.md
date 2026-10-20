---
tipo: requisito
codigo: REQ-CAL-001
nombre: Control Metrológico, Tratamiento Térmico y Gestión de NC (ISO 9001:2015)
fase: F1-F4
modulo: Calidad de Producto
prioridad: ALTA
estado: aprobado
autor: Analista Funcional / Arquitecto de Software
normativa_aplicable: ISO 9001:2015 (Numerales 8.5.1, 8.5.2, 8.6, 8.7, 9.1.2)
sistema_destino: ERP FastAPI + PostgreSQL
---

# REQ-CAL-001: Control Metrológico, Tratamiento Térmico y Gestión de NC (ISO 9001:2015)

## 1. Contexto y Cumplimiento Normativo ISO 9001:2015
Este requisito normativo asegura que el ERP cumpla con los estándares de calidad para la industria de alimentos y manufactura CNC:
- **ISO 9001:2015 - Numeral 8.5.1 (Control de la producción)**: Seguimiento de condiciones controladas en puesto CNC.
- **ISO 9001:2015 - Numeral 8.5.2 (Identificación y trazabilidad)**: Trazabilidad total de la OP (`100XXXX`, `300XXXX`, `400XXXX`) desde el material hasta la entrega.
- **ISO 9001:2015 - Numeral 8.6 (Liberación de productos y servicios)**: Registro metrológico obligatorio antes de autorizar el cierre de OP o despacho.
- **ISO 9001:2015 - Numeral 8.7 (Control de las salidas no conformes)**: Registro de No Conformidades (NC), segregación de material defectuoso y re-solicitud automática de materia prima.

---

## 2. Historias de Usuario ISO

### HU-CAL-01: Inspección Metrológica Registrada (ISO 8.6)
- **Como** Inspector de Calidad,
- **Quiero** registrar la medición dimensional de las piezas con micrómetro, calibrador pie de rey o patrones,
- **Para** verificar la conformidad del producto antes de proceder al tratamiento térmico o entrega final.

### HU-CAL-02: Evidencia Fotográfica y Envío Maquila (ISO 8.5.1)
- **Como** Inspector de Calidad,
- **Quiero** adjuntar obligatoriamente fotos del lote y generar un informe de Tratamiento Térmico en PDF enviado por email al proveedor,
- **Para** mantener evidencia objetiva de las condiciones enviadas a maquila externa.

### HU-CAL-03: Control de Salidas No Conformes y Scrap (ISO 8.7)
- **Como** Inspector de Calidad,
- **Quiero** emitiir un reporte de No Conformidad (`NC-AAAA-XXXX`) cuando una pieza no cumpla tolerancias, activando una solicitud de reposición de materia prima a Compras,
- **Para** evitar la entrega inadvertida de piezas fuera de especificación y reiniciar la fabricación trazable.

---

## 3. Criterios de Aceptación (BDD / Gherkin)

### Escenario 1: Bloqueo de liberación sin inspección metrológica
- **DADO QUE** la OP `4001002` terminó su etapa de mecanizado CNC,
- **CUANDO** el Jefe de Operaciones intente ejecutar el `Cierre de OP`,
- **ENTONCES** el ERP bloquea la acción con un error `400 Bad Request` si no existe un registro de inspección metrológica en la tabla `inspecciones_calidad`.

### Escenario 2: Generación automática de No Conformidad
- **DADO QUE** se registra una cota fuera de tolerancia en `inspecciones_calidad`,
- **CUANDO** el resultado sea marcado como `NO_CONFORME`,
- **ENTONCES** el sistema crea un registro en `no_conformidades`,
- **Y** dispara una solicitud de materia prima en la pestaña de Compras con el ID de la OP original.

---

## 4. Preguntas por Validar

### Responsables y suplencias:
- [PENDIENTE: Definir si el informe de inspección metrológica firmado digitalmente se enviará también al cliente final como certificado de calidad.]