<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — release-manager and fill-fields comments

Part of the Step 2b lookup in [`signals-to-actions.md`](signals-to-actions.md), which says when to read this file.

- **Remediation-developer fill-fields comment** — when mandatory CVE body fields are not yet populated,
  propose posting (or PATCH-updating) a comment tagging the **remediation developer** with the concrete list of missing fields.
  The tracker stays assigned to the remediation developer; the release-manager hand-off is **not** fired until the gate clears.

  **This is its own first-class comment, not a rollup entry**: like the RM hand-off, it is a call to action.

  **Trigger — two firing points**:

  1. **At the `pr created` → `pr merged` transition (Step 11)** — when sync proposes that label swap,
     check whether all six mandatory body fields are populated
     (*CWE*, *Affected versions*, *Severity*, *Reporter credited
     as*, *Short public summary for publish*, *PR with the fix*).
     An empty *Reporter credited as* passes when the status rollup records a no-finder decision
     (reporter opt-out, or no finder to name, per the [finder-credit policy](../../../../tools/cve-tool-vulnogram/finder-credit-policy.md)).
     If any field is empty / `_No response_` without that exception, propose the fill-fields comment with that field list.
     The issue stays assigned to the remediation developer (in the common case also the fix-PR author and current assignee).
     **Do not propose any RM-related action at Step 11**; that belongs to Step 12.
  2. **At the `pr merged` → `fix released` transition (Step 12)** — after Step 5b's push attempt, check the CVE record state in Vulnogram.
     If it is still `DRAFT` for any reason (a body field still empty, the push blocked,
     or the push landed but the state did not advance because the JSON failed CNA-schema validation),
     **re-fire** the fill-fields comment with the refreshed list of what is still blocking.
     **Do not** fire the RM hand-off, flip the label to `fix released`, or swap the assignee — those all gate on `state == REVIEW`.
     A later sync that finds the state promoted to `REVIEW` clears the gate and fires the RM hand-off then.

  **Idempotency + PATCH-in-place**. Same shape as the hand-off
  comment: scan for the marker
  ```html
  <!-- apache-magpie: remediation-developer-fill-fields v1 -->
  ```
  on line 1 of each comment. Three outcomes:

  - **No marker found** — POST a fresh comment.
  - **Marker found, current body matches the body the skill would
    render this run** — no-op; surface as
    *"fill-fields comment already posted on `<comment-url>` and
    the missing-fields list is unchanged (skipping)"*.
  - **Marker found, current body does NOT match** (typically the remediation developer filled some, but not all, fields between runs) —
    PATCH-edit the existing comment with the refreshed list.

  **Body source.** `tools/<cve-tool>/remediation-developer-fill-fields-comment.md`
  (for Vulnogram:
  [`tools/cve-tool-vulnogram/remediation-developer-fill-fields-comment.md`](../../../../tools/cve-tool-vulnogram/remediation-developer-fill-fields-comment.md)).
  It has no OAuth-pushed / manual-paste variants: the remediation developer fills body fields and never sees the API-push state.

  **Resolving placeholders.** The placeholders it shares with the hand-off comment
  (`CVE_ID`, `RECORD_URL`, `TRACKER_URL`, `SECURITY_LIST`,
  `SECURITY_LIST_DOMAIN`, `FRAMEWORK_README_URL`,
  `FRAMEWORK_SYNC_SKILL_URL`) resolve the same way. Plus two unique placeholders:

  - `REMEDIATION_DEVELOPER_HANDLE` — read from the tracker's *Remediation developer* body field.
    When it carries a `Full Name (@handle)` line, extract the `@handle` token.
    When only the name is set, fall back to the fix-PR author's `@`-handle (`author.login` from the Step 1b PR fetch — no extra call)
    and propose adding the `@handle` to the body field on the same pass, so the next sync resolves cleanly.
  - `MISSING_FIELDS_LIST` — Markdown bullets, one per empty mandatory field, shaped
    `- **<Field name>** — currently the
    empty placeholder; <one-line hint on how to fill it>`.
    The hint comes from the project's *Issue-template fields* docs;
    for Vulnogram-based projects it is the field's `description` from
    `<project-config>/.github/ISSUE_TEMPLATE/issue_report.yml`.

  **Apply mechanic.** See the *Remediation-developer fill-fields comment* bullet in Step 4; POST vs PATCH is decided by the marker check above.

  **Recap.** Surface the comment URL (new or PATCH-edited) in the recap (Step 6), plus a one-line note *"hand-off to RM blocked on N
  field(s); fill-fields comment posted/refreshed"*.

- **Release-manager hand-off comment** — when this pass proposes the `pr merged` → `fix released` label swap (Step 12),
  **also** propose posting a separate hand-off comment that walks the release manager through Steps 13–15 end-to-end on the tracker page,
  without the rollup or external docs.

  **This is its own first-class comment, not a rollup entry**: it is the release manager's one-shot orientation,
  which a `<details>` block would bury.

  **Trigger — gated on `state == REVIEW`.** Fires *exactly once* per tracker, at the pass that proposes `pr merged` → `fix released`
  **AND** finds the CVE record state in Vulnogram is `REVIEW`
  (verified after Step 5b's push attempt — the push includes the `body.CNA_private.state =
  "REVIEW"` advance when all six mandatory body fields are populated).
  When the record is still `DRAFT` after the push attempt, **do not** fire this hand-off;
  fire the *Remediation-developer fill-fields comment* instead and leave the tracker assigned to the remediation developer.
  **The RM must never receive this hand-off while the record is in `DRAFT`** — the template body asserts it, so the RM can recognise a misfire.
  Do not propose it earlier than Step 12, nor again once posted (idempotency check below).

  **Idempotency + variant edit-in-place.** Before proposing, scan
  the issue's existing comments for the marker
  ```html
  <!-- apache-magpie: release-manager-handoff v1 -->
  ```
  exactly. It is on line 1 of the body, so a literal prefix match over the comments the Step 1a fetch already returned detects it without another call.
  Three outcomes:

  - **No marker found.** Propose a fresh POST of the appropriate
    variant (per Step 5c's decision).
  - **Marker found, current body matches the variant the skill
    would render this run.** No-op; surface as *"hand-off comment
    already posted on `<comment-url>` and matches the current
    variant (skipping)"* in the observed-state dump.
  - **Marker found, current body does NOT match the variant the
    skill would render this run.** Propose a PATCH-in-place (rewrite the body to the current variant).
    Common cases: a previous sync posted the manual-paste variant and this sync's OAuth push succeeded → flip to the OAuth-pushed variant;
    or vice-versa (Vulnogram token expired between sync runs).
    The PATCH keeps the comment URL, timeline position and delivered notifications.

  The `security-pages-checklist v1` checkbox is RM state, not
  template content: compare bodies with that item's box
  normalised to `- [ ]`, so a tick alone never counts as a
  mismatch, and when a PATCH does go out, carry a ticked
  `- [x]` over into the re-rendered body; resetting it would re-fire the security-pages reminder for a done step.

  **Body source.** The comment body comes from the project's configured CVE tool, in two **variants** picked by Step 5c:

  - **OAuth-pushed variant** —
    `tools/<cve-tool>/release-manager-handoff-comment-oauth-pushed.md`
    (for Vulnogram:
    [`tools/cve-tool-vulnogram/release-manager-handoff-comment-oauth-pushed.md`](../../../../tools/cve-tool-vulnogram/release-manager-handoff-comment-oauth-pushed.md)).
    Used when Step 5b's `vulnogram-api-record-update` succeeded
    this sync run.
  - **Manual-paste variant (today's default)** —
    `tools/<cve-tool>/release-manager-handoff-comment.md`
    (for Vulnogram:
    [`tools/cve-tool-vulnogram/release-manager-handoff-comment.md`](../../../../tools/cve-tool-vulnogram/release-manager-handoff-comment.md)).
    Used when Step 5b skipped (no credentials, expired session)
    or the push failed.

  Both variants carry the same marker on line 1.
  The substitutions are listed in each template's HTML-comment header (the OAuth-pushed variant additionally takes `PUSH_TIMESTAMP`).
  Do not fork or paraphrase the template body: load it verbatim, substitute the placeholders, post or PATCH per the idempotency rules above.

  **Resolving placeholders.** All values come from configuration or the tracker, so there is no free-form drafting:

  - `CVE_ID` — from the tracker's *CVE tool link* body field.
  - `RM_HANDLE` — the three-source cascade in Step 2c (`release-trains.md` / Release Plan wiki / dev@ `[RESULT][VOTE]` thread);
    the same lookup the assignee swap uses — do it once and reuse.
  - `SECURITY_LIST`, `USERS_LIST`, `ANNOUNCE_LIST` — from
    [`<project-config>/project.md`](../../../../<project-config>/project.md#mailing-lists).
  - `RECORD_URL`, `SOURCE_TAB_URL`, `EMAIL_TAB_URL` — substitute `<CVE-ID>` into
    `cve_tool_record_url_template` (from project.md): as is for `RECORD_URL`, with
    `#source` / `#email` appended for the others, per [`tools/cve-tool-vulnogram/record.md`](../../../../tools/cve-tool-vulnogram/record.md#record-urls).
    Every link that sends a reader to the record uses `RECORD_URL`; `SOURCE_TAB_URL` is only the manual-paste target.
  - `JSON_ANCHOR_URL` — the deep link `generate-cve-json` prints on every regen
    (the `https://github.com/<tracker>/issues/<N>#cve-json--paste-ready-for-<cve-id-slug>` anchor).
  - `ARCHIVE_SCAN_URL` — `ponymail_public_search_url_template` from project.md, parameterised with the CVE ID.
  - `FRAMEWORK_RECORD_MD_URL`, `FRAMEWORK_SYNC_SKILL_URL`, `FRAMEWORK_README_URL` — absolute GitHub URLs into `apache/magpie` `main`,
    since the gitignored snapshot at `<adopter-tracker>/.apache-magpie/` does not render through the parent-repo viewer.
  - `CANNED_RESPONSES_URL` — absolute GitHub URL into the tracker
    repo's `<project-config>/canned-responses.md`.
  - `SECURITY_PAGES_URL` — the `security_pages_url` key from
    [`<project-config>/project.md`](../../../../<project-config>/project.md#repositories).
    When the key is unset, render the link text without the link:
    `[security pages](SECURITY_PAGES_URL)` becomes plain
    `security pages`. This is the one sanctioned deviation from the
    verbatim template, and the proposal flags the missing key.

  **Apply mechanic** — see the *Release-manager hand-off comment* bullet in Step 4:
  a fresh `gh issue comment` (first hand-off) or a `gh api -X PATCH` on the existing comment's REST id (variant flip).
  Neither path PATCHes the rollup.

  **Recap.** Surface the comment URL (new or PATCH-edited) in the recap (Step 6).
  After a PATCH, note which variant the body now carries
  (*"flipped to OAuth-pushed variant after this sync's auto-push succeeded"* or vice-versa).

- **Publication-ready notification comment** — when this pass proposes populating the *Public advisory URL* body field
  (Step 14 — the *Advisory archived on `<users-list>`* row of the Step 1d table),
  **also** propose a separate publication-ready notification comment telling the release manager that the archive URL is captured,
  the JSON is regenerated with it as a `vendor-advisory` reference, and the final paste + `READY` → `PUBLIC` move is unblocked.

  **Why a second comment instead of one comment with two states.**
  The Step 12 hand-off ends at `READY` and points to this follow-up for `PUBLIC`;
  a fresh comment gives the RM a dated surface and a working `@`-mention.

  **Trigger.** Fires *exactly once* per tracker, at the pass that proposes the *Public advisory URL* body update —
  not earlier (the URL is not captured yet), not repeatedly (idempotency check below).

  **Idempotency.** Before proposing, scan the issue's existing
  comments for the marker
  ```html
  <!-- apache-magpie: release-manager-publication-ready v1 -->
  ```
  exactly. If a comment carrying it exists, do not re-post — surface as *"publication-ready comment already posted on
  `<comment-url>` (skipping)"* and move on.

  **Body source.** Same load-from-tool-doc model as the hand-off comment:
  `tools/<cve-tool>/release-manager-publication-comment.md` (for
  Vulnogram:
  [`tools/cve-tool-vulnogram/release-manager-publication-comment.md`](../../../../tools/cve-tool-vulnogram/release-manager-publication-comment.md)).
  Placeholders substituted: `CVE_ID`, `RM_HANDLE`, `ARCHIVE_URL`
  (the just-captured archive URL), `RECORD_URL`,
  `JSON_ANCHOR_URL`, `CVE_ORG_URL`
  (`https://www.cve.org/CVERecord?id=<CVE-ID>`).

  **Apply mechanic** — same as the hand-off comment: a fresh
  `gh issue comment`, surfaced in the recap.
