<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 4 + Step 5 — Apply confirmed changes + regenerate + push CVE artifact

> Extracted from [`SKILL.md`](SKILL.md) so subagents that only need
> this slice can load just this file. Loaded automatically when the
> orchestrator (or a subagent) is in the matching step.

This subdoc carries the apply loop (Step 4), CVE JSON regen mechanics (Step 5/5a), the OAuth API push including the seven pre-push hygiene gates (Step 5b), and the release-manager hand-off comment reconciliation (Step 5c).

---

## Step 4 — Apply confirmed changes

For each confirmed item, run exactly one command and report the result before moving on to the next item.
Use:

- **Labels:** `gh issue edit <N> --repo <tracker> --add-label "..." --remove-label "..."`
- **Milestone (existing):** `gh issue edit <N> --repo <tracker> --milestone "<title>"`
- **Milestone (create then assign):** run the create call from 2b, then the edit. The create call mirrors `due_on` from the matching upstream milestone when available — see the *Read the due date from upstream* rule in [`<project-config>/milestones.md`](../../../../<project-config>/milestones.md#read-the-due-date-from-upstream).
- **Milestone (close):** `gh api -X PATCH repos/<tracker>/milestones/<N> -f state=closed`. Only when the last open tracker on that milestone just closed via Step 15 (cve.org PUBLISHED). See the condition set in [`<project-config>/milestones.md`](../../../../<project-config>/milestones.md#closing-the-milestone).
- **Assignees:** `gh issue edit <N> --repo <tracker> --add-assignee @me` (or a named user).
- **Body fields (one or a few changed fields):** one call per confirmed field.
  Write the new value to `<scratch>/field-<N>-<slug>.md` with the Write tool, then:

  ```bash
  uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-sync body-field-set <N> "<Field>" <scratch>/field-<N>-<slug>.md
  ```

  This covers every Step 2b body-field item — CWE, Severity, Affected versions,
  Reporter credited as, Short public summary for publish, PR with the fix,
  Remediation developer, Public advisory URL, CVE tool link, and backtick-wrapping an existing value.
  Exit `3` means the heading is absent or duplicated: fall back to the whole-body path below for that tracker.
  The secure setup lets `vetted-op-tracker` out of the sandbox (every write still asks).
  Without the secure setup, the same operations are `uv run --directory <framework>/tools/github-rollup github-rollup --repo <tracker> append|amend-latest|fold …` and `uv run --directory <framework>/tools/github-body-field body-field --repo <tracker> get|set …`.
  See [`tools/vetted-ops/README.md`](../../../../tools/vetted-ops/README.md#tracker-procedures-rollup-and-body-field-writes).
- **Description (whole body):** `gh issue edit <N> --repo <tracker> --body-file <tmpfile>`, with the new body written to a temporary file first.
  Only for proposals that change the body's structure rather than field values:
  adding `### Field` sections the body lacks (the *Description fields* item in
  [`signals-to-actions.md`](signals-to-actions.md), which shows the full replacement body),
  adding the `### Related references` audit section from the title cleanup,
  or a field `body-field-set` refused with exit `3`.
- **Status-rollup comment:** write the entry body (no `<details>` envelope, no marker, no ruler)
  to `<scratch>/rollup-entry-<N>.md` with the Write tool, then:

  ```bash
  uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-sync rollup-append <N> "Sync (<short headline>)" <scratch>/rollup-entry-<N>.md
  ```

  The tool adds the envelope and ruler, and creates the rollup with its marker on a legacy tracker that has none yet; the rollup body never enters context.
  Before writing the entry file, **scrub it for bare-name mentions** of anyone on the release-manager and security-team rosters in
  [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md):
  replace each with the ``@``-handle (or `"<Full Name> (@handle)"`), per the "Mentioning maintainers and security-team members" section of [`AGENTS.md`](../../../../AGENTS.md).
  Grep for every full name on those rosters (name-to-handle via
  [`<project-config>/naming-conventions.md`](../../../../<project-config>/naming-conventions.md)
  when it declares a mapping), plus any name in a `Reporter credited as` field without a confirmed external-credit decision.
- **CVE-reviewer-comment ledger:** when this run acted on any reviewer comment found in
  [Step 1e](gather.md#1e-check-the-cve-record-for-reviewer-comments) —
  including pure acknowledgements that needed no other change —
  put the ledger marker in the same rollup entry body file the rest of the run's changes land in:

  ```markdown
  <!-- magpie: cve-review-comments-processed <CVE-ID> slug1,slug2 -->
  ```

  One marker per CVE ID, slugs comma-separated with no spaces.
  It must land **in the same `rollup-append`** as the entry recording the changes,
  so a run that fails after the body update does not re-propose the comment next time.
  Never ledger a slug whose body update was *not* confirmed: it would vanish from every future run.

- **Fold legacy comments:** one call per confirmed legacy comment, oldest first,
  before the pass's own `rollup-append`:

  ```bash
  uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-sync rollup-fold <N> <comment-id> "<Action>"
  ```

  The tool appends the legacy body as an entry under its original date and author,
  and deletes the legacy comment only after the append succeeded.
- **Release-manager hand-off comment:** pick the body template per the variant decision in
  [Step 5c](#step-5c--reconcile-the-release-manager-hand-off-comment) —
  `tools/<cve-tool>/release-manager-handoff-comment-oauth-pushed.md`
  when this run's `vulnogram-api-record-update` push succeeded,
  `tools/<cve-tool>/release-manager-handoff-comment.md` (manual-paste) otherwise.
  Substitute the placeholders (per the *Release-manager hand-off comment* bullet in Step 2b; the OAuth-pushed variant also takes `PUSH_TIMESTAMP`) and write the result to a temp file.
  This fires whenever the tracker's proposal carries the hand-off item —
  at the `pr merged` → `fix released` transition **and** on the invariant-repair path for a tracker already at `fix released` with a review-ready record but no hand-off marker
  (see *Hand-off presence is an invariant* under **Assignees** in [`signals-to-actions.md`](signals-to-actions.md)).
  Decide POST vs PATCH by scanning the comments the [Step 1a](gather.md#1a-read-the-github-issue) fetch already returned
  for one whose body starts with `<!-- apache-magpie: release-manager-handoff v1 -->` — no extra call.

  - **No marker found (first hand-off, or marker lost)** — POST a fresh comment:

    ```bash
    gh issue comment <N> --repo <tracker> --body-file <tmpfile>
    ```

  - **Marker found** — compare the existing body (from the same 1a fetch) against the re-rendered body for the current variant,
    and PATCH it in place only if they differ.
    The REST id (not the GraphQL node id) is the number after `#issuecomment-` in that comment's `url` field, so no lookup call is needed:

    ```bash
    gh api -X PATCH repos/<tracker>/issues/comments/<id> \
      -F body=@<tmpfile> --jq '{id, updated_at}'
    ```

  The PATCH flips the existing comment between variants in place (for example after the Vulnogram token expired),
  so the RM keeps a single comment instead of a duplicate burying the timeline.

  Capture the comment URL (POST or PATCH) for the Step 6 recap.
  Before posting or PATCHing, apply the rollup entry's bare-name → `@`-handle scrub to the resolved body, so the `RM_HANDLE` substitution notifies the release manager.
- **Publication-ready notification comment:** same recipe as the hand-off comment above (same variant decision, same POST-vs-PATCH logic, same scrub), but loading
  `tools/<cve-tool>/release-manager-publication-comment-oauth-pushed.md`
  or `tools/<cve-tool>/release-manager-publication-comment.md`.
  The marker is `<!-- apache-magpie: release-manager-publication-ready v1 -->`.
  Apply it only after the *Public advisory URL* body-field update has landed, the CVE JSON has been regenerated (Step 5a), and (when applicable) the OAuth push has landed (Step 5b),
  so the comment's *"the JSON has been regenerated to include the archive URL and pushed to the record"* claim is true when the RM reads it.
- **Wrap-up comment (post-close, informational only):** load
  [`tools/<cve-tool>/release-manager-wrap-up-comment.md`](../../../../tools/cve-tool-vulnogram/release-manager-wrap-up-comment.md)
  and post it as the **last** action of the *Advisory archived on `<users-list>`* combined apply,
  right after sync has (a) archived the tracker from the project board via `archiveProjectV2Item` and (b) closed the milestone if the just-closed tracker was the last open sibling.
  **The comment is purely informational** — a timeline marker confirming what sync did, **not** a ping for residual manual actions:
  the RM has none left after sending the advisory email.

  Placeholders: `CVE_ID`, `RM_HANDLE` (from the release-manager identity resolved in Step 1f / `release-trains.md`),
  `PUBLISH_TIMESTAMP` (from the just-completed `vulnogram-api-record-publish` call),
  `ADVISORY_URL` (the archive URL captured in the same apply), and the conditional `MILESTONE_BULLET`.

  **`MILESTONE_BULLET` is the only conditional in the template.**
  When sync's milestone-close action fired in the same apply (the just-closed tracker was the last open sibling on its milestone),
  substitute a one-line *informational* note — not an ask:

  ```text
  Milestone [`<ms-title>`](https://github.com/<tracker>/milestone/<ms-number>) closed automatically (every tracker on it is now done).
  ```

  This needs no extra call:
  the apply already knows whether the milestone-close PATCH ran (it fired only after its open-sibling count came back `0`),
  and `<ms-number>` / `<ms-title>` are the tracker's milestone from the [Step 1a](gather.md#1a-read-the-github-issue) fetch.
  When the close did not fire, or the tracker has no milestone, substitute an empty string.

  Write the substituted template to a temp file and POST a fresh comment;
  there is no PATCH recovery for this template (the tracker is already closed).
  Idempotency keys on the marker `<!-- apache-magpie: release-manager-wrap-up v1 -->`:
  if it is already on the tracker, skip the post entirely.
  Apply the same bare-name → `@handle` scrub before posting.
- **Vulnogram state transition (`REVIEW → PUBLIC`):** invoke the
  [`vulnogram-api-record-publish`](../../../../tools/cve-tool-vulnogram/oauth-api/README.md)
  CLI to flip the record's `CNA_private.state` over the OAuth API.
  It refuses the transition unless the current state is `REVIEW`;
  widen with `--allow-state` only when explicitly justified (e.g. a record already moved to `READY` manually):

  ```bash
  uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api \
    vulnogram-api-record-publish --cve-id <CVE-YYYY-NNNNN>
  ```

  Use it only as part of the *Advisory archived on `<users-list>`* combined apply in [Step 2b](SKILL.md#step-2--build-a-proposal-do-not-apply-anything-yet):
  the trigger is *"the advisory has provably shipped on `<users-list>`"*, the signal a human would use before clicking the Vulnogram `REVIEW → PUBLIC` button.
  Outside that trigger, the state transition stays manual.

  Idempotent: re-running on a record already in `PUBLIC` exits 0 with an informational message.
  Exit codes match `record-update` (2 = token expired, 3 = unexpected state, 5 = save failed, 6 = other API error, 7 = unexpected envelope).
  On a non-zero exit, the combined apply stops and the failure surfaces in the recap;
  the partial state (URL captured, labels flipped, JSON re-pushed, tracker NOT yet closed) is the recovery starting point for the next sync.
- **Advisory short-summary extraction:** when the *Advisory archived on `<users-list>`* combined apply fires (Step 2b row),
  fetch the archived advisory email body from the `<mail-archive-url>` archive
  and extract the public-facing short summary into the *Short public summary for publish* body field **before** the Step 5 JSON regen,
  so the published text lands verbatim in the re-pushed JSON.

  Heuristic — from the archive entry's JSON, take the prose block between the CVE header line (matching `^CVE-\d{4}-\d+:`)
  and the first *Affected version range:* / *Affected versions:* block,
  trim leading/trailing blank lines, and collapse internal blank runs to a single blank line.
  Surface the extracted summary in the Step 2 proposal so the user can spot over- or under-extraction before the body-field update applies;
  accept a free-form override at re-confirmation if the heuristic misfires.
- **Close / reopen:** `gh issue close <N> --repo <tracker> --reason completed` (or `not planned`).
  On a GitHub-backed tracker that uses a project board, **always** follow a successful close with the *Archive a board item* mutation in
  [`tools/github/project-board.md`](../../../../tools/github/project-board.md#archive-a-board-item--terminal-state-cleanup)
  — otherwise a reopened tracker resurfaces on its old column and board sweeps still see it.
  Archive on every close, whatever the reason (terminal Step 15, or `invalid` / `duplicate` / `wontfix`); the mutation is idempotent.
- **Project-board column:** apply the `updateProjectV2ItemFieldValue` recipe in
  [`tools/github/project-board.md`](../../../../tools/github/project-board.md#write--move-a-tracker-to-a-different-column),
  with the board node ID, status-field node ID and target-column option ID from
  [`<project-config>/project.md`](../../../../<project-config>/project.md#github-project-board)
  and the `itemId` captured in Step 1a's board read.
  The same doc has the orphan-issue path (`addProjectV2ItemById` then `updateProjectV2ItemFieldValue`) for an issue with no project item,
  and the introspection query to re-fetch option IDs when a write starts returning `not found`.
- **Gmail draft:** include `security_cc` from the shared
  [security draft CC resolution](../../../../tools/mail-source/contract.md#security-draft-cc-resolution)
  in every draft's CC; block creation if unresolved.
  Create it through the configured drafting backend per [`tools/gmail/draft-backends.md`](../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend).
  The draft is **plain text**; the **preferred** backend is `oauth_curl`, which preserves URLs in the body verbatim:

  - **`oauth_curl`** (preferred — `tools.gmail.draft_backend: oauth_curl`, credentials at
    `tools.gmail.oauth_credentials_path` / `$GMAIL_OAUTH_CREDENTIALS` / default `~/.config/apache-magpie/gmail-oauth.json`) — invoke
    `uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-create`
    (see [`tools/gmail/oauth-draft/README.md`](../../../../tools/gmail/oauth-draft/README.md))
    with `--thread-id` from Step 1c, the standard `--to` / `--cc`,
    `--subject "Re: <root subject>"`, and a `--body-file`.
  - **`claude_ai_mcp`** (**discouraged** — it silently rewrites embedded URLs into Google tracking redirects, see
    [`draft-backends.md`](../../../../tools/gmail/draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)) —
    only when `oauth_curl` credentials are missing **and** the body has no links;
    reply on the Step 1c thread with `subject="Re: <root subject>"` and `replyToMessageId=` its last message, per the call shape in
    [`draft-backends.md` § *How the skills pick a backend*](../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend).

  **Before drafting, check for an existing pending draft on the thread** with **both** detection paths
  (`mcp__claude_ai_Gmail__list_drafts` **and** `mcp__claude_ai_Gmail__get_thread` with `messageFormat: MINIMAL`, scanning for a `DRAFT` label) in
  [`draft-backends.md` § *Detecting drafts that already exist on a thread*](../../../../tools/gmail/draft-backends.md#detecting-drafts-that-already-exist-on-a-thread):
  `list_drafts` alone misses thread-attached drafts under pile-up, whatever the backend.

  **Surface which backend and which threading path the draft took** (thread-attached vs subject fallback) in the proposal;
  when subject fallback kicks in, record the backend and reason on the tracker's status comment so a future triager understands why the threading degraded.
  **Never send** — both backends create drafts only.
  Tell the user the draft is waiting for their review in Gmail.

If any command fails, stop the apply loop, report the failure, and ask the user how to proceed — do not guess.

---

## Step 5 — Regenerate the CVE artifact via the project's CVE tool

After the apply loop finishes — **every time**, not as a proposal — regenerate the CVE artifact via the project's declared CVE tool.
For `cve_tool: vulnogram` (see [`<project-config>/project.md`](../../../../<project-config>/project.md#cve-tooling)) that means running the
[`generate-cve-json`](../../../../tools/cve-tool-vulnogram/generate-cve-json/SKILL.md) script with `--attach`
to refresh the CVE JSON attachment on the tracking issue.
The Vulnogram record mechanics (DRAFT / REVIEW / PUBLIC state machine, `#source` paste flow) are in
[`tools/cve-tool-vulnogram/record.md`](../../../../tools/cve-tool-vulnogram/record.md).
The attachment is **embedded in the issue body** (at the very end, right after the *CVE tool link* field), not a separate comment.
The script brackets its block with a pair of HTML-comment markers
(``<!-- generate-cve-json: cve=CVE-YYYY-NNNN+ version=v1 -->`` …
``<!-- generate-cve-json:end cve=CVE-YYYY-NNNN+ version=v1 -->``)
and on every run **replaces the block between them in place**, leaving the rest of the body untouched;
with no previous block, it appends a fresh one after the *CVE tool link* field.
Re-running is cheap and idempotent.

### When to skip

Skip the regeneration **only** when one of the following is true, and call it out explicitly in the Step 6 recap:

- **No CVE has been allocated yet** — the *CVE tool link* field is still `_No response_`
  (the generator would embed a block with an `UNKNOWN` CVE marker).
  Remind the user to allocate a CVE via `<cve-tool-url>`; the next sync embeds the JSON automatically once a CVE is set.
- **The tracking issue was closed as `invalid` /
  `duplicate`** and there is nothing to attach.

In every other case — including already-published CVEs — regenerate.

### How to run it

The minimum command, from the `<tracker>` clone root:

```bash
uv run --project <framework>/tools/cve-tool-vulnogram/generate-cve-json generate-cve-json <N> --attach
```

That alone is enough: the script reads every template field from the issue body, emits the full CVE 5.x record, and patches (or appends to) the tracking issue body in place.

### Remediation-developer credit comes from the body field

The *Remediation developer* body field is the **single source of truth** for the `type: "remediation developer"` credits in the regenerated JSON.
The generator reads it via `extract_field`, parses it line by line (same shape as *Reporter credited as*), and emits one credit per non-empty line.
**No `--remediation-developer` CLI flag is needed in the normal flow.**

The Step 1d row that fires when *"PR with the fix"* is set and *"Remediation developer"* lacks the PR author
appends the resolved name to the body field, so by Step 5 the generator already has it.
Because the credit lives in the body, manual edits (co-authors, spelling fixes, "Anonymous" overrides) survive every regen.

**Pitfall caught on [<tracker>#241](https://github.com/<tracker>/issues/241)** —
the body mentioned `<upstream>#44322` as prior-art context before the actual fix `<upstream>#63028`,
and a naive `grep | head` against the whole body picked the wrong PR.
The Step 1d row scopes the URL extraction to the *"PR with the fix"* section only (`awk` between the section heading and the next `### ` heading);
apply the same scoping if you resolve the author by hand.

```bash
uv run --project <framework>/tools/cve-tool-vulnogram/generate-cve-json generate-cve-json <N> --attach
```

If the *"Remediation developer"* field is empty at regeneration time (e.g. the Step 1d PR-author lookup has not yet run on a freshly-set *PR with the fix* field),
the regen succeeds but the embedded JSON carries no remediation-developer credit.
Either run a follow-up sync to populate the field,
or pass `--remediation-developer "<Name>"` once on the command line and let the next sync fold the name into the body field.

### Don't override `--version-start`

The sync deliberately does **not** guess `--version-start`.
If the *Affected versions* body field has a `>= X, < Y` shape, the script picks `X` automatically.
For a bare `< Y` shape (the typical case) it uses the default `"0"`,
and the reviewer can tighten it later with a manual `--version-start 3.0.0` invocation that patches the same embedded block.

### Report the result

The script prints one of two lines on success:

- `Embedded CVE JSON in issue body on <tracker>#<N>` — first
  run (or first run after the legacy comment-based attachment was
  cleaned up).
- `Replaced CVE JSON in issue body on <tracker>#<N>` —
  subsequent run; the existing embedded block was replaced in place.

Capture the printed URL — it deep-links to the `## CVE JSON — paste-ready for <CVE>` heading anchor inside the body — and include it in the Step 6 recap.

---

## Step 5b — Push the regenerated JSON to the CVE tool via the adapter

**When the operator's machine has a valid authenticated session** for the adapter named in `cve_authority.tool`
(one-time setup per `tools/<cve-tool>/README.md`; for Vulnogram,
`uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api vulnogram-api-setup`, see
[`tools/cve-tool-vulnogram/oauth-api/README.md`](../../../../tools/cve-tool-vulnogram/oauth-api/README.md)),
**sync pushes the JSON to the record directly** through the adapter's `push_update(cve_id, fields, state_transition=None)` method
(per [`tools/cve-tool/README.md`](../../../../tools/cve-tool/README.md))
instead of leaving the paste step to the release manager.

**Push trigger — every regen, not only `fix released`.** Every run that regenerates the CVE JSON
(any `generate-cve-json` / Step 5a `--attach`) pushes it to the record in the **same apply pass**, so the record never drifts from the body.
The operator's confirmation of the change that triggered the regen **is** the authorisation to push:
there is no separate confirmation, and the push is never deferred to the release manager. Triggers include, beyond `fix released`:

- **advisory-URL / `announced` close-out** on an already-`public` (Vulnogram: `PUBLIC`) record —
  the regen adds the `vendor-advisory` reference from the *Public advisory URL* body field, and the push writes it to the published record;
- **reviewer-feedback title / summary edits** on a record still in `allocated` / `review-ready` (Vulnogram: `DRAFT` / `REVIEW`);
- **field corrections** — *Affected versions*, *CWE*, *Severity*, *Reporter credited as*, *Remediation developer* —
  that change any value the generator reads into the record.

Because `push_update` writes the generator-computed `CNA_private.state` verbatim (see below),
a regen can legitimately walk a record **back** — e.g. `review-ready → allocated` (Vulnogram: `REVIEW → DRAFT`) —
when a title or summary edit re-opens a question a reviewer had signed off on; the reviewer then re-reviews from the lower state.
Surface every such state change in the Step 6 recap so it is never silent.

**State auto-promote from `allocated` to `review-ready` — driven by the generator, not by sync.**
The generator emits the adapter-native state token based on the readiness of the tracker's body fields,
and the contract maps it onto the generic state verbs (the *Generic state verbs* table in [`tools/cve-tool/README.md`](../../../../tools/cve-tool/README.md)).
For Vulnogram the native tokens are `DRAFT` / `REVIEW` / `READY` / `PUBLIC`, and
`compute_cna_private_state` in
[`tools/cve-tool-vulnogram/generate-cve-json`](../../../../tools/cve-tool-vulnogram/generate-cve-json/src/generate_cve_json/cve_json.py)
emits:

- `allocated` (Vulnogram: `DRAFT`) — when any required field is
  missing (no title, no description, no affected versions, no
  CWE, no non-Unknown severity, no credit, no reference).
- `review-ready` (Vulnogram: `REVIEW`) — when every field a
  release manager needs to send the advisory is present, **but**
  no public advisory URL has been captured yet.
- `public` (Vulnogram: `PUBLIC`) — when the CNA is review-ready
  AND at least one `references[]` entry is tagged
  `vendor-advisory` (i.e. the *Public advisory URL* body field
  is populated with the archived users-list URL).

Sync's role is **just** to push the generated JSON via `push_update` and verify, through `fetch_current_state`, that the saved state matches what the generator computed.
`push_update` writes any embedded state field verbatim where the tool supports it, so no separate state-flip call is needed for `allocated` → `review-ready`.
This is the load-bearing gate for the release-manager hand-off (Step 2b's *Two-stage gate*): the RM never receives the hand-off comment while the record is still in `allocated`.

**The `pr merged → fix released` transition is the one instance of the push-on-regen rule that is also *mandatory*: it performs this push in the same apply pass and it is not deferrable.**
The label flip and this 5a-regen + 5b-push are **one atomic unit**, authorised by the user's confirmation of the transition.
The `fix released` label is in the generator's forward-state set (`compute_cna_private_state`), so the regenerated JSON carries `review-ready`,
and the push advances the record `allocated → review-ready` — the action that unblocks the hand-off.
Do **not** park the push behind a second confirmation, and do **not** defer it on the reasoning that "the release manager will promote the record":
the RM owns `review-ready → publish-ready → advisory`; the `allocated → review-ready` promotion is sync's job at `fix released`.
A tracker labelled `fix released` whose record is still `allocated` (Vulnogram: `DRAFT`) after the sync is a **process bug** — it strands the RM, who is gated on `review-ready`, and silently stalls the advisory.

**The only acceptable deferral** is a genuinely-unavailable authenticated session at sync time (the session probe returns `expired` or `not-configured` — see the decision flow below).
Then, and only then, sync posts the **manual-paste** hand-off variant *and* raises an explicit blocker in the Step 6 recap
(*"<CVE> still in `allocated`/DRAFT — push on the next authenticated sync"*).
Completing the push is the first action of the next session-capable sync.

The remaining transitions stay separate:

- `review-ready` → `publish-ready` is a **release-manager UI action** in the CVE tool (for Vulnogram, the State dropdown going `REVIEW` → `READY`),
  done as Step 1 of the RM hand-off after any reviewer comments on the record are resolved.
  The generator does not emit `publish-ready`: it is a human decision that reviewer feedback is closed.
- `publish-ready` → `public` is **sync-driven** via the adapter's `publish(cve_id)` method (see Step 4 above),
  fired when the advisory archive URL has been captured on `<mail-archive-url>/list.html?<users-list>`.

Step 6 below describes how to verify the state advance landed (and what to do if it did not).

### Decision flow

1. **Skip-condition gate.** Skip 5b entirely when 5a was skipped
   (no CVE allocated; tracker closed as invalid / duplicate / not
   CVE worthy). There is no record to push to.

1b. **Pre-push hygiene-gate scan.** Before any push call, re-scan
   the JSON about to be pushed for the seven pre-push gates that
   make the published CVE record user-facing:

   - **Title strip cascade** — `containers.cna.title` must have gone through the
     [`security-cve-allocate` Step 2 cascade](../cve-allocate/title-normalize.md#step-2--compute-the-cve-ready-title)
     and contain no project-name prefix/suffix, no `[GHSA-...]` / `(ZDRES-...)` / `(HUNTR-...)` / `(GHSL-...)` external tracker IDs,
     no `(split from #NNN)` markers, no `[Security Report]` classifier, no version-noise suffix.
     The issue-title hygiene Step 1d row enforces the same cascade; this gate re-runs it on the JSON's `title`, because the generator reads the issue title verbatim.
   - **Short public summary names an upgrade-target version** —
     `descriptions[0].value` must contain a `<package> <X.Y.Z>`
     pattern; bare *"upgrade to the version that contains the
     fix"* fails.
   - **Short public summary states trigger conditions** — the
     who / when / action triplet from the Step 2b paragraph
     above; at least two of three must be unambiguously present.
   - **Incomplete-fix cross-CVE clause** — when the tracker is
     a follow-up to a prior PUBLISHED CVE (the rollup or body
     declares the relationship), the summary must name the prior
     CVE AND tell users who applied the prior fix to also apply
     this one.
   - **CWE field has the long-form description** —
     `problemTypes[0].descriptions[0].description` must be in
     the `CWE-NNN: <Title>` shape, not a bare `CWE-NNN` token.
   - **Anonymise private-scanner and internal-finder names** —
     when the tracker's source is a private scanner, an internal-partner-shared scan, or an unpublished bug-bounty pipeline
     (signal: the *Security mailing list thread* body field references a scanner product name, or names an individual reporter who arrived through a private channel rather than `security@`),
     the regenerated JSON must NOT carry the scanner product name or the individual finder's name in any public-facing field.
     Scan `containers.cna.descriptions[].value` (the public summary) and `containers.cna.credits[].value` for
     scanner-product tokens declared in [`<project-config>/scanner-products.md`](../../../../<project-config>/scanner-products.md)
     (e.g. `Mythos`, `<vendor> SAST`, `<scanner-tool>`),
     and for `credits[].value` entries matching a person-name pattern (`<First> <Last>` shape) when the `discovery-channel` signal is private.
     On match: propose replacing the credit value with the scanner's declared **public credit name**, emitted with `type: "tool"` per
     [`bot-credits-policy.md`](../../../../tools/cve-tool-vulnogram/bot-credits-policy.md);
     when none is declared, **omit the `finder` credit** rather than writing a placeholder, per
     [Rule 2 of the finder-credit policy](../../../../tools/cve-tool-vulnogram/finder-credit-policy.md).
     Also strip the scanner product name from the summary text.
     The tracker's *Security mailing list thread* field stays unchanged (it is the private audit trail); only the CVE-record JSON gets the scrub.
     **Public bug-bounty submissions and named ASF-community reporters are exempt** —
     never anonymise a credit already public elsewhere (HackerOne report URL, huntr.dev public report, the reporter's own self-disclosure on `security@` with their real name).
     Rationale, examples, and the opt-in / opt-out matrix: [`<project-config>/scanner-products.md`](../../../../<project-config>/scanner-products.md).
   - **Conservative affected-versions range** — when the JSON's `affected[].versions[]` describes a lower-bounded range
     (typically from the body's `>= X.Y.Z, < A.B.C` shape: `version: "X.Y.Z"`, `versionType: "semver"`, `lessThan: "A.B.C"`),
     the body field must show explicit evidence that earlier versions are NOT affected —
     an "introduced in `<version>`", "regression from `<version>`", or "`<X-line>` is EOL" marker for the lower-bound version in the rollup, body, or linked PR text.
     Without that evidence the gate refuses the push and surfaces the widened-range proposal (`version: "0"` lower bound) from the matching Step 1d row:
     the default is all-versions-affected unless there is positive evidence to the contrary.

   When any gate fails the JSON the regen just produced, do **not** push:
   fix the underlying body field (or title, for the title gate), re-regen, then re-scan.
   The gates catch body fields that drifted between the Step 2b proposal and the push
   (e.g. the user confirmed only some of the proposed updates); a skipped push makes the next sync surface the rest.

2. **Probe the adapter's authenticated session.** Invoke the adapter's session-probe entrypoint
   (per `tools/<cve-tool>/README.md`; for Vulnogram,
   `uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api vulnogram-api-check`).
   It returns one of three outcomes:

   - **`valid`** → proceed to step 3.
   - **`expired`** → skip the push and surface a one-line reminder in the Step 6 recap:
     *"CVE-tool authenticated session expired — re-run the adapter's setup entrypoint (for the Vulnogram adapter, `vulnogram-api-setup`) to restore automatic push; using manual-paste hand-off this run."*
     Use the manual-paste hand-off variant for any 5c comment work below.
   - **`not-configured`** → skip the push;
     the manual-paste hand-off (via the `cve_authority.source_tab_url_template` link) still works.
     Silent on other runs, but on a `fix released` transition the record still needs `allocated → review-ready`,
     so raise the deferral blocker from the rule above in the Step 6 recap.
     Use the manual-paste hand-off variant for any 5c comment work below.

3. **Extract the regenerated JSON.** Re-run the
   [`generate-cve-json`](../../../../tools/cve-tool-vulnogram/generate-cve-json/SKILL.md)
   generator with `--stdout` (no `--attach`) into a temporary file,
   or extract it from the body via `awk` between the
   `<!-- generate-cve-json: cve=<CVE> version=v1 -->` / `<!-- generate-cve-json:end ... -->` markers —
   the generator is deterministic, so both yield the same bytes.
   Conventional path: `<scratch>/cve-<CVE-ID>-<N>.json`.
   `<scratch>` is the session scratch directory as an absolute path (fall back to `$TMPDIR`); `gh` may run outside the sandbox, where `$TMPDIR` differs, so pass it absolute paths.

4. **Push the update through the adapter's `push_update` method**
   (`push_update(cve_id, fields, state_transition=None)` per [`tools/cve-tool/README.md`](../../../../tools/cve-tool/README.md)).
   For Vulnogram the entrypoint is `vulnogram-api-record-update`:

   ```bash
   uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api vulnogram-api-record-update \
     --cve-id <CVE-ID> --json-file <scratch>/cve-<CVE-ID>-<N>.json
   ```

   `state_transition` is omitted: the JSON already carries the generator-computed state,
   which an adapter that embeds state in the record body (Vulnogram does) writes in the same call;
   an adapter that needs a separate state-flip call does it internally, keeping the call atomic from the skill's side.

   Capture the exit code and `stdout` / `stderr`:

   - **`exit 0`** → push succeeded.
     Record the ISO-8601 timestamp (`PUSH_TIMESTAMP`); the Step 5c comment work uses the **OAuth-pushed variant**;
     the Step 6 recap includes *"CVE record auto-pushed to the CVE tool at `PUSH_TIMESTAMP`."* (for Vulnogram, *"auto-pushed to Vulnogram"*).
   - **`exit ≠ 0`** → push failed.
     Surface the error verbatim in the Step 6 recap and **fall back** to the manual-paste hand-off for the Step 5c comment work.
     Do **not** retry in the same sync run; the next sync retries.

5. **Idempotence note.** `push_update` is idempotent by contract (the Vulnogram upsert endpoint satisfies this),
   so do not short-circuit "already pushed this JSON":
   every successful run that re-regenerated the JSON re-pushes, keeping the record byte-identical to the tracker body.

6. **Verify the state advance landed (`allocated` → `review-ready`
   gate).** When step 4 succeeded **and** the pushed JSON carried the adapter-native equivalent of `review-ready`
   (for Vulnogram, `body.CNA_private.state = "REVIEW"`),
   immediately call the adapter's `fetch_current_state(cve_id)` to confirm the state advanced.
   For Vulnogram the entrypoint is `vulnogram-api-record-fetch`:

   ```bash
   uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api vulnogram-api-record-fetch \
     --cve-id <CVE-ID> --jq '.body.CNA_private.state'
   ```

   If that fetch entrypoint is not yet installed on the operator's machine (see [`tools/cve-tool-vulnogram/oauth-api/README.md`](../../../../tools/cve-tool-vulnogram/oauth-api/README.md)),
   read the state from the `push_update` response envelope, which the contract requires to include the saved state.

   `fetch_current_state` normalises the native token onto the generic verbs
   (`allocated`, `review-ready`, `publish-ready`, `public`, `retracted`, `unknown`).
   Three outcomes:

   - **`review-ready` or any later state (`publish-ready` / `public`)** → state-gate clear.
     Step 5c picks the OAuth-pushed hand-off variant and Step 4 of the *Reconcile* flow posts / PATCH-flips the RM hand-off comment.
     The Step 6 recap notes *"CVE record state auto-promoted to `review-ready` at `PUSH_TIMESTAMP`."*
     (for Vulnogram, add *"i.e. `DRAFT` → `REVIEW` in the underlying record"*).
   - **`allocated`** → state-gate NOT cleared.
     Surface the specific reason: usually a body field was empty, so the JSON never carried `state = "review-ready"` (Stage 1 of the two-stage gate caught this);
     otherwise a body field carried a value the CNA schema rejected silently (the upsert saved what it could parse but did not advance the state).
     Either way, **do not post the RM hand-off comment**.
     Fire the *Remediation-developer fill-fields comment* instead per the dedicated Step 2b bullet, and surface the state-gate-not-cleared blocker in the Step 6 recap.
   - **Fetch failed (transient HTTP error, session expired between push and fetch, or the adapter returned `unknown`)** →
     surface the fetch failure as a blocker, post nothing on the RM-hand-off front this run, and retry the verification on the next sync.

## Step 5c — Reconcile the release-manager hand-off comment

The Step 12 (`pr merged` → `fix released`) **hand-off comment** and the Step 14 (advisory archived) **publication-ready notification** both come in two variants.
The templates live under `tools/<cve-tool>/` — the adapter directory named by `cve_authority.tool` in `<project-config>/project.md` —
so each adapter ships variants tuned to its own copy-paste surface and push path:

| Variant | Template | When |
|---|---|---|
| Manual-paste (today's default) | `tools/<cve-tool>/release-manager-handoff-comment.md`, `tools/<cve-tool>/release-manager-publication-comment.md` (for the Vulnogram adapter: [`tools/cve-tool-vulnogram/release-manager-handoff-comment.md`](../../../../tools/cve-tool-vulnogram/release-manager-handoff-comment.md), [`tools/cve-tool-vulnogram/release-manager-publication-comment.md`](../../../../tools/cve-tool-vulnogram/release-manager-publication-comment.md)) | Step 5b skipped (`expired` / `not-configured`) or the push failed |
| OAuth-pushed | `tools/<cve-tool>/release-manager-handoff-comment-oauth-pushed.md`, `tools/<cve-tool>/release-manager-publication-comment-oauth-pushed.md` (for the Vulnogram adapter: [`tools/cve-tool-vulnogram/release-manager-handoff-comment-oauth-pushed.md`](../../../../tools/cve-tool-vulnogram/release-manager-handoff-comment-oauth-pushed.md), [`tools/cve-tool-vulnogram/release-manager-publication-comment-oauth-pushed.md`](../../../../tools/cve-tool-vulnogram/release-manager-publication-comment-oauth-pushed.md)) | Step 5b's `push_update` succeeded this run |

Both variants of each comment carry the **same marker** on line 1
(`<!-- apache-magpie: release-manager-handoff v1 -->` for the hand-off, `<!-- apache-magpie: release-manager-publication-ready v1 -->` for the publication-ready);
idempotency keys on the marker, and the variant gets no marker of its own.
When the marker is found, PATCH the existing comment in place to the variant matching this run's outcome, rather than posting a duplicate:

- **First-time hand-off** (no existing comment, label transition
  fires this run) → POST the appropriate variant.
- **Subsequent sync, `push_update` succeeded this run** → PATCH the existing comment to the OAuth-pushed body, refreshing `PUSH_TIMESTAMP`.
  If it is already the OAuth-pushed variant, still PATCH: the timestamp is the audit trail.
- **Subsequent sync, `push_update` failed (or was skipped)** → PATCH the existing comment to the manual-paste variant,
  so the RM sees a fresh "please paste" ask the moment the auto-push stops working.
- **Subsequent sync, no relevant transition fired and the JSON did
  not change** → no PATCH. Idempotency: marker present, body
  byte-identical, nothing to do.

The POST and PATCH mechanics are the *Release-manager hand-off comment* and *Publication-ready notification comment* bullets in Step 4.

---

## Step 5d — End-of-sync reconciliation sweep (board / milestone / RM hand-off)

After every confirmed per-tracker change has been applied — and **before** the Step 6 recap is printed —
the sync runs a **final reconciliation sweep over every tracker in the run** (single-issue or bulk),
making three dimensions consistent with each tracker's label / PR-derived state.

It is **unconditional**: it runs on every sync, whether or not a signal surfaced in Step 1d.
The signal-driven proposals in [`signals-to-actions.md`](signals-to-actions.md) cover the moves a signal triggers;
this sweep catches the drift no signal captures — a label flipped by hand, a release shipped since the last sync,
a hand-off announced in the rollup but never made in the assignee field.

Run it over the same tracker set the sync just processed;
in bulk mode the orchestrator runs it after the sequential apply phase (never inside the read-only assessor subagents).
For each tracker:

1. **Board `Status` column.** Compute the correct column from the tracker's labels + body per the label→column mapping the adopter declares in
   [`<project-config>/project.md`](../../../../<project-config>/project.md),
   and move any tracker whose current column differs via the `updateProjectV2ItemFieldValue` mutation
   (introspection + write recipe in [`tools/github/project-board.md`](../../../../tools/github/project-board.md)).
   Precedence when several labels coexist: a *needs-triage* marker keeps the tracker in the triage column until a disposition lands
   (per-adopter — some projects couple `needs triage` with scope, some treat them as independent; follow the adopter's `project.md`);
   otherwise the **highest fix-flow state wins**
   (advisory-shipped › fix-released › pr-merged › pr-created › cve-allocated › assessed).
   Closed trackers that have shipped their advisory are **archived off the board**, not recoloured.

2. **Milestone.** Compute the correct milestone from the fix PR's milestone / the shipped release per
   [`<project-config>/milestones.md`](../../../../<project-config>/milestones.md)
   and correct any drift.
   **Never guess** a due date or a release date: if the correct milestone is ambiguous, or would require creating a new milestone on an unknown date,
   **flag it in the recap for confirmation** rather than auto-creating (creating one on a documented, unambiguous date is fine).
   Pre-release trackers (no shipped version yet) correctly keep an empty milestone; that is not drift.

3. **RM assignee hand-off.** For each tracker at `fix released` (or transitioning to it this run) whose assignee is still the remediation developer,
   **swap it to the release manager** for the shipping release, looked up via the three-source cascade in Step 2c
   ([`<project-config>/release-trains.md` § *Release managers for releases currently relevant to the security tracker*](../../../../<project-config>/release-trains.md#release-managers-for-releases-currently-relevant-to-the-security-tracker) → the project's Release Plan wiki →
   the `[RESULT][VOTE] Release <product> <version>` thread on `<dev-list>`).
   `Fix released` hands ownership to the RM for Steps 13–15, so the **board column and the assignee move together**.
   **Always hand off** at `fix released`, even when the fix is incomplete or a follow-up is still open:
   then still swap the assignee to the RM **and post a guard note** on the tracker (`@`-mention the RM) telling them to **hold advisory publication** until the follow-up merges.
   A withheld assignee is the wrong signal; the note carries the "don't publish yet" nuance.
   If the RM is not yet a `<tracker>` collaborator, surface that as a blocker (GitHub silently drops assignee writes for non-collaborators) instead of a silent no-op.

**Confirmation model.** Pure label-derived reconciliation — a column move, an RM swap to the *looked-up* release manager, assigning an *already-existing* milestone —
is the confirmed end-of-sync behaviour and does **not** need separate per-item confirmation.
Anything that **creates** state (a new milestone, an ambiguous release-date choice) or posts an outbound message (the guard note `@`-mentioning the RM)
still follows the skill's propose-before-apply rule (Golden rule 1).
The Step 6 recap always lists what the sweep moved (column, milestone, assignee) per tracker.

---
