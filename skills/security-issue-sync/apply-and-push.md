<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 4 + Step 5 — Apply confirmed changes + regenerate + push CVE artifact

> Extracted from [`SKILL.md`](SKILL.md) so subagents that only need
> this slice can load just this file. Loaded automatically when the
> orchestrator (or a subagent) is in the matching step.

This subdoc carries the apply loop (Step 4), CVE JSON regen mechanics (Step 5/5a), the OAuth API push including the six pre-push hygiene gates (Step 5b), and the release-manager hand-off comment reconciliation (Step 5c).

---

## Step 4 — Apply confirmed changes

For each confirmed item, run exactly one command and report the result
before moving on to the next item. Use:

- **Labels:** `gh issue edit <N> --repo <tracker> --add-label "..." --remove-label "..."`
- **Milestone (existing):** `gh issue edit <N> --repo <tracker> --milestone "<title>"`
- **Milestone (create then assign):** run the create call from 2b, then the edit. The create call mirrors `due_on` from the matching upstream milestone when available — see the *Read the due date from upstream* rule in [`<project-config>/milestones.md`](../../<project-config>/milestones.md#read-the-due-date-from-upstream).
- **Milestone (close):** `gh api -X PATCH repos/<tracker>/milestones/<N> -f state=closed`. Only when the last open tracker on that milestone just closed via Step 15 (cve.org PUBLISHED). See the condition set in [`<project-config>/milestones.md`](../../<project-config>/milestones.md#closing-the-milestone).
- **Assignees:** `gh issue edit <N> --repo <tracker> --add-assignee @me` (or a named user).
- **Description:** `gh issue edit <N> --repo <tracker> --body-file <tmpfile>` — write the
  new body to a temporary file first so nothing is lost to shell quoting.
- **Status-rollup comment:** use the upsert recipe in
  [`tools/github/status-rollup.md`](../../tools/github/status-rollup.md#upsert-recipe--append-to-an-existing-rollup-or-create-one).
  On a tracker that already carries a rollup, this is
  `gh api -X PATCH repos/<tracker>/issues/comments/<id> --input
  <json>` with the old body + `\n\n---\n\n` + the new entry; on a
  legacy tracker with no rollup yet, it is a one-off `gh issue
  comment <N> --repo <tracker> --body-file <tmpfile>` seeded with
  the marker + the new entry + any folded legacy entries.
  Before PATCHing / posting, **scrub the entry body for bare-name
  mentions** of anyone on the "Current release managers" or
  rotation-roster lists in
  [`AGENTS.md`](../../AGENTS.md), and of known security-team
  members. Replace each bare name with the corresponding
  ``@``-handle (or `"<Full Name> (@handle)"` when readability
  warrants keeping the plain name too) so GitHub actually notifies
  the person. See the "Mentioning maintainers and
  security-team members" section of
  [`AGENTS.md`](../../AGENTS.md). Concrete grep-list to check
  against: `Jarek Potiuk`, `Jens Scheffler`, `Vincent BECK`,
  `Shahar Epstein`, `Buğra Öztürk`, `Jedidiah Cunningham`,
  `Rahul Vats`, `Aritra Basu`, `Pierre Jeambrun`, `Kaxil Naik`,
  `Amogh Desai`, plus any name that appears in a `Reporter credited
  as` field without a confirmed external-credit decision.
- **Fold-legacy deletes:** after the rollup PATCH succeeds and
  carries the folded entries, delete each original legacy bot
  comment with `gh api -X DELETE
  repos/<tracker>/issues/comments/<id>`. Never delete before the
  PATCH lands.
- **Release-manager hand-off comment:** pick the body template
  per the variant decision from
  [Step 5c](#step-5c--reconcile-the-release-manager-hand-off-comment) —
  `tools/<cve-tool>/release-manager-handoff-comment-oauth-pushed.md`
  when this sync run's `vulnogram-api-record-update` push succeeded,
  `tools/<cve-tool>/release-manager-handoff-comment.md` (manual-paste)
  otherwise. Substitute the placeholders (per the *Release-manager
  hand-off comment* bullet in Step 2b; the OAuth-pushed variant also
  takes `PUSH_TIMESTAMP`), write the result to a temp file. Then
  decide POST vs PATCH by grepping the tracker's comment list for
  the marker:

  ```bash
  existing=$(gh issue view <N> --repo <tracker> --json comments \
    --jq '[.comments[] | select(.body | startswith("<!-- apache-magpie: release-manager-handoff v1 -->"))] | .[0].id // empty')
  ```

  - **No marker found (first hand-off, or marker lost)** — POST a
    fresh comment:

    ```bash
    gh issue comment <N> --repo <tracker> --body-file <tmpfile>
    ```

  - **Marker found** — fetch the existing body, compare against the
    re-rendered body for the current variant, and PATCH-edit
    in-place only if they differ (skip the round-trip when the
    body is byte-identical):

    ```bash
    # extract the REST id (not the GraphQL node id)
    rest_id=$(gh api repos/<tracker>/issues/comments \
      --jq '.[] | select(.node_id == "<existing>") | .id')
    # PATCH
    jq -n --rawfile body <tmpfile> '{body: $body}' | \
      gh api -X PATCH repos/<tracker>/issues/comments/${rest_id} \
        --input - --jq '{id, updated_at}'
    ```

  The PATCH path is what powers the "OAuth-pushed today, manual-paste
  next sync (because the cookie expired)" recovery: the existing
  comment's body flips between variants in place, keeping a single
  comment as the canonical RM-facing surface and avoiding the
  "fresh duplicate buries the timeline" failure mode (same rationale
  as the rollup-comment PATCH-don't-post rule).

  Capture the comment URL (POST or PATCH) for the Step 6 recap.
  Before posting / PATCHing, **scrub the resolved body** for the
  same bare-name → `@`-handle replacements documented for the rollup
  PATCH above, so the `RM_HANDLE` substitution actually notifies
  the release manager.
- **Publication-ready notification comment:** same recipe as the
  hand-off comment above (same variant decision, same POST-vs-PATCH
  logic, same scrub), but loading
  `tools/<cve-tool>/release-manager-publication-comment-oauth-pushed.md`
  or `tools/<cve-tool>/release-manager-publication-comment.md` based
  on the same Step 5c variant choice. The marker is
  `<!-- apache-magpie: release-manager-publication-ready v1 -->`.
  Apply right after the *Public advisory URL* body-field update has
  landed, the CVE JSON has been regenerated (Step 5a), and (when
  applicable) the OAuth push has landed (Step 5b) — that way the
  comment's *"the JSON has been regenerated to include the archive
  URL and pushed to the record"* claim is true at the moment the
  RM reads it.
- **Wrap-up comment (post-close, informational only):** load
  [`tools/<cve-tool>/release-manager-wrap-up-comment.md`](../../tools/cve-tool-vulnogram/release-manager-wrap-up-comment.md)
  and post it as the **last** action of the *Advisory archived on
  `<users-list>`* combined apply, right after sync has already
  (a) archived the tracker from the project board via
  `archiveProjectV2Item` and (b) closed the milestone if the
  just-closed tracker was the last open sibling. **The comment is
  purely informational** — a timeline-event marker confirming
  what sync did, **not** a ping for residual manual actions. The
  RM has zero remaining actions post-Send-Email; asking them to
  do what sync already did creates the same confusion class the
  state-gated hand-off was designed to eliminate (worked example:
  RM feedback on the original wrap-up template — *"Same here for
  step 3 - not idiot safe (I fail to understand)"*).

  Placeholders to substitute: `CVE_ID`, `RM_HANDLE` (from the
  release-manager identity resolved in Step 1f / `release-trains.md`),
  `PUBLISH_TIMESTAMP` (from the just-completed
  `vulnogram-api-record-publish` call), `ADVISORY_URL` (the
  archive URL captured in the same apply), and the conditional
  `MILESTONE_BULLET` — see below.

  **`MILESTONE_BULLET` is the only conditional in the template.**
  When sync's milestone-close action fired in the same apply
  (i.e. the just-closed tracker was the last open sibling on its
  milestone), substitute with a one-line *informational* note —
  not an ask:

  ```bash
  ms=$(gh issue view <N> --repo <tracker> --json milestone \
    --jq '.milestone.number // empty')

  if [ -n "$ms" ]; then
    # The just-closed tracker is no longer in the open list, so
    # `open` here counts SIBLINGS still open on the same milestone.
    open=$(gh issue list --repo <tracker> --milestone "$ms" \
      --state open --limit 1000 --json number --jq 'length')
    if [ "$open" -eq 0 ]; then
      ms_url=$(gh api repos/<tracker>/milestones/$ms --jq '.html_url')
      ms_title=$(gh api repos/<tracker>/milestones/$ms --jq '.title')
      bullet="Milestone [\`$ms_title\`]($ms_url) closed automatically (every tracker on it is now done)."
    else
      bullet=""
    fi
  else
    bullet=""
  fi
  ```

  Substitute into the template, write the result to a temp file,
  then POST a fresh comment — there is no PATCH recovery for this
  template (the tracker is closed by the time it posts;
  informational only). Idempotency keys on the marker
  `<!-- apache-magpie: release-manager-wrap-up v1 -->`; if the
  marker is already present on the tracker, skip the post
  entirely.

  Before posting, apply the same bare-name → `@handle` scrub used
  for the rollup PATCH and hand-off comment, so the `RM_HANDLE`
  substitution actually notifies the release manager.
- **Vulnogram state transition (`REVIEW → PUBLIC`):** invoke the
  [`vulnogram-api-record-publish`](../../tools/cve-tool-vulnogram/oauth-api/README.md)
  CLI to flip the record's `CNA_private.state` over the OAuth API.
  The default refuses the transition unless the current state is
  `REVIEW`; widen with `--allow-state` only when explicitly
  justified (e.g. a record that has already been moved to `READY`
  manually):

  ```bash
  uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api \
    vulnogram-api-record-publish --cve-id <CVE-YYYY-NNNNN>
  ```

  Use this action only as part of the *Advisory archived on
  `<users-list>`* combined apply in [Step 2b](SKILL.md#step-2--build-a-proposal-do-not-apply-anything-yet) —
  the trigger is *"the advisory has provably shipped on
  `<users-list>`"*, which is the real-world signal a human would
  use before clicking the Vulnogram `REVIEW → PUBLIC` button.
  Outside that trigger, the state transition stays manual.

  Idempotent: re-running on a record already in `PUBLIC` exits 0
  with an informational message. Exit-code interpretation matches
  `record-update` (2 = session expired, 3 = unexpected state,
  4 = CSRF, 5 = save failed, 6 = other API error, 7 = unexpected
  envelope). On a non-zero exit, the combined apply stops and the
  failure surfaces in the recap; the partial state (URL captured,
  labels flipped, JSON re-pushed, tracker NOT yet closed) is the
  right recovery starting point for the next sync once the
  underlying issue is resolved.
- **Advisory short-summary extraction:** when the *Advisory
  archived on `<users-list>`* combined apply fires (Step 2b row),
  fetch the archived advisory email body from the
  `<mail-archive-url>` archive and extract the public-facing short
  summary into the *Short public summary for publish* body field
  **before** the Step 5 JSON regen.

  Heuristic — read the archive entry's JSON, extract the prose
  block between the CVE header line (matching `^CVE-\d{4}-\d+:`)
  and the first *Affected version range:* / *Affected versions:*
  block, trim leading/trailing blank lines, collapse internal blank
  runs to a single blank line. Surface the extracted summary in
  the Step 2 proposal so the user can spot any over- or
  under-extraction before the body-field update applies; accept a
  free-form override at re-confirmation if the heuristic misfires.

  **Why ahead of Step 5's regen.** The regeneration step reads the
  body fields as source of truth; updating *Short public summary
  for publish* before regen means the re-pushed JSON carries the
  published summary verbatim (lock-step). Updating after regen
  drifts the pushed JSON from the body until the next sync.
- **Close / reopen:** `gh issue close <N> --repo <tracker> --reason completed` (or `not planned`).
  When this is a GitHub-backed tracker that uses a project board,
  **always** follow a successful close with the **archive-from-board**
  mutation per the *Archive a board item* recipe in
  [`tools/github/project-board.md`](../../tools/github/project-board.md#archive-a-board-item--terminal-state-cleanup).
  Closed issues leave the active board view automatically, but an
  explicit archive (`archiveProjectV2Item`) is what moves the item
  to the board's *"Archived items"* view permanently — without it,
  reopening a tracker resurfaces it on whatever column its `Status`
  field still points at, and historical board sweeps still see the
  item. Apply the archive for every close, regardless of the close
  reason (terminal-Step-15 or non-terminal disposition like
  `invalid` / `duplicate` / `wontfix`); the
  mutation is idempotent and a no-op on already-archived items.
- **Project-board column:** apply via the `updateProjectV2ItemFieldValue`
  GraphQL recipe in
  [`tools/github/project-board.md`](../../tools/github/project-board.md#write--move-a-tracker-to-a-different-column).
  Substitute the project's board node ID, status-field node ID, and
  target-column option ID from
  [`<project-config>/project.md`](../../<project-config>/project.md#github-project-board).
  Use the `itemId` captured in Step 1a's board read. If the issue
  does not yet have a project item, use the orphan-issue path from
  the same reference (`addProjectV2ItemById` then
  `updateProjectV2ItemFieldValue`). Re-fetch the option IDs via the
  introspection query in the same reference if a write mutation
  starts returning `not found`.
- **Gmail draft:** create via the project's configured drafting
  backend per [`tools/gmail/draft-backends.md`](../../tools/gmail/draft-backends.md#how-the-skills-pick-a-backend).
  The **preferred** backend is `oauth_curl` — it preserves URLs in
  the body verbatim. The `claude_ai_mcp` backend is **discouraged**
  because it silently rewrites embedded URLs into Google tracking
  redirects (see [`draft-backends.md`](../../tools/gmail/draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)); use it only when
  `oauth_curl` credentials are missing AND the body has no links.
  Per-backend call shape:

  - **`claude_ai_mcp`** (discouraged — rewrites URLs) — first call
    `mcp__claude_ai_Gmail__get_thread(threadId=<from Step 1c>,
    messageFormat='MINIMAL')` to resolve the chronologically-last
    message ID; then call `mcp__claude_ai_Gmail__create_draft` with
    `subject="Re: <root subject>"`, the standard `to` / `cc` / `body`,
    and `replyToMessageId=<that message id>`. The draft attaches to
    the inbound thread on the sender's Gmail and surfaces in both the
    conversation view and the global Drafts folder.
  - **`oauth_curl`** (preferred — for users who set
    `tools.gmail.draft_backend: oauth_curl` and have credentials at
    `tools.gmail.oauth_credentials_path` /
    `$GMAIL_OAUTH_CREDENTIALS` / default
    `~/.config/apache-magpie/gmail-oauth.json`) — invoke
    `uv run --project <framework>/tools/gmail/oauth-draft oauth-draft-create`
    (see [`tools/gmail/oauth-draft/README.md`](../../tools/gmail/oauth-draft/README.md))
    with `--thread-id` from Step 1c, the standard `--to` / `--cc`,
    `--subject "Re: <root subject>"`, and a `--body-file`.

  **Before drafting, check for an existing pending draft on the
  thread.** Run **both** `mcp__claude_ai_Gmail__list_drafts` (catches
  drafts in the global Drafts folder) **and**
  `mcp__claude_ai_Gmail__get_thread` on the inbound `threadId` with
  `messageFormat: MINIMAL`, scanning each message for a `DRAFT` label
  (catches thread-attached drafts that may pile up and hide from the
  global Drafts folder, regardless of backend). `list_drafts` alone
  misses thread-attached drafts under pile-up. See the *Detecting
  drafts that already exist on a thread* section of
  [`draft-backends.md`](../../tools/gmail/draft-backends.md#detecting-drafts-that-already-exist-on-a-thread).

  **Surface which backend and which threading path the draft took**
  (thread-attached vs subject fallback) in the proposal so the user
  can see the threading at a glance; record the backend + reason on
  the tracker's status comment when subject fallback kicks in (so a
  future triager understands why the threading degraded). **Never
  send** — both backends create drafts only. Tell the user the
  draft is waiting for their review in Gmail.

If any command fails, stop the apply loop, report the failure, and ask the user
how to proceed — do not guess.

---

## Step 5 — Regenerate the CVE artifact via the project's CVE tool

After the apply loop finishes — **every time**, not as a proposal — regenerate the
CVE artifact via the project's declared CVE tool. For the adopting project (`cve_tool: vulnogram` —
see [`<project-config>/project.md`](../../<project-config>/project.md#cve-tooling)) that means
running the
[`generate-cve-json`](../../tools/cve-tool-vulnogram/generate-cve-json/SKILL.md) script with `--attach`
to refresh the CVE JSON attachment on the tracking issue. The Vulnogram-side
record mechanics (DRAFT / REVIEW / PUBLIC state machine, `#source` paste flow) live
in [`tools/cve-tool-vulnogram/record.md`](../../tools/cve-tool-vulnogram/record.md). The attachment
lives **embedded in the issue body** (at the very end, right after the
*CVE tool link* field), not as a separate comment — this way it stays
above every status-change comment in the timeline and reads as part of
the tracker itself. Re-running the generator is cheap and idempotent: the
script brackets its block with a pair of HTML-comment markers
(``<!-- generate-cve-json: cve=CVE-YYYY-NNNN+ version=v1 -->`` …
``<!-- generate-cve-json:end cve=CVE-YYYY-NNNN+ version=v1 -->``) and on
every run **replaces the block between them in place**, leaving the rest
of the body untouched. If there is no previous attachment block yet, the
script appends a fresh one after the *CVE tool link* field.

Keeping the attachment in lock-step with the tracking issue body has two
payoffs:

1. The release manager can always grab the most-current JSON straight from
   the issue at advisory-publication time, without having to remember to
   regenerate, and without scrolling through the comment timeline.
2. The `#source` paste URL is visible on every sync, so if a reviewer
   notices the issue body drifting from the Vulnogram record they can
   jump straight to the paste-ready JSON.

### When to skip

Skip the regeneration **only** when one of the following is true, and call
it out explicitly in the Step 6 recap:

- **No CVE has been allocated yet** — the issue body's *CVE tool link*
  field is still `_No response_`. Running the generator in that state
  would embed a block with an `UNKNOWN` CVE marker, which is not useful.
  Remind the user to allocate a CVE via
  `<cve-tool-url>` and mention that the next
  sync run will embed the JSON automatically once a CVE is set.
- **The tracking issue was closed as `invalid` /
  `duplicate`** and there is nothing to attach.

In every other case — including already-published CVEs — regenerate.

### How to run it

The minimum command, from the `<tracker>` clone root:

```bash
uv run --project <framework>/tools/cve-tool-vulnogram/generate-cve-json generate-cve-json <N> --attach
```

That alone is enough. The script reads every template field from the
issue body, emits the full CVE 5.x record, and patches (or appends to)
the tracking issue body in place.

### Remediation-developer credit comes from the body field

The *Remediation developer* body field is the **single source of
truth** for the `type: "remediation developer"` credits in the
regenerated JSON. The generator reads the field directly via
`extract_field`, parses it newline-by-newline (same shape as
*Reporter credited as*), and emits one credit per non-empty line.
**No `--remediation-developer` CLI flag is needed in the normal
flow.**

The PR-author resolution that used to happen at regeneration time now
happens earlier: the table in Step 1d (the row that fires when
*"PR with the fix"* is set and *"Remediation developer"* is missing
the PR author) appends the resolved name to the body field. By the
time Step 5 runs, the field already contains the right names, the
generator picks them up, and the embedded JSON carries the credit.

This earlier hand-off matters for two reasons:

1. **The credit survives manual edits.** Co-authors added by the
   triager, name spelling corrections, or "Anonymous" overrides all
   live in the body field where they are visible at a glance and
   diffable in the issue history. The previous CLI-flag flow lost
   any such edit on the next regen.
2. **The credit survives lost overrides.** Re-running
   `generate-cve-json --attach` after a long gap no longer needs the
   triager to remember which `--remediation-developer` flag was
   passed last time — the field is in the body and survives any
   number of regen cycles.

**Pitfall caught on
[<tracker>#241](https://github.com/<tracker>/issues/241)** — the
body mentioned `<upstream>#44322` as prior-art context before the
actual fix `<upstream>#63028`, and a naive `grep | head` against the
whole body had picked the wrong PR. The Step 1d row scopes the URL
extraction to the *"PR with the fix"* section only (`awk` between the
section heading and the next `### ` heading) for exactly this
reason; the same scoping rule applies if you ever need to resolve
the author by hand.

```bash
uv run --project <framework>/tools/cve-tool-vulnogram/generate-cve-json generate-cve-json <N> --attach
```

If the *"Remediation developer"* field is empty at regeneration time
(e.g. because the PR author lookup in Step 1d hasn't run yet on a
freshly-set *PR with the fix* field), the regen succeeds but the
embedded JSON carries no remediation-developer credit. Either run a
follow-up sync to populate the field, or pass `--remediation-developer
"<Name>"` once on the command line and let the next sync fold the
name into the body field for permanence.

### Don't override `--version-start`

The sync skill deliberately does **not** try to guess `--version-start`.
If the *Affected versions* body field has a `>= X, < Y` shape, the script
picks `X` automatically. If it has a bare `< Y` shape (the typical
case), the script's default `"0"` is used, and the reviewer can
tighten it later with a manual `--version-start 3.0.0` invocation that
patches the same embedded attachment block.

### Report the result

The script prints one of two lines on success:

- `Embedded CVE JSON in issue body on <tracker>#<N>` — first
  run (or first run after the legacy comment-based attachment was
  cleaned up).
- `Replaced CVE JSON in issue body on <tracker>#<N>` —
  subsequent run; the existing embedded block was replaced in place.

Capture the printed URL — it deep-links to the `## CVE JSON — paste-ready
for <CVE>` heading anchor inside the body — and include it in the Step 6
recap so the user has one-click access to the attached JSON.

---

## Step 5b — Push the regenerated JSON to the CVE tool via the adapter

The regenerated JSON above is paste-ready for the project's CVE
tool. **When the operator's machine has a valid authenticated session
configured** for the adapter named in
`cve_authority.tool` (one-time setup per the
`tools/<cve-tool>/README.md` adapter doc — for the Vulnogram adapter,
that is `uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api vulnogram-api-setup`
backing the contract's authenticated-session probe; see
[`tools/cve-tool-vulnogram/oauth-api/README.md`](../../tools/cve-tool-vulnogram/oauth-api/README.md)),
**sync pushes the JSON to the record directly** through the
adapter's `push_update(cve_id, fields, state_transition=None)`
method (per [`tools/cve-tool/README.md`](../../tools/cve-tool/README.md))
instead of leaving the paste step to the release manager. The push
is mechanical and follows from the same JSON the user just approved
as part of the body update.

**State auto-promote from `allocated` to `review-ready` — driven by
the generator, not by sync.** The CVE JSON the generator produces
already carries the correct `CNA_private.state` value based on the
readiness of the tracker's body fields. The generator emits the
adapter-native state token, which the contract maps onto the generic
state verbs the skills speak in (see the *Generic state verbs* table
in [`tools/cve-tool/README.md`](../../tools/cve-tool/README.md)).
For the Vulnogram adapter the native tokens are `DRAFT` / `REVIEW` /
`READY` / `PUBLIC`; the generator's logic (see
`compute_cna_private_state` in
[`tools/cve-tool-vulnogram/generate-cve-json`](../../tools/cve-tool-vulnogram/generate-cve-json/src/generate_cve_json/cve_json.py))
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

Sync's role is therefore **just** to push the generated JSON via
the adapter's `push_update` and verify, through `fetch_current_state`,
that the saved state matches what the generator computed. The
contract guarantees `push_update` writes any embedded state field
verbatim where the underlying tool supports it; no separate
state-flip call is needed for the `allocated` → `review-ready`
transition. This is the load-bearing gate for the release-manager
hand-off (see Step 2b's *Two-stage gate*): the RM never receives
the hand-off comment while the record is still in `allocated`.

The remaining transitions stay separate:

- `review-ready` → `publish-ready` is a **release-manager UI
  action** in the CVE tool (for the Vulnogram adapter, the State
  dropdown going `REVIEW` → `READY`), done as Step 1 of the RM
  hand-off after any reviewer comments on the record are resolved.
  The generator does not emit `publish-ready` — it is intentionally
  a human decision that reviewer feedback is closed.
- `publish-ready` → `public` is **sync-driven** via the
  adapter's `publish(cve_id)` method (see Step 4 below), fired
  when the advisory archive URL has been captured on
  `<mail-archive-url>/list.html?<users-list>` — the CNA-feed
  dispatch trigger has a real-world signal (the archived
  advisory) so sync drives it.

Step 6 below describes how to verify the state advance landed
(and what to do if it did not).

### Decision flow

1. **Skip-condition gate.** Skip 5b entirely when 5a was skipped
   (no CVE allocated; tracker closed as invalid / duplicate / not
   CVE worthy). There is no record to push to.

1b. **Pre-push hygiene-gate scan.** Before any push call, re-scan
   the JSON about to be pushed for the seven pre-push gates that
   make the published CVE record user-facing:

   - **Title strip cascade** — `containers.cna.title` must have
     gone through the [`security-cve-allocate` Step 2 cascade](../security-cve-allocate/SKILL.md#step-2--compute-the-cve-ready-title)
     and contain no project-name prefix/suffix, no `[GHSA-...]` /
     `(ZDRES-...)` / `(HUNTR-...)` / `(GHSL-...)` external tracker
     IDs, no `(split from #NNN)` markers, no `[Security Report]`
     classifier, no version-noise suffix. The cascade is the same
     one the issue-title hygiene Step 1d row enforces; this gate
     re-runs it on the JSON's `title` field directly because the
     generator reads the GitHub issue title verbatim and the JSON
     value is what actually ships.
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
   - **Anonymise private-scanner and internal-finder names**
     — when the tracker's source is a private scanner, an
     internal-partner-shared scan, or an unpublished bug-bounty
     pipeline (signal: the *Security mailing list thread* body
     field references a scanner product name or names an
     individual reporter who arrived through a private channel
     rather than `security@`), the regenerated JSON must NOT
     carry the scanner product name or the individual finder's
     name in any public-facing field. Scan
     `containers.cna.descriptions[].value` (the public summary)
     and `containers.cna.credits[].value` for: known
     scanner-product tokens declared in
     [`<project-config>/scanner-products.md`](../../<project-config>/scanner-products.md)
     (e.g. `Mythos`, `<vendor> SAST`, `<scanner-tool>`); and
     for `credits[].value` entries that match a person-name
     pattern (`<First> <Last>` shape) when the
     `discovery-channel` signal is private. On match: propose
     replacing the credit value with `anonymous` and stripping
     the scanner product name from the summary text. The
     tracker's *Security mailing list thread* body field stays
     unchanged (it is the private audit trail); only the
     CVE-record JSON gets the anonymise scrub. **Public
     bug-bounty submissions and named ASF-community reporters
     are exempt** (the scrubber must not anonymise a credit
     that was already public elsewhere — HackerOne report URL,
     huntr.dev public report, the reporter's own self-disclosure
     on `security@` with their real name). Rationale, examples,
     and the full opt-in / opt-out matrix live in
     [`<project-config>/scanner-products.md`](../../<project-config>/scanner-products.md).
   - **Conservative affected-versions range** — when the
     JSON's `affected[].versions[]` array describes a
     lower-bounded range (typically emitted from the body's
     `>= X.Y.Z, < A.B.C` shape: `version: "X.Y.Z"`,
     `versionType: "semver"`, `lessThan: "A.B.C"`), the body
     field must show explicit evidence that the operator
     verified earlier versions are NOT affected — an
     "introduced in `<version>`", "regression from `<version>`",
     or "`<X-line>` is EOL" marker for the lower-bound version
     in the rollup, body, or linked PR text. Without that
     evidence the gate refuses the push and surfaces the
     widened-range proposal (`version: "0"` lower bound)
     described in the matching Step 1d row. Per conservative
     security-advisory practice, the default is all-versions-affected
     unless we have positive evidence to the contrary.

   When any gate fails the JSON the regen just produced, the
   right recovery is **not** to push — fix the underlying body
   field (or title, for the title gate), re-regen, then re-scan.
   The gates exist to catch the cases where the body fields drift
   between the Step 2b proposal cycle and the actual push (e.g.
   a Step 2b proposal landed but the user edited only a subset
   of the proposed updates). Skipping the push on a gate failure
   forces the next sync iteration to surface the remaining edits.

2. **Probe the adapter's authenticated session.** Invoke the
   adapter's session-probe entrypoint (per
   `tools/<cve-tool>/README.md`; for the Vulnogram adapter this is
   `uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api vulnogram-api-check`).
   The contract requires the probe to return one of three outcomes:

   - **`valid`** → proceed to step 3.
   - **`expired`** → skip the push, surface a one-line reminder in
     the Step 6 recap: *"CVE-tool authenticated session expired —
     re-run the adapter's setup entrypoint (for the Vulnogram
     adapter, `vulnogram-api-setup`) to restore automatic push;
     using manual-paste hand-off this run."* Fall through to the
     manual-paste hand-off variant for any 5c comment work below.
   - **`not-configured`** → skip the push silently. Not every
     operator runs the adapter-backed push path; that is fine,
     the manual-paste hand-off (via the
     `cve_authority.source_tab_url_template` link) still works.
     Fall through to the manual-paste hand-off variant for any 5c
     comment work below.

3. **Extract the regenerated JSON.** The
   [`generate-cve-json`](../../tools/cve-tool-vulnogram/generate-cve-json/SKILL.md)
   step in 5a embedded the JSON inside the tracker body between the
   `<!-- generate-cve-json: cve=<CVE> version=v1 -->` /
   `<!-- generate-cve-json:end ... -->` markers. Re-run the
   generator with `--stdout` (no `--attach`) into a temporary file,
   or extract from the body via `awk` between the markers — either
   yields a byte-identical payload because the generator is
   deterministic. Conventional path:
   `/tmp/cve-<CVE-ID>-<N>.json`.

4. **Push the update through the adapter's `push_update` method.**
   Invoke `push_update(cve_id, fields, state_transition=None)` per
   [`tools/cve-tool/README.md`](../../tools/cve-tool/README.md).
   For the Vulnogram adapter the wire-level entrypoint backing the
   method is `vulnogram-api-record-update`:

   ```bash
   uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api vulnogram-api-record-update \
     --cve-id <CVE-ID> --json-file /tmp/cve-<CVE-ID>-<N>.json
   ```

   The `state_transition` argument is omitted here — the JSON
   already carries the generator-computed state field, and any
   adapter whose tool embeds state inside the record body (the
   Vulnogram adapter does) will write it as part of the same
   `push_update` call. Adapters whose tool requires a separate
   state-flip API call perform that flip internally; the contract
   keeps the call atomic from the skill's point of view.

   Capture the call's exit code and `stdout` / `stderr`:

   - **`exit 0`** → push succeeded. Record the ISO-8601 timestamp
     (`PUSH_TIMESTAMP`); the Step 5c comment work uses the
     **OAuth-pushed variant** of the relevant template; the Step 6
     recap includes *"CVE record auto-pushed to the CVE tool at
     `PUSH_TIMESTAMP`."* (for the Vulnogram adapter, name it in the
     recap as *"auto-pushed to Vulnogram"*).
   - **`exit ≠ 0`** → push failed. Surface the error verbatim in
     the Step 6 recap and **fall back** to the manual-paste hand-off
     for the Step 5c comment work. Do **not** retry on the same
     sync run — a transient HTTP error or a schema rejection is
     better surfaced once and re-tried on the next sync (after
     either Gmail-side or body-side state has settled).

5. **Idempotence note.** The contract requires `push_update` to be
   idempotent: re-posting the same `fields` dict on a subsequent
   sync is a no-op on the underlying tool's side (the Vulnogram
   adapter's upsert endpoint satisfies this naturally). The sync
   skill does not need to short-circuit "already pushed this JSON"
   — every successful sync run that re-regenerated the JSON should
   re-push to keep the record byte-identical to the tracker body.

6. **Verify the state advance landed (`allocated` → `review-ready`
   gate).** When step 4 above succeeded **and** the JSON pushed
   included a state field set to the adapter-native equivalent of
   `review-ready` (for the Vulnogram adapter, that is
   `body.CNA_private.state = "REVIEW"`), immediately call the
   adapter's `fetch_current_state(cve_id)` method to confirm the
   state actually advanced. For the Vulnogram adapter the
   wire-level entrypoint backing the method is
   `vulnogram-api-record-fetch`:

   ```bash
   uv run --project <framework>/tools/cve-tool-vulnogram/oauth-api vulnogram-api-record-fetch \
     --cve-id <CVE-ID> --jq '.body.CNA_private.state'
   ```

   *(If the adapter's standalone fetch entrypoint is not yet
   available on the operator's machine — the Vulnogram adapter's
   `vulnogram-api-record-fetch` CLI was added together with this
   gate; see [`tools/cve-tool-vulnogram/oauth-api/README.md`](../../tools/cve-tool-vulnogram/oauth-api/README.md)
   — fall back to extracting the state from the `push_update`
   call's response envelope, which the contract requires to
   include the saved state.)*

   The contract specifies that `fetch_current_state` normalises
   the underlying tool's native state token onto the generic verbs
   (`allocated`, `review-ready`, `publish-ready`, `public`,
   `retracted`, `unknown`). Three outcomes:

   - **`review-ready` or any later state (`publish-ready` /
     `public`)** → state-gate clear. Step 5c picks the
     OAuth-pushed hand-off variant and Step 4 of the *Reconcile*
     flow posts / PATCH-flips the RM hand-off comment. Step 6
     recap notes *"CVE record state auto-promoted to
     `review-ready` at `PUSH_TIMESTAMP`."* (for the Vulnogram
     adapter, named-example aside: *"i.e. `DRAFT` → `REVIEW` in
     the underlying record"*).
   - **`allocated`** → state-gate NOT cleared. Surface the
     specific reason: the most common case is one of the body
     fields was empty so the JSON did not include
     `state = "review-ready"` in the first place (Stage 1 of the
     two-stage gate caught this); the other common case is that
     a body field carried a value the CNA schema rejected
     silently (the upsert saved fields it could parse but did not
     advance the state). Either way, **do not post the RM
     hand-off comment**. Fire the *Remediation-developer
     fill-fields comment* instead per the dedicated Step 2b
     bullet, and surface the state-gate-not-cleared blocker in
     the Step 6 recap.
   - **Fetch failed (transient HTTP error, session expired
     between push and fetch, or the adapter returned `unknown`)**
     → conservative fallback: surface the fetch failure as a
     blocker, post nothing on the RM-hand-off front this run,
     and retry the verification on the next sync.

## Step 5c — Reconcile the release-manager hand-off comment

The Step 12 (`pr merged` → `fix released`) **hand-off comment** and
the Step 14 (advisory archived) **publication-ready notification**
both come in two variants. The template files live under
`tools/<cve-tool>/` — the adapter directory named by
`cve_authority.tool` in `<project-config>/project.md` — so each
adapter ships variants tuned to its own copy-paste surface and its
own automated push path:

| Variant | Template | When |
|---|---|---|
| Manual-paste (today's default) | `tools/<cve-tool>/release-manager-handoff-comment.md`, `tools/<cve-tool>/release-manager-publication-comment.md` (for the Vulnogram adapter: [`tools/cve-tool-vulnogram/release-manager-handoff-comment.md`](../../tools/cve-tool-vulnogram/release-manager-handoff-comment.md), [`tools/cve-tool-vulnogram/release-manager-publication-comment.md`](../../tools/cve-tool-vulnogram/release-manager-publication-comment.md)) | Step 5b skipped (`expired` / `not-configured`) or the push failed |
| OAuth-pushed | `tools/<cve-tool>/release-manager-handoff-comment-oauth-pushed.md`, `tools/<cve-tool>/release-manager-publication-comment-oauth-pushed.md` (for the Vulnogram adapter: [`tools/cve-tool-vulnogram/release-manager-handoff-comment-oauth-pushed.md`](../../tools/cve-tool-vulnogram/release-manager-handoff-comment-oauth-pushed.md), [`tools/cve-tool-vulnogram/release-manager-publication-comment-oauth-pushed.md`](../../tools/cve-tool-vulnogram/release-manager-publication-comment-oauth-pushed.md)) | Step 5b's `push_update` succeeded this run |

Both variants of each comment carry the **same marker** on line 1
(`<!-- apache-magpie: release-manager-handoff v1 -->` for the
hand-off, `<!-- apache-magpie: release-manager-publication-ready v1 -->`
for the publication-ready). Idempotency detection still keys on the
marker — the variant choice does not get its own marker. When the
marker is found on the tracker, the existing comment's body is
PATCH-edited in place to the variant that matches the current sync
run's outcome (the rationale mirrors the rollup-comment PATCH-don't-
post rule: a fresh duplicate comment buries the timeline). Concrete
rules:

- **First-time hand-off** (no existing comment, label transition
  fires this run) → POST the appropriate variant.
- **Subsequent sync, `push_update` succeeded this run** → PATCH the
  existing comment to the OAuth-pushed body (refreshing the
  `PUSH_TIMESTAMP` placeholder). If the existing comment is already
  the OAuth-pushed variant, the only material change is the
  timestamp — still PATCH; the timestamp is the audit trail.
- **Subsequent sync, `push_update` failed (or was skipped)** →
  PATCH the existing comment to the manual-paste variant. The RM
  sees a fresh "please paste" ask the moment the auto-push stops
  working, which is the right escalation.
- **Subsequent sync, no relevant transition fired and the JSON did
  not change** → no PATCH. Idempotency: marker present, body
  byte-identical, nothing to do.

The apply mechanic for both POST and PATCH lives in Step 4 — see
the *Release-manager hand-off comment* and *Publication-ready
notification comment* bullets there.

---
