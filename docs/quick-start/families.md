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

Three plugins are the **strongly recommended** starting set. Take all three,
then add families against a problem you have today:

| Plugin | Why it is in the baseline |
|---|---|
| `magpie-setup` | **Install this one first — nothing else works without it.** It is what installs, upgrades, configures and adopts everything else, and it carries the secure-isolation skills that sandbox your agent. |
| `magpie-agent-guard` | The deterministic pre-execution guard: a hook that inspects each shell command *before* it runs and denies the dangerous shapes outright. It is not a family and has no skills of its own — it is a safety net under whatever else you install. |
| `magpie-utilities` | `list-skills`, so you can see what is actually installed, plus skill authoring and a path to report framework bugs upstream. Small, and the thing you reach for when something is not behaving. |

This is not an arbitrary recommendation: it is exactly the set a project
commits as its **floor** when it adopts Magpie
([Installation or Adoption?](two-ways.md)). What a project recommends to
everyone who clones it is what you should have yourself.

Isolation belongs here too. It is not a plugin but a run —
[Step 3 of the quick start](../quick-start.md#step-3--lock-the-agent-down)
— and it ships inside `magpie-setup`.

## The ten families

Skills ship in ten **families**. Install the ones that match a problem you have
today — you are not meant to take all of them.

| Plugin | Skills | The problem it solves | What it offers |
|---|---|---|---|
| `magpie-setup` | 9 | Your agent can read every credential on your machine, and you have no way to tell whether it is sandboxed right now. | A filesystem sandbox, a clean-env wrapper, a status line that shows sandbox state, and a red banner before any bypass. Plus install, upgrade, and drift checks. **You must install this one first** — it is what installs everything else. |
| `magpie-security` | 15 | Security reports arrive by mail and must be triaged, fixed, and disclosed on a clock — with nothing leaking early. | A 16-step lifecycle: intake from the mailbox, validity triage, canned responses, fix drafting, CVE allocation, advisory and publication. Drafts land in Gmail; nothing is ever sent for you. |
| `magpie-release-management` | 10 | An ASF release is a long checklist where one missed step invalidates the vote. | RC cut, RC verification (signatures, hashes, LICENSE/NOTICE, no stray binaries), the `[VOTE]` thread, the tally, promotion, `[ANNOUNCE]`, archive sweep, audit log. The agent never holds your signing key and never publishes. |
| `magpie-pr-management` | 8 | The PR queue grows faster than you can read it, and the oldest ones quietly rot. | Queue triage into ready / needs-review / waiting-on-author, deep code review with blocking vs non-blocking findings, reviewer routing, express-lane merge, stale sweep, and queue statistics. |
| `magpie-issue` | 8 | A backlog full of duplicates, unreproducible reports, and issues nobody has read in a year. | Triage with proposed labels, duplicate clustering, reproduction attempts across versions, fix drafting, reassessment of old issues, stale sweep, and backlog stats. |
| `magpie-repo-health` | 7 | Slow rot you only notice when it breaks: vulnerable deps, unpinned actions, licence drift, flaky tests. | Read-only audits for dependency CVEs, dependency licences, LICENSE/NOTICE compliance, Actions workflow security, obsolete runner labels, and flaky-test patterns — plus a skill that fixes what they find. |
| `magpie-contributor-growth` | 6 | Contributors who have earned committership go unnoticed because nobody is tracking the signal. | Activity sweeps against a review threshold, readiness tracking, sentiment signals, nomination briefs for the PMC, and committer / post-vote onboarding checklists. |
| `magpie-utilities` | 5 | You want to write your own skills, or find out what is actually installed. | Skill authoring and restructuring, a state reconciler, a live index of installed skills, and a path to report framework bugs upstream. **In the baseline.** |
| `magpie-mentoring` | 4 | Newcomers open one PR, hit a wall of unwritten conventions, and never come back. | First-contact welcome comments, plain-language explanations of an issue for someone new, good-first-issue authoring, and a sweep that keeps that backlog honest. |
| `magpie-pairing` | 2 | You want the obvious problems found before a reviewer spends their time on them. | A structured self-review of your own diff, and a multi-agent adversarial review that verifies its findings before reporting them. |
