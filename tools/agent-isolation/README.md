<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/agent-isolation/` — secure agent setup helpers](#toolsagent-isolation--secure-agent-setup-helpers)
  - [Prerequisites](#prerequisites)
  - [Files](#files)
  - [Usage at a glance](#usage-at-a-glance)
  - [Referenced by](#referenced-by)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/agent-isolation/` — secure agent setup helpers

**Capability:** substrate:sandbox

**Harness:** Claude Code, OpenCode

This directory ships the moving pieces the framework's
[`docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md) document
references. It is not a Python project (unlike the sibling tools
under `tools/cve-tool-vulnogram/` and `tools/gmail/oauth-draft/`) — these are
plain shell scripts plus a TOML manifest of pinned upstream
versions.

The clean-environment launcher [`agent-iso.sh`](agent-iso.sh) is
agent-agnostic at its core: it exposes a `claude-iso` entry point (the
default) and an `opencode-iso` entry point that launch **Claude Code** and
**OpenCode** respectively under the same `env -i` credential strip. Only the
Claude path adds the in-process `--settings` sandbox grant; OpenCode takes its
filesystem isolation from the OS-level sandbox of the secure setup. Isolate
OpenCode by sourcing the script and calling `opencode-iso`, or when running it
directly, `AGENT_ISO_AGENT=opencode bash agent-iso.sh …` (or a symlink named
`opencode-iso`).

## Prerequisites

- **Runtime:** Bash + coreutils — this directory is plain shell scripts plus a TOML manifest, not a Python project (the `pyproject.toml` ships only the test harness, which runs under Python 3.11+ via `uv`). `claude-term-bg.sh` uses `python3` / `python` for one heuristic and falls back to calm when absent.
- **CLIs:** `jq` (required by `check-tool-updates.sh` and the status-line scripts), `curl` (the update check), `git` (status line / git hooks), and `gh` (optional — status-line PR title). The secure setup itself installs the pinned `bubblewrap` and `socat` (via `apt-get`) and `@anthropic-ai/claude-code` (via `npm`).
- **Credentials / auth:** None for these helpers; the wrapped `claude` session authenticates on its own (and `agent-iso.sh` deliberately strips credential-shaped env vars).
- **Network:** `api.github.com` and `www.dest-unreach.org` (the release checks in `check-tool-updates.sh`); the install step also reaches the apt and npm registries.

## Files

| File | Purpose |
|---|---|
| [`pinned-versions.toml`](pinned-versions.toml) | Machine-readable manifest of pinned upstream versions for `bubblewrap`, `socat`, and `claude-code`. Each entry carries a `released` date that satisfies the framework's 7-day cooldown convention. |
| [`check-tool-updates.sh`](check-tool-updates.sh) | Reads the manifest and reports upstream releases that are newer than the pin AND have themselves aged past the 7-day cooldown. Side-effect-free — no installs, no edits, no PRs. |
| [`agent-iso.sh`](agent-iso.sh) | Shell function to launch Claude Code with `env -i` and a tiny passthrough list, stripping every credential-shaped environment variable from the parent shell. The framework's "layer 0" of the secure setup. |
| [`sandbox-bypass-warn.sh`](sandbox-bypass-warn.sh) | Claude Code `PreToolUse` hook (Bash matcher). Prints a bold-red banner to stderr whenever the model invokes the Bash tool with `dangerouslyDisableSandbox: true`. Belt-and-braces visibility for the sandbox-bypass permission prompt. Recommended user-scope (`~/.claude/settings.json`) so it fires across every session on the host. |
| [`sandbox-error-hint.sh`](sandbox-error-hint.sh) | Claude Code `PostToolUse` hook (Bash matcher). Scans the tool's stdout + stderr for the three known sandbox-shaped error signatures (SSH agent / Yubikey unreachable, loopback port-bind blocked, docker / podman socket denied) and prints a `[sandbox-hint]` line pointing at the matching entry in [`docs/setup/sandbox-troubleshooting.md`](../../docs/setup/sandbox-troubleshooting.md). Fail-open: any unexpected JSON shape exits silent. Recommended user-scope so the hint fires across every session. Complements `setup-isolated-setup-doctor` (the structured probe) by surfacing the catalog reference at the moment of failure, without the user having to remember the catalog exists. |
| [`sandbox-status-line.sh`](sandbox-status-line.sh) | Claude Code `statusLine` helper. Renders `<model> [sandbox]` (green) or `<model> [NO SANDBOX]` (bold red) based on `sandbox.enabled` in the active settings — project `settings.local.json` first, then project `settings.json`, then user-scope, mirroring Claude Code's own precedence. Reflects in-session `/sandbox` toggles (which persist to project `settings.local.json`). Recommended user-scope. |
| [`sandbox-status-line-rich.sh`](sandbox-status-line-rich.sh) | Opt-in richer alternative to `sandbox-status-line.sh`. Same sandbox-state detection, plus folder name (hash-coloured), git branch + dirty + ahead/behind, per-branch PR title (cached, gated by `gh`), and a yellow `[sandbox-auto]` tag for the `autoAllowBashIfSandboxed` setting. Wire one *or* the other into `statusLine.command`. |
| [`claude-term-bg.sh`](claude-term-bg.sh) | **Opt-in quality-of-life helper (not a security control).** Keeps a calm baseline background and tints it only when Claude genuinely wants you to act (never while working, and never when it merely *finished* a turn), so a window you've tabbed away from can't sit blocked unnoticed. Distinguishes "blocked on a decision" from "finished and idle" — which look identical at the `Stop` event — via three signals across six hooks: `Stop` → `stop` (heuristic — tints only if the final assistant message reads as a question/request; a completion stays calm; needs `python3`/`python`, else defaults calm); `PreToolUse` (matcher `AskUserQuestion`) → `wait` (exact — a structured question was posed); `PostToolUse` (matcher `*`) → `reset` (calm while working, and clears the tint the instant you approve a permission prompt or answer a question); `Notification` → `notify` (tints for permission prompts only — the plain idle ping is a no-op so it can't wipe a pending question's tint); and `UserPromptSubmit` + `SessionStart` → `reset` (you replied / fresh session clears any stale tint). Writes the OSC escape to the Claude pty discovered by walking the process tree (hooks have no controlling tty); the only deterministic reset is an explicit `CLAUDE_RESET_BG` colour via OSC 11 (iTerm2 ignores OSC 111). Colours overridable via `CLAUDE_WAIT_BG` / `CLAUDE_RESET_BG`. Tested on iTerm2 + macOS; fail-soft elsewhere. See [`docs/setup/secure-agent-setup.md` → *Waiting-for-input terminal tint*](../../docs/setup/secure-agent-setup.md#waiting-for-input-terminal-tint). |
| [`sandbox-add-project-root.sh`](sandbox-add-project-root.sh) | Adds the current adopter repo's project root (and, with `--all-worktrees`, every linked git worktree's working dir) as an explicit absolute path to `sandbox.filesystem.allowRead` and `allowWrite` in the project-local, gitignored `<repo>/.claude/settings.local.json` — one entry per worktree, each in that worktree's own settings file. Defensive against [issue #197](https://github.com/apache/magpie/issues/197) — `allowRead: ["."]` does not in practice cover CWD because the harness pre-resolves the `.` literal away from the read side. Never modifies user-scope or committed project-scope. Idempotent, atomic, tolerant of missing prereqs. Invoked from `setup-isolated-setup-install`, `/magpie-setup` (adopt / upgrade / worktree-init), and the `post-checkout` git hook installed by `/magpie-setup adopt`. |
| [`git-global-post-checkout.sh`](git-global-post-checkout.sh) | Universal `post-checkout` git hook installed at `~/.claude/git-hooks/post-checkout` when the operator picks **whole-user** scope in `setup-isolated-setup-install`. Activated by `git config --global core.hooksPath ~/.claude/git-hooks/` so every `git checkout` / `git clone` / `git worktree add` across the host invokes it. Two responsibilities (both best-effort + idempotent + `\|\| true`): (1) `setup verify --auto-fix-symlinks` for Magpie-adopted repos; (2) invoke `sandbox-add-project-root.sh` for any project with a `.claude/` directory. Trade-off documented in [`docs/setup/secure-agent-setup.md` → *Per-project vs whole-user scope*](../../docs/setup/secure-agent-setup.md#per-project-vs-whole-user-scope): `core.hooksPath` shadows per-repo `.git/hooks/*` across every repo on the host. |

## Usage at a glance

```bash
# Initial install (read pinned-versions.toml for the version pin):
sudo apt-get install --no-install-recommends bubblewrap=0.11.1-* socat=1.8.1.1-*
npm install -g --no-save @anthropic-ai/claude-code@2.1.117

# Source the wrapper into your shell:
source /path/to/magpie/tools/agent-isolation/agent-iso.sh

# Optional: make claude-iso the default `claude` (see docs/setup/secure-agent-setup.md
# for the trade-off — the alias also strips env in non-tracker sessions):
alias claude='claude-iso'

# Launch a session with no inherited credentials:
cd ~/code/<tracker>
claude-iso

# Periodically (or via /schedule weekly), check for upgrade candidates:
bash /path/to/magpie/tools/agent-isolation/check-tool-updates.sh
```

## Referenced by

- [`../../docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md) —
  the user-facing setup document. Read that first.
- [`../../.claude/settings.json`](../../.claude/settings.json) — the
  framework's own dogfooded secure config. Adopters scaffold their
  own version from the example block in `docs/setup/secure-agent-setup.md`.
