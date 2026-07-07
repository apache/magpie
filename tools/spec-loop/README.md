<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# spec-loop

**Capability:** substrate:framework-dev

**Harness:** Claude Code, Codex, Cursor, Gemini CLI, OpenCode, Kiro

A spec-driven build loop for this framework, in the general
[Ralph](https://ghuntley.com/ralph/) style (run a fresh agent context
against a fixed prompt, repeat), adapted to the framework's
human-in-the-loop posture. The full write-up is in
[`docs/spec-driven-development.md`](../../docs/spec-driven-development.md);
this is the operator quickstart.

The loop drives a **headless agent CLI** and is not tied to one harness.
`SPEC_LOOP_AGENT` picks the CLI (default `claude`) and `SPEC_LOOP_HARNESS`
picks its run convention:

- `claude` — `claude -p --dangerously-skip-permissions --output-format …`,
  prompt on stdin.
- `codex` — `codex exec --dangerously-bypass-approvals-and-sandbox -`,
  prompt on stdin.
- `cursor` — `cursor agent --print --force --trust --workspace … "<prompt>"`
  or `cursor-agent --print --force --trust --workspace … "<prompt>"`.
- `gemini` — `gemini --yolo --prompt "<prompt>"`.
- `opencode` — `opencode run --auto --model … "<prompt>"`, prompt as a
  positional argument.

`SPEC_LOOP_HARNESS` defaults from the agent basename, so
`SPEC_LOOP_AGENT=codex`, `SPEC_LOOP_AGENT=cursor-agent`,
`SPEC_LOOP_AGENT=gemini`, or `SPEC_LOOP_AGENT=opencode` is usually all that
is needed:

```bash
SPEC_LOOP_AGENT=codex tools/spec-loop/loop.sh build 5
```

```bash
SPEC_LOOP_AGENT=cursor-agent tools/spec-loop/loop.sh build 5
```

```bash
SPEC_LOOP_AGENT=gemini tools/spec-loop/loop.sh build 5
```

```bash
SPEC_LOOP_AGENT=opencode SPEC_LOOP_MODEL=anthropic/claude-sonnet-4-5 \
  tools/spec-loop/loop.sh build 5
```

All conventions run the agent non-interactively with permissions
auto-approved; the loop's safety rails (never push, never open a PR) come from
the OS sandbox, missing push/write credentials, repo hooks, and the loop's own
guards. Claude also gets per-invocation `--disallowedTools` hard-deny flags;
the other harnesses rely on their own policy/config plus the external sandbox.
See the SECURITY notes in [`loop.sh`](loop.sh).

## Prerequisites

- **Runtime:** Bash + coreutils (`loop.sh` is the runner); the
  spec-side helper tools it drives are Python 3.11+ run via `uv`.
- **CLIs:** `git` (required — must run inside a git checkout), `gh`
  (for open-PR duplicate-work checks), and one supported headless agent
  CLI (`SPEC_LOOP_AGENT`, default `claude`; also supports `codex`,
  `cursor` / `cursor-agent`, `gemini`, and `opencode`).
- **Credentials / auth:** `gh` must be authenticated for the PR checks;
  the loop is designed to run with **no** push/write credentials in the
  environment (it hard-denies `git push` and `gh` writes).
- **Network:** Reaches GitHub (via `gh`) and the agent/model backend; the
  agent itself performs the model calls.

## The pieces

| File | Role |
|---|---|
| [`specs/`](specs/) | The functional description of the product — one spec per area. The desired state the loop reconciles code against. |
| [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | Prioritised **work items** (the gaps). One work item = one branch = one PR. |
| [`AGENTS.md`](AGENTS.md) | Loop-scoped operational rules (repo map, validation commands, branch + hard-limit rules). |
| `PROMPT_plan.md` / `PROMPT_build.md` / `PROMPT_update.md` / `PROMPT_consolidate.md` | The per-beat prompts. |
| `loop.sh` | The runner. |
| `../spec-inventory/` | Deterministic compact inventory helper appended to prompts as a routing aid. |

## Modes

```bash
./tools/spec-loop/loop.sh              # build, unlimited iterations
./tools/spec-loop/loop.sh 10           # build, max 10 iterations
./tools/spec-loop/loop.sh plan         # gap-analysis → rewrite the plan (no code changes; 1 pass, add N for more)
./tools/spec-loop/loop.sh update       # back-fill specs from functionality others contributed (1 pass, add N for more)
./tools/spec-loop/loop.sh consolidate  # shrink the plan when it grows too long (1 pass, add N for more)
```

- **plan** — compares `specs/` against the code and rewrites
  `IMPLEMENTATION_PLAN.md`. Plans only; no commits. It also checks open
  PRs and does not add work items that are already in flight.
- **build** — implements the single highest-priority work item on its own
  `<slug>` branch, validates, and commits there. If the top plan
  item is already covered by an open PR, it skips to the next uncovered
  item.
- **update** — the inverse of plan: scans the code for functionality not
  yet described by a spec (someone contributed it the normal way) and
  brings the specs back in sync, on a `sync-specs-<timestamp>` branch.
- **consolidate** — shrinks the plan without losing planned work (build
  auto-switches to this when the plan grows past ~500 lines).

## The two non-negotiables

- **A branch per work item.** Build/update never commit to the
  integration base; each carves out its own branch, so every change is
  one reviewable, revertible PR.
- **Never pushes, never opens a PR.** `git push` and `gh pr create` are in
  `.claude/settings.json` `ask` — the human's step. Each beat ends at a
  local commit and prints the exact push + `gh pr create --web` commands.

## Security

The loop runs the agent with `--dangerously-skip-permissions`, so it
**must** be launched inside the project's sandbox harness, with no
push/write credentials in the environment. The flag bypasses the agent
permission layer (`.claude/settings.json` deny/ask) but **not** the OS
sandbox (clean-env + filesystem/network), which stays the real boundary;
for Claude, as defence in depth, the loop also hard-denies `git push` and
`gh` via `--disallowedTools`. Full rationale:
[`docs/spec-driven-development.md` § Security and unattended agent loops](../../docs/spec-driven-development.md#security-and-unattended-agent-loops).

## Stop / configure

- Stop: `Ctrl+C`, or `touch STOP` (exits after the current iteration).
- `SPEC_LOOP_BASE` — branch to fork work items from. Defaults to `main`;
  set it explicitly to build on top of a different branch.
- `SPEC_LOOP_AGENT` — supported headless agent CLI or wrapper to run
  (default `claude`; `codex`, `cursor`, `gemini`, and `opencode` are
  first-class harnesses).
- `SPEC_LOOP_HARNESS` — override the invocation convention when the CLI
  name does not imply it (`claude`, `codex`, `cursor`, `gemini`, or
  `opencode`).
- `SPEC_LOOP_MODEL` — model passed to the agent CLI. Defaults to `sonnet`
  for Claude; Codex/Cursor/Gemini/OpenCode use their configured default
  unless this is set.
- `SPEC_LOOP_PR_LIMIT` — number of open PRs to include in duplicate-work
  checks (default `100`).
- `SPEC_LOOP_PLAN_MAX` — plan line count that triggers one consolidation
  round before building (default `500`). The consolidate beat targets
  ~300 lines (hysteresis) and runs at most once until the plan drops back
  under the limit, so a plan that is long because of *pending work* never
  re-consolidates in a loop.

## Not the RFCs

The specs are the *functional description of the code*. The
[`docs/rfcs/`](../../docs/rfcs/) are the separate normative governance
layer — the loop respects them as constraints and never reads or edits
them.
