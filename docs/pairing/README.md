<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Pairing skill family](#pairing-skill-family)
  - [Skills](#skills)
    - [When to use which](#when-to-use-which)
  - [Relationship to `pr-management-code-review`](#relationship-to-pr-management-code-review)
  - [Adopter contract](#adopter-contract)
  - [Status](#status)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Pairing skill family

Developer-side pre-flight review skills that run in the maintainer's or
contributor's **own** dev loop — after local changes are ready but before
opening a PR. The family absorbs mechanical implementation-detail review
so the eventual human-to-human conversation between contributor and
maintainer stays on design, reasoning, and the trade-offs the project
cares about.

**Mentorship is intrinsic.** Pairing skills are not a replacement for
human code review; they are a pre-flight filter that separates
implementation-detail nits (formatting, convention violations, obvious
logical gaps) from the design-level conversation the project's
contributor-to-committer path is built on.

**No state changes.** Every skill in this family reads local git state
and returns a structured report. No PR is opened, no GitHub write
happens, no comment is posted, and the working tree is never mutated.

---

## Skills

| Skill | Purpose | Status |
|---|---|---|
| [`pairing-self-review`](../../skills/pairing-self-review/SKILL.md) | Structured pre-flight self-review of local changes against a configurable base. Single-pass: correctness, security, and conventions in one report. | experimental |
| [`pairing-multi-agent-review`](../../skills/pairing-multi-agent-review/SKILL.md) | Fan the same diff through three independent axis-focused passes (correctness, security, conventions); merge findings with deduplication and severity ranking. Higher confidence than a single pass; each axis is isolated so findings cannot cross-contaminate. | experimental |

### When to use which

- **`pairing-self-review`** — the default quick check. Fast, single
  context, covers correctness + security + conventions.
- **`pairing-multi-agent-review`** — when you want adversarial
  independence between review axes. Each pass cannot see the others'
  findings, so a security issue buried in a conventions sweep cannot
  get lost. Use for changes touching security-sensitive paths or for
  the final check before a high-stakes PR.

Both skills are read-only / hand-back and produce the same structured
report format, so you can switch between them without changing your
workflow.

---

## Relationship to `pr-management-code-review`

`pairing-self-review` and `pairing-multi-agent-review` run **before** a
PR is open. Once a PR is open and you want a maintainer-side deep code
review of an incoming contribution, use
[`pr-management-code-review`](../../skills/pr-management-code-review/SKILL.md)
instead.

---

## Adopter contract

The Pairing skills have no project-specific config files. They resolve
two standard placeholders from the adopter's `<project-config>/`:

| Placeholder | Resolved from |
|---|---|
| `<upstream>` | `project.md → upstream_repo` (owner/name of the public source repo) |
| `<default-branch>` | `project.md → upstream_default_branch` (e.g. `main`) |

No additional config files are required. The skills do not write to the
project's tracker, label set, or any shared infrastructure.

---

## Status

**Experimental.** Both `pairing-self-review` and
`pairing-multi-agent-review` are shipped and validate under
`skill-and-tool-validate`. No adopter-pilot evaluation has run yet;
shape may change between framework versions.

---

## Cross-references

- [`MISSION.md` § Pairing](../../MISSION.md#technical-scope) — mode
  rationale, sequencing constraints relative to Auto-merge.
- [`docs/modes.md` § Pairing](../modes.md#pairing) — implementation
  status and mode-lifecycle stage.
- [`docs/modes.md` § Mode lifecycle](../modes.md#mode-lifecycle) — how
  a mode moves from `experimental` to `stable`.
- [`projects/_template/README.md`](../../projects/_template/README.md) —
  adopter scaffold index.
- [`docs/setup/agentic-overrides.md`](../setup/agentic-overrides.md) —
  the override mechanism every skill in this family supports.
