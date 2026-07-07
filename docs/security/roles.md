<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Security workflow — roles, conventions, and role guides](#security-workflow--roles-conventions-and-role-guides)
  - [Who this guide is for](#who-this-guide-is-for)
  - [Shared conventions](#shared-conventions)
    - [Keeping the reporter informed](#keeping-the-reporter-informed)
    - [Recording status transitions on the tracker](#recording-status-transitions-on-the-tracker)
    - [Confidentiality](#confidentiality)
  - [For issue triagers — Steps 1–6](#for-issue-triagers--steps-16)
    - [Daily triage loop](#daily-triage-loop)
    - [Assessing a report](#assessing-a-report)
    - [Allocating the CVE](#allocating-the-cve)
    - [Tools you use most](#tools-you-use-most)
  - [For remediation developers — Steps 7–11](#for-remediation-developers--steps-711)
    - [Picking up a tracker](#picking-up-a-tracker)
    - [Attempting an automated fix](#attempting-an-automated-fix)
    - [Opening the public fix PR manually](#opening-the-public-fix-pr-manually)
    - [Private-PR fallback](#private-pr-fallback)
    - [Handoff to the release manager](#handoff-to-the-release-manager)
    - [Tools you use most](#tools-you-use-most-1)
  - [For release managers — Steps 12–15](#for-release-managers--steps-1215)
    - [Handoff from the remediation developer](#handoff-from-the-remediation-developer)
    - [Sending the advisory](#sending-the-advisory)
    - [Capturing the public archive URL and closing out](#capturing-the-public-archive-url-and-closing-out)
    - [Publishing the CVE and closing the issue](#publishing-the-cve-and-closing-the-issue)
    - [Post-release credit corrections](#post-release-credit-corrections)
    - [Tools you use most](#tools-you-use-most-2)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security workflow — roles, conventions, and role guides

Three roles share the security-issue handling process —
issue triager (Steps 1–6), remediation developer (Steps 7–11),
and release manager (Steps 12–15). This document covers who
owns what, the shared conventions every role observes, and
the per-role workflow. The detailed step descriptions live
in [`process.md`](process.md).

## Who this guide is for

Three roles share the handling process. Any security-team member can take on
any of them for a given issue, and in practice people rotate — but at any
moment a given tracking issue has exactly one person who owns the next move.

Pick whichever applies to you now:

- **I am new to the security team, or I mostly just want to comment on
  issues.** Read [Shared conventions](#shared-conventions) below. The
  adopting project's security-issues board — see
  `<project-config>/project.md → GitHub project board` — is the main
  view. You do not need an agent for commenting.
- **I am a rotational triager** — running `import new reports` and
  `sync all` a few times a week. Jump to
  [For issue triagers — Steps 1–6](#for-issue-triagers--steps-16).
- **I picked up a tracker and am about to open a fix PR.** Jump to
  [For remediation developers — Steps 7–11](#for-remediation-developers--steps-711).
- **I am the release manager for a cut containing a security fix.** Jump to
  [For release managers — Steps 12–15](#for-release-managers--steps-1215).
- **I am looking up a specific step or label.** Go straight to
  [Process reference](process.md#process-reference-the-16-steps) or
  [Label lifecycle](process.md#label-lifecycle).

## Shared conventions

These conventions bind every role. If you are unsure whether a rule applies to
you, it does.

### Keeping the reporter informed

The security team commits to keeping the original reporter informed about the
state of their report **at every status transition**, on the original mail
thread (not on the GitHub-notifications mirror thread). A short status update
should be sent to the reporter whenever any of the following happens:

* the report has been acknowledged or assessed (valid / invalid);
* a CVE has been allocated;
* a fix PR has been opened;
* a fix PR has been **merged**;
* the issue has been scheduled for a specific release (milestone set);
* the release has shipped and the public advisory has been sent;
* the CVE record has been published on cve.org (completes the disclosure);
* any credits or fields visible in the eventual public advisory have changed.

Each status update should plainly state what has changed, link to the relevant
artifact (PR URL, CVE ID, advisory link), and state what comes next. If the
reporter has not yet replied with their preferred credit, ask the
credit-preference question — but **do not re-ask it if it has already been
asked** on the same thread and is still awaiting a reply. Pinging the reporter
twice about the same open question is rude and gets us blocklisted; default to
the reporter's full name from the original email if they do not respond
before publication.

Reusable wording for the common cases lives in
[`<project-config>/canned-responses.md`](<project-config>/canned-responses.md) — consult it before drafting a
reply from scratch.

**When there's no direct reporter contact** (ASF-relay reports,
read-only GHSA, anonymous tips), the team communicates with the
*forwarder* instead — the security-team member or relay service
that delivered the report. In that **via-forwarder mode**, only
the five lifecycle milestones (report accepted as valid, report
invalidated, CVE allocated, advisory sent, additional information
requested) are relayed. Regular workflow status (label flips,
PR-opened, PR-merged) and credit-confirmation questions are
**not** sent to the forwarder — they would burn the forwarder's
goodwill with low-signal updates. See
[`forwarder-routing-policy.md`](forwarder-routing-policy.md) for
detection rules, the full milestone list, and the negative space.

### Recording status transitions on the tracker

**Every status transition must also be recorded as a comment on the GitHub
issue in `<tracker>`**, not only sent by email. The two channels
serve different audiences: the email keeps the reporter informed; the issue
comment keeps the rest of the security team and the release manager informed
without forcing them to reconstruct the state from labels and timestamps. The
comment should briefly state what changed, link to the artifact (PR URL, CVE
ID, advisory link), and indicate whether the reporter has been notified.

### Confidentiality

Confidentiality of the private tracker (`<tracker>` for the
adopting project) is both a **lifecycle rule** and a **writing rule**:
every transition you record on a tracker, every status comment, every
email draft has to respect it. The full rule set — forbidden surfaces,
allowed surfaces, scrubbing guidance, the exception buckets for private
`security@` / `private@` threads and in-repo `gh issue comment` calls —
lives in
[`AGENTS.md` — Confidentiality of the tracker repository](../../AGENTS.md#confidentiality-of-the-tracker-repository).
Read it before editing anything that might be seen outside the team.

The [threat model](threat-model.md) enumerates the trust boundaries
this rule defends and the adversaries each role should expect on
those boundaries.

## For issue triagers — Steps 1–6

You own the tracker from an inbound report on `<security-list>`
through to a CVE allocated, a scope label applied, and the issue ready for a
remediation developer to pick up. Step 6 (the CVE allocation itself) is
PMC-gated: **only the adopting project's PMC members can submit the
CVE-tool allocation form**. If you are not on the PMC you relay a
pre-drafted request to a PMC
member — either way you are the one who lands the resulting CVE ID back into
the tracker.

### Daily triage loop

A typical triage sweep runs three skills in order:

1. **`import new reports`** —
   [`security-issue-import`](../../skills/security-issue-import/SKILL.md)
   scans `<security-list>` for threads not yet imported,
   classifies each candidate (real report vs. automated-scan / consolidated /
   media / spam), and proposes a tracker per valid report plus a
   receipt-of-confirmation Gmail draft. See
   [Step 2](process.md#step-2--import-the-report).
2. **`sync all`** —
   [`security-issue-sync`](../../skills/security-issue-sync/SKILL.md)
   reconciles every open tracker against its mail thread, the fix PR, the
   release train, and the users@ archive. Proposes label / milestone /
   assignee / body changes in one pass.
3. **`allocate CVE for issue #N`** —
   [`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md) when a report has
   been assessed as valid. See [Step 6](process.md#step-6--allocate-the-cve).

Nothing is applied without an explicit confirmation — each skill is a
proposal engine, not an auto-pilot.

### Assessing a report

For each `needs triage` tracker, drive the validity assessment in comments,
pulling at least one other security-team member into the discussion. Use the
canned-response templates from [`<project-config>/canned-responses.md`](<project-config>/canned-responses.md)
for negative assessments so the tone stays polite-but-firm.

When the report is confirmed valid, apply exactly one scope label from
the project's scope set (declared in
[`<project-config>/scope-labels.md`](<project-config>/scope-labels.md)).
If a report affects more than one scope, split into per-scope trackers
before allocation — the `security-issue-sync` skill surfaces this as
a blocker. See
[Step 5](process.md#step-5--land-the-validinvalid-consensus).

If discussion stalls for about 30 days, escalate to a broader audience per
[Step 4](process.md#step-4--escalate-stalled-discussions).

### Allocating the CVE

Use [`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md). The skill asks up
front whether you are on the PMC; if not, it reshapes the recipe into an
``@``-mention relay message you forward to a PMC member on the tracker or on
the `<security-list>` thread. Once the allocated `CVE-YYYY-NNNNN`
is pasted back, the skill wires it into the tracker in one pass (the *CVE
tool link* body field, the `cve allocated` label, a status-change comment, a
refreshed CVE-JSON attachment) and hands off to `security-issue-sync` to
reconcile the rest of the tracker. See [Step 6](process.md#step-6--allocate-the-cve)
for the full detail.

### Tools you use most

- [`security-issue-import`](../../skills/security-issue-import/SKILL.md) —
  *"import new reports"* at the start of each triage sweep. The entry point
  into the process for `<security-list>` reports.
- [`security-issue-import-from-pr`](../../skills/security-issue-import-from-pr/SKILL.md) —
  *"import a tracker from PR <N>"* when a security-relevant fix landed
  publicly without going through `<security-list>` and the team has agreed
  it warrants a CVE. Lands directly in the `Assessed` column.
- [`security-issue-sync`](../../skills/security-issue-sync/SKILL.md) —
  *"sync <issue-ref>"* or *"sync all"*. Surfaces stalled issues, missing
  fields, credit replies, and scope-split requirements in one combined
  proposal.
- [`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md) — *"allocate a CVE
  for <issue-ref>"*.
- [`generate-cve-json`](../../tools/cve-tool-vulnogram/generate-cve-json/SKILL.md) — to
  refresh the paste-ready JSON embedded in the issue body on demand.
  (The named example here is the Vulnogram adapter under
  `tools/cve-tool-vulnogram/`; resolved from `cve_authority.tool` in
  [`<project-config>/project.md`](../../<project-config>/project.md#cve-authority)
  — adopters running a different CNA tool point at their own
  `<cve-tool>/` adapter.)
- [`security-issue-deduplicate`](../../skills/security-issue-deduplicate/SKILL.md) —
  when two trackers describe the same root-cause bug discovered
  independently.
- [`security-issue-invalidate`](../../skills/security-issue-invalidate/SKILL.md) —
  *"close NN as invalid"* once Step 5 lands a consensus-invalid
  decision. Applies the `invalid` label, archives the project-board
  item, and (for `<security-list>`-imported trackers) drafts a reply
  to the reporter explaining the reasoning.

## For remediation developers — Steps 7–11

You own the tracker from a CVE allocated to a merged public fix PR in
`<upstream>` (including the `pr merged` hand-off where the tracker sits
waiting for the release train to ship). The role name matches the
`remediation developer` credit you receive in the published CVE record (see
`credits[]` with `type: "remediation developer"` in the generated CVE JSON).

### Picking up a tracker

Pick a tracker that has a scope label, `cve allocated`, and clear consensus
on the fix shape. Self-assign yourself on GitHub so the board reflects
ownership. See [Step 7](process.md#step-7--self-assign-and-implement-the-fix).

### Attempting an automated fix

Before writing the fix by hand, consider letting the
[`security-issue-fix`](../../skills/security-issue-fix/SKILL.md) skill try
it first. Invoked as *"try to fix issue #N"* (or *"draft a PR for #N"*), the
skill:

- runs `security-issue-sync` first to make sure the tracker's state is
  current;
- reads the full tracker discussion and the linked `security@` mail
  thread and decides whether the issue is *easily fixable* — clear
  consensus on the fix shape, small scope, known location in
  `<upstream>`. If it is not, the skill stops and tells you what
  more the tracker needs before it is safe to attempt;
- if it is, proposes an implementation plan (which file(s) to touch,
  what to change, what tests to add) and **waits for your explicit
  confirmation** before making any edits;
- writes the change in your local `<upstream>` clone, runs the
  local static checks and tests, and iterates on failures;
- opens the public PR from your fork via `gh pr create --web` with a
  scrubbed title and body — every public surface (commit message,
  branch name, PR title, PR body, newsfragment) is grep-checked for
  `CVE-`, the `<tracker>` repo slug, `vulnerability`, *"security fix"*
  and similar leakage before being written or pushed;
- updates the `<tracker>` tracking issue with the new PR
  link and applies the `pr created` label, handing back off to
  `security-issue-sync`.

The skill refuses to proceed in cases where a human decision still
needs to happen: reports that are still being assessed, reports not
yet classified as valid vulnerabilities, and changes that require the
private-PR fallback in
[Step 9](process.md#step-9--open-a-private-pr-exceptional-cases). If it refuses,
fall back to the manual flow below.

Even when the skill succeeds end-to-end, you remain the PR's author
and reviewer-facing contact on the public `<upstream>` PR. Stay
on the PR through review and merge.

### Opening the public fix PR manually

If you are writing the fix by hand, write the code change in your local
`<upstream>` clone, run the local checks and tests, and open the PR
via `gh pr create --web`. The PR description **must not** reveal the CVE,
the security nature of the change, or link back to `<tracker>` —
see [Step 8](process.md#step-8--open-a-public-pr-straightforward-cases) and the
confidentiality rules in
[`AGENTS.md`](../../AGENTS.md#confidentiality-of-the-tracker-repository).

Request a `backport-to-v3-2-test` (or equivalent) label on the public PR
when the fix should ship on a patch train.

### Private-PR fallback

In exceptional cases — highly critical fixes, or code that needs private
review — open the PR against the `main` branch of `<tracker>`
instead of `<upstream>`. CI does not run there, so run static checks and
tests manually before asking for review. Once approved, re-open the PR in
`<upstream>` by pushing the branch public. See
[Step 9](process.md#step-9--open-a-private-pr-exceptional-cases).

### Handoff to the release manager

Once the `<upstream>` PR merges, `security-issue-sync` moves the tracker
from `pr created` to `pr merged` and sets the milestone of the release the
fix will ship in. The tracker then waits for the release train.

The `pr merged` → `fix released` hand-off is **gated**: every one of the six
mandatory CVE body fields must be populated (*CWE*, *Affected versions*,
*Severity*, *Reporter credited as*, *Short public summary for publish*,
*PR with the fix*) **and** the CVE record must have been promoted from
`allocated` to `review-ready` in the project's CVE tool — the adapter
named in `cve_authority.tool` (for the airflow-s adopter, the Vulnogram
adapter, where `review-ready` corresponds to the `REVIEW` state). If any
field is still empty when the PR merges (Step 11) or when the release
ships (Step 12), sync posts a **Remediation-developer fill-fields
comment** on the tracker @-mentioning you with the specific missing
fields. The tracker stays assigned to you and the RM hand-off is **not**
posted until you fill them in. See
[Step 11](process.md#step-11--pr-merged) and [Step 12](process.md#step-12--fix-released).

### Tools you use most

- [`security-issue-fix`](../../skills/security-issue-fix/SKILL.md) —
  *"try to fix issue #N"*. Proposes a plan, writes the code, runs local
  tests, and opens a `--web` PR with a scrubbed title/body. See
  [Attempting an automated fix](#attempting-an-automated-fix) above for
  the full flow and the cases where the skill refuses to proceed.
- [`security-issue-sync`](../../skills/security-issue-sync/SKILL.md) — to
  keep the tracker's labels, milestone, and assignee aligned with the PR
  state as it moves through review and merge.

## For release managers — Steps 12–15

You own the tracker from the moment the fix actually ships (`fix released`)
to a closed tracking issue with a PUBLISHED CVE record. The hand-off from
the remediation developer is automatic: `security-issue-sync` detects the
milestone version on PyPI / the Helm registry, swaps `pr merged` →
`fix released`, and assigns the advisory-send to you.

### Handoff from the remediation developer

Watch your `fix released` queue on the board. Until the `pr merged` →
`fix released` swap fires, the tracker is still the remediation developer's
(Step 11 territory). Once it fires, it is yours. See
[Step 12](process.md#step-12--fix-released).

### Sending the advisory

By the time the hand-off comment lands, every mandatory body field is
already populated (Step 12's gate) and the regenerated CVE JSON has been
pushed to the project's CVE tool (the adapter named in `cve_authority.tool`)
in `review-ready` state. Your three actions are the numbered list in the
hand-off comment, all single clicks in the CVE tool — **no shell
commands, no JSON paste:**

1. **Address reviewer feedback (if any) and promote the record from
   `review-ready` to `publish-ready`.** Open the record in the CVE tool —
   the URL is built from `cve_authority.record_url_template` substituted
   with the CVE ID; for adapters that expose a raw-state view, sync also
   includes the `cve_authority.source_tab_url_template` link in the
   hand-off comment. If the CVE reviewer has posted comments, work
   through them on the same thread; when it is clear, promote the
   record to `publish-ready` and save. (For the Vulnogram adapter, that
   is the State dropdown going `REVIEW → READY` on the `#source` tab.)
   Most CVEs go through `review-ready` with no reviewer comments and
   the promotion is immediate.
2. **Preview and send.** The hand-off comment links the CVE tool's
   advisory-email preview — for the Vulnogram adapter, the `#email` tab
   on the record. Verify recipients (`<users-list>` and
   `<announce-list>`) and body, then click the send action.
3. **Stop.** Sync drives the rest at the archive-URL trigger
   ([Step 14](process.md#step-14--capture-the-public-advisory-url-and-close-out)).

Sync does the `fix released → announced - emails sent` flip at Step 14,
not here — you do not touch labels. **Do not close the issue** — sync
does that too, in the same Step 14 combined apply.

### Capturing the public archive URL and closing out

This is a handoff the sync skill handles for you. Once the advisory has
been archived on the users@ list, the next `security-issue-sync` run
fires a **single combined apply** that:

* writes the URL into the *Public advisory URL* body field;
* extracts the short public summary from the archived advisory email and
  writes it back to the *Short public summary for publish* body field;
* flips labels `fix released → announced - emails sent + announced`;
* regenerates and re-pushes the CVE JSON;
* promotes the record from `publish-ready` to `public` in the project's
  CVE tool (the adapter named in `cve_authority.tool`) — the act that
  dispatches the record onto the public CNA feed at
  [`cve.org`](https://cve.org). (For the Vulnogram adapter, that is the
  State dropdown going `READY → PUBLIC` on the record.)
* moves the project board to the `Announced` column;
* closes the tracker;
* archives the tracker from the `Announced` column;
* if every milestone-sibling is also closed at that moment, closes the
  milestone too.

See
[Step 14](process.md#step-14--capture-the-public-advisory-url-and-close-out)
for the full sequence.

### Publishing the CVE and closing the issue

**Nothing to do.** Step 14 above already promoted the CVE record to
`public` in the project's CVE tool, closed the tracker, and archived it
from the board. You receive a purely-informational wrap-up comment as a
timeline marker that the lifecycle is complete. See
[Step 15](process.md#step-15--rm-verifies-the-close-out-landed).

A tracker that sits on `announced - emails sent` without `announced` for
more than a day or two is a signal that sync did not see the advisory
in the `<users-list>` archive yet — re-run sync or wait for the next
scheduled pass.

### Post-release credit corrections

If credits need correction after announcement, respond to the announcement
emails with the missing credits, update the record in the project's CVE
tool (open the URL built from `cve_authority.record_url_template`), and —
where the adapter requires it — ask the upstream CNA/relay to push the
information to `cve.org`. (For the airflow-s adopter on Vulnogram, that
relay is the ASF security team.) See
[Step 16](process.md#step-16--credit-corrections).

### Tools you use most

- [`security-issue-sync`](../../skills/security-issue-sync/SKILL.md) —
  *"sync CVE-YYYY-NNNN"* to drill into one specific CVE before sending the
  advisory (confirms the hand-off comment was posted and reflects the
  current record state). Subsequent syncs by the security team drive the
  post-advisory close-out automatically when the archive URL appears on
  `<users-list>`.
- [`generate-cve-json`](../../tools/cve-tool-vulnogram/generate-cve-json/SKILL.md) — to
  regenerate the attachment on demand when a body field changes after the
  URL has been captured (rarely needed — sync regenerates and re-pushes
  on every relevant body change). The link points at the named ASF
  example; the active generator is the one under `<cve-tool>/` resolved
  from `cve_authority.tool`.
