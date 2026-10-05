<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `marketplace`. `.apache-magpie.lock` exists in this repo
(the project is already adopted).

This run is in a linked worktree, `/home/dev/acme-wt/feature`, created with
`git worktree add`. It has no `.apache-magpie-local/` of its own; the main
checkout `/home/dev/acme` has one.

Personal layer (`python3 -m setup_preflight.layers`):
  `personal_layers`: `/home/dev/acme-wt/feature/.apache-magpie-local/` (absent),
                     `/home/dev/acme/.apache-magpie-local/`
  `personal_dir`:    `/home/dev/acme/.apache-magpie-local/` — the main checkout's

Scope: `config pr-management-code-review` narrowed this run to one skill,
`magpie-pr-management-code-review`.

Step 3 wrote: `/home/dev/acme/.apache-magpie-local/reviewer-routing.md`
  (the last missing `requires_config:` entry for this skill;
  `fix-workflow.md` was already committed at
  `.apache-magpie-overrides/fix-workflow.md`).

`magpie-pr-management-code-review`'s current `surface_hash` (from its
  `SKILL.md` frontmatter, already in context): sha256:1d0038ec4fde60bf

Running plugin version: 0.3.1

Today: 2026-09-21
