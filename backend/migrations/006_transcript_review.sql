CREATE TABLE repoviva.transcript_reviews (
    turn_id TEXT PRIMARY KEY REFERENCES repoviva.turns(id) ON DELETE CASCADE,
    owner TEXT NOT NULL REFERENCES repoviva.users(id) ON DELETE CASCADE,
    receipt_id TEXT NOT NULL UNIQUE,
    transcript TEXT NOT NULL CHECK(length(transcript) BETWEEN 1 AND 4000),
    checks JSONB NOT NULL
);
ALTER TABLE repoviva.drafts ADD COLUMN speech_review JSONB;
