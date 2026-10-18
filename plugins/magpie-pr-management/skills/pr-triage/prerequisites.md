<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Prerequisites

Before running any PR mutation the skill must confirm the
maintainer has the access needed to carry it out. A failure in
any of the blocking checks below is a **stop** — surface it to
the maintainer with the exact remediation command and do *not*
proceed to fetch PR data.

Keep this check cheap: a pre-flight that itself costs 5 GraphQL
calls defeats the whole rate-limit strategy of this skill.

---

## Step 0 — Pre-flight check

Run the checks in [`prerequisites.md`](prerequisites.md) before
touching any PR:

1. `gh auth status` must return authenticated, and the active
   account must be a collaborator on `<repo>`. (Without
   collaborator access the mutations below — label-add,
   convert-to-draft, close, approve-workflow — will silently
   fail.)
2. The expected labels (`ready for maintainer review`,
   `closed because of multiple quality violations`,
   `suspicious changes detected`) must exist on `<repo>`;
   missing ones degrade to "post the comment, skip the label"
   with a warning.
3. Note the session cache at
   `<scratch>/triage-session.json` (see
   [`triage session record`](../../../../tools/pr-management/README.md#triage-session-record--triage-session-summary)).

A failure of step 1 is a **stop** — surface it and ask the
maintainer to run `gh auth login`. Steps 2 and 3 degrade
gracefully with warnings.

## 1. `gh` CLI authenticated (blocking)

```bash
gh auth status
```

Pass condition: exit code `0` and the output lists an account
with `api.github.com` scope covering `repo` and `workflow`.
Capture the active login from the output for later — it is the
viewer login referenced throughout the other files.

On failure, stop and say:

> `gh` is not authenticated. Run `gh auth login` with SSH or
> HTTPS and the `repo, workflow` scopes, then re-invoke the
> skill.

This is the only check that *must* go through `gh auth status` —
do not try to parse tokens from the environment. A maintainer
running through `gh` also gets the TTY login prompt handled for
them when the token expires.

### `gist` scope (non-blocking)

[Step 6b](session-history.md#step-6b--propose-session-history-gist-update)
(session-history gist persistence) needs the `gist` scope on
the `gh` token. If the scope is missing, the rest of the skill
runs unchanged; only Step 6b is skipped with a one-line notice.

To add the scope:

```bash
gh auth refresh -s gist
```

`gist` is a non-blocking prerequisite by design — first-time
adopters can run the skill end-to-end without ever creating a
history gist, and only opt in once they want the cross-session
calibration view.

---

## 1b. A save directory for the sweep (blocking, one-time)

Every read in this skill is saved with `vetted-op-read --save`, which writes only into a `saved/` directory under the vetted-ops workspace that holds a `.vetted-ops-save` marker — it creates neither, so it can never write where you could not.
If the first save refuses with *"holds no .vetted-ops-save file"* or *"is unusable"*, ask the maintainer to create it once (the workspace path is in the refusal):

```bash
mkdir -m 700 <workspace>/saved && touch <workspace>/saved/.vetted-ops-save
```

---

## 2–3. Viewer permission and the triage labels

One read, one check:

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage --save preflight.json gql-pr-triage-preflight
uv run --project <framework>/tools/pr-management pr-management triage preflight --saved-dir <workspace>/saved
```

- `ok: false` → stop and show `blocking` (the viewer has read access or none: *"ask to be added as a collaborator"* or *"check you're logged in as the right account"*).
- `warnings` → show each once. `TRIAGE` permission is enough for labels, closes and drafts but not for workflow approval, which then falls back to "ask a WRITE-level maintainer".
- `missing_labels` → the action that would add one posts its note and skips the label. The skill **does not** create labels — that is a repository-admin decision. A missing ready label means `mark-ready` cannot run at all. On `<upstream>` a missing label is itself an anomaly worth flagging.

The labels checked are the configured ones (`ready_for_maintainer_review`, `quality_violations_close`, `suspicious_changes`).

---

## 4. Session cache

The session cache is `<scratch>/triage-session.json`, written by `triage session record` and read by `triage classify --session`.
A PR recorded with a terminal action and an unchanged head is skipped for the rest of the session; a new push produces a new head and re-classifies it.
A missing file is an empty session; `clear-cache` deletes it.
The cache skips *classification*, never *verification*: every mutation still guards on fresh reads.

---

## 5. `gh` subcommand availability (non-blocking)

Verify that the `gh` install supports the subcommands the skill
uses:

```bash
gh run --help   # needs `approve` and `rerun`
gh pr --help    # needs `comment`, `close`, `edit`, `ready`, `update-branch`
gh api --help
```

Any missing subcommand means an older `gh` — warn and skip the
affected action (most commonly `gh pr update-branch`, which
landed in `gh` 2.20+; earlier versions need the REST call from
[`actions/rebase.md`](actions/rebase.md)).

---

## 6. Typed-decision shadow pre-filter prerequisites (when enabled)

When `enable_typed_decision_prefilter: true` is configured in `<project-config>/pr-management-config.md` or overrides:

1. **Third-party endpoint:** The provider calls `https://api.typesafe.ai/v1/systemone` to classify PR states.
2. **Credentials:** `TYPESAFE_API_KEY` (or fallback `JEV_API_KEY`) environment variable or `~/.config/apache-magpie/typesafe.key` must be present.
3. **Privacy-LLM opt-in:** Requires an approved entry in `<project-config>/privacy-llm.md` with a non-empty `Data-residency contract` and valid maintainer `Approved-by` sign-offs.
4. **Prompt injection defense:** Contributor title, body, and commits are enclosed in `<untrusted-external-data>` as data only.
5. **Fail-open contract:** If any credential, module import, or privacy approval is missing, or on network error/timeout, the pre-filter logs `fell_through` and triage proceeds normally without interrupting the maintainer.

---

## What to do when a prerequisite fails mid-session

If step 1 or 2 passes at start but a later mutation fails with a
permission error — e.g. the viewer's token expired, or they got
removed from the repo mid-sweep — stop the current group, tell
the maintainer, and print the summary for what *was* done this
session. Do not keep trying; retries on a permissions error
burn GraphQL budget without progress.

---

## Adopter overrides

Before running the default behaviour documented
below, this skill consults
[`.apache-magpie-local/pr-management-triage.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/pr-management-triage.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo if it exists, and applies any
agent-readable overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)
for the contract — what overrides may contain, hard
rules, the reconciliation flow on framework upgrade,
upstreaming guidance.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-magpie/`. Local modifications
go in the override file. Framework changes go via PR
to `apache/magpie`.

---
