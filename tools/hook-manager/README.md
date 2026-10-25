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
The shim takes the tool from the name it is installed under, rewrites only the install subcommand, and passes every other invocation through unchanged.
It leaves the install alone when the caller already chose a target, asked for help, or is not in a git work tree.

| Strategy | What the shim does | Status |
|---|---|---|
| `git-dir-flag` | Inserts `<flag> <common dir>` after the install subcommand (prek: `--git-dir`; prek refuses a bare install while a global `core.hooksPath` is set). | implemented |
| `hide-global-config` | Runs the install with `GIT_CONFIG_GLOBAL=/dev/null`, for a manager that writes to the common dir but refuses while a global `core.hooksPath` is set (pre-commit, lefthook). | planned |
| `hooks-path-env` | Runs the install with `GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=core.hooksPath`, `GIT_CONFIG_VALUE_0=<common dir>/hooks`, for a manager that writes into whatever `core.hooksPath` names (overcommit, CaptainHook). The value must be that absolute path: git treats an empty `core.hooksPath` as set, and hooks then resolve against the filesystem root. | planned |
| `none` | The manager already writes to the repository's own hooks directory whatever the global value (simple-git-hooks, cargo-husky, the JGit-based Maven plugins). | planned |

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
| Shim | per host, for the repositories the operator works in | `setup-isolated-setup-install` installs `~/.claude/bin/<tool>` only when such a repository uses the manager. |
| Verify check 19d | per repository | **n/a** for a project that does not use prek. |
| Default-home deny (`Edit(<default>/**)`) | per user | Always, for every registered manager: another repository's terminal commits run from that home. |
| Host home (dispatcher) | per user | Always, outside the sandbox, for every registered manager: an unused variable is harmless, a missed detection would let a bypassed command inherit the sandbox home. |

How prek configures itself, from its source (v0.5.7): it reads one project config per directory, `prek.toml`, then `.pre-commit-config.yaml`, then `.pre-commit-config.yml` (`crates/prek-consts/src/lib.rs`); searches upward from the current directory to the git root for the workspace root, and below it for nested project configs, honouring `.gitignore` and `.prekignore` (`crates/prek/src/workspace.rs`); takes `--config <path>` instead, which disables discovery and is baked into the installed hook; and reads a user-level `prek.toml` under the platform config directory that holds only update and display options, so it says nothing about whether a repository uses prek.
The two YAML names are shared with pre-commit, so a repository with one uses both managers as far as detection goes; configuring a home the repository's hooks do not end up using is harmless.

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
| `home` | Omitted for a manager that keeps nothing outside the repository. |
| `home.env` | The environment variable that relocates the home. |
| `home.default`, `home.sandbox`, `home.host` | The three directories above. |
| `home.expands_tilde` | Whether the manager expands a leading `~` in `home.env`; must be `true` today. |

[`tools/dev/sync-hook-managers.py`](../dev/sync-hook-managers.py) validates the registry against the rules and writes it into the implementations, which run where the registry is not available, as generated blocks:

- [`tools/agent-isolation/hook-manager-shim.sh`](../agent-isolation/hook-manager-shim.sh) — the install rewrite per tool;
- [`tools/agent-isolation/git-hook-dispatcher.sh`](../agent-isolation/git-hook-dispatcher.sh) — the host home per tool;
- [`tools/sandbox-lint/`](../sandbox-lint/) — `HOOK_MANAGER_HOMES`, which fails any settings file whose deny list lacks `Edit(<default>/**)`, and a project's settings file whose `env.<var>` is missing or overlaps the default home when the project uses the manager.

It also checks, without writing, that [`.claude/settings.json`](../../.claude/settings.json) and [`tools/sandbox-lint/expected.json`](../sandbox-lint/expected.json) deny every manager's default home and carry the sandbox home of each manager this repository uses.
It runs as the `sync-hook-managers` prek hook.

## Operations

The contract has no binary of its own.
Its operations are carried out by the scripts generated from the registry:

| Operation | Run by | Invocation | Behaviour |
|---|---|---|---|
| Install rewrite | [`hook-manager-shim.sh`](../agent-isolation/hook-manager-shim.sh), installed as `~/.claude/bin/<tool>` | `<tool> <install.subcommand> [args…]`, e.g. `prek install` | Applies the adapter's install strategy — for prek, runs `prek install --git-dir <absolute common dir> [args…]`. Left unchanged when `args` already carry the flag or `-h` / `--help`, or outside a git work tree. Every other subcommand passes through to the real binary, the next `<tool>` on `PATH` that is not the shim. Exits 127 when the name it is installed under has no adapter or no real binary is found. |
| Host home | [`git-hook-dispatcher.sh`](../agent-isolation/git-hook-dispatcher.sh), from `~/.claude/git-hooks/` | Every hook git runs, before it chains to the repository's own hook | Outside the sandbox (no `SANDBOX_RUNTIME`), exports `<home.env>=~/.local/share/<home.host>` for every registered manager unless the operator's value lies outside `~/.cache`, and moves `XDG_CACHE_HOME` to `~/.local/share/prek-host/cache` by the same rule. Sandboxed hooks keep their values. |
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
| `prek` | Rust | `git-dir-flag` (`--git-dir`); detected by `prek.toml`, `.pre-commit-config.yaml` or `.pre-commit-config.yml` (nested too) or a hook mentioning `prek` | `PREK_HOME`: `~/.cache/prek` → sandbox `~/.cache/prek-sandbox`, host `~/.local/share/prek-host` | shipping |

## Adding an adapter

1. Read the manager's source for the answers the registry needs — where its install writes and whether it honours, refuses or sets `core.hooksPath`; whether a `PATH` shim can reach the install; the home variable, its default, and whether it expands `~`; whether a hook run executes code from the home.
2. Add the adapter to `registry.json`. If it needs an install strategy the shim does not implement, add the strategy to the shim and to `STRATEGIES` in the generator in the same change.
3. Give the detection rules: the config file names, whether nested configs count, and a marker every hook it installs contains.
4. Deny the default home in `.claude/settings.json` and `tools/sandbox-lint/expected.json`, and, if this repository uses the manager, give the sandbox home in their `env`.
5. Run `tools/dev/sync-hook-managers.py`, then the agent-isolation, sandbox-lint and dev tests, and add a shim test for the new strategy.
6. Add a row above, and update the troubleshooting and verify pages if the manager brings a failure mode of its own.

## Consumers

- [`setup-isolated-setup-install`](../../plugins/magpie-setup/skills/isolated-setup-install/step-p-sandbox-allowlists.md) Step P.3b-whole-user installs the shim once per adapter the operator uses.
- [`setup-isolated-setup-verify`](../../plugins/magpie-setup/skills/isolated-setup-verify/SKILL.md) check 19 and [`setup-isolated-setup-update`](../../plugins/magpie-setup/skills/isolated-setup-update/SKILL.md) check the homes through `sandbox-lint`.
