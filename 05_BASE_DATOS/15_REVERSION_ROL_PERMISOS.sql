-- 15_REVERSION_ROL_PERMISOS.sql
-- Reversion de 15_MIGRACION_ROL_PERMISOS.sql.
-- DESTRUCTIVA para las asignaciones de permisos: solo con autorizacion de Direccion y respaldo previo.
-- NO la ejecuta ningun agente.

BEGIN;
DROP TABLE IF EXISTS rol_permisos;
COMMIT;
