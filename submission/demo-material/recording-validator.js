// Recording validation for a speaking-practice application.
// durationMs arrives from a timer in milliseconds.
// minSeconds is the minimum speaking time in seconds.
// A recording exactly at the minimum must be accepted.
// Non-numeric, missing, negative and invalid minimum values must be rejected.
function validateRecording(durationMs, minSeconds) {
  if (!Number.isFinite(durationMs) || !Number.isFinite(minSeconds)
      || durationMs < 0 || minSeconds <= 0) {
    return false;
  }
  const durationSeconds = durationMs / 1000;
  return durationSeconds >= minSeconds;
}

// Example: 30000 milliseconds is 30 seconds, so (30000, 30) returns true.
// Example: 29999 milliseconds is below the minimum, so (29999, 30) returns false.
// Example: a negative duration is invalid, so (-1000, 30) returns false.
