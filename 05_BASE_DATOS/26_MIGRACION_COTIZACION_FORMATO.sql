-- 26_MIGRACION_COTIZACION_FORMATO.sql
-- Formato aprobado de la cotización (reglas/cotizacion-formato-y-borrador.md, aprobada por
-- Alejo el 2026-11-11):
--   * Tabla maestra condiciones_pago con la lista inicial del documento: Anticipado; 8, 30, 60 y
--     120 días; 50% Anticipo - 50% Saldo a 30 días; Contra documentos de embarque.
--   * Columnas nuevas en cotizaciones:
--       moneda               COP por defecto, USD opcional por cotización
--       validez_oferta_dias  validez de la oferta, editable por cotización
--       id_condicion_pago    condición de pago desde condiciones_pago
--       termino_negociacion  por defecto "Puesto en planta HD"
--       referencia           referencia global de la oferta
--       observaciones        observaciones de los términos comerciales
--     Las cotizaciones existentes quedan en COP, sin condición de pago ni validez (NULL).
-- Solo agrega: no borra ni cambia datos existentes. Idempotente.
-- NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo de sgi_db
-- y ensayo en BD de prueba.
-- Reversión: 26_REVERSION_COTIZACION_FORMATO.sql

BEGIN;

CREATE TABLE IF NOT EXISTS condiciones_pago (
    id_condicion_pago SERIAL PRIMARY KEY,
    codigo            VARCHAR(30)  NOT NULL,
    descripcion       VARCHAR(100) NOT NULL,
    orden             INTEGER      NOT NULL DEFAULT 0,
    activo            BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_condiciones_pago_codigo UNIQUE (codigo)
);
COMMENT ON TABLE condiciones_pago IS
    'Condiciones de pago de la cotización (datos maestros). Migración 26.';

INSERT INTO condiciones_pago (codigo, descripcion, orden) VALUES
    ('ANTICIPADO', 'Anticipado', 10),
    ('8_DIAS', '8 días', 20),
    ('30_DIAS', '30 días', 30),
    ('60_DIAS', '60 días', 40),
    ('120_DIAS', '120 días', 50),
    ('50_ANTICIPO_50_30_DIAS', '50% Anticipo - 50% Saldo a 30 días', 60),
    ('CONTRA_DOCUMENTOS_EMBARQUE', 'Contra documentos de embarque', 70)
ON CONFLICT (codigo) DO NOTHING;

ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS moneda VARCHAR(3) NOT NULL DEFAULT 'COP';
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS validez_oferta_dias INTEGER;
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS id_condicion_pago INTEGER;
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS termino_negociacion VARCHAR(100) DEFAULT 'Puesto en planta HD';
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS referencia VARCHAR(150);
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS observaciones TEXT;

ALTER TABLE cotizaciones DROP CONSTRAINT IF EXISTS ck_cotizaciones_moneda;
ALTER TABLE cotizaciones ADD CONSTRAINT ck_cotizaciones_moneda CHECK (moneda IN ('COP', 'USD'));
ALTER TABLE cotizaciones DROP CONSTRAINT IF EXISTS ck_cotizaciones_validez_oferta;
ALTER TABLE cotizaciones ADD CONSTRAINT ck_cotizaciones_validez_oferta
    CHECK (validez_oferta_dias IS NULL OR validez_oferta_dias > 0);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.cotizaciones'::regclass AND conname = 'fk_cotizaciones_condicion_pago'
    ) THEN
        ALTER TABLE cotizaciones ADD CONSTRAINT fk_cotizaciones_condicion_pago
            FOREIGN KEY (id_condicion_pago) REFERENCES condiciones_pago (id_condicion_pago) ON DELETE RESTRICT;
    END IF;
END $$;

COMMIT;
