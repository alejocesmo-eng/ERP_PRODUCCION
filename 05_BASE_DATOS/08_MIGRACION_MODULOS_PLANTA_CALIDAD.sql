-- Apply once during a planned database deployment; the API does not execute this file.
ALTER TABLE centros_trabajo
    ADD COLUMN IF NOT EXISTS horas_capacidad_turno NUMERIC(5, 2) NOT NULL DEFAULT 8,
    ADD COLUMN IF NOT EXISTS equivalencia VARCHAR(50) NOT NULL DEFAULT 'GENERAL';

ALTER TABLE planos
    ADD COLUMN IF NOT EXISTS tiempo_estimado_setup_minutos DOUBLE PRECISION NOT NULL DEFAULT 20,
    ADD COLUMN IF NOT EXISTS tiempo_estimado_mecanizado_horas DOUBLE PRECISION;

ALTER TABLE ordenes_produccion
    ADD COLUMN IF NOT EXISTS tiempo_setup_estandar_minutos DOUBLE PRECISION NOT NULL DEFAULT 20;

ALTER TABLE registros_tiempo_operario
    ADD COLUMN IF NOT EXISTS fase_activa VARCHAR(20),
    ADD COLUMN IF NOT EXISTS justificacion_exceso TEXT,
    ADD COLUMN IF NOT EXISTS motivo_pausa VARCHAR(150);

ALTER TABLE no_conformidades
    ADD COLUMN IF NOT EXISTS causa_raiz VARCHAR(50),
    ADD COLUMN IF NOT EXISTS piezas_scrap INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS disposicion VARCHAR(50);

CREATE TABLE IF NOT EXISTS equipos_planta (
    id_equipo UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_maquina VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    centro_trabajo_asociado VARCHAR(50) REFERENCES centros_trabajo(codigo_centro) ON DELETE SET NULL,
    horas_uso_acumuladas NUMERIC(14, 2) NOT NULL DEFAULT 0,
    estado_maquina VARCHAR(30) NOT NULL DEFAULT 'OPERATIVA'
        CHECK (estado_maquina IN ('OPERATIVA', 'EN_MANTENIMIENTO', 'FUERA_DE_SERVICIO')),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ordenes_mantenimiento (
    id_otm UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_otm VARCHAR(50) NOT NULL UNIQUE,
    id_equipo UUID NOT NULL REFERENCES equipos_planta(id_equipo) ON DELETE RESTRICT,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('PREVENTIVO', 'CORRECTIVO')),
    descripcion_falla TEXT NOT NULL,
    repuestos_solicitados_almacen JSONB NOT NULL DEFAULT '[]'::jsonb,
    fecha_programada DATE,
    estado VARCHAR(20) NOT NULL DEFAULT 'ABIERTA'
        CHECK (estado IN ('ABIERTA', 'EN_PROCESO', 'CERRADA')),
    creada_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    cerrada_en TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS acciones_capa (
    id_capa UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_rnc UUID NOT NULL REFERENCES no_conformidades(id_nc) ON DELETE CASCADE,
    accion_correctiva TEXT NOT NULL,
    responsable_id UUID REFERENCES usuarios(id_usuario) ON DELETE SET NULL,
    fecha_compromiso DATE NOT NULL,
    estado_cierre VARCHAR(30) NOT NULL DEFAULT 'ABIERTA'
        CHECK (estado_cierre IN ('ABIERTA', 'CERRADA')),
    evidencia_cierre TEXT,
    cerrada_en TIMESTAMPTZ,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ordenes_mantenimiento_equipo ON ordenes_mantenimiento(id_equipo);
CREATE INDEX IF NOT EXISTS ix_acciones_capa_rnc ON acciones_capa(id_rnc);

ALTER TABLE sublotes_operacion
    ADD COLUMN IF NOT EXISTS prioridad_cola INTEGER NOT NULL DEFAULT 0;

ALTER TABLE inspecciones_calidad
    ADD COLUMN IF NOT EXISTS proveedor_tratamiento VARCHAR(150),
    ADD COLUMN IF NOT EXISTS costo_tratamiento NUMERIC(14, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS mediciones_dimensionales JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS informe_tratamiento_html TEXT;
