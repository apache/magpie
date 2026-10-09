<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `rerun` — rerun the failed CI jobs

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save runs-head-<N>.json runs-at-head <head_sha>
uv run --project <framework>/tools/pr-management pr-management triage guard rerun --pr <N> --head <head_sha> --saved-dir <workspace>/saved
```

- `rerun_failed` → rerun only the failed jobs of each run (plain `gh run rerun` reruns the whole workflow — expensive and unnecessary):

  ```bash
  gh run rerun <run_id> --repo <upstream> --failed
  ```

- `cancel_and_rerun` → nothing completed-and-failed to rerun; restart the in-progress runs, which discards their current work:

  ```bash
  gh run cancel <run_id> --repo <upstream>
  gh run rerun <run_id> --repo <upstream>
  ```

- `proceed: false` → no runs at the head: tell the maintainer the PR may need a push or a rebase to re-trigger CI, and propose [`rebase`](rebase.md) next time.

No note is posted.
