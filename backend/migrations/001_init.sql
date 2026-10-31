CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS scenes(id uuid PRIMARY KEY,name text NOT NULL,status text NOT NULL DEFAULT 'created',created_at timestamptz NOT NULL DEFAULT now(),failure jsonb,publication text);
CREATE TABLE IF NOT EXISTS jobs(id uuid PRIMARY KEY,scene_id uuid NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,status text NOT NULL DEFAULT 'queued',created_at timestamptz NOT NULL DEFAULT now(),started_at timestamptz,finished_at timestamptz,error jsonb);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_one_active ON jobs(scene_id) WHERE status IN ('queued','running');
CREATE TABLE IF NOT EXISTS stage_runs(scene_id uuid NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,stage text NOT NULL,algorithm text NOT NULL,status text NOT NULL,manifest jsonb,error jsonb,updated_at timestamptz NOT NULL DEFAULT now(),started_at timestamptz,progress jsonb,PRIMARY KEY(scene_id,stage));
CREATE TABLE IF NOT EXISTS objects(scene_id uuid NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,id text NOT NULL,label text NOT NULL,box jsonb NOT NULL,best_views jsonb NOT NULL DEFAULT '[]',embedding vector(1024),description text NOT NULL,PRIMARY KEY(scene_id,id));
CREATE INDEX IF NOT EXISTS objects_embedding_idx ON objects USING hnsw(embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS scene_events(id bigserial PRIMARY KEY,scene_id uuid NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,event text NOT NULL,data jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
