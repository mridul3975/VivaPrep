CREATE TABLE repoviva.incident_labs (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    state JSONB NOT NULL,
    lease_token TEXT,
    busy_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX incident_labs_owner_date ON repoviva.incident_labs(owner, updated_at DESC);
CREATE TABLE repoviva.incident_usage (
    id TEXT PRIMARY KEY,
    -- Keep the anonymous shared-spend entry after guest expiry/account deletion.
    owner TEXT REFERENCES repoviva.users(id) ON DELETE SET NULL,
    period DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX incident_usage_day ON repoviva.incident_usage(period, owner);
