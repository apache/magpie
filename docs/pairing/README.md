<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Agentic Pairing skill family](#agentic-pairing-skill-family)
  - [Install & first runs](#install--first-runs)
    - [Before the first run](#before-the-first-run)
    - [Works well with](#works-well-with)
    - [Try these first](#try-these-first)
  - [Skills](#skills)
    - [When to use which](#when-to-use-which)
  - [Relationship to `pr-management-code-review`](#relationship-to-pr-management-code-review)
  - [Adopter contract](#adopter-contract)
  - [Status](#status)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Agentic Pairing skill family

> **Scope.** Works on any project, ASF or not — no
> Apache-Software-Foundation-specific assumptions baked in.

Developer-side pre-flight review skills that run in the maintainer's or
contributor's **own** dev loop — after local changes are ready but before
opening a PR. The family absorbs mechanical implementation-detail review
so the eventual human-to-human conversation between contributor and
maintainer stays on design, reasoning, and the trade-offs the project
cares about.

**Mentorship is intrinsic.** Agentic Pairing skills are not a replacement for
human code review; they are a pre-flight filter that separates
implementation-detail nits (formatting, convention violations, obvious
logical gaps) from the design-level conversation the project's
contributor-to-committer path is built on.

**No state changes.** Every skill in this family reads local git state
and returns a structured report. No PR is opened, no GitHub write
happens, no comment is posted, and the working tree is never mutated.

---

> [!TIP]
> **Why this family**
> - Review your own diff before a maintainer spends their time on it
> - Findings split into blocking and non-blocking, so the nits do not drown the real problems
> - Nothing is sent, posted, or merged — the report is the output

## Install & first runs

Install just this family — one plugin, 2 skills. Review your own change before anyone else has to.

Once you have [added the marketplace](../setup/marketplace-install.md):

```text
/plugin install magpie-pairing@apache-magpie
```

New to Magpie? The [quick start](../quick-start.md) walks the whole path in
one place — install, the first `/magpie-setup` run, and a recording of it
happening — plus the other agents and the secure-isolation setup to run next.

### Before the first run

<!-- BEGIN generated: skill-config (tools/dev/check-skill-config.py --fix) -->

**Nothing here has to be configured.** These skills read the file below
when the project has one and fall back to a documented default when it
does not.

**Optional.** Each has a documented fallback; absent, the skill still runs.

| File | What it carries | Read by |
|---|---|---|
| [`project.md`](../../projects/_template/project.md) | Project manifest. Identity, repositories, mailing lists, tools enabled, CVE tooling, GitHub project-board + issue-template field declarations. The single file every skill reads to resolve project-scoped references. | `multi-agent-review`, `self-review` |

<!-- END generated: skill-config -->

<!-- BEGIN generated: companion-skills (tools/dev/check-companion-skills.py --fix) -->

### Works well with

Third-party packages, none of them required: this family works with none of
them installed, and Magpie neither bundles nor depends on any. They are named
because they are what a maintainer goes looking for next, and because the
answer differs by agent.

**[Code Review](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/code-review)** — Anthropic

Automated pull-request review through several specialised agents, scored by confidence.

*With this family:* Runs the same kind of pass over a PR that self-review runs over your local diff.

Available on **Claude Code** only.

**[Superpowers](https://github.com/obra/superpowers)** — obra (community)

A skills library and development methodology: brainstorming, plan writing, subagent-driven execution, systematic debugging.

*With this family:* self-review and multi-agent-review are pre-flight reads of your own diff; Superpowers adds the test-first and systematic-debugging habits upstream of them.

Available on **Claude Code**, **OpenAI Codex CLI**, **VS Code / GitHub Copilot**, **Google Gemini CLI**, **Cursor**, **OpenCode**.

Ships a plugin manifest per harness and one shared skills/ tree, the same shape Magpie uses, so it is not a Claude Code-only package.

Install commands per agent are in
[**Companion skill packages**](../setup/companion-skills.md).

<!-- END generated: companion-skills -->

### Try these first

*Illustrative shapes, not real transcripts — your output will differ.
Both skills are read-only: nothing is sent, merged, or posted.*

**Self-review before you push.**

```text
/magpie-pairing:self-review
```

![A self-review run over four changed files: one blocking finding and two non-blocking ones, with nothing sent, posted or merged](../../assets/quickstart/families/pairing/self-review.svg)

**Send it through an adversarial panel.**

```text
/magpie-pairing:multi-agent-review
```

![A multi-agent-review run showing what two independent reads of the same diff each found, and what only one of them found](../../assets/quickstart/families/pairing/multi-agent-review.svg)

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

The Agentic Pairing skills read local git state and write nothing: no PR is
opened, no comment posted, and the working tree is never mutated. They resolve
`<upstream>` and `<project-config>` placeholders when the project defines
them, and run without either.

## Status

**Experimental.** Both `pairing-self-review` and
`pairing-multi-agent-review` are shipped and validate under
`skill-and-tool-validate`. No adopter-pilot evaluation has run yet;
shape may change between framework versions.

To provide pilot feedback, copy
[`docs/pilot-report-template.md`](../pilot-report-template.md) into your
project notes, fill in each section, and optionally validate the filled-in
report with:

```bash
uv run --project tools/pilot-report-validator pilot-report-validate <your-report.md>
```

---

## Cross-references

- [`MISSION.md` § Agentic Pairing](../../MISSION.md#technical-scope) — mode
  rationale, sequencing constraints relative to Agentic Autonomous.
- [`docs/modes.md` § Pairing](../modes.md#pairing) — implementation
  status and mode-lifecycle stage.
- [`docs/modes.md` § Mode lifecycle](../modes.md#mode-lifecycle) — how
  a mode moves from `experimental` to `stable`.
- [`projects/_template/README.md`](../../projects/_template/README.md) —
  adopter scaffold index.
- [`docs/setup/agentic-overrides.md`](../setup/agentic-overrides.md) —
  the override mechanism every skill in this family supports.
