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

  **If the milestone does not yet exist**, the proposal says so and includes the exact `gh api` command to create it.
  Before constructing the create call, **run the upstream-date lookup** per
  [`<project-config>/milestones.md` § *Read the due date from upstream*](../../../../<project-config>/milestones.md#read-the-due-date-from-upstream):
  query `<upstream>` for the matching milestone (by scope label mapping) and, if found, reuse its `due_on` verbatim.
  Never guess a date.
  For a provider-wave milestone the description names the release manager, so the advisory owner is visible at a glance:

  **Use the Write tool** (not Bash) to write each field value verbatim
  to a temp file, then pass via `-F`.
  `<scratch>` is the session scratch directory as an absolute path (fall back to `$TMPDIR`); `gh` may run outside the sandbox, where `$TMPDIR` differs, so pass it absolute paths.

  *Write tool call:* `file_path: <scratch>/ms-title-<tracker>.txt`,
  `content: <Milestone>`

  *Write tool call:* `file_path: <scratch>/ms-desc-<tracker>.txt`,
  `content: <optional>`

  ```bash
  # Core or chart (due_on mirrored from upstream when available):
  gh api repos/<tracker>/milestones \
    -F title=@<scratch>/ms-title-<tracker>.txt \
    -f state=open \
    -F description=@<scratch>/ms-desc-<tracker>.txt \
    -f due_on='<ISO8601 from upstream, omit if upstream has none>'
  ```

  For provider waves, update the Write tool calls with:

  *Write tool call:* `file_path: <scratch>/ms-title-<tracker>.txt`,
  `content: Providers YYYY-MM-DD`

  *Write tool call:* `file_path: <scratch>/ms-desc-<tracker>.txt`,
  `content: Providers release cut on YYYY-MM-DD, RM: <Name>`

  ```bash
  # Provider wave (cut date + RM from the Release Plan wiki /
  # dev@ [VOTE] thread; upstream does not milestone providers
  # waves so due_on typically comes from the wiki):
  gh api repos/<tracker>/milestones \
    -F title=@<scratch>/ms-title-<tracker>.txt \
    -f state=open \
    -F description=@<scratch>/ms-desc-<tracker>.txt
  ```

  After the create call, assign the milestone via `gh issue edit <N> --milestone 'Providers YYYY-MM-DD'`
  (or by milestone number via the REST API if the milestone is closed).

  **Closing the milestone on the last close.** When a sync pass closes a tracker (the Step 15 terminal transition — cve.org reports PUBLISHED),
  check whether it was the last open issue on its milestone; if so, **propose closing the milestone itself** in the same run,
  as its own numbered item alongside the per-tracker close.
  Condition set and PATCH recipe: [`<project-config>/milestones.md`](../../../../<project-config>/milestones.md#closing-the-milestone).
  Concretely: after the per-tracker close lands, run
  `gh api 'repos/<tracker>/issues?milestone=<N>&state=open&per_page=1' --jq 'length'`
  — if it returns `0` and the milestone is still `open`, PATCH `state=closed` on `repos/<tracker>/milestones/<N>`.
  Do not auto-close an empty milestone whose trackers were closed for other reasons than Step 15 (e.g. `duplicate` / `invalid`):
  the closure applies only when every tracker landed through the terminal advisory flow.

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

  **Assignee hand-off at the `fix released` transition (and its repair).** At the `fix released` transition (Step 12 — the fix has shipped to PyPI / the Helm registry),
  ownership moves from the remediation developer to the release manager for Steps 13–15 (advisory send → URL capture → Vulnogram PUBLIC → close).
  **Propose swapping the assignee from the remediation developer to the release manager** in the same sync run that flips `pr merged` → `fix released`,
  as a concrete numbered item.
  Look up the release manager with the three-source cascade from Step 2c
  ([`<project-config>/release-trains.md` § *Release managers for releases currently relevant to the security tracker*](../../../../<project-config>/release-trains.md#release-managers-for-releases-currently-relevant-to-the-security-tracker),
  then the project's Release Plan wiki (`<project-wiki>`),
  then the `[RESULT][VOTE] Release <product> <version>` thread on `<dev-list>`).
  If the release manager is not yet a collaborator on `<tracker>`, surface that as a blocker and ask whether to invite them before assigning
  — GitHub silently ignores assignee writes for non-collaborators.

  The swap fires at the `fix released` transition **and on the repair path below** (a tracker already at `fix released` whose swap never landed).
  Earlier transitions (`pr created`, `pr merged`) keep the remediation developer;
  later ones (`announced - emails sent`, `announced`, `vendor-advisory`) keep the release manager.
  Do **not** shuffle assignees back and forth — the swap fires once, at (or in repair of) the `fix released` hand-off.

  **Hand-off presence is an invariant — repair trackers already at
  `fix released`.** A tracker can reach `fix released` *without* a hand-off ever having been posted —
  a prior run's POST failed, the label was applied by hand, or the CVE record reached review-ready (Vulnogram `REVIEW`) on a later run than the label flip.
  No transition fires on those later syncs, so without a check the advisory stays with **no named owner**.

  So check the hand-off on **every sync**, not only as a transition side-effect.
  On every sync of a tracker at `fix released` whose CVE record is review-ready (Vulnogram `REVIEW`),
  grep the tracker's comments for the marker `<!-- apache-magpie: release-manager-handoff v1 -->` (the same grep Step 5c runs).
  If the marker is **absent**, generate the hand-off proposal item — POST the hand-off comment and propose the assignee swap — exactly as at the transition,
  whether or not this run performed the flip.
  If present, skip (Step 5c's PATCH path handles content drift).
  Resolve the release manager **authoritatively — never guess a "plausible" name**:
  for a release train that ships many packages in one wave (e.g. a providers / plugins wave),
  the owning RM is the sender of *that specific wave's* `[RESULT][VOTE]` / release `[ANNOUNCE]`,
  frequently a different person from the core-release RM for the same period;
  resolve it per the release-trains data, and record the wave + RM there if missing, before posting.
  A generic *"Action (RM): send the advisory …"* status line is **never** an acceptable substitute for the hand-off comment.
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
  - The body or title mentions *"incomplete fix for `<CVE-ID>`"*, *"follow-up to `<CVE-ID>`"*, or *"split from"* a sibling tracker whose CVE is already PUBLIC;
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

  1. If `announced - emails sent` is set and the field is still empty, **scan the public users@ archive for the CVE ID**, by one of two paths:

     - **PonyMail MCP (preferred when enabled).** If Step 0
       recorded `ponymail_authenticated: true`, call:

       ```text
       mcp__ponymail__search_list(
         list: "users",
         domain: "<project>.apache.org",
         query: "<CVE-ID>",
         timespan: "lte=30d"
       )
       ```

       `users@` is public, so no LDAP allowlist check is needed.
       A single hit is the advisory thread; capture its `tid` and build the archive URL with the manifest's `ponymail_thread_url_template`.
       Call shape: [`tools/ponymail/operations.md` — Find the advisory archive thread](../../../../tools/ponymail/operations.md#find-the-advisory-archive-thread-on-usersprojectapacheorg).

     - **PonyMail HTTP API (fallback).** When PonyMail MCP is disabled, unauthenticated, or errors,
       use the anonymous-HTTPS HTTP API + `list.html` pattern in
       [`tools/gmail/ponymail-archive.md`](../../../../tools/gmail/ponymail-archive.md#use-case--security-issue-sync);
       it works for every triager regardless of LDAP status.
       URL templates (`ponymail_api_url_template`, `ponymail_public_search_url_template`, `ponymail_thread_url_template`) are in
       [`<project-config>/project.md`](../../../../<project-config>/project.md#gmail-and-ponymail).

     On a hit, propose populating the field with the resolved thread URL (per `ponymail_thread_url_template`),
     regenerating the CVE JSON attachment, and adding the `announced` label.
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

- **Status update to the reporter** — **whenever the issue's status has changed since our last message to the reporter, propose a Gmail draft that brings the reporter up to date.**
  The transitions that warrant one are listed in
  [`docs/security/roles.md` — Keeping the reporter informed](../../../../docs/security/roles.md#keeping-the-reporter-informed),
  including the post-close *"CVE is live on cve.org"* transition surfaced by
  [Step 1g](gather.md#1g-recently-closed-trackers--check-cveorg-publication-state).

  **Pick the matching canned-response template** rather than free-drafting.
  [`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md)
  carries one template per lifecycle transition — *"CVE allocated"*,
  *"Fix PR opened"*, *"Fix PR merged"*, *"Release shipped"*,
  *"Advisory sent"*, *"CVE published on cve.org"*, *"Credit
  correction"*.
  Substitute the SCREAMING_SNAKE_CASE placeholders (`CVE_ID`, `PR_URL`, `VERSION`, `ADVISORY_URL`, `RELEASE_URL`)
  with values from the tracker body and the Step 1b / Step 1g signals.
  Draft from scratch only if the transition is not in the canned set,
  and then offer to add the new wording to the canned-responses file as a follow-up.

  Each status update follows the three-paragraph shape in
  [*Brevity: emails state facts, not context*](../../../../docs/editorial-guidelines.md#brevity-emails-state-facts-not-context):
  (a) one sentence on what changed, (b) one sentence on what comes next and roughly when, (c) the artifact URLs on their own line(s).
  Nothing else: no re-introduction, no recap, no process explanation, no speculation about severity or schedule.

  Always reply on the **original** Gmail thread (identified in Step 1c), not the GitHub-notifications mirror thread.

  **Use full, clickable URLs for every reference in the email body.**
  Shorthand like ``<upstream>#65346`` or ``<tracker>#261`` does **not** render as a link in mail. Concretely:

  - Tracking issue (allowed on the private mail thread): the **full** URL ``https://github.com/<tracker>/issues/<N>``, never ``#<N>`` or ``<tracker>#<N>``.
  - Fix PRs on ``<upstream>``: the **full** URL ``https://github.com/<upstream>/pull/<N>``, never ``<upstream>#<N>``.
  - Any other GitHub reference (public issues, commits, security advisories): the full URL.
    Markdown-link syntax (``[text](url)``) does **not** render in plain-text email — use the bare URL.
  - CVE IDs appear as **plain ``CVE-YYYY-NNNN`` inline text only**.
    **Never** include the CVE-tool URL (``<cve-tool-url>/cve5/CVE-YYYY-NNNN``) in a reporter email.
    Once the CVE is **published** on ``cve.org`` (advisory sent, ``announced`` label set),
    the ``cve.org`` URL (``https://www.cve.org/CVERecord?id=CVE-YYYY-NNNN``) is an acceptable alternative,
    but plain text stays the default. Full rule and pre-draft self-check:
    [*Reporter emails: CVE ID only, never the ASF CVE-tool URL*](../../../../docs/editorial-guidelines.md#reporter-emails-cve-id-only-never-the-asf-cve-tool-url).
  - Advisory archive URLs (``<mail-archive-url>/thread/...``) are already full URLs; paste them as-is.

  This applies to the **email** path only; comments on the ``<tracker>`` issue use the
  markdown-linked ``[#<N>](url)`` / ``[<upstream>#<N>](url)`` form per Golden rule 2.

  **Confidentiality:** the tracking-issue URL is a public-safe identifier and *may* go in the reporter email;
  the tracker's content and, before the advisory ships, the security framing may not, per
  [Confidentiality of `<tracker>`](../../../../AGENTS.md#confidentiality-of-the-tracker-repository).
  For a reporter who cannot access the tracker, pair the URL with a one-line identifier-only note
  (see [`docs/confidentiality.md`](../../../../docs/confidentiality.md#sharing-a-tracker-url-with-someone-who-cannot-access-it)).

  **Do not re-ask questions that have already been asked.** Before drafting, scan the thread end-to-end for open questions we already put to the reporter —
  most importantly the credit-preference question, but also technical follow-ups.
  If one is still pending an answer, **omit it from the new draft**.
  Restate the credit question only if (a) it has never been asked on the thread,
  or (b) more than ~7 days have passed since it was last asked **and** publication is imminent.
  When in doubt, ask the user before re-pinging the reporter.

  Concrete check: in our previous messages on the thread, look for *"credited"*, *"credit"*, *"how would
  you like to be"*, *"name (and, if applicable, affiliation"*, or *"prefer to
  remain anonymous"*.
  If any is present and the reporter has not replied, the credit question is **already pending** — do not re-ask.

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
  instructions only.** The rollup is the default surface for every sync output — status changes, label rationale, milestone moves, assignee swaps,
  reporter-draft notes, fix-PR links, CVE-review-comment surfacing, legacy-fold entries, recap pointers, blockers, *everything*.
  The **only** comments this skill posts outside the rollup are the release-manager-directed call-to-action comments further down this list:
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

- **Remediation-developer fill-fields comment** — when mandatory CVE body fields are not yet populated,
  propose posting (or PATCH-updating) a comment tagging the **remediation developer** with the concrete list of missing fields.
  The tracker stays assigned to the remediation developer; the release-manager hand-off is **not** fired until the gate clears.

  **This is its own first-class comment, not a rollup entry**: like the RM hand-off, it is a call to action.

  **Trigger — two firing points**:

  1. **At the `pr created` → `pr merged` transition (Step 11)** — when sync proposes that label swap,
     check whether all six mandatory body fields are populated
     (*CWE*, *Affected versions*, *Severity*, *Reporter credited
     as*, *Short public summary for publish*, *PR with the fix*).
     If any is empty / `_No response_`, propose the fill-fields comment with that field list.
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
  (`CVE_ID`, `SOURCE_TAB_URL`, `TRACKER_URL`, `SECURITY_LIST`,
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
  - `SOURCE_TAB_URL`, `EMAIL_TAB_URL` — substitute `<CVE-ID>` into
    `cve_tool_record_url_template` (from project.md), append
    `#source` / `#email` per [`tools/cve-tool-vulnogram/record.md`](../../../../tools/cve-tool-vulnogram/record.md#record-urls).
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

- **Security-pages reminder comment** — the ASF security-committers policy's post-announcement step *"The project team updates the
  project's security pages"* is a website edit, which sync cannot perform or gate the close-out on
  (the close-out fires on the archive-URL signal).
  Sync carries the checklist item that records it: both hand-off comment variants embed a
  `- [ ] <!-- apache-magpie: security-pages-checklist v1 --> Project
  security pages updated with CVE_ID` box, and ticking it records the completion marker on the tracker.
  This proposal covers the marker still unrecorded after the advisory has shipped.

  **Trigger.** Step 1g recorded `security_pages_reminder_pending: true` for a closed-`announced` tracker —
  the *Public advisory URL* body field is populated (the advisory has demonstrably shipped),
  no ticked `- [x] <!-- apache-magpie: security-pages-checklist v1 -->` item exists anywhere on the tracker,
  and no comment carries the reminder marker below.
  The trigger state exists only on a closed tracker (the Step 14 close-out adds `announced` and closes in one apply),
  so this proposal is reached through the
  [1g](gather.md#1g-recently-closed-trackers--check-cveorg-publication-state)
  closed-bucket scan, never through the open-tracker signals.
  An unticked box in the hand-off comment is the *pending* state that fires the reminder, not the satisfied one.

  **Proposed action.** A short status comment tagging the release
  manager. Line 1 of the body is the reminder marker
  ```html
  <!-- apache-magpie: security-pages-reminder v1 -->
  ```
  followed by one sentence naming the outstanding item with a link to the project's security pages
  (the `security_pages_url` key from
  [`<project-config>/project.md`](../../../../<project-config>/project.md#repositories);
  when unset, the plain phrase *"the project's security pages"* with no link, and flag the missing key in the proposal), and
  the checklist item
  `- [ ] <!-- apache-magpie: security-pages-checklist v1 --> Project security pages updated with CVE_ID`,
  so ticking the box on either comment records the step.
  Per [*"Brevity: emails state facts, not context"*](../../../../docs/editorial-guidelines.md#brevity-emails-state-facts-not-context),
  state the outstanding item, not the rationale (the RM has already seen it in the hand-off comment).

  **Guard.** The reminder marker makes this once per tracker:
  never re-propose while a comment carrying `<!-- apache-magpie: security-pages-reminder v1 -->` exists, ticked or not.
  The checklist marker cannot serve as the guard, because the hand-off comment always carries it.
  Never propose editing the website, reopening the tracker, or any label on this signal's behalf.

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
  (the just-captured archive URL), `SOURCE_TAB_URL`,
  `JSON_ANCHOR_URL`, `CVE_ORG_URL`
  (`https://www.cve.org/CVERecord?id=<CVE-ID>`).

  **Apply mechanic** — same as the hand-off comment: a fresh
  `gh issue comment`, surfaced in the recap.

- **Overdue-for-disclosure escalation** — when `overdue_for_disclosure: true` (Step 1a), the tracker has passed its CVD window without the advisory being sent.
  Propose appending a rollup entry that:

  1. Notes the elapsed time and the configured `window_days` ceiling (e.g.
     *"Tracker is {issue_age_days} days old; the project's CVD window is
     {window_days} days — disclosure is overdue."*).
  2. Recommends one of:
     - Notifying the reporter of an extended timeline on the mail thread
       (propose a Gmail draft if the acknowledgement model is `manual`); or
     - Proceeding to disclosure with a partial or advisory-only fix if a
       coordinated full fix cannot ship in the near term.
  3. Does **not** override or silence any other proposal — the overdue flag
     is additive context, not a shortcut past the normal lifecycle steps.

  When `grace_period_expired: true` (fix shipped but the grace period has also lapsed),
  promote the entry to a **separate first-class comment** (not a `<details>` entry), visible to the release manager and the team without expanding the rollup.
  Use the RM hand-off comment's idempotency check — scan for the marker
  ```html
  <!-- apache-magpie: disclosure-overdue v1 -->
  ```
  before proposing; if it already exists, update it in-place via PATCH rather than posting a duplicate.

- **Distributor pre-announcement draft** — when `distributor_notify_pending: true` (Step 1a), the project keeps an embargo distributor list and the fix is about to ship.
  Propose a Gmail draft pre-announcement to the distributor list declared in `<project-config>/distributor-list.md`
  (if that file is absent, surface a one-line note that the adopter should create it and document the list URL there before this proposal can be executed).
  The draft:

  - Names the CVE ID and the affected product/versions from the tracker body.
  - States the expected public disclosure date as
    `createdAt + window_days + grace_period_days` (or earlier if the team
    decides to disclose sooner) — do not commit to a specific calendar date
    unless the advisory send date has already been confirmed by the team.
  - Omits any detail beyond what is in the advisory's *Short public summary
    for publish* body field — the pre-announcement is not the advisory itself.
  - Is marked **DRAFT, NEVER SEND** until the team confirms the wording, the
    recipient list, and the timing.

  Trigger condition: `distributor_notify_pending: true` AND the `announced` label is absent
  AND no pre-announcement draft already exists in Gmail for this tracker's thread (check via the Step 1e Gmail draft-scan before proposing a new draft).

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

- **Draft email to reporter (other reasons)** — whenever the ball is in our court on the thread for another reason
  (a reporter question, a triage follow-up, a negative assessment), propose a **Gmail draft** reply (not a sent message).
  State the draft's intent in one line, and reuse a canned response from
  [`canned-responses.md`](../../../../<project-config>/canned-responses.md) verbatim where one applies.
  Show the exact subject, recipients, In-Reply-To, and body in the proposal.

  **Brevity** applies: fresh wording carries only the facts the reporter needs (the question answered, the decision communicated) plus one artifact link,
  per [*Brevity: emails state facts, not context*](../../../../docs/editorial-guidelines.md#brevity-emails-state-facts-not-context).

  **Route through the forwarder-relay adapter when one is registered.**
  If the parent tracker carries a forwarder-adapter marker (set by the optional
  [`security-issue-import-via-forwarder`](../issue-import-via-forwarder/SKILL.md)
  sub-skill when `forwarders.enabled` is non-empty in
  [`<project-config>/project.md`](../../../../<project-config>/project.md)
  and the inbound message matched a registered adapter),
  route any drafted reply through that adapter's `contact_handle` and use its `reporter_addressing_block` convention.
  Contract, including the per-event do-relay / suppress matrix that decides whether a draft is proposed at all
  (e.g. CVE-allocated and advisory-sent events relay; routine credit-form questions and reviewer-comment relays are suppressed):
  [`tools/forwarder-relay/README.md`](../../../../tools/forwarder-relay/README.md).
  When no adapter is registered (`forwarders.enabled` is empty, or the tracker has no forwarder-adapter marker),
  proceed in direct-reporter mode — the draft targets the reporter on the inbound thread.
  In either of those cases do not load or invoke the sub-skill at all:
  with `forwarders.enabled` empty its Step 0 returns no match, and the marker is the recorded result of the import-time `detect()`, so a tracker without it has no adapter to route through.
  The sub-skill's Step 1 stays the authoritative detection for the trackers that do carry the marker.

  **Never send.** Always create a draft, preferably attached to the inbound mail thread
  (the preferred `oauth_curl` backend uses `--thread-id` directly and preserves URLs verbatim;
  the discouraged `claude_ai_mcp` backend resolves the latest message ID from the inbound `threadId` and passes it as `replyToMessageId` but rewrites embedded URLs —
  see [`draft-backends.md`](../../../../tools/gmail/draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)).
  If Step 1c could not resolve a `threadId`, fall back to a subject-matched draft (thread-attachment parameter omitted, `subject: Re: <root subject>`)
  per [`tools/gmail/threading.md`](../../../../tools/gmail/threading.md).
  Surface which path was taken in the proposal.
  The Gmail MCP's no-update-no-delete limitation — corrections surface the prior `draftId` for manual discard rather than silently shadowing it —
  is in [`tools/gmail/operations.md`](../../../../tools/gmail/operations.md#hard-limitation--no-update-no-delete).

- **Signal — a fix PR merged, but not onto the branch its milestone
  ships from.** When proposing `pr created` → `pr merged` on a tracker whose milestone is a **patch** release,
  check that the fix is actually on that release's branch.
  A PR merged to the main development branch reaches a patch release only if backported,
  and the *Affected versions* upper bound claims which release contains the fix.

  **Check it at `pr merged`, not at `fix released`.** Once the release is cut, the wave ships without the fix and the advisory names a version that never contained it.
  This is the *containment* half of the [`fix released` gate](SKILL.md), moved one step earlier while it is still cheap to correct.

  **How to check — content probe, not ancestry.** A cherry-pick changes the SHA, so `compare/<sha>...<branch>` reporting `diverged` is not evidence of absence.
  Pick a distinctive string the fix introduces (a comment line, a new identifier), fetch the file on
  each branch as a plain `gh` call, and look for the string in the output:

  ```bash
  gh api "repos/<upstream>/contents/<path>?ref=<branch>" \
    -H "Accept: application/vnd.github.raw+json"
  ```

  Probe the development branch, the release branch the milestone ships from, and the corresponding stable branch.
  Present the result as a table — the asymmetry is the finding.

  **Corroborating signal:** projects that automate backports use a per-branch label (`backport-to-<branch>` or similar).
  Its absence on a merged PR whose tracker is milestoned to that branch's release is a strong hint,
  but the label is a *convention* and the content probe is the *evidence* — do not conclude either way from the label alone.

  **Two ways to resolve, and they are not equivalent** — surface both and let the operator choose, because they change what ships in the published record:

  1. **Backport** — apply the branch label, milestone the PR to the
     patch release, and cherry-pick. The tracker's milestone and its
     `< <patch>` upper bound both stay correct.
  2. **Let it ride to the next feature release** — move the tracker
     milestone, **and** widen *Affected versions* to that release.
     Leaving the old bound in place is the actual danger: it tells
     users to upgrade to a version that does not contain the fix.

  Never pick silently. Option 2 changes a CVE-affecting body field,
  so it belongs in the CVE-affecting bucket and needs explicit
  confirmation.
