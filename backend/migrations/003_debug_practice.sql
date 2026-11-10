CREATE TABLE repoviva.debug_runs (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    source_id TEXT REFERENCES repoviva.sources(id) ON DELETE CASCADE,
    scenario_id TEXT NOT NULL,
    state JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX debug_runs_owner_date ON repoviva.debug_runs(owner, updated_at DESC);
