<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Agentic Mentoring skill family](#agentic-mentoring-skill-family)
  - [Skills](#skills)
    - [What each skill covers](#what-each-skill-covers)
  - [Adopter contract](#adopter-contract)
  - [Status](#status)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Agentic Mentoring skill family

> **Scope.** Works on any project, ASF or not — no
> Apache-Software-Foundation-specific assumptions baked in.

Maintainer-facing skills that join contributor threads in a teaching
register, author newcomer-ready issues, curate the existing backlog for
newcomers, orient first-time contributors, and track a contributor's
readiness path to committer nomination.
Five skills shipped at `experimental`.

MISSION names Agentic Mentoring as the highest-value project-side mode and the one
off-the-shelf agent tooling skips. The framework lands the spec — tone guide,
hand-off protocol, adopter contract — and the skill implementations together,
so the project's tone choices are reviewable independently of runtime
behaviour and can be evolved without editing the skill body.

## Skills

| Skill | Purpose | Status |
|---|---|---|
| [`pr-management-mentor`](../../skills/pr-management-mentor/SKILL.md) | Draft a teaching-register comment on a single GitHub issue or PR thread; waits for maintainer confirmation before posting. | experimental |
| [`good-first-issue-author`](../../skills/good-first-issue-author/SKILL.md) | Draft one net-new good first issue from a supplied gap or small task; a suitability gate and R1–R9 readiness checklist gate the draft; waits for maintainer confirmation before filing via `gh`. | experimental |
| [`mentoring-welcome`](../../skills/mentoring-welcome/SKILL.md) | Draft a first-contact orientation comment for a first-time contributor on a newly opened issue or PR; detects first-time authorship via the GitHub `author_association` field; skips repeat contributors. | experimental |
| [`contributor-to-committer`](../../skills/contributor-to-committer/SKILL.md) | Read-only readiness tracker that maps a contributor's GitHub activity against the adopter's declared committer/PMC thresholds; surfaces a traffic-light brief (Not yet / Approaching / Ready to nominate) plus the specific evidence gaps that remain. | experimental |
| [`good-first-issue-sweep`](../../skills/good-first-issue-sweep/SKILL.md) | Sweep the open issue backlog for existing issues that could be labelled as good first issues; scores each against the G1–G7 suitability rubric and classifies as READY / NEAR-MISS / SKIP; proposes labels only after explicit maintainer confirmation. | experimental |

All five skills are read-only on tracker state or draft-then-confirm: no
skill posts, labels, closes, or files anything without explicit maintainer
confirmation in-session.

### What each skill covers

- **`pr-management-mentor`** — the thread-level Agentic Mentoring skill. Reads an
  issue or PR thread, decides whether a teaching-register intervention is
  warranted (clarifying question, convention pointer, paired example from a
  prior PR), drafts the comment, and waits for maintainer confirmation before
  posting. Never reviews code, routes PRs, or authors fixes — those are Agentic Triage
  and Agentic Drafting respectively.
- **`good-first-issue-author`** — the issue on-ramp skill. Takes a maintainer-
  supplied gap or small task, applies a suitability gate (too large, security-
  sensitive, or requiring a design decision → decline), runs through R1–R9
  readiness criteria, and drafts one self-contained issue a newcomer can pick
  up without prior repo context: scope, code pointers, contributing-doc links,
  acceptance criteria, and a rough effort estimate.
- **`mentoring-welcome`** — the first-contact skill. Triggered immediately
  after a first-time contributor opens an issue or PR. Drafts a lightweight
  orientation comment (contributing-guide link, community-norm pointers,
  expected next steps). Skips silently for repeat contributors and
  security-sensitive threads.
- **`contributor-to-committer`** — the readiness-tracking skill. Takes a
  GitHub handle, fetches their public activity on `<upstream>`, and maps it
  against the adopter's declared committer or PMC thresholds from
  `committer-readiness.md`. Returns a traffic-light verdict (Not yet /
  Approaching / Ready to nominate) plus a gap table showing exactly what
  evidence the contributor still needs. Read-only; never opens a nomination
  thread, sends a message, or modifies any record.
- **`good-first-issue-sweep`** — the backlog-curation skill. Sweeps the
  open issue backlog and scores each issue against the G1–G7 suitability
  rubric (scope, self-containment, code pointer, small effort, no security
  sensitivity, no architectural decision, no deprecation decision).
  Classifies each as READY (propose the GFI label), NEAR-MISS (surface
  specific edits that would make it GFI-ready), or SKIP (not suitable).
  Complements `good-first-issue-author`: the sweep stocks the on-ramp queue
  from existing work; the author creates net-new issues from supplied gaps.
  Read-only; proposes labels only after explicit maintainer confirmation.

## Adopter contract

The skills resolve project-specific content from these files in the adopter's
`<project-config>/` directory:

| File | Used by |
|---|---|
| [`mentoring-config.md`](../../projects/_template/mentoring-config.md) | `pr-management-mentor` (tone knobs, hand-off team, footer, `max_agent_turns`) |
| [`good-first-issue-config.md`](../../projects/_template/good-first-issue-config.md) | `good-first-issue-author`, `good-first-issue-sweep` (candidate-scope rules, GFI-label name, suitability rubric threshold) |
| [`mentoring-welcome-config.md`](../../projects/_template/mentoring-welcome-config.md) | `mentoring-welcome` (welcome-comment bodies, detection rules, contributing-guide URL) |
| [`committer-readiness.md`](../../projects/_template/committer-readiness.md) | `contributor-to-committer` (committer/PMC threshold declarations: PR count, review count, issue participation, tenure window) |

See the spec's [Adopter contract section](spec.md#adopter-contract) for the
required key documentation.

## Status

**Experimental.** Five skills shipped. No adopter has run the full
contributor-to-committer interaction path under evaluation conditions yet;
shape may change between framework versions.

To provide pilot feedback, copy
[`docs/pilot-report-template.md`](../pilot-report-template.md) into your
project notes, fill in each section, and optionally validate the filled-in
report with:

```bash
uv run --project tools/pilot-report-validator pilot-report-validate <your-report.md>
```

## Cross-references

- [`MISSION.md` § Agentic Mentoring](../../MISSION.md#technical-scope) —
  mode definition, contributor-empowerment framing.
- [`docs/modes.md` § Mentoring](../modes.md#mentoring) —
  current implementation status.
- [`spec.md`](spec.md) — full Agentic Mentoring spec: tone guide, hand-off
  protocol, adopter contract.
- [`projects/_template/README.md`](../../projects/_template/README.md) —
  adopter scaffold index.
- [`docs/setup/agentic-overrides.md`](../setup/agentic-overrides.md) —
  the override mechanism every skill in this family supports.
