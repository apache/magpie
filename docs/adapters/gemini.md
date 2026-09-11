<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gemini CLI runtime](#gemini-cli-runtime)
  - [Runtime contract](#runtime-contract)
  - [Invoke a Magpie skill](#invoke-a-magpie-skill)
  - [Deterministic guard rules](#deterministic-guard-rules)
  - [Spec-loop runner](#spec-loop-runner)
  - [Clean-environment wrapper](#clean-environment-wrapper)
  - [Verify](#verify)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gemini CLI runtime

**Capability:** capability:platform

**Harness:** Gemini CLI

Gemini CLI uses Magpie's skill sources, repository instructions, action guard,
and spec-loop runner.
This guide documents those integrations for
[#314](https://github.com/apache/magpie/issues/314).
The CLI checks described here used Gemini CLI **0.59.0** on Linux.

## Runtime contract

| Magpie requirement | Gemini CLI implementation |
|---|---|
| Skill discovery | Gemini reads the canonical `.agents/skills/magpie-*/SKILL.md` links. The existing `universal` row in `skills/setup/agents.md` covers this path. |
| Repository instructions | The framework's `GEMINI.md` imports its `AGENTS.md`. |
| Deterministic guard | Project `.gemini/settings.json` wires `agent_guard/__init__.py --gemini` to `BeforeTool` shell events, which call the harness-neutral `dispatch()` core. Snapshot adopters register the hook using the recipe below. |
| Spec-loop | The `gemini` profile forwards the prompt, model, and output format. |
| Credential isolation | `agent-iso gemini` launches the CLI through the generic clean-environment wrapper, which filters inherited environment variables. |

The integration follows [add-a-harness](add-a-harness.md):
Gemini uses the existing skill registry and runner profile, with a thin
guard adapter and matching harness declarations.

## Invoke a Magpie skill

After [setup](../../skills/setup/SKILL.md) creates the canonical links,
Gemini discovers the same skill sources used by the other runtimes.
The framework also provides `gemini-extension.json` for extension installation,
with the workflows under `skills/` and context in `GEMINI.md`.

Gemini's [skill discovery](https://geminicli.com/docs/cli/using-agent-skills/)
supports `.agents/skills/`.
No skill conversion or separate Gemini copy is required.
The framework's `GEMINI.md` uses a
[context import](https://geminicli.com/docs/cli/gemini-md/) to load `AGENTS.md`.
Adopters retain their own project instructions alongside the framework context.

From the adopter repository root:

1. Start Gemini with `gemini --approval-mode default`.
2. Use `/memory show` to inspect the effective repository instructions.
3. Use `/skills list` to see the available skills.
4. Ask `Use the magpie-list-skills skill.` and review the activation request.

Skills use the framework's existing `tools/*` adapters.
Each tool's README declares its runtime, authentication, and network prerequisites.
Skill activation consent is separate from approval to execute a tool.

## Deterministic guard rules

The repository's [`.gemini/settings.json`](../../.gemini/settings.json) wires the
`magpie-agent-guard` hook for `run_shell_command`.
Start Gemini from the checkout root; the command resolves the engine through
`GEMINI_PROJECT_DIR`, so it works without a machine-specific path.

Snapshot adopters register the hook in their own settings using the
[agent-guard Gemini recipe](../../tools/agent-guard/README.md#gemini-cli).
The repository's settings are not loaded from inside an adopter's
`.apache-magpie/` snapshot, and `/magpie-setup` does not yet install Gemini hooks.

The adapter:

1. Reads the `BeforeTool` event from stdin.
2. Matches `run_shell_command` and passes `tool_input.command` and `cwd`
   to `dispatch()`.
3. Returns exit `2` with the denial reason on stderr when a guard denies the call.
4. Returns exit `0` silently for permitted commands and malformed or non-shell events.

The adapter follows the existing guard's fail-open contract.
It covers shell calls; native file and MCP tools use Gemini's own permissions.
Project-hook execution depends on the workspace's
[trust state](https://geminicli.com/docs/cli/trusted-folders/).

## Spec-loop runner

The existing `gemini` profile in
[`tools/spec-loop/lib.sh`](../../tools/spec-loop/lib.sh) invokes the CLI with
`--yolo`, `--prompt`, and `--output-format`.
It forwards `--model` when one is supplied.
Gemini has no per-invocation effort flag in the inspected CLI, so the runner
omits that option.

The runner uses automatic approval for headless execution.
See the [spec-loop guide](../../tools/spec-loop/README.md) for its operating
environment and invocation options.

## Clean-environment wrapper

The generic [agent-isolation wrapper](../../tools/agent-isolation/README.md)
supports Gemini:

```bash
source /path/to/magpie/tools/agent-isolation/agent-iso.sh
agent-iso gemini --approval-mode default
```

The wrapper filters inherited environment variables before launching the CLI.
Filesystem sandboxing, network restrictions, and tool approval are separate
controls described in the [secure-agent setup](../setup/secure-agent-setup.md).

## Verify

The following checks cover the implemented wiring:

```bash
uv run --project tools/symlink-lint symlink-lint
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --directory tools/agent-guard --project . python -m pytest
bash tools/spec-loop/tests/test_runner_fixtures.sh
bash -n tools/spec-loop/loop.sh
bash -n tools/spec-loop/lib.sh
```

With an isolated user configuration and a trusted framework checkout,
`gemini skills list` discovered 75 Magpie skills.

An offline probe of Gemini 0.59.0's settings loader, hook registry, and native
hook runner loaded the project settings and registered `magpie-agent-guard`.
It recognized the adapter's exit `2` and `no-verify` denial, and accepted a
`git status --short` hook event silently, including from a checkout path
containing spaces.
Only the hook dispatcher ran; neither guarded command was executed.

The adapter tests cover command-line routing, the exit-code and stderr
protocol, preservation of core decisions, workspace-aware Git checks,
and malformed or non-shell input. They also execute the hook command from
the project settings, including a checkout path containing spaces.
The runner fixtures verify prompt, model, and output-format forwarding.

To verify the registration in a live session, start Gemini at the framework
checkout root with `gemini --approval-mode default`, review the project trust
prompt if shown, and open `/hooks panel`.
Confirm that `magpie-agent-guard` is enabled for `BeforeTool`.
Ask Gemini to run `git status --short`; it should pass the guard.
For a harmless denial probe, ask it to run
`git commit --dry-run --no-verify -m hook-probe`.
The expected result is an `agent-guard[no-verify]` denial before Git starts.
If Git instead reports its dry-run status, the guard did not block the call.
The `--dry-run` flag prevents this probe from creating a commit even if the
hook is missing.
