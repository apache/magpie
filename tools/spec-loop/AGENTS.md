<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# AGENTS — spec-loop operational context

This file is the **operational** context for the spec-loop only:
build/validate commands, the repository map, and the branch rules. It is
loaded by the loop's prompts in addition to the repository-wide
[`/AGENTS.md`](../../AGENTS.md), which still governs everything (commit
trailers, placeholder convention, privacy/security posture). Where the
two overlap, the repo-wide `AGENTS.md` wins.

## Repository map (what the loop edits)

This repo has no `src/` tree. Work lands in one of:

- `.claude/skills/<name>/SKILL.md` — agent-readable skills (Markdown +
  YAML frontmatter; required keys `name`, `description`, `license`).
- `tools/<tool>/` — deterministic Python tools (`uv`, hatchling,
  `src/` + `tests/`, `dependencies = []` where possible).
- `docs/` — human-facing documentation. `docs/rfcs/` is the **separate**
  governance layer — the loop never edits it.
- `tools/spec-loop/specs/` — the specs this loop consumes.

## Validation commands (the build "backpressure" step)

Run the spec's own **Validation** block first. General checks:

```bash
# Validate skill definitions (frontmatter, links, placeholders)
uv run --project tools/skill-validator --group dev skill-validate

# A skill's behavioural eval suite (every skill must have one)
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/<skill-name>/

# A tool's own tests (substitute the tool path)
uv run --project tools/<tool> --group dev pytest

# Shell scripts
bash -n <script>.sh && shellcheck <script>.sh
```

There is no repo-wide test runner; validate the specific surface the
spec touches. If a work item adds or changes a **skill**, it must also
add/extend that skill's eval suite under
`tools/skill-evals/evals/<skill-name>/` (per `/AGENTS.md` § Reusable
skills — a skill without an eval suite is incomplete). If a work item
adds a **tool**, that tool ships its own tests. Both must pass before
commit.

## Branch rules (the user's constraint: one branch per fix/feature)

- **Never commit feature work to the integration branch.** Build mode
  branches `<slug>` off the integration branch (`$SPEC_LOOP_BASE`,
  default: `main`) first.
- **One spec per branch, one branch per PR.** Do not bundle specs.
- A feature branch edits only **its own** spec's `status:` (→ `done`) —
  not sibling specs and not `IMPLEMENTATION_PLAN.md` (avoids cross-branch
  conflicts; the plan is reconciled by a later `plan` pass).
- The **`update`** beat (specs fell behind code others contributed)
  branches `sync-specs` and edits `specs/` **only** — it documents
  reality, it never changes a skill, tool, or doc outside the spec dir.
- The runner feeds each iteration **both** the open PRs and the local
  work-item branches as in-flight work. Because the loop never pushes, a
  built-but-un-pushed item exists only as a local branch with no PR, so the
  local-branch list (not just open PRs) is what prevents the loop from
  rebuilding the same item every iteration.

## Hard limits (governance — do not cross)

- **No push, no PR.** `git push` and `gh pr create` are in the `ask`
  list of `.claude/settings.json`. The loop stops at a local commit and
  prints the human-run commands. Opening the PR is the human's click.
- **No `.claude/settings.json` edits** (it is in the `deny` list).
- **No new network/filesystem allowances.** Run inside the existing
  sandbox.

## Commits

- Imperative subject describing the user-visible change.
- Trailer `Generated-by: Claude (Opus 4.7)` — **never** `Co-Authored-By`
  with an agent (repo-wide `AGENTS.md` § Commit and PR conventions).
- One commit per build iteration (the change + its spec `status` flip).
