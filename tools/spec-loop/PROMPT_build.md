<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are running the **build** beat of the spec-driven loop for this
repository. Implement exactly ONE work item, on its OWN branch.

Context to load first:

- `tools/spec-loop/AGENTS.md` — operational rules (repo map, validation
  commands, branch + hard-limit rules). The repo-wide `/AGENTS.md` also
  applies (commit trailers, placeholder convention, confidentiality).
- `tools/spec-loop/IMPLEMENTATION_PLAN.md` — the prioritised work items.
- The appended **Open pull-request context** block from the runner.
- Only the spec(s) and source files relevant to the chosen work item —
  do not read the whole tree.

Steps:

1. Read the appended **Open pull-request context**. Treat open PRs as
   in-flight work. Pick the single highest-priority work item from
   `IMPLEMENTATION_PLAN.md`. If a **Tooling source** block is appended
   below, read the plan from the control branch as it shows
   (`git show <ref>:tools/spec-loop/IMPLEMENTATION_PLAN.md`), not from the
   working tree — the tree is on the integration base, which need not carry
   the plan. Pick an item not already substantially covered by an open PR.
   One only.
2. **Create its branch off the integration base**, then switch to it:
   `git checkout -b <slug>` where `<slug>` is the work item's branch — the
   bare slug, **no `spec/` or other prefix** (e.g.
   `pairing-self-review`). NEVER commit the work to the integration
   branch. One branch per work item.
3. Read only the relevant spec file(s) — from the control branch if a
   **Tooling source** block is appended, otherwise from the working tree —
   plus the relevant `.claude/skills/` / `tools/` / `docs/` files from the
   working tree. Confirm what already exists before writing — do not assume.
4. Implement the work item **completely** — no placeholders, no stubs.
   Skills: follow the skill format (frontmatter `name` / `description` /
   `license`, SPDX header, placeholder convention, every state change a
   confirmed proposal) **and ship an eval suite** under
   `tools/skill-evals/evals/<skill-name>/` exercising each step with
   fixture cases (per `/AGENTS.md` § Reusable skills — a skill without a
   matching eval suite is incomplete). Tools: ship tests.
5. Run the work item's **Validation** command(s) from its spec (the
   backpressure). Fix until they pass.
6. Specs and `IMPLEMENTATION_PLAN.md` live on the control branch. If a
   **Tooling source** block is appended, they are **not** on this work
   branch — do not create or edit them here; instead note any `status` or
   `Known gap` change in the PR body for a later plan/update beat to
   reconcile. (If no such block is present, the tooling is on this branch:
   update **only that spec's** frontmatter/Known-gaps, and never
   `IMPLEMENTATION_PLAN.md`.)
7. `git add -A` then `git commit` with an imperative subject and a
   `Generated-by: Claude (Opus 4.7)` trailer. **Never** add a
   `Co-Authored-By:` trailer for an agent.

Then STOP. Do NOT push and do NOT open a PR — `git push` and
`gh pr create` are the human's step (they are in `.claude/settings.json`
`ask`). Print the exact commands the human can run:

```text
git push -u origin <slug>
gh pr create --web --base <integration-base> --head <slug> \
  --title "<subject>" --body-file <prepared-body>
```

Rules:

- One work item per iteration. Do not bundle.
- Do not duplicate in-flight work from open PRs. If the highest-priority
  plan item is covered by an open PR, skip it and choose the next
  uncovered item.
- If a work item is blocked, note why in its spec's `Known gaps` and pick
  the next item instead.
- Stay inside the sandbox; never edit `.claude/settings.json`; never add a
  new network/filesystem allowance.
- Single sources of truth — no duplicate logic; extend `tools/`.
