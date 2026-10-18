<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `rebase` — update the PR branch with its base

Never on a conflicting PR: GitHub's update-branch side-merges the base and refuses on conflicts, returning 422.
Guard on the live state:

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save liveness-<N>.json gql-pr-liveness <N>
uv run --project <framework>/tools/pr-management pr-management triage guard rebase --pr <N> --head <head_sha> --saved-dir <workspace>/saved
```

- `proceed: true`:

  ```bash
  gh pr update-branch <N> --repo <upstream>
  ```

  A 422 despite the guard (GitHub recomputed mergeability in between): surface it and **do not retry**; route the PR to `draft` with the merge-conflicts violation.
- `proceed: false` → `draft` when conflicting, `retry` when mergeability is not computed yet.

No note is posted; the contributor sees the update on their PR.
