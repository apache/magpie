<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2b — Proposed changes (signal-to-action lookup table)

> Extracted from [`SKILL.md`](SKILL.md) so subagents that only need
> this slice can load just this file. Loaded automatically when the
> orchestrator (or a subagent) is in the matching step.

The signal-to-action lookup table: each Step 1d signal and the body-field update, label change, status comment or draft email it translates to.

---

## 2b. Proposed changes

Each proposed change is a **numbered item** that says *what* will change and *why*.
Group them by category:

- **Labels to add / remove** — e.g. *"remove `needs triage`; add `<scope-a>`"*. Reason: one scope label is required by the process once triage is complete.

  **Release-vote label (opt-in, ASF projects only).** When release-vote gating is enabled (`[workflow].release_vote_gating = true` in the CVE-JSON generator's config),
  Step 1h's detection adds two proposal shapes:

  - *Add* the configured `rc voting` label (default `"rc voting"`) when a matching open `[VOTE]` thread was detected on `<dev-list>` and the tracker is in the `pr merged` window.
    Quote the PonyMail thread URL as the rationale so the team can spot-check the match —
    *"detected active vote thread: `<thread-url>` carrying version X.Y.Z, matches fix-PR milestone"*.
  - *Remove* the `rc voting` label when the existing `pr merged` → `fix released` transition fires (the release shipped),
    as part of that same numbered item, so the user confirms one combined label flip.
    Sync does not detect *failed* votes; the team removes the label by hand when it re-cuts an RC.

  Projects that did not opt in never see the label proposed, added, or referenced,
  and the generator's legacy *"ready ⇒ REVIEW"* behaviour applies.
- **Milestone** — propose the matching release milestone on the issue.
  The scope → milestone-format mapping, and the rule that a merged PR's own milestone wins over the release-train default, are in
  [`<project-config>/milestones.md`](../../../../<project-config>/milestones.md);
  the release-train default used when no PR milestone is available is in
  [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md).

  **If the milestone does not yet exist**, or **when a sync pass closes a tracker** (the Step 15 terminal transition — cve.org reports PUBLISHED),
  read [`milestone-create-close.md`](milestone-create-close.md) before proposing the create or close item.

- **Assignees** — when a fix PR exists in `<upstream>` (found in Step 1b or named in the *"PR with the fix"* body field)
  **and the PR author is a member of the project security team**, **propose setting the tracking issue's assignee to that PR author**,
  the natural owner for the rest of the process.
  Membership: the handle appears in the security-team roster in
  [`<project-config>/release-trains.md`](../../../../<project-config>/release-trains.md);
  when in doubt, `gh api repos/<tracker>/collaborators --jq '.[].login'` is the authoritative check —
  run once per run and reused for every membership check below;
  **every collaborator counts regardless of their permission level** (read, triage, write, maintain and admin are all valid).

  If the PR author is **not** on the roster (e.g. an external contributor who submitted the fix via the public process), do **not** assign them.
  Leave the assignee empty or propose a security-team member already engaged in the discussion.

  **Sign-up (volunteer) branch.** When a person has **signed up** to own the issue — the *volunteer-owner* signal from
  [`gather.md` Step 1d](gather.md#1d-mine-comments-and-mail-messages-for-actionable-signals)
  (*"I'll take this"*, *"assign me"*, *"I can work on the fix"*, *"I'll drive the advisory"*) —
  **propose setting that person as the assignee**, subject to the **same project-member gate** as the PR-author branch
  (roster, or the collaborators list already fetched this run; every permission level counts).
  On a private tracker a non-collaborator **cannot see the issue**, and GitHub silently drops assignee writes for them,
  so a volunteer who is **not** a project member is recorded in the proposal as context but **not** assigned — surface *"`<handle>`
  volunteered but is not a `<tracker>` collaborator — invite them
  first?"* and let the user decide. Precedence and idempotency:

  - When both a sign-up and a fix-PR author exist, the **PR author wins** (the in-flight fix is the stronger signal);
    record the volunteer as context only.
  - Propose the sign-up assignment only when the issue has **no assignee**.
    Never override an existing assignee on a volunteer signal — that is a hand-off, which only happens at the `fix released` transition below.

  Also propose clearing a stale assignment if the person is no longer active on the issue,
  and propose self-assigning a team member only if the user explicitly asks.

  The assignee hand-off from the remediation developer to the release manager at the `fix released` transition,
  and its repair on a tracker already at `fix released`, is in [`release-manager-comments.md`](release-manager-comments.md), read per the release-manager comments item below.
- **Issue title hygiene** — the issue title ships verbatim into the CVE record's `containers.cna.title` (read by `generate-cve-json` on every regen),
  and from there into the published advisory and `cve.org`.
  **On every sync pass**, run the title-strip cascade
  [`security-cve-allocate` applies at allocation time](../cve-allocate/title-normalize.md#step-2--compute-the-cve-ready-title) —
  strip leading/trailing project-name tokens (e.g. ``<project>:``, ``in <project>``, ``(<project> X.Y)``),
  internal split-markers (``(split from #NNN)``), report-form classifiers (``[Security Report]``, ``[Security Issue]``),
  external-tracker IDs (``[GHSA-...]``, ``(ZDRES-...)``, ``(HUNTR-...)``, ``(GHSL-...)``)
  and version-noise suffixes (``(v3.2.1)``, ``(3.x)``).
  When the cascade would change the title, propose the diff as a numbered Step 2b item;
  on confirmation, ``gh issue edit <N> --title "<cleaned>"``, then regen + push CVE JSON so the record's `title` picks up the cleaned value.
  **Preserve stripped context as audit trail** — split-from references, GHSA IDs and report-form classifiers help the team navigate sibling reports and reviewer threads:
  move them into the issue body (a `### Related references` section) or into the rollup as an audit entry; never silently drop them.
  Titles drift after allocation (manual edits, sibling-tracker splits, GHSA-relay imports appending the GHSA ID),
  so the cascade re-runs on every sync even when no other body update is proposed;
  the Step 1d row *"The issue title contains adopter-specific or internal noise"* is its detector.
- **Description fields** — if the issue body is missing any field the release manager will need
  (CWE, product, affected versions, severity, CVE ID, credits, links to PRs, short public summary for publish), propose a patched description.
  Show the full replacement body in the proposal, not a diff.
  This is the whole-body write in Step 4; a field whose `### ` heading already exists
  and only needs a value is a per-field `body-field-set` item instead.

  **Every `_No response_` field must be explicitly reviewed in every sync
  run.** Before presenting the proposal, scan the body for `_No response_` placeholders.
  For each, either propose a concrete value (if the discussion, mail thread, PR or GHSA provides enough information)
  or flag it as *"still `_No response_` — needs \<what\> before it can be filled"*.
  Do not leave fields empty silently across sync runs: the release manager at Step 13 needs **every** field filled,
  and the `pr merged → fix released` transition is gated on the six mandatory fields.
  An empty *Reporter credited as* is not a gap when the rollup records a no-finder decision
  (the gate rows in [`gather.md`](gather.md#1d-mine-comments-and-mail-messages-for-actionable-signals)); say so instead of flagging it.

  **Agent-derivable fields — propose high-confidence values proactively.**
  Two mandatory fields can be derived from artefacts already in the sync's evidence pool.
  This is the allow-listed set for auto-proposal whenever the field is empty or `_No response_`:

  - **CWE** — map the patch to a CWE class (e.g. a missing-auth-check fix → CWE-287,
    untrusted-input-into-SQL fix → CWE-89, path-traversal guard fix → CWE-22).
    **Propose only when the patch is unambiguous**; when several CWE classes fit, flag the ambiguity instead of guessing.
    Cite the file path(s) and line range(s) that drove the mapping.

  - **Affected versions** — derive from the `<upstream>` PR's milestone / fix-version metadata mapped to the per-scope convention
    (see [`<project-config>/scope-labels.md` — *Affected versions
    convention by scope*](../../../../<project-config>/scope-labels.md#affected-versions-convention-by-scope)).
    Propose only when the milestone uniquely determines the range;
    flag ambiguity (e.g. multiple backport milestones with partial coverage) rather than guessing.
    **Always emit the proposed value wrapped in backticks** (e.g. `` `>= X.Y.Z, < A.B.C` ``, `` `< A.B.C` ``);
    see the *"`Affected versions` body field has a value but it is not backtick-wrapped"* row in the Step 1d signal table
    (raw `>=` renders as a blockquote and form-UI edits silently lose the prefix).

  All other mandatory fields stay on the *external-signal* path:
  propose values only when the discussion, mail thread, PR, or GHSA
  provides enough information — never guess them.

  **"Short public summary for publish" must include user-facing
  instructions.** This field becomes the published CVE description.
  Beyond stating the vulnerability in one or two sentences, it tells users **what to do**:
  the fixed version to upgrade to, mitigations for users who cannot upgrade immediately,
  and the CWE class (allowed — CWE is not embargoed once the advisory ships).

  **Validate this on every sync pass that proposes a body-field update or a JSON regen**, not only at the `pr merged → fix released` boundary.
  A summary that names the vulnerability but lacks the upgrade-target version
  (e.g. *"upgrade to the version that contains the fix"* without naming `3.3.0`) is a defect;
  propose tightening it before the regen lands in the embedded JSON and the next push to the CVE record.

  **The summary must also state the triggering conditions** — the reader asks *"does this affect us?"*,
  and the answer comes from the trigger context, not the bug mechanism.
  The summary makes these three unambiguous, one sentence each, in any order:

  1. **Who** — the attacker role / capability required (e.g. *"an
     authenticated UI user with `Op` permissions"*, *"a Dag author"*,
     *"a partner with write access to the source bucket"*, *"a worker
     holding a valid Execution-API JWT"*, *"a user able to reach the
     login endpoint"*).
  2. **When / configuration** — the deployment shape / config /
     feature that has to be active for the issue to apply (e.g.
     *"when `[opensearch] host` embeds credentials"*, *"when the
     Kubernetes executor is configured"*, *"when the
     `<product>-<component>` auth manager is enabled"*,
     *"when DAGs with assets are configured to materialise via the
     REST API"*).
  3. **Action / surface** — the step the attacker takes against
     which surface (e.g. *"follows a crafted `next=` redirect URL"*,
     *"uploads an object containing `..` path segments"*, *"reads
     task logs in the UI"*, *"PATCHes the deferred-state endpoint
     with crafted `next_kwargs`"*).

  When the field is accurate but missing one of (who / when / action), propose adding it on the
  same sync pass as the upgrade-target tightening.

  Worked example shape (a single CVE):

  > *"An authenticated UI user with permission to read DAGs could
  > craft a `next=` parameter on the login route that bypassed
  > `is_safe_url`, redirecting other users to an attacker-controlled
  > origin after authentication. Affects deployments where the
  > webserver is reachable by untrusted users. Users are advised to
  > upgrade to `<product>` 3.2.2 or later."*

  Sentence one names the attacker (*authenticated UI user*), the action (*crafts `next=`*) and the surface (*login route*);
  sentence two the configuration (*webserver reachable by untrusted users*); sentence three the upgrade ask.
  When the carrier release is known (the fix PR's milestone is set), name it verbatim —
  ``<product> 3.3.0 or later``,
  ``<product>-<component> 11.2.0 or later``,
  ``<product> 1.18.0 or later``, etc.
  When it is not yet known (early `pr created`, no PR milestone), keep the placeholder but flag the gap in Step 2c so the next sync after milestone-set catches it.
  The Step 1d row *"`Short public summary for publish` is populated but does not name a concrete upgrade-target version"* is the detector.

  **Incomplete-fix-to-another-CVE: the summary must name the prior
  CVE *and* tell users who already applied that fix to apply this
  one too.** When the tracker is an *incomplete-fix follow-up* to a previously-published CVE,
  the summary must additionally:

  1. Name the prior CVE explicitly (``<project> previously
     released a fix for `<PRIOR-CVE-ID>` that addressed the
     `<other-package>` side of the same vulnerability class``).
  2. State that the **previous fix did not cover the current
     product / surface** (e.g. ``The previous fix covered the
     `<sibling-package>` package; the `<current-package>` package
     was not patched at the time``).
  3. Tell users who already applied the prior CVE's fix to **also
     apply this one** (``Users who already upgraded
     `<sibling-package>` per the `<PRIOR-CVE-ID>` advisory should
     additionally upgrade `<current-package>` to <X.Y.Z> or later
     — the two fixes are complementary, not duplicates``).

  Otherwise a reader assumes *"I already applied the earlier fix; this one is a duplicate"* and misses the second upgrade.

  **Detection signals** (any one triggers the cross-CVE summary shape):

  - The `Short public summary` already mentions the prior `CVE-YYYY-NNNNN` token but lacks the *"users who applied the prior fix should also..."* clause.
  - The rollup carries a *"sibling tracker"* / *"split for scope clarity"* / *"follow-up to `<PRIOR-CVE-ID>`"* entry.
  - The body or title mentions *"incomplete fix for `<CVE-ID>`"*, *"follow-up to `<CVE-ID>`"*, or *"split from"* a sibling tracker whose CVE is already public;
    an *"incomplete fix for `<PRIOR-CVE-ID>`"* title parenthetical is stripped by the title-strip cascade, but the relationship is preserved in body / rollup.
  - The CVE record's `affected[]` names a different `packageName` than the prior CVE's record, AND the prior CVE is on the same root-cause class.

  When any signal fires, propose the cross-CVE summary expansion in the same Step 2b body-field update set.
  Do **not** emit a summary that omits the cross-CVE / cross-product upgrade ask.

  **Special case for the "Security mailing list thread" field — leave
  it alone.** It is the internal link to the private `<security-list>` thread, expected to 404 outside the security team.
  **Do not scrub this field, do not replace the URL with a textual note, do not "clean it up".**
  `generate-cve-json` never exports it to `references[]`.

  **The "Public advisory URL" body field** carries the archived public advisory URL on
  `<mail-archive-url>/list.html?<users-list>` (or `<announce-list>`).
  Empty until Step 13 — the release manager fills it in **after** the advisory email has been sent and archived.
  Every sync run must:

  1. If `announced - emails sent` is set and the field is still empty, **scan the public advisory archive for the CVE ID**:
     read [`advisory-url-capture.md`](advisory-url-capture.md) and follow it before proposing anything for this field.
  2. If the field is already populated, treat it as authoritative — no scan.
     Regenerate the CVE JSON attachment so the URL flows into `references[]` as `vendor-advisory`.
  3. The sync's responsibility ends when the label is `announced`.
     **Do not propose closing the issue** — closing is a Step 15 action for the release manager,
     who copies the attached CVE JSON into Vulnogram and closes the issue (no label changes).
  4. On subsequent sync runs, check whether the CVE record on `<cve-tool-url>/cve5/<CVE-ID>` has moved to PUBLISHED;
     when it has, propose closing the issue (do not update labels).
     This is the only place sync proposes closing an advisory-flow issue;
     earlier closes are only for closing dispositions (`invalid` / `duplicate` / `wontfix`) at Steps 5–6.

  The two-field split: [`AGENTS.md` § *CVE references must never point at non-public mailing-list threads*](../../../../AGENTS.md#cve-references-must-never-point-at-non-public-mailing-list-threads).

  **Special case for the `Severity` field — never propagate reporter-supplied
  CVSS scores.** A reporter's CVSS vector or qualitative label (*"Low"*, *"High"*, *"Critical"*), from the thread, a GHSA draft or the body,
  goes in the *observed state* as informational context (e.g. *"reporter estimated CVSS 4.0 = 7.2 per the GHSA"*), **never** as the proposed `Severity` value.
  The field stays `_No response_` until a security-team member scores it independently (in-thread or in an issue comment), then carries that score.
  The same applies to a self-assigned CWE. Rule and rationale:
  [`AGENTS.md` § *Reporter-supplied CVSS scores*](../../../../AGENTS.md#reporter-supplied-cvss-scores-are-informational-only--never-propagate-them).
- **Status transitions** — e.g. *"close the issue as invalid"*, *"add `Not yet
  announced` now that <upstream>#NNNN has merged"*, *"add `vendor-advisory
  ready` now that the users@ advisory URL has been captured — the release
  manager will copy the CVE JSON to Vulnogram and close the issue"*.

- **Project-board column.** Every tracker has exactly one `Status` option set on the Security-issues board, and it must match the issue's label-derived state;
  reconcile whenever labels and column disagree.
  The label + body-state → column mapping and the board URL are in
  [`<project-config>/project.md`](../../../../<project-config>/project.md#github-project-board);
  the `updateProjectV2ItemFieldValue` GraphQL recipe is in
  [`tools/github/project-board.md`](../../../../tools/github/project-board.md#write--move-a-tracker-to-a-different-column),
  invoked from the Step 4 apply list.

- **Draft email to the reporter** — **whenever the issue's status has changed since our last message to the reporter**,
  or the ball is in our court on the thread for another reason (a reporter question, a triage follow-up, a negative assessment),
  propose a Gmail draft (never a sent message): read [`reporter-drafts.md`](reporter-drafts.md) before drafting it.

- **Status update on the GitHub issue (`<tracker>`)** — **every status change is also recorded on the issue itself**, not only sent by email
  (rationale: [`docs/security/roles.md` — Recording status transitions on the tracker](../../../../docs/security/roles.md#recording-status-transitions-on-the-tracker)).

  **The status record lives in a single rollup comment, not a new
  comment per sync.** The first bot-authored comment on a tracker is the **rollup comment** (created by
  [`security-issue-import`](../issue-import/SKILL.md));
  every later pass — this skill, security-cve-allocate, security-issue-deduplicate, security-issue-fix — appends an *entry* to it instead of posting a fresh comment.
  Shape, summary conventions, upsert recipe and legacy-comment-folding rules:
  [`tools/github/status-rollup.md`](../../../../tools/github/status-rollup.md).
  Re-read it before composing the entry body — the zero-extra-spacing rule is load-bearing and easy to miss.

  **Standalone comments are reserved for release-manager
  instructions, plus the team nudge.** The rollup is the default surface for every sync output — status changes, label rationale, milestone moves, assignee swaps,
  reporter-draft notes, fix-PR links, CVE-review-comment surfacing, legacy-fold entries, recap pointers, blockers, *everything*.
  The **only** comments this skill posts outside the rollup are the team nudge (*Unanswered team question*, below) and the release-manager-directed call-to-action comments further down this list:
  the *Release-manager hand-off comment* (`pr merged` → `fix released`, Step 12)
  and the *Publication-ready notification comment* (*Public advisory URL* update, Step 14):
  they tell the RM to *do something next*, which a `<details>`-collapsed entry hides.
  Everything else goes into the rollup; do not invent a new standalone-comment shape because something "feels important enough".

  **Entry shape for a sync pass.** Emit the entry body below;
  `rollup-append` wraps it in the rollup's
  `<details><summary><YYYY-MM-DD> · @<author-handle> · Sync (<short headline>)</summary>` block:

  ```markdown
  **Sync <YYYY-MM-DD> — <one-sentence bold headline>.**

  - <Action 1: short, imperative, links only when load-bearing>
  - <Action 2>
  - <Action 3>

  **Next:** <one sentence on the expected next step>.

  <Reporter-notification line — one of the four options below.>

  <Full rationale — everything the auditor needs: verbatim reviewer
  comments, CVSS rationale, RM-attribution trail, label-transition
  reasoning, stale-draft flags, cross-links, prior-entry pointers.
  Flush-left, no leading spaces, no sub-`<details>` blocks.>
  ```

  The entry is collapsed inside `<details>`, so there is no line cap: write what the auditor needs, without padding.
  Each entry is *incremental* — what changed in this pass, what comes next; do not restate earlier entries.

  **Reporter-notification line options** (exactly one when applicable; omit when no reporter notification is meaningful):

  - *"Reporter has been notified on the original mail thread."* —
    when a status-update draft has been created in the same sync.
  - *"No reporter notification needed (reporter is on the security
    team)."* — only if the real reporter is themselves a member of
    the security team and is already in the loop.
  - *"Reporter notification still pending — see draft `<draftId>`."*
    — if a draft was created but the user has not yet sent it.
    **Before emitting this line**, call `mcp__claude_ai_Gmail__list_drafts` and confirm `<draftId>` is in the result.
    If it is gone, flip to *"Reporter
    draft `<draftId>` is no longer in Drafts — sent or
    discarded."* — never assert "still pending" without checking.
    This applies on **every** sync that emits the line, including the one that created the draft,
    per the [verify-before-claim rule](../../../../tools/gmail/operations.md#verify-before-claim--never-assert-a-draft-is-still-pending-without-checking).

  **Summary action-label for a sync pass** — see the table in
  [`status-rollup.md`](../../../../tools/github/status-rollup.md#summary--action-labels).
  Use `Sync (<one-phrase headline>)` for an ordinary pass,
  `Sync (Step 4 escalation)` for an escalation, or
  `Reformat (N legacy comments folded)` when this pass's primary
  purpose is migrating pre-rollup bot comments (see below).

  **Apply recipe** — `rollup-append` (the Status-rollup comment item in
  [Step 4](apply-and-push.md#step-4--apply-confirmed-changes)).
  On a tracker that already carries a rollup (the common case) it edits the existing rollup, not a fresh `gh issue comment`;
  on a tracker with **no rollup yet** (pre-dating the convention) the same call creates it,
  and the pass also runs the legacy-fold sub-step below so the new rollup absorbs every pre-existing bot comment.

  **Fold legacy bot comments into the rollup.** Every sync pass runs a legacy-fold sub-step.
  Step 1d's comment-mining scan surfaces every pre-rollup bot comment using
  [`status-rollup.md` — Detecting a legacy bot comment](../../../../tools/github/status-rollup.md#detecting-a-legacy-bot-comment)
  (content-anchored sweep: author on the security-team roster **and**
  body starts with one of `**Sync `, `**Status update`, `**Merged `,
  `**Closing as duplicate`, `**Split for scope clarity`, `**Imported
  on `, `**Process-step escalation`, `**Allocated CVE`, or the
  bare-text `Sync status (` / `Sync YYYY-MM-DD` / `Status update`
  legacy prefixes, or a content tell like `security-issue-sync
  skill`). For each hit, the Step 2 proposal carries a numbered
  item: *"fold legacy comment `<url>` (`<YYYY-MM-DD>`, first line
  <first-line>) into the rollup as a `<Action>` entry, then
  delete the original"*. On user confirmation, apply each with one
  `rollup-fold` call, oldest first (the Fold legacy comments item in
  [Step 4](apply-and-push.md#step-4--apply-confirmed-changes)):

  ```bash
  uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-sync rollup-fold <N> <comment-id> "<derived-Action>"
  ```

  The tool keeps the legacy comment's `createdAt` date and author in the summary,
  left-trims every line (a single stray leading space wrecks markdown rendering inside `<details>`),
  and deletes the original only after the append lands.
  Never touch a comment authored by someone outside the security-team roster (that is reporter discussion, not bot noise).

  When the same pass also writes a regular sync entry, the legacy-fold entries are appended **first** (chronologically), the sync entry last.
  Tag the pass's own summary `Reformat (N legacy comments folded)` when the fold is the primary action;
  otherwise use `Sync (<headline>)` and mention the fold count in the entry body.

  **Before emitting any rollup body — run the zero-whitespace
  self-check.** `<details>` blocks break silently when any line inside carries leading whitespace
  (the tool supplies the blank line after `<summary>`, not the entry body's indentation):
  the entry renders as a single preformatted block and hides every link.
  Re-read [`status-rollup.md` — The rollup comment shape](../../../../tools/github/status-rollup.md#the-rollup-comment-shape)
  before posting, and do not indent entries for "readability".

- **Remediation-developer fill-fields, release-manager hand-off and publication-ready comments, the `fix released` assignee hand-off, and the fix-PR backport check** — read [`release-manager-comments.md`](release-manager-comments.md) before proposing anything when this pass proposes `pr created` → `pr merged`, on any open tracker labelled `pr merged` or `fix released`, even when a gate blocks the next label, when it proposes populating the *Public advisory URL* body field, or when the tracker already carries a `remediation-developer-fill-fields`, `release-manager-handoff` or `release-manager-publication-ready` marker comment.

- **Advisory-records update and security-pages reminder comment** — on a closed-`announced` tracker from the Step 1g scan, and when this pass proposes the *Advisory archived on `<users-list>`* combined apply for a project that configures `advisory_records`, read [`post-advisory-records.md`](post-advisory-records.md) before proposing anything.

- **Overdue-for-disclosure escalation and distributor pre-announcement draft** — when Step 1a reports
  `overdue_for_disclosure: true`, `grace_period_expired: true` or `distributor_notify_pending: true`,
  read [`disclosure-escalation.md`](disclosure-escalation.md) before proposing anything for them.

- **Reporter unresponsiveness (proceed-without-sign-off proposal)** —
  when Step 1c's staleness check
  ([`gather.md` 1c step 5](gather.md#1c-find-the-real-reporter-and-read-the-mailing-list-thread))
  marks the reporter thread **stale** (the team's latest outbound message is older than `security_inbox.reporter_response_timeout_days` —
  resolved per the [configuration resolution order](../../../../AGENTS.md#configuration-resolution-order), 14 in both shipped organizations —
  with no reporter reply since), propose a **numbered proposal item** — not a silent status-comment entry — with this exact shape:

  > *N.* Reporter has not replied in **`<days>` days** — propose
  > proceeding with fix and announcement without further reporter
  > sign-off, per [ASF security policy](https://www.apache.org/security/committers.html).

  Substitute the actual elapsed day count for `<days>`.
  The item is a proposal only (see [`SKILL.md` § 2b](SKILL.md#2b-proposed-changes)).
  If the user confirms, continue with the other Step 2b items this pass proposes, treating the reporter's last-known position as final;
  do **not** hold them back pending a reporter reply.
  Re-surface the item on every later pass while the thread stays stale; it stops once the reporter replies and the `gather.md` check no longer fires.

- **Unanswered team question (team nudge)** — when the newest triage proposal on the tracker, or a question put to named team members,
  has had no answer from any of them for at least `nudge_after_days` (default 7, in the `security-issue-sync.md` override file),
  propose one short status comment that restates the decision asked for in one line and `@`-mentions the people asked,
  leaving out every handle in `security_issue_sync.do_not_ping` of the resolved `user.md` (personal, never committed).
  It is a **standalone comment**, not a rollup entry, like the release-manager comments below:
  it asks named people to act, and an `@`-mention added to the edited rollup notifies nobody.
  Its first line is the marker
  ```html
  <!-- apache-magpie: team-nudge v1 -->
  ```
  and its body links the question comment it chases (`#issuecomment-<C>`), so pre-flight counts it as skill-authored
  and a later sync sees the nudge for that question.
  Propose it at most once per question: when a comment with that marker already links the question, propose none (in bulk mode, report `nudged: true`).
  Apply it with `gh issue comment <N> --repo <tracker> --body-file <file>` and add a one-line rollup entry pointing at it.
  **In bulk mode the nudges can collapse:** when at least `nudge_summary_threshold` trackers (default 5) would get one,
  no tracker gets a nudge and the run proposes one state-summary email to `<security-list>` instead,
  per [`bulk-mode.md` step 4b](bulk-mode.md#orchestrator-responsibilities).
