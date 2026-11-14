<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `approve-workflow` — approve pending CI for a first-time contributor

Use the [action recording protocol](../recovery.md#action-recording-protocol) around every operation below; the parent action finishes only after all operations or its stop/error path.

**Inspect the diff first** — [`workflow-approval.md`](../workflow-approval.md) holds the protocol.
Only after the maintainer confirms the diff is not malicious, re-list the pending runs at action time (another maintainer may have approved since the sweep) and refresh the liveness read (`guard` checks the head against any saved copy, so a stale one reports a head move that never happened):

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save runs-head-<N>.json runs-at-head <head_sha>
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save liveness-<N>.json gql-pr-liveness <N>
uv run --project <framework>/tools/pr-management pr-management triage guard approve-workflow --pr <N> --head <head_sha> --saved-dir <workspace>/saved
```

- `proceed: true` → approve each id in `run_ids`:

  ```bash
  gh api -X POST repos/<upstream>/actions/runs/<run_id>/approve
  ```

  GitHub accepts this only for first-time contributors' runs. A run that answers HTTP 403 *"This workflow run is not waiting for approval"* needs a full re-run instead; one that then answers *"already running"* is done:

  ```bash
  gh run rerun <run_id> --repo <upstream>
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
