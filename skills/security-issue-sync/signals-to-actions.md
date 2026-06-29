<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 2b — Proposed changes (signal-to-action lookup table)

> Extracted from [`SKILL.md`](SKILL.md) so subagents that only need
> this slice can load just this file. Loaded automatically when the
> orchestrator (or a subagent) is in the matching step.

This subdoc carries the signal-to-action lookup table — every row a Step 1d signal that translates to a proposed body-field update / label change / status comment / draft email. The full table is loaded only when Step 2b is actively building a proposal.

---

## 2b. Proposed changes

Each proposed change is a **numbered item** and must be explicit about *what*
will change and *why*. Group them by category:

- **Labels to add / remove** — e.g. *"remove `needs triage`; add `<scope-a>`"*. Reason: one scope label is required by the process once triage is complete.

  **Release-vote label (opt-in, ASF projects only).** When release-
  vote gating is enabled (`[workflow].release_vote_gating = true` in
  the CVE-JSON generator's config), Step 1h's detection feeds two
  more proposal shapes into this category:

  - *Add* the configured `rc voting` label (default `"rc voting"`)
    when a matching open `[VOTE]` thread was detected on
    `<dev-list>` and the tracker is in the
    `pr merged` window. The proposal must quote the PonyMail
    thread URL as the rationale so the security team can spot-
    check the match before confirming — *"detected active vote
    thread: `<thread-url>` carrying version X.Y.Z, matches fix-PR
    milestone"*.
  - *Remove* the `rc voting` label when the existing
    `pr merged` → `fix released` transition fires (the release
    shipped — the vote passed and is now historical). This
    removal piggy-backs on the same proposal that adds
    `fix released` and removes `pr merged`; surface it as part
    of the same numbered item so the user confirms one combined
    label flip rather than two separate ones. The label can
    also be removed by hand if a vote *fails* and the team
    re-cuts an RC; the sync skill does not actively detect
    failed votes (the heuristic is fragile and the human re-add
    on the next vote is cheap).

  The label gating is **only** consulted for projects that
  opted in via the generator config. For non-ASF adopters that
  did not opt in, this entire sub-paragraph is a no-op — the
  label is never proposed, added, or referenced, and the
  generator's legacy *"ready ⇒ REVIEW"* behaviour applies.
- **Milestone** — propose the matching release milestone on the
  issue. The milestone format depends on the scope label and is
  project-specific; for the adopting project see
  [`<project-config>/milestones.md`](../../<project-config>/milestones.md)
  (the scope → milestone-format mapping and the rule that a merged PR's
  own milestone wins over the release-train default). The current
  release-train default used when no PR milestone is available lives
  in
  [`<project-config>/release-trains.md`](../../<project-config>/release-trains.md).

  **If the milestone does not yet exist**, the proposal must say
  so and include the exact `gh api` command to create it. Before
  constructing the create call, **run the upstream-date lookup**
  per the *Read the due date from upstream* subsection of
  [`<project-config>/milestones.md`](../../<project-config>/milestones.md#read-the-due-date-from-upstream) —
  query `<upstream>` for the matching milestone (by scope label
  mapping) and, if found, reuse its `due_on` verbatim. Never guess
  a date. For a provider-wave milestone the description should name
  the release manager so the advisory owner is visible at a glance:

  **Use the Write tool** (not Bash) to write each field value verbatim
  to a temp file, then pass via `-F`:

  *Write tool call:* `file_path: /tmp/ms-title-<tracker>.txt`,
  `content: <Milestone>`

  *Write tool call:* `file_path: /tmp/ms-desc-<tracker>.txt`,
  `content: <optional>`

  ```bash
  # Core or chart (due_on mirrored from upstream when available):
  gh api repos/<tracker>/milestones \
    -F title=@/tmp/ms-title-<tracker>.txt \
    -f state=open \
    -F description=@/tmp/ms-desc-<tracker>.txt \
    -f due_on='<ISO8601 from upstream, omit if upstream has none>'
  ```

  For provider waves, update the Write tool calls with:

  *Write tool call:* `file_path: /tmp/ms-title-<tracker>.txt`,
  `content: Providers YYYY-MM-DD`

  *Write tool call:* `file_path: /tmp/ms-desc-<tracker>.txt`,
  `content: Providers release cut on YYYY-MM-DD, RM: <Name>`

  ```bash
  # Provider wave (cut date + RM from the Release Plan wiki /
  # dev@ [VOTE] thread; upstream does not milestone providers
  # waves so due_on typically comes from the wiki):
  gh api repos/<tracker>/milestones \
    -F title=@/tmp/ms-title-<tracker>.txt \
    -f state=open \
    -F description=@/tmp/ms-desc-<tracker>.txt
  ```

  After the create call, assign the milestone to the issue via
  `gh issue edit <N> --milestone 'Providers YYYY-MM-DD'` (or by
  milestone number via the REST API if the milestone is closed).

  **Closing the milestone on the last close.** When a sync pass
  closes a tracker (the Step 15 terminal transition — cve.org
  reports PUBLISHED), also check whether that tracker was the last
  remaining open issue on its milestone. If so, **propose closing
  the milestone itself** in the same sync run. The exact condition
  set and the `gh api` PATCH recipe live in
  [`<project-config>/milestones.md`](../../<project-config>/milestones.md#closing-the-milestone).
  Concretely: after the per-tracker close lands, run
  `gh api 'repos/<tracker>/issues?milestone=<N>&state=open&per_page=1' --jq 'length'`
  — if it returns `0` and the milestone is still `open`, PATCH
  `state=closed` on `repos/<tracker>/milestones/<N>`. Do not
  auto-close an empty milestone whose unfinished trackers were
  closed for reasons other than Step 15 (e.g. `duplicate` /
  `invalid`); the milestone closure only makes sense when every
  tracker landed through the terminal advisory flow. Surface the
  milestone-close proposal as its own numbered item alongside the
  per-tracker close.

- **Assignees** — when a fix PR exists in `<upstream>` (found in
  Step 1b or named in the *"PR with the fix"* body field) **and the
  PR author is a member of the project security team** (their GitHub
  handle appears in the security-team roster in
  [`<project-config>/release-trains.md`](../../<project-config>/release-trains.md) — when in doubt,
  run `gh api repos/<tracker>/collaborators --jq '.[].login'`
  as the authoritative check; **every collaborator counts regardless
  of their permission level** — read, triage, write, maintain, and
  admin are all valid), **propose setting the tracking issue's
  assignee to that PR author**. The PR author is the natural owner
  for driving the issue through the rest of the process (review,
  merge, backport label, advisory coordination), and setting them
  as assignee gives the whole team a fast "who is on this?" answer
  in the issue list.

  If the PR author is **not** on the security-team roster (for
  example, an external contributor who submitted the fix via the
  public process), do **not** assign them — they are not part of the
  internal handling process and do not need the tracking-issue
  notifications. Instead, leave the assignee empty or propose a
  security-team member who is already engaged in the discussion.

  **Sign-up (volunteer) branch.** A fix PR is not the only ownership
  signal. When a person has **signed up** to own the issue — the
  *volunteer-owner* signal from
  [`gather.md` Step 1d](gather.md#1d-mine-comments-and-mail-messages-for-actionable-signals)
  (a comment volunteering to take it: *"I'll take this"*, *"assign
  me"*, *"I can work on the fix"*, *"I'll drive the advisory"*) —
  **propose setting that person as the assignee**, subject to the
  **same project-member gate** as the PR-author branch: their handle
  must appear in the security-team roster in
  [`<project-config>/release-trains.md`](../../<project-config>/release-trains.md),
  or in `gh api repos/<tracker>/collaborators --jq '.[].login'`
  (every permission level counts). The gate matters twice over for a
  private tracker: a non-collaborator **cannot see the issue**, and
  GitHub silently drops assignee writes for non-collaborators. So a
  volunteer who is **not** a project member is recorded in the
  proposal as context but **not** assigned — surface *"`<handle>`
  volunteered but is not a `<tracker>` collaborator — invite them
  first?"* and let the user decide. Precedence and idempotency:

  - When both a sign-up and a fix-PR author exist, the **PR author
    wins** — the in-flight fix is the stronger ownership signal;
    record the volunteer as context only.
  - Only propose the sign-up assignment when the issue currently has
    **no assignee**. Never override an existing assignee on a
    volunteer signal — that is a hand-off, which only happens at the
    `fix released` transition below.

  Also propose clearing a stale assignment if the person is no longer
  active on the issue, and propose self-assigning a team member only
  if the user explicitly asks.

  **Assignee hand-off at the `fix released` transition.** When the
  sync transitions an issue to `fix released` (Step 12 — the fix has
  shipped to PyPI / the Helm registry), ownership moves from the
  remediation developer to the release manager for Steps 13–15
  (advisory send → URL capture → Vulnogram PUBLIC → close).
  **Propose swapping the assignee from the remediation developer to
  the release manager** in the same sync run that flips
  `pr merged` → `fix released`, so the issue list reflects who is
  actually on the hook next. Look up the release manager using the
  three-source cascade from Step 2c (the "Known release managers"
  subsection of [`AGENTS.md`](../../AGENTS.md), then the
  project's Release Plan wiki (`<project-wiki>`),
  then the `[RESULT][VOTE] Release <product> <version>` thread on
  `<dev-list>`), and propose the swap as a concrete
  numbered item in Step 2b. If the release manager is not a
  collaborator on `<tracker>` yet, surface that as a
  blocker and ask the user whether to invite them before assigning
  — GitHub silently ignores assignee writes for non-collaborators.

  This swap is **only** appropriate at the `fix released`
  transition. Earlier transitions (`pr created`, `pr merged`) keep
  the remediation developer as assignee because the fix PR is still
  their responsibility. Later transitions
  (`announced - emails sent`, `announced`,
  `vendor-advisory`) keep the release manager because the advisory
  lifecycle is theirs. Do **not** shuffle assignees back and forth.
- **Issue title hygiene** — the GitHub issue title ships verbatim into
  the CVE record's `containers.cna.title` field (read by the
  `generate-cve-json` script on every regen) and from there into the
  published advisory and `cve.org`. **On every sync pass**, run the
  same title-strip cascade the
  [`security-cve-allocate` skill applies at allocation time](../security-cve-allocate/SKILL.md#step-2--compute-the-cve-ready-title) —
  strip leading/trailing project-name tokens (e.g. ``<project>:``,
  ``in <project>``, ``(<project> X.Y)``), internal
  split-markers (``(split from #NNN)``), report-form classifiers
  (``[Security Report]``, ``[Security Issue]``), external-tracker IDs
  (``[GHSA-...]``, ``(ZDRES-...)``, ``(HUNTR-...)``, ``(GHSL-...)``)
  and version-noise suffixes (``(v3.2.1)``, ``(3.x)``). When the
  cascade would change the title, propose the diff as a numbered
  Step 2b item; on confirmation, ``gh issue edit <N> --title
  "<cleaned>"`` and then regen + push CVE JSON so the record's
  `title` field picks up the cleaned value. **Preserve stripped
  context as audit trail** — split-from references, GHSA IDs,
  internal report-form classifiers all carry information the
  security team uses to navigate sibling reports and reviewer
  threads. Move them into the issue body (a `### Related references`
  section) or into the rollup as an audit entry; never silently
  drop them. Titles drift between allocation and the final regen
  (manual edits, sibling-tracker splits, GHSA-relay imports that
  append the GHSA ID), so the cascade has to re-run on every sync
  even when no other body update is being proposed. The Step 1d
  signal-table row *"The issue title contains adopter-specific or
  internal noise"* is the detector that surfaces the cleanup
  proposal on every qualifying pass.
- **Description fields** — if the issue body is missing any of the fields the
  release manager will eventually need (CWE, product, affected versions, severity,
  CVE ID, credits, links to PRs, short public summary for publish), propose a
  patched description. Show the full replacement body in the proposal, not a
  diff, so the user can review it.

  **Every `_No response_` field must be explicitly reviewed in every sync
  run.** Before presenting the proposal, scan the issue body for remaining
  `_No response_` placeholders. For each one, either propose a concrete
  value (if the discussion, the mail thread, the PR, or the GHSA provides
  enough information to fill it in) or flag it explicitly in the proposal
  as *"still `_No response_` — needs \<what\> before it can be filled"*.
  Do not silently leave fields empty across multiple sync runs — the
  release manager at Step 13 needs **every** field filled in to send the
  advisory, and the `pr merged → fix released` transition is gated on
  the six mandatory fields per the table row in Step 2b above.

  **Agent-derivable fields — propose high-confidence values proactively.**
  Two of the mandatory fields can be derived by the agent itself with
  high confidence from artefacts already in the sync's evidence pool,
  rather than waiting for a human to fill them in. Treat the following
  as the allow-listed set for active auto-proposal whenever the field
  is empty or `_No response_`:

  - **CWE** — map the patch to a CWE class (e.g., a missing-auth-check
    fix → CWE-287, untrusted-input-into-SQL fix → CWE-89, path-traversal
    guard fix → CWE-22). **Propose only when the patch is unambiguous**
    — when multiple plausible CWE classes fit, flag the ambiguity
    instead of guessing. Cite the file path(s) and line range(s) that
    drove the mapping so the user can sanity-check before confirming.

  - **Affected versions** — derive from the `<upstream>` PR's milestone
    / fix-version metadata mapped to the project's per-scope convention
    (see [`<project-config>/scope-labels.md` — *Affected versions
    convention by scope*](../../<project-config>/scope-labels.md#affected-versions-convention-by-scope)).
    Propose only when the milestone uniquely determines the affected
    range; flag ambiguity (e.g. multiple backport milestones with
    partial coverage) rather than guessing. **Always emit the proposed
    value wrapped in backticks** (e.g. `` `>= X.Y.Z, < A.B.C` ``,
    `` `< A.B.C` ``); see the *"`Affected versions` body field has a
    value but it is not backtick-wrapped"* row in the Step 1d signal
    table for why this matters (raw `>=` renders as a markdown
    blockquote and form-UI edits silently lose the prefix).

  All other mandatory fields stay on the *external-signal* path:
  propose values only when the discussion, mail thread, PR, or GHSA
  provides enough information — never guess them.

  **"Short public summary for publish" must include user-facing
  instructions.** This field powers the published CVE description that
  end users read in the advisory. Beyond stating the vulnerability in
  one or two sentences, the summary must tell users **what to do**:
  the fixed version to upgrade to, the mitigations available for users
  who cannot upgrade immediately, and the CWE class (allowed and
  useful — CWE is not embargoed information once the advisory ships).

  **Validate this on every sync pass that proposes a body-field update
  or a JSON regen**, not only at the `pr merged → fix released`
  boundary. A summary that names the vulnerability accurately but
  lacks the upgrade-target version (e.g. *"upgrade to the
  version that contains the fix"* without naming `3.3.0`) is a
  defect; propose tightening it before regen lands in the embedded
  JSON + the next push to the CVE record.

  **The summary must also state the triggering conditions** — the
  reader scans the published advisory asking *"does this affect us?"*,
  and the answer comes from the trigger context, not the bug
  mechanism. Concretely the summary should make these three things
  unambiguous in one sentence each (in any order):

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

  The condition tuple lets a reader who is *not* familiar with the
  internal code paths decide whether their deployment is exposed
  without opening the source or the original report. A summary that
  omits any of the three forces them to read the issue PR / patch
  to figure out the trigger — exactly the work the advisory is
  meant to remove. When the field is technically accurate but
  missing one of (who / when / action), propose adding it on the
  same sync pass as the upgrade-target tightening.

  Worked example shape (a single CVE):

  > *"An authenticated UI user with permission to read DAGs could
  > craft a `next=` parameter on the login route that bypassed
  > `is_safe_url`, redirecting other users to an attacker-controlled
  > origin after authentication. Affects deployments where the
  > webserver is reachable by untrusted users. Users are advised to
  > upgrade to `<product>` 3.2.2 or later."*

  The first sentence names the attacker (*authenticated UI user*),
  the action (*crafts `next=`*), and the surface (*login route*); the
  second sentence names the configuration (*webserver reachable by
  untrusted users*); the third is the upgrade ask. When the carrier release
  is known (the fix PR's milestone is set), name it verbatim —
  ``<product> 3.3.0 or later``,
  ``<product>-<component> 11.2.0 or later``,
  ``<product> 1.18.0 or later``, etc. When the
  carrier release is not yet known (early `pr created` state where
  the PR has no milestone), keep the placeholder but flag the gap
  in Step 2c so the next sync after milestone-set catches it. The
  Step 1d signal-table row *"`Short public summary for publish` is
  populated but does not name a concrete upgrade-target version"*
  is the detector that surfaces the rewrite proposal on every
  qualifying pass.

  **Incomplete-fix-to-another-CVE: the summary must name the prior
  CVE *and* tell users who already applied that fix to apply this
  one too.** When the tracker is an *incomplete-fix follow-up* to a
  previously-published CVE — detected by the rollup, the body, or
  the issue title mentioning *"incomplete fix for `<CVE-ID>`"*,
  *"follow-up to `<CVE-ID>`"*, *"split from"* a sibling tracker
  whose CVE is already PUBLIC, or by the title's prior-CVE token —
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

  **Why this matters.** When a CVE is published as a "follow-up"
  to an earlier CVE, the reader's natural reading is *"I already
  applied the earlier fix; this one is a duplicate"*. Without
  explicit cross-CVE + cross-product framing, downstream consumers
  miss that two upgrades are needed (one per product / package) to
  close the original vulnerability fully. The advisory has to do
  the work of explaining the split — the CVE ID alone is not
  enough signal.

  **Detection signals** (any one triggers the cross-CVE summary
  shape):

  - The tracker's `Short public summary` already mentions the
    prior `CVE-YYYY-NNNNN` token but lacks the *"users who
    applied the prior fix should also..."* clause.
  - The rollup carries a *"sibling tracker"* / *"split for scope
    clarity"* / *"follow-up to `<PRIOR-CVE-ID>`"* entry.
  - The issue title contains an explicit *"incomplete fix for
    `<PRIOR-CVE-ID>`"* parenthetical (per the title-strip
    cascade — that token is stripped from the title but the
    cross-CVE relationship is preserved in body / rollup).
  - The CVE record's `affected[]` array names a different
    `packageName` than the prior CVE's record, AND the prior CVE
    is on the same root-cause class.

  When any signal fires, propose the cross-CVE summary expansion
  as part of the same Step 2b body-field update set. Do **not**
  silently emit a summary that omits the cross-CVE / cross-product
  upgrade ask — that creates the "I already applied the fix"
  blind spot the rule exists to prevent.

  **Special case for the "Security mailing list thread" field — leave
  it alone.** This field holds the internal navigation reference to
  the private `<security-list>` thread that originated the
  report. The URL is expected to 404 for anyone outside the security
  team; that is the intended behaviour. **Do not scrub this field,
  do not replace the URL with a textual note, do not "clean it up".**
  The `generate-cve-json` script no longer exports URLs from this
  field to `references[]`, so the 404-risk it used to carry is gone.
  Keep whatever the reporter or triager put there so the team can
  navigate back to the original thread from the tracker.

  **The "Public advisory URL" body field** is a separate body field
  that carries the archived public advisory URL on
  `<mail-archive-url>/list.html?<users-list>` (or
  `<announce-list>`). Empty until Step 13 — the release manager
  fills it in **after** the advisory email has been sent and archived.
  Every sync run must:

  1. If `announced - emails sent` is set and the field is still
     empty, **scan the public users@ archive for the CVE ID**. Two
     paths, picked by what the user has configured:

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

       `users@` is a public list so no LDAP allowlist check is
       required. A single hit is the advisory thread; capture its
       `tid` and construct the pastable archive URL via the
       `ponymail_thread_url_template` from the project manifest.
       See
       [`tools/ponymail/operations.md` — Find the advisory archive thread](../../tools/ponymail/operations.md#find-the-advisory-archive-thread-on-usersprojectapacheorg)
       for the exact call shape.

     - **PonyMail HTTP API (fallback).** When PonyMail MCP is
       disabled, unauthenticated, or returns an error, fall back
       to the HTTP API + `list.html` pattern documented in
       [`tools/gmail/ponymail-archive.md`](../../tools/gmail/ponymail-archive.md#use-case--security-issue-sync).
       The adopting project's URL templates are declared in
       [`<project-config>/project.md`](../../<project-config>/project.md#gmail-and-ponymail)
       (`ponymail_api_url_template`,
       `ponymail_public_search_url_template`,
       `ponymail_thread_url_template`). The fallback path is
       anonymous-HTTPS only and works for every triager regardless
       of LDAP status.

     Either way, if the archive returns a hit, propose populating
     the field with the resolved thread URL (per
     `ponymail_thread_url_template`), regenerating the CVE JSON
     attachment, and adding the `announced` label.
  2. If the field is already populated, treat it as authoritative —
     no scan needed. Regenerate the CVE JSON attachment so the URL
     flows into `references[]` as `vendor-advisory`.
  3. The sync skill's responsibility ends when the label is
     `announced`. **Do not propose closing the issue**
     — closing is a Step 15 action and belongs to the release
     manager, who finishes the lifecycle by copying the attached
     CVE JSON into Vulnogram and closing the issue (no label
     changes).
  4. On subsequent sync runs, check whether the CVE record on
     `<cve-tool-url>/cve5/<CVE-ID>` has moved to PUBLISHED.
     When it has, propose closing the issue (do not update labels).
     This is the only place sync proposes closing an advisory-flow
     issue; all earlier closes are only for closing dispositions
     (`invalid` / `duplicate` / `wontfix`) at
     Steps 5–6.

  See the "CVE references must never point at non-public mailing-list
  threads" section of [`AGENTS.md`](../../AGENTS.md) for the full
  rationale of the two-field split.

  **Special case for the `Severity` field — never propagate reporter-supplied
  CVSS scores.** If the reporter attached a CVSS vector or a qualitative label
  (*"Low"*, *"High"*, *"Critical"*) to the mail thread, a GHSA draft, or the
  issue body, surface it in the *observed state* dump as informational context
  (e.g. *"reporter estimated CVSS 4.0 = 7.2 per the GHSA"*) but **do not** use
  it as the proposed value for the `Severity` field. The security team
  scores every accepted vulnerability independently during the CVE-allocation
  step; the independent score is the one that ends up in the CVE record and
  the public advisory. The `Severity` field on the tracking issue must either
  stay `_No response_` until a security-team member scores it independently
  (in-thread or in an issue comment), or reflect that independent score —
  never the reporter's. Apply the same rule to a self-assigned CWE the
  reporter attaches alongside. Full rationale: the
  "Reporter-supplied CVSS scores are informational only" subsection of
  [`AGENTS.md`](../../AGENTS.md).
- **Status transitions** — e.g. *"close the issue as invalid"*, *"add `Not yet
  announced` now that <upstream>#NNNN has merged"*, *"add `vendor-advisory
  ready` now that the users@ advisory URL has been captured — the release
  manager will copy the CVE JSON to Vulnogram and close the issue"*.

- **Project-board column.** Every tracker has exactly one `Status`
  option set on the Security-issues board, and the column must match
  the issue's label-derived state. Reconcile whenever the labels and
  the column disagree — the board is the primary overview surface for
  the security team and scans of *"who owns what right now"* start
  there.

  The label + body-state → board-column mapping and the board URL
  live in
  [`<project-config>/project.md`](../../<project-config>/project.md#github-project-board).
  Board-column mutations are applied via the GraphQL
  `updateProjectV2ItemFieldValue` mutation; the recipe lives in
  [`tools/github/project-board.md`](../../tools/github/project-board.md#write--move-a-tracker-to-a-different-column)
  and is invoked from the Step 4 apply list.

- **Status update to the reporter** — **whenever the issue's status has changed
  since the last message we sent to the reporter, propose a Gmail draft that
  brings the reporter up to date.** The set of transitions that warrant a
  status update is enumerated authoritatively in
  [`docs/security/roles.md` — Keeping the reporter informed](../../docs/security/roles.md#keeping-the-reporter-informed);
  the skill must draft an update when any of those has happened since our
  last message in the original mail thread, including the post-close
  *"CVE is live on cve.org"* transition surfaced by
  [Step 1g](gather.md#1g-recently-closed-trackers--check-cveorg-publication-state).

  **Pick the matching canned-response template** rather than
  free-drafting wording. The adopting project's
  [`<project-config>/canned-responses.md`](../../<project-config>/canned-responses.md)
  carries one template per lifecycle transition — *"CVE allocated"*,
  *"Fix PR opened"*, *"Fix PR merged"*, *"Release shipped"*,
  *"Advisory sent"*, *"CVE published on cve.org"*, *"Credit
  correction"*. Substitute the SCREAMING_SNAKE_CASE placeholders
  (`CVE_ID`, `PR_URL`, `VERSION`, `ADVISORY_URL`, `RELEASE_URL`)
  with the concrete values read from the tracker body and the
  Step 1b / Step 1g signals. Only draft from scratch if the
  transition is not in the canned set; if you do, follow the
  "Brevity: emails state facts, not context" rule in
  [`AGENTS.md`](../../AGENTS.md) and offer to add the new
  wording to the canned-responses file as a follow-up.

  Each status update follows the three-paragraph shape from the
  "Brevity: emails state facts, not context" section of
  [`AGENTS.md`](../../AGENTS.md): (a) one sentence on what
  changed, (b) one sentence on what comes next and roughly when,
  (c) the relevant artifact URLs on their own line(s). Nothing else.
  No re-introduction of the vulnerability, no recap of earlier
  messages on the same thread, no process explanation, no
  speculation about severity or schedule beyond the single
  forward-looking sentence. The reporter read the previous update
  on this same thread — trust that and do not restate it.

  Always reply on the **original** Gmail thread (the one identified
  in Step 1c), not on the GitHub-notifications mirror thread.

  **Use full, clickable URLs for every reference in the email body.**
  Gmail renders plain URLs as clickable links; shorthand like
  ``<upstream>#65346`` or ``<tracker>#261`` does **not**
  render as a link and forces the reporter to reconstruct the URL by
  hand. Concretely:

  - For the internal tracking issue (allowed on the private mail
    thread), write the **full** URL:
    ``https://github.com/<tracker>/issues/<N>``. Do not use
    ``#<N>`` or ``<tracker>#<N>`` shorthand.
  - For fix PRs on ``<upstream>``, write the **full** URL:
    ``https://github.com/<upstream>/pull/<N>``. Do not use
    ``<upstream>#<N>`` shorthand.
  - Same rule for any other GitHub reference you mention in the body
    (public issues, commits, security advisories): always the full
    URL. Markdown-link syntax (``[text](url)``) does **not** render
    in plain-text email — use the bare URL.
  - CVE IDs appear as **plain ``CVE-YYYY-NNNN`` inline text only**
    — email clients typically do not autolink them, which is the
    intended behaviour. **Never** include the CVE-tool URL
    (``<cve-tool-url>/cve5/CVE-YYYY-NNNN``) in a
    reporter email: the tool is access-gated, the reporter
    cannot authenticate, and the URL exposes internal tooling to
    an external party. Once the CVE is **published** on
    ``cve.org`` (advisory sent, ``announced`` label set on the
    tracker), the ``cve.org`` URL
    (``https://www.cve.org/CVERecord?id=CVE-YYYY-NNNN``) is an
    acceptable clickable alternative, but plain CVE-ID text is
    still the default. See the "Reporter emails: CVE ID only,
    never the CVE-tool URL" subsection of
    [`AGENTS.md`](../../AGENTS.md) for the full rule +
    rationale + the pre-draft self-check.
  - Advisory archive URLs (``<mail-archive-url>/thread/...``) are
    already full URLs; just paste them as-is.

  This is specific to the **email** path. Comments on the
  ``<tracker>`` issue itself should still use the
  markdown-linked ``[#<N>](url)`` / ``[<upstream>#<N>](url)``
  form per Golden rule 2, because GitHub does render that markdown.

  **Confidentiality:** tracker URLs are identifiers — public-safe
  per the
  [Confidentiality of `<tracker>`](../../AGENTS.md#confidentiality-of-the-tracker-repository)
  rule. A status-update email to the reporter on the
  `<security-list>` thread *may* include the
  `<tracker>` tracking-issue URL; on a public surface (a public
  `<upstream>` PR description, a public commit message, the
  archived advisory) the same URL is also fine **as long as the
  surrounding text does not characterise the change as a security
  fix** before the advisory ships. What stays internal is the
  *content* of the tracker — comment quotes, label transitions,
  rollup-entry text, severity assessments — and the security
  framing of an embargoed PR. When the recipient is an external
  reporter who cannot access the tracker, pair the URL with a
  one-line note that the link is an identifier-only reference (see
  *Sharing a tracker URL with someone who cannot access it* in
  AGENTS.md).

  **Do not re-ask questions that have already been asked.** Before drafting,
  scan the existing thread end-to-end for any open question we have already
  put to the reporter — most importantly the credit-preference question, but
  also any technical follow-ups. If a question is already pending an answer
  from the reporter, **omit it from the new draft**. Restate the credit
  question only if (a) it has never been asked on the thread, or (b) more than
  ~7 days have passed since it was last asked **and** publication is imminent.
  When in doubt, ask the user before re-pinging the reporter — pinging twice
  about the same question is rude and gets us blocklisted.

  Concrete check: when you find a previous message from the security team in
  the thread, look for keywords like *"credited"*, *"credit"*, *"how would
  you like to be"*, *"name (and, if applicable, affiliation"*, or *"prefer to
  remain anonymous"*. If any of those are present in a message we sent and
  the reporter has not replied, the credit question is **already pending** —
  do not re-ask.

- **Status update on the GitHub issue (`<tracker>`)** — **every
  status change must also be recorded on the issue itself**, not
  only sent by email. The two-channels rationale (email keeps the
  reporter, the issue record keeps the team and the release
  manager) lives in
  [`docs/security/roles.md` — Recording status transitions on the tracker](../../docs/security/roles.md#recording-status-transitions-on-the-tracker).

  **The status record lives in a single rollup comment, not a new
  comment per sync.** The first bot-authored comment on a tracker
  is the **rollup comment** (created by the
  [`security-issue-import`](../security-issue-import/SKILL.md)
  skill); every subsequent pass — this sync skill, security-cve-allocate,
  security-issue-deduplicate, security-issue-fix — appends a new
  *entry* to that comment instead of posting a fresh one. Readers
  scroll one comment instead of fifteen. The full shape, summary
  conventions, upsert recipe, and legacy-comment-folding rules
  live in the shared spec at
  [`tools/github/status-rollup.md`](../../tools/github/status-rollup.md).
  Re-read that file before composing the entry body — the
  zero-extra-spacing rule is load-bearing and easy to miss.

  **Standalone comments are reserved for release-manager
  instructions only.** The rollup is the default surface for
  every sync output — status changes, label rationale, milestone
  moves, assignee swaps, reporter-draft notes, fix-PR links,
  CVE-review-comment surfacing, legacy-fold entries, recap
  pointers, blockers, *everything*. The **only** comment shapes
  this skill posts as separate, first-class comments outside the
  rollup are the two **release-manager-directed call-to-action**
  comments documented further down in this Step 2b list: the
  *Release-manager hand-off comment* (fired at the
  `pr merged` → `fix released` transition, Step 12) and the
  *Publication-ready notification comment* (fired at the
  *Public advisory URL* update, Step 14). Both exist because they
  tell the RM to *do something next* on a fresh, dated,
  mention-bearing surface — the rollup's `<details>`-collapsed
  entries are the wrong shape for an actionable nudge. If a
  proposal does not fit one of those two shapes, it goes into the
  rollup. When in doubt, default to the rollup; do not invent a
  new standalone-comment shape because something "feels important
  enough".

  **Entry shape for a sync pass.** Inside the rollup's
  `<details>` block, emit:

  ```markdown
  <details><summary><YYYY-MM-DD> · @<author-handle> · Sync (<short headline>)</summary>

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

  </details>
  ```

  Because the entire entry is already inside a `<details>`
  collapsed by default (the scroller never sees it until they
  expand the summary), the old pre-rollup *"keep visible part
  under six lines"* cap is retired. Write what the auditor needs
  — but do not pad. Each entry is *incremental*: what changed in
  this pass, what comes next. Earlier state lives in earlier
  entries; do not restate.

  **Reporter-notification line options** (one exactly, when
  applicable — omit when no reporter notification is meaningful):

  - *"Reporter has been notified on the original mail thread."* —
    when a status-update draft has been created in the same sync.
  - *"No reporter notification needed (reporter is on the security
    team)."* — only if the real reporter is themselves a member of
    the security team and is already in the loop.
  - *"Reporter notification still pending — see draft `<draftId>`."*
    — if a draft was created but the user has not yet sent it.
    **Before emitting this line**, call
    `mcp__claude_ai_Gmail__list_drafts` and confirm `<draftId>` is
    in the result. If it is gone (sent or discarded between draft
    creation and this status-comment post), flip to *"Reporter
    draft `<draftId>` is no longer in Drafts — sent or
    discarded."* — never assert "still pending" without checking.
    This rule applies on **every** sync that emits the line,
    including the sync that created the draft (the user may have
    switched to Gmail and sent it before the comment landed). See
    the [verify-before-claim rule](../../tools/gmail/operations.md#verify-before-claim--never-assert-a-draft-is-still-pending-without-checking)
    for the full rationale.

  **Summary action-label for a sync pass** — see the table in
  [`status-rollup.md`](../../tools/github/status-rollup.md#summary--action-labels).
  Use `Sync (<one-phrase headline>)` for an ordinary pass,
  `Sync (Step 4 escalation)` for an escalation, or
  `Reformat (N legacy comments folded)` when this pass's primary
  purpose is migrating pre-rollup bot comments (see below).

  **Apply recipe** — use the upsert recipe in
  [`status-rollup.md` — Upsert recipe](../../tools/github/status-rollup.md#upsert-recipe--append-to-an-existing-rollup-or-create-one).
  For a tracker that already carries a rollup (the common case)
  this is `gh api -X PATCH repos/<tracker>/issues/comments/<id>
  --input <json-body>` — a single PATCH on the existing rollup,
  not a fresh `gh issue comment`. The PATCH surfaces on the
  tracker as an *edit* of the rollup comment, not as a new
  timeline event, which is exactly the noise reduction the
  rollup is for.

  For a tracker with **no rollup yet** (legacy tracker pre-dating
  the convention), the sync pass creates it via Step 2b of the
  upsert recipe and immediately runs the legacy-fold sub-step
  below so the new rollup absorbs every pre-existing bot
  comment.

  **Fold legacy bot comments into the rollup.** Every sync pass
  runs a legacy-fold sub-step. Step 1d's comment-mining scan
  surfaces every pre-rollup bot comment on the tracker using the
  detection rules in
  [`status-rollup.md` — Detecting a legacy bot comment](../../tools/github/status-rollup.md#detecting-a-legacy-bot-comment)
  (content-anchored sweep: author on the security-team roster **and**
  body starts with one of `**Sync `, `**Status update`, `**Merged `,
  `**Closing as duplicate`, `**Split for scope clarity`, `**Imported
  on `, `**Process-step escalation`, `**Allocated CVE`, or the
  bare-text `Sync status (` / `Sync YYYY-MM-DD` / `Status update`
  legacy prefixes, or a content tell like `security-issue-sync
  skill`). For each hit, the Step 2 proposal carries a numbered
  item: *"fold legacy comment `<url>` (`<YYYY-MM-DD>`, first line
  <first-line>) into the rollup as a `<Action>` entry, then
  delete the original"*. On user confirmation:

  1. Read the legacy comment's body and `createdAt`.
  2. Wrap in a rollup entry with summary
     `<createdAt-date> · @<author-login> · <derived-Action>`.
  3. Left-trim every line in the body (a single stray leading
     space wrecks markdown rendering inside `<details>`).
  4. Append to the rollup via the upsert recipe (oldest-first,
     preserving chronological order).
  5. **Only after the PATCH succeeds**, delete the original with
     `gh api -X DELETE repos/<tracker>/issues/comments/<id>`.

  Never delete a legacy comment before the append lands. Never
  touch a comment authored by someone outside the security-team
  roster (that is reporter discussion, not bot noise).

  When the same sync pass also needs to write a regular sync
  entry, the legacy-fold entries are appended **first**
  (chronologically), then the sync entry last. Tag the pass's
  own summary as
  `Reformat (N legacy comments folded)` when the fold is the
  primary action; otherwise use `Sync (<headline>)` and mention
  the fold count in the entry body.

  **Before emitting any rollup body — run the zero-whitespace
  self-check.** `<details>` blocks in GitHub markdown break
  silently when any line inside carries leading whitespace, or
  when the blank-line-after-`<summary>` is missing. Re-read
  [`status-rollup.md` — The rollup comment shape](../../tools/github/status-rollup.md#the-rollup-comment-shape)
  before posting; the bug manifests as the entry rendering as a
  single preformatted block and hiding every link. Do not
  indent entries for "readability".

- **Remediation-developer fill-fields comment** — when this sync
  pass detects that mandatory CVE body fields are not yet
  populated, propose posting (or PATCH-updating) a comment tagging
  the **remediation developer** with the concrete list of missing
  fields. The tracker stays assigned to the remediation developer;
  the release-manager hand-off is **not** fired until the gate
  clears.

  **This is its own first-class comment, not a rollup entry**, for
  the same reason as the RM hand-off — it carries a concrete
  call-to-action that needs to be visible at-a-glance, not hidden
  inside a `<details>` block.

  **Trigger — two firing points**:

  1. **At the `pr created` → `pr merged` transition (Step 11)** —
     when sync proposes the `pr created` → `pr merged` label swap,
     check whether all six mandatory body fields are populated
     (*CWE*, *Affected versions*, *Severity*, *Reporter credited
     as*, *Short public summary for publish*, *PR with the fix*).
     If any field is empty / `_No response_`, propose the
     fill-fields comment with that field list. Issue stays
     assigned to the remediation developer (who is also the fix-PR
     author and the current assignee in the common case). **Do
     not propose any RM-related action at Step 11**; that belongs
     to Step 12.
  2. **At the `pr merged` → `fix released` transition (Step 12)** —
     after sync's Step 5b push attempt, check the CVE record state
     in Vulnogram. If the state is still `DRAFT` for any reason
     (one of the body fields was still empty, the JSON push was
     blocked, the API push happened but the state did not advance
     because the JSON failed CNA-schema validation, etc.),
     **re-fire** the fill-fields comment with the refreshed list
     of what is still blocking. **Do not** fire the RM hand-off,
     do not flip the label to `fix released`, do not swap the
     assignee — those all gate on `state == REVIEW`. A subsequent
     sync run that finds the state finally promoted to `REVIEW`
     will clear the gate and fire the RM hand-off then.

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
  - **Marker found, current body does NOT match** (typically: the
    missing-fields list changed because the remediation developer
    filled some — but not all — fields between sync runs) —
    PATCH-edit the existing comment with the refreshed list.

  **Body source.** `tools/<cve-tool>/remediation-developer-fill-fields-comment.md`
  (for Vulnogram:
  [`tools/cve-tool-vulnogram/remediation-developer-fill-fields-comment.md`](../../tools/cve-tool-vulnogram/remediation-developer-fill-fields-comment.md)).
  This template carries no OAuth-pushed / manual-paste variants —
  the remediation developer's job is to fill in body fields, and
  the API-push state is invisible to them.

  **Resolving placeholders.** Inherits the same resolution rules
  as the hand-off comment for the placeholders it shares
  (`CVE_ID`, `SOURCE_TAB_URL`, `TRACKER_URL`, `SECURITY_LIST`,
  `SECURITY_LIST_DOMAIN`, `FRAMEWORK_README_URL`,
  `FRAMEWORK_SYNC_SKILL_URL`). Plus two unique placeholders:

  - `REMEDIATION_DEVELOPER_HANDLE` — read from the tracker's
    *Remediation developer* body field. When the field carries a
    `Full Name (@handle)` line, extract the `@handle` token. When
    only the name is set, fall back to the fix-PR author's
    `@`-handle (looked up via `gh pr view --json author --jq
    .author.login`) and propose adding the `@handle` to the body
    field on the same sync pass (so the next sync resolves
    cleanly).
  - `MISSING_FIELDS_LIST` — Markdown bullet list, one line per
    empty mandatory field, of the shape
    Markdown bullets shaped `- **<Field name>** — currently the
    empty placeholder; <one-line hint on how to fill it>`. The hint
    comes from the project's
    *Issue-template fields* docs; for Vulnogram-based projects
    the hint is the field's `description` from
    `<project-config>/.github/ISSUE_TEMPLATE/issue_report.yml`.

  **Apply mechanic.** See the *Remediation-developer fill-fields
  comment* bullet in Step 4 below; POST vs PATCH decided by the
  marker check above.

  **Recap.** Surface the comment URL (new or PATCH-edited) in the
  recap (Step 6) so the user can click through and verify the
  list, plus a one-line note *"hand-off to RM blocked on N
  field(s); fill-fields comment posted/refreshed"*.

- **Release-manager hand-off comment** — when this sync pass
  proposes the `pr merged` → `fix released` label swap (Step 12),
  **also** propose posting a separate hand-off comment that walks
  the release manager through the rest of the lifecycle (Steps
  13–15) end-to-end, on a single tracker page, without forcing them
  to consult the rollup or external docs.

  **This is its own first-class comment, not a rollup entry.** The
  rollup is for the security team's audit trail and accumulates many
  small entries; the hand-off comment is a one-shot orientation
  surface for the release manager and must stay readable as a single
  comment. Folding it into the rollup would bury the call-to-action
  inside a `<details>` block.

  **Trigger — gated on `state == REVIEW`.** Fires *exactly once*
  per tracker, at the sync pass that proposes
  `pr merged` → `fix released` **AND** finds the CVE record state
  in Vulnogram is `REVIEW` (verified by sync after Step 5b's push
  attempt — the push includes the `body.CNA_private.state =
  "REVIEW"` advance when all six mandatory body fields are
  populated). When the CVE record is still in `DRAFT` after the
  push attempt, **do not** fire this hand-off; fire the
  *Remediation-developer fill-fields comment* instead and leave
  the tracker assigned to the remediation developer. **The RM
  must never receive this hand-off while the record is in
  `DRAFT`** — that invariant is asserted in the template body
  itself so the RM can recognise a misfire if it ever happens.
  Do not propose it earlier than Step 12; do not propose it on
  subsequent runs once it has already been posted (idempotency
  check below).

  **Idempotency + variant edit-in-place.** Before proposing, scan
  the issue's existing comments for the marker
  ```html
  <!-- apache-magpie: release-manager-handoff v1 -->
  ```
  exactly. The marker is on line 1 of the comment body so a
  literal `gh issue view --json comments --jq` filter detects it
  cheaply. Three outcomes:

  - **No marker found.** Propose a fresh POST of the appropriate
    variant (per Step 5c's decision).
  - **Marker found, current body matches the variant the skill
    would render this run.** No-op; surface as *"hand-off comment
    already posted on `<comment-url>` and matches the current
    variant (skipping)"* in the observed-state dump.
  - **Marker found, current body does NOT match the variant the
    skill would render this run.** Propose a PATCH-in-place
    (rewrite the body to the current variant). Common cases:
    a previous sync posted the manual-paste variant and this
    sync's OAuth push succeeded → flip to the OAuth-pushed
    variant; or vice-versa (cookie expired between sync runs).
    The PATCH preserves the comment URL, the timeline position,
    and any notifications already delivered for it; the body
    flip is what the RM cares about. Same PATCH-don't-post
    rationale as the rollup-comment upsert.

  **Body source.** The comment body comes from the project's
  configured CVE tool, in two **variants** picked by Step 5c:

  - **OAuth-pushed variant** —
    `tools/<cve-tool>/release-manager-handoff-comment-oauth-pushed.md`
    (for Vulnogram:
    [`tools/cve-tool-vulnogram/release-manager-handoff-comment-oauth-pushed.md`](../../tools/cve-tool-vulnogram/release-manager-handoff-comment-oauth-pushed.md)).
    Used when Step 5b's `vulnogram-api-record-update` succeeded
    this sync run.
  - **Manual-paste variant (today's default)** —
    `tools/<cve-tool>/release-manager-handoff-comment.md`
    (for Vulnogram:
    [`tools/cve-tool-vulnogram/release-manager-handoff-comment.md`](../../tools/cve-tool-vulnogram/release-manager-handoff-comment.md)).
    Used when Step 5b skipped (no credentials, expired session)
    or the push failed.

  Both variants carry the same marker on line 1, so idempotency
  detection is unchanged. Both templates are parameterised; the
  substitutions the skill performs are listed in each template's
  HTML-comment header (the OAuth-pushed variant additionally
  takes `PUSH_TIMESTAMP`). Do not fork or paraphrase the
  template body in the proposal — load it verbatim, substitute
  the placeholders, post or PATCH per the idempotency rules
  above.

  **Resolving placeholders.** All values come from configuration or
  from the tracker itself, so there is no free-form drafting:

  - `CVE_ID` — from the tracker's *CVE tool link* body field.
  - `RM_HANDLE` — looked up via the three-source cascade in Step 2c
    (project's *Known release managers* / Release Plan wiki / dev@
    `[RESULT][VOTE]` thread). Same lookup the assignee swap uses;
    do it once and reuse.
  - `SECURITY_LIST`, `USERS_LIST`, `ANNOUNCE_LIST` — from
    [`<project-config>/project.md`](../../<project-config>/project.md#mailing-lists).
  - `SOURCE_TAB_URL`, `EMAIL_TAB_URL` — substitute `<CVE-ID>` into
    `cve_tool_record_url_template` (from project.md), append
    `#source` / `#email` per [`tools/cve-tool-vulnogram/record.md`](../../tools/cve-tool-vulnogram/record.md#record-urls).
  - `JSON_ANCHOR_URL` — the deep link the `generate-cve-json` tool
    prints on every regen (the
    `https://github.com/<tracker>/issues/<N>#cve-json--paste-ready-for-<cve-id-slug>`
    anchor).
  - `ARCHIVE_SCAN_URL` — the project's PonyMail public-search URL
    template (`ponymail_public_search_url_template` from project.md),
    parameterised with the CVE ID.
  - `FRAMEWORK_RECORD_MD_URL`, `FRAMEWORK_SYNC_SKILL_URL`,
    `FRAMEWORK_README_URL` — absolute GitHub URLs into
    `apache/magpie` `main`, since the framework lives in
    the gitignored snapshot at `<adopter-tracker>/.apache-magpie/`
    that does not render through the parent-repo viewer (per the
    absolute-URL rule used elsewhere in this repo).
  - `CANNED_RESPONSES_URL` — absolute GitHub URL into the tracker
    repo's `<project-config>/canned-responses.md`.

  **Apply mechanic** — see the *Release-manager hand-off comment*
  bullet in Step 4 below; depending on the idempotency outcome it
  is either a fresh `gh issue comment` (first hand-off) or a
  `gh api -X PATCH` on the existing comment's REST id (variant
  flip). Neither path PATCHes the rollup.

  **Recap.** Surface the comment URL (new or PATCH-edited) in the recap
  (Step 6) so the user can click through and verify the result.
  When the path was a PATCH, the recap notes which variant the
  body now carries (*"flipped to OAuth-pushed variant after this
  sync's auto-push succeeded"* or vice-versa).

- **Publication-ready notification comment** — when this sync pass
  proposes populating the *Public advisory URL* body field (Step 14
  — see the *Advisory archived on `<users-list>`* row of the Step 1d
  table), **also** propose posting a separate publication-ready
  notification comment on the tracker. The comment tells the release
  manager that the archive URL has been captured, the JSON has been
  regenerated to include it as a `vendor-advisory` reference, and
  the final paste + `READY` → `PUBLIC` move is now unblocked.

  **Why a second comment instead of one comment with two states.**
  The hand-off comment posted at Step 12 has `READY` as its
  rendered-final state and `PUBLIC` as a "wait for follow-up"
  pointer. The follow-up is exactly this notification. Splitting
  the call-to-action into two comments (rather than nudging the RM
  to re-read step 7 of the same comment from days ago) gives the
  RM a fresh, dated surface for the second action and a working
  `@`-mention notification.

  **Trigger.** Fires *exactly once* per tracker, at the same sync
  pass that proposes the *Public advisory URL* body update. Do not
  propose it earlier (the URL is not yet captured) or repeatedly
  (idempotency check below).

  **Idempotency.** Before proposing, scan the issue's existing
  comments for the marker
  ```html
  <!-- apache-magpie: release-manager-publication-ready v1 -->
  ```
  exactly. If a comment carrying this marker already exists, do not
  re-post — surface as *"publication-ready comment already posted on
  `<comment-url>` (skipping)"* and move on.

  **Body source.** Same load-from-tool-doc model as the hand-off
  comment — the body comes from
  `tools/<cve-tool>/release-manager-publication-comment.md` (for
  Vulnogram:
  [`tools/cve-tool-vulnogram/release-manager-publication-comment.md`](../../tools/cve-tool-vulnogram/release-manager-publication-comment.md)).
  Placeholders substituted: `CVE_ID`, `RM_HANDLE`, `ARCHIVE_URL`
  (the just-captured archive URL), `SOURCE_TAB_URL`,
  `JSON_ANCHOR_URL`, `CVE_ORG_URL`
  (`https://www.cve.org/CVERecord?id=<CVE-ID>`).

  **Apply mechanic** — same as the hand-off comment: a fresh
  `gh issue comment`, surfaced in the recap.

- **Overdue-for-disclosure escalation** — when `overdue_for_disclosure: true`
  (Step 1a) the tracker has passed its CVD window without the advisory being
  sent.  Propose appending a rollup entry that:

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

  When `grace_period_expired: true` (fix shipped but grace period has also
  lapsed), promote the rollup entry to a **separate first-class comment** (not
  a `<details>` entry) so it is immediately visible to the release manager and
  the security team without expanding the rollup.  Use the same idempotency
  check as the RM hand-off comment — scan for the marker
  ```html
  <!-- apache-magpie: disclosure-overdue v1 -->
  ```
  before proposing; if it already exists, update it in-place via PATCH rather
  than posting a duplicate.

- **Distributor pre-announcement draft** — when `distributor_notify_pending: true`
  (Step 1a) the project maintains an embargo distributor list and the fix is
  about to ship.  Propose a Gmail draft pre-announcement to the distributor
  list declared in `<project-config>/distributor-list.md` (if that file exists;
  if absent, surface a one-line note that the adopter should create it and
  document the list URL there before this proposal can be executed).  The draft:

  - Names the CVE ID and the affected product/versions from the tracker body.
  - States the expected public disclosure date as
    `createdAt + window_days + grace_period_days` (or earlier if the team
    decides to disclose sooner) — do not commit to a specific calendar date
    unless the advisory send date has already been confirmed by the team.
  - Omits any detail beyond what is in the advisory's *Short public summary
    for publish* body field — the pre-announcement is not the advisory itself.
  - Is marked **DRAFT, NEVER SEND** until the team confirms the wording, the
    recipient list, and the timing.

  Trigger condition: `distributor_notify_pending: true` AND the `announced`
  label is absent AND no pre-announcement draft already exists in Gmail for
  this tracker's thread (check via the existing Gmail draft-scan the skill
  performs in Step 1e before proposing a new draft).

- **Draft email to reporter (other reasons)** — whenever the ball is in our
  court on the email thread for any other reason (a question from the
  reporter, a follow-up needed for triage, communicating a negative
  assessment), propose a **Gmail draft** reply (not a sent message). State
  the intent of the draft in one line and prefer to reuse a canned response
  from [`canned-responses.md`](../../<project-config>/canned-responses.md) verbatim where
  one applies. Show the exact subject, recipients, In-Reply-To, and body in
  the proposal.

  **Brevity** applies here too — if no canned response fits and you are
  drafting fresh wording, keep it to the facts the reporter needs (the
  question being answered, the decision being communicated) plus one
  artifact link. See the "Brevity: emails state facts, not context"
  section of [`AGENTS.md`](../../AGENTS.md).

  **Route through the forwarder-relay adapter when one is registered.**
  If the parent tracker carries a forwarder-adapter marker (set by
  the optional
  [`security-issue-import-via-forwarder`](../security-issue-import-via-forwarder/SKILL.md)
  sub-skill when `forwarders.enabled` is non-empty in
  [`<project-config>/project.md`](../../<project-config>/project.md)
  and the inbound message matched a registered adapter), route any
  drafted reply through that adapter's `contact_handle` and use the
  adapter's `reporter_addressing_block` convention. See
  [`tools/forwarder-relay/README.md`](../../tools/forwarder-relay/README.md)
  for the contract — including the per-event do-relay / suppress
  matrix the adapter applies to decide whether a draft should be
  proposed at all (e.g. CVE-allocated and advisory-sent events
  relay; routine credit-form questions and reviewer-comment relays
  are suppressed). When no adapter is registered (the
  `forwarders.enabled` list is empty, or the tracker has no
  forwarder-adapter marker), proceed in direct-reporter mode as
  written above — the draft targets the reporter on the inbound
  thread.

  **Never send.** Always create a draft. Prefer attaching it to the
  inbound mail thread (the preferred `oauth_curl` backend uses
  `--thread-id` directly and preserves URLs verbatim; the discouraged
  `claude_ai_mcp` backend resolves the latest message ID from the
  inbound `threadId` and passes it as `replyToMessageId` but rewrites
  embedded URLs — see [`draft-backends.md`](../../tools/gmail/draft-backends.md#privacy-warning--the-claudeai-gmail-mcp-rewrites-embedded-urls-into-google-tracking-redirects)). If Step 1c could not resolve a `threadId`,
  fall back to a subject-matched draft (thread-attachment parameter
  omitted, `subject: Re: <root subject>`) per the threading rule in
  [`tools/gmail/threading.md`](../../tools/gmail/threading.md).
  Surface which path was taken in the proposal. The Gmail MCP's
  no-update-no-delete limitation — and the resulting rule that
  corrections surface the prior `draftId` for manual discard
  rather than silently shadowing it — is documented in
  [`tools/gmail/operations.md`](../../tools/gmail/operations.md#hard-limitation--no-update-no-delete).
