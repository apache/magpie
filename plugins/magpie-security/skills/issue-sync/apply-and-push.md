<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 4 + Step 5 — Apply confirmed changes + regenerate + push CVE artifact

> Extracted from [`SKILL.md`](SKILL.md) so subagents that only need
> this slice can load just this file. Loaded automatically when the
> orchestrator (or a subagent) is in the matching step.

This subdoc carries the apply loop (Step 4), when to run the CVE JSON regen, the OAuth API push and the release-manager hand-off comment reconciliation (Steps 5–5c), and the end-of-sync sweep (Step 5d).

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
  Write the new value to `<workspace>/field-<N>-<slug>.md` with the Write tool, then:

  ```bash
  uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-sync body-field-set <N> "<Field>" <workspace>/field-<N>-<slug>.md
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
  to `<workspace>/rollup-entry-<N>.md` with the Write tool, then:

  ```bash
  uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-sync rollup-append <N> "Sync (<short headline>)" <workspace>/rollup-entry-<N>.md
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
- **Release-manager hand-off and publication-ready notification comments:** apply them per
  [`release-manager-comments.md` § *Step 4*](release-manager-comments.md#step-4--apply-the-release-manager-comments).
- **Team nudge comment:** write the body (first line `<!-- apache-magpie: team-nudge v1 -->`, then the one-line question, the link to the question comment and the `@`-mentions, minus `do_not_ping`) to a temp file and POST it:
  `gh issue comment <N> --repo <tracker> --body-file <tmpfile>`.
  Never PATCH an earlier nudge; a new question gets a new nudge. Add a one-line rollup entry linking the posted comment.
- **Advisory close-out items:** when the confirmed items include the *Advisory archived on `<users-list>`* combined apply
  (the wrap-up comment, the `review-ready → public` state transition, the short-summary extraction) or an advisory-records update,
  read [`advisory-closeout-apply.md`](advisory-closeout-apply.md) and apply those items from it.
- **Close / reopen:** `gh issue close <N> --repo <tracker> --reason completed` (or `not planned`).
  On a GitHub-backed tracker that uses a project board, **always** follow a successful close with
  `uvx --from ~/.claude/magpie/vetted-ops vetted-op --caller security-issue-sync board-archive-item <item_id>`
  (the *Archive a board item* mutation in [`tools/github/project-board.md`](../../../../tools/github/project-board.md#archive-a-board-item--terminal-state-cleanup) without vetted-ops)
  — otherwise a reopened tracker resurfaces on its old column and board sweeps still see it.
  Archive on every close, whatever the reason (terminal Step 15, or `invalid` / `duplicate` / `wontfix`); the mutation is idempotent.
- **Project-board column:** `uvx --from ~/.claude/magpie/vetted-ops vetted-op --caller security-issue-sync board-set-status <item_id> "<Column>"`,
  with the `item_id` from Step 1a's `board-item` read and a column the policy declares
  (on exit `5`, a column or other value the policy does not list, follow [unlisted-value-ask.md](unlisted-value-ask.md)).
  For a tracker with no item yet, first `uvx --from ~/.claude/magpie/vetted-ops vetted-op --caller security-issue-sync board-add-item <node_id>` (it prints the new item id), then set its column.
  Without vetted-ops, the `updateProjectV2ItemFieldValue` and orphan-issue recipes in
  [`tools/github/project-board.md`](../../../../tools/github/project-board.md#write--move-a-tracker-to-a-different-column) do the same,
  and its introspection query re-fetches option IDs when a write starts returning `not found`.
- **Gmail draft:** include `security_cc` from the shared
  [security draft CC resolution](../../../../tools/mail-source/contract.md#security-draft-cc-resolution)
  in every draft's CC; block creation if unresolved.
  On a reporter-facing draft (status, credit and advisory notices, direct or via a forwarder) put `security_bcc` in Bcc:
  the private list, when the project has no dedicated security list; never in To or Cc.
  Create it through the configured drafting backend per [`tools/gmail/draft-backends.md`](../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend).
  The draft is **plain text**; the **preferred** backend is `oauth_curl`, which preserves URLs in the body verbatim:

  - **`oauth_curl`** (preferred — `tools.gmail.draft_backend: oauth_curl`, credentials at
    `tools.gmail.oauth_credentials_path` / `$GMAIL_OAUTH_CREDENTIALS` / default `~/.config/apache-magpie/gmail-oauth.json`) — call
    `mcp__gmail-plaintext__create_draft`, never a shell command
    (see [`draft-backends.md` § *How the skills pick a backend*](../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend))
    with `thread_id` from Step 1c, the standard `to` / `cc` lists, `bcc=security_bcc`,
    `subject="Re: <root subject>"`, and the plain-text `body`.
    When Step 1c found no Gmail thread but the inbound `Message-ID` is known
    (PonyMail, or the tracker's recorded root `Message-ID`), pass it as `in_reply_to`
    (with its `References` chain as `references` when known) instead of `thread_id`.
  - **`claude_ai_mcp`** (**discouraged** — it silently rewrites embedded URLs into Google tracking redirects, see
    [`draft-backends.md`](../../../../tools/gmail/draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)) —
    only when `oauth_curl` credentials are missing **and** the body has no links;
    reply on the Step 1c thread with `subject="Re: <root subject>"` and `replyToMessageId=` its last message, per the call shape in
    [`draft-backends.md` § *How the skills pick a backend*](../../../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend).
  - **`maildir`** (when the drafting backend resolves to it) — `maildir-draft-create` per
    [*The Maildir backend*](../../../../tools/gmail/draft-backends.md#the-maildir-backend),
    with `--in-reply-to` / `--references` from the thread's `Message-ID`s, the standard `--to` / `--cc` (it takes no Bcc: name a non-empty `security_bcc` in the proposal for the human to add),
    `--subject "Re: <root subject>"`, and a `--body-file`.

  **Before drafting, check for an existing pending draft on the thread** with **both** detection paths
  (`mcp__claude_ai_Gmail__list_drafts` **and** `mcp__claude_ai_Gmail__get_thread` with `messageFormat: MINIMAL`, scanning for a `DRAFT` label) in
  [`draft-backends.md` § *Detecting drafts that already exist on a thread*](../../../../tools/gmail/draft-backends.md#detecting-drafts-that-already-exist-on-a-thread):
  `list_drafts` alone misses thread-attached drafts under pile-up, whatever the backend.
  On `maildir`, `maildir-draft-find` replaces both Gmail paths.

  **Surface which backend and which threading path the draft took** (thread-attached vs subject fallback) in the proposal;
  when subject fallback kicks in, record the backend and reason on the tracker's status comment so a future triager understands why the threading degraded.
  **Never send** — both backends create drafts only.
  Tell the user the draft is waiting for their review in Gmail.

If any command fails, stop the apply loop, report the failure, and ask the user how to proceed — do not guess.

---

## Step 5 — Regenerate the CVE artifact via the project's CVE tool

After the apply loop finishes — **every time**, not as a proposal — regenerate the CVE artifact, push it to the CVE tool and reconcile the release-manager hand-off comment (Steps 5, 5b and 5c):
when the *CVE tool link* field is populated, read [`cve-regen-push.md`](cve-regen-push.md) and run it — unconditionally, not as a proposal — unless one of the skip conditions below holds.

### When to skip

Skip the regeneration **only** when one of the following is true, and call it out explicitly in the Step 6 recap:

- **No CVE has been allocated yet** — the *CVE tool link* field is still `_No response_`
  (the generator would embed a block with an `UNKNOWN` CVE marker).
  Remind the user to allocate a CVE via `<cve-tool-url>`; the next sync embeds the JSON automatically once a CVE is set.
- **The tracking issue was closed as `invalid` /
  `duplicate`** and there is nothing to attach.

In every other case — including already-published CVEs — regenerate.

## Step 5b — Push the regenerated JSON to the CVE tool via the adapter

Moved to [`cve-regen-push.md`](cve-regen-push.md#step-5b--push-the-regenerated-json-to-the-cve-tool-via-the-adapter).

### Decision flow

Moved to [`cve-regen-push.md`](cve-regen-push.md#decision-flow).

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
   and move any tracker whose current column differs with `board-set-status` (vetted-ops; the raw mutation in
   [`tools/github/project-board.md`](../../../../tools/github/project-board.md) without it).
   An **open tracker that is not on the board** (Step 1a's `board-item` printed `item: null`) is added with `board-add-item` and then given its column.
   Precedence when several labels coexist: a *needs-triage* marker keeps the tracker in the triage column until a disposition lands
   (per-adopter — some projects couple `needs triage` with scope, some treat them as independent; follow the adopter's `project.md`);
   otherwise the **highest fix-flow state wins**
   (advisory-shipped › fix-released › pr-merged › pr-created › cve-allocated › assessed).
   **Every closed tracker** still on the board, whatever it closed as (announced, invalid, duplicate, not affected, hardening),
   is **archived off the board** with `board-archive-item`, not recoloured.
   **The board holds security trackers only.** Once per run, also read every item with
   `uvx --from ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-sync board-items`
   and propose archiving each one that is not an issue in `<tracker>` carrying the `tracker.labels.security_marker` label
   (pull requests, draft items, issues from another repository, the rejections ledger, an unlabelled stray).
   List them by number and title in the proposal; archiving is reversible from the board's *Archived items* view.
   When Step 1a recorded *"no board configured"*, skip this item and add one recap line proposing the board step of
   [`setup config`](../../../../plugins/magpie-setup/skills/setup/config.md#step-3a1--project-board-github-trackers),
   unless `tracker.project_board_enabled` is `false`.

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

**Then, in bulk mode, the state summary.** When the bulk confirmation kept a state summary in place of the team nudges,
it is rendered from the state this sweep leaves, confirmed and drafted to `<security-list>` as a new thread now, before the recap:
[`bulk-mode.md` step 6](bulk-mode.md#orchestrator-responsibilities).

---
