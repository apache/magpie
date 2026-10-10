<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Grok Build](#grok-build)
  - [Harness contract](#harness-contract)
  - [Verified runtime](#verified-runtime)
  - [Installation](#installation)
    - [Marketplace plugin](#marketplace-plugin)
    - [Framework checkout](#framework-checkout)
    - [Pinned snapshot](#pinned-snapshot)
  - [Trust and security boundary](#trust-and-security-boundary)
  - [Guard behavior](#guard-behavior)
  - [Verify](#verify)
  - [Update and uninstall](#update-and-uninstall)
  - [Spec-loop runner](#spec-loop-runner)
  - [Known limitations](#known-limitations)
  - [Developer checks](#developer-checks)
  - [Upstream references](#upstream-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Grok Build

**Capability:** platform:harness

Grok Build is supported for the deterministic Magpie action guard and the
spec-loop headless runner.
This does not add a dedicated Grok sandbox profile.

## Harness contract

| Surface | Grok contract | Magpie integration |
|---|---|---|
| Hook event | `PreToolUse` | `agent-guard` |
| Shell matcher | `Bash` | marketplace plugin or setup-installed project hook |
| Captured shell tool | `run_terminal_command` | reads `toolInput.command` |
| Workspace path | `GROK_WORKSPACE_ROOT` | source/snapshot project hook |
| Plugin path | `GROK_PLUGIN_ROOT` | marketplace/plugin hook |
| Deny | JSON decision with reason | shared `dispatch()` result |
| Allow | exit 0 | shared `dispatch()` result |

## Verified runtime

The `PreToolUse` payload contract was captured against:

`grok 1.0.46 (2765805b9442)`

Marketplace/plugin loading and failure semantics were additionally verified
against:

`grok 1.0.50` (`c58f321264ba`)

The shared marketplace hook was also live-verified on Claude Code 2.1.287.
With the rebuilt `magpie-agent-guard` plugin installed from this checkout,
`git commit --no-verify --dry-run` was denied by
`agent-guard[no-verify]` before Git executed.

A real `PreToolUse` payload captured on 2026-10-08 is retained in
`tools/agent-guard/tests/test_grok.py`.
The capture was triggered by asking Grok to run `pwd`.
The captured event reported `toolName: "run_terminal_command"` and placed the
shell command in `toolInput.command`.

## Installation

### Marketplace plugin

Grok reads Claude-compatible marketplaces, plugins, and hooks without extra compatibility setup.
The `magpie-agent-guard` plugin registers its hook through `hooks/hooks.json`.
Its command resolves the bundled guard through
`${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}`.
The no-argument dispatcher selects the Grok adapter from the incoming
camelCase `toolName` / `toolInput` payload shape rather than from environment
variables.

The guard runtime is materialized as real files inside the plugin rather than
through an out-of-root symlink, because Grok's local plugin installation does
not preserve that symlink target.

### Framework checkout

This repository enables `magpie-agent-guard` through `.claude/settings.json`,
which Grok also reads, so the Magpie checkout intentionally does not commit an
active `.grok/hooks/magpie-agent-guard.json`.
That avoids running the same guard twice.

Source-style adopters that do not use the marketplace plugin may install the
project-hook template from
`plugins/magpie-setup/templates/grok-agent-guard-hook.json`.
It resolves the guard through `GROK_WORKSPACE_ROOT` and invokes `--grok`.

### Pinned snapshot

A snapshot adopter may install the same single Magpie-owned project hook.
Its executable path points through
`$GROK_WORKSPACE_ROOT/.apache-magpie/tools/agent-guard/`.

Magpie owns only that exact hook file.
It does not own `.grok/hooks/`, `.grok/config.toml`, unrelated hooks, or project trust.

## Trust and security boundary

Project `.grok/hooks/` entries require an explicit Grok trust decision.
Magpie must never grant or reset that trust on the operator's behalf.

The action guard is separate from Grok permissions and from the operating-system sandbox.
It inspects shell commands before execution and rejects commands that violate a
hard Magpie framework rule.
It does not turn native file tools, MCP tools, or the rest of the process into a sandbox.

## Guard behavior

For a relevant `run_terminal_command` event, the adapter passes the command and
optional string `cwd` to the harness-neutral `dispatch()` core.

A denial emits a Grok deny decision containing the shared guard reason and exits
with the guard deny code.
An allowed shell command exits 0 without emitting a decision.

Malformed input, unrelated tools, or an invalid command field handled by the
adapter are ignored and fail open by returning exit 0.

Hook-process failure has different semantics. On Grok 1.0.50, a hook process
that exits 2 blocks the tool call even without deny JSON. A missing Python hook
target likewise produced exit 2 and blocked the shell call. Installation
verification should still exercise a known allow and a known denial rather than
treating configuration presence as sufficient.

## Verify

Use:

`grok inspect --json`

Confirm that the intended Magpie action-guard hook is active and that the
selected installation method has not introduced a duplicate project hook.

In the Magpie framework checkout, `grok inspect --json` should report the
enabled `magpie-agent-guard` plugin's `hooks/hooks.json` as the single active
Magpie action-guard hook; the checkout intentionally carries no active
`.grok/hooks/magpie-agent-guard.json`.

For a source or snapshot project hook, verify that its command resolves to an
existing `agent_guard/__init__.py`.
For a marketplace installation, verify that the installed
`magpie-agent-guard` plugin supplies the hook and that no duplicate project hook
was added merely to reach the executable.

Then perform harmless live probes:
one command that Magpie permits and one known guard denial.
A static configuration check does not replace the live denial probe.

## Update and uninstall

Marketplace installations follow the plugin manager lifecycle.
Updating the plugin updates its bundled guard implementation.

Source and snapshot installs compare only
`.grok/hooks/magpie-agent-guard.json` with the expected shape from
`plugins/magpie-setup/templates/grok-agent-guard-hook.json`.
A stock stale copy may be refreshed.
A hand-edited copy must be shown for review before replacement or removal.

Repository uninstall removes only the Magpie-owned project hook.
It does not uninstall a user's marketplace plugin and does not change Grok trust.

## Spec-loop runner

Grok Build 1.0.50 was live-verified as a headless spec-loop runtime.

The runner uses `--prompt-file` for the assembled prompt, `--cwd` for the
repository root, and `--always-approve` for unattended local edits inside the
external Magpie sandbox.
`SPEC_LOOP_OUTPUT_FORMAT=text` maps to Grok's `plain` output and
`stream-json` maps to `streaming-json`.
`SPEC_LOOP_MODEL` maps to `--model`, while `SPEC_LOOP_EFFORT` maps to
`--reasoning-effort low|medium|high`.

The runner also supplies explicit `--deny` rules for `git push` and `gh`.
On Grok Build 1.0.50 these exact rule shapes were live-verified to deny the
matching shell calls before execution even with `--always-approve`.

A disposable repository probe confirmed that the same profile can create a
local file headlessly while leaving unrelated tracked files unchanged.

## Known limitations

Grok spec-loop support relies on the same external OS sandbox required by the
other unattended harness profiles.
The per-invocation deny rules are defense in depth rather than a replacement
for that sandbox.

Malformed or unrelated input handled inside the adapter is deliberately
fail-open. Hook-process exit 2 is fail-closed on the Grok 1.0.50 runtime tested:
both a bare `exit 2` hook and a missing Python hook target blocked the shell
tool call.

Verification must still include a real denial probe so configuration,
packaging, and runtime behavior are checked together.

The captured payload contract comes from Grok Build 1.0.46.
Marketplace loading, bundled-runtime execution, policy denial, and exit-2
failure behavior were verified on Grok Build 1.0.50.
Future Grok hook-schema changes require a fresh runtime capture before changing
the adapter contract.

## Developer checks

`uv run --directory tools/agent-guard --group dev pytest`

`uv run --directory tools/agent-guard --group dev python -m ruff check src tests`

## Upstream references

- xAI Hooks: https://docs.x.ai/build/features/hooks
- xAI Skills, Plugins & Marketplaces: https://docs.x.ai/build/features/skills-plugins-marketplaces
- xAI Permissions: https://docs.x.ai/build/features/permissions
- xAI CLI Reference: https://docs.x.ai/build/cli/reference
