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
| 2b | Proposed changes | 10 | Label swap, milestone create, providers wave, disclosure overdue, distributor pre-announce, reporter unresponsive + replied, security-pages reminder |
| 2c | Next-step recommendation | 4 | Steps 3, 6, 11, 13 |
| Guardrails | Guardrail violation detection | 3 | CVSS propagation, ASF project naming, clean pass |
| 3 | Confirm with user | 3 | apply-all, selective, cancel |
| 6 | Recap | 2 | Structural assertions; with and without CVE/draft |
| Bulk orchestration | Bucket-and-walk decision in bulk mode | 3 | All label-only (one bundled), mixed buckets (split), all CVE-affecting (all walked) |
| 1d | Actionable signals in comments and mail | 6 | Affected-versions lower bound (widen / keep + backtick-wrap), title strip and its under-3-words guard, private-scanner credit (anonymise / public-credit exemption), reporter CVSS surfaced only |
| 5b | Push decision for the regenerated CVE JSON | 6 | Skip gate, expired session hand-off, title and private-finder hygiene gates, clean push with `allocated → review-ready`, close-out push on a `PUBLIC` record |
| Bulk selectors | Selector resolution and pre-flight skips | 6 | Injection-shaped CVE token rejected, CVE list expansion, `sync all` skip rules, named trackers never skipped, `force-sync`, review-ready push exemption |
| GHSA access tier | Repository security advisory writes by access tier | 5 | Collaborator direct field edit, 403 admin hand-off relay draft, admin direct write, reporter reply by browser paste, non-collaborator relay fallback |

## Hard rules exercised

- **CVSS not propagated**: Reporter-supplied CVSS score in proposed body patch or status comment is flagged (guardrails case-1).
- **Other ASF project vulnerabilities not named**: Naming a specific CVE from another ASF project is flagged (guardrails case-3).
- **Observed state is tight**: 2a summary is a bullet list of facts only — no proposed actions embedded.
- **Milestone create needed**: When the target milestone does not exist on the repo, `milestone_create_needed: true` must be set (2b case-2).
- **Providers milestone is never the PR milestone**: For providers scope the milestone is the next wave date (2b case-3).
- **CVE allocate skill explicitly named and linked**: Step-6 next-step must name and link `security-cve-allocate` (2c case-2).
- **No-action parking**: Step-11 produces `has_concrete_action: false` (2c case-3).
- **Security-pages reminder fires only post-advisory, once**: on a closed-`announced` tracker with *Public advisory URL* populated, the hand-off comment's checklist item still unticked and no reminder marker posted, the reminder status comment is proposed with `security_pages_reminder_proposed: true`; a ticked checklist item or an already-posted reminder proposes nothing (2b cases 8-10).
- **Golden rule 2 — no bare issue numbers**: `has_bare_issue_numbers` must always be false.
- **CVE-affecting trackers walked individually**: in bulk mode, any tracker whose `proposed_body_field_updates` names a CVE-publication field (Title, Short public summary for publish, CWE, Severity, Affected versions, Reporter credited as, Remediation developer, PR with the fix, Public advisory URL) must end up in `cve_affecting` and the `walk_order` is ascending by tracker number (bulk-orchestration cases 2 + 3).
- **Non-CVE-affecting trackers bundled**: trackers whose proposals are limited to label flips, milestone touches, assignee swaps, project-board moves, status-rollup entries, reporter Gmail drafts, or RM hand-off comments end up in `non_cve_affecting` (bulk-orchestration case 1 + the two label-only trackers in case 2).
