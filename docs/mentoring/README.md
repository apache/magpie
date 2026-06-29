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

> **Scope — `asf: false`.** Works on any project, ASF or not — no
> Apache-Software-Foundation-specific assumptions baked in.

Maintainer-facing skills that join contributor threads in a teaching
register, author newcomer-ready issues, and orient first-time contributors.
Three skills shipped at `experimental`; a fourth (`contributor-to-committer`)
is in-flight.

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

All three skills are read-only on tracker state or draft-then-confirm: no
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

## Adopter contract

The skills resolve project-specific content from these files in the adopter's
`<project-config>/` directory:

| File | Used by |
|---|---|
| [`mentoring-config.md`](../../projects/_template/mentoring-config.md) | `pr-management-mentor` (tone knobs, hand-off team, footer, `max_agent_turns`) |
| [`good-first-issue-config.md`](../../projects/_template/good-first-issue-config.md) | `good-first-issue-author` (candidate-scope rules, R1–R9 threshold, filing target) |
| [`mentoring-welcome-config.md`](../../projects/_template/mentoring-welcome-config.md) | `mentoring-welcome` (welcome-comment bodies, detection rules, contributing-guide URL) |

See the spec's [Adopter contract section](spec.md#adopter-contract) for the
required key documentation.

## Status

**Experimental.** Three skills shipped. No adopter has run the full
contributor-to-committer interaction path under evaluation conditions yet;
shape may change between framework versions.

An in-flight fourth skill — `contributor-to-committer` — assembles readiness
evidence for a contributor approaching committer nomination and surfaces the
signals `contributor-nomination` already gathers. It is not yet on `main`.

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
