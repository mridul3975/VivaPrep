ALTER TABLE repoviva.users ADD COLUMN profile JSONB NOT NULL DEFAULT '{}';
ALTER TABLE repoviva.sources ADD COLUMN last_opened_at TIMESTAMPTZ NOT NULL DEFAULT now();
UPDATE repoviva.sources SET last_opened_at=created_at;
ALTER TABLE repoviva.sources ADD COLUMN selected_practice_id TEXT REFERENCES repoviva.practice_sets(id) ON DELETE SET NULL;
ALTER TABLE repoviva.practice_sets ADD COLUMN last_turn_id TEXT;
CREATE INDEX sources_owner_fingerprint ON repoviva.sources(owner, (document->>'revision'), (document->>'kind'));
CREATE TABLE repoviva.drafts (
    turn_id TEXT PRIMARY KEY REFERENCES repoviva.turns(id) ON DELETE CASCADE,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    answer TEXT NOT NULL CHECK(length(answer)<=4000),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE repoviva.api_usage (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK(action IN ('questions','answers','transcriptions')),
    period DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX api_usage_owner_day ON repoviva.api_usage(owner, period, action);
