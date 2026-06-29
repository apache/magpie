<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are running the **plan** beat of the spec-driven loop for this
repository. Plan only — do NOT implement anything and do NOT commit code.

Context to load first:

- `tools/spec-loop/AGENTS.md` — operational rules (repo map, validation
  commands, branch + hard-limit rules). The repo-wide `/AGENTS.md` also
  applies.
- `tools/spec-loop/specs/*` — the functional description of the product.
- `tools/spec-loop/IMPLEMENTATION_PLAN.md` (if present; may be stale).
- The appended **Open pull-request context** block from the runner.
- The appended **Local work-item branches** block from the runner. Built
  but un-pushed work items live here, not in the PR context.

Steps:

1. Study each spec in `tools/spec-loop/specs/` and compare it against the
   actual code it names in **Where it lives** (`.claude/skills/`,
   `tools/`, `docs/`). You may use parallel subagents for reading. Do NOT
   assume something is missing — confirm with a code search first.
2. Read the appended **Open pull-request context** and **Local work-item
   branches**. Treat both open PRs and existing local work-item branches as
   in-flight work. If an apparent gap is already substantially covered by an
   open PR (including draft PRs) or already built on a local work-item
   branch, do not add it as a planned work item. The loop never pushes, so a
   built item may exist only as a local branch with no PR yet.
3. For each spec, identify the **gaps**: a `proposed` area with no skill,
   a documented step that drifted from the code, a missing test, a
   `Known gaps` item. Each gap is a candidate work item.
4. Rewrite `tools/spec-loop/IMPLEMENTATION_PLAN.md` as a prioritised list
   of work items. Each work item names: the change, the spec it serves,
   its **Validation** command, and a branch slug (`<slug>`, the bare
   slug — **no `spec/` or other prefix, no numbers**).
5. Do NOT create work items against an `off` spec (e.g. Agentic Autonomous) —
   that would skip the proof MISSION requires.

Rules:

- Plan only. No edits to skills, tools, or docs. No commits in this beat.
- Keep the plan prioritised and concise; one work item = one branch = one
  PR.
- Do not duplicate in-flight work. If a stale existing plan item is now
  covered by an open PR or already built on a local work-item branch, remove
  it or mark it as in-flight rather than leaving it available for the build
  beat.
- Treat `tools/` as the standard library — prefer extending an existing
  tool over a new ad-hoc one.
