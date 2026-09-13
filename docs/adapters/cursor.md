<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Cursor runtime (Composer + Agent CLI)](#cursor-runtime-composer--agent-cli)
  - [Harness contract](#harness-contract)
  - [Invoke a Magpie skill](#invoke-a-magpie-skill)
    - [Inside Cursor Composer (IDE)](#inside-cursor-composer-ide)
    - [Headless or CLI invocation (`cursor-agent`)](#headless-or-cli-invocation-cursor-agent)
  - [Human-in-the-loop and Auto-Run controls](#human-in-the-loop-and-auto-run-controls)
  - [Deterministic guard rules and tool bridges](#deterministic-guard-rules-and-tool-bridges)
  - [Spec-loop runner](#spec-loop-runner)
  - [Clean-environment wrapper](#clean-environment-wrapper)
  - [Verify](#verify)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Cursor runtime (Composer + Agent CLI)

**Capability:** capability:platform

**Harness:** Cursor (Composer + Agent CLI)

Cursor provides interactive and headless agent capabilities via Cursor Composer in the IDE and the `cursor-agent` CLI.
This guide documents how Cursor operates as a first-class Apache Magpie skill runtime for [#316](https://github.com/apache/magpie/issues/316).

Cursor integrates with Magpie without requiring custom skill copies, translation passes, or proprietary prompt wrappers.
The integration follows [RFC-AI-0004 Principle 3 (Vendor Neutrality)](../rfcs/RFC-AI-0004.md) and [Adding a new agent harness](add-a-harness.md).

## Harness contract

| Magpie requirement | Cursor implementation |
|---|---|
| Skill discovery | Cursor reads the canonical `.agents/skills/magpie-*/SKILL.md` symlinks directly. The existing `universal` row in `skills/setup/agents.md` covers this path. |
| Repository instructions | Cursor ingests repository instructions from `AGENTS.md` and project rules from `.cursor/rules/` or `.cursorrules`. |
| Human-in-the-loop (HITL) | Cursor Composer enforces per-action approval modals for file edits and terminal commands. Auto-Run permissions map directly to Magpie's proposal-then-confirm discipline. |
| Tool bridges | Skills invoke the standard `tools/*` CLI adapters. Network access for authenticated operations respects the project isolation policy. |
| Model and MCP bridges | Cursor's MCP support connects to framework MCP servers (PonyMail, Gmail, ASF project metadata). |
| Spec-loop | The `cursor` profile forwards `--workspace`, `--print`, `--force`, and `--trust` flags for automated non-interactive runs. |
| Credential isolation | `agent-iso` launches Cursor or `cursor-agent` through the shared clean-environment wrapper, stripping unapproved ambient tokens. |

## Invoke a Magpie skill

After running `/magpie-setup` to adopt the repository, the canonical `.agents/skills/` links are active in your working tree.
Cursor scans `.agents/skills/` and discovers all available Magpie workflows.

### Inside Cursor Composer (IDE)

1. Open the adopted project folder in Cursor.
2. Open Cursor Composer (`Ctrl+I` / `Cmd+I` or `Ctrl+Shift+J` / `Cmd+Shift+J`).
3. Mention or reference a skill, for example:
   > Use the `magpie-security-issue-triage` skill to triage the latest reports.
4. Composer resolves the referenced `SKILL.md` workflow, checks prerequisites, and presents a proposed plan before executing state mutations.

### Headless or CLI invocation (`cursor-agent`)

For non-interactive triage sweeps, automated spec-loops, or terminal sessions:

```bash
# Interactive terminal session with filtered environment
agent-iso cursor-agent

# Run a specific Magpie workflow headlessly
cursor-agent --print --workspace /path/to/repo "Run the magpie-list-skills skill and print the summary."
```

## Human-in-the-loop and Auto-Run controls

Magpie enforces strict [Human-in-the-Loop principles](../rfcs/RFC-AI-0004.md): no state mutation (closing issues, writing files, dispatching emails, pushing branches) occurs without explicit human approval.

In Cursor:
- **Default mode**: Every terminal command and write action requires an explicit **Approve** or **Run** click in the Composer UI.
- **Auto-Run allowlist**: If you configure Auto-Run rules in Cursor settings, restrict allowlists strictly to read-only diagnostic commands (such as `git status`, `uv run pytest`, `gh issue list`).
- **Never auto-approve destructive commands**: Commands that mutate remote trackers (`gh issue close`, `git push`, `gh pr create`) must always require human confirmation.

## Deterministic guard rules and tool bridges

Cursor runs tool commands through standard subshells in your project environment.
Deterministic tool scripts under `tools/` (e.g. `tools/cve-tool-vulnogram/`, `tools/github/`, `tools/privacy-llm/`) execute with standard Python / Groovy runtimes.

When running in environments where `agent-guard` is enabled:
- The command dispatcher checks shell calls before execution.
- Any attempt to bypass git verification flags (such as `--no-verify`) or push to protected branches is rejected deterministically.

## Spec-loop runner

The `cursor` profile in [`tools/spec-loop/lib.sh`](../../tools/spec-loop/lib.sh) invokes the CLI headlessly:

```bash
cursor agent --print --force --trust --workspace "$root" "<prompt>"
# or via the standalone CLI
cursor-agent --print --force --trust --workspace "$root" "<prompt>"
```

Cursor does not provide a per-invocation reasoning-effort flag, so the runner omits reasoning-level parameters.
See the [spec-loop guide](../../tools/spec-loop/README.md) for full options.

## Clean-environment wrapper

To isolate sensitive tokens and run Cursor under the standard Magpie credential policy:

```bash
source <framework>/tools/agent-isolation/agent-iso.sh
agent-iso cursor .
```

The `agent-iso` launcher scrubs undeclared environment variables while preserving local developer toolchains (`git`, `uv`, `gh`).

## Verify

Verify that the Cursor runtime wiring conforms to the framework standards:

```bash
# 1. Verify skill discovery topology
$env:PYTHONUTF8=1; uv run --project tools/symlink-lint symlink-lint

# 2. Validate skill and tool metadata
$env:PYTHONUTF8=1; uv run --project tools/skill-and-tool-validator skill-and-tool-validate

# 3. Check vendor neutrality score
$env:PYTHONUTF8=1; uv run --project tools/vendor-neutrality-score vendor-neutrality-score

# 4. Run pre-commit formatting and link verification
uv run prek run doctoc --all-files
```

## See also

- [`docs/adapters/add-a-harness.md`](add-a-harness.md) — recipe for adding runtime harnesses.
- [`skills/setup/agents.md`](../../skills/setup/agents.md) — agent-target registry (`universal` canonical path).
- [`docs/rfcs/RFC-AI-0004.md`](../rfcs/RFC-AI-0004.md) — normative principles for vendor neutrality and HITL.
- [`docs/vendor-neutrality.md`](../vendor-neutrality.md) — framework vendor neutrality index.
