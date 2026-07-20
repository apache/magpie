<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Review body (disposition: COMMENT):**

Approach looks reasonable; two observations inline that I'd like resolved
before merging — none blocking.

### Smaller observations

- `scheduler/job_runner.py:88` — the retry loop swallows
  `TimeoutError`; consider logging before continuing.

### Worth a second look from

This change touches `scheduler/`; folks with the most context here:

- `@alice-maint` — `CODEOWNERS` owner for `scheduler/` (committer)
- `@bob-active` — authored 6 of the last 20 commits under `scheduler/job_runner.py`

None of them have been notified — asking any of them for an
extra pass is the maintainer's call, and optional.

**Inline comments (1):**

1. `scheduler/job_runner.py:88` — Swallowed `TimeoutError` — log it
   before continuing so operators can see the retries.
