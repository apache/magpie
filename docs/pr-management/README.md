<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [PR management skill family](#pr-management-skill-family)
  - [Install & first runs](#install--first-runs)
    - [Before the first run](#before-the-first-run)
    - [Try these first](#try-these-first)
  - [Skills](#skills)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# PR management skill family

> **Scope.** Works on any project, ASF or not — no
> Apache-Software-Foundation-specific assumptions baked in.

Maintainer-facing PR-queue management for projects with a public
contributor PR queue. Eight skills that compose into a complete
triage + review + mentoring + hygiene pass:

1. **Agentic Triage** — sweep open PRs, classify against the project's
   quality criteria, propose a disposition (draft / comment /
   close / rebase / rerun / mark ready / ping), execute on
   maintainer confirmation.
2. **Stats** — read-only summary tables of the open PR backlog,
   grouped by area label, so the maintainer can see where queue
   pressure is sitting before / after a triage sweep.
3. **Code review** — deep, line-aware code review one PR at a
   time. Reads the diff, applies the project's review criteria,
   drafts an `APPROVE` / `REQUEST_CHANGES` / `COMMENT` review
   with inline comments, posts on confirmation.
4. **Quick-merge** — express-lane screener for trivial, low-risk
   PRs (docs, changelog, translations, tests) that pass every
   quality gate; surfaces ranked candidates with diff summaries
   and the exact merge command for the maintainer to run. Never
   merges itself — automated merge is the framework's
   deliberately-deferred Agentic Autonomous mode.
5. **Mentor** — joins a PR (or issue) thread in a teaching
   register: clarifying questions, pointers to project conventions
   and docs, an explanation of *why* a change is being asked for.
   Waits for explicit maintainer confirmation before posting;
   never gatekeeps. Lives in the Mentoring mode but operates on
   the same PR surface as skills 1–4.
6. **Stale-sweep** — identify open PRs past a configurable
   inactivity threshold, classify as `NUDGE` or `CLOSE-STALE`,
   post one comment per PR on maintainer confirmation.
7. **Pre-first-PR check** — pre-flight a contributor's first PR
   against project conventions before it reaches a human reviewer;
   surfaces formatting, test, and documentation gaps.
8. **Reviewer routing** — suggest the best-fit reviewer(s) for a
   new PR based on path ownership, recent review history, and
   current load.

Why a framework skill family? These skills were originally
maintained inside one ASF project's developer-tooling repo as
`breeze pr auto-triage` and `breeze pr stats` — useful for any
ASF project with a meaningful contributor-PR queue, but locked
behind that project's local toolchain. Lifting them into the
framework lets other adopters reuse the playbook with their own
[adopter-config files](../../projects/_template/) for project-specific
knobs (committers team handle, area-label prefix, comment-template
wording, CI-check → doc-URL map, review-criteria source files).

> [!TIP]
> **Why this family**
> - A maintainer's review queue, sorted by what actually needs you today
> - Deep, sequential review of one PR at a time, with the draft review shown before it is posted
> - Nothing is posted, merged or closed without your explicit confirmation on that PR

## Install & first runs

Install just this family — one plugin, 8 skills. Maintainer-facing PR-queue management.

Once you have [added the marketplace](../setup/marketplace-install.md):

```text
/plugin install magpie-pr-management@apache-magpie
```

New to Magpie? The [quick start](../quick-start.md) walks the whole path in
one place — install, the first `/magpie-setup` run, and a recording of it
happening — plus the other agents and the secure-isolation setup to run next.

### Before the first run

<!-- BEGIN generated: skill-config (tools/dev/check-skill-config.py --fix) -->

Every skill here resolves project-specific values from the adopter's
[`<project-config>/`](../../projects/_template/) directory.
[`/magpie-setup adopt`](../setup/team-adoption.md) scaffolds all of them from
templates; you fill in the `TODO` fields for the skills you use.

**Required.** Without these a skill would act on a guess, so it stops and
says which file is missing.

| File | What it carries | Read by |
|---|---|---|
| [`pr-management-code-review-criteria.md`](../../projects/_template/pr-management-code-review-criteria.md) | List of project's review-criteria source files (repo-wide AGENTS.md, code-review docs, per-area AGENTS.md), security-model calibration doc, backport-branch pattern, section-anchor URLs. | `code-review` |
| [`pr-management-config.md`](../../projects/_template/pr-management-config.md) | Committers team handle, area-label prefix, project-specific labels (`ready for maintainer review`, etc.), grace windows. | `quick-merge`, `stale-sweep`, `stats`, `triage` |
| [`pr-management-quick-merge-config.md`](../../projects/_template/pr-management-quick-merge-config.md) | Thresholds, path globs, and the merge-command template for the express lane. | `quick-merge` |
| [`pr-management-triage-comment-templates.md`](../../projects/_template/pr-management-triage-comment-templates.md) | Comment-body URLs (PR quality criteria, two-stage triage rationale), AI-attribution footer wording, project display name. | `triage` |
| [`project.md`](../../projects/_template/project.md) | Project manifest. Identity, repositories, mailing lists, tools enabled, CVE tooling, GitHub project-board + issue-template field declarations. The single file every skill reads to resolve project-scoped references. | `code-review`, `mentor`, `quick-merge`, `reviewer-routing`, `stale-sweep`, `triage` |
| [`reviewer-roster.md`](../../projects/_template/reviewer-roster.md) | Who reviews what. | `reviewer-routing` |

**Optional.** Each has a documented fallback; absent, the skill still runs.

| File | What it carries | Read by |
|---|---|---|
| [`mentoring-config.md`](../../projects/_template/mentoring-config.md) | Tone knobs and hand-off protocol for the thread-level mentoring skill. | `mentor` |
| [`pr-management-triage-ci-check-map.md`](../../projects/_template/pr-management-triage-ci-check-map.md) | CI-check name pattern → category name + doc-URL mapping for the violations comment. | `triage` |
| [`privacy-llm.md`](../../projects/_template/privacy-llm.md) | Which model tier may see which class of content, for projects routing foundation-private information away from third-party models. | `reviewer-routing` |
| [`release-trains.md`](../../projects/_template/release-trains.md) | Active release branches, release-manager attribution per cut, rotation rosters, security-team roster. | `code-review`, `reviewer-routing` |
| [`stale-sweep-config.md`](../../projects/_template/stale-sweep-config.md) | Grace windows and exemption labels for stale sweeps. Absent, the framework defaults apply. | `stale-sweep` |

<!-- END generated: skill-config -->

### Try these first

*Illustrative shapes, not real transcripts — your output will differ. Nothing
below sends, merges, or posts anything without you confirming it.*

**Review a PR in depth.**

```text
> review PR #5193

  PR #5193  'Add retry to the S3 client'  +212 -18, 6 files
  2 blocking:   retry loop swallows KeyboardInterrupt (client.py:88)
                no test for the exhausted-retries path
  3 non-blocking nits. Review comment drafted, not posted.
```

**Triage the whole queue.**

```text
/magpie-pr-management:triage
```

![A triage run proposing one action each for four PRs — mark ready, ask if still active, ask for a rebase, promote out of draft — each needing confirmation](../../assets/quickstart/families/pr-management/triage.svg)

**See where the queue is stuck.**

```text
/magpie-pr-management:stats
```

![A stats run: a FAIR health rating, this week's and last week's open/close counts, the three areas under most pressure, and the triage funnel](../../assets/quickstart/families/pr-management/stats.svg)

## Skills

| Skill | Purpose |
|---|---|
| [`pr-management-triage`](../../skills/pr-management-triage/SKILL.md) | First-pass triage. Successor to `breeze pr auto-triage`. |
| [`pr-management-stats`](../../skills/pr-management-stats/SKILL.md) | Read-only summary tables grouped by area label. |
| [`pr-management-code-review`](../../skills/pr-management-code-review/SKILL.md) | Deep code review, one PR at a time. |
| [`pr-management-quick-merge`](../../skills/pr-management-quick-merge/SKILL.md) | Express-lane screener for trivial, low-risk PRs in the `ready for maintainer review` queue; surfaces ranked candidates with diff summaries and the exact merge command. Read-only on the queue; the one optional mutation (APPROVE) requires explicit per-PR confirmation. |
| [`pr-management-mentor`](../../skills/pr-management-mentor/SKILL.md) | Draft a teaching-register comment on a single GitHub issue or PR thread (clarifying questions, project-convention pointers, rationale explanations); waits for explicit maintainer confirmation before posting. `mode: Mentoring` — see also [`docs/mentoring/README.md`](../mentoring/README.md). |
| [`pr-stale-sweep`](../../skills/pr-stale-sweep/SKILL.md) | Sweep open PRs for inactivity past a configurable threshold; classify as `NUDGE` or `CLOSE-STALE` and post one comment per PR on confirmation. |
| [`pre-first-pr-check`](../../skills/pre-first-pr-check/SKILL.md) | Pre-flight a contributor's first PR against project conventions before it reaches a human reviewer. |
| [`reviewer-routing`](../../skills/reviewer-routing/SKILL.md) | Suggest the best-fit reviewer(s) for a new PR based on path ownership, recent review history, and current load. |

## Cross-references

- [Top-level README — Install](../../README.md#install) — 3-step bootstrap.
- [`projects/_template/README.md`](../../projects/_template/README.md) — adopter scaffold index, including the PR-management config files.
- [`tools/spec-loop/specs/pr-management-family.md`](../../tools/spec-loop/specs/pr-management-family.md) — functional spec: acceptance criteria, validation commands, and known gaps.
- [`docs/mentoring/README.md`](../mentoring/README.md) — `pr-management-mentor` family overview.
