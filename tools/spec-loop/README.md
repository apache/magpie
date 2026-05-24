<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# spec-loop

A spec-driven build loop for this framework, in the general
[Ralph](https://ghuntley.com/ralph/) style (run a fresh agent context
against a fixed prompt, repeat), adapted to the framework's
human-in-the-loop posture. The full write-up is in
[`docs/spec-driven-development.md`](../../docs/spec-driven-development.md);
this is the operator quickstart.

## The pieces

| File | Role |
|---|---|
| [`specs/`](specs/) | The functional description of the product — one spec per area. The desired state the loop reconciles code against. |
| [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) | Prioritised **work items** (the gaps). One work item = one branch = one PR. |
| [`AGENTS.md`](AGENTS.md) | Loop-scoped operational rules (repo map, validation commands, branch + hard-limit rules). |
| `PROMPT_plan.md` / `PROMPT_build.md` / `PROMPT_update.md` / `PROMPT_consolidate.md` | The per-beat prompts. |
| `loop.sh` | The runner. |

## Modes

```bash
./tools/spec-loop/loop.sh              # build, unlimited iterations
./tools/spec-loop/loop.sh 10           # build, max 10 iterations
./tools/spec-loop/loop.sh plan         # gap-analysis → rewrite the plan (no code changes)
./tools/spec-loop/loop.sh update       # back-fill specs from functionality others contributed
./tools/spec-loop/loop.sh consolidate  # shrink the plan when it grows too long
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
  brings the specs back in sync, on a `sync-specs` branch.
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
as defence in depth the loop also hard-denies `git push` and `gh` via
`--disallowedTools`. Full rationale:
[`docs/spec-driven-development.md` § Security and the dangerously-skip-permissions flag](../../docs/spec-driven-development.md#security-and-the-dangerously-skip-permissions-flag).

## Stop / configure

- Stop: `Ctrl+C`, or `touch STOP` (exits after the current iteration).
- `SPEC_LOOP_BASE` — branch to fork work items from. Defaults to `main`;
  set it explicitly to build on top of a different branch.
- `SPEC_LOOP_AGENT` — Claude-compatible agent CLI or wrapper to run
  (default `claude`).
- `SPEC_LOOP_MODEL` — model passed to the agent CLI (default `sonnet`).
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
