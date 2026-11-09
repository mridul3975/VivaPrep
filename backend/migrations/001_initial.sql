CREATE TABLE repoviva.users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_sign_in TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE repoviva.login_sessions (
    token_hash TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    expires_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX login_sessions_expiry ON repoviva.login_sessions(expires_at);
CREATE TABLE repoviva.sources (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    document JSONB NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    next_snippet INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_active_source_per_student ON repoviva.sources(owner) WHERE active;
CREATE TABLE repoviva.practice_sets (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES repoviva.sources(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX practice_sets_owner_date ON repoviva.practice_sets(owner, created_at DESC);
CREATE TABLE repoviva.turns (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    practice_id TEXT NOT NULL REFERENCES repoviva.practice_sets(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    payload JSONB NOT NULL,
    busy_until TIMESTAMPTZ,
    lease_token TEXT,
    UNIQUE (practice_id, position)
);
CREATE INDEX turns_owner ON repoviva.turns(owner);
CREATE TABLE repoviva.attempts (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    turn_id TEXT NOT NULL REFERENCES repoviva.turns(id) ON DELETE CASCADE,
    answer TEXT NOT NULL CHECK (length(answer) BETWEEN 1 AND 4000),
    feedback JSONB NOT NULL,
    earned NUMERIC NOT NULL,
    possible NUMERIC NOT NULL,
    percentage NUMERIC CHECK (percentage BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX attempts_turn_date ON repoviva.attempts(turn_id, created_at DESC);
