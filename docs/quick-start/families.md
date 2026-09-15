<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [What each family solves](#what-each-family-solves)
  - [Start with the baseline](#start-with-the-baseline)
  - [The ten families](#the-ten-families)

<!-- END doctoc -->

# What each family solves

## Start with the baseline

Install these three recommended plugins, then add the families needed for your tasks:

| Plugin | Why it is in the baseline |
|---|---|
| `magpie-setup` | Install first. Provides installation, upgrades, local configuration, team adoption, and agent-isolation setup. |
| `magpie-agent-guard` | Inspects shell commands before execution and blocks prohibited patterns on supported agents. It is a hook plugin, not a skill family. |
| `magpie-utilities` | Lists installed skills, supports skill authoring, and prepares framework bug reports. |

Team adoption uses the same baseline as its shared recommendation.
See [installation and adoption](two-ways.md) for the distinction.
Installing `magpie-setup` makes the isolation skills available; run [isolation setup](../quick-start.md#step-3--isolate--guard) to enable the protections.

## The ten families

Choose by the task and output you need.
For example, `pr-management` reviews an open PR, while `pairing` reviews a local diff before you submit it.
`repo-health` audits the repository's dependencies and CI configuration rather than reviewing one change.

| Plugin | Skills | Use for | Output or action boundary |
|---|---|---|---|
| [`magpie-setup`](../setup/README.md) | 10 | Installation, configuration, isolation, and upgrades | Proposed setup changes, installation status, and drift reports. |
| [`magpie-security`](../security/README.md) | 15 | Security-report intake through CVE publication | Triage assessments, tracker updates, fix drafts, and advisory drafts. Outbound messages require review. |
| [`magpie-release-management`](../release-management/README.md) | 10 | ASF release candidates, votes, and announcements | RC checks, vote drafts and tallies, promotion instructions, and audit records. The agent does not hold signing keys or publish releases. |
| [`magpie-pr-management`](../pr-management/README.md) | 8 | Open-PR triage, code review, and queue maintenance | Draft reviews, proposed routing and stale-PR actions, merge proposals, and queue statistics. |
| [`magpie-issue`](../issue-management/README.md) | 8 | Issue triage, reproduction, fixes, and reassessment | Disposition proposals, reproduction evidence, draft fixes, deduplication proposals, and backlog reports. |
| [`magpie-repo-health`](../repo-health/README.md) | 7 | Dependencies, licences, CI workflows, runners, and flaky tests | Read-only audit reports. A separate fix skill handles supplied non-security audit findings. |
| [`magpie-contributor-growth`](../contributor-growth/README.md) | 6 | Contributor activity, nominations, and onboarding | Activity reports, threshold-based readiness tracking, sentiment reports, nomination briefs, and onboarding checklists. |
| [`magpie-utilities`](../utilities/README.md) | 5 | Skill discovery, authoring, and maintenance | Installed-skill index, new or restructured skills, reconciliation, and framework issue reports. |
| [`magpie-mentoring`](../mentoring/README.md) | 4 | Newcomer orientation and good-first-issue preparation | Draft welcome comments, issue explanations, new issue drafts, and backlog suitability assessments. |
| [`magpie-pairing`](../pairing/README.md) | 2 | Local diff review | Structured self-review or independent multi-agent review findings, without posting or modifying code. |
