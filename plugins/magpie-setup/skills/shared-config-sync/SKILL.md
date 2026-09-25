---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: shared-config-sync
family: setup
mode: Meta
description: >-
  Commit and push the user's shared Claude config to the
  `~/.claude-config` sync repo, rebasing first so a push never buries
  work from another machine. Bootstraps the repo when it is missing.
  Never force-pushes, never rewrites pushed history, never creates a
  public remote, and touches nothing outside `~/.claude-config/`.
when_to_use: >-
  When the user wants their shared Claude config synced, or has just
  edited something under `~/.claude-config/`. Also on a fresh host with
  no such repo yet, and after `setup-isolated-setup-update` finds drift
  on a script they keep there.
capability:
  - capability:intake
  - capability:platform
surface_hash: sha256:ca51fa0c9ac2a8ce
license: Apache-2.0
---

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory -->

# setup-shared-config-sync

This skill pushes local edits in `~/.claude-config/` to the sync repo's remote, so other machines can pull them.
It is the counterpart to the periodic `git pull --rebase --autostash` that the framework's example `sync.sh` runs on a timer: that pulls *upstream* into the local clone; this skill pushes *local* changes upstream.

## Adopter overrides

Before running the default behaviour below, this skill reads
[`.apache-magpie-local/setup-shared-config-sync.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/setup-shared-config-sync.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo, if present, and applies any agent-readable overrides it finds.
The contract (what overrides may contain, hard rules, reconciliation on framework upgrade, upstreaming) is in [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md).

**Hard rule**: agents NEVER modify the snapshot under `<adopter-repo>/.apache-magpie/`.
Local changes go in the override file.
Framework changes go via PR to `apache/magpie`.

---

## Snapshot drift

Also at the top of every run, this skill compares the gitignored `.apache-magpie.local.lock` (per-machine fetch) against the committed `.apache-magpie.lock` (the project pin).
On mismatch it surfaces the gap and proposes [`setup upgrade`](../setup/upgrade.md).
The proposal is non-blocking; the user may defer and run with the local snapshot for now.
Full flow: [`docs/quick-start/other-install-methods.md` § Subsequent runs and drift detection](../../../../docs/quick-start/other-install-methods.md#subsequent-runs-and-drift-detection).

Drift severity:

- **method or URL differ** → ✗ full re-install needed.
- **ref differs** (project bumped tag, or `git-branch` local is behind upstream tip) → ⚠ sync needed.
- **`svn-zip` SHA-512 mismatches the committed anchor** → ✗ security-flagged; investigate before upgrading.

---
## Hardcoded path

The sync repo lives at `~/.claude-config/`, the convention documented in
[`docs/setup/secure-agent-setup.md` → Syncing user-scope config across machines](../../../../docs/setup/secure-agent-setup.md#syncing-user-scope-config-across-machines).
The path is intentionally not parameterised: the doc names one canonical location, so adopters with a sync repo elsewhere fork this skill.

## The default remote

When the skill has to **bootstrap** a missing `~/.claude-config/`
(see [Bootstrapping a missing `~/.claude-config/`](#bootstrapping-a-missing-claude-config)),
it resolves the remote to clone or create in this order:

1. **An explicit URL the user passed this invocation** (e.g. *"bootstrap from `git@gitlab.com:me/claude-config.git`"*) wins over everything.
2. **The default GitHub convention**: `git@github.com:<handle>/claude-config.git`, the SSH form the doc's
   [Setting up a fresh host](../../../../docs/setup/secure-agent-setup.md#setting-up-a-fresh-host)
   snippet uses.
   `<handle>` comes from `gh api user --jq .login` (requires an authenticated `gh`).
   The repo name is `claude-config`.

If neither resolves (`gh` is missing or unauthenticated **and** the user gave no URL), ask the user for the remote URL rather than guessing.
Any remote the skill *creates* is **private** (see the golden rules); never public.

## Golden rules

- **Never force-push.** No `--force`, no `--force-with-lease`, no `--no-verify`, no rewriting commits already pushed to the remote.
  The sync repo is the source of truth between machines; rewriting its history can lose work from a machine that has not been pulled here yet.
- **Never modify a file outside `~/.claude-config/`.**
  If the user's intended change is to a file in `~/.claude/` directly (not via a symlink into `~/.claude-config/`), surface that and stop; they need a different action, not this skill.
  The **one** exception is the fresh-host symlink wiring during bootstrap (`ln -sfn ~/.claude-config/... ~/.claude/...`), and only after the user confirms it; see
  [Bootstrapping a missing `~/.claude-config/`](#bootstrapping-a-missing-claude-config).
- **Any remote the skill creates is private.** When bootstrap creates a new remote (`gh repo create`), it always passes `--private`: never public, never `--internal` unless the user asks.
  `~/.claude/CLAUDE.md` carries personal collaboration preferences and the scripts may reference internal paths; a public config repo leaks both.
  This mirrors the doc's *"a **private** git repository (private, not public …)"* rule.
- **Confirm before creating or pushing to a new remote.** Creating a GitHub repo and pushing the first commit is outward-facing and hard to reverse.
  Bootstrap shows the exact plan (repo name, `--private` visibility, remote URL, the files it will scaffold) and waits for explicit approval before running `gh repo create` or the initial `git push`.
  **Cloning** an existing remote is lower-risk (it writes only into the new `~/.claude-config/` checkout) and may proceed without a separate confirmation, though the skill still reports what it cloned.
- **Never clobber a non-repo `~/.claude-config/`.** If the path exists but is not a git working tree, stop and surface it; do not `rm` it or `git init` over it.
  Bootstrap only ever *creates* a `~/.claude-config/` that was entirely absent.
- **Pull-with-rebase first.** If `git fetch` shows the local checkout is behind the remote, run `git pull --rebase --autostash` *before* the commit + push.
  Concurrent work from another machine takes precedence; the local commit lands on top, as the example `sync.sh` does for the periodic pull.
- **Draft the commit message; never auto-send.** For every uncommitted change, draft a one-line commit subject (plus a 2–4 line body if the change merits it) and show it to the user.
  The user replies *"go"* / *"yes"* / edits / *"split into two commits"* etc. before any `git commit` runs.
- **Use the resolved attribution trailer, added with `--trailer`.** Agent-authored commits carry the trailer the user's commit-attribution convention names, resolved per [`commit-attribution.md`](../../../../docs/setup/commit-attribution.md) (the sync repo has no project file, so the user's choice applies, else `Generated-by: <agent> (<model>)`), where `<agent>` and `<model>` are the agent and model you are actually running as (e.g. `Claude (Opus 4.8)`, `OpenCode (Big Pickle)`). Add it with `git commit --trailer`, never in the message body.
  Do not hardcode either, and never use `Co-Authored-By:`.
  Canonical wording: [AGENTS.md → Commit and PR conventions](../../../../AGENTS.md#commit-and-pr-conventions).
- **Stop on lock conflict.** The example `sync.sh` uses `flock --nonblock` on `~/.claude-config/.sync.lock` so two sync runs do not race.
  If `.sync.lock` is held, do not steal the lock; surface the conflict and stop.
  The other process is likely the user's recurring sync timer.

## Bootstrapping a missing `~/.claude-config/`

Reached from [Walk-through step 1](#walk-through) when the sync repo is **entirely absent**.
The goal is a working `~/.claude-config/` git checkout wired to a private remote, by cloning the default remote if it exists or creating it if not.
The skill touches nothing outside the new checkout except the confirmed fresh-host symlink wiring at the end.

### Step B1 — resolve the remote

Resolve the remote per [The default remote](#the-default-remote): an explicit URL the user passed, else `git@github.com:<handle>/claude-config.git` with `<handle>` from `gh api user --jq .login`.
If neither resolves (`gh` missing/unauthenticated **and** no URL given), ask the user for the remote URL and stop until they provide one; do not guess a handle.

### Step B2 — does the remote exist?

- **GitHub default:** `gh repo view <handle>/claude-config`: exit `0` ⇒ exists, non-zero ⇒ does not exist.
  If the error is auth/permission rather than "not found", surface it and stop rather than assuming absence.
- **Explicit non-GitHub URL:** `git ls-remote <url>`: exit `0` ⇒ exists, non-zero ⇒ does not exist / unreachable.

### Step B3a — remote exists → clone

`git clone <url> ~/.claude-config`.
This low-risk path (it writes only the new checkout) may proceed without a separate create-confirmation; report the clone result.
Then continue to [Step B4 — fresh-host symlink wiring](#step-b4--fresh-host-symlink-wiring) and resume the sync walk-through from step 2 (typically *"in sync, nothing to do"*).

### Step B3b — remote does not exist → create + scaffold + push

Creating an outward-facing remote is confirm-first (golden rule).
**Show the full plan and wait for explicit approval**: the repo name, `--private` visibility, the remote URL, and the files to be scaffolded.
On approval:

1. **Create the private remote.**
   - GitHub: `gh repo create <handle>/claude-config --private --description "Personal Claude Code shared config (synced across machines)"`
     (no `--clone`, no auto-init; the local scaffold below becomes the first commit).
   - Non-GitHub explicit URL: the skill cannot create the remote; tell the user to create an **empty private** repo at that URL and re-invoke.
2. **Init + scaffold the minimal layout** under `~/.claude-config/`, matching the doc's
   [Layout](../../../../docs/setup/secure-agent-setup.md#layout) and
   [A minimal `sync.sh`](../../../../docs/setup/secure-agent-setup.md#a-minimal-syncsh):

   ```text
   git init -b main ~/.claude-config
   ~/.claude-config/
   ├── README.md      # what's in the repo + per-machine install steps
   ├── sync.sh        # the pull/commit/push helper (chmod +x)
   ├── scripts/       # (empty; hooks land here as the user adopts them)
   └── .gitignore     # excludes .sync.lock and any *.credentials* / secrets
   ```

   `sync.sh` is the verbatim script from the doc's
   [A minimal `sync.sh`](../../../../docs/setup/secure-agent-setup.md#a-minimal-syncsh)
   section.
   `.gitignore` must at minimum carry `.sync.lock` (the `flock` file) so the lock is never committed.
3. **Initial commit + push.** `git add` the scaffolded files individually (never `git add -A`; see [Walk-through](#walk-through) step 5), commit with the resolved attribution trailer (via `--trailer`), `git remote add origin <url>`, then `git push -u origin main`.

### Step B4 — fresh-host symlink wiring

The new (or freshly cloned) checkout only *protects* this host once its tracked artifacts are symlinked into `~/.claude/`.
This is the **one** write outside `~/.claude-config/` the skill performs, and only after the user confirms.
Offer to run the
[Setting up a fresh host](../../../../docs/setup/secure-agent-setup.md#setting-up-a-fresh-host)
wiring (the `ln -sfn ~/.claude-config/… ~/.claude/…` block, which `mv`s any pre-existing real file to `.bak` before symlinking).
If the user declines, point them at that doc section.
Wire only the artifacts the checkout contains; on a brand-new scaffold `scripts/` may be empty, so this step is often a no-op beyond `CLAUDE.md`.

## Walk-through

1. **`cd ~/.claude-config`** and verify it is a git working tree pointing at a private remote.
   - If the directory **does not exist** at all, do not stop — **bootstrap** it: jump to
     [Bootstrapping a missing `~/.claude-config/`](#bootstrapping-a-missing-claude-config),
     then resume the sync walk-through from step 2.
   - If the directory **exists but is not a git repo**, surface that and stop (per the golden rule — never clobber a non-repo path).
     The user has a stray `~/.claude-config/`; they resolve it, then re-invoke.
   - If it is a git repo, continue to step 2.

2. **`git fetch origin`** to learn the remote's current state.
   Report:
   - commits behind upstream (will be pulled in step 4),
   - commits ahead of upstream (committed local work not yet pushed),
   - uncommitted working-tree modifications (`git status --short`),
   - untracked files the user may want to either add or `.gitignore`.

3. **Decide the action.** The four reachable states:
   - **In sync, nothing to do.** No uncommitted changes, no unpushed commits, not behind.
     Report and stop.
   - **Push-only.** Committed local work needs to land on the remote, but not behind and no uncommitted edits.
     Pull-with-rebase is unnecessary; go straight to push.
   - **Commit-then-push.** Uncommitted edits exist.
     Walk each modified file with the user (diff + draft commit message + approval), commit each batch the user accepts, then push.
   - **Pull-then-commit-then-push.** Uncommitted edits *and* behind upstream.
     Run `git pull --rebase --autostash` first; if rebase succeeds cleanly, proceed to the commit-then-push flow.
     If rebase conflicts, stop and surface — conflicts in `~/.claude-config/` are the user's to resolve, not the skill's.

4. **Pull-with-rebase (when applicable).** Run `git pull --rebase --autostash`.
   Report what changed (commits pulled, files touched).

5. **Stage + commit (when applicable).** For each modification the user approves:
   - `git add <file>` for the specific file (never `git add -A` or `git add .` — the sync repo is the user's most personal directory and `git add -A` risks staging an editor swap file or a `.DS_Store` you forgot to gitignore),
   - `git commit -m '<subject>' -m '<body>' --trailer '<trailer>'` with the approved message.
     `<trailer>` is the resolved attribution trailer (see the golden rule above) — the actual agent and model you are running as, not a hardcoded value; omit `--trailer` when the convention is `none`.

   Probe the gpg-agent cache first when `commit.gpgsign` is true: a token-backed key with a cold cache stalls this commit until `gpg: signing failed: Timeout`.
   Surface a dialogue, or hand the user the command — see
   [`AGENTS.md` → *Commit and PR conventions*](../../../../AGENTS.md#commit-and-pr-conventions).

6. **Push.** `git push` to the upstream branch. No `--force`.
   A rejected (non-fast-forward) push means another machine pushed after our `git fetch` in step 2; stop, surface, and recommend re-invoking the skill (which repeats the fetch + pull-with-rebase).
   Do not retry in-flight.

## After the push lands

Report:
- which commit SHA is now on the remote,
- a one-line summary of what was pushed (so the user can confirm in their terminal scrollback),
- whether other-machine pulls are needed (the timer-driven `sync.sh` on the user's other hosts picks the change up on its next run; do not nag about this).

If the changes touched a file under `~/.claude-config/scripts/` that is symlinked from `~/.claude/scripts/`, also note that the change is *immediately* live on this host, since the symlink resolves to the modified file.
No re-`cp` needed.
