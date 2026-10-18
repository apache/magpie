<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `approve-workflow` — approve pending CI for a first-time contributor

**Inspect the diff first** — [`workflow-approval.md`](../workflow-approval.md) holds the protocol.
Only after the maintainer confirms the diff is not malicious, re-list the pending runs at action time (another maintainer may have approved since the sweep):

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save runs-head-<N>.json runs-at-head <head_sha>
uv run --project <framework>/tools/pr-management pr-management triage guard approve-workflow --pr <N> --head <head_sha> --saved-dir <workspace>/saved
```

- `proceed: true` → approve each id in `run_ids`:

  ```bash
  gh api -X POST repos/<upstream>/actions/runs/<run_id>/approve
  ```

- `proceed: false` with "already approved" → nothing to do; say so in one line, so the no-op is visible.

No note is posted: CI starting is what the contributor wanted.

## `flag-suspicious` — close all open PRs by the author

The heaviest action in the skill, for a diff with clear tampering indicators (secret exfiltration, CI pipeline changes, `.env` writes, curl-to-shell outside a legitimate tool update — the list is in [`workflow-approval.md`](../workflow-approval.md)).
The maintainer confirms **once per author**, then the whole set runs: this author's activity is being treated as a unit.

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save author-<login>.json gql-pr-triage-author <login>
```

For every open PR in that file: render the `suspicious-changes` note ([`deliver-note.md`](deliver-note.md) step 1, action `flag-suspicious`), then

```bash
gh pr comment <M> --repo <upstream> --body-file <body_file>
gh pr close <M> --repo <upstream>
gh pr edit <M> --repo <upstream> --add-label "suspicious changes detected"
```

The note is short and non-accusatory: the action is the message, the note is the receipt.
