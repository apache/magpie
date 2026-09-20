<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/agent-isolation/` — secure agent setup helpers](#toolsagent-isolation--secure-agent-setup-helpers)
  - [Prerequisites](#prerequisites)
  - [Files](#files)
  - [Usage at a glance](#usage-at-a-glance)
  - [Explicit environment opt-in](#explicit-environment-opt-in)
  - [Referenced by](#referenced-by)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/agent-isolation/` — secure agent setup helpers

**Capability:** substrate:sandbox

**Harness:** agnostic

One exception to that tag:
[`sandbox-status-line.sh`](sandbox-status-line.sh) is Claude Code only.
Every other script here is harness-agnostic.

This directory ships the moving pieces the framework's
[`docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md) document
references. It is not a Python project (unlike the sibling tools
under `tools/cve-tool-vulnogram/` and `tools/gmail/oauth-draft/`) — these are
plain shell scripts plus a TOML manifest of pinned upstream
versions.

The clean-environment launcher [`agent-iso.sh`](agent-iso.sh) provides
harness-agnostic env isolation. It exposes four entry points, all sharing
the same `env -i` credential-strip core:

- **`claude-iso`** — launches Claude Code; additionally injects a one-shot
  `--settings` sandbox `allowRead` grant for the current repo (Claude-specific).
- **`opencode-iso`** — launches OpenCode with the same clean env; no settings
  grant (OpenCode takes its filesystem isolation from the OS-level sandbox).
- **`kiro-iso`** — launches Kiro CLI (the `kiro` name normalises to its
  `kiro-cli` binary) with the same clean env; like OpenCode, it takes its
  filesystem isolation from the OS-level sandbox (no `--settings` grant).
- **`agent-iso <cli>`** — launches *any* agentic CLI (`codex`, `cursor`,
  `gemini`, `aider`, …) with the same credential strip. The `--settings`
  injection is skipped for non-Claude CLIs, which take their filesystem
  isolation from the OS-level sandbox. The `-w` / `--worktree` flag is a
  Claude-only control flag and is stripped from the argv of non-Claude CLIs
  (it has no meaning for them). The Layer 0 env passthrough (including
  `SSH_AUTH_SOCK`) is identical for every harness per
  [RFC-AI-0002 § Layer 0](https://magpie.apache.org/docs/rfcs/rfc-ai-0002/#layer-0--clean-env-wrapper);
  gating git push is a separate Layer 3 concern wired per-harness (see
  [`docs/adapters/add-a-harness.md`](../../docs/adapters/add-a-harness.md)).

All entry points enforce layer 0 of the secure-agent posture regardless of
which harness drives the session. Harness-specific layers (the in-process
action guard, the `permissions.ask` confirmation list) are wired separately
per runtime — see [`docs/adapters/add-a-harness.md`](../../docs/adapters/add-a-harness.md).

> ⚠️ **Generic harnesses (`agent-iso <cli>`) get Layer 0 only — no push gate.**
> Claude and OpenCode ship a Layer 3 push gate (agent-guard / `permissions.ask`),
> so a `git push` from those harnesses is gated. An arbitrary CLI launched via
> `agent-iso` (`codex`, `aider`, …) receives the live `SSH_AUTH_SOCK` with
> **nothing gating `git push`**. The credential-strip posture is identical across
> harnesses, but the *net* protection is weaker: a runtime with no Layer 3 adapter
> is responsible for providing its own push gate before it is trusted with the
> agent socket.

## Prerequisites

- **Runtime:** Bash + coreutils — this directory is plain shell scripts plus a TOML manifest, not a Python project (the `pyproject.toml` ships only the test harness, which runs under Python 3.11+ via `uv`). `claude-term-bg.sh` uses `python3` / `python` for one heuristic and falls back to calm when absent.
- **CLIs:** `jq` (required by `check-tool-updates.sh` and the status-line scripts), `curl` (the update check), `git` (status line / git hooks), and `gh` (optional — status-line PR title). The secure setup itself installs the pinned `bubblewrap` and `socat` (via `apt-get`) and `@anthropic-ai/claude-code@latest` (via `npm` — the agent harness is intentionally unpinned; see [`pinned-versions.toml`](pinned-versions.toml)).
- **Credentials / auth:** None for these helpers; the wrapped runtime authenticates separately. For authentication requiring environment variables, use the explicit opt-in below.
- **Network:** `api.github.com` and `www.dest-unreach.org` (the release checks in `check-tool-updates.sh`); the install step also reaches the apt and npm registries.

## Files

| File | Purpose |
|---|---|
| [`pinned-versions.toml`](pinned-versions.toml) | Machine-readable manifest of pinned upstream versions for the sandbox primitives `bubblewrap` and `socat`. Each entry carries a `released` date that satisfies the framework's 7-day cooldown convention. `claude-code` is deliberately **not** pinned — the agent harness installs at `@latest` so it always carries the newest permission-rule / sandbox / prompt-injection fixes. |
| [`check-tool-updates.sh`](check-tool-updates.sh) | Reads the manifest and reports upstream releases that are newer than the pin AND have themselves aged past the 7-day cooldown. Side-effect-free — no installs, no edits, no PRs. |
| [`agent-iso.sh`](agent-iso.sh) | Shell function to launch Claude Code with `env -i` and a tiny passthrough list, stripping every credential-shaped environment variable from the parent shell. The framework's "layer 0" of the secure setup. |
| [`sandbox-bypass-warn.sh`](sandbox-bypass-warn.sh) | Claude Code `PreToolUse` hook (Bash matcher). Prints a bold-red banner to stderr whenever the model invokes the Bash tool with `dangerouslyDisableSandbox: true`. Belt-and-braces visibility for the sandbox-bypass permission prompt. Recommended user-scope (`~/.claude/settings.json`) so it fires across every session on the host. |
| [`sandbox-error-hint.sh`](sandbox-error-hint.sh) | Claude Code `PostToolUse` hook (Bash matcher). Scans the tool's stdout + stderr for the four known sandbox-shaped error signatures (SSH agent / Yubikey unreachable, loopback port-bind blocked, docker / podman socket denied, temp files blocked under `/tmp`) and prints a `[sandbox-hint]` line pointing at the matching entry in [`docs/setup/sandbox-troubleshooting.md`](../../docs/setup/sandbox-troubleshooting.md). Fail-open: any unexpected JSON shape exits silent. Recommended user-scope so the hint fires across every session. Complements `setup-isolated-setup-doctor` (the structured probe) by surfacing the catalog reference at the moment of failure, without the user having to remember the catalog exists. |
| [`sandbox-status-line.sh`](sandbox-status-line.sh) | Claude Code `statusLine` helper, and the only one Magpie ships. **Claude Code only** — the one script in this directory that is not harness-agnostic: it is wired through Claude Code's `statusLine` setting, is fed Claude Code's statusLine payload on stdin, and reads Claude Code's `sandbox.enabled` schema. No other harness the framework supports has a status-line hook of that shape; Codex, Gemini, OpenCode and Kiro carry their sandbox posture in their own config and surface it, where they surface it at all, through their own UI. A harness that grows one gets its own helper — see [`docs/adapters/add-a-harness.md`](../../docs/adapters/add-a-harness.md). Leads with the sandbox state — green `[sandbox]`, yellow `[sandbox-auto]` when `autoAllowBashIfSandboxed` widens the blast radius, bold-red `[NO SANDBOX]` — read from `sandbox.enabled` in the active settings, project `settings.local.json` first, then project `settings.json`, then user-scope, mirroring Claude Code's own precedence, so in-session `/sandbox` toggles are reflected. Inside a linked git worktree the walk **leads with the main checkout** — that is where Claude Code scopes the project and where `/sandbox` persists the toggle, so it is the only file that can describe the session; reading `<cwd>` alone there falls through to user scope and paints a green `[sandbox]` on a session that has none. Layout-agnostic: worktrunk's `<repo>.<branch>/` siblings, `.claude/worktrees/<name>`, and plain `git worktree add` all resolve the same way, and a bare repo's worktrees — which have no main checkout at all — fall through to user scope rather than reading the bare directory's parent. Then the context that tells sessions apart: hash-coloured folder (stable per repo and worktree), git branch + dirty + ahead/behind (local only, no network), the branch's PR number and title (cached, gated by `gh`, silent without it), and the model. Every segment degrades to silence when its input is missing. Install user-scope. |
| [`gpg-touch-overlay.sh`](gpg-touch-overlay.sh) | Claude Code `PreToolUse`/`PostToolUse` hook (Bash matcher). Puts a window on screen while a hardware signing key blocks waiting for a touch — the case pinentry never prompts for, and which is indistinguishable from a hung `git commit`. `arm` starts a watcher before a git command that could reach the key — one that signs, or one that talks to a remote over ssh; the watcher shows the window only once the key has actually blocked, stays quiet while pinentry owns the screen, and `disarm` tears the whole process group down afterwards. Watches both signing commands — `gpg`, and the `ssh-keygen -Y sign` git runs under `gpg.format=ssh` — and, for the authentication touch a `git pull` / `push` / `fetch` over ssh asks for, the connection ssh holds open to the agent's socket while its request is out. `wrap` is the same watcher for git commands the agent never runs — a commit or push from the operator's own terminal: git is pointed at the script as its signing program (`gpg.ssh.program` via the argument-free `gpg-touch-wrap-ssh-keygen` symlink, or `gpg.program`) and its ssh command (`core.sshCommand … wrap ssh`), and the script runs the real program with a watcher alive for exactly that long. See [`docs/setup/secure-agent-setup.md` → *Hardware-key touch overlay*](../../docs/setup/secure-agent-setup.md#hardware-key-touch-overlay) and [→ *From your own terminal*](../../docs/setup/secure-agent-setup.md#from-your-own-terminal--gits-program-config). |
| [`gpg-touch-overlay-window.py`](gpg-touch-overlay-window.py) | The window itself on Linux: a GTK overlay, one per monitor, that dims the desktop around a pulsing contact ring. Spawned by the watcher, killed by it when the touch lands. Falls back to a `zenity` dialog on a host without PyGObject. |
| [`gpg-touch-overlay-window-macos.py`](gpg-touch-overlay-window-macos.py) | The same window on macOS, drawn with Tk — a Mac has neither PyGObject nor zenity, so without this the hook has nothing to show. Main display only, and borderless rather than natively fullscreen so macOS does not switch Spaces out from under the terminal. Takes the keyboard while it is up, so a touch that lands before the key asks for one — which fires the key's OTP slot — types into the overlay instead of whatever was in front. |
| [`container-gateway-hook.sh`](container-gateway-hook.sh) | Claude Code `SessionStart` / `SessionEnd` hook. `start` launches the per-project [container gateway](../container-gateway/) as a detached daemon so sandboxed `podman` / `docker` commands have a policy-checked socket to talk to; `stop` ends it with the session. Finds the gateway in the operator's installed copy (`~/.claude/scripts/container-gateway/src`) or the adopter's `.apache-magpie/` pinned snapshot, and is a silent no-op when neither is present; in-repo copies are never trusted. See [`docs/setup/secure-agent-setup.md` → *Container gateway*](../../docs/setup/secure-agent-setup.md#container-gateway). |
| [`claude-term-bg.sh`](claude-term-bg.sh) | **Opt-in quality-of-life helper (not a security control).** Keeps a calm baseline background and tints it only when Claude genuinely wants you to act (never while working, and never when it merely *finished* a turn), so a window you've tabbed away from can't sit blocked unnoticed. Distinguishes "blocked on a decision" from "finished and idle" — which look identical at the `Stop` event — via three signals across six hooks: `Stop` → `stop` (heuristic — tints only if the final assistant message reads as a question/request; a completion stays calm; needs `python3`/`python`, else defaults calm); `PreToolUse` (matcher `AskUserQuestion`) → `wait` (exact — a structured question was posed); `PostToolUse` (matcher `*`) → `reset` (calm while working, and clears the tint the instant you approve a permission prompt or answer a question); `Notification` → `notify` (tints for permission prompts only — the plain idle ping is a no-op so it can't wipe a pending question's tint); and `UserPromptSubmit` + `SessionStart` → `reset` (you replied / fresh session clears any stale tint). Writes the OSC escape to the Claude pty discovered by walking the process tree (hooks have no controlling tty); the only deterministic reset is an explicit `CLAUDE_RESET_BG` colour via OSC 11 (iTerm2 ignores OSC 111). Colours overridable via `CLAUDE_WAIT_BG` / `CLAUDE_RESET_BG`. Tested on iTerm2 + macOS; fail-soft elsewhere. See [`docs/setup/secure-agent-setup.md` → *Waiting-for-input terminal tint*](../../docs/setup/secure-agent-setup.md#waiting-for-input-terminal-tint). |
| [`sandbox-add-project-root.sh`](sandbox-add-project-root.sh) | Adds the current adopter repo's project root (and, with `--all-worktrees`, every linked git worktree's working dir) as an explicit absolute path to `sandbox.filesystem.allowRead` and `allowWrite` in the project-local, gitignored `<repo>/.claude/settings.local.json` — one entry per worktree, each in that worktree's own settings file. Defensive against [issue #197](https://github.com/apache/magpie/issues/197) — `allowRead: ["."]` does not in practice cover CWD because the harness pre-resolves the `.` literal away from the read side. Never modifies user-scope or committed project-scope. Idempotent, atomic, tolerant of missing prereqs. Invoked from `setup-isolated-setup-install`, `/magpie-setup` (adopt / upgrade / worktree-init), and the `post-checkout` git hook installed by `/magpie-setup adopt`. |
| [`git-global-post-checkout.sh`](git-global-post-checkout.sh) | Universal `post-checkout` git hook installed at `~/.claude/git-hooks/post-checkout` when the operator picks the **simple whole-user** flavour in `setup-isolated-setup-install`. Activated by `git config --global core.hooksPath ~/.claude/git-hooks/` so every `git checkout` / `git clone` / `git worktree add` across the host invokes it. Best-effort + idempotent + `\|\| true`: invokes `sandbox-add-project-root.sh` for any worktree with a `.claude/` directory. Trade-off documented in [`docs/setup/secure-agent-setup.md` → *Per-project vs whole-user scope*](../../docs/setup/secure-agent-setup.md#per-project-vs-whole-user-scope): `core.hooksPath` shadows per-repo `.git/hooks/*` across every repo on the host. The **dispatcher** flavour (below) supersedes this file. |
| [`git-hook-dispatcher.sh`](git-hook-dispatcher.sh) | Universal, basename-keyed git-hook **dispatcher** for the **whole-user dispatcher** flavour. Symlinked to every hook name under `~/.claude/git-hooks/`. For each git operation it runs the framework's own logic for that hook type (the `post-checkout` sandbox-allowlist sync) **and then chains through to the repo-local `.git/hooks/<name>`** (resolved via `git rev-parse --git-common-dir`, worktree-safe; `exec`-ed with original argv + inherited stdin so a failing local hook still aborts the git op). Restores per-repo hooks (prek / pre-commit / husky / hand-written) under global `core.hooksPath`; a repo with no local hook is a clean no-op. See [`docs/setup/secure-agent-setup.md` → *Whole-user with the per-repo dispatcher*](../../docs/setup/secure-agent-setup.md#whole-user-with-the-per-repo-dispatcher). |
| [`prek-shim.sh`](prek-shim.sh) | Transparent `prek` front installed as `~/.claude/bin/prek` (with `~/.claude/bin` prepended to PATH) for the whole-user dispatcher flavour. Rewrites **only** `prek install` — injecting `--git-dir "$(git rev-parse --git-common-dir)"` unless the caller already passed `--git-dir`, asked for `--help`, or is outside a git work tree — so prek's shim lands in the repo-local `.git/hooks/` where the dispatcher chains, instead of the shared `core.hooksPath` dir. Every other `prek` invocation passes through unchanged; no-op on hosts with no global `core.hooksPath`. |

## Usage at a glance

```bash
# Initial install (read pinned-versions.toml for the bubblewrap/socat pins):
sudo apt-get install --no-install-recommends bubblewrap=0.11.1-* socat=1.8.1.1-*
# claude-code is unpinned — always install the latest for the newest security fixes:
npm install -g --no-save @anthropic-ai/claude-code@latest

# Source the wrapper into your shell:
source /path/to/magpie/tools/agent-isolation/agent-iso.sh

# Optional: make claude-iso the default `claude` (see docs/setup/secure-agent-setup.md
# for the trade-off — the alias also strips env in non-tracker sessions):
alias claude='claude-iso'

# Launch a session with no inherited credentials:
cd ~/code/<tracker>
claude-iso

# For any other harness — same credential strip, no Claude-specific settings:
agent-iso codex [codex-args]
agent-iso cursor [cursor-args]
agent-iso gemini [gemini-cli-args]
# Or directly without sourcing:
bash /path/to/magpie/tools/agent-isolation/agent-iso.sh agent-iso codex [codex-args]

# Periodically (or via /schedule weekly), check for upgrade candidates:
bash /path/to/magpie/tools/agent-isolation/check-tool-updates.sh
```

## Explicit environment opt-in

`AGENT_ISO_ALLOW` names the additional variables the launcher may pass through, separated by spaces.
Values must already be set in the invoking shell or on the invocation line; naming a variable does not obtain a credential.
For example, with `GH_TOKEN` already set for a workflow that needs GitHub authentication:

```bash
AGENT_ISO_ALLOW=GH_TOKEN agent-iso <your-runtime-cli>
```

The same mechanism supports non-secret configuration such as a project ID or region.
Consult your runtime's adapter for required variables; the [Gemini authentication recipes](../../docs/adapters/gemini.md#authentication-with-the-clean-environment-wrapper) show one mapping.
Credentials intentionally passed through are available to the runtime; this is an explicit exception to environment stripping, not a separate secret store.
Store persistent credentials under the runtime's home-directory convention, never in a project `.env` file.

`CLAUDE_ISO_ALLOW` remains supported for existing installations and all harnesses.
When `AGENT_ISO_ALLOW` is set, it replaces that legacy list; an explicitly empty value permits no additional variables.
Setting `KEY=value` alone does not bypass the strip.
The wrapper does not print values, and rejects invalid variable names before launching the runtime.

## Referenced by

- [`../../docs/setup/secure-agent-setup.md`](../../docs/setup/secure-agent-setup.md) —
  the user-facing setup document. Read that first.
- [`../../.claude/settings.json`](../../.claude/settings.json) — the
  framework's own dogfooded secure config. Adopters scaffold their
  own version from the example block in `docs/setup/secure-agent-setup.md`.
