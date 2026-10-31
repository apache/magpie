<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [tools/hook-manager/](#toolshook-manager)
  - [Prerequisites](#prerequisites)
  - [Why a contract](#why-a-contract)
  - [The rules](#the-rules)
    - [Install target](#install-target)
    - [Home](#home)
    - [Detection](#detection)
  - [Registry](#registry)
  - [Operations](#operations)
  - [Configuration](#configuration)
  - [Adapters](#adapters)
    - [Verified runs](#verified-runs)
  - [Adding an adapter](#adding-an-adapter)
  - [Consumers](#consumers)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# tools/hook-manager/

**Capability:** contract:hook-manager

**Kind:** interface

**Vendor:** agnostic

This file defines the contract for **git-hook managers** — prek, pre-commit, lefthook, husky and their kin — under the [secure agent setup](../../docs/setup/secure-agent-setup.md).
A hook manager installs a script into a repository's hooks directory and, when git runs that hook, runs the checks the repository configured, often from environments it built and keeps outside the repository.
Both halves meet the sandbox: where the install writes, and where the environments live.
The contract states the two rules every manager must satisfy, and [`registry.json`](registry.json) records, per manager, how it satisfies them.

The secure setup does not *run* hook managers; it keeps them working, and keeps them from becoming a way out of the sandbox.
It configures a manager for a repository only where the repository uses it (see [Detection](#detection)): a repository that uses none gets no shim and no sandbox-home requirement. The protections of the per-user default and host homes apply everywhere.

## Prerequisites

- **Runtime:** None of its own — this file is a contract *specification* plus a JSON registry.
  The implementations are shell scripts (`tools/agent-isolation/`) and Python (`tools/sandbox-lint/`).
- **CLIs:** `git`; the hook manager itself is the operator's.
- **Credentials / auth:** None.
- **Network:** None.

## Why a contract

Under the whole-user flavour of the secure setup, `git config --global core.hooksPath ~/.claude/git-hooks/` makes git read hooks from one shared directory, where the [dispatcher](../agent-isolation/git-hook-dispatcher.sh) runs the framework's own hook logic and then chains to the repository's own `$(git rev-parse --git-common-dir)/hooks/<name>`.
Separately, the sandbox makes `~/.cache/` writable, and most hook managers keep their environments there.
Each manager meets those two facts differently — one writes into whatever `core.hooksPath` names, one refuses to install while it is set, one sets its own — so each needs its own fix, and the fixes must not drift apart.
The contract names the rules; the registry is the one place a manager's answers are written down; the implementations are generated from it.

## The rules

### Install target

A manager's install must put its hook in the repository's own `$(git rev-parse --git-common-dir)/hooks/`, never in the shared `core.hooksPath` directory, and must not leave a repository-level `core.hooksPath` behind.

- The shared directory belongs to the dispatcher. A manager that writes there replaces the dispatcher for every repository on the host.
- A repository-level `core.hooksPath` overrides the global one, so git never reaches the dispatcher, and with it the host-only home below.
  magpie-setup's session-start hook removes one that points at the repository's own `.git/hooks` and reports any other value.
- `--git-common-dir`, not `--git-dir`: a linked worktree shares its main checkout's hooks.

The fix is an **install strategy**, applied by [`hook-manager-shim.sh`](../agent-isolation/hook-manager-shim.sh), installed as `~/.claude/bin/<tool>` ahead of the real binary on `PATH`.
The shim takes the tool from the name it is installed under.
`git-dir-flag` rewrites only the install subcommand and leaves it alone when the caller already chose a target, asked for help, or is not in a git work tree.
`hooks-path-env` applies its override to every invocation, because a manager may accept the install command after global options or as an abbreviation; run commands ignore the override.
When `PATH` holds no real binary, the shim falls back to `<repository root>/vendor/bin/<tool>`, so a Composer project's local binary works without widening `PATH`.

| Strategy | What the shim does | Status |
|---|---|---|
| `git-dir-flag` | Inserts `<flag> <common dir>` after the install subcommand (prek: `--git-dir`; prek refuses a bare install while a global `core.hooksPath` is set). | implemented |
| `hide-global-config` | Runs the install with `GIT_CONFIG_GLOBAL=/dev/null`, for a manager that writes to the common dir but refuses while a global `core.hooksPath` is set (pre-commit, lefthook). | planned |
| `hooks-path-env` | On every invocation, appends `GIT_CONFIG_KEY_<n>=core.hooksPath` and `GIT_CONFIG_VALUE_<n>=<common dir>/hooks` at the next `GIT_CONFIG_COUNT`, for a manager that writes into whatever `core.hooksPath` names (overcommit, CaptainHook). Appending keeps any entries the caller already set. The value must be that absolute path: git treats an empty `core.hooksPath` as set, and hooks then resolve against the filesystem root. | implemented |
| `none` | The manager already writes to the repository's own hooks directory whatever the global value (simple-git-hooks, cargo-husky, the JGit-based Maven plugins). | implemented |

A manager whose install the shim cannot reach (one run from `node_modules/.bin` by an npm script, from `vendor/bin` by a composer plugin, or from a `build.rs`, all ahead of `~/.claude/bin` or off `PATH` entirely) needs a strategy outside the shim, and a manager that writes a repository-level `core.hooksPath` itself (husky on every `npm install`) needs the dispatcher to chain to that directory instead; the adapter issues name the candidates.

### Home

A hook that runs outside the sandbox must never run an environment a sandboxed command could have written.

A manager that keeps environments in a home outside the repository gets three directories:

| Directory | Who uses it | How |
|---|---|---|
| `default` (under `~/.cache/`) | The operator's terminal under per-project scope. | Sandboxed commands may not edit it: `permissions.deny` carries `Edit(<default>/**)`. |
| `sandbox` (under `~/.cache/`, disjoint from `default`) | Every command Claude Code runs. | The committed settings' `env.<var>`, which only Claude Code's commands see. |
| `host` (one directory under `~/.local/share/`) | Every hook the whole-user dispatcher runs outside the sandbox (no `SANDBOX_RUNTIME`). | The dispatcher exports `<var>=~/.local/share/<host>` for every registered manager unless the operator chose a value outside `~/.cache`. |

`~/.local/share/` is outside every sandbox write grant, so nothing sandboxed can plant code in the host home.
The committed settings can name a per-user directory only with `~`, so the contract requires a manager whose home variable is relative to `~` to expand it (`expands_tilde: true`); one that does not needs the sandbox home written as an absolute path into the per-user `settings.local.json`, which no adapter does yet.

### Detection

A repository **uses** a hook manager when any of these holds:

1. One of the manager's config files sits at the repository root.
2. For a manager with nested project configs (prek's workspace mode), one of its config files is tracked anywhere below the root (`git ls-files ':(glob)**/<name>'`). An untracked nested file does not count.
3. One of the repository's installed hooks (`$(git rev-parse --git-common-dir)/hooks/*`, samples aside) contains the manager's hook marker. This covers an install with a custom config path (`prek install --config ci/hooks.yaml` leaves no standard file name behind) and one made from a nested project.

Detection decides what the setup configures *for a repository*; it never decides a per-user protection, since a manager's default and host homes are shared by every repository on the host, and a hook can reach a manager detection does not see (through a script):

| Integration | Scope | Rule |
|---|---|---|
| Sandbox home (`env.<var>`) | per repository | `sandbox-lint` (`uses_hook_manager`) requires it only for a project that uses the manager; with no project to look at, every manager counts. A project without it is still safe: its sandboxed runs of the manager fail on the denied default home. The generator checks the framework's own settings the same way, from the root config files. |
| Shim | per host, for the repositories the operator works in | `setup-isolated-setup-install` installs `~/.claude/bin/<tool>` only when such a repository uses the manager, and only for adapters with an install strategy other than `none` (managers requiring no install fix need no shim). |
| Verify check 19d | per repository | **n/a** for a project that does not use prek. |
| Default-home deny (`Edit(<default>/**)`) | per user | Always, for every registered manager: another repository's terminal commits run from that home. |
| Host home (dispatcher) | per user | Always, outside the sandbox, for every registered manager: an unused variable is harmless, a missed detection would let a bypassed command inherit the sandbox home. |

How prek configures itself, from its source (v0.5.7): it reads one project config per directory, `prek.toml`, then `.pre-commit-config.yaml`, then `.pre-commit-config.yml` (`crates/prek-consts/src/lib.rs`); searches upward from the current directory to the git root for the workspace root, and below it for nested project configs, honouring `.gitignore` and `.prekignore` (`crates/prek/src/workspace.rs`); takes `--config <path>` instead, which disables discovery and is baked into the installed hook; and reads a user-level `prek.toml` under the platform config directory that holds only update and display options, so it says nothing about whether a repository uses prek.
The two YAML names are shared with pre-commit, so a repository with one uses both managers as far as detection goes; configuring a home the repository's hooks do not end up using is harmless.

How CaptainHook configures itself, from its source (v5.29.2): it reads `captainhook.json` at the repository root, or the path given with `--configuration`.
`Repository::getHooksDir()` reads `git config --get core.hooksPath` (`Command/Config/Get.php:53`), uses an absolute value as-is, and refuses only `/dev/null` (`Installer.php:291-296`), so under the whole-user setup an unshimmed install writes into the shared dispatcher directory.
A relative value is joined to the repository root; in a linked worktree with no `core.hooksPath` the hooks dir is built from the worktree's absolute gitdir, which does not exist (`Repository.php:88-101`).
The `hooks-path-env` override fixes both, because the install then reads the common dir's `hooks` as an absolute value.
`vendor/bin/captainhook` is not on `PATH`, so the shim falls back to `<repository root>/vendor/bin/captainhook` when its `PATH` walk finds no real binary; `~/.claude/bin/captainhook install` therefore works from anywhere in the repository, including a linked worktree.
The `captainhook/hook-installer` Composer plugin still installs on every `composer install` and `composer update`, outside the shim.
The documented path is one explicit `~/.claude/bin/captainhook install` from the repository root after a clone, with `extra.captainhook.disable-plugin` set to `true` in `composer.json` so the plugin does not install into the shared directory behind the shim's back.
When `composer.json` requires the plugin and does not set `disable-plugin`, an install through the shim warns on stderr that the next dependency update will undo it.
The generated shell and PHP templates run the binary and configuration through repository-relative paths and rely on git running hooks from the top level, which the dispatcher keeps; the PHP template additionally derives `.git` from the hook file's location (`Local/PHP.php:84`), so check it from the common dir in a linked worktree.
`CAPTAINHOOK_SKIP_HOOKS=1` skips a run.

## Registry

[`registry.json`](registry.json) holds one adapter per manager under `adapters.<binary name>`:

| Field | Meaning |
|---|---|
| `language` | The ecosystem the manager comes from (for the reader, not the implementation). |
| `upstream` | The manager's source repository. |
| `detect.config_files` | The config file names that say a repository uses it (bare names, no directories). |
| `detect.nested` | Whether a tracked config below the root counts (rule 2 of [Detection](#detection)). |
| `detect.hook_marker` | Text every hook the manager installs contains (rule 3). |
| `install.subcommand` | The subcommand the shim rewrites. |
| `install.strategy` | One of the install strategies above. |
| `install.flag` | For `git-dir-flag`: the long option that takes the git directory. |
| `install.runtime_env` | For `hooks-path-env`: also give every hook run the same `core.hooksPath` override, so a manager that re-checks its install at run time accepts the chained hook. |
| `home` | Omitted for a manager that keeps nothing outside the repository. |
| `home.env` | The environment variable that relocates the home. |
| `home.default`, `home.sandbox`, `home.host` | The three directories above. |
| `home.expands_tilde` | Whether the manager expands a leading `~` in `home.env`; must be `true` today. |

[`tools/dev/sync-hook-managers.py`](../dev/sync-hook-managers.py) validates the registry against the rules and writes it into the implementations, which run where the registry is not available, as generated blocks:

- [`tools/agent-isolation/hook-manager-shim.sh`](../agent-isolation/hook-manager-shim.sh) — the install rewrite per tool;
- [`tools/agent-isolation/git-hook-dispatcher.sh`](../agent-isolation/git-hook-dispatcher.sh) — the host home and run-time override per tool;
- [`tools/sandbox-lint/`](../sandbox-lint/) — `HOOK_MANAGER_HOMES`, which fails any settings file whose deny list lacks `Edit(<default>/**)`, and a project's settings file whose `env.<var>` is missing or overlaps the default home when the project uses the manager.

It also checks, without writing, that [`.claude/settings.json`](../../.claude/settings.json) and [`tools/sandbox-lint/expected.json`](../sandbox-lint/expected.json) deny every manager's default home and carry the sandbox home of each manager this repository uses.
It runs as the `sync-hook-managers` prek hook.

## Operations

The contract has no binary of its own.
Its operations are carried out by the scripts generated from the registry:

| Operation | Run by | Invocation | Behaviour |
|---|---|---|---|
| Install rewrite | [`hook-manager-shim.sh`](../agent-isolation/hook-manager-shim.sh), installed as `~/.claude/bin/<tool>` | `<tool> [args…]`, e.g. `prek install`, `overcommit --install`, `captainhook -n install` or `captainhook inst` | Applies the adapter's install strategy. For `git-dir-flag` (prek), runs `prek install --git-dir <absolute common dir> [args…]`, left unchanged when the args already carry the target flag or `-h` / `--help`, or outside a git work tree. For `hooks-path-env` (overcommit, CaptainHook), points `core.hooksPath` at `<absolute common dir>/hooks` on every invocation, so the install lands there however the manager spells the command, and run commands ignore the override. The real binary is the next `<tool>` on `PATH` that is not the shim, or `<repository root>/vendor/bin/<tool>` when the walk finds none. Exits 127 when the name it is installed under has no adapter or no real binary is found. |
| Host home and run-time override | [`git-hook-dispatcher.sh`](../agent-isolation/git-hook-dispatcher.sh), from `~/.claude/git-hooks/` | Every hook git runs, before it chains to the repository's own hook | Outside the sandbox (no `SANDBOX_RUNTIME`), exports `<home.env>=~/.local/share/<home.host>` for every registered manager unless the operator's value lies outside `~/.cache`, and moves `XDG_CACHE_HOME` to `~/.local/share/prek-host/cache` by the same rule. Sandboxed hooks keep their values. Before chaining to a hook whose marker matches an adapter with `install.runtime_env`, exports the same `core.hooksPath` override the shim used, so the manager's own run-time check accepts the hook. |
| Home check | [`sandbox-lint`](../sandbox-lint/) | `uv run --project tools/sandbox-lint sandbox-lint` | Fails a settings file whose `permissions.deny` lacks `Edit(<home.default>/**)` for any registered manager, and, for a project that uses a manager (see [Detection](#detection)), one whose `env.<home.env>` is missing or overlaps the default home. |
| Registry sync | [`tools/dev/sync-hook-managers.py`](../dev/sync-hook-managers.py) | `tools/dev/sync-hook-managers.py [--check]`; the `sync-hook-managers` prek hook | Validates `registry.json`, rewrites the generated blocks of the three scripts above, and checks the committed settings and the sandbox-lint baseline. Exits 1 when a block changed (re-stage and commit), or, with `--check`, when one would. |

## Configuration

The registry is framework-side: an adopter does not edit it.
What a repository or an operator configures is where each manager's environments live and which binary answers to the manager's name:

| Setting | Where | Value for prek | Required |
|---|---|---|---|
| `permissions.deny` entry `Edit(<home.default>/**)` | `.claude/settings.json` (and `tools/sandbox-lint/expected.json` in this repository) | `Edit(~/.cache/prek/**)` | Always, for every registered manager. |
| `env.<home.env>` | `.claude/settings.json` | `"PREK_HOME": "~/.cache/prek-sandbox"` | Only when the repository uses the manager; it must not overlap the default home. |
| `<home.env>` in the operator's environment | the shell the operator commits from | unset, or a directory outside `~/.cache` | Optional: a value outside `~/.cache` is kept by the dispatcher; one under it is replaced with the host home. |
| `PATH` | the operator's shell profile | `~/.claude/bin` ahead of the real `prek` | Only under whole-user scope, where the shim is installed; removing `~/.claude/bin` from `PATH` restores the stock binary. |

[`setup-isolated-setup-install`](../../plugins/magpie-setup/skills/isolated-setup-install/SKILL.md) brings in the first two with its copy of the framework's `.claude/settings.json` and the `PATH` entry in [Step P](../../plugins/magpie-setup/skills/isolated-setup-install/step-p-sandbox-allowlists.md); `sandbox-lint` checks the first two.

## Adapters

| Adapter | Language | Install strategy | Home | Status |
|---|---|---|---|---|
| `captainhook` | PHP | `hooks-path-env` (`install`); detected by `captainhook.json` or a hook mentioning `CaptainHook` | none (no external home) | shipping (verified: v5.29.2 on PHP 8.5.12 with Composer 2.11.1; the install through the shim uses the `vendor/bin` fallback and writes the repository's own hooks, and a bare install replaces the shared dispatcher) |
| `cargo-husky` | Rust | `none`; detected by a hook mentioning `cargo-husky` | none (no external home) | shipping (in linked worktrees `build.rs` skips hook install: searches for a `.git` directory) |
| `git-build-hook` | Java | `none`; detected by `pom.xml` (nested too) or a hook mentioning `git-build-hook` | none (no external home) | shipping (JGit `getGitDir()` targets `<worktree>/hooks` in linked worktrees; `configure` goal can set repo-local `core.hooksPath`) |
| `git-code-format-maven-plugin` | Java | `none`; detected by `pom.xml` (nested too) or a hook mentioning `git-code-format-maven-plugin` | none (no external home) | shipping (JGit `getCommonDirectory()` targets common hooks dir, coexisting cleanly in linked worktrees) |
| `prek` | Rust | `git-dir-flag` (`--git-dir`); detected by `prek.toml`, `.pre-commit-config.yaml` or `.pre-commit-config.yml` (nested too) or a hook mentioning `prek` | `PREK_HOME`: `~/.cache/prek` → sandbox `~/.cache/prek-sandbox`, host `~/.local/share/prek-host` | shipping |
| `overcommit` | Ruby | `hooks-path-env` (`--install`); detected by `.overcommit.yml` or a hook mentioning `overcommit` | none — it keeps its own state in git config and the repository | shipping |
| `simple-git-hooks` | JavaScript | `none`; detected by `package.json`, `.simple-git-hooks.{js,cjs,json}`, `simple-git-hooks.{js,cjs,json}` or a hook mentioning `simple-git-hooks` | none (no external home) | shipping |

*Ecosystem notes:*
- **Behavior and verification under whole-user dispatcher:**
  - `simple-git-hooks` (v2.14.0, empirically verified):
    Installs to `$(git rev-parse --git-common-dir)/hooks/` directly, ignoring global `core.hooksPath`.
    Commits chain through the dispatcher to the local hook.
    In linked worktrees, commits chain through the dispatcher to the common hooks directory, and running install within a worktree resolves `commondir` without error.
  - `cargo-husky` (v1.5.0, empirically verified):
    Installs to `.git/hooks/pre-push` via `build.rs`.
    Commits and pushes chain through the dispatcher.
    In a linked worktree, `build.rs` expects `.git` to be a directory.
    Encountering a worktree `.git` file, it logs `Warning: .git directory was not found` to stderr and skips hook installation without failing the build.
    Detection relies solely on installed hook markers (`config_files: []`) so generic Rust checkouts with `Cargo.toml` are not falsely detected as `cargo-husky` repos.
  - `git-build-hook` (v3.6.0, verified from upstream source):
    Installs hooks directly into JGit's `Repository.getGitDir() + "/hooks"` (`InstallMojo.java:53`).
    Commits in the main checkout chain through the dispatcher.
    In linked worktrees, `getGitDir()` evaluates to `<commondir>/worktrees/<name>`, placing hooks in `<worktree>/hooks/` which C-git ignores on commit.
    Running `mvn git-build-hook:configure` can write a repo-local `core.hooksPath`, overriding the dispatcher.
  - `git-code-format-maven-plugin` (`com.cosium.code:git-code-format-maven-plugin` 5.3, verified from upstream source):
    `AbstractMavenGitCodeFormatMojo.getOrCreateHooksDirectory()` uses `gitRepository().getCommonDirectory().toPath().resolve(HOOKS_DIR)`.
    Because it targets the common directory, hooks land in `$(git rev-parse --git-common-dir)/hooks/` and coexist cleanly in linked worktrees.
    Installs a bash wrapper invoking `mvn git-code-format-maven-plugin:format-code`.
- **JGit in linked worktrees (Maven):**
  The linked-worktree limitation applies only to `git-build-hook` (`InstallMojo`), which uses `getGitDir()` and creates hooks under `<commondir>/worktrees/<name>/hooks/`.
  Because C-git commits read hooks exclusively from `$(git rev-parse --git-common-dir)/hooks/`, hooks installed by `git-build-hook` from within a worktree are ignored by Git.
  Conversely, `git-code-format-maven-plugin` explicitly calls `getCommonDirectory()`, so its hooks populate the common directory and function across worktrees.
- **Gradle & Go hook tools:**
  Standard Gradle plugins and Go hook utilities remain unadapted and unregistered until someone tests them under the dispatcher.
  `lefthook` (Go) refuses install when a global `core.hooksPath` is set and is reserved for the planned `hide-global-config` install strategy.

### Verified runs

An install strategy is written from the manager's source. Where a run against the real manager confirmed it, the run is recorded here, with the controls that show what fails without the adapter.

- **`overcommit`, v0.73.0 on Ruby 3.2.3, Ubuntu 24.04, whole-user dispatcher.** `overcommit --install` through the shim wrote `<common dir>/hooks/` (a hook carrying the `overcommit` marker) and left `~/.claude/git-hooks/` identical — no `overcommit-hook` in it, no `old-hooks/`, the global `core.hooksPath` unchanged, and no repository-level `core.hooksPath` left behind. A commit behind the dispatcher ran the repository's own `.overcommit.yml`: its `PreCommit` `TrailingWhitespace` hook rejected a trailing-whitespace commit, and a clean commit went through with no self-update failure.
  Both controls fail without the adapter, which is why it needs a strategy of its own. A bare `overcommit --install` (no shim) installs *into* the shared dir and moves the dispatcher's symlinks aside — `Hook '…/pre-commit' already exists and was not installed by Overcommit. Moving to '…/.claude/git-hooks/old-hooks'` — and a correct install under a dispatcher that does not export the run-time override dies in overcommit's own check with `No such file or directory @ rb_file_s_size - ~/.claude/git-hooks/overcommit-hook` (`installer.rb:59`, `compare_file`).
- **`captainhook`, v5.29.2 on PHP 8.5.12, Composer 2.11.1 and git 2.54.0 in a `composer:2` container, whole-user dispatcher.** The global `core.hooksPath` named a shared dir with `git-hook-dispatcher.sh` symlinked under every hook name; the repository required `captainhook/captainhook` through Composer, so its binary was only at `vendor/bin/captainhook`. `~/.claude/bin/captainhook install` exited 0 through the shim: it found the binary with the `vendor/bin` fallback, installed `pre-commit` (525 bytes, carrying the CaptainHook marker) and the other hooks in the repository's own `.git/hooks/`, left every shared symlink and the global `core.hooksPath` unchanged, and created no `old-hooks/`. A commit behind the dispatcher ran the repository's own `captainhook.json`: its `pre-commit` `Exists` action failed on the missing file, printed `Error: 1 file(s) could not be found`, and the commit was rejected.
  The control fails without the adapter. A bare `vendor/bin/captainhook install` with the shim removed from `PATH` wrote through the shared dispatcher symlinks, so `git-hook-dispatcher.sh` became CaptainHook's last-installed hook instead of the dispatcher. The next commit did not run the repository's own hook and died inside the wrong CaptainHook subcommand.

## Adding an adapter

1. Read the manager's source for the answers the registry needs — where its install writes and whether it honours, refuses or sets `core.hooksPath`; whether a `PATH` shim can reach the install; the home variable, its default, and whether it expands `~`; whether a hook run executes code from the home.
2. Add the adapter to `registry.json`. If it needs an install strategy the shim does not implement, add the strategy to the shim and to `STRATEGIES` in the generator in the same change.
3. Give the detection rules: the config file names, whether nested configs count, and a marker every hook it installs contains.
4. Deny the default home in `.claude/settings.json` and `tools/sandbox-lint/expected.json`, and, if this repository uses the manager, give the sandbox home in their `env`.
5. Run `tools/dev/sync-hook-managers.py`, then the agent-isolation, sandbox-lint and dev tests, and add shim and dispatcher tests for the new strategy.
6. Add a row above, and update the troubleshooting and verify pages if the manager brings a failure mode of its own.
7. Exercise the adapter against the real manager — the install through the shim and a commit behind the dispatcher, plus the control that fails without it — and record the run under [Verified runs](#verified-runs).

## Consumers

- [`setup-isolated-setup-install`](../../plugins/magpie-setup/skills/isolated-setup-install/step-p-sandbox-allowlists.md) Step P.3b-whole-user installs the shim once per adapter the operator uses.
- [`setup-isolated-setup-verify`](../../plugins/magpie-setup/skills/isolated-setup-verify/SKILL.md) check 19 and [`setup-isolated-setup-update`](../../plugins/magpie-setup/skills/isolated-setup-update/SKILL.md) check the homes through `sandbox-lint`.
