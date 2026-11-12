-- Aggregate guest reservations remain separate from account ownership/upgrade.
CREATE TABLE repoviva.guest_events (
    id TEXT PRIMARY KEY,
    period DATE NOT NULL,
    bucket TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('sessions','questions','answers','transcriptions'))
);
CREATE INDEX guest_events_day ON repoviva.guest_events(period, action, bucket);
