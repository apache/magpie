<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**PR #5123 — "Refactor executor task-state polling"**
Author: `@dave-newcontrib`

Changed paths:
- `executor/base_executor.py`

CODEOWNERS rules:
```
/executor/     @alice-maint @eve-maint
```

Recent commit authors on the changed paths (last 30 commits per file):
- `@alice-maint` — 6 commits on `executor/base_executor.py` (committer: yes)
- `@eve-maint` — 5 commits on `executor/base_executor.py` (committer: yes)
- `@grace-active` — 8 commits on `executor/base_executor.py` (committer: no)

Already requested / already reviewing:
- `@alice-maint` (already submitted a review on this PR)

PR body:
> Pulls the polling loop into a helper. No behaviour change intended.
