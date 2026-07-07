<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Contributor-growth skill family](#contributor-growth-skill-family)
  - [Stage coverage](#stage-coverage)
  - [Skills](#skills)
  - [Family boundary](#family-boundary)
  - [Adopter contract](#adopter-contract)
  - [Status](#status)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Contributor-growth skill family

> **Scope — `organization: ASF` · 🪶 ASF-specific.** This family encodes Apache Software
> Foundation processes (the contributor-to-committer path) and assumes an ASF
> adopter profile by default. Non-ASF projects can still adopt it through the
> adapter/config layer, but it carries ASF assumptions the generic families do not.

Maintainer-facing skills that span the contributor-to-committer path:
welcoming first-time contributors, keeping the issue backlog newcomer-
ready, tracking contribution activity, checking readiness against declared
thresholds, assembling nomination evidence, and walking nominators through
post-vote onboarding. Seven skills cover the staged path from first contact
through committer promotion.

Why a framework skill family? The contributor-to-committer path is one
of the highest-leverage levers an open-source project has for long-term
health — lowering onboarding friction and shortening the time from first
PR to committer status keeps the contributor pipeline healthy. These
skills were designed independently but cover a contiguous path; grouping
them makes the adopter configuration and the evaluation story coherent.

## Stage coverage

| Stage | Skill | What it does |
|---|---|---|
| **First contact** | [`mentoring-welcome`](../../skills/mentoring-welcome/SKILL.md) | Drafts an orientation comment for a first-time contributor on a newly opened issue or PR; detects first-time authorship via the GitHub `author_association` field and skips repeat contributors. |
| **Issue on-ramp** | [`good-first-issue-author`](../../skills/good-first-issue-author/SKILL.md) | Drafts one net-new good first issue from a supplied gap or small task; a suitability gate and R1–R9 readiness checklist gate the draft; waits for maintainer confirmation before filing via `gh`. |
| **Backlog curation** | [`good-first-issue-sweep`](../../skills/good-first-issue-sweep/SKILL.md) | Sweeps the open issue backlog for existing issues that could be labelled as good first issues; scores each against the G1–G7 suitability rubric; classifies as READY / NEAR-MISS / SKIP and proposes labels after explicit maintainer confirmation. |
| **Activity tracking** | [`contributor-activity-sweep`](../../skills/contributor-activity-sweep/SKILL.md) | Produces a read-only GitHub activity card (PRs authored, code reviews, issues, comments) over a configurable window. |
| **Readiness check** | [`contributor-to-committer`](../../skills/contributor-to-committer/SKILL.md) | Maps a contributor's GitHub activity against the adopter's PMC-declared committer or PMC thresholds; surfaces a traffic-light brief (Not yet / Approaching / Ready to nominate) and a gap table showing what would close each remaining gap. Read-only; never opens a nomination thread. |
| **Nomination brief** | [`contributor-nomination`](../../skills/contributor-nomination/SKILL.md) | Assembles evidence prose for a committer or PMC vote thread: activity breadth, consistency, vendor-neutrality context, and a nomination-ready summary. Read-only; never posts to any list. |
| **Post-vote onboarding** | [`committer-onboarding`](../../skills/committer-onboarding/SKILL.md) | Walks the nominator through ICLA check, account provisioning, permissions grant, and the welcome announcement for committer and PMC promotions at ASF TLPs and podlings. |

Every stage is read-only on governance artefacts or propose-before-post:
no skill modifies a roster, posts an announcement, or files an issue
without explicit maintainer confirmation.

## Skills

| Skill | Mode | Status |
|---|---|---|
| [`mentoring-welcome`](../../skills/mentoring-welcome/SKILL.md) | Mentoring | experimental |
| [`good-first-issue-author`](../../skills/good-first-issue-author/SKILL.md) | Mentoring | experimental |
| [`good-first-issue-sweep`](../../skills/good-first-issue-sweep/SKILL.md) | Mentoring | experimental |
| [`contributor-activity-sweep`](../../skills/contributor-activity-sweep/SKILL.md) | Triage | experimental |
| [`contributor-to-committer`](../../skills/contributor-to-committer/SKILL.md) | Mentoring | experimental |
| [`contributor-nomination`](../../skills/contributor-nomination/SKILL.md) | Triage | experimental |
| [`committer-onboarding`](../../skills/committer-onboarding/SKILL.md) | Triage | experimental |

All seven skills are `experimental`; no adopter has run the full
contributor-to-committer path under evaluation conditions yet.

## Family boundary

This family sits **alongside** two overlapping skill families:

- [`docs/mentoring/README.md`](../mentoring/README.md) — the Agentic Mentoring
  mode spec and family overview. `mentoring-welcome`,
  `good-first-issue-author`, and `good-first-issue-sweep` carry
  `mode: Mentoring` and are also listed in that spec. The families
  cross-reference each other; a later maturity review may clarify the
  boundary or merge the two into one.
- [`docs/issue-management/README.md`](../issue-management/README.md) —
  general-issue triage and fix workflow. The contributor-growth family
  reads GitHub activity data about contributors, not issue content; the
  two families use different query surfaces and produce different
  artefacts (activity cards and nomination briefs vs. issue disposition
  proposals).

Skills in this family propose every state-changing action for human
sign-off. `committer-onboarding` emits paste-ready command recipes the
nominator executes as themselves; no skill submits an ICLA form, invites
an account, or modifies repository permissions without the nominator's
direct action.

## Adopter contract

The skills resolve project-specific content from these files in the
adopter's `<project-config>/` directory:

| File | Used by |
|---|---|
| [`project.md`](../../projects/_template/project.md) | all skills (upstream repo slug, GitHub token context, `<tracker>` reference) |
| [`pmc-roster.md`](../../projects/_template/pmc-roster.md) | `contributor-nomination`, `committer-onboarding` (PMC and committer rosters, ICLA-checker URL) |
| [`contributor-nomination-config.md`](../../projects/_template/contributor-nomination-config.md) | `contributor-nomination` (activity-window length, committer / PMC thresholds, required-areas gates); also used by `contributor-to-committer` as a fallback when `committer-readiness.md` is absent |
| [`committer-readiness.md`](../../projects/_template/committer-readiness.md) | `contributor-to-committer` (per-target threshold tables for committer/PMC readiness, assessment window; takes precedence over `contributor-nomination-config.md`) |
| [`mentoring-welcome-config.md`](../../projects/_template/mentoring-welcome-config.md) | `mentoring-welcome` (tone knobs, contributing-doc links, AI-attribution footer wording) |
| [`good-first-issue-config.md`](../../projects/_template/good-first-issue-config.md) | `good-first-issue-author`, `good-first-issue-sweep` (issue-tracker URL, getting-started link, GFI-label name, suitability rubric threshold) |

## Status

**Experimental.** All seven skills are on main with eval suites; no
adopter has run the full contributor-to-committer path end-to-end under
evaluation conditions.

Known deferred items (each pending a spec-RFC pass that enumerates
per-project policy knobs before a skill can safely propose anything):

- **PMC-member nomination** — vote mechanics, quorum rules, and
  post-vote steps differ from committer promotion and warrant a
  separate capability-flag variant of `committer-onboarding` or a
  standalone skill.
- **Emeritus / inactive-committer handling and contributor offboarding**
  — these involve project-level governance decisions (roster policy,
  access removal, farewell communication norms) that need per-project
  configuration.

## Cross-references

- [`docs/modes.md` § Triage](../modes.md#triage) — mode taxonomy the
  three Agentic Triage-mode family skills declare against.
- [`docs/modes.md` § Mentoring](../modes.md#mentoring) — mode taxonomy
  the three Agentic Mentoring-mode family skills declare against.
- [`docs/mentoring/README.md`](../mentoring/README.md) — the Agentic Mentoring
  mode family overview, which cross-references `mentoring-welcome`,
  `good-first-issue-author`, and `good-first-issue-sweep`.
- [`projects/_template/README.md`](../../projects/_template/README.md) —
  adopter scaffold index, including the three contributor-growth config
  templates listed in the Adopter contract above.
- [`docs/setup/agentic-overrides.md`](../setup/agentic-overrides.md) —
  the override mechanism every skill in this family supports.
