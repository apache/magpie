<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Modes — MISSION taxonomy mapped to current skills](#modes--mission-taxonomy-mapped-to-current-skills)
  - [Status legend](#status-legend)
  - [Modes at a glance](#modes-at-a-glance)
  - [Triage](#triage)
  - [Mentoring](#mentoring)
  - [Drafting](#drafting)
  - [Pairing](#pairing)
  - [Auto-merge](#auto-merge)
  - [Outside the modes](#outside-the-modes)
  - [Mode lifecycle](#mode-lifecycle)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Modes — MISSION taxonomy mapped to current skills

[`MISSION.md`](../MISSION.md) frames the framework around five
toggleable **modes** of agent-assisted repository maintainership
and development: **Triage**, **Mentoring**, **Drafting**
(agent-authored fixes with human review), **Pairing**
(developer-side dev-cycle skills with mentorship intrinsic), and
**Auto-merge** (narrowly-scoped fix-and-merge). Each adopting
project picks the modes that match its culture and risk
tolerance.

This document maps that taxonomy to the skills that currently
ship in the framework. It is the **honest snapshot** — modes
that are not yet implemented are listed as such, with a tracking
issue or roadmap pointer rather than a placeholder shell. Read
[`MISSION.md`](../MISSION.md) for the *why* of each mode and the
sequencing commitments behind them.

## Status legend

| Status | Meaning |
|---|---|
| **stable** | Implemented, in use by at least one adopter, behaviour expected to remain backward-compatible across minor framework versions. |
| **experimental** | Implemented but not yet covered by an adopter pilot or contributor-sentiment evaluation; shape may change. |
| **proposed** | Designed in [`MISSION.md`](../MISSION.md) but no skill yet exists; tracked for future implementation. |
| **off** | Deliberately not implemented per a MISSION-level sequencing rule (Auto-merge). |

## Modes at a glance

| Mode | Purpose | Status | Skill count |
|---|---|---|---|
| **Triage** | Issues, security reports, PRs: spot, classify, route, surface duplicates. Every output is a suggestion the human signs off on. | stable (security) / experimental (pr-management, issue-management, contributor-nomination) / proposed (release-management) | 19 + 4 proposed |
| **Mentoring** | Joins issue and PR threads in a teaching register: clarifying questions, pointers to project conventions, paired examples from prior PRs, hand-off to a human when scope exceeds the agent. Also authors net-new good first issues to lower onboarding latency. | experimental | 2 |
| **Drafting** | Agent drafts a fix for a well-scoped problem and opens a PR; every PR is reviewed and merged by a human committer. | stable (security-only); experimental (issue-management, audit-findings); release-management family proposed | 3 + 6 proposed |
| **Pairing** | Developer-side dev-cycle skills with mentorship intrinsic — multi-agent review pipelines, self-review and pre-flight patterns, scoped fix drafting under the developer's driver's seat. | experimental | 2 |
| **Auto-merge** | Auto-merge restricted to objectively boring change classes (lint, dependency bumps inside an allow-list, license-header insertion, formatting, broken-link repair). | off | 0 |

A few skills sit **outside** the mode taxonomy by design — see
[Outside the modes](#outside-the-modes) below.

## Triage

Inbound report and PR triage. The lowest-risk surface and the
foundation everything else builds on. Skills propose labels,
spot duplicates, link related discussions, classify reports
against prior triaged cases, and route to the right human; they
do not act without human review.

| Skill | Domain | Status |
|---|---|---|
| [`pr-management-triage`](../skills/pr-management-triage/SKILL.md) | Generic PR queue triage. | experimental |
| [`pr-management-stats`](../skills/pr-management-stats/SKILL.md) | PR-queue reporting (supports triage decisions). | experimental |
| [`pr-management-code-review`](../skills/pr-management-code-review/SKILL.md) | Maintainer-facing deep code review. | experimental |
| [`issue-triage`](../skills/issue-triage/SKILL.md) | General-issue-tracker triage (per-issue classification + disposition proposal). | experimental |
| [`issue-reassess`](../skills/issue-reassess/SKILL.md) | Pool-level sweep of resolved / EOL issues for re-assessment. | experimental |
| [`contributor-nomination`](../skills/contributor-nomination/SKILL.md) | Nomination-readiness brief for a named contributor — activity breadth, consistency, and evidence prose for a committer or PMC thread. | experimental |
| [`security-issue-import`](../skills/security-issue-import/SKILL.md) | Inbound security-report classification + initial routing. | stable |
| [`security-issue-import-from-pr`](../skills/security-issue-import-from-pr/SKILL.md) | Open a tracker from a security-relevant public PR. | stable |
| [`security-issue-import-from-md`](../skills/security-issue-import-from-md/SKILL.md) | Bulk-import findings from a markdown report. | stable |
| [`security-issue-deduplicate`](../skills/security-issue-deduplicate/SKILL.md) | Merge two trackers describing the same root-cause vulnerability. | stable |
| [`security-issue-invalidate`](../skills/security-issue-invalidate/SKILL.md) | Close a tracker as invalid with a polite-but-firm reporter reply. | stable |
| [`security-issue-sync`](../skills/security-issue-sync/SKILL.md) | Reconcile a tracker against its mail thread, fix PR, release train, and archives. | stable |
| [`security-cve-allocate`](../skills/security-cve-allocate/SKILL.md) | Allocate a CVE for a tracker (Vulnogram URL + paste-ready JSON). | stable |
| [`security-issue-triage`](../skills/security-issue-triage/SKILL.md) | Batch-triage open tracker issues carrying `needs triage`; classifies each into one of six dispositions and posts a proposal comment on confirmation. | experimental |
| [`security-issue-import-via-forwarder`](../skills/security-issue-import-via-forwarder/SKILL.md) | Sub-skill of `security-issue-import` / `-invalidate` / `-sync` for the relay/forwarder case: reports relayed by an upstream broker (e.g. ASF security team) rather than arriving directly from the reporter. | experimental |
| [`security-issue-import-from-scan`](../skills/security-issue-import-from-scan/SKILL.md) | Triage a security scanner's multi-finding output (via the `scan-format` adapter) into per-finding dispositions; opens tracker issues only after operator confirmation of the triage decisions. | experimental |
| [`contributor-activity-sweep`](../skills/contributor-activity-sweep/SKILL.md) | Read-only GitHub activity card for a named contributor: PR authorship, code-review participation, issues, and comments over a configurable window. | experimental |
| [`pr-management-quick-merge`](../skills/pr-management-quick-merge/SKILL.md) | Identify trivial, low-risk PRs in the `ready for maintainer review` queue that pass every quality gate and touch only supplementary areas (docs, changelog, translations, tests); surfaces candidates with diff summaries and the exact merge command. | experimental |
| [`ci-runner-audit`](../skills/ci-runner-audit/SKILL.md) | Read-only audit of GitHub Actions workflow runner compatibility across one repo, an explicit set, one Apache project's repos, or the full Apache GitHub org. | experimental |
| `release-verify-rc` | Read-only pre-flight on a staged RC: signatures against project KEYS, checksums, license headers (Apache RAT), NOTICE/LICENSE diff, no prohibited binaries, version-string consistency. Doubles as a Pairing-mode skill voters run in their own dev loop. | proposed |
| `release-vote-tally` | Parse a `[VOTE]` thread, classify each reply (+1 / 0 / -1) binding vs non-binding against the PMC roster, propose `[RESULT] [VOTE]`. Conservative on ambiguous votes, refuses to count. | proposed |
| `release-archive-sweep` | Scan `dist/release/<project>/`, identify releases past retention, propose the `svn mv` sequence to `archive.apache.org`. | proposed |
| `release-audit-report` | Per-release structured report (RM, voters with binding flags, artefacts with sigs and checksums, promote revision, `[ANNOUNCE]` archive URL) appended to the project's audit log. | proposed |

Three notes on the boundaries:

- `pr-management-code-review` is a deeper variant of triage —
  the agent reads diff and surrounding code rather than only
  metadata, but the output is still a suggestion for the human
  reviewer. It belongs to Triage by the same rule.
- `security-cve-allocate` is procedural rather than classificatory
  (CVE allocation happens after assessment), but it shares Triage's
  shape: the agent prepares a paste-ready artefact, the human
  PMC member submits it. Listed here for navigability.
- The four `release-*` Triage skills share the same paste-ready-
  artefact shape: `release-verify-rc` reports pass/fail per check,
  `release-vote-tally` proposes `[RESULT]`, `release-archive-sweep`
  proposes an `svn mv` sequence, `release-audit-report` proposes
  an audit-log append. None of them flip state labels or
  publish artefacts, see
  [`docs/release-management/spec.md` § Cross-cutting commitments](release-management/spec.md#cross-cutting-commitments).

## Mentoring

**Status: experimental. 2 skills shipped.**

[`MISSION.md` § Mentoring](../MISSION.md#technical-scope) names this
the highest-value project-side mode and the one off-the-shelf agent
tooling skips. The spec — tone guide, hand-off protocol, adopter
contract — landed ahead of the skill code so the project's tone
choices were reviewable independently from the runtime behaviour.

| Skill | Purpose | Status |
|---|---|---|
| [`pr-management-mentor`](../skills/pr-management-mentor/SKILL.md) | Draft a teaching-register comment on a single GitHub issue or PR thread; waits for maintainer confirmation before posting. | experimental |
| [`good-first-issue-author`](../skills/good-first-issue-author/SKILL.md) | Draft one net-new good first issue from a supplied gap or small task (suitability gate + readiness checklist); waits for maintainer confirmation before filing. | experimental |

| Doc | Purpose |
|---|---|
| [`docs/mentoring/README.md`](mentoring/README.md) | Family overview, current status, planned shape. |
| [`docs/mentoring/spec.md`](mentoring/spec.md) | Full spec: scope, triggers, register, hand-off, adopter knobs. |
| [`projects/_template/mentoring-config.md`](../projects/_template/mentoring-config.md) | Adopter-config scaffold (required before running the skill). |

The prototype ships flagged `mode: Mentoring` + `experimental`. Shape
may change as adopter pilots and contributor-sentiment evaluation land.
The skill is read-only by default and never posts without explicit
maintainer confirmation — see
[`pr-management-mentor/SKILL.md`](../skills/pr-management-mentor/SKILL.md)
for the full contract.

The closest existing surface is
[`pr-management-triage/comment-templates.md`](../skills/pr-management-triage/comment-templates.md),
which carries Triage classification responses — informational,
not pedagogical. It is **not** Mentoring.

## Drafting

The agent drafts a fix for a well-scoped problem (a tracked
issue, a triaged security report with team consensus on scope, a
failing test with an obvious cause, a documentation hole) and
opens a PR. Every PR is reviewed and merged by a human committer;
the agent never merges its own work.

| Skill | Domain | Status |
|---|---|---|
| [`security-issue-fix`](../skills/security-issue-fix/SKILL.md) | Draft a fix PR in `<upstream>` from a triaged, CVE-allocated tracker. | stable (security-only) |
| [`issue-fix-workflow`](../skills/issue-fix-workflow/SKILL.md) | Draft a fix for a triaged general-issue-tracker issue (BUG or FEATURE-REQUEST). | experimental |
| [`audit-finding-fix`](../skills/audit-finding-fix/SKILL.md) | Draft fixes for non-security audit-tool findings (lint violations, type errors, CodeQL alerts, doc-coverage gaps); re-runs the tool after each batch to confirm findings are cleared. | experimental |
| `release-prepare` | Planning issue + version-bump / changelog / NOTICE / LICENSE prep PR (Steps 1-2). Also the post-release `-SNAPSHOT` bump (Step 14). | proposed |
| `release-keys-sync` | Draft the `KEYS` diff for a new Release Manager (Step 3). Agent never holds the private key. | proposed |
| `release-rc-cut` | Paste-ready command sequence: signed tag, build, detached signatures, checksums, `svn import` to `dist/dev/` (Steps 4-5). Agent never signs and never imports. | proposed |
| `release-vote-draft` | Draft the `[VOTE]` email body to `dev@<project>` (Step 7). Agent never sends. | proposed |
| `release-promote` | Paste-ready `svn mv dist/dev → dist/release` command set after a passing vote (Step 10). Agent never moves; the human commit is the act of release. | proposed |
| `release-announce-draft` | Draft the `[ANNOUNCE]` email body for `announce@apache.org` and the site-bump PR (Step 11). Agent never sends mail and never merges the PR. | proposed |

[`audit-finding-fix`](../skills/audit-finding-fix/SKILL.md)
extends Drafting to **non-security audit-tool findings**: lint
violations, type errors, CodeQL alerts, and documentation-coverage
gaps. It is the generic-Drafting companion to
[`issue-fix-workflow`](../skills/issue-fix-workflow/SKILL.md)
(issue-tracker bugs) and
[`security-issue-fix`](../skills/security-issue-fix/SKILL.md)
(security-class findings). Failing tests with an obvious cause
remain proposed.

The six `release-*` Drafting skills above land as a single family
([`docs/release-management/README.md`](release-management/README.md))
once the spec lands. They share the security family's discipline
that every state-changing action is a *proposal* the human
executes, see
[`docs/release-management/spec.md` § Cross-cutting commitments](release-management/spec.md#cross-cutting-commitments).

For security-class Drafting PRs, the public surface strips CVE
and private context per the project's disclosure policy, so the
public surface stays clean until the embargo lifts — see
[`AGENTS.md` § Confidentiality](../AGENTS.md#confidentiality-of-the-tracker-repository)
for the rules the skill enforces.

## Pairing

**Status: experimental. 2 skills.**

[`MISSION.md` § Pairing](../MISSION.md#technical-scope) introduces
this mode as the developer-side counterpart to the project-side
modes. Where Triage / Mentoring / Drafting / Auto-merge describe
the agent's presence on the project's own infrastructure, Pairing
skills run in the maintainer's or contributor's *own* dev loop —
multi-agent review pipelines, self-review and pre-flight patterns,
scoped fix drafting under the developer's driver's seat.
**Mentorship is intrinsic** to Pairing skills: the agent handles
the mechanical, implementation-detail review (formatting,
conventions, lint-grade nits) so the human conversation between
contributor and maintainer — and between peer maintainers —
stays on design, reasoning, and the trade-offs the project cares
about. Pairing skills are the platform's mechanism for protecting
the **ASF contribution path** (contributor → committer → PMC)
against being eroded by automation that replaces, rather than
augments, the human-to-human relationships that path is built on.

Pairing skills don't make state changes on behalf of the project;
they share the same skill format and security posture as the
project-side modes, so a maintainer who already trusts the
framework for Triage gets the same posture for the patches they
write themselves.

| Skill | Domain | Status |
|---|---|---|
| [`pairing-self-review`](../skills/pairing-self-review/SKILL.md) | Pre-flight self-review of local changes before opening a PR. Read-only; returns a structured report. | experimental |
| [`pairing-multi-agent-review`](../skills/pairing-multi-agent-review/SKILL.md) | Fan a diff through three independent review passes (correctness, security, conventions) and merge findings. | experimental |

**Sequencing.** Pairing ships before Auto-merge in the project's
automation roadmap — full auto-merge of maintainer-driven changes
follows only after Pairing has established that human reasoning
and relationships, not implementation chatter, are the
load-bearing parts of the workflow.

## Auto-merge

**Status: off. Deliberately not implemented.**

[`MISSION.md` § Auto-merge](../MISSION.md#technical-scope) holds
auto-merge off until Triage, Mentoring, Drafting, and Pairing
have been running for two quarters and contributor-sentiment
data says the project is healthier, not just faster.
Security-class changes are explicitly **out** of Auto-merge — no
auto-merge ever touches anything embargoed or CVE-tagged.

The framework's current `.asf.yaml` configuration reflects this
posture: `pull_requests.allow_auto_merge` is set to `false`
([`.asf.yaml`](../.asf.yaml)).

When Auto-merge ships, the eligible change classes will be
declared per-adopter in `<project-config>/` and gated by an
allow-list that the framework refuses to grow without an
adopter PR.

## Outside the modes

Several skills are framework infrastructure rather than
maintainership modes. They support adoption, isolation, and
upgrade flows; they do not act on issues, PRs, or contributor
threads on their own.

| Skill | Purpose |
|---|---|
| [`setup`](../skills/setup/SKILL.md) | Adopt the framework into an adopter repo; manage the snapshot, symlinks, and overrides. |
| [`issue-reproducer`](../skills/issue-reproducer/SKILL.md) | Per-issue code extraction + execution; produces structured evidence. Read-only on the tracker. |
| [`issue-reassess-stats`](../skills/issue-reassess-stats/SKILL.md) | Read-only dashboard over reassessment-campaign verdict.json files. |
| [`setup-isolated-setup-install`](../skills/setup-isolated-setup-install/SKILL.md) | Install the credential-isolation sandbox harness. |
| [`setup-isolated-setup-update`](../skills/setup-isolated-setup-update/SKILL.md) | Update pinned system tools (`bubblewrap`, `socat`, agent CLI) past the cooldown window. |
| [`setup-isolated-setup-verify`](../skills/setup-isolated-setup-verify/SKILL.md) | Read-only health check of the sandbox harness. |
| [`setup-override-upstream`](../skills/setup-override-upstream/SKILL.md) | Promote an adopter's local override into a framework PR. |
| [`setup-shared-config-sync`](../skills/setup-shared-config-sync/SKILL.md) | Sync shared configuration across worktrees. |
| [`setup-isolated-setup-doctor`](../skills/setup-isolated-setup-doctor/SKILL.md) | In-session functional health check of the secure-agent sandbox: probes SSH agent / Yubikey reachability, localhost port access, and filesystem restrictions. |
| [`setup-status`](../skills/setup-status/SKILL.md) | Render a Markdown adoption dashboard: install method and pin, drift, and which skills are wired in the current repo. |
| [`committer-onboarding`](../skills/committer-onboarding/SKILL.md) | Post-vote committer and PMC onboarding for Apache projects: walks the nominator through every step from ICLA check to welcome announcement for both podlings and TLPs. |
| [`security-tracker-stats-dashboard`](../skills/security-tracker-stats-dashboard/SKILL.md) | Generate a self-contained HTML dashboard of `<tracker>` statistics (lifecycle-band breakdowns, time-to-triage trends, velocity) without modifying any tracker state. |
| [`optimize-skill`](../skills/optimize-skill/SKILL.md) | Optimize an existing framework skill by applying restructuring patterns: split oversized SKILL.md into linked sibling docs, trim frontmatter, improve eval alignment. |
| [`list-skills`](../skills/list-skills/SKILL.md) | Print a live index of every skill in this repository grouped by family, with each skill's name and first-sentence description. |
| [`write-skill`](../skills/write-skill/SKILL.md) | Author a new framework skill or update an existing one: frontmatter, placeholder convention, injection defences, Privacy-LLM gate-check, and validator sign-off. |

The `setup*` skills ship as a single **setup family** — see
[`docs/setup/README.md`](setup/README.md). The remaining skills
(`committer-onboarding`, `security-tracker-stats-dashboard`,
`optimize-skill`, `list-skills`, `write-skill`) are standalone
framework utilities.

## Mode lifecycle

A mode moves through four states as it matures:

1. **proposed** — designed in [`MISSION.md`](../MISSION.md), no
   skill code yet. Spec PRs may land before any skill code so
   tone, scope, and adopter knobs are reviewable in isolation.
2. **experimental** — at least one skill exists, behaviour may
   change, no adopter pilot has run an evaluation. Adopters
   can opt-in but should expect breaking changes between
   framework versions.
3. **stable** — at least one adopter is running the mode in
   production, behaviour is backward-compatible across minor
   framework versions. The default state for skills shipped to
   adopters.
4. **graduated-to-Auto-merge-eligible** *(future state; Triage,
   Mentoring, Drafting, and Pairing only)* — the mode has run
   stable for two quarters with positive contributor-sentiment
   evidence, the framework will start considering an equivalent
   change class for Auto-merge. This state does not exist yet
   because Auto-merge itself is off.

A mode can be **retracted** from any state. The retraction
triggers MISSION names — sustained negative contributor
sentiment, a confidentiality leak, a sandbox bypass that escapes
detection — apply per-adopter and per-mode. A retraction in one
adopter does not auto-retract in another, but the framework
records it for cross-adopter pattern detection.

## Cross-references

- [`MISSION.md`](../MISSION.md) — the *why* of each mode, the
  sequencing commitments, and the privacy/security/vendor-
  neutrality posture each mode inherits.
- [`README.md`](../README.md#skill-families) — adopter-facing
  skill family table; this document is the maintainer-facing
  taxonomy view of the same skills.
- [`AGENTS.md`](../AGENTS.md) — repository-level rules every
  mode inherits (external content as data, polite-but-firm
  tone, brevity, confidentiality).
- [`docs/mode-economics.md`](mode-economics.md) — indicative token-cost
  shape per mode and model class; for maintainers evaluating adoption.
