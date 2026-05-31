Candidate (surfaced by a backlog-grooming pass):

Proposed title: Make the scheduler event-driven
Description: The scheduler currently polls the database on a fixed
interval. We want to re-architect it to react to events (new task,
completed task, config change) instead of polling, across the scheduler,
the executor interface, and the database notification layer. This touches
many modules and needs new integration tests throughout.
max_effort_hours: 4
Named source files:
  - the entire scheduler package, plus parts of the executor and db layers
Acceptance notes: the scheduler no longer polls; scheduling latency drops;
all existing behaviour is preserved.
