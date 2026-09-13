<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Contributor-growth skill family](#contributor-growth-skill-family)
  - [Install & first runs](#install--first-runs)
    - [Before the first run](#before-the-first-run)
    - [Try these first](#try-these-first)
  - [Stage coverage](#stage-coverage)
  - [Skills](#skills)
  - [Family boundary](#family-boundary)
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
thresholds, measuring contributor sentiment, assembling nomination evidence,
and walking nominators through post-vote onboarding. Nine skills cover the staged path from first contact
through committer promotion.

Why a framework skill family? The contributor-to-committer path is one
of the highest-leverage levers an open-source project has for long-term
health — lowering onboarding friction and shortening the time from first
PR to committer status keeps the contributor pipeline healthy. These
skills were designed independently but cover a contiguous path; grouping
them makes the adopter configuration and the evaluation story coherent.

> [!TIP]
> **Why this family**
> - A nomination brief built from a year of evidence rather than a recent impression
> - The post-vote checklist, from ICLA to welcome mail, with the steps that need a PMC chair marked
> - It names what GitHub cannot see — mailing lists, release votes, mentoring — instead of quietly scoring without them

## Install & first runs

Install just this family — one plugin, 6 skills. The path-to-committer track.

Once you have [added the marketplace](../setup/marketplace-install.md):

```text
/plugin install magpie-contributor-growth@apache-magpie
```

New to Magpie? The [quick start](../quick-start.md) walks the whole path in
one place — install, the first `/magpie-setup` run, and a recording of it
happening — plus the other agents and the secure-isolation setup to run next.

### Before the first run

<!-- BEGIN generated: skill-config (tools/dev/check-skill-config.py --fix) -->

![An animated `/magpie-setup config` run for the contributor-growth family: the check failing, the values derived from the repository, one question for the rest, and gitignored files written](../../assets/quickstart/wizard/contributor-growth.svg)

*Illustrative — the real run derives more and asks better. What is true is
the shape: it runs itself, it writes only gitignored files, and it stages
nothing.*

Every skill here resolves project-specific values from the adopter's
[`<project-config>/`](../../projects/_template/) directory — which is
`.apache-magpie-local/` (gitignored, yours) first, then
`.apache-magpie-overrides/` (committed, the project's).

**For yourself:** `/magpie-setup config` scaffolds and fills these locally.
Nothing is staged, nothing is committed, and it works on a repository that
has never adopted Magpie.

**For the project:** [`/magpie-setup adopt`](../setup/team-adoption.md)
commits them for every contributor, either scaffolded directly or promoted
from what you configured locally.

**Required.** Without these a skill would act on a guess, so it stops and
says which file is missing.

| File | What it carries | Read by |
|---|---|---|
| [`committer-onboarding-config.md`](../../projects/_template/committer-onboarding-config.md) | Capability-flag vocabulary for committer intake and governance models (`icla`/`dco`/`no-cla`; `asf-pmc`/`github-codeowners`/`maintainer-roster`). | `committer-onboarding` |
| [`committer-readiness.md`](../../projects/_template/committer-readiness.md) | The project's declared committer and PMC thresholds — what a contributor's activity is measured against. | `contributor-to-committer` |
| [`contributor-nomination-config.md`](../../projects/_template/contributor-nomination-config.md) | Nomination-brief thresholds and assessment window. | `nomination` |
| [`contributor-sentiment-config.md`](../../projects/_template/contributor-sentiment-config.md) | Signal thresholds for the sentiment gate. Every key has a default. | `sentiment` |
| [`onboarding-concierge-config.md`](../../projects/_template/onboarding-concierge-config.md) | The path a new contributor is walked through, and who owns each step. | `onboarding-concierge` |
| [`project.md`](../../projects/_template/project.md) | Project manifest. Identity, repositories, mailing lists, tools enabled, CVE tooling, GitHub project-board + issue-template field declarations. The single file every skill reads to resolve project-scoped references. | `activity-sweep`, `committer-onboarding`, `contributor-to-committer`, `nomination`, `onboarding-concierge`, `sentiment` |

**Optional.** Each has a documented fallback; absent, the skill still runs.

| File | What it carries | Read by |
|---|---|---|
| [`pmc-roster.md`](../../projects/_template/pmc-roster.md) | Who is binding. Read wherever a vote is counted or a PMC-only action is gated. | `nomination` |
| [`privacy-llm.md`](../../projects/_template/privacy-llm.md) | Which model tier may see which class of content, for projects routing foundation-private information away from third-party models. | `committer-onboarding` |

<!-- END generated: skill-config -->

### Try these first

*Illustrative shapes, not real transcripts — your output will differ. Nothing
below sends, merges, or posts anything without you confirming it.*

**Sweep recent contributor activity.**

```text
/magpie-contributor-growth:activity-sweep
```

![An activity-sweep run: ninety days of authored PRs, reviews, issues and comments for one contributor, with a note that mailing lists and release votes are not in the total](../../assets/quickstart/families/contributor-growth/activity-sweep.svg)

**Draft a nomination brief.**

```text
/magpie-contributor-growth:nomination
```

![A nomination run summarising a year of GitHub activity, naming the off-GitHub evidence it cannot see, and drafting the discussion thread without sending it](../../assets/quickstart/families/contributor-growth/nomination.svg)

**Onboard a new committer.**

```text
/magpie-contributor-growth:committer-onboarding
```

![A committer-onboarding run: two steps done, two waiting on a PMC chair, and the welcome announcement drafted but not sent](../../assets/quickstart/families/contributor-growth/committer-onboarding.svg)

## Stage coverage

| Stage | Skill | What it does |
|---|---|---|
| **First contact** | [`mentoring-welcome`](../../skills/mentoring-welcome/SKILL.md) | Drafts an orientation comment for a first-time contributor on a newly opened issue or PR; detects first-time authorship via the GitHub `author_association` field and skips repeat contributors. |
| **Issue on-ramp** | [`good-first-issue-author`](../../skills/good-first-issue-author/SKILL.md) | Drafts one net-new good first issue from a supplied gap or small task; a suitability gate and R1–R9 readiness checklist gate the draft; waits for maintainer confirmation before filing via `gh`. |
| **Backlog curation** | [`good-first-issue-sweep`](../../skills/good-first-issue-sweep/SKILL.md) | Sweeps the open issue backlog for existing issues that could be labelled as good first issues; scores each against the G1–G7 suitability rubric; classifies as READY / NEAR-MISS / SKIP and proposes labels after explicit maintainer confirmation. |
| **Activity tracking** | [`contributor-activity-sweep`](../../skills/contributor-activity-sweep/SKILL.md) | Produces a read-only GitHub activity card (PRs authored, code reviews, issues, comments) over a configurable window. |
| **Readiness check** | [`contributor-to-committer`](../../skills/contributor-to-committer/SKILL.md) | Maps a contributor's GitHub activity against the adopter's PMC-declared committer or PMC thresholds; surfaces a traffic-light brief (Not yet / Approaching / Ready to nominate) and a gap table showing what would close each remaining gap. Read-only; never opens a nomination thread. |
| **Nomination brief** | [`contributor-nomination`](../../skills/contributor-nomination/SKILL.md) | Assembles evidence prose for a committer or PMC vote thread: activity breadth, consistency, vendor-neutrality context, and a nomination-ready summary. Read-only; never posts to any list. |
| **Sentiment analysis** | [`contributor-sentiment`](../../skills/contributor-sentiment/SKILL.md) | Analyse contributor sentiment signals (issue tone, PR abandonment, response-time frustration) to surface early-warning indicators of contributor disengagement. Read-only. |
| **Onboarding concierge** | [`onboarding-concierge`](../../skills/onboarding-concierge/SKILL.md) | Interactive first-session guide for new contributors: walks through repo setup, points to good first issues, introduces project conventions and communication channels. |
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
| [`contributor-sentiment`](../../skills/contributor-sentiment/SKILL.md) | Triage | experimental |
| [`onboarding-concierge`](../../skills/onboarding-concierge/SKILL.md) | Mentoring | experimental |
| [`contributor-activity-sweep`](../../skills/contributor-activity-sweep/SKILL.md) | Triage | experimental |
| [`contributor-to-committer`](../../skills/contributor-to-committer/SKILL.md) | Mentoring | experimental |
| [`contributor-nomination`](../../skills/contributor-nomination/SKILL.md) | Triage | experimental |
| [`committer-onboarding`](../../skills/committer-onboarding/SKILL.md) | Triage | experimental |

All nine skills are `experimental`; no adopter has run the full
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

## Status

**Experimental.** All nine skills are on main with eval suites; no
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
  adopter scaffold index, with a purpose line for every file the table under
  *Before the first run* links.
- [`docs/setup/agentic-overrides.md`](../setup/agentic-overrides.md) —
  the override mechanism every skill in this family supports.
