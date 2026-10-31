<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are running the **update** beat of the spec-driven loop. Specs can
fall behind the code when contributors land functionality the normal
way (a regular PR, not through this loop). This beat brings the specs
back in sync with reality. It is the inverse of `plan`: `plan` finds code
missing against specs; `update` finds **functionality missing against
specs** and back-fills the specs.

Context to load first:

- `tools/spec-loop/AGENTS.md` and the repo-wide `/AGENTS.md`.
- `tools/spec-loop/specs/*` — the current functional description.
- The actual code: `.claude/skills/`, `tools/`, `docs/`, `docs/modes.md`.
- The appended **Compact repository inventory** block from the runner —
  use it as the first routing map before opening full files.

Steps:

1. **Check the `## Incremental scope` section appended below by the
   runner.** If it names a previous sync commit, run the `git diff
   --name-only` command it provides and treat that file list as the
   *only* surface to re-audit — everything else is already in sync as of
   that commit. If the diff is empty, exit without creating a branch or
   commit (print "specs already in sync as of <SHA>"). If no previous
   sync commit is recorded, fall through to a full inventory.
2. Read the appended **Compact repository inventory**. Use it to identify
   likely spec/source relationships and validation commands before opening
   full files. The inventory is a routing aid, not proof; confirm with a
   code search before recording something as present or absent.
3. **Create a uniquely-named sync branch off the integration base**, then
   switch to it: `git checkout -b "sync-specs-$(date +%Y%m%d-%H%M%S)"`. A
   fresh branch every run keeps each sync as its own reviewable PR and
   never collides with or commits on top of a previous `sync-specs*`
   branch. Note the exact name you created — you will print it in the
   human-run commands below. Never commit the sync to the integration
   branch.
4. Inventory the code with parallel subagents (full inventory only if
   step 1 did not narrow the surface):
   - every `.claude/skills/*/SKILL.md` (name, mode, what it does);
   - every `tools/*` project (what it does, its tests);
   - the mode/status table in `docs/modes.md`.
5. Diff that inventory against `tools/spec-loop/specs/`:
   - **New functionality with no spec** → author a new topic-named spec
     (no number prefix) following the format in
     [`specs/README.md`](specs/README.md), grounded in the real code it
     describes.
   - **Drifted spec** → a spec whose *Where it lives*, *Behaviour &
     contract*, or `status` no longer matches the code → update it to
     match reality (e.g. a `proposed` area that now has a shipped skill
     becomes `experimental`/`stable`; skill counts in `docs/modes.md`
     are reflected).
   - **Removed functionality** → mark the spec or move it to a `Known
     gaps`/retired note; do not silently delete history.
6. Update `specs/overview.md` and `specs/README.md` indexes if areas were
   added or renamed.
7. `git add -A` then `git commit` with subject
   `docs(spec-loop): sync specs with contributed functionality` and a
   `Generated-by: <agent> (<model>)` trailer, where `<agent>` and
   `<model>` are the actual agent and model you are running as (e.g.
   `Claude (Opus 4.8)`, `OpenCode (Big Pickle)`) — do not hardcode
   either. **Do NOT touch
   `tools/spec-loop/.last-sync` yourself** — `loop.sh` amends the marker
   into this commit after you finish, so the next `update` run knows to
   scope from `$BASE_HEAD`. Leaving it alone avoids merge conflicts with
   that amendment.

Then STOP. Do NOT push, do NOT open a PR. Print the human-run commands:

(substitute `<sync-branch>` with the exact branch name you created in
step 2)

```text
git push -u origin <sync-branch>
gh pr create --web --base <integration-base> --head <sync-branch> \
  --title "Sync specs with contributed functionality" --body-file <body>
```

Rules:

- **Edit specs only.** This beat changes `tools/spec-loop/specs/` and
  the spec indexes. It must NOT change any skill, tool, or doc outside the
  spec directory — it documents reality, it does not alter it. The marker
  file `.last-sync` is owned by `loop.sh`; do not touch it.
- Confirm with a code search before recording something as present or
  absent. Do not invent behaviour the code does not have.
- **Re-verify every `Known gaps` bullet you keep.** A bullet is retained
  only if this pass found evidence it is still open, of the same three
  kinds the plan beat uses: a call site (`file:line` where the behaviour is
  or is not wired), file content (text, or its absence, at a named path),
  or a counted value derived from the tree. A name match is not evidence.
  A bullet proven closed is removed or rewritten to what remains open; a
  bullet you cannot verify is kept and marked unverified, never silently
  carried forward as true. Where a gap has a crisp end state, add
  `<!-- gap-closes-when: … -->` (`path-exists:<path>`,
  `symbol-called:<path>::<name>`, `skill-count:<family>=<n>`, or
  `none (narrative)`) so `spec-validate` can check it from then on.
- Keep the RFCs untouched — they are a separate governance layer.
