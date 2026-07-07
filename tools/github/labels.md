<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [GitHub — lifecycle label taxonomy](#github--lifecycle-label-taxonomy)
  - [Lifecycle labels](#lifecycle-labels)
  - [Closing-disposition labels](#closing-disposition-labels)
  - [Secondary labels](#secondary-labels)
  - [Maintenance](#maintenance)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# GitHub — lifecycle label taxonomy

The **generic** label taxonomy every GitHub-backed tracker shares.
These labels drive the state machine the skills reconcile; their
spellings and meanings are project-agnostic and stable across projects
that reuse this framework.

Project-specific labels — in particular the **scope labels** that pin
a tracker to a product family — live in the adopting project's
directory. For Airflow, see
[`../../<project-config>/scope-labels.md`](../../<project-config>/scope-labels.md).

The end-to-end state diagram that combines these labels into a
lifecycle lives in [`../../README.md`](../../README.md).

## Lifecycle labels

| Label | Meaning | Added at process step | Removed at process step |
|---|---|---|---|
| `needs triage` | Freshly filed; assessment not yet started. | 1 (set automatically by the issue template) | 5 |
| *scope label* | Project-specific scope pin (e.g. `airflow` / `providers` / `chart`). Exactly one is set after triage. Per-project definitions live in the project directory. | 5 | never (sticks for the lifetime of the issue) |
| `cve allocated` | A CVE has been reserved for the issue. Allocation is gated by the project's CVE-tool policy (see the project manifest's `cve_allocation_gated_by` value). | 6 | never |
| `pr created` | A public fix PR has been opened on the upstream repository but has not yet merged. | 10 | 11 (replaced by `pr merged`) |
| `pr merged` | The fix PR has merged upstream; no release carrying the fix has shipped yet. | 11 | 12 (replaced by `fix released` when the release ships) |
| `fix released` | A release carrying the fix has shipped to users; advisory has not been sent yet. | 12 | 13 (replaced by `announced - emails sent`) |
| `announced - emails sent` | The public advisory has been sent to the project's `announce` / `users` mailing lists. The issue **stays open** after this label is applied; closing is gated on the RM completing Step 15. | 13 | never (stays on the issue after closing for audit history) |
| `announced` | The public advisory URL has been captured in the tracking issue's *Public advisory URL* body field and the attached CVE JSON has been regenerated so its `references[]` now carries the `vendor-advisory` URL. | 14 | never (stays on the issue after closing) |

## Closing-disposition labels

Applied when a tracker leaves the lifecycle without producing a CVE.
These are mutually exclusive — a tracker closes with exactly one of:

| Label | Meaning |
|---|---|
| `invalid` | Report is not a vulnerability per the project's Security Model. |
| `not CVE worthy` | Reproducible but not severe / scoped enough to warrant a CVE (e.g. self-XSS, DoS by authenticated admin). |
| `duplicate` | Root-cause-equivalent to another tracker; kept tracker carries the CVE. See the `security-issue-deduplicate` skill. |
| `wontfix` | Will not be fixed (e.g. feature-not-bug, deprecated surface being removed in the next release). |

## Secondary labels

These do not gate state transitions but carry coordination signals.

| Label | Meaning | Scope |
|---|---|---|
| `security issue` | Applied by the issue template. Flags the issue as security-related for the GitHub UI and any org-level filters. | Generic — applied by the issue template. |
| Backport labels (e.g. `backport-to-v3-2-test`) | Project-specific — applied on the **public upstream PR**, not on the private tracker. Trigger the project's backport automation. | Project-specific; see the per-project fix-workflow file (for Airflow, [`../../<project-config>/fix-workflow.md#backport-labels`](../../<project-config>/fix-workflow.md#backport-labels)). |

## Maintenance

The `security-issue-sync` skill is the authority on label transitions
— on every run it detects the current state (labels + body fields +
fix-PR state + release state) and proposes the label transitions the
process requires.

Adding a new generic lifecycle label is a **process change** that
should be proposed, reviewed, and merged in the same PR that adds the
label to `<tracker>` via `gh label create` (see
[`operations.md`](operations.md#create-1)).
