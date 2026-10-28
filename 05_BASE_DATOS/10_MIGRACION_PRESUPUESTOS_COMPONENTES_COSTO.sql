-- Almacena los presupuestos comerciales por componente para la comparación
-- con los costos reales de materiales, tiempos MES y servicios externos.
ALTER TABLE proyectos
    ADD COLUMN IF NOT EXISTS presupuestos_componentes JSONB NOT NULL DEFAULT '[]'::jsonb;
