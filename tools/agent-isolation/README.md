<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/agent-isolation/` — secure agent setup helpers](#toolsagent-isolation--secure-agent-setup-helpers)
  - [Files](#files)
  - [Usage at a glance](#usage-at-a-glance)
  - [Referenced by](#referenced-by)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/agent-isolation/` — secure agent setup helpers

This directory ships the moving pieces the framework's
[`docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md) document
references. It is not a Python project (unlike the sibling tools
under `tools/vulnogram/` and `tools/gmail/oauth-draft/`) — these are
plain shell scripts plus a TOML manifest of pinned upstream
versions.

## Files

| File | Purpose |
|---|---|
| [`pinned-versions.toml`](pinned-versions.toml) | Machine-readable manifest of pinned upstream versions for `bubblewrap`, `socat`, and `claude-code`. Each entry carries a `released` date that satisfies the framework's 7-day cooldown convention. |
| [`check-tool-updates.sh`](check-tool-updates.sh) | Reads the manifest and reports upstream releases that are newer than the pin AND have themselves aged past the 7-day cooldown. Side-effect-free — no installs, no edits, no PRs. |
| [`claude-iso.sh`](claude-iso.sh) | Shell function to launch Claude Code with `env -i` and a tiny passthrough list, stripping every credential-shaped environment variable from the parent shell. The framework's "layer 0" of the secure setup. |
| [`sandbox-bypass-warn.sh`](sandbox-bypass-warn.sh) | Claude Code `PreToolUse` hook (Bash matcher). Prints a bold-red banner to stderr whenever the model invokes the Bash tool with `dangerouslyDisableSandbox: true`. Belt-and-braces visibility for the sandbox-bypass permission prompt. Recommended user-scope (`~/.claude/settings.json`) so it fires across every session on the host. |
| [`sandbox-error-hint.sh`](sandbox-error-hint.sh) | Claude Code `PostToolUse` hook (Bash matcher). Scans the tool's stdout + stderr for the three known sandbox-shaped error signatures (SSH agent / Yubikey unreachable, loopback port-bind blocked, docker / podman socket denied) and prints a `[sandbox-hint]` line pointing at the matching entry in [`docs/setup/sandbox-troubleshooting.md`](../../docs/setup/sandbox-troubleshooting.md). Fail-open: any unexpected JSON shape exits silent. Recommended user-scope so the hint fires across every session. Complements `setup-isolated-setup-doctor` (the structured probe) by surfacing the catalog reference at the moment of failure, without the user having to remember the catalog exists. |
| [`sandbox-status-line.sh`](sandbox-status-line.sh) | Claude Code `statusLine` helper. Renders `<model> [sandbox]` (green) or `<model> [NO SANDBOX]` (bold red) based on `sandbox.enabled` in the active settings — project `settings.local.json` first, then project `settings.json`, then user-scope, mirroring Claude Code's own precedence. Reflects in-session `/sandbox` toggles (which persist to project `settings.local.json`). Recommended user-scope. |
| [`sandbox-status-line-rich.sh`](sandbox-status-line-rich.sh) | Opt-in richer alternative to `sandbox-status-line.sh`. Same sandbox-state detection, plus folder name (hash-coloured), git branch + dirty + ahead/behind, per-branch PR title (cached, gated by `gh`), and a yellow `[sandbox-auto]` tag for the `autoAllowBashIfSandboxed` setting. Wire one *or* the other into `statusLine.command`. |
| [`sandbox-add-project-root.sh`](sandbox-add-project-root.sh) | Adds the current adopter repo's project root (and, with `--all-worktrees`, every linked git worktree's working dir) as an explicit absolute path to `sandbox.filesystem.allowRead` and `allowWrite` in the project-local, gitignored `<repo>/.claude/settings.local.json` — one entry per worktree, each in that worktree's own settings file. Defensive against [issue #197](https://github.com/apache/airflow-steward/issues/197) — `allowRead: ["."]` does not in practice cover CWD because the harness pre-resolves the `.` literal away from the read side. Never modifies user-scope or committed project-scope. Idempotent, atomic, tolerant of missing prereqs. Invoked from `setup-isolated-setup-install`, `/setup-steward` (adopt / upgrade / worktree-init), and the `post-checkout` git hook installed by `/setup-steward adopt`. |
| [`git-global-post-checkout.sh`](git-global-post-checkout.sh) | Universal `post-checkout` git hook installed at `~/.claude/git-hooks/post-checkout` when the operator picks **whole-user** scope in `setup-isolated-setup-install`. Activated by `git config --global core.hooksPath ~/.claude/git-hooks/` so every `git checkout` / `git clone` / `git worktree add` across the host invokes it. Two responsibilities (both best-effort + idempotent + `\|\| true`): (1) `setup-steward verify --auto-fix-symlinks` for steward-adopted repos; (2) invoke `sandbox-add-project-root.sh` for any project with a `.claude/` directory. Trade-off documented in [`docs/setup/secure-agent-setup.md` → *Per-project vs whole-user scope*](../../docs/setup/secure-agent-setup.md#per-project-vs-whole-user-scope): `core.hooksPath` shadows per-repo `.git/hooks/*` across every repo on the host. |

## Usage at a glance

```bash
# Initial install (read pinned-versions.toml for the version pin):
sudo apt-get install --no-install-recommends bubblewrap=0.11.1-* socat=1.8.1.1-*
npm install -g --no-save @anthropic-ai/claude-code@2.1.117

# Source the wrapper into your shell:
source /path/to/airflow-steward/tools/agent-isolation/claude-iso.sh

# Optional: make claude-iso the default `claude` (see docs/setup/secure-agent-setup.md
# for the trade-off — the alias also strips env in non-tracker sessions):
alias claude='claude-iso'

# Launch a session with no inherited credentials:
cd ~/code/<tracker>
claude-iso

# Periodically (or via /schedule weekly), check for upgrade candidates:
bash /path/to/airflow-steward/tools/agent-isolation/check-tool-updates.sh
```

## Referenced by

- [`../../docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md) —
  the user-facing setup document. Read that first.
- [`../../.claude/settings.json`](../../.claude/settings.json) — the
  framework's own dogfooded secure config. Adopters scaffold their
  own version from the example block in `docs/setup/secure-agent-setup.md`.
