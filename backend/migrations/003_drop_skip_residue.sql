-- Every Job runs all Stages (ADR-0005): no Stage is skipped, so nothing compares configuration hashes.
UPDATE stage_runs SET status='done' WHERE status='skipped';
ALTER TABLE stage_runs DROP COLUMN IF EXISTS config_hash;
ALTER TABLE jobs DROP COLUMN IF EXISTS from_stage;
