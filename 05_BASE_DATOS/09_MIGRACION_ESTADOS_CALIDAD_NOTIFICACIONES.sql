-- Agrega estados de recepción de producto y notificación de despacho a las órdenes.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'estadoopenum') THEN
        ALTER TYPE estadoopenum ADD VALUE IF NOT EXISTS 'TERMINADA';
        ALTER TYPE estadoopenum ADD VALUE IF NOT EXISTS 'INSPECCION_CALIDAD';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tiponotificacionenum') THEN
        ALTER TYPE tiponotificacionenum ADD VALUE IF NOT EXISTS 'CALIDAD_APROBADA_DESPACHO';
    END IF;
END $$;
