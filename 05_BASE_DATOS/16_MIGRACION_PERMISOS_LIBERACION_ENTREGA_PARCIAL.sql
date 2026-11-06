-- 16_MIGRACION_PERMISOS_LIBERACION_ENTREGA_PARCIAL.sql
-- Ajuste de permisos por rol:
--   * PERM_ENTREGA_PARCIAL_AUTORIZAR: nuevo permiso, asignado a ALMACEN (RN-OP-004B:
--     la entrega parcial solo procede si la autoriza el almacenista).
--   * PERM_OP_LIBERAR: pasa de PRODUCCION a DISENO (Diseno libera la OP tras el
--     Quality Gate RN-OP-004: plano PDF congelado y requisicion BOM).
-- No modifica 02_DATOS_INICIALES.sql: se aplica despues de sus secciones 1 a 3.
-- Idempotente, sin perdida de datos. NO la ejecuta ningun agente sobre sgi_db:
-- la aplica Direccion con respaldo previo de sgi_db y ensayo en BD de prueba.
-- Requiere 15_MIGRACION_ROL_PERMISOS.sql y los roles ALMACEN, PRODUCCION y DISENO.
-- Reversion: 16_REVERSION_PERMISOS_LIBERACION_ENTREGA_PARCIAL.sql

BEGIN;

INSERT INTO permisos (id_permiso, modulo, descripcion) VALUES
('PERM_ENTREGA_PARCIAL_AUTORIZAR', 'ALMACEN', 'Autorizar entrega parcial de material con registro de faltante, fecha estimada y razón (RN-OP-004B)')
ON CONFLICT (id_permiso) DO NOTHING;

INSERT INTO rol_permisos (id_rol, id_permiso) VALUES
('ALMACEN', 'PERM_ENTREGA_PARCIAL_AUTORIZAR')
ON CONFLICT DO NOTHING;

DELETE FROM rol_permisos
WHERE id_rol = 'PRODUCCION' AND id_permiso = 'PERM_OP_LIBERAR';

INSERT INTO rol_permisos (id_rol, id_permiso) VALUES
('DISENO', 'PERM_OP_LIBERAR')
ON CONFLICT DO NOTHING;

COMMIT;
