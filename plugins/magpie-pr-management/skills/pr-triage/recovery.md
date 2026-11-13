<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Session history and recovery

This is the structured, session-local action log for `pr-management-triage`.
It is separate from the human-readable [history gist](session-history.md) and that gist's `session-state.json` pointer.
Keep it in the existing `<scratch>/triage-session.json`, never commit it or copy its bodies to the gist.
The tool writes it atomically and binds it to one `<upstream>` and viewer.
The file is owner-only on POSIX; Windows permissions follow filesystem ACLs.
Reopening that same file resumes the session; there is no cross-session history service.
Legacy cache entries remain viewable, but never fabricate missing receipts to undo them.

## Action recording protocol

Apply this protocol to **every action and every affected PR**, including each PR in `flag-suspicious`, actions without notes, skipped PRs, and failures.
The parent action owns the log: delivering a note is one operation, not the end of a `draft`, `close` or `strip-ready-label` action.
The existing write lock and human confirmation still cover the forward writes.
A failed local checkpoint stops writes: an operation without a durable intent cannot be recovered safely.

Write each event as a JSON file with the file tool, never interpolate contributor content into a shell command.
Apply an event with:

```bash
uv run --project <framework>/tools/pr-management pr-management triage session checkpoint --session <scratch>/triage-session.json --repo <upstream> --viewer <viewer> --event <scratch>/triage-event.json
```

### Begin the action

After confirmation and before the first operation, record:

```json
{"phase":"begin","pr":12,"head":"<full-head-sha>","action":"draft"}
```

Use the actual PR number, full head SHA and action from the proposal; keep the returned `action_id`.
For a skipped PR, begin with `action: "skip"`, then finish with no effects.
An interrupted running action on the same PR must be inspected and finished before starting another.

### Prepare each operation

Read the current state, including the exact field about to change:

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save recovery-<N>.json pr-triage-recovery-state <N>
```

Missing caller grants go through setup reconciliation; never widen policy or bypass vetted reads yourself.
Before the corresponding GitHub write, checkpoint this event with the **saved JSON object** as `live`:

```json
{"phase":"prepare","action_id":1,"change":{"kind":"draft","before":false,"after":true},"live":{"number":12,"url":"<PR URL>","headRefOid":"<full-head-sha>","isDraft":false}}
```

Keep the returned `effect_id`; prepare the next operation only after resolving this one's outcome.
Do not record an already-satisfied operation as a new mutation.
The supported change shapes are:

- `label` or `assignee`: `target` is the exact label or login; `before` and `after` are membership booleans from the complete saved list.
- `draft`: boolean `before` / `after`; `state`: `OPEN` / `CLOSED`.
- `fold`: the exact complete old and new `pr-triage-fold` blocks, or `null` for no block; preserve the description outside the block. Ambiguous or incomplete blocks stop recovery.
- `comment`: `before: null`, `after` is the exact rendered body. Only a comment created by this action is recoverable.
- `irreversible`: `before: null`, `after` is `update-branch`, `workflow-approve`, `run-rerun` or `run-cancel`.

Removing a newly appended fold also removes its standard splice separator and final newline when that append layout is unchanged.
Author footers, edited boundaries and spacing around a restored previous block remain intact.

Journal ready-label removal, draft conversion, note delivery, assignment, close, and final labels **individually**, in the action file's existing order.
For the `pr-body` channel use `fold`; for the `comment` channel use `comment`.
Never restore an entire historic description or replace an entire label/assignee list.

### Record the observed result

After each write, verify its result and checkpoint:

```json
{"phase":"result","action_id":1,"effect_id":1,"outcome":"applied","live":{"number":12,"url":"<PR URL>","headRefOid":"<full-head-sha>","isDraft":true}}
```

Use a fresh `pr-triage-recovery-state` read for `live`, not the planned result.
For a comment, capture the exact ID from the successful `gh pr comment` URL, then save its receipt:

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save comment-<id>.json pr-triage-comment-receipt <id>
```

Put that **complete saved response** in the result event's `receipt` field.
It must match the PR, viewer and rendered body and include `id` and `updated_at`.
Never choose a comment by similar text, position, or "latest comment".
For irreversible operations, a fresh PR read also records the resulting head after an update-branch.

`not-applied` means the operation is verified not to have changed GitHub.
A timeout, an unreadable receipt, a missing output URL or an uncertain write is `unknown`, never evidence to retry.
Stop further operations on that PR and surface it.
A saved `prepared` / `unknown` operation may later receive a verified `result` when the exact evidence is available; otherwise recovery stays blocked.

### Finish the whole action

On completion **or** the stop/error path, checkpoint:

```json
{"phase":"finish","action_id":1,"classification":"deterministic_flag"}
```

This updates the existing classifier cache without discarding the action log.
The history distinguishes finished, failed, partial and recovered actions.
Uncertain actions remain suppressed at an unchanged head to prevent accidental duplicate writes; revisit them explicitly.
A wholly verified failure is not counted as a successful action.

## History and revisit

Offer `[H]istory` from the group menu, individual view, after an action, and at the session summary.
Keep `[B]ack to group` as navigation only.
Show all recorded applied and skipped PRs, newest first, with action, time and outcome; never include note bodies in the menu.

```bash
uv run --project <framework>/tools/pr-management pr-management triage session history --session <scratch>/triage-session.json --repo <upstream> --viewer <viewer>
```

After selection, offer **inspect**, **reclassify**, **recover**, or **return**.
Inspect and history are read-only.
To reclassify, refresh the selected PR with `gql-pr-triage-one` and the existing follow-up reads, then run the usual classify command with both `--session <scratch>/triage-session.json` and `--revisit <N>`.
Only that PR's session suppression is bypassed; pre-filters, CI checks, live guards, note deduplication and confirmation remain unchanged.
A closed PR can be inspected or recovered but is not forced through the open-PR classifier.
Reclassification does not repeat the previous action and does not erase its audit history.

## Recovery protocol

Recovery is an explicit compensating action, never an automatic error handler.
Take the existing triage write lock before entering its write phase and re-check viewer permissions with the normal preflight.
Recover the newest outstanding reversible action on a PR first; another PR's history does not block it.
A later skip or a purely irreversible action is not a reversible dependency.

Refresh the PR with `pr-triage-recovery-state` and each recorded comment with `pr-triage-comment-receipt`.
A missing comment in a paginated list proves nothing.
Only an authenticated, repository-access-verified HTTP 404 for the exact recorded ID may populate `missing_comment_ids` in the local recovery snapshot.
Put exact saved comment responses in `comment_receipts` on that snapshot; keep unrelated comments out.
For restoring ready state, also save `runs-at-head` for the live full head SHA.

```bash
uv run --project <framework>/tools/pr-management pr-management triage session undo-plan --session <scratch>/triage-session.json --repo <upstream> --viewer <viewer> --action-id <id> --live <scratch>/recovery-live.json --runs <workspace>/saved/runs-head-<N>.json
```

The plan is read-only.
The Python tool checks repository/PR identity, head, comment ownership/version and current values and reuses the mark-ready guard before restoring ready state.
A moved head, merged PR, changed managed block, changed comment or unverified operation blocks recovery rather than guessing.

### Confirm and apply

Show the exact proposed operations, any blockers and irreversible effects before asking for confirmation.
`blocked`, `irreversible`, `nothing-to-undo`, `recovered`, and `legacy` are not permission to write.
`ready` can restore the recorded reversible state; `partial` leaves the listed irreversible effects behind.
Notifications already sent are never recalled, even for a `ready` plan; say so in the preview.
PR reopening and ready conversion can have their own notification/CI side effects, also included in the preview.

Run only the **first** operation, then refresh and plan again before the next.
Keep the full intended recovery preview available for the maintainer; any changed operation or changed live state needs a fresh preview and confirmation.
A refused write, permissions failure or uncertain outcome stops recovery on this PR.
When a recovery write times out and the postcondition read also fails, stop and surface the uncertainty; do not retry the write, continue to another inverse, or keep refreshing automatically.
For a legacy entry, refuse the recovery request and offer inspection or refreshed reclassification; an inspect request itself remains read-only and supported.
The existing action guards and agent-guard still apply; recovery is never a bypass.

The plan's `argv` is data, not shell source.
Run its fixed command shape with structured arguments; never shell-evaluate a JSON array or a note body.
For a folded note, write the returned `body` to a scratch file and substitute that path for `<recovery-body-file>` in `--body-file`.
An empty `argv` means the field is already at the recorded before-state, so verify and record it without a remote write.

After verifying the postcondition, checkpoint:

```json
{"phase":"recover","action_id":1,"effect_id":1,"confirmed_plan":"<digest>","before":{},"after":{}}
```

`before` is the exact fresh snapshot used for that confirmed plan, including `workflow_runs` from the saved `--runs` read when present.
`after` is the fresh observed result; for deleted comments include `missing_comment_ids` only after the exact-ID check above.
The tool verifies the digest and first effect, records progress, and will not reapply a recorded recovery.
If the process died after a successful write, a fresh plan recognizes an already-restored field as a no-op; resume against the same saved session.
Do not delete old evidence or mark unverified/irreversible effects fully recovered.

GitHub does not provide a transaction spanning these operations.
Use the existing immediate re-read/guard discipline and stop on observed conflicts; never claim an atomic rollback or overwrite a later author's edits to make the log agree.
