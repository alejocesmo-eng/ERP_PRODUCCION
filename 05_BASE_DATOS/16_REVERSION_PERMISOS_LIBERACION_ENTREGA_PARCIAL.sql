-- 16_REVERSION_PERMISOS_LIBERACION_ENTREGA_PARCIAL.sql
-- Reversion de 16_MIGRACION_PERMISOS_LIBERACION_ENTREGA_PARCIAL.sql.
-- Restaura PERM_OP_LIBERAR en PRODUCCION y retira los cambios de la migracion 16.
-- PERM_ENTREGA_PARCIAL_AUTORIZAR solo se borra de permisos si ya no tiene asignaciones.
-- Idempotente. Solo con autorizacion de Direccion y respaldo previo.
-- NO la ejecuta ningun agente sobre sgi_db.

BEGIN;

DELETE FROM rol_permisos
WHERE id_rol = 'ALMACEN' AND id_permiso = 'PERM_ENTREGA_PARCIAL_AUTORIZAR';

INSERT INTO rol_permisos (id_rol, id_permiso) VALUES
('PRODUCCION', 'PERM_OP_LIBERAR')
ON CONFLICT DO NOTHING;

DELETE FROM rol_permisos
WHERE id_rol = 'DISENO' AND id_permiso = 'PERM_OP_LIBERAR';

DELETE FROM permisos
WHERE id_permiso = 'PERM_ENTREGA_PARCIAL_AUTORIZAR'
  AND NOT EXISTS (
      SELECT 1 FROM rol_permisos WHERE id_permiso = 'PERM_ENTREGA_PARCIAL_AUTORIZAR'
  );

COMMIT;
