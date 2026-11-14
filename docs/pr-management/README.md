<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Pull requests](#pull-requests)
  - [Install & first runs](#install--first-runs)
  - [Review a pull request](#review-a-pull-request)
  - [Skills](#skills)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<a id="pr-management-skill-family"></a>
# Pull requests

> **Scope.** Works on any project, ASF or not — no
> Apache-Software-Foundation-specific assumptions baked in.

Maintainer-facing PR-queue management for projects with a public
contributor PR queue. Nine skills that compose into a complete
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
9. **Stack review** — review a GitHub stacked pull request as one
   unit: chain currency, file-by-layer matrix, removed-definition
   seams, narrative drift, and code read by tier with a coverage
   table. Drafts one rolling `COMMENT` on the lowest open layer and
   names the layers that deserve a `code-review` pass. Never
   approves.

Why a framework skill family? These skills were originally
maintained inside one ASF project's developer-tooling repo as
`breeze pr auto-triage` and `breeze pr stats` — useful for any
ASF project with a meaningful contributor-PR queue, but locked
behind that project's local toolchain. Lifting them into the
framework lets other adopters reuse the playbook with their own
[adopter-config files](../../plugins/magpie-setup/templates/) for project-specific
knobs (committers team handle, area-label prefix, comment-template
wording, CI-check → doc-URL map, review-criteria source files).

> [!TIP]
> **Why this family**
> - A maintainer's review queue, sorted by what actually needs you today
> - Deep, sequential review of one PR at a time, with the draft review shown before it is posted
> - Nothing is posted, merged or closed without your explicit confirmation on that PR

## Install & first runs

[Install & first runs](install.md) has the install command for this family,
the files to configure before the first run, and the skills to try first.

## Review a pull request

Run `/magpie-pr-management:code-review` to review one pull request and draft a review for maintainer confirmation.
Run `/magpie-pr-management:stack-review` to review a stacked pull request as one unit.
Use `/magpie-pr-management:pr-triage` to classify the open queue and propose next steps.

## Skills

| Skill | Purpose |
|---|---|
| [`pr-management-triage`](../../skills/pr-management-triage/SKILL.md) | First-pass triage. Successor to `breeze pr auto-triage`. |
| [`pr-management-stats`](../../skills/pr-management-stats/SKILL.md) | Read-only summary tables grouped by area label. |
| [`pr-management-code-review`](../../skills/pr-management-code-review/SKILL.md) | Deep code review, one PR at a time. |
| [`pr-management-merge-candidates`](../../skills/pr-management-merge-candidates/SKILL.md) | Express-lane screener for trivial, low-risk PRs in the `ready for maintainer review` queue; surfaces ranked candidates with diff summaries and the exact merge command. Read-only on the queue; the one optional mutation (APPROVE) requires explicit per-PR confirmation. |
| [`pr-management-thread-mentor`](../../skills/pr-management-thread-mentor/SKILL.md) | Draft a teaching-register comment on a single GitHub issue or PR thread (clarifying questions, project-convention pointers, rationale explanations); waits for explicit maintainer confirmation before posting. `mode: Mentoring` — see also [`docs/mentoring/README.md`](../mentoring/README.md). |
| [`pr-stale-sweep`](../../skills/pr-stale-sweep/SKILL.md) | Sweep open PRs for inactivity past a configurable threshold; classify as `NUDGE` or `CLOSE-STALE` and post one comment per PR on confirmation. |
| [`pre-first-pr-check`](../../skills/pre-first-pr-check/SKILL.md) | Pre-flight a contributor's first PR against project conventions before it reaches a human reviewer. |
| [`reviewer-routing`](../../skills/reviewer-routing/SKILL.md) | Suggest the best-fit reviewer(s) for a new PR based on path ownership, recent review history, and current load. |
| [`pr-management-stack-review`](../../skills/pr-management-stack-review/SKILL.md) | Review a GitHub stacked pull request as one unit — chain, file-by-layer matrix, removed-definition seams, narrative drift, code by tier with a coverage table. One rolling `COMMENT` on the lowest open layer; never approves; hands each layer to `pr-management-code-review`. |

## Cross-references

- [Top-level README — Install](../../README.md#install) — 3-step bootstrap.
- [`projects/_template/README.md`](../../plugins/magpie-setup/templates/README.md) — adopter scaffold index, including the PR-management config files.
- [`tools/spec-loop/specs/pr-management-family.md`](../../tools/spec-loop/specs/pr-management-family.md) — functional spec: acceptance criteria, validation commands, and known gaps.
- [`docs/mentoring/README.md`](../mentoring/README.md) — the Agentic Mentoring overview, including `pr-management-thread-mentor`.
