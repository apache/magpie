<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync — overdue disclosure and distributor pre-announcement

Part of the Step 2b lookup in [`signals-to-actions.md`](signals-to-actions.md), which says when to read this file.

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
