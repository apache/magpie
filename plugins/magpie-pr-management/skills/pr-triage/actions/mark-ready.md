<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `mark-ready` — add the ready-for-maintainer-review label

The label is the signal; no note is posted, except the ✅ flip when the PR carries a triage fold (`details.fold_flip`).

**Golden rule 1b: never mark ready while workflow approval is pending.** Read the live state, then guard:

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save liveness-<N>.json gql-pr-liveness <N>
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save runs-head-<N>.json runs-at-head <head_sha>
uv run --project <framework>/tools/pr-management pr-management triage guard mark-ready --pr <N> --head <head_sha> --saved-dir <workspace>/saved
```

- `proceed: true` → apply the label:

  ```bash
  gh pr edit <N> --repo <upstream> --add-label "ready for maintainer review"
  ```

  then, when `details.fold_flip` is set, deliver the ✅ note ([`deliver-note.md`](deliver-note.md), action `ready`), which also unassigns the author.
- `proceed: false` → do not label. Route by `reroute`: `pending_workflow_approval` → the [workflow-approval flow](approve-workflow.md); `draft` → the PR is conflicting, [row 9](../classifications/merge-conflict.md); `retry` → mergeability not computed yet, leave it for the next sweep; `reclassify` → the head moved, classify the PR again.

The agent-guard `mark-ready` guard enforces rule 1b again on the `gh pr edit --add-label` itself.
If the label does not exist on the repo, stop and surface it: this action's sole purpose is the label, so there is no graceful degradation.
