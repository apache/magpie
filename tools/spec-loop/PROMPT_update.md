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

Steps:

1. **Check the `## Incremental scope` section appended below by the
   runner.** If it names a previous sync commit, run the `git diff
   --name-only` command it provides and treat that file list as the
   *only* surface to re-audit — everything else is already in sync as of
   that commit. If the diff is empty, exit without creating a branch or
   commit (print "specs already in sync as of <SHA>"). If no previous
   sync commit is recorded, fall through to a full inventory.
2. **Create the sync branch off the integration base**, then switch to
   it: `git checkout -b sync-specs`. (One reviewable PR for the
   sync.) Never commit the sync to the integration branch.
3. Inventory the code with parallel subagents (full inventory only if
   step 1 did not narrow the surface):
   - every `.claude/skills/*/SKILL.md` (name, mode, what it does);
   - every `tools/*` project (what it does, its tests);
   - the mode/status table in `docs/modes.md`.
4. Diff that inventory against `tools/spec-loop/specs/`:
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
5. Update `specs/overview.md` and `specs/README.md` indexes if areas were
   added or renamed.
6. `git add -A` then `git commit` with subject
   `docs(spec-loop): sync specs with contributed functionality` and a
   `Generated-by: Claude (Opus 4.7)` trailer. **Do NOT touch
   `tools/spec-loop/.last-sync` yourself** — `loop.sh` amends the marker
   into this commit after you finish, so the next `update` run knows to
   scope from `$BASE_HEAD`. Leaving it alone avoids merge conflicts with
   that amendment.

Then STOP. Do NOT push, do NOT open a PR. Print the human-run commands:

```text
git push -u origin sync-specs
gh pr create --web --base <integration-base> --head sync-specs \
  --title "Sync specs with contributed functionality" --body-file <body>
```

Rules:

- **Edit specs only.** This beat changes `tools/spec-loop/specs/` and
  the indexes. It must NOT change any skill, tool, or doc outside the
  spec directory — it documents reality, it does not alter it. The
  marker file `.last-sync` is owned by `loop.sh`; do not touch it.
- Confirm with a code search before recording something as present or
  absent. Do not invent behaviour the code does not have.
- Keep the RFCs untouched — they are a separate governance layer.
