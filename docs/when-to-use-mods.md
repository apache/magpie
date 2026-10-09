<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [When to use a mod in a Magpie family plugin](#when-to-use-a-mod-in-a-magpie-family-plugin)
  - [Overview and motivation](#overview-and-motivation)
  - [The four non-negotiable constraints](#the-four-non-negotiable-constraints)
    - [1. Vendor neutrality (the additive-only rule)](#1-vendor-neutrality-the-additive-only-rule)
    - [2. Security and unsandboxed execution boundaries](#2-security-and-unsandboxed-execution-boundaries)
    - [3. Privacy-LLM compliance](#3-privacy-llm-compliance)
    - [4. Distribution and enterprise policy fallbacks](#4-distribution-and-enterprise-policy-fallbacks)
  - [Architectural seam: mods vs. capabilities vs. skills](#architectural-seam-mods-vs-capabilities-vs-skills)
  - [Decision rubric: when to author a mod](#decision-rubric-when-to-author-a-mod)
    - [Allowed and recommended uses](#allowed-and-recommended-uses)
    - [Forbidden anti-patterns](#forbidden-anti-patterns)
  - [Starting points across skill families](#starting-points-across-skill-families)
  - [Packaging, testing, and CI validation](#packaging-testing-and-ci-validation)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# When to use a mod in a Magpie family plugin

Claude Code introduces **mods** (TypeScript/JavaScript event hook modules packaged in plugins).
This page documents the framework rules, boundaries, and decision rubric for when to introduce a mod into an Apache Magpie family plugin, and where mods must never be used.

The central theme of any Magpie mod is **moving deterministic or presentational work out of the model's context**.
Doing work in local code eliminates token consumption, removes latency, and produces deterministic user experiences while preserving full multi-harness portability.

## Overview and motivation

A mod is a plugin component that executes inside the host agent process when events occur.
Each hook acts as middleware `($, e, next)` that can observe an event, rewrite it, or answer it without initiating a model turn.

In Apache Magpie, skills are the universal unit of workflow authorship ([`PRINCIPLES.md` §15](../PRINCIPLES.md#15-skills-are-the-unit-of-authorship)).
A skill is plain Markdown that any capable agentic harness can execute.
However, certain repetitive tasks do not require model reasoning:
- Checking whether local lockfiles have drifted before executing a skill.
- Rendering live terminal dashboards, progress bands, or interactive multi-item selection panes.
- Executing zero-token slash commands (such as listing available skills or inspecting local setup status).
- Enforcing deterministic safety checks (such as grepping outgoing patches for private CVE identifiers before pushing).

When implemented as a mod, these operations run with **zero token cost** and zero latency.

## The four non-negotiable constraints

Every mod authored for or shipped with Apache Magpie must strictly comply with four non-negotiable constraints.

### 1. Vendor neutrality (the additive-only rule)

Vendor neutrality is a foundational design principle of Apache Magpie ([`PRINCIPLES.md` §10](../PRINCIPLES.md#10-vendor-neutrality-is-non-negotiable), [`docs/vendor-neutrality.md`](vendor-neutrality.md)).
Mods exist only in Claude Code (CLI and Desktop Code tab).
They don't run in Codex or Gemini CLI, and the VS Code panel and `claude -p` don't draw them.

Therefore, a mod can **only ever enhance a skill additively**.
Every skill must continue to work end-to-end when mods are disabled, unsupported, or absent.
A skill that requires a mod to complete its core workflow is broken by definition.

When a mod accelerates or formats an interaction, the underlying skill must maintain a clean fallback:
- If a mod provides an interactive multi-item review pane, the skill must still support sequential terminal prompts or standard markdown output on other harnesses.
- If a mod performs a zero-token pre-flight check, the skill must retain its standard markdown pre-flight step for harnesses without mod support.

### 2. Security and unsandboxed execution boundaries

Mods execute directly in the user's host environment with full user privileges outside the Bash sandbox.
A mod's `$.fs`, `$.process`, and `$.http` calls bypass the filesystem isolation and network egress gateways that sandbox standard agent tool executions.
Furthermore, a mod can intercept and approve tool calls that an interactive user confirmation rule would otherwise prompt for.

To protect adopters:
- Any mod shipped in a Magpie family plugin must expose a minimal, strictly auditable `calls:` surface.
- Mods must never execute unvetted external scripts, spawn long-lived unsandboxed background daemons, or initiate untracked network requests.
- All secure-setup documentation ([`docs/setup/secure-agent-setup.md`](setup/secure-agent-setup.md)) must explicitly document the security trade-offs of enabled mods.

### 3. Privacy-LLM compliance

The privacy-aware LLM routing policy ([`docs/setup/privacy-llm.md`](setup/privacy-llm.md), [`RFC-AI-0003`](rfcs/RFC-AI-0003.md)) governs every model interaction.
Calls to `$.model.complete`, `$.model.fork`, or `turn.step` model routing constitute model hops under the privacy rules.

- A mod must never route sensitive or private project data to an unapproved model endpoint.
- A mod must not attempt to circumvent privacy sanitization or PII redaction filters.
- Mods should favor deterministic code execution over embedded model calls whenever possible.

### 4. Distribution and enterprise policy fallbacks

Magpie distributes skills through modular family plugins (such as `plugins/magpie-setup/` and `plugins/magpie-utilities/`).
When a family includes a mod, the mod files live under the family plugin's `hooks/` directory (e.g. `hooks/hooks.json` and `hooks/register.ts`), not directly in the plugin root.

Enterprise environments often enforce strict administrator policies, such as `allowManagedModsOnly`.
In these environments, user-level or third-party mods will be blocked by the agent runtime.
Magpie plugins must handle this gracefully: the plugin and its skills will load normally, and the workflow must proceed without throwing errors or halting execution.

## Architectural seam: mods vs. capabilities vs. skills

To maintain architectural clarity, Magpie enforces a strict distinction between skills, capability contracts, tools, and mods:

```text
┌────────────────────────────────────────────────────────┐      ┌─────────────────────────────────────────────────┐
│ SKILLS (Universal Markdown)                            │      │ MODS (Claude Code Only)                         │
│ - Portable across all harnesses (Gemini, Codex, etc.)  │      │ - Additive event hooks                          │
│ - Declares required capability contracts (contract:*)  │<─────┤ - Hooks harness alongside skill execution       │
└───────────────────────────┬────────────────────────────┘      │ - Zero-token UI, commands, & pre-checks         │
                            │                                   │ - Lives under plugins/<family>/hooks/           │
                            v                                   └─────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ CAPABILITY CONTRACTS & TOOLS (Python / Shell)          │
│ - Abstraction layer for vendor backends (GitHub, Git)  │
│ - Backed by tool adapters under tools/<name>/          │
└────────────────────────────────────────────────────────┘
```

A mod is **not** a Magpie capability contract.
Capability contracts (`contract:tracker`, `contract:source-control`, `contract:cve-authority`) define abstract operations fulfilled by swappable backend tools.
Mods operate purely at the harness integration tier alongside skill execution to enhance user experience and optimize token efficiency.

## Decision rubric: when to author a mod

Contributors and maintainers should evaluate proposed mod implementations against the following rubric.

### Allowed and recommended uses

| Use Case | Implementation Mechanism | Benefit |
|---|---|---|
| **Zero-Token Slash Commands** | `$.command.register` + `command.run` | Instant execution of deterministic utilities (e.g. `/magpie-skills`, `/magpie-status`) without consuming model tokens or waiting for LLM turns. |
| **Presentational UI & Live Panes** | `ui.render` (`Pane`, `AbovePrompt`), `$.ui.toast`, `$.ui.status` | Rich interactive terminal surfaces (e.g. review finding selectors, vote tally countdowns, triage progress bands). |
| **Deterministic Pre-Push & Safety Guards** | `tool.call`, `tool.check` on `git commit` / `gh pr` | Intercepting commands to inspect outgoing text for accidental private CVE or secret leaks before network dispatch. |
| **Token-Free Lock Drift Detection** | `session.start` hook comparing lockfiles via `$.fs` | Immediate notification of snapshot drift without burning prompt tokens on every skill execution. |
| **Hardware Key & Auth Toasts** | `$.ui.toast` / `$.ui.status` during GPG signing | Non-intrusive status indicators when operations wait on hardware token touches. |

### Forbidden anti-patterns

| Anti-Pattern | Why It Is Forbidden | Correct Alternative |
|---|---|---|
| **Embedding Skill Workflow Logic in a Mod** | Violates vendor neutrality; breaks execution on Gemini CLI, Codex, and Cursor. | Keep workflow steps in the skill's markdown; use the mod only for presentational enhancement. |
| **Replacing Capability Tools with Unsandboxed Mod Calls** | Bypasses sandbox security and breaks backend interchangeability. | Implement backend functionality as a tool adapter under `tools/<name>/` fulfilling a capability contract. |
| **Silent Tool Call Approvals** | Bypasses the human-in-the-loop safety principle ([`PRINCIPLES.md` §7](../PRINCIPLES.md#7-the-human-is-always-in-the-loop-until-they-choose-otherwise)). | Always require explicit maintainer confirmation before executing state-changing operations. |
| **Unvetted Network Egress** | Violates data residency and sandbox egress controls. | Restrict mod network calls; route external fetches through vetted tool adapters. |

## Starting points across skill families

The following table summarizes candidate opportunities for additive mods across Magpie skill families:

| Skill Family | Candidate Mod Enhancement | Fallback Behaviour (Without Mod) |
|---|---|---|
| **`family:setup`** | Instant lockfile drift notification on `session.start`; zero-token `/magpie-status` command; GPG hardware touch toast. | Skill pre-flight step performs comparison in prompt context; standard CLI status output. |
| **`family:utilities`** | Zero-token `/magpie-skills` command; live token-usage band during skill authoring and evals. | Standard skill execution via model turn. |
| **`family:security`** | Deterministic pre-commit/pre-push grep for unredacted CVE references; local tracker queue dashboard pane. | Explicit grep check instruction in `security-issue-fix` workflow step. |
| **`family:pr-management`** | Interactive review pane with accept/skip/edit buttons for code review findings; triage sweep progress band. | Sequential `AskUserQuestion` prompts or consolidated review summary markdown. |
| **`family:issue`** | Issue backlog status pane; triage sweep progress indicator. | Standard terminal summary output. |
| **`family:release-management`** | Live 72-hour vote tally countdown timer; step-by-step RC verification checklist pane. | Static markdown checklist rendered in terminal. |
| **`family:pairing`** | Side-by-side multi-agent review findings pane. | Consolidated sequential findings list in session transcript. |

## Packaging, testing, and CI validation

Mods ship inside their respective family plugins in `plugins/<family>/` under the `hooks/` directory.
The plugin manifest sits at `.claude-plugin/plugin.json` declaring plugin metadata:

```json
{
  "name": "magpie-utilities",
  "description": "Apache Magpie — framework meta-skills and zero-token utilities.",
  "version": "0.9.0.dev0"
}
```

The hooks manifest at `hooks/hooks.json` lists the mod modules to load:

```json
{
  "modules": ["./register.ts"]
}
```

The module (`hooks/register.ts`) exports a `register(on, options)` function that registers event listeners with the harness.
It imports only its own files, by relative path, and `claude-code`.
Node built-ins such as `node:fs` are not available: reach files, the environment and processes through the mods API (`$.fs`, `$.env`, `$.process`), so the `calls:` line `claude plugin validate` prints is the module's whole surface.
`hooks/hooks.json` can also carry the plugin's settings hooks under `hooks`, next to `modules`; a mod that takes over from a settings hook keeps that hook wired there for sessions where mods do not load.

Every mod must include unit tests and pass strict validation before landing:
1. **Static Validation**: Mod modules must pass `claude plugin validate <dir> --strict` to verify hooked events and API calls.
   Claude Code runs the same analysis when it loads a mod and skips a module that fails it, so a mod that fails here does nothing at all on an adopter's machine.
2. **Automated Unit Tests**: Hook logic must be tested using `claude plugin test` with corresponding `*.test.ts` test suites written against `claude-code/testing`.
   A mod with no tests fails the check.
3. **CI Integration**: the `check-claude-mods` prek hook ([`tools/dev/check-claude-mods.sh`](../tools/dev/check-claude-mods.sh)) runs both commands on every plugin whose `hooks/hooks.json` declares `modules`, on every pull request and push to `main`.
   prek installs a pinned Claude Code into the hook environment, so neither a local install nor a login is needed.
   The hook is in the `manual` stage, so ordinary commits skip it; run it before pushing a mod with `prek run check-claude-mods --hook-stage manual --all-files`.
   The pin is bumped three times a week, with a 12-hour cooldown, by [`bump-hook-npm-pins.yml`](../.github/workflows/bump-hook-npm-pins.yml).
   Claude Code is a dev-only tool here: CI runs it to check the mods, it is not a dependency of anything Magpie ships, and nothing from it goes into a release or a plugin.

## See also

- [`docs/vendor-neutrality.md`](vendor-neutrality.md) — How Magpie achieves neutrality across six independent axes
- [`docs/extending.md`](extending.md) — Extension points across skills, tools, organizations, and harnesses
- [`docs/labels-and-capabilities.md`](labels-and-capabilities.md) — The capability taxonomy and label taxonomy
- [`docs/setup/secure-agent-setup.md`](setup/secure-agent-setup.md) — The sandboxed agent execution environment
- [`docs/setup/privacy-llm.md`](setup/privacy-llm.md) — Privacy-aware LLM routing and endpoint approval
- [`PRINCIPLES.md`](../PRINCIPLES.md) — Core architectural principles of Apache Magpie
