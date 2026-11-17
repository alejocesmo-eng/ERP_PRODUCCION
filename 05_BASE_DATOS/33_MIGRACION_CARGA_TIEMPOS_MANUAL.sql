-- 33_MIGRACION_CARGA_TIEMPOS_MANUAL.sql
-- Carga manual de tiempos desde la orden de fabricación (reglas/carga-tiempos-manual.md del
-- proyecto PRISMA).
--   * registro_tiempos_produccion: proceso de la ruta de la OP (id_operacion), setup en segundos
--     (opcional), fecha del trabajo, origen (CRONOMETRO o MANUAL) y quién registró. Las filas del
--     cronómetro quedan con origen CRONOMETRO y el resto de columnas nuevas en NULL.
--   * tiempos_manuales_correcciones: cada corrección de una fila manual con su motivo, los valores
--     anteriores y los nuevos. Las filas manuales no se borran.
--   * maquina_operarios: operarios asignados a cada máquina en Configuración.
-- Idempotente. NO la ejecuta ningún agente sobre sgi_db: la aplica Dirección con respaldo previo
-- de sgi_db y ensayo en BD de prueba.
-- Reversión: 33_REVERSION_CARGA_TIEMPOS_MANUAL.sql

BEGIN;

ALTER TABLE registro_tiempos_produccion
    ADD COLUMN IF NOT EXISTS id_operacion UUID REFERENCES operaciones_ot(id_operacion) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS segundos_setup INTEGER,
    ADD COLUMN IF NOT EXISTS fecha_trabajo DATE,
    ADD COLUMN IF NOT EXISTS origen VARCHAR(20) NOT NULL DEFAULT 'CRONOMETRO',
    ADD COLUMN IF NOT EXISTS registrado_por VARCHAR(100);

ALTER TABLE registro_tiempos_produccion DROP CONSTRAINT IF EXISTS ck_registro_tiempos_origen;
ALTER TABLE registro_tiempos_produccion ADD CONSTRAINT ck_registro_tiempos_origen
    CHECK (origen IN ('CRONOMETRO', 'MANUAL'));
ALTER TABLE registro_tiempos_produccion DROP CONSTRAINT IF EXISTS ck_registro_tiempos_setup;
ALTER TABLE registro_tiempos_produccion ADD CONSTRAINT ck_registro_tiempos_setup
    CHECK (segundos_setup IS NULL OR segundos_setup >= 0);
-- Una fila manual siempre dice proceso, fecha y quién la registró
ALTER TABLE registro_tiempos_produccion DROP CONSTRAINT IF EXISTS ck_registro_tiempos_manual;
ALTER TABLE registro_tiempos_produccion ADD CONSTRAINT ck_registro_tiempos_manual
    CHECK (origen <> 'MANUAL' OR (id_operacion IS NOT NULL AND fecha_trabajo IS NOT NULL AND registrado_por IS NOT NULL));

COMMENT ON COLUMN registro_tiempos_produccion.segundos_setup IS
    'Setup de una fila manual (opcional). En las filas del cronómetro el setup va en tipo_tiempo = SETUP.';
COMMENT ON COLUMN registro_tiempos_produccion.origen IS
    'CRONOMETRO (puesto CNC) o MANUAL (carga de tiempos desde la orden de fabricación).';

CREATE TABLE IF NOT EXISTS tiempos_manuales_correcciones (
    id_correccion BIGSERIAL PRIMARY KEY,
    id_registro INTEGER NOT NULL REFERENCES registro_tiempos_produccion(id) ON DELETE RESTRICT,
    valores_anteriores JSONB NOT NULL,
    valores_nuevos JSONB NOT NULL,
    motivo TEXT NOT NULL CHECK (length(btrim(motivo)) > 0),
    corregido_por VARCHAR(100) NOT NULL,
    corregido_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_tiempos_manuales_correcciones_registro
    ON tiempos_manuales_correcciones (id_registro);
COMMENT ON TABLE tiempos_manuales_correcciones IS
    'Correcciones de filas manuales de registro_tiempos_produccion, con motivo. Solo se agregan filas.';

CREATE TABLE IF NOT EXISTS maquina_operarios (
    id_equipo UUID NOT NULL REFERENCES equipos_planta(id_equipo) ON DELETE CASCADE,
    id_usuario UUID NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    asignado_por VARCHAR(100) NOT NULL,
    asignado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id_equipo, id_usuario)
);
COMMENT ON TABLE maquina_operarios IS
    'Operarios asignados a cada máquina (Configuración); la carga manual de tiempos los ofrece por máquina.';

COMMIT;
