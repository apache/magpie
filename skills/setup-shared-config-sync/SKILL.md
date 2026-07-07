---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-setup-shared-config-sync
description: |
  Commit + push the user's shared Claude config to the
  `~/.claude-config` private dotfile-style sync repo. Inspects
  for uncommitted local edits and unpushed commits, drafts a
  commit message, and after explicit approval commits and
  pushes. Runs `git pull --rebase` first if the local checkout
  is behind, so a push never overwrites concurrent work from
  another machine. Never force-pushes; never rewrites
  already-pushed history; never modifies files outside
  `~/.claude-config/`.
when_to_use: |
  Invoke when the user says "sync my Claude config", "push my
  ~/.claude-config", "commit shared Claude config", or after
  modifying a file in `~/.claude-config/` (scripts, CLAUDE.md,
  commands, sync.sh). Also appropriate after
  `setup-isolated-setup-update` surfaces drift on a script the
  user keeps in `~/.claude-config/` and wants propagated to
  other machines.
capability:
  - capability:intake
  - capability:platform
license: Apache-2.0
---

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory -->

# setup-shared-config-sync

This skill propagates local edits in `~/.claude-config/` to the
sync repo's remote, so other machines can pull them. It is the
counterpart to the periodic `git pull --rebase --autostash` that
the framework's example `sync.sh` runs on a timer — that direction
pulls *upstream* into the local clone; this skill pushes *local*
modifications upstream.

## Adopter overrides

Before running the default behaviour documented
below, this skill consults
[`.apache-magpie-overrides/setup-shared-config-sync.md`](../../docs/setup/agentic-overrides.md)
in the adopter repo if it exists, and applies any
agent-readable overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../docs/setup/agentic-overrides.md)
for the contract — what overrides may contain, hard
rules, the reconciliation flow on framework upgrade,
upstreaming guidance.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-magpie/`. Local modifications
go in the override file. Framework changes go via PR
to `apache/magpie`.

---

## Snapshot drift

Also at the top of every run, this skill compares the
gitignored `.apache-magpie.local.lock` (per-machine
fetch) against the committed `.apache-magpie.lock`
(the project pin). On mismatch the skill surfaces the
gap and proposes
[`/magpie-setup upgrade`](../setup/upgrade.md).
The proposal is non-blocking — the user may defer if
they want to run with the local snapshot for now. See
[`docs/setup/install-recipes.md` § Subsequent runs and drift detection](../../docs/setup/install-recipes.md#subsequent-runs-and-drift-detection)
for the full flow.

Drift severity:

- **method or URL differ** → ✗ full re-install needed.
- **ref differs** (project bumped tag, or `git-branch`
  local is behind upstream tip) → ⚠ sync needed.
- **`svn-zip` SHA-512 mismatches the committed
  anchor** → ✗ security-flagged; investigate before
  upgrading.

---
## Hardcoded path

The sync repo lives at `~/.claude-config/`. This is the convention
documented in
[`docs/setup/secure-agent-setup.md` → Syncing user-scope config across machines](../../docs/setup/secure-agent-setup.md#syncing-user-scope-config-across-machines).
Adopters who maintain a sync repo at a different path will need to
fork this skill — the path is intentionally not parameterised
because the doc specifies one canonical location and forking the
skill is cleaner than per-invocation path-passing.

## Golden rules

- **Never force-push.** No `--force`, no `--force-with-lease`, no
  `--no-verify`, no rewriting commits already pushed to the
  remote. The sync repo is the source of truth between machines;
  rewriting its history risks losing work made on another
  machine that has not yet been pulled here.
- **Never modify a file outside `~/.claude-config/`.** This skill
  is scoped strictly to that one directory. If the user's
  intended change is to a file in `~/.claude/` directly (not via a
  symlink into `~/.claude-config/`), surface that and stop — the
  user wants a different action, not this skill.
- **Pull-with-rebase first.** If `git fetch` shows the local
  checkout is behind the remote, run `git pull --rebase --autostash`
  *before* the commit + push. Concurrent work from another
  machine takes precedence; the local commit lands on top.
  This matches what the example `sync.sh` does for the periodic
  pull.
- **Draft the commit message; never auto-send.** For every
  uncommitted modification, the skill drafts a one-line commit
  subject (plus a 2–4 line body if the change merits it) and
  shows it to the user for approval. The user replies with
  *"go"* / *"yes"* / edits / *"split into two commits"* etc.
  before any `git commit` runs.
- **Use the `Generated-by:` trailer per AGENTS.md.** Commits
  authored by an agent on the user's behalf carry
  `Generated-by: Claude Code (Opus <version>)` at the end of
  the body — never `Co-Authored-By:`. See
  [AGENTS.md → Commit and PR conventions](../../AGENTS.md#commit-and-pr-conventions)
  for the canonical wording.
- **Stop on lock conflict.** The example `sync.sh` uses
  `flock --nonblock` on `~/.claude-config/.sync.lock` so two
  concurrent sync runs do not race. If `.sync.lock` is held, do
  not steal the lock — surface the conflict and stop. The other
  process is likely the user's recurring sync timer.

## Walk-through

1. **`cd ~/.claude-config`** and verify it is a git working tree
   pointing at a private remote. If the directory does not exist
   or is not a git repo, surface that and stop — the user has
   not yet set up a sync repo per the doc, and the right next
   action is for them to follow
   [Setting up a fresh host](../../docs/setup/secure-agent-setup.md#setting-up-a-fresh-host).

2. **`git fetch origin`** to learn the remote's current state.
   Report:
   - commits behind upstream (will be pulled in step 4),
   - commits ahead of upstream (already-committed local work
     that has not yet been pushed),
   - uncommitted working-tree modifications (`git status --short`),
   - untracked files the user may want to either add or
     `.gitignore`.

3. **Decide the action.** The four reachable states:
   - **In sync, nothing to do.** No uncommitted changes, no
     unpushed commits, not behind. Report and stop.
   - **Push-only.** Already-committed local work needs to land
     on the remote, but no behind / no uncommitted edits.
     Pull-with-rebase is unnecessary; go straight to push.
   - **Commit-then-push.** Uncommitted edits exist. Walk each
     modified file with the user (diff + draft commit message
     + approval), commit each batch the user accepts, then
     push.
   - **Pull-then-commit-then-push.** Uncommitted edits *and*
     behind upstream. Run `git pull --rebase --autostash`
     first; if rebase succeeds cleanly, proceed to the
     commit-then-push flow. If rebase conflicts, stop and
     surface — conflicts in `~/.claude-config/` are the user's
     to resolve, not the skill's.

4. **Pull-with-rebase (when applicable).** Run
   `git pull --rebase --autostash`. Report what changed
   (commits pulled, files touched).

5. **Stage + commit (when applicable).** For each modification
   the user approves:
   - `git add <file>` for the specific file (never `git add -A`
     or `git add .` — the sync repo is the user's most personal
     directory and `git add -A` risks staging an editor swap
     file or a `.DS_Store` you forgot to gitignore),
   - `git commit -m '<subject>' -m '<body>'` with the
     approved message. Always include the
     `Generated-by: Claude Code (Opus <version>)` trailer in
     the body per AGENTS.md.

6. **Push.** `git push` to the upstream branch. No `--force`.
   If push is rejected (non-fast-forward) it means another
   machine pushed concurrently after our `git fetch` in step 2;
   stop, surface, and recommend re-invoking the skill (which
   will repeat the fetch + pull-with-rebase). Do not retry
   in-flight.

## After the push lands

Report:
- which commit SHA is now on the remote,
- a one-line summary of what was pushed (so the user can
  confirm in their terminal scrollback),
- whether other-machine pulls are needed (the timer-driven
  `sync.sh` on the user's other hosts will pick the change up
  on its own next run; the skill does not need to nag about
  this).

If the modifications touched a file under
`~/.claude-config/scripts/` that is symlinked from
`~/.claude/scripts/`, also note that the change is *immediately*
live on this host — the symlink resolves to the just-modified
file. No re-`cp` needed.
