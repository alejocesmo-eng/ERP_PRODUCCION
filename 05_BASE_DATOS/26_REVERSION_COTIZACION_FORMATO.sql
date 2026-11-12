-- 26_REVERSION_COTIZACION_FORMATO.sql
-- Reversión de 26_MIGRACION_COTIZACION_FORMATO.sql: quita de cotizaciones las columnas moneda,
-- validez_oferta_dias, id_condicion_pago, termino_negociacion, referencia y observaciones, y
-- elimina la tabla condiciones_pago.
--   * SE PIERDEN los valores guardados en esas columnas y las condiciones de pago agregadas
--     después de la migración. Respaldar antes.
-- Idempotente. Solo con autorización de Dirección y respaldo previo.
-- NO la ejecuta ningún agente sobre sgi_db.

BEGIN;

ALTER TABLE cotizaciones DROP CONSTRAINT IF EXISTS fk_cotizaciones_condicion_pago;
ALTER TABLE cotizaciones DROP CONSTRAINT IF EXISTS ck_cotizaciones_moneda;
ALTER TABLE cotizaciones DROP CONSTRAINT IF EXISTS ck_cotizaciones_validez_oferta;
ALTER TABLE cotizaciones DROP COLUMN IF EXISTS observaciones;
ALTER TABLE cotizaciones DROP COLUMN IF EXISTS referencia;
ALTER TABLE cotizaciones DROP COLUMN IF EXISTS termino_negociacion;
ALTER TABLE cotizaciones DROP COLUMN IF EXISTS id_condicion_pago;
ALTER TABLE cotizaciones DROP COLUMN IF EXISTS validez_oferta_dias;
ALTER TABLE cotizaciones DROP COLUMN IF EXISTS moneda;

DROP TABLE IF EXISTS condiciones_pago;

COMMIT;
