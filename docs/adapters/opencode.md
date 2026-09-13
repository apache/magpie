<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [OpenCode harness](#opencode-harness)
  - [Harness contract](#harness-contract)
  - [Deterministic guard rules](#deterministic-guard-rules)
  - [Spec-loop runner](#spec-loop-runner)
  - [Clean-environment wrapper](#clean-environment-wrapper)
  - [Verify](#verify)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# OpenCode harness

**Capability:** capability:platform

**Harness:** OpenCode

OpenCode uses Magpie's skill sources, deterministic action guard, spec-loop
runner, and clean-environment wrapper. Nothing about a Magpie skill or a guard
rule is harness-aware: the same files that serve Claude Code serve OpenCode,
through a different registration mechanism.

## Harness contract

| Magpie requirement | OpenCode implementation |
|---|---|
| Skill discovery | OpenCode is part of the cluster that converged on `.agents/skills/`, which is the canonical target the `universal` row in [`agents.md`](../../skills/setup/agents.md) already writes. It also reads native Agent Skills from `.opencode/skills/` (project) or `~/.opencode/skills/` (personal). |
| Deterministic guard | A [plugin](https://opencode.ai/docs/plugins/) on `tool.execute.before` forwards each `bash` command to `agent-guard.py --opencode` and throws the deny reason, which aborts the tool call. |
| Spec-loop | The `opencode` profile passes the prompt positionally to `opencode run`, with `--auto`, `--model`, and `--format json`. |
| Credential isolation | `opencode-iso` launches the CLI through the clean-environment wrapper. |

## Deterministic guard rules

OpenCode aborts a tool call whose `tool.execute.before` handler throws, which
is the OpenCode equivalent of a Claude Code `PreToolUse` deny. The plugin in
[`tools/agent-guard/opencode/plugin.js`](../../tools/agent-guard/opencode/plugin.js)
forwards each `bash` command to the shared `dispatch()` core and throws with
the reason the core returns.

Register it by dropping the plugin into OpenCode's plugin directory:

```bash
mkdir -p .opencode/plugin
ln -s "<framework>/tools/agent-guard/opencode/plugin.js" .opencode/plugin/agent-guard.js
```

The plugin locates the engine at `.claude/hooks/agent-guard.py` under the
worktree by default, so a repository already wired for Claude Code needs no
second copy of the script, and honours
`MAGPIE_AGENT_GUARD=/abs/path/agent-guard.py` to point elsewhere.

Because both harnesses call the same `dispatch()`, the bundled and
skill-contributed guards, the `MAGPIE_*` overrides, and the deny reasons are
byte-for-byte identical across the two. Full wiring notes are in the
[agent-guard OpenCode recipe](../../tools/agent-guard/README.md#opencode).

## Spec-loop runner

The `opencode` profile in [`tools/spec-loop/lib.sh`](../../tools/spec-loop/lib.sh)
runs `opencode run --auto --model … "<prompt>"` from the repository root and
asks for stream JSON with `--format json`. Setting `SPEC_LOOP_AGENT=opencode`
is normally the whole configuration:

```bash
SPEC_LOOP_AGENT=opencode SPEC_LOOP_MODEL=anthropic/claude-sonnet-4-5 \
  tools/spec-loop/loop.sh <spec>
```

OpenCode is the one harness whose reasoning-effort band is not an identity
mapping: the runner translates the neutral `low` / `medium` / `high` to
`--variant minimal` / `medium` / `max`. See the
[spec-loop guide](../../tools/spec-loop/README.md).

## Clean-environment wrapper

```bash
source /path/to/magpie/tools/agent-isolation/agent-iso.sh
opencode-iso
```

`opencode-iso` applies the same `env -i` credential strip as `claude-iso`, and
adds no settings grant: OpenCode takes its filesystem isolation from the
OS-level sandbox rather than from a per-launch allowlist. Network restrictions
and tool approval are separate controls, described in the
[secure-agent setup](../setup/secure-agent-setup.md).

## Verify

```bash
uv run --directory tools/agent-guard --project . python -m pytest
bash tools/spec-loop/tests/test_runner_fixtures.sh
```

The guard tests cover the OpenCode path end-to-end — the plugin's command
routing, the throw-on-deny contract, and that a decision made by the shared
core is preserved unchanged. The runner fixtures verify the positional prompt,
the `--auto` flag, and the effort-band translation, including the `low` →
`minimal` mapping that is unique to this harness.

To verify in a live session, start OpenCode from the checkout root and ask it
to run `git status --short`; it should pass the guard. For a harmless denial
probe, ask it to run `git commit --dry-run --no-verify -m hook-probe` — the
expected result is an `agent-guard[no-verify]` denial before Git starts. The
`--dry-run` flag prevents the probe from creating a commit even if the plugin
is not registered.
