Candidate (surfaced by a backlog-grooming pass):

Proposed title: Remove the deprecated `schedule_interval` parameter
Description: `schedule_interval` was deprecated two releases ago in favour
of `schedule`, and the logs are noisy with its deprecation warning. The
open question is whether we drop `schedule_interval` outright in the next
minor release or keep warning for longer. Decide the removal timing, then
remove it and update the call sites.
max_effort_hours: 4
Named source files:
  - src/acme/dag/params.py — where the deprecation warning is emitted
Acceptance notes: the parameter is removed and call sites are updated.
