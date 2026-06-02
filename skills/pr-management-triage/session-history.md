<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Session-history gist

Step 6b of [`SKILL.md`](SKILL.md) proposes appending each
triage session to a long-lived, **private** GitHub gist scoped
to one adopter repo. This file is the contract for that gist:
location of the local state anchor, content schema, create vs.
update logic, and the maintainer-confirmation flow.

Why this exists:

- A single triage session shows what happened *this morning*.
  A multi-session history shows *which rules consistently fire
  with no override*, *which rules the maintainer routinely
  rewrites*, and *which heuristics need recalibration*.
- That second view is the input signal for which actions can be
  promoted from "human-confirmed" to "automated" in future
  framework revisions. Without persistence, every session's
  data is lost the moment the skill exits.
- The gist is the simplest viable backend: free, private,
  attributed to the maintainer's GitHub account, accessible
  from any machine the maintainer logs into.

---

## Local state file

**Path.** `<adopter-repo-root>/.apache-magpie.session-state.json`.

**Status.** Gitignored. The adopter repo's snapshot mechanism
already gitignores `.apache-magpie.local.lock` next to the
session-state file; the same `.gitignore` entry covers both.

**Schema.**

```json
{
  "pr-management-triage": {
    "history_gist_id":  "c419315f2ac318f74a3e63134757723a",
    "history_gist_url": "https://gist.github.com/<viewer>/c419315f2ac318f74a3e63134757723a",
    "history_filename": "triage-history.md"
  }
}
```

The top-level key is per-skill; other skills (e.g.
`pr-management-stats`) may add their own keys later. The
schema is deliberately additive — never remove or rename
fields, only add.

**Reads.** Step 6b reads the file at session entry. Missing
file or missing `pr-management-triage.history_gist_id` is
treated as "first run" — the create path fires.

**Writes.** Step 6b writes the file once, after a successful
gist create (the update path doesn't change the URL). Atomic
write: write to a temp file alongside, `fsync`, rename. Never
write a partial JSON file — a malformed state file blocks
future runs.

---

## Required `gh` scope

The token used by `gh` must carry the `gist` OAuth scope. Step
6b's pre-flight check:

```bash
scopes=$(gh auth status 2>&1 | sed -n 's/.*Token scopes: //p' | head -1)
case "$scopes" in
  *gist*) ;;
  *) echo "history-gist: gh token lacks 'gist' scope — skipping. Re-run \`gh auth refresh -s gist\` to enable." >&2; exit 0 ;;
esac
```

A missing scope is **not** an error — Step 6b is opt-in and
soft-fails to a one-line notice so the rest of the session
summary still prints. Document the re-auth command on the
notice line so the maintainer can fix it before the next run.

See [`prerequisites.md#gh-scopes`](prerequisites.md) for the
canonical scope list.

---

## Gist filename and structure

**Filename.** `triage-history.md` (Markdown, single file).

**Description.** `PR Triage History — <repo> — maintained by <viewer>`.

**Visibility.** Always created with the default-secret flag (no
`--public`). The skill MUST refuse to write to a public gist
even if pointed at one — if the gist URL in the local state
file resolves to a public gist via
`gh api gists/<id> --jq .public`, the skill aborts Step 6b with
a one-line notice and asks the maintainer to delete the public
gist and re-run.

**Content layout.** Reverse chronological — newest session at
the top. Each session is a `## <YYYY-MM-DD> — <repo>` heading,
collapsible by GitHub's gist renderer.

Session block template (Markdown):

```markdown
## <YYYY-MM-DD HH:MM UTC> — <repo>

**Maintainer:** @<viewer>  ·  **Agent:** <agent-name-and-version>  ·  **Session length:** Nm

### Action counts

| Action | Count | PR numbers |
|---|---|---|
| `mark-ready` | N | #..., #..., ... |
| `approve-workflow` | N | #..., #..., ... |
| `draft` | N | #... |
| `comment` | N | #... |
| `rebase` | N | #... |
| `rerun` | N | #... |
| `ping` | N | #... |
| `request-author-confirmation` | N | #... |
| `close` (deterministic_flag) | N | #... |
| `close` (stale-sweep 1a) | N | #... |
| `close` (stale-sweep 1b) | N | #... |
| `draft` (stale-sweep 2) | N | #... |
| `draft` (stale-sweep 3) | N | #... |
| `strip-ready-label` (stale-sweep 4a) | N | #... |
| `close` (stale-sweep 4b) | N | #... |
| `ping` (stale-sweep 5) | N | #... |
| `promote-bot-draft` (Step 0.5) | N | #... |
| `flag-suspicious` | N | #... |

### Pre-filter skips

| Filter | Count |
|---|---|
| F1 collaborator/member/owner | N |
| F2 bot | N |
| F3 active draft (≤14d) | N |
| F4 already-ready-no-regression | N |
| F5a recent maintainer comment | N |
| F5b unanswered maintainer-to-maintainer ping | N |
| F6 maintainer co-drafted | N |

### Decision-rule signal

One row per decision-table rule that fired this session. The
"overrides" column counts cases where the maintainer rejected
the proposed action and picked something else (skip, different
verb, batch deferral). High override rates are the calibration
signal.

| Rule | Fired | Auto-confirmed | Maintainer overrode | Override notes |
|---|---|---|---|---|
| Row 1 (`pending_workflow_approval`) | N | N | N | One-line per override |
| Row 2 (`stale_copilot_review`) | N | N | N | |
| Row 9 (CONFLICTING → draft) | N | N | N | |
| ... | | | | |

### Per-PR override notes

PRs where the maintainer picked a non-default action are listed
here so the framework-maintenance loop can review them:

- #<NN> — rule said `<X>`, maintainer chose `<Y>` because <reason>.
- ...

### Deferrals

- Stale-sweep 1b candidates left untouched: N (member-authored)
- Stale-sweep 2 candidates left untouched: N (member-authored)
- Row 22 (`unclassified` — rollup not settled): N PRs to retry next sweep

---
```

The schema is intentionally flat-table heavy and free of
free-form prose between sections. The next session's append
operation is a simple "insert this block at line 1 of the gist
body, after the H1 if present". A more nested layout would
require parsing on every update; the flat-table schema does
not.

---

## Create vs. update logic

```text
state := read_local_state_file()
if state.history_gist_id is null:
    # First-run path — create
    body := render_session_block() + intro_header()
    confirm with maintainer (show first 50 lines + URL it will live at)
    on confirm:
      url := gh gist create --desc "<desc>" - < /tmp/body.md
      write_local_state_file(url, gist_id_from(url))
else:
    # Steady-state path — update
    existing := gh gist view <gist_id> --filename triage-history.md
    new_body := render_session_block() + "\n\n---\n\n" + existing
    confirm with maintainer (show first 50 lines of *new* block + gist URL)
    on confirm:
      gh gist edit <gist_id> --filename triage-history.md - < /tmp/new_body.md
```

**First-run preview.** The maintainer sees:

```text
About to CREATE a private gist on your account:
  Description: PR Triage History — <repo> — maintained by @<viewer>
  Filename:    triage-history.md
  Visibility:  secret (default; not public)
  Length:      <N> lines
  Local state will be written to: .apache-magpie.session-state.json

First 50 lines:
─────────────────────────────────────────────────────
<...>
─────────────────────────────────────────────────────

[Y] create  [N] skip Step 6b for this run  [E] edit before posting
```

**Steady-state preview.** Show the new block being **prepended**:

```text
About to UPDATE existing gist:
  URL:      <history_gist_url>
  Length:   appending +<N> lines (new total: <M>)

First 50 lines of new section:
─────────────────────────────────────────────────────
<...>
─────────────────────────────────────────────────────

[Y] update  [N] skip Step 6b for this run  [E] edit before posting
```

`[E]` opens `$EDITOR` (or `gh gist edit`'s `--editor` mode) on
the rendered Markdown and resumes after save.

---

## Failure modes and recovery

| Failure | Detection | Recovery |
|---|---|---|
| Local state references a deleted gist | `gh api gists/<id>` returns 404 | Treat as first-run; warn the maintainer that the previous gist is gone; create a new one on confirm; overwrite the local state. |
| Local state references a *public* gist | `gh api gists/<id> --jq .public` returns `true` | Refuse to write. Print a notice instructing the maintainer to delete the public gist (`gh gist delete <id>`) and re-run. |
| Local state JSON is malformed | `json.JSONDecodeError` on read | Refuse to write. Print the parse error + path; the maintainer must fix or delete the file. Never silently rewrite a corrupt file — silent loss is worse than a stop. |
| `gh gist create` fails (network, scope) | Non-zero exit | Print the `gh` stderr verbatim. The on-screen Step 6 summary is unaffected; the session is still recorded for the maintainer's own copy. |
| `gh gist edit` race (someone else edited the gist between view and edit) | `gh gist edit` 4xx with conflict | The skill is the only writer to its own gist by contract, so this should not happen. If it does, refuse to write, surface the conflict, and let the maintainer reconcile manually. |
| Two skill instances running concurrently (e.g. two worktrees) | The second instance's `view` sees the first's update; the prepend is correct, no conflict | Native to the prepend pattern — no special handling needed. |

---

## Privacy

The gist is private by default. It still ends up under the
maintainer's GitHub account and is **not** anonymous to the
maintainer's collaborators with access to the link.

The skill MUST NOT include:

- PR comment bodies verbatim (only the action verb + reason
  string from `classify-and-act.md`),
- diff snippets (those live only in the per-session scratch
  cache),
- author email addresses or any field outside the PR / repo
  metadata that drove the classification,
- the `gh` token, any cookie, or any credential material.

Override reasons typed by the maintainer DO go into the gist
(the maintainer is the author of that text). The skill should
not paraphrase or expand them.

---

## What this file is NOT

- A long-term analytics warehouse. Use
  [`pr-management-stats`](../pr-management-stats/SKILL.md) for
  cross-session metrics over the live PR queue. Session-history
  is *append-only* and human-readable; it is not designed to be
  parsed back into structured data.
- A replacement for git history on the framework repo. Concrete
  rule changes still go via PR to
  [`apache/airflow-steward`](https://github.com/apache/airflow-steward).
  The session-history gist is the **input** to those PRs; the
  framework repo's diff is the **output**.
- A substitute for the on-screen summary. Step 6 always prints
  the maintainer-facing summary; Step 6b is the persistence
  layer on top.
