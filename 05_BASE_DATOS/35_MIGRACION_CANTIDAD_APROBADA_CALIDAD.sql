-- 35_MIGRACION_CANTIDAD_APROBADA_CALIDAD.sql
-- Cantidad aprobada por Calidad en cada inspección (decisión de Alejo, 2026-11-17).
--   * inspecciones_calidad.cantidad_aprobada: piezas que la inspección aprobó para despacho.
--   * inspecciones_calidad.tipo_aprobacion: INDIVIDUAL (una pieza) o LOTE (varias a la vez).
--   * Solo una inspección APROBADO_DESPACHO aprueba piezas; las de tratamiento o rechazo quedan en 0
--     y sin tipo. Una INDIVIDUAL aprueba exactamente una pieza.
--   * Las inspecciones anteriores quedan con 0: no se deduce cuántas piezas aprobaron.
-- La OP queda terminada cuando la suma de cantidad_aprobada iguala su cantidad (la aplicación lo
-- controla y notifica al Jefe de Producción).
-- Idempotente. NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Reversión: 35_REVERSION_CANTIDAD_APROBADA_CALIDAD.sql

BEGIN;

ALTER TABLE inspecciones_calidad
    ADD COLUMN IF NOT EXISTS cantidad_aprobada INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS tipo_aprobacion VARCHAR(10);

ALTER TABLE inspecciones_calidad DROP CONSTRAINT IF EXISTS ck_inspecciones_cantidad_aprobada;
ALTER TABLE inspecciones_calidad ADD CONSTRAINT ck_inspecciones_cantidad_aprobada
    CHECK (cantidad_aprobada >= 0);
-- Sin piezas: sin tipo. Con piezas: solo APROBADO_DESPACHO, con tipo, al menos una pieza, e
-- INDIVIDUAL exactamente una. tipo_aprobacion IS NOT NULL va explícito: una comparación con NULL da
-- NULL y un CHECK que da NULL se acepta.
ALTER TABLE inspecciones_calidad DROP CONSTRAINT IF EXISTS ck_inspecciones_tipo_aprobacion;
ALTER TABLE inspecciones_calidad ADD CONSTRAINT ck_inspecciones_tipo_aprobacion CHECK (
    (cantidad_aprobada = 0 AND tipo_aprobacion IS NULL)
    OR (resultado_inspeccion = 'APROBADO_DESPACHO'
        AND tipo_aprobacion IS NOT NULL
        AND cantidad_aprobada >= 1
        AND (tipo_aprobacion = 'LOTE' OR (tipo_aprobacion = 'INDIVIDUAL' AND cantidad_aprobada = 1)))
);

COMMENT ON COLUMN inspecciones_calidad.cantidad_aprobada IS
    'Piezas aprobadas para despacho en esta inspección. La suma por OP define sus piezas terminadas.';
COMMENT ON COLUMN inspecciones_calidad.tipo_aprobacion IS
    'INDIVIDUAL (una pieza) o LOTE; NULL si la inspección no aprobó piezas.';

COMMIT;
