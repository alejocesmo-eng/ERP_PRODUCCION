-- Instrucción técnica de Ingeniería anexa a la OP (tolerancias, sobremedidas,
-- notas para compras o taller). Se muestra en el expediente y en la tablet MES.
ALTER TABLE planos
    ADD COLUMN IF NOT EXISTS observaciones_tecnicas TEXT NULL;
