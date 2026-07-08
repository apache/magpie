<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Spec-loop runner
status: experimental
kind: feature
mode: infra
source: >
  tools/spec-loop/README.md, tools/spec-loop/loop.sh,
  tools/spec-loop/lib.sh, tools/spec-loop/tests/test_runner_fixtures.sh,
  tools/spec-loop/PROMPT_plan.md, tools/spec-loop/PROMPT_build.md,
  tools/spec-loop/PROMPT_update.md, tools/spec-loop/PROMPT_consolidate.md,
  and docs/spec-driven-development.md.
acceptance:
  - The loop supports plan, build, update, and consolidate beats with one
    fresh agent context per iteration.
  - Build and update beats never commit to the integration base; they create
    reviewable local branches and stop before push or PR creation.
  - Open PRs and local work-item branches are passed into plan/build prompts
    as in-flight work so the loop does not duplicate already-built items.
  - The headless-agent harness contract is explicit for Claude Code, Codex,
    Cursor, Gemini CLI, OpenCode, and Kiro.
  - The update marker `tools/spec-loop/.last-sync` is owned by the runner,
    not by the prompt.
---

# Spec-loop runner

## What it does

The spec-loop runner is the framework's local, review-first development
loop. It runs a headless agent CLI against fixed prompts, one iteration at
a time, to compare specs with the working tree, produce planned changes,
back-fill specs after normal contributions, or consolidate a long
implementation plan.

The loop is not an autonomous merge system. Its boundary is local branch
creation: it may edit, validate, and commit locally, but it never pushes
and never opens a pull request.

## Where it lives

- `tools/spec-loop/loop.sh` — Bash runner for the four beats.
- `tools/spec-loop/lib.sh` — deterministic prompt assembly, harness
  command rendering, agent launch, and `.last-sync` marker helpers used
  by the runner and fixture tests.
- `tools/spec-loop/tests/test_runner_fixtures.sh` — deterministic
  fixture tests for prompt assembly, harness command construction, and
  `.last-sync` marker helpers; executed by `spec-validate`.
- `tools/spec-loop/PROMPT_plan.md` — gap-analysis prompt that rewrites
  `IMPLEMENTATION_PLAN.md`.
- `tools/spec-loop/PROMPT_build.md` — implementation prompt for exactly
  one work item.
- `tools/spec-loop/PROMPT_update.md` — spec back-fill prompt for
  functionality that landed outside the loop.
- `tools/spec-loop/PROMPT_consolidate.md` — plan-size reduction prompt.
- `tools/spec-loop/AGENTS.md` — loop-specific operational context:
  repository map, validation commands, branch rules, hard limits, and
  commit rules.
- `tools/spec-loop/README.md` — operator quickstart.
- `docs/spec-driven-development.md` — full explanation of the loop's
  posture and lifecycle.

## Behaviour & contract

- **Four beats, one mechanism.** `plan` compares specs to code and updates
  the implementation plan without committing. `build` implements one
  uncovered work item. `update` compares code to specs and back-fills the
  spec directory. `consolidate` shrinks the implementation plan without
  dropping planned work.
- **One work item, one branch, one PR.** Build work creates a bare
  `<slug>` branch off `SPEC_LOOP_BASE` and commits exactly one work item
  there. Update work creates a uniquely named `sync-specs-<timestamp>`
  branch. Consolidate commits only the plan file on the control branch.
- **No remote state changes.** The runner and prompts forbid `git push`
  and `gh pr create`; each successful build/update beat prints the
  human-run push and `gh pr create --web` commands instead.
- **In-flight duplicate guard.** Before each relevant iteration, the
  runner appends open PR context and local work-item branch context to the
  prompt. Plan/build treat both as in-flight work. This matters because a
  loop-built branch may be local-only and invisible to GitHub.
- **Control branch vs integration base.** `TOOLING_REF` is captured before
  checkout. When the integration base does not carry the spec-loop files,
  the runner tells the agent to read prompts/specs/plan from the control
  branch with `git show`, while implementing product changes on the work
  branch.
- **Update marker ownership.** `tools/spec-loop/.last-sync` records the
  base SHA last synced by the update beat. The runner reads it to append
  incremental-scope guidance, then amends or creates a marker commit after
  the agent finishes. Prompts must not instruct the agent to edit the
  marker.
- **Plan-size hysteresis.** Build mode switches to one consolidate pass
  when `IMPLEMENTATION_PLAN.md` exceeds `SPEC_LOOP_PLAN_MAX`, then builds
  even if planned work alone keeps the file over the threshold. The latch
  resets once the plan drops below the threshold.

## Headless harness contract

Every supported harness must provide the same loop-level behaviour: run
one non-interactive agent iteration in the repository root, receive the
assembled prompt, allow local edits/validation/commits under the external
sandbox, and stop without pushing or opening a PR.

| Harness | Prompt transport | Cwd contract | Unattended flag | Model override | Output mode | Extra denial |
|---|---|---|---|---|---|---|
| Claude Code | stdin to `claude -p` | launched from repo root | `--dangerously-skip-permissions` | `--model` | `--output-format` | `--disallowedTools` denies push and `gh` |
| Codex | stdin to `codex exec -` | `--cd "$ROOT"` | `--dangerously-bypass-approvals-and-sandbox` | `--model` | `--json` for stream JSON | external sandbox and exec policy |
| Cursor | positional prompt to `cursor agent --print` or `cursor-agent --print` | `--workspace "$ROOT"` | `--force --trust` | `--model` | `--output-format` | external sandbox and Cursor policy |
| Gemini CLI | `--prompt "<prompt>"` | launched from repo root | `--yolo` | `--model` | default CLI output | external sandbox and Gemini policy |
| OpenCode | positional prompt to `opencode run` | launched from repo root | `--auto` | `--model` | `--format json` for stream JSON | external sandbox and OpenCode policy |
| Kiro | positional prompt to `kiro-cli chat` | launched from repo root | `--no-interactive` | agent config (`.kiro/agents`) | plain text only | external sandbox and the agent-guard `--kiro` hook |

`SPEC_LOOP_AGENT` chooses the CLI. `SPEC_LOOP_HARNESS` chooses the
invocation convention and defaults from the agent basename. Adding a new
harness means extending this matrix, documenting the safety boundary, and
updating `loop.sh` in the same change.

## Out of scope

- Auto-pushing, auto-opening PRs, auto-merging, or changing remote state.
- Replacing the project sandbox or adding new filesystem/network
  permissions.
- Teaching individual skills how to do their domain work; those contracts
  live in the corresponding functional specs.
- Editing `docs/rfcs/`; RFCs remain the separate governance layer.

## Acceptance criteria

1. `loop.sh` accepts `plan`, `build`, `update`, and `consolidate`, plus a
   bare numeric build count, and rejects unknown modes or non-numeric
   iteration counts.
2. Build/update iterations check out `SPEC_LOOP_BASE`, create a non-base
   branch, and stop if a commit lands on the base.
3. Plan/build prompts receive both open PR context and local work-item
   branch context.
4. Update prompts receive incremental-scope guidance from `.last-sync`
   when present, but the runner remains the only writer of `.last-sync`.
5. Claude Code, Codex, Cursor, Gemini CLI, OpenCode, and Kiro are documented in
   the headless harness matrix and implemented in `loop.sh`.
6. Operator docs and prompts agree on branch naming: build uses bare
   `<slug>` branches; update uses `sync-specs-<timestamp>` branches.
7. Security docs describe unattended agent flags as harness-specific
   agent-level bypasses that must run under the external sandbox.

## Validation

```bash
bash -n tools/spec-loop/loop.sh
shellcheck tools/spec-loop/loop.sh
shellcheck tools/spec-loop/lib.sh tools/spec-loop/tests/test_runner_fixtures.sh
uv run --project tools/spec-validator --group dev spec-validate
```

## Known gaps

- The non-Claude harnesses rely on external policy/config plus the OS
  sandbox for push/PR denial; only Claude has a per-invocation hard-deny
  flag in the current runner.
- The update beat's incremental-scope mapping is path-based; it does not
  yet map changed files to likely spec topics with a deterministic helper.
