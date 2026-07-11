---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-setup-isolated-setup-install
family: setup
mode: Meta
description: |
  Guide an adopter through the first-time install of the
  framework's secure agent setup (bubblewrap + socat +
  claude-code, sandbox/permissions/clean-env layers). Walks
  every step interactively; never auto-runs sudo, shell-rc
  edits, or settings overwrites.
when_to_use: |
  Invoke when the user says "set up the secure agent setup",
  "first-time install of the secure config", "install the
  secure setup in this tracker", "walk me through the
  secure-agent-setup install", or starts working on a fresh
  adopter clone without secure-config wiring. Also appropriate
  after a fresh OS install / new dev machine where
  `~/.claude/scripts/` is empty. Skip when the secure setup is
  already in place — use `setup-isolated-setup-verify` (to
  confirm completeness) or `setup-isolated-setup-update` (to
  refresh against the framework's latest) instead.
capability: capability:platform
license: Apache-2.0
---

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory
     <tracker>        → value of `tracker_repo:` in <project-config>/project.md
     <upstream>       → value of `upstream_repo:` in <project-config>/project.md -->

# setup-isolated-setup-install

This skill is the **on-ramp** for adopters who do not yet have the
secure setup running. It is a thin walkthrough wrapper around the
canonical install path documented in
[`docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md). The
authoritative content lives there; this skill exists so an adopter
can say *"set up the secure agent setup"* in a fresh session and
land in the right step-by-step flow without first reading the
document.

## Adopter overrides

Before running the default behaviour documented
below, this skill consults
[`.apache-magpie-overrides/setup-isolated-setup-install.md`](../../docs/setup/agentic-overrides.md)
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
## Golden rules

- **Do not auto-run privilege-elevating commands.** Anything that
  needs `sudo` (apt / dnf installs, system-wide writes) is *printed*
  for the user to copy-paste into their own terminal. The skill
  never invokes `sudo` itself.
- **Do not edit shell rc files without approval.** `~/.bashrc` /
  `~/.zshrc` modifications (sourcing `agent-iso.sh`, the optional
  `alias claude='claude-iso'`) are surfaced as the exact line to
  add; the user pastes it themselves. The skill confirms the rc
  file path with the user first; it does not assume.
- **Do not overwrite an existing settings file silently.** If the
  user already has a project `.claude/settings.json` or a
  user-scope `~/.claude/settings.json`, the skill *diffs* the
  desired merge against the existing file and asks for explicit
  approval before writing. Re-installs / partial-state recoveries
  are common — the skill must not blow away an unrelated
  pre-existing hook or `permissions.ask` rule. The desired merge
  **includes the agent-guard `hooks.PreToolUse` entry** (matcher
  `Bash`, command running the user-scope `~/.claude/scripts/agent-guard.py`)
  — the deterministic guard from
  [`tools/agent-guard`](../../tools/agent-guard/README.md). Install
  the script as `~/.claude/scripts/agent-guard.py` and populate
  `~/.claude/scripts/guards.d/` from both the engine's bundled
  `guards.d/*.py` and every skill-owned `skills/*/guards/*.py`
  (so skill-owned guards like `mention` / `mark-ready` are active),
  alongside the other user-scope scripts (Step P); wire the
  `PreToolUse` entry once, and preserve any pre-existing `hooks`
  entries.
- **Stop on the first failure.** If a step fails (manifest read
  fails, framework path wrong, an existing file conflicts in a way
  the user has not yet decided about), stop and report. Do not
  push past a failure to the next step.

## Up-front confirmations

Before walking any install step, confirm with the user:

1. **OS / distro.** macOS, Ubuntu / Debian (apt), Fedora / RHEL
   (dnf), or Arch / NixOS / other. macOS skips bubblewrap +
   socat (Seatbelt is built-in); Linux installs both per the
   distro shortcut.
2. **Framework checkout path.** The path to the user's local
   `magpie` clone. Required to read
   `tools/agent-isolation/pinned-versions.toml`,
   `.claude/settings.json`, and the
   `tools/agent-isolation/*.sh` scripts. If the user does not
   have a clone, walk them through `git clone` first.
3. **Fresh install or re-install.** For a re-install on a partial
   existing state, the skill must enumerate the existing wiring
   (project settings.json, user settings.json, hooks dir, the
   agent-guard `hooks.PreToolUse` entry + `~/.claude/scripts/agent-guard.py`,
   shell rc) before any merge so the user knows what is being
   preserved vs replaced.
4. **Sync repo (optional).** Whether the user maintains a
   private dotfile-style `~/.claude-config` repo per
   [Syncing user-scope config across machines](../../docs/setup/secure-agent-setup.md#syncing-user-scope-config-across-machines).
   If yes, the skill installs user-scope scripts as **symlinks**
   into `~/.claude-config/scripts/` rather than `cp`-ing into
   `~/.claude/scripts/` — the symlink approach is what makes
   sync push the upgrades to other machines automatically.

## Walk-through

Follow the canonical step list at
[docs/setup/secure-agent-setup.md → Adopter setup → Via a Claude Code prompt](../../docs/setup/secure-agent-setup.md#via-a-claude-code-prompt).
Each step in that list maps 1:1 to a step in this skill. Do not
re-write the list here — read the doc, follow it, and surface each
sub-step with the user. The doc names are the source of truth; the
skill is the runner.

For the verification step at the end, hand off to the
`setup-isolated-setup-verify` skill rather than re-walking the checklist
inline.

### Agent runtime — install `@latest`, enforce the floor

`claude-code` is **not** pinned to an exact version. Install it with
`npm install -g --no-save @anthropic-ai/claude-code@latest` (the
command in the doc's install list) — latest always carries the newest
permission-rule / sandbox / prompt-injection fixes. The manifest's
`[tools.claude-code]` table in
[`pinned-versions.toml`](../../tools/agent-isolation/pinned-versions.toml)
declares a `min_version` **floor**, not a pin. Because this install is
driven from Claude Code, apply the same hard gate
`setup-isolated-setup-verify` check 5 applies: read the running
version (`claude --version`) and, if it is **below** `min_version`,
**hard-fail** — stop the install, tell the operator to upgrade to
`@latest`, and have them re-run. The secure setup must not be stood up
on a below-floor runtime.

### Step P — Project-root coverage in the sandbox allowlists

Per
[`docs/setup/secure-agent-setup.md` → *Project-root coverage in the sandbox allowlists*](../../docs/setup/secure-agent-setup.md#project-root-coverage-in-the-sandbox-allowlists)
and [issue #197](https://github.com/apache/magpie/issues/197),
the harness pre-resolves `sandbox.filesystem.allowRead: ["."]` at
session start in a way that silently drops the literal `.` from the
resolved set, so a session in a freshly-cloned adopter repo can
write to CWD but cannot **read** from it under the sandbox.

The defensive measure is to add the project root as an explicit
**absolute path** to `sandbox.filesystem.allowRead` and `allowWrite`
in the adopter's **project-local** settings file
(`<repo>/.claude/settings.local.json`) — gitignored, per-machine,
per-project, merged on top of the committed project-scope and
user-scope by the harness. Worktrees handle themselves: each
worktree has its own `<worktree>/.claude/settings.local.json`,
and each gets its own root added.

#### Step P.0 — Ask the user: per-project or whole-user scope?

Before installing anything, ask the operator which scope they
want — see
[`docs/setup/secure-agent-setup.md` → *Per-project vs whole-user scope*](../../docs/setup/secure-agent-setup.md#per-project-vs-whole-user-scope)
for the full rationale + trade-offs:

- **Per-project.** The skill runs the helper for the
  current project only. Future projects on this host need the
  skill re-run in each, OR the operator can pick whole-user later.
  No global git config changes.
- **Whole-user (global).** The skill walks the operator's existing
  local git checkouts and populates their `settings.local.json`
  files, then sets `git config --global core.hooksPath` so every
  future `git checkout` / `git clone` / `git worktree add` on the
  host picks up the framework's universal post-checkout hook.

**Detect whether whole-user (global) scope is already active first.**
Read `git config --global --get core.hooksPath`:

- If it is **unset** (or does not point at the framework's shared
  hook dir), whole-user isolation is **not yet set up on this host**.
  In that case **propose whole-user (global) as the default** — it
  is the recommended baseline because it covers every current and
  future repo on the host in one pass, so the operator does not have
  to re-run this skill per project. Present per-project as the
  narrower alternative for operators who deliberately want to keep
  their per-repo git hooks (see the Step P.0a caveats).
- If it is **already set** to the framework's shared hook dir,
  whole-user isolation is already in place; default to **per-project**
  for this specific project (the global hook already covers the host,
  so only this project's `settings.local.json` needs the local pass).

**Prefer structured Q&A.** When the agent harness offers a
structured-question tool (e.g. Claude Code's `AskUserQuestion`),
use a single-select prompt whose default is chosen by the detection
above — `Whole-user (global, recommended)` when whole-user is not
yet set up, otherwise `Per-project`. Free-form chat is the fallback.

If the user picks **per-project**, skip to *Step P.1 — Install
the helper script* and *Step P.2 — Run the helper for this project*,
then move on to the next step in the canonical install list.

If the user picks **whole-user**, follow Step P.0a's loud
disclosure first, then Step P.0b (pick the whole-user *flavour* —
simple vs dispatcher), then Step P.1, then Steps P.2-whole-user
(walk existing checkouts) and P.3-whole-user (install the global
hook + set `core.hooksPath`). If they chose the dispatcher flavour,
also run Step P.3b-whole-user (install the dispatcher + prek shim).

##### Step P.0a — Loud disclosure before setting whole-user scope

If the operator picked whole-user, surface this disclosure
**before** any global config write. The operator must
acknowledge it explicitly; no silent proceed:

> **!!! WHOLE-USER SCOPE — `core.hooksPath` GLOBAL OVERRIDE !!!**
>
> Setting `git config --global core.hooksPath` makes git look up
> hooks in **one shared directory** for every repo on this host.
> Every `.git/hooks/*` in every existing repo on this machine
> becomes **inert** — git will no longer fire your per-repo
> `pre-commit`, `commit-msg`, `pre-push`, or any other hook
> unless the shared dir chains back to them.
>
> There are two whole-user flavours (you choose next, Step P.0b):
>
> - **Simple** — the framework installs **only** the
>   `post-checkout` hook in the shared dir. Every other per-repo
>   hook stays inert until you migrate it into `~/.claude/git-hooks/`
>   yourself. Pick this only if you don't rely on per-repo hooks.
> - **With per-repo dispatcher (recommended if you use prek /
>   pre-commit / husky / any per-repo hook)** — the framework
>   installs a **dispatcher** for each hook type. Each dispatcher
>   runs the framework's own logic (the `post-checkout`
>   sandbox-allowlist sync) **and then chains through to that
>   repo's own `.git/hooks/<name>`**. Your per-repo hooks keep
>   firing, and a repo with no hook is a clean no-op. A bundled
>   `prek` PATH shim makes `prek install` write its shim into the
>   repo-local `.git/hooks/` (via `--git-dir`) so the dispatcher
>   can find it.
>
> Either way, whole-user scope is reversible:
> `git config --global --unset core.hooksPath` restores per-repo
> hook lookup, and (dispatcher flavour) removing
> `~/.claude/bin` from PATH restores the stock `prek`.

Confirm the operator wants to proceed with whole-user scope after
reading the disclosure. If they hesitate or pick per-project,
fall back to the per-project path.

##### Step P.0b — Choose the whole-user flavour: simple or dispatcher

If the operator confirmed whole-user, ask which flavour (see the
disclosure above for the trade-off). **Default to the dispatcher
flavour** — it is a strict superset of simple (it still runs the
`post-checkout` sync everywhere) and it avoids silently shadowing
per-repo hooks, which is the most common whole-user surprise.
Pick simple only if the operator explicitly wants the minimal
footprint and confirms they run no per-repo hooks.

**Prefer structured Q&A** here too: a single-select with
`With per-repo dispatcher (recommended)` as the default and
`Simple (post-checkout only)` as the alternative.

- **Simple** → Step P.3-whole-user installs `git-global-post-checkout.sh`
  only.
- **Dispatcher** → Step P.3-whole-user still runs, and Step
  P.3b-whole-user additionally installs `git-hook-dispatcher.sh`
  (symlinked to each hook name, including `post-checkout` — which
  in this flavour supersedes the standalone `git-global-post-checkout.sh`)
  and the `prek` PATH shim.

#### Step P.1 — Install the helper script

(Both scopes.)

Copy `tools/agent-isolation/sandbox-add-project-root.sh` into
`~/.claude/scripts/sandbox-add-project-root.sh` (or symlink it
from `~/.claude-config/scripts/` if the operator uses the
private sync repo), mode `0755`. The script file lives
user-scope so a single install covers every adopter project on
the host; what it **writes** is project-local. The same install
mechanism the `sandbox-bypass-warn.sh` and `sandbox-status-line.sh`
helpers use (see the *Sandbox-bypass visibility hook* and
*Sandbox-state status line* sections of the doc).
#### Step P.2 — Run the helper for this project (per-project scope)

Skip if the operator picked whole-user scope (Step P.2-whole-user
below covers the equivalent).

Run the helper once with `--all-worktrees` in the adopter
repo's main checkout. The helper enumerates
`git worktree list --porcelain` and, for each worktree, writes
that worktree's absolute path into that worktree's own
`<worktree>/.claude/settings.local.json` (creating the file if
it does not yet exist). Idempotent, atomic, tolerant of missing
prereqs (see the script's header comment for the full
failure-mode list). On success, surface the diff so the operator
sees which entries landed; on no-op (paths already present),
surface a one-line "already covered" confirmation.

**Sandbox-bypass requirement when invoked from inside an agent
session.** `.claude/settings.local.json` is in Claude Code's
built-in sandbox `denyWithinAllow` set (verified empirically —
see
[`docs/setup/secure-agent-setup.md` → *Security rationale*](../../docs/setup/secure-agent-setup.md#security-rationale--why-project-local-is-safe-to-write-to)),
so the helper's Bash write is blocked when invoked through the
agent's `Bash` tool. If this skill is being walked from inside
a sandboxed session, invoke the helper with
`dangerouslyDisableSandbox: true` and the reason
*"writing project-local sandbox-allowlist entries (issue #197 fix)"*.
The bypass triggers `sandbox-bypass-warn.sh`'s loud-red banner
so the operator sees and approves the single write. When the
operator runs `setup-isolated-setup-install` directly from a
terminal (the typical first-time-install path), no bypass is
needed — the script runs outside the agent sandbox.

#### Step P.2-whole-user — Walk existing checkouts (whole-user scope)

Skip if the operator picked per-project scope.

Walk the operator's existing git checkouts and populate each
one's `.claude/settings.local.json`. This pass is **settings-only**
by default — it does NOT install per-repo `post-checkout` hooks
(the global hook installed in Step P.3-whole-user covers that
for both existing and future repos via `core.hooksPath`).

1. **Prompt the operator for root directories to scan.**
   Default suggestions: `~/code/`, `~/projects/`, `~/dev/`,
   `~/work/`. Show the operator the list, let them edit it.
   Empty list → skip the walk; the operator can re-run this
   skill later when they want existing repos covered.

2. **Walk each root dir.** Use a depth-limited `find` with
   reasonable exclusions:

   ```bash
   find "<root>" -maxdepth 5 -type d -name .git \
       -not -path '*/node_modules/*' \
       -not -path '*/.venv/*' \
       -not -path '*/__pycache__/*' \
       -not -path '*/build/*' \
       -not -path '*/dist/*' \
       -not -path '*/.cache/*' \
       -prune
   ```

   For each `.git/` found, the parent dir is a working tree.
   De-duplicate by canonical path.

3. **For each working tree found, run the helper with
   `--all-worktrees`.** Same invocation as the per-project
   variant — the helper itself handles `git worktree list` so
   linked worktrees of the same repo get processed. The helper's
   built-in `git check-ignore` guard skips repos whose
   `.claude/settings.local.json` is not gitignored (defense in
   depth — the operator should fix the `.gitignore` first).

4. **Tabulate the result** for the operator: how many checkouts
   were scanned, how many had `.claude/` (so the helper wrote),
   how many were skipped (no `.claude/` directory, or
   `.claude/settings.local.json` not gitignored).

5. **Do not install per-repo `post-checkout` hooks** during this
   pass. The next sub-step covers future and existing repos
   uniformly via the global hook.

#### Step P.3-whole-user — Install the global post-checkout hook (whole-user scope)

Skip if the operator picked per-project scope. **Dispatcher
flavour (Step P.0b):** skip step 1 below — Step P.3b-whole-user
installs the dispatcher as `post-checkout` instead, superseding the
standalone `git-global-post-checkout.sh`. Still run step 2 (set
`core.hooksPath`) here.

1. **(Simple flavour only) Install the universal `post-checkout`
   hook.** Copy
   `tools/agent-isolation/git-global-post-checkout.sh` into
   `~/.claude/git-hooks/post-checkout` (or symlink it from
   `~/.claude-config/git-hooks/post-checkout` if the operator
   uses the private sync repo), mode `0755`. The hook content is
   in
   [`tools/agent-isolation/git-global-post-checkout.sh`](../../tools/agent-isolation/git-global-post-checkout.sh) —
   it calls the sandbox-allowlist helper for Claude-Code-aware
   worktrees.

2. **Set `core.hooksPath` globally** so every git operation across
   every repo on the host uses the shared hook dir:

   ```bash
   git config --global core.hooksPath "$HOME/.claude/git-hooks"
   ```

   Surface the resulting `git config --global --get core.hooksPath`
   value to the operator to confirm the write.

3. **Reiterate the implication** from Step P.0a's disclosure:
   per-repo `.git/hooks/*` are now inert across the entire host.
   The operator must migrate any per-repo hooks they want to keep.
   `git config --global --unset core.hooksPath` is the reversal.

After this step, future `git clone`, `git worktree add`, and
`git checkout` operations anywhere on the host invoke the
framework's universal post-checkout, which keeps each
Claude-Code-aware project's `.claude/settings.local.json` in
sync without any further operator action.

#### Step P.3b-whole-user — Install the per-repo dispatcher + prek shim (dispatcher flavour only)

Skip unless the operator picked the **dispatcher** flavour in
Step P.0b. This is what keeps the operator's per-repo hooks (prek,
pre-commit, husky, hand-written) firing under global
`core.hooksPath` — the shared dir runs the framework's logic **and
then chains through to each repo's own `.git/hooks/<name>`**. See
[`docs/setup/secure-agent-setup.md` → *Whole-user with the per-repo dispatcher*](../../docs/setup/secure-agent-setup.md#whole-user-with-the-per-repo-dispatcher)
for the full rationale + the validated behaviour matrix.

1. **Install the dispatcher for each hook type.** Copy
   [`tools/agent-isolation/git-hook-dispatcher.sh`](../../tools/agent-isolation/git-hook-dispatcher.sh)
   into `~/.claude/git-hooks/git-hook-dispatcher.sh` (or symlink
   from `~/.claude-config/git-hooks/` under the private sync repo),
   mode `0755`, then create one symlink per hook name pointing at
   it — including `post-checkout`, which replaces the standalone
   file from Step P.3 (the dispatcher runs the same sandbox sync,
   then chains to any repo-local `post-checkout`):

   ```bash
   cd ~/.claude/git-hooks
   for h in post-checkout pre-commit prepare-commit-msg commit-msg \
            post-commit pre-push post-merge post-rewrite \
            pre-rebase pre-merge-commit; do
     ln -sf git-hook-dispatcher.sh "$h"
   done
   ```

   The dispatcher is basename-keyed, so one file serves every hook
   type. It resolves the repo-local hook via
   `git rev-parse --git-common-dir` (worktree-safe) and `exec`s it
   with the original argv + inherited stdin, so a failing local
   `pre-commit` / `pre-push` still aborts the git operation.

2. **Install the `prek` PATH shim** so `prek install` writes its
   shim into the repo-local `.git/hooks/` (where the dispatcher
   chains) instead of the shared dir. Copy
   [`tools/agent-isolation/prek-shim.sh`](../../tools/agent-isolation/prek-shim.sh)
   into `~/.claude/bin/prek` (or symlink from
   `~/.claude-config/bin/prek`), mode `0755`. The shim rewrites
   only `prek install` (injecting
   `--git-dir "$(git rev-parse --git-common-dir)"` unless the caller
   already passed `--git-dir`, asked for `--help`, or is outside a
   git work tree); **every other `prek` invocation passes through
   unchanged**. It is a no-op on hosts with no global
   `core.hooksPath`.

3. **Surface the PATH line for the operator to add** to their
   `~/.bashrc` / `~/.zshrc` (per the golden rules — never edit the
   rc file directly):

   ```bash
   export PATH="$HOME/.claude/bin:$PATH"
   ```

   Confirm the rc path with the operator; print the line for them
   to paste. Until it is on PATH ahead of the real `prek`, the
   shim is inert and `prek install` reverts to writing into the
   shared dir.

4. **Tell the operator how their existing prek repos are picked up.**
   Repos that already ran `prek install` before this setup have
   their shim in `.git/hooks/pre-commit` already (that is where a
   pre-`core.hooksPath` `prek install` put it), so the dispatcher
   finds them with no further action. Repos where they run
   `prek install` *after* the global switch will now install
   locally via the shim. Only repos where the shim already landed
   in the shared dir (from a `prek install` run *while*
   `core.hooksPath` was set but *before* this dispatcher setup)
   need a one-time `prek install` re-run through the shim.

The `.` entry stays in the committed project-scope `allowRead`
regardless — the explicit absolute path in
`settings.local.json` is belt-and-braces, not a replacement. If
the harness ever stops resolving `.`, the explicit path still
covers the project; if `.` works correctly, the explicit entry is
redundant but harmless. The committed project-scope file is
**never** modified by the helper (machine-specific absolute paths
have no business in a file shared across contributors).

The helper is also invoked by `/magpie-setup adopt`,
`/magpie-setup upgrade`, and `/magpie-setup worktree-init` for
the same reason. The `post-checkout` git hook installed by
`/magpie-setup adopt` chains into the helper too, so new
worktrees added via `git worktree add` after this install pass
inherit access automatically — no operator action needed.

## After the install lands

Suggest two follow-up routines the user can wire later:

- `setup-isolated-setup-verify` — re-run after every Claude Code upgrade
  or settings-file edit, to confirm denials still fire as
  expected. The "did a denial silently turn into an allow?"
  signal is exactly what this skill exists for.
- `setup-isolated-setup-update` — periodic check for framework
  updates, pinned-tool upgrade candidates, and drift between the
  installed user-scope copies and the framework's
  source-of-truth. Recommend a per-Claude-Code-upgrade or
  monthly cadence, whichever comes first.

**Always propose shared-config sync once the install lands.**
Regardless of whether the operator already maintains the
`~/.claude-config` sync repo, proactively offer to run
`setup-shared-config-sync` as a follow-up:

- If the `~/.claude-config` sync repo is already in place, the
  skill commits + pushes the local modifications (the user-scope
  scripts, hooks, and settings this install just wired up) so the
  other machines pick them up.
- If the operator does **not** yet have `~/.claude-config`, the
  `setup-shared-config-sync` skill bootstraps it (clones the
  default private remote if it exists, or creates a fresh private
  remote and scaffolds the layout). Mention this so a first-time
  operator knows the follow-up will set sync up from scratch — the
  point of proposing it is precisely so the just-installed config
  does not stay machine-local.

Surface it as an offer for the operator to accept, not an
auto-run — the sync skill has its own confirmation gates before it
commits or pushes anything.
