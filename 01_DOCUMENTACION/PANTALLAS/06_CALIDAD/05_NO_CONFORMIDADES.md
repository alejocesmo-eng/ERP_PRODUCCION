# NO CONFORMIDADES

## 1. Objetivo

El módulo de No Conformidades permite registrar y realizar seguimiento a los productos o procesos que no cumplen con los requisitos establecidos.

Una no conformidad podrá originarse durante una inspección de Calidad.

---

## 2. Acceso

Permisos:

- CALIDAD_VER
- CALIDAD_CREAR_NO_CONFORMIDAD
- CALIDAD_MODIFICAR_NO_CONFORMIDAD

---

## 3. Información de la no conformidad

Cada registro deberá contener como mínimo:

- Número de no conformidad.
- OP relacionada.
- Proyecto.
- Producto.
- Fecha.
- Usuario que registra.
- Descripción.
- Cantidad afectada.
- Tipo de no conformidad.
- Estado.
- Observaciones.

El número de no conformidad será generado automáticamente por el sistema.

Ejemplo:

NC-2026-0001

---

## 4. Tipos

Los tipos deberán ser configurables.

Ejemplos:

- Dimensional.
- Material.
- Acabado.
- Visual.
- Funcional.
- Documental.
- Proceso.
- Otro.

Los tipos definitivos serán definidos por la empresa.

---

## 5. Estados

Estados propuestos:

- ABIERTA
- EN ANÁLISIS
- PENDIENTE DE CORRECCIÓN
- EN CORRECCIÓN
- PENDIENTE DE VERIFICACIÓN
- CERRADA

---

## 6. Cantidades

Cuando la no conformidad afecte productos, deberá registrarse:

- Cantidad producida.
- Cantidad afectada.
- Cantidad aprobada.
- Cantidad rechazada.

Ejemplo:

Cantidad producida: 100

Cantidad afectada: 5

Cantidad aprobada: 95

Cantidad rechazada: 5

---

## 7. Acción correctiva

Cuando sea necesario realizar una corrección, se deberá registrar:

- Acción requerida.
- Responsable.
- Fecha prevista.
- Fecha realizada.
- Observaciones.
- Resultado.

La estructura definitiva de acciones correctivas será definida posteriormente según el proceso de Calidad de la empresa.

---

## 8. Relación con Producción

Cuando una no conformidad requiera corrección del producto:

CALIDAD
   ↓
NO CONFORMIDAD
   ↓
CORRECCIÓN
   ↓
PRODUCCIÓN
   ↓
NUEVA INSPECCIÓN
   ↓
CALIDAD

La información deberá mantenerse relacionada con la OP original.

---

## 9. Reinspección

Después de realizar una corrección, Calidad podrá realizar una nueva inspección.

La nueva inspección deberá quedar relacionada con:

- OP original.
- No conformidad.
- Inspección anterior.
- Corrección realizada.
- Nuevo resultado.

---

## 10. Cierre de no conformidad

Una no conformidad podrá cerrarse cuando:

- Se haya realizado la corrección requerida, si aplica.
- Calidad haya verificado la corrección.
- El resultado sea aceptable.
- Se hayan registrado las observaciones correspondientes.

El sistema deberá impedir el cierre cuando existan requisitos pendientes.

---

## 11. Relación con cierre de OP

Una OP con una no conformidad pendiente que impida su aprobación no podrá cerrarse.

La condición de cierre dependerá del resultado de Calidad y de las reglas definidas para cada tipo de no conformidad.

---

## 12. Evidencias

El sistema podrá permitir adjuntar:

- Fotografías.
- Informes.
- Mediciones.
- Documentos.
- Evidencias de corrección.

La implementación definitiva se definirá posteriormente.

---

## 13. Trazabilidad

Toda modificación deberá conservar:

- Usuario.
- Fecha.
- Hora.
- Estado anterior.
- Estado nuevo.
- Acción realizada.
- Observaciones.

No se deberán eliminar registros históricos de no conformidades.

---

## 14. Regla principal

Una no conformidad debe permanecer vinculada a la Orden de Producción que la originó.

Esto permitirá conocer posteriormente:

OP → INSPECCIÓN → NO CONFORMIDAD → CORRECCIÓN → REINSPECCIÓN → RESULTADO