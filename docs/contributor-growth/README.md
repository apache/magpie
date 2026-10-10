<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Contributor-growth skill family](#contributor-growth-skill-family)
  - [Surface information, never rank](#surface-information-never-rank)
  - [Install & first runs](#install--first-runs)
    - [Before the first run](#before-the-first-run)
    - [Why the configuration is personal](#why-the-configuration-is-personal)
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
ready, tracking contribution activity, comparing it with the project's
reference levels, measuring contributor sentiment, assembling nomination evidence,
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

## Surface information, never rank

The skills that look at people — `activity-sweep`, `calibrate`, `candidate-screen`, `contributor-to-committer` and `nomination` — only surface information.
The decision about who is nominated, and when, is always made by PMC members.

- **Never a ranking.**
  No skill orders people by any measure, scores them against each other, or picks a "top" few.
  Every list of people is in alphabetical order of GitHub handle, compared case-insensitively.
- **Never a verdict.**
  No skill says or suggests whether someone is ready, close, or not ready to be nominated.
  Counts are shown next to the project's reference levels as plain numbers, without a status, a band or a recommendation.
  `candidate-screen` goes further: it uses the reference levels only to pre-filter out the long tail, and shows everyone else's data with no reference levels at all.
- **Deliberately more, not fewer.**
  A list of likely candidates includes more people than the PMC would consider, on purpose, so that nobody is overlooked.
  `calibrate` sets its reference levels well below what the project has actually elected — by default three quarters of it (`calibration_relaxation`, `0.75`) — to make that true.
  Appearing on a list means only that someone's details are worth a look.
- **A report is a list and a summary.**
  A report lists the people it covers, alphabetically, each linked to their details, followed by a paragraph or two summarising what was found.
  The summary describes the findings; it does not judge or recommend anyone.

Every brief and report these skills produce says this at the top.

## Install & first runs

Install just this family — one plugin, 9 skills. The path-to-committer track.

Once you have [added the marketplace](../setup/marketplace-install.md):

```text
/plugin install magpie-contributor-growth@apache-magpie
```

New to Magpie? The [quick start](../quick-start.md) walks the whole path in
one place — install, the first `/magpie-setup` run, and a recording of it
happening — plus the other agents and the secure-isolation setup to run next.

### Before the first run

<!-- BEGIN generated: skill-config (tools/dev/check-skill-config.py --fix) -->

![An animated `/magpie-setup config` run for the contributor-growth family: the check failing, the values derived from the repository, one question for the rest, and personal files written](../../assets/quickstart/wizard/contributor-growth.svg)

*Illustrative — the real run derives more and asks better. What is true is
the shape: it runs itself, it writes only your personal layer, and it
stages nothing.*

Every skill here resolves project-specific values from the adopter's
[`<project-config>/`](../../plugins/magpie-setup/templates/) directory — which is
your personal layer first — `.apache-magpie-local/` (gitignored) in a
project that adopted Magpie, `<git-common-dir>/apache-magpie/` in one
that did not — then `.apache-magpie-overrides/` (committed, the project's).

**For yourself:** `/magpie-setup config` scaffolds and fills these locally.
Nothing is staged, nothing is committed, and it works on a repository that
has never adopted Magpie.

**This configuration stays personal.** `/magpie-setup adopt` never
promotes or scaffolds it into `.apache-magpie-overrides/`: committed
thresholds would tell every contributor how to game them.

**Required.** Without these a skill would act on a guess, so it stops and
says which file is missing.

| File | What it carries | Read by |
|---|---|---|
| [`committer-onboarding-config.md`](../../plugins/magpie-setup/templates/committer-onboarding-config.md) | Capability-flag vocabulary for committer intake and governance models (`icla`/`dco`/`no-cla`; `asf-pmc`/`github-codeowners`/`maintainer-roster`). | `committer-onboarding` |
| [`committer-readiness.md`](../../plugins/magpie-setup/templates/committer-readiness.md) | The project's declared committer and PMC thresholds — what a contributor's activity is measured against. | `calibrate`, `candidate-screen`, `contributor-to-committer` |
| [`contributor-nomination-config.md`](../../plugins/magpie-setup/templates/contributor-nomination-config.md) | Nomination-brief thresholds and assessment window. | `calibrate`, `candidate-screen`, `nomination` |
| [`contributor-sentiment-config.md`](../../plugins/magpie-setup/templates/contributor-sentiment-config.md) | Signal thresholds for the sentiment gate. Every key has a default. | `sentiment` |
| [`onboarding-concierge-config.md`](../../plugins/magpie-setup/templates/onboarding-concierge-config.md) | The path a new contributor is walked through, and who owns each step. | `onboarding-concierge` |
| [`privacy-llm.md`](../../plugins/magpie-setup/templates/privacy-llm.md) | Which model tier may see which class of content, for projects routing foundation-private information away from third-party models. | `calibrate` |
| [`project.md`](../../plugins/magpie-setup/templates/project.md) | Project manifest. Identity, repositories, mailing lists, tools enabled, CVE tooling, GitHub project-board + issue-template field declarations. The single file every skill reads to resolve project-scoped references. | `activity-sweep`, `calibrate`, `candidate-screen`, `committer-onboarding`, `contributor-to-committer`, `identity-map`, `nomination`, `onboarding-concierge`, `sentiment` |

**Optional.** Each has a documented fallback; absent, the skill still runs.

| File | What it carries | Read by |
|---|---|---|
| [`contributor-identities.md`](../../plugins/magpie-setup/templates/contributor-identities.md) | The project's community channels, and confirmed mappings from each contributor's GitHub handle to their Slack, Discord, mailing-list, and social-media handles. Written by `contributor-identity-map` after a maintainer confirms each one. | `committer-onboarding`, `identity-map` |
| [`issue-tracker-config.md`](../../plugins/magpie-setup/templates/issue-tracker-config.md) | Tracker URL, project key, auth model, default query templates. | `activity-sweep`, `calibrate`, `contributor-to-committer`, `nomination`, `sentiment` |
| [`pmc-roster.md`](../../plugins/magpie-setup/templates/pmc-roster.md) | Who is binding. Read wherever a vote is counted or a PMC-only action is gated. | `candidate-screen`, `nomination` |

<!-- END generated: skill-config -->

### Why the configuration is personal

This family is **personal-recommended and not adoptable by default.**
Install it for yourself — user scope, or install-only in this repository — on the machine of each maintainer who runs these skills.
`/magpie-setup adopt` leaves it out of the committed floor unless a maintainer explicitly insists and accepts the risk below, and records that acceptance in `.apache-magpie.lock`.

The reason is gaming.
Committer thresholds, nomination criteria, calibration floors, sentiment caps and the identity map are the project's private judgement about people.
Committed to the repository, they become a public checklist:
a contributor can point at a threshold and demand a nomination, and every later edit to it becomes a negotiation rather than a decision.

So the five files this family adds — `committer-onboarding-config.md`, `committer-readiness.md`, `contributor-identities.md`, `contributor-nomination-config.md` and `contributor-sentiment-config.md` — always live in your personal layer, even in a project that has adopted Magpie and even when the family itself is in the floor:
`<git-common-dir>/apache-magpie/` when Magpie is only installed, `.apache-magpie-local/` when the project has adopted it.
Never commit them to `.apache-magpie-overrides/`;
`adopt` does not promote or scaffold them there, and the skill validator warns when it finds one.
`contributor-calibrate` writes its floors to the personal layer and never offers the committed one.
Maintainers who want the same numbers share them the way they share the deliberation itself, on the private list.

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
| **Calibration** | [`contributor-calibrate`](../../skills/contributor-calibrate/SKILL.md) | Derives committer and PMC reference levels from the project's own past nomination decisions on the private list, deliberately relaxed well below what the project elected; proposes a config diff holding numbers only, with nothing about any nominee leaving the session. |
| **Candidate screening** | [`contributor-candidate-screen`](../../skills/contributor-candidate-screen/SKILL.md) | Pre-filters out the long tail of recent contributors, then shows the activity data of everyone else — deliberately more people than the PMC would consider, never scored or compared with thresholds — and writes a report to a repository the GitHub API reports as private, after the maintainer has read it: an alphabetical list linked to each person's details, and a paragraph or two summarising the findings. Never a ranking, never a verdict. |
| **Activity vs. reference** | [`contributor-to-committer`](../../skills/contributor-to-committer/SKILL.md) | Shows a contributor's activity next to the project's committer or PMC reference levels, as plain numbers with the difference, and a short factual summary. No status, band, or readiness verdict. Read-only; never opens a nomination thread. |
| **Identity mapping** | [`contributor-identity-map`](../../skills/contributor-identity-map/SKILL.md) | Maps any contributor's GitHub handle to their Slack, Discord, Matrix, mailing-list, and social-media handles; infers from the sources the session can reach and records only the mappings a maintainer confirms. Used by `committer-onboarding` and `contributor-nomination`. |
| **Nomination brief** | [`contributor-nomination`](../../skills/contributor-nomination/SKILL.md) | Assembles evidence for a committer or PMC discussion: activity breadth, consistency, vendor-neutrality context, and factual narrative prose. Never rates the contributor or says whether they are ready. Read-only; never posts to any list. |
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
| [`contributor-identity-map`](../../skills/contributor-identity-map/SKILL.md) | Triage | experimental |
| [`contributor-to-committer`](../../skills/contributor-to-committer/SKILL.md) | Mentoring | experimental |
| [`contributor-nomination`](../../skills/contributor-nomination/SKILL.md) | Triage | experimental |
| [`contributor-calibrate`](../../skills/contributor-calibrate/SKILL.md) | Triage | experimental |
| [`contributor-candidate-screen`](../../skills/contributor-candidate-screen/SKILL.md) | Triage | experimental |
| [`committer-onboarding`](../../skills/committer-onboarding/SKILL.md) | Triage | experimental |

All twelve skills are `experimental`; no adopter has run the full
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

**Experimental.** All eleven skills are on main with eval suites; no
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
- [`projects/_template/README.md`](../../plugins/magpie-setup/templates/README.md) —
  adopter scaffold index, with a purpose line for every file the table under
  *Before the first run* links.
- [`docs/setup/agentic-overrides.md`](../setup/agentic-overrides.md) —
  the override mechanism every skill in this family supports.
