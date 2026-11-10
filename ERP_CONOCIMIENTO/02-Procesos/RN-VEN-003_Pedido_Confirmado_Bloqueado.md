---
id_regla: RN-VEN-003
nombre: Ventas solo edita el pedido en borrador; confirmado queda bloqueado y pasa a Diseño
proceso_asociado: PM-01 Ventas / PM-02 Diseño e Ingeniería
estado: confirmada
confirmada_por: negocio, comunicada por el usuario del proyecto
fecha_confirmacion: 2026-11-10
---

# RN-VEN-003: pedido confirmado bloqueado para Ventas

## 1. Regla confirmada por negocio (2026-11-10)
1. Ventas solo edita un pedido en borrador (`proyectos.confirmado = false`).
2. Al confirmarlo, el pedido queda bloqueado para edición y pasa a Diseño.
3. Ventas no ve ni maneja órdenes de producción (OP). Las OP de las líneas las crean Diseño y Producción después de la confirmación.

## 2. Verificación contra el código (`fase-d-frontend`, 2026-11-10)

| Punto | Código | Estado |
|---|---|---|
| Confirmar | `PATCH /proyectos/{id}/confirmar`, roles ADMIN y VENTAS (`04_CODIGO/BACKEND/app/api/v1/proyectos.py:720-724`); marca `confirmado = true` y registra la traza BORRADOR → CONFIRMADO (`:760-770`) | implementada |
| Bloqueo de edición | `PATCH /proyectos/{id}` responde 400 «❌ Bloqueo ISO 9001…» antes de cambiar nada, también las líneas (`proyectos.py:622-626`). Pruebas: `tests/test_pedido_edicion_lineas.py` (`d9ae979`) | implementada |
| Pasa a Diseño | No hay traspaso: la bandeja de Diseño carga todos los pedidos de `GET /proyectos/`, también los borradores (`04_CODIGO/FRONTEND/src/views/nivel2/DisenoPlanosView.jsx:159,166,224,1230`) | parcial (contradice el punto 2) |
| Ventas no ve OP | El expediente del pedido devuelve las OP (`proyectos.py:466,522`) y Ventas las ve en «Órdenes de producción vinculadas» (`ProyectosView.jsx:955,2010`) | contradice el punto 3 |
| Ventas no maneja OP | `POST /ordenes/` acepta cualquier token, incluido VENTAS (`ordenes.py:660-665`) | contradice el punto 3 |
| OP solo de pedidos confirmados | `POST /ordenes/` no exige que el pedido esté confirmado | no existe |
| Requisitos para confirmar (RN-VEN-001, `01_DOCUMENTACION/09_REGLAS_DE_NEGOCIO_SGI.md:17`: cliente, fecha prometida y documentación técnica) | La confirmación no valida ninguno: solo revalida el stock PT y crea el picking | no existe |

## 3. Pendientes (no se cambian sin decisión)
- **Bandeja de Diseño:** ¿debe mostrar solo los pedidos confirmados?
- **OP y Ventas:** ¿se quita la sección de OP vinculadas de la vista de Ventas y del expediente que recibe Ventas, y se restringe `POST /ordenes/` a Diseño, Producción y ADMIN? Cambia roles, así que necesita la matriz de roles.
- **OP sobre pedido en borrador:** ¿`POST /ordenes/` debe rechazar las líneas de un pedido sin confirmar?
- **RN-VEN-001:** ¿qué datos exige la confirmación (cliente, fecha prometida, documentación técnica) y con qué mensaje?
