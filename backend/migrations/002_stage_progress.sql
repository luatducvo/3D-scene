ALTER TABLE stage_runs ADD COLUMN IF NOT EXISTS started_at timestamptz;
ALTER TABLE stage_runs ADD COLUMN IF NOT EXISTS progress jsonb;
