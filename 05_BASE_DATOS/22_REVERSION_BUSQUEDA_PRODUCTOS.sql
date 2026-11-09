-- 22_REVERSION_BUSQUEDA_PRODUCTOS.sql
-- Reversión de 22_MIGRACION_BUSQUEDA_PRODUCTOS.sql.
--   * Elimina los índices de trigramas y las funciones sgi_normalizar y sgi_normalizar_codigo.
--   * Las extensiones pg_trgm y unaccent se conservan: pueden usarlas otros objetos.
-- No toca datos. Idempotente. Solo con autorización de Dirección.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

DROP INDEX IF EXISTS ix_productos_descripcion_trgm;
DROP INDEX IF EXISTS ix_productos_codigo_rn_trgm;
DROP INDEX IF EXISTS ix_productos_codigo_anterior_trgm;
DROP FUNCTION IF EXISTS sgi_normalizar_codigo(TEXT);
DROP FUNCTION IF EXISTS sgi_normalizar(TEXT);

COMMIT;
