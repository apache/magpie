Candidate (surfaced by a backlog-grooming pass):

Proposed title: Reject non-positive timeout values in config
Description: The config loader currently accepts a negative or zero
`timeout`, which later causes the worker to hang. It should raise a clear
validation error at load time when `timeout <= 0`.
max_effort_hours: 4
Named source files:
  - none provided — the grooming note did not say where the config loader lives
Acceptance notes: loading a config with timeout <= 0 raises a validation
error that names the field; valid configs are unaffected; a test covers
both.
