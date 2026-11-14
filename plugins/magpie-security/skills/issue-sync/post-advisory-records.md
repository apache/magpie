<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — records after the advisory

Part of the Step 2b lookup in [`signals-to-actions.md`](signals-to-actions.md), which says when to read this file.

- **Advisory-records update** — records the published CVE in the project's own security records
  (the site repository its security pages are built from), when the project configures
  [`advisory_records`](../../../../<project-config>/project.md#advisory-records)
  ([`docs/security/advisory-records.md`](../../../../docs/security/advisory-records.md)).
  It replaces the security-pages reminder for those projects: sync makes the edit instead of asking the release manager for it.

  **Trigger.** Step 1g recorded `advisory_records_pending: true` for a closed-`announced` tracker:
  cve.org reports the CVE `PUBLISHED`, no comment carries the `advisory-records v1` marker,
  and the `advisory-records` planner returned a change (or, with no working copy yet, a `checkout` command).
  Before publication there is no proposal — the planner refuses, and the observed state says *"waiting for cve.org"*.
  Without `advisory_records` there is no proposal either; the observed state says *"not configured — skipped"*.

  **Proposed action.** One numbered item showing the planner's file change (the diff it printed) and its numbered
  [`magpie-vcs`](../../../../tools/vcs/README.md) commands, verbatim and in order:
  the clean check, the branch check (Git), `update`, the planner re-run with `--apply`, `stage`, `diff`, `commit`, and `push` (Git).
  On Subversion, say that the `commit` publishes the change.
  With no working copy, the item is the single `checkout` command; the change is proposed on the next sync.

  **Guard.** Never run a command the user has not confirmed, never edit the page or the JSON file by hand,
  and never push to another branch or remote than the configured ones.
  The planner is idempotent: an already-recorded CVE yields `unchanged` and no proposal.

- **Security-pages reminder comment** — the ASF security-committers policy's post-announcement step *"The project team updates the
  project's security pages"* is a website edit, which sync cannot perform or gate the close-out on
  (the close-out fires on the archive-URL signal).
  Projects that configure `advisory_records` never get this reminder: the *Advisory-records update* above makes the edit.
  Sync carries the checklist item that records it: both hand-off comment variants embed a
  `- [ ] <!-- apache-magpie: security-pages-checklist v1 --> Project
  security pages updated with CVE_ID` box, and ticking it records the completion marker on the tracker.
  This proposal covers the marker still unrecorded after the advisory has shipped.

  **Trigger.** Step 1g recorded `security_pages_reminder_pending: true` for a closed-`announced` tracker —
  the *Public advisory URL* body field is populated (the advisory has demonstrably shipped),
  no comment holds a ticked `- [x] <!-- apache-magpie: security-pages-checklist v1 -->` item (the body never counts: it carries report text),
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
