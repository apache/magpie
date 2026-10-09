<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `promote-bot-draft` — flip a bot draft to ready and label it

Golden rule 1b applies: guard on the head's runs first.

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save liveness-<N>.json gql-pr-liveness <N>
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save runs-head-<N>.json runs-at-head <head_sha>
uv run --project <framework>/tools/pr-management pr-management triage guard promote-bot-draft --pr <N> --head <head_sha> --saved-dir <workspace>/saved
```

- `proceed: true`:

  ```bash
  gh pr ready <N> --repo <upstream>
  gh pr edit <N> --repo <upstream> --add-label "ready for maintainer review"
  ```

  Order matters: ready first, then the label. If `gh pr ready` fails (no longer a draft, closed, the head moved), stop before labelling; the next run re-classifies it. If only the label fails, do not roll back — log it for the summary.
- `proceed: false` with `reroute: pending_workflow_approval` → hand it to the [workflow-approval flow](approve-workflow.md) instead of promoting blind.

No note is posted: a contributor-facing footer is misdirected at a bot.
