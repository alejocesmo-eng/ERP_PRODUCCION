# INSPECCIÓN DE CALIDAD

## 1. Objetivo

La pantalla de Inspección permite registrar la verificación realizada por Calidad sobre una Orden de Producción.

El objetivo es determinar si el producto fabricado cumple con los requisitos establecidos.

---

## 2. Acceso

Permisos relacionados:

- CALIDAD_VER
- CALIDAD_INSPECCIONAR

---

## 3. Información de la OP

Antes de realizar la inspección se deberá mostrar:

- Número de OP.
- Proyecto.
- Cliente.
- Producto.
- Cantidad solicitada.
- Cantidad producida.
- Cantidad rechazada por Producción.
- Número de plano.
- Revisión.
- Fecha de producción.
- Responsable de Producción.

---

## 4. Información técnica

Calidad deberá poder consultar la información necesaria para realizar la inspección.

Puede incluir:

- Planos.
- Revisiones.
- Especificaciones.
- Dimensiones.
- Tolerancias.
- Material.
- Tratamientos.
- Requisitos especiales.
- Documentos asociados.
- Requisitos establecidos por el cliente.

La información exacta dependerá del tipo de producto.

---

## 5. Registro de inspección

La inspección deberá permitir registrar:

- Fecha.
- Hora.
- Inspector.
- Cantidad inspeccionada.
- Cantidad aprobada.
- Cantidad rechazada.
- Resultado.
- Observaciones.

---

## 6. Resultado

El resultado de la inspección podrá ser:

- APROBADO
- RECHAZADO
- PENDIENTE DE CORRECCIÓN
- REQUIERE REINSPECCIÓN

---

## 7. Evidencias

El sistema podrá permitir adjuntar evidencias relacionadas con la inspección.

Ejemplos:

- Fotografías.
- Informes.
- Mediciones.
- Documentos.
- Registros de equipos de medición.

La implementación específica de evidencias será definida posteriormente.

---

## 8. Cantidades

El sistema deberá diferenciar:

- Cantidad producida.
- Cantidad inspeccionada.
- Cantidad aprobada.
- Cantidad rechazada.
- Cantidad pendiente.

Ejemplo:

Cantidad producida: 100

Cantidad inspeccionada: 100

Cantidad aprobada: 95

Cantidad rechazada: 5

---

## 9. Registro de mediciones

Para productos que requieran control dimensional, el sistema podrá permitir registrar:

- Característica inspeccionada.
- Valor nominal.
- Tolerancia.
- Valor medido.
- Instrumento utilizado.
- Resultado.

Ejemplo:

| Característica | Nominal | Tolerancia | Medición | Resultado |
|---|---:|---:|---:|---|
| Diámetro | 50.00 mm | ±0.05 mm | 50.02 mm | OK |
| Longitud | 100.00 mm | ±0.10 mm | 100.08 mm | OK |

La estructura definitiva de las inspecciones dimensionales será definida posteriormente según las necesidades de la empresa.

---

## 10. Finalización de inspección

Al finalizar la inspección, el sistema deberá exigir:

- Resultado.
- Cantidad inspeccionada.
- Cantidad aprobada.
- Cantidad rechazada, si aplica.
- Observaciones cuando sean necesarias.

El usuario deberá confirmar el registro.

---

## 11. Regla de seguridad

Una inspección registrada no deberá modificarse silenciosamente.

Si se requiere modificar información crítica después de finalizarla, el sistema deberá mantener trazabilidad del cambio.

---

## 12. Trazabilidad

Registrar:

- Usuario.
- Fecha.
- Hora.
- OP.
- Inspección.
- Resultado.
- Cantidades.
- Observaciones.
- Documentos/evidencias.
- Estado anterior.
- Estado nuevo.