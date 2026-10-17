-- The version (Job id) whose result folder DATA_DIR/scenes/{id}/{version} the Scene serves (ADR-0006).
ALTER TABLE scenes ADD COLUMN IF NOT EXISTS publication text;
