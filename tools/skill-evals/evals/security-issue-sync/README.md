<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-sync eval suite

Behavioral evals for the `security-issue-sync` skill.
Steps 0 (pre-flight), 1a–1c and 1e (data gathering), 1g (cve.org API check), 4 (shell apply), 5/5a and 5c (CVE artifact regeneration) are skipped — all low-signal for structured-output evals.

## Steps

| Step | Name | Cases | Notes |
|------|------|-------|-------|
| 1f | Process step identification | 7 | Decision table covering steps 1-2 through 14 |
| 2a | Observed state | 3 | Step 11 (PR merged), step 6 (CVE needed), step 2 (stale) |
| 2b | Proposed changes | 12 | Label swap, milestone create, providers wave, disclosure overdue, distributor pre-announce, reporter unresponsive + replied, security-pages reminder, advisory-records update (proposed once published, held while cve.org is not) |
| 2c | Next-step recommendation | 4 | Steps 3, 6, 11, 13 |
| 5b | The four judged pre-push gates | 2 | A private-scanner analyst credit fails the anonymise gate; a clean fix-released record passes all four |
| 1d | Actionable signals in comments and mail | 6 | Affected-versions lower bound (widen / keep + backtick-wrap), title strip and its under-3-words guard, private-scanner credit (anonymise / public-credit exemption), reporter CVSS surfaced only |
| D4 | Dashboard-mode proposals | 3 | A dashboard-triage finding beside an untracked report; two findings for the ASF Security team; an untagged case that may be a standing label |
| Hand-off delegate | Next-step hand-off honouring a project delegate (pre-flight `step-13`) | 4 | Triage delegated (`replace`) named and invoked through `security-issue-triage`, CVE allocation delegated (`after`), a delegate for an unrelated skill (not named), and `--no-overrides` (ignored) |

## Hard rules exercised

- **Observed state is tight**: 2a summary is a bullet list of facts only — no proposed actions embedded.
- **Milestone create needed**: When the target milestone does not exist on the repo, `milestone_create_needed: true` must be set (2b case-2).
- **Providers milestone is never the PR milestone**: For providers scope the milestone is the next wave date (2b case-3).
- **CVE allocate skill explicitly named and linked**: Step-6 next-step must name and link `security-cve-allocate` (2c case-2).
- **No-action parking**: Step-11 produces `has_concrete_action: false` (2c case-3).
- **Security-pages reminder fires only post-advisory, once**: on a closed-`announced` tracker with *Public advisory URL* populated, the hand-off comment's checklist item still unticked and no reminder marker posted, the reminder status comment is proposed with `security_pages_reminder_proposed: true`; a ticked checklist item or an already-posted reminder proposes nothing (2b cases 8-10).
- **Hand-offs run delegates inside the wrapper**: a delegated next skill is named with its delegate and invoked through the Magpie skill, never by running the project skill directly (hand-off delegate cases 1-4).
- **No second reporter reply for a dashboard decision**: a `dashboard-triage` finding links the project page and drafts no reporter reply, since the dashboard emails the reporter itself; every `asf-security` finding goes into one note, and a case that may be one of the security team's standing labels is confirmed as a report before any import; nothing is applied unconfirmed even when asked to (D4 cases 1-3).
- **Advisory records only after publication**: with `advisory_records` configured, a closed-`announced` tracker whose CVE cve.org reports `PUBLISHED` gets one `advisory_records` item carrying the planner's change and commands (`advisory_records_proposed: true`) and no security-pages reminder; while cve.org does not report it `PUBLISHED`, nothing is proposed (2b cases 11-12).
- **Golden rule 2 — no bare issue numbers**: `has_bare_issue_numbers` must always be false.

## Deterministic steps — pytest, not model evals

Bulk selector resolution and pre-flight, the CVE-impact buckets, the Step 3 and bulk confirmation forms, the Guardrails surface check, the Step 6 recap,
the security CC and drafting-backend choice, the GHSA access tier and delivery, and the Step 5b push decision flow
are decided or rendered by `security-management issue-sync` and pytest-tested in
[`tools/security-management/tests/test_issue_sync.py`](../../../security-management/tests/test_issue_sync.py),
and `tests/test_issue_sync_rules.py`, one test per former case of `step-bulk-selectors` (cases 1–8), `step-bulk-orchestration` (1–3), `step-3-confirm` (1–3), `step-6-recap` (1–2), `step-guardrails` (1–3),
`step-security-cc` (1–13), `step-draft-backend` (1–5), `step-ghsa-access-tier` (1–5) and `step-5b-push-decision` (1–8),
with the hard rules they graded: an injection-shaped CVE token stops the selector before any search, named trackers and CVE selectors are never skipped,
a reporter reply under 24h is `dispatch-urgent`, the `allocated → review-ready` push rides the non-CVE-affecting confirmation,
a CVE-affecting tracker is walked individually in ascending order, a reporter CVSS score outside the observed state and another ASF project's name are flagged,
a bare CVE ID is flagged on markdown surfaces and the CVE-tool URL in a reporter email, the first layer declaring a CC key wins (an explicit null disables the fallback),
an admin-only advisory change at the collaborator tier (or after a `403`, never retried) is a draft relay and never a tracker comment,
the push is skipped, blocked at the first failing gate or handed off on an expired or missing session, and no bare `#NNN`.
