<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**PR #5120 — "Cap scheduler DAG parsing loop"**
Author: `@dave-newcontrib`

Changed paths:
- `scheduler/job_runner.py`
- `scheduler/dag_processing/manager.py`

CODEOWNERS rules:
```
/scheduler/    @alice-maint
/api/          @frank-maint
```

Recent commit authors on the changed paths (last 30 commits per file):
- `@alice-maint` — 9 commits on `scheduler/job_runner.py` (committer: yes)
- `@bob-active` — 7 commits on `scheduler/job_runner.py`, 4 on `manager.py` (committer: no)
- `@dave-newcontrib` — 1 commit on `manager.py` (committer: no)

Already requested / already reviewing: (none)

PR body:
> Small fix to bound the parsing loop. Ran the scheduler tests locally.
