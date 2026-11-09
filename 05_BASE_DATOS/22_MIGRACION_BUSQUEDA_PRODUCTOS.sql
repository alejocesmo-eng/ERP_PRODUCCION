-- 22_MIGRACION_BUSQUEDA_PRODUCTOS.sql
-- Búsqueda de productos tolerante a mayúsculas, acentos y errores de tipeo
-- (GET /api/v1/maestros/productos).
--   * Extensiones pg_trgm (similitud por trigramas) y unaccent (quita acentos).
--     Ambas son trusted desde PostgreSQL 13: las crea el dueño de la base.
--   * sgi_normalizar(texto): minúsculas, sin acentos, espacios colapsados.
--   * sgi_normalizar_codigo(texto): sgi_normalizar sin nada que no sea letra o dígito
--     ("RN-088-001", "rn088001" y "Rn 088 001" quedan iguales).
--     Las dos son IMMUTABLE (unaccent con diccionario explícito) para poder indexarlas.
--   * Índices GIN gin_trgm_ops sobre descripcion, codigo_rn y codigo_anterior normalizados.
-- Idempotente y sin pérdida de datos.
-- NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo de sgi_db
-- y ensayo en BD de prueba.
-- Requiere 18_MIGRACION_PRODUCTOS_RN.sql.
-- Reversión: 22_REVERSION_BUSQUEDA_PRODUCTOS.sql

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE OR REPLACE FUNCTION sgi_normalizar(texto TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
    SELECT regexp_replace(lower(public.unaccent('public.unaccent'::regdictionary, btrim(coalesce(texto, '')))), '\s+', ' ', 'g');
$$;

CREATE OR REPLACE FUNCTION sgi_normalizar_codigo(texto TEXT)
RETURNS TEXT
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
    -- Calificada con public: los índices la evalúan con search_path vacío (pg_restore)
    SELECT regexp_replace(public.sgi_normalizar(texto), '[^a-z0-9]', '', 'g');
$$;

CREATE INDEX IF NOT EXISTS ix_productos_descripcion_trgm
    ON productos USING gin (sgi_normalizar(descripcion) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_productos_codigo_rn_trgm
    ON productos USING gin (sgi_normalizar_codigo(codigo_rn) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_productos_codigo_anterior_trgm
    ON productos USING gin (sgi_normalizar_codigo(codigo_anterior) gin_trgm_ops);

COMMIT;
