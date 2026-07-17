<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Codex first-class runtime](#codex-first-class-runtime)
  - [Runtime contract](#runtime-contract)
  - [Invoke a Magpie skill](#invoke-a-magpie-skill)
  - [Install](#install)
  - [Security model](#security-model)
    - [Sandbox and network](#sandbox-and-network)
    - [Exec-policy rules and approval policy](#exec-policy-rules-and-approval-policy)
    - [Deterministic guard rules](#deterministic-guard-rules)
    - [Trust boundary](#trust-boundary)
  - [Verify](#verify)
  - [setup-isolated lifecycle](#setup-isolated-lifecycle)
  - [Known limitations](#known-limitations)
  - [Upstream references](#upstream-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Codex first-class runtime

**Capability:** capability:platform

**Harness:** OpenAI Codex CLI, IDE, and desktop local runtime

This adapter makes Codex a native Apache Magpie skill runtime. It is not the
Claude Code codex delegation plugin: a maintainer with Codex and no Claude Code
can discover, invoke, and run Magpie skills end to end.

The implementation follows
[RFC-AI-0004](../rfcs/RFC-AI-0004.md): shared skill sources, a native sandbox,
and per-action human confirmation through Codex's own approval and exec-policy
layers.

## Runtime contract

| Magpie requirement | Codex implementation |
|---|---|
| Skill discovery | Codex reads the existing canonical `.agents/skills/magpie-*/SKILL.md` symlinks directly. No SKILL.md-to-AGENTS.md translation or duplicate source tree is needed. |
| Repository instructions | Codex reads the repository `AGENTS.md` hierarchy natively. |
| Tool bridges | Skills invoke the same language-neutral `tools/` CLI adapters. Network is disabled inside `workspace-write`; approved network actions cross the sandbox through Codex rules and approval policy. |
| Filesystem sandbox | Project `.codex/config.toml` selects `workspace-write`. |
| Human in the loop | `approval_policy = "on-request"` and `.codex/rules/magpie.rules` allow scoped reads, prompt mutations, and forbid credential disclosure. |
| Deterministic guard | The shared `tools/agent-guard` dispatch core is reachable through its harness-neutral `--check` / `--exec` modes (see [Deterministic guard rules](#deterministic-guard-rules)). |
| Credential isolation | `tools/agent-isolation/agent-iso.sh` launches `agent-iso codex` through the shared clean-environment wrapper. |

The committed profile lives in:

~~~text
.codex/
|-- config.toml
`-- rules/
    `-- magpie.rules
~~~

Both files are policy and are reviewed in Git.

## Invoke a Magpie skill

Codex scans `.agents/skills` from the current directory to the repository root,
follows symlinked skill directories, and reads `SKILL.md` when a skill is
chosen. After `magpie-setup` has adopted the repository:

1. Start Codex at the adopter repository root, preferably with
   `agent-iso codex`.
2. Use `/skills` to confirm that `magpie-*` skills are visible.
3. Invoke a skill explicitly by mentioning it with `$`, for example
   `$magpie-security-issue-triage`, or describe a task that matches its
   frontmatter description.
4. The selected skill resolves `tools/*` commands and project placeholders in
   exactly the same way as every other runtime.

An end-to-end triage therefore starts with:

~~~text
$magpie-security-issue-triage
~~~

There is no generated AGENTS.md per skill. `AGENTS.md` carries persistent
repository instructions; `SKILL.md` remains the workflow source.

## Install

Run `$magpie-setup` from Codex and select adopt or upgrade. The setup
lifecycle:

1. Creates the canonical `.agents/skills` links and harness relay links.
2. Merges the reviewed Codex posture into `.codex/` without deleting unrelated
   project settings. Conflicting sandbox or approval values are surfaced to the
   maintainer; they are never silently weakened.
3. Runs `sandbox-lint --codex .codex` on the merged result.
4. Asks the operator to trust the project in Codex. Repository content cannot
   grant its own trust.

When `.codex/` already exists, setup preserves unrelated keys. `magpie.rules`
is Magpie-owned; hand edits are shown before replacement.

For the clean-environment layer on Linux or macOS:

~~~bash
source <framework>/tools/agent-isolation/agent-iso.sh
agent-iso codex
~~~

On Windows, run the POSIX isolation layer through WSL when that layer is
required. Codex's native Windows sandbox and the project policy still apply to
a native Windows session.

## Security model

### Sandbox and network

The profile requires:

~~~toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[sandbox_workspace_write]
network_access = false
~~~

Networked bridges such as `gh`, `jira`, Gmail, PonyMail, and CVE tooling
therefore cannot silently use network access from the workspace sandbox. The
exec-policy file allows narrowly scoped read-only commands, prompts known
mutations, and forbids `gh auth token` and credential refresh operations.
Commands not matched by an allow rule still follow the native on-request
approval path.

### Exec-policy rules and approval policy

Per-action confirmation belongs to Codex's native rules and approval system:
`.codex/rules/magpie.rules` classifies known commands as `allow`, `prompt`,
or `forbidden` before they cross the sandbox boundary, and
`approval_policy = "on-request"` routes everything else to the operator. This
is the Codex mapping of RFC-AI-0004 Principle 1 (human-in-the-loop).

### Deterministic guard rules

Claude Code and OpenCode additionally wire the deterministic
[`tools/agent-guard`](../../tools/agent-guard/README.md) denials (AI
`Co-Authored-By` trailers, premature `--ready-for-review`, unsafe public
security wording, empty force-pushes) as in-process pre-tool hooks. Codex has
no equivalent wired hook adapter in this profile; the same `dispatch()` core
remains available through the harness-neutral `--check` / `--exec` modes
documented in the
[agent-guard README](../../tools/agent-guard/README.md#harness-neutral-path-any-runtime).
Until a native Codex adapter exists, those framework invariants rely on the
exec-policy prompts plus the operator's review of each confirmed action.

### Trust boundary

Project `.codex` configuration and rules load only for a trusted project. The
operator reviews that trust decision. The framework does not modify user trust
state.

Policy changes remain normal reviewed repository changes: an approved elevated
action can still modify `.codex/`, so the profile complements — never
replaces — code review.

## Verify

Run the static validator from the framework or snapshot:

~~~bash
uv run --directory tools/sandbox-lint --group dev sandbox-lint --codex .codex
~~~

Then test native rule classification:

~~~bash
codex execpolicy check --pretty \
  --rules .codex/rules/magpie.rules \
  -- gh pr view 313

codex execpolicy check --pretty \
  --rules .codex/rules/magpie.rules \
  -- gh pr create --title test --body test

codex execpolicy check --pretty \
  --rules .codex/rules/magpie.rules \
  -- gh auth token
~~~

The expected strictest decisions are `allow`, `prompt`, and `forbidden`,
respectively.

Also verify:

- `/skills` lists `magpie-setup` and a representative workflow skill.
- Each `tools/*` bridge used by the selected skill is present and
  authenticated; tool-specific preflight remains owned by that skill.

## setup-isolated lifecycle

The four setup-isolated skills route Codex to this adapter:

- `setup-isolated-setup-install` installs or merges the project profile and
  explains `agent-iso codex`.
- `setup-isolated-setup-verify` runs the static validator, rule-classification
  probes, `/skills` checks, and tool preflights.
- `setup-isolated-setup-update` compares the installed profile with the
  current framework snapshot. It reports drift and never weakens policy
  automatically.
- `setup-isolated-setup-doctor` runs the shared live environment probes inside
  the active Codex sandbox and reports native approval or network failures
  separately.

The Claude-specific setup remains available for Claude Code. Runtime routing
must happen before a setup-isolated skill follows Claude-only settings paths.

## Known limitations

- Codex exec-policy rules are an evolving runtime interface. Pin a minimum
  tested Codex version before calling the adapter stable, and rerun the
  classification probes on upgrades.
- The deterministic agent-guard denials are not wired as a native Codex hook;
  see [Deterministic guard rules](#deterministic-guard-rules).
- Native project policy requires explicit project trust.
- The clean-environment wrapper is POSIX shell. Native Windows sessions rely
  on the Codex Windows sandbox unless launched through WSL.
- MCP and account-backed integrations still require user-scoped registration
  and authentication. Repository policy never copies credentials into the
  project.

## Upstream references

- [Codex skills](https://developers.openai.com/codex/skills)
- [Codex configuration](https://developers.openai.com/codex/config-reference)
- [Codex rules](https://developers.openai.com/codex/rules)
- [Codex CLI source](https://github.com/openai/codex)
- [Agent Skills specification](https://agentskills.io/specification)
