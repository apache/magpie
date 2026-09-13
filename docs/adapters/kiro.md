<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Kiro CLI harness](#kiro-cli-harness)
  - [Harness contract](#harness-contract)
  - [Installing skills](#installing-skills)
  - [Deterministic guard rules](#deterministic-guard-rules)
  - [Spec-loop runner](#spec-loop-runner)
  - [Clean-environment wrapper](#clean-environment-wrapper)
  - [Verify](#verify)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Kiro CLI harness

**Capability:** capability:platform

**Harness:** Kiro CLI

Kiro uses Magpie's skill sources, deterministic action guard, spec-loop runner,
and clean-environment wrapper. As everywhere else, nothing about a Magpie skill
or a guard rule is Kiro-aware: the same files serve it through a different
registration mechanism.

Kiro is the one supported harness with **no marketplace**. It installs skills
per-skill from a GitHub subdirectory rather than consuming a repository root,
which changes how Magpie arrives and nothing about how it behaves once there.

## Harness contract

| Magpie requirement | Kiro implementation |
|---|---|
| Skill discovery | Native, from `.kiro/skills/`, which the `kiro` row in [`agents.md`](../../skills/setup/agents.md) writes as a relay into the canonical `.agents/skills/` tree. Kiro also installs a skill directly from a GitHub subdirectory on a pinned tag. |
| Deterministic guard | The `preToolUse` hook. Kiro pipes the event to the hook command and **blocks** the call when it exits `2`, returning stderr to the model — the Kiro equivalent of a Claude Code `PreToolUse` deny. |
| Spec-loop | The `kiro` profile passes the prompt positionally to `kiro-cli chat`, with `--no-interactive`. |
| Credential isolation | `kiro-iso` launches the CLI through the clean-environment wrapper. |

## Installing skills

There is no marketplace to add. Point Kiro's *install from GitHub* at the
subdirectory of the skill you want, on a pinned tag:

```text
https://github.com/apache/magpie/tree/0.2.0/skills/release-vote-tally
```

Kiro reads the `skills/<name>/SKILL.md` there. Pin a tag rather than tracking
`main`: without a marketplace there is no update command to run later, so the
version you install is the version you keep until you install again.

That per-skill shape is why Kiro is absent from the family-plugin story. A
family plugin is a bundle, and Kiro does not consume bundles — you take the
skills you want, one at a time.

## Deterministic guard rules

`agent-guard.py --kiro` matches the shell tool, runs the shared `dispatch()`
core, and on a deny writes the reason to stderr and exits `2`. Register it in
the agent configuration's `hooks` field; the full recipe, including the event
shape Kiro sends, is in the
[agent-guard Kiro recipe](../../tools/agent-guard/README.md#kiro-cli).

Because Kiro calls the same core as every other harness, the bundled and
skill-contributed guards, the `MAGPIE_*` overrides, and the deny reasons are
byte-for-byte identical to Claude Code's.

## Spec-loop runner

```bash
SPEC_LOOP_AGENT=kiro tools/spec-loop/loop.sh <spec>
```

Two Kiro-specific details the runner handles: the model is selected through the
agent configuration under `.kiro/agents` rather than a `--model` flag, and the
output is plain text only — there is no structured mode to ask for. Its
reasoning-effort scale runs to `xhigh` and `max`; the runner maps the neutral
`low`/`medium`/`high` band onto `--effort`.

## Clean-environment wrapper

```bash
source /path/to/magpie/tools/agent-isolation/agent-iso.sh
kiro-iso
```

The `kiro` name normalises to the `kiro-cli` binary. Like OpenCode and unlike
Claude Code, it takes no `--settings` filesystem grant: Kiro gets its
filesystem isolation from the OS-level sandbox.

## Verify

```bash
uv run --directory tools/agent-guard --project . python -m pytest
bash tools/spec-loop/tests/test_runner_fixtures.sh
```

The guard tests cover the Kiro path end-to-end — the `--kiro` event parsing,
the exit-`2`-plus-stderr deny protocol, and that a decision from the shared
core survives unchanged. The runner fixtures verify the positional prompt and
the `--no-interactive` flag.

To verify in a live session, ask Kiro to run `git status --short`; it should
pass the guard. For a harmless denial probe, ask it to run
`git commit --dry-run --no-verify -m hook-probe` — the expected result is an
`agent-guard[no-verify]` denial before Git starts. The `--dry-run` flag
prevents the probe from creating a commit even if the hook is not registered.
