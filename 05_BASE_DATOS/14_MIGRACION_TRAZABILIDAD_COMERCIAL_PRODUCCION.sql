-- IMPL-TRZ-001
-- Historial transaccional para cotizaciones, pedidos comerciales y OP.
-- Aplicar durante un despliegue planificado; la API no ejecuta este archivo.

BEGIN;

CREATE TABLE IF NOT EXISTS historial_acciones_documento (
    id_historial UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_entidad VARCHAR(30) NOT NULL,
    identificador_documento VARCHAR(50) NOT NULL,
    accion VARCHAR(60) NOT NULL,
    estado_anterior VARCHAR(50),
    estado_nuevo VARCHAR(50),
    pausa_tiempo_productivo BOOLEAN NOT NULL DEFAULT FALSE,
    motivo_observacion TEXT,
    usuario_responsable VARCHAR(100) NOT NULL,
    area_origen VARCHAR(50) NOT NULL DEFAULT 'VENTAS',
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_historial_acciones_documento_tipo_entidad
    ON historial_acciones_documento (tipo_entidad);

CREATE INDEX IF NOT EXISTS ix_historial_acciones_documento_identificador_documento
    ON historial_acciones_documento (identificador_documento);

COMMIT;
