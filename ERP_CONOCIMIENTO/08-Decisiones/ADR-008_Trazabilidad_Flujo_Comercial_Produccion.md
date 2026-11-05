---
id: ADR-008
titulo: Base de trazabilidad transaccional de documentos
estado: aprobado
fecha: 2026-11-03
autor: Dirección / Equipo Prisma
iso_9001_2026: Cláusulas 7.5 y 8.5.2
relacionados: ["[[Modelo_ERD_PostgreSQL]]", "[[Mapeo_Modulos_SGI_vs_SAP]]"]
---

# ADR-008: Base de trazabilidad transaccional de documentos

## 1. Contexto

Prisma ya define el modelo `historial_acciones_documento`, pero la tabla no tenía una migración propia y las rutas de historial aceptaban el nombre y el área del responsable desde el cliente. Además, el evento se guardaba en una transacción separada y un fallo al guardarlo solo se registraba en consola.

## 2. Decisión

1. La tabla `historial_acciones_documento` registra estados, acción, responsable, área, motivo y fecha con zona horaria. El esquema se incorpora mediante la migración aditiva planificada `14_MIGRACION_TRAZABILIDAD_COMERCIAL_PRODUCCION.sql`.
2. El servicio `app/services/auditoria.py` (`agregar_evento_trazabilidad`) añade el evento a la transacción activa sin confirmarla. Quien lo llama confirma el evento junto con el cambio que registra; si el historial no se puede guardar, el cambio tampoco se confirma.
3. Las rutas de historial (`GET /historial/{tipo_entidad}/{identificador}`, `POST /historial/suspender` y `POST /historial/reactivar`) exigen un JWT válido. El responsable y el área se obtienen del correo y del rol del token, no de los datos enviados por el cliente.
4. Si falla el registro de una suspensión o reactivación, la API revierte la transacción y devuelve el error en lugar de ocultarlo.

## 3. Alcance y límites

Esta decisión solo establece la base: la tabla, el servicio y las rutas de historial. Los módulos que registran eventos con este servicio se incorporan en cambios posteriores, cada uno con su propia revisión.

No implementa todavía la bitácora inmutable global `auditoria_sistema` descrita en el ERD, ni registra una fotografía JSON de todos los campos modificados. La identificación se basa en el correo del token; se requieren cuentas individuales para atribuir acciones de forma inequívoca a cada persona.

La migración `14_MIGRACION_TRAZABILIDAD_COMERCIAL_PRODUCCION.sql` debe aplicarse en un despliegue planificado antes de usar estas rutas en una base que aún no tenga la tabla.
