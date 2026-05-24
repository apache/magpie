<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are running the **build** beat of the spec-driven loop for this
repository. Implement exactly ONE work item, on its OWN branch.

Context to load first:

- `tools/spec-loop/AGENTS.md` — operational rules (repo map, validation
  commands, branch + hard-limit rules). The repo-wide `/AGENTS.md` also
  applies (commit trailers, placeholder convention, confidentiality).
- `tools/spec-loop/IMPLEMENTATION_PLAN.md` — the prioritised work items.
- Only the spec(s) and source files relevant to the chosen work item —
  do not read the whole tree.

Steps:

1. Pick the single highest-priority work item from
   `IMPLEMENTATION_PLAN.md`. One only.
2. **Create its branch off the integration base**, then switch to it:
   `git switch -c <slug>` where `<slug>` is the work item's branch (e.g.
   `spec/pairing-self-review`). NEVER commit the work to the integration
   branch. One branch per work item.
3. Read only the spec file(s) and `.claude/skills/` / `tools/` / `docs/`
   files relevant to this work item. Confirm what already exists before
   writing — do not assume.
4. Implement the work item **completely** — no placeholders, no stubs.
   Skills: follow the skill format (frontmatter `name` / `description` /
   `license`, SPDX header, placeholder convention, every state change a
   confirmed proposal) **and ship an eval suite** under
   `tools/skill-evals/evals/<skill-name>/` exercising each step with
   fixture cases (per `/AGENTS.md` § Reusable skills — a skill without a
   matching eval suite is incomplete). Tools: ship tests.
5. Run the work item's **Validation** command(s) from its spec (the
   backpressure). Fix until they pass.
6. If this work item closes a `Known gap` or moves a spec's `status`,
   update **only that spec's** frontmatter/Known-gaps — do not touch
   sibling specs or `IMPLEMENTATION_PLAN.md` (the plan is reconciled by a
   later plan beat, so concurrent branches never conflict).
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
- If a work item is blocked, note why in its spec's `Known gaps` and pick
  the next item instead.
- Stay inside the sandbox; never edit `.claude/settings.json`; never add a
  new network/filesystem allowance.
- Single sources of truth — no duplicate logic; extend `tools/`.
