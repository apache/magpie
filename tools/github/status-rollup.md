<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Status-rollup comment — shared shape for skill-authored status updates](#status-rollup-comment--shared-shape-for-skill-authored-status-updates)
  - [The rollup comment shape](#the-rollup-comment-shape)
  - [Summary — action labels](#summary--action-labels)
  - [The entry body](#the-entry-body)
  - [Upsert recipe — append to an existing rollup, or create one](#upsert-recipe--append-to-an-existing-rollup-or-create-one)
    - [1. Find the existing rollup comment](#1-find-the-existing-rollup-comment)
    - [2a. Append to an existing rollup](#2a-append-to-an-existing-rollup)
    - [2b. Create a new rollup](#2b-create-a-new-rollup)
  - [Migrating legacy comments into a rollup](#migrating-legacy-comments-into-a-rollup)
    - [Detecting a legacy bot comment](#detecting-a-legacy-bot-comment)
    - [Folding a legacy comment into the rollup](#folding-a-legacy-comment-into-the-rollup)
    - [The fold-legacy sub-step is a proposal, not an auto-apply](#the-fold-legacy-sub-step-is-a-proposal-not-an-auto-apply)
    - [When a tracker has no rollup yet but has many legacy comments](#when-a-tracker-has-no-rollup-yet-but-has-many-legacy-comments)
  - [Hard rules](#hard-rules)
  - [Referenced by](#referenced-by)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Status-rollup comment — shared shape for skill-authored status updates

Every agent-authored status update on a `<tracker>` issue (the import
receipt, each sync pass, CVE allocation, dedupe merges, fix-PR
announcements, etc.) lands in **one single rollup comment** per
tracker. Each pass appends a new *entry* to that comment instead of
posting a fresh one. The result: scrolling a tracker's timeline shows
one rollup comment plus the human discussion, not twenty bot comments
drowning out the actual conversation.

This file is the canonical shape + upsert recipe. Skills (`sync-*`,
`import-*`, `allocate-*`, `deduplicate-*`, `fix-*`) reference this
file instead of re-specifying the shape.

## The rollup comment shape

One comment per tracker, identified by an opening HTML marker on the
first line:

```markdown
<!-- airflow-s status rollup v1 — all bot-authored status updates fold into this single comment. -->
<details><summary>YYYY-MM-DD · @user · <Action></summary>

<entry body>

</details>

---

<details><summary>YYYY-MM-DD · @user · <Action></summary>

<entry body>

</details>
```

Rules (all load-bearing — breaking any of them breaks GitHub's
Markdown rendering):

- **First line is the marker.** `<!-- airflow-s status rollup v1 — … -->`
  identifies the comment as the rollup. Detection is anchored on
  `airflow-s status rollup v` so future `v2` bumps remain findable.
- **Every entry is its own `<details>` block.** Including the very
  first one (the import receipt). There is no always-visible
  preamble above the first `<details>`. The reason: every entry —
  current and historical — is collapsed by default per the user's
  rule; nothing is promoted above the fold.
- **Open tag is one line.** Write `<details><summary>…</summary>` on
  a single line. Do **not** split `<details>` onto its own line and
  `<summary>` onto the next — that variant renders reliably on
  github.com too, but the one-line form is what the skills emit and
  detection passes match on.
- **Summary contains three fields, `·`-separated**, in this order:
  `YYYY-MM-DD · @handle · <Action>`. No trailing text, no parenthetical
  headlines, nothing else. The details-open arrow on github.com already
  consumes horizontal space; keep the summary scannable at a glance.
  Optional fourth field in parentheses is allowed only for
  disambiguation — see *Summary — action labels* below.
- **Exactly one blank line after `<summary>…</summary>`.** Markdown
  inside a `<details>` needs a blank line after the open to render.
  Two blank lines is fine; zero blank lines silently suppresses all
  markdown inside.
- **Exactly one blank line before `</details>`.** Same reason, other
  end.
- **No leading whitespace on any line inside the entry.** A leading
  space or tab turns the line into a preformatted-code block and
  wrecks the rendering for every subsequent line. When a sync
  proposal pastes multi-line content into an entry, *left-trim every
  line* before writing.
- **Entries are separated by a bare `---` on its own line**, with one
  blank line on each side:

  ```markdown
  </details>

  ---

  <details><summary>…</summary>
  ```

  The ruler is GitHub's `<hr>`. Skip the blank lines around it and the
  preceding `</details>` will stay attached.
- **Chronological order — newest at the bottom.** New entries append;
  the comment grows downward. A reader opens the rollup and scrolls
  to the latest entry at the end.

## Summary — action labels

Each skill emits one of the following `<Action>` strings so the summary
line tells the reader at a glance *what* the entry represents:

| Emitting skill | `<Action>` value | Optional parenthetical |
|---|---|---|
| `security-issue-import` | `Import` | class + reporter, e.g. `Import (Report, Jane Doe)` |
| `security-issue-sync` (ordinary pass) | `Sync` | one-phrase headline, e.g. `Sync (pr merged → fix released)` |
| `security-issue-sync` (escalation, Step 4) | `Sync` | `Sync (Step 4 escalation)` |
| `security-issue-sync` (reformat-only, migrating legacy comments) | `Reformat` | `Reformat (N legacy comments folded)` |
| `security-cve-allocate` | `CVE allocated` | the allocated ID, e.g. `CVE allocated (CVE-2026-40913)` |
| `security-issue-deduplicate`, on the kept tracker | `Merge (kept)` | dropped side's number, e.g. `Merge (kept) (from #305)` |
| `security-issue-deduplicate`, on the dropped tracker | `Merge (dropped)` | kept side's number, e.g. `Merge (dropped) (into #244)` |
| `security-issue-fix` | `Fix PR` | upstream PR number, e.g. `Fix PR (<upstream>#65346)` |

The parenthetical is optional; include it when it adds information a
scroller actually wants (the CVE ID, the dedupe counterpart, the PR
number). Do **not** restate the same fact inside the entry body and in
the parenthetical; the body carries the detail, the summary carries
the headline.

## The entry body

Inside the `<details>` block, write what the skill used to write in
its pre-collapse body — the bold headline, the `**Next:**` line, the
reporter-notification line, the full rationale. The entire body is
already inside `<details>`, so the "keep visible part under six
lines" rule from the legacy status-comment shape **no longer
applies**. Write what the auditor needs to reconstruct the decision;
the scroller sees the summary only and only expands entries they
care about.

That said — brevity still wins. Do not pad. Do not restate the
previous entry. Each entry is *incremental*: what changed in this
pass, what comes next, what the reporter now knows. Earlier state
lives in earlier entries.

Required elements inside every entry body:

- **Bold headline** as the first line — the same bold-first-line rule
  the old pre-collapse comments used. Example: `**Sync 2026-04-21 —
  pr merged → fix released.**`. This is what a reader sees first
  when they expand the entry.
- **`**Next:**` line** — one sentence on what comes next. Omit only
  when the entry is terminal (e.g. dedupe on the dropped side, the
  *"all triage continues on #<keep>"* line replaces `**Next:**`).
- **Reporter-notification line** when applicable — one of the four
  forms from the legacy spec (see each skill's dedicated section).

Outside that required frame, the content is free-form markdown.
Clickable `<tracker>` references (the *Linking tracker issues and
PRs* rule in [`AGENTS.md`](../../AGENTS.md)) apply everywhere, same
as before.

## Upsert recipe — append to an existing rollup, or create one

Every skill that emits a status update runs this recipe. The steps
assume the skill has already composed `<new-entry>` — the full
`<details>…</details>` block for this pass, with no leading/trailing
blank lines.

### 1. Find the existing rollup comment

```bash
gh issue view <N> --repo <tracker> \
  --json comments \
  --jq '.comments[] | select(.body | startswith("<!-- airflow-s status rollup v")) | {id: .id, body: .body, url: .url}'
```

The matching comment is the rollup. If the query returns nothing,
there is no rollup yet (expected on a fresh tracker where
`security-issue-import` has not run, or on a legacy tracker that
pre-dates this convention).

Use the **first** match chronologically if the query somehow returns
more than one — two rollups is a bug; surface it to the user and
let them pick which one to keep.

### 2a. Append to an existing rollup

Construct the new body by concatenating the old body + a ruler + the
new entry, with exactly one blank line on each side of the ruler:

```text
<old body>

---

<new entry>
```

Write the new body to a temp file and PATCH the comment:

```bash
python3 - <<'PY' > /tmp/rollup-body.md
import pathlib, subprocess, json, textwrap

old = subprocess.check_output(
    ["gh", "api", "repos/<tracker>/issues/comments/<comment-id>", "--jq", ".body"],
    text=True,
).rstrip("\n")
new_entry = pathlib.Path("/tmp/new-entry.md").read_text().rstrip("\n")
print(old + "\n\n---\n\n" + new_entry)
PY

jq -Rs '{body: .}' /tmp/rollup-body.md > /tmp/rollup-patch.json
gh api -X PATCH repos/<tracker>/issues/comments/<comment-id> --input /tmp/rollup-patch.json
```

The `-X PATCH repos/<tracker>/issues/comments/<id>` form is the only
reliable way; `gh issue comment --edit-last` does **not** target an
arbitrary comment, and the `--input` flag is needed because
`--field body=@file` URL-encodes the newlines in the body.

### 2b. Create a new rollup

Only if Step 1 returned no existing rollup. Prepend the marker line
and emit the new entry as the rollup's first entry:

```markdown
<!-- airflow-s status rollup v1 — all bot-authored status updates fold into this single comment. -->
<new entry>
```

Post as a regular comment via `gh issue comment --body-file`:

```bash
gh issue comment <N> --repo <tracker> --body-file /tmp/rollup-body.md
```

Capture the returned comment URL + ID so subsequent passes in the
same run can append without re-searching.

## Migrating legacy comments into a rollup

Trackers created before this convention carry one or more bot-authored
status comments as separate top-level comments. Every sync pass runs
a **fold-legacy** sub-step: detect each legacy bot comment, move its
content into the rollup as its own entry, and delete (or minimise) the
original.

### Detecting a legacy bot comment

A comment is a candidate for folding when **all** of the following hold:

1. **Not already a rollup.** Its body does not start with
   `<!-- airflow-s status rollup v`.
2. **Author is on the security-team roster.** Cross-check
   `.comments[].author.login` against the collaborator list (see
   [`operations.md`](operations.md#collaborator-lookup-security-team-roster))
   or the project's roster declared in
   [`<project-config>/release-trains.md`](../../<project-config>/release-trains.md#security-team-roster).
   Human discussion from an external reporter is *never* folded;
   their content stays as a top-level comment.
3. **Body matches one of the bot-shape prefixes** (case-sensitive,
   first ~500 characters of the body):
   - `**Sync `
   - `**Status update`
   - `**Merged `
   - `**Closing as duplicate`
   - `**Split for scope clarity`
   - `**Imported on `
   - `**Process-step escalation`
   - `**Allocated CVE` / `**CVE allocated` / `**Sync … — CVE`
   - Legacy bare-text prefixes (no leading `**`): `Sync status (`,
     `Sync YYYY-MM-DD`, `Status update`
   - Content tells when the prefix is idiosyncratic:
     `security-issue-sync skill`, `re-triage`,
     `Reporter notification still pending`, `Outstanding — Step `,
     a verbatim `generate-cve-json` embed block.

A comment that matches **1 + 2 + 3** is foldable. A comment that
matches only **1 + 2** (team-member comment with no bot-shape prefix)
is regular human discussion — **leave it alone.**

### Folding a legacy comment into the rollup

For each foldable legacy comment, in chronological order:

1. **Reconstruct the entry shape.** Take the legacy body and wrap it
   in the rollup's `<details>` envelope:

   ```html
   <details><summary><createdAt date> · @<author.login> · <Action></summary>

   <legacy body — verbatim, left-trimmed>

   </details>
   ```

   - `<createdAt date>` is the first 10 chars of the legacy
     comment's `createdAt` (`YYYY-MM-DD`).
   - `<Action>` is derived from the legacy body's prefix via the
     table in *Summary — action labels* above; when the prefix does
     not map cleanly, use `Sync` and tag the fold as
     `Reformat (N legacy comments folded)` on the overall rollup
     entry the sync is about to write.
   - **Left-trim every line** before pasting. Legacy comments that
     were hand-edited sometimes carry stray indentation (see
     `airflow-s#244`'s 2026-04-20 comment, which had `        ` on
     most lines); leaving that indentation inside a `<details>`
     turns the whole entry into a preformatted-code block.
2. **Append the reconstructed entry to the rollup**, using the upsert
   recipe above (Step 2a). Preserve the original order by appending
   oldest-first.
3. **Delete the legacy comment** once the rollup PATCH succeeds:

   ```bash
   gh api -X DELETE repos/<tracker>/issues/comments/<legacy-comment-id>
   ```

   Only delete after the append lands — if the PATCH fails, the
   content is still on the tracker via the legacy comment and the
   fold can be retried on the next pass. Never delete first and hope
   the append works.

### The fold-legacy sub-step is a proposal, not an auto-apply

Like every other skill action, surface each proposed fold as a
numbered item in the skill's Step 2 proposal. Show the legacy
comment's URL, its first ~3 lines, and the derived `<Action>` for
the summary. The user may accept all, accept some, or reject (for
example when a legacy comment has inline discussion from a reporter
mixed into a status update — in that case leave it alone, it is not
a pure bot comment).

### When a tracker has no rollup yet but has many legacy comments

The fold path still works: create the rollup (Step 2b) with the
*oldest* foldable legacy comment as its first entry, then append the
rest (Step 2a), then append the current pass's new entry last. The
recap reports *"created new rollup comment on #<N>, folded N legacy
comments into it"* and lists the deleted comment IDs so the user can
audit the change.

## Hard rules

- **Never touch a human-authored comment.** Step 2 of the detection
  (author is on the security-team roster) is not optional. A reporter
  quoting a status update in their own words is not bot content — it
  is their message.
- **Never delete a legacy comment before the append succeeds.** If
  the PATCH lands a partial body (e.g. truncated), the only
  recoverable artefact is the original legacy comment.
- **Never rewrite the content of a folded entry.** Copy the legacy
  body verbatim inside the `<details>` block (with left-trim applied
  to fix indentation-induced rendering bugs, but nothing else).
  Paraphrasing a historical status update rewrites the audit trail.
- **Never promote a newer entry above an older one.** The rollup is
  chronological. A sync pass that appends out of order hides the
  timeline.
- **Never write markdown with leading spaces inside a `<details>`
  block.** A single stray indentation breaks rendering for every
  subsequent line of the entry. Compose entries with all lines
  flush-left.
- **Never create two rollups on the same tracker.** If Step 1 of the
  upsert finds more than one `<!-- airflow-s status rollup v` marker,
  stop and ask the user which to keep — the cheapest recovery is a
  manual merge, not a silent overwrite.
- **Never name or describe other ASF projects' vulnerabilities** in a
  rollup entry body, even when the reporter or your own signal
  mining has surfaced them. Cross-project observations belong in
  the private mail channel they arrived on — not in the tracker.
  See the *"Other ASF projects — never name or describe their
  vulnerabilities"* subsection of
  [`AGENTS.md`](../../AGENTS.md#other-asf-projects--never-name-or-describe-their-vulnerabilities)
  for the full rule, the *why*, and the grep-list self-check to run
  before posting. Summarise load-bearing cross-project context in
  de-identified form (*"the reporter has filed similar reports with
  other ASF projects"*) rather than naming the project.

## Referenced by

- [`.claude/skills/security-issue-import/SKILL.md`](../../skills/security-issue-import/SKILL.md) — creates the rollup with the first entry.
- [`.claude/skills/security-issue-sync/SKILL.md`](../../skills/security-issue-sync/SKILL.md) — appends per-sync entries and runs the fold-legacy sub-step.
- [`.claude/skills/security-cve-allocate/SKILL.md`](../../skills/security-cve-allocate/SKILL.md) — appends the CVE-allocation entry.
- [`.claude/skills/security-issue-deduplicate/SKILL.md`](../../skills/security-issue-deduplicate/SKILL.md) — appends the merge entry on both trackers.
- [`.claude/skills/security-issue-fix/SKILL.md`](../../skills/security-issue-fix/SKILL.md) — appends the fix-PR entry.
