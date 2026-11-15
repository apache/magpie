<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The mechanical checks, by hand: 1 to 6, 8 and 11

`setup_preflight.isolated_verify` decides these checks; `SKILL.md` § *The checks* runs it.
Read this file only when the checker is not installed, or for a check it reported `unknown`: then read the files it lists under `unreadable` with the file-reading tool, never `cat`, and apply that check's section below.
A `fail` or `warn` the checker already found stands.
These are also the rules the checker implements, for when the user asks why a check came out as it did.

## Locating the framework checkout

Checks 5, 10a and 13c compare against files that exist only in a `magpie` checkout; a marketplace-only install has no `tools/` in the plugin cache.
Look, in order, for: the current repository when it is the framework itself; an `.apache-magpie/` snapshot in the adopter repo; the checkout the shell rc sources `agent-iso.sh` or `claude-iso.sh` from (`grep` the source line in `~/.bashrc` / `~/.zshrc`).
A candidate counts only when it has `tools/agent-isolation/pinned-versions.toml`; a copy under `~/.claude/agent-isolation/` is not a checkout.
With none found, ask the user for the path once.
With no checkout at all, report 10a's script comparison and 13c as **unchecked — no framework checkout**, not ✗ or ⚠, and say which path to supply.
Check 5's `bubblewrap`/`socat` pin comparisons are likewise unchecked, but the `claude-code` `min_version` floor is a hard gate that cannot be read without the manifest: an unenforced floor is **⚠** (overall `warn`), never unchecked, because a marketplace-only install below the minimum would otherwise pass.
Check 5 still reports the running `claude --version` beside that verdict.

## Check 1 — effective settings shape

Effective settings shape: `sandbox.enabled: true`, `permissions.deny`, `permissions.ask`, `sandbox.network.allowedDomains`, the `sandbox.filesystem` allowlist (`allowRead`/`allowWrite`), and `sandbox.filesystem.denyRead` containing `~/` (or the resolved absolute home).
Evaluate the merge of the project `.claude/settings.json`, the project-local `.claude/settings.local.json`, the user-scope `~/.claude/settings.json` and, where readable, the managed settings (`/etc/claude-code/managed-settings.json` and `managed-settings.d/` on Linux, `/Library/Application Support/ClaudeCode/` on macOS, `C:\Program Files\ClaudeCode\` on Windows), and name the file each key came from.
A missing `denyRead` home entry is ✗: Linux bubblewrap reads are deny-only, so without it every credential file under `~/` stays readable to sandboxed commands (`tools/sandbox-lint` enforces the same rule).
A missing committed project `.claude/settings.json` is not ✗ on its own when the merged settings pass; say which file carries them.

## Check 2 — user-scope hook wiring

User-scope `~/.claude/settings.json` wiring: `PreToolUse` `Bash` matcher → `sandbox-bypass-warn.sh`, `PostToolUse` `Bash` matcher → `sandbox-error-hint.sh`, `statusLine` → `sandbox-status-line.sh` (or a custom statusline script that embeds the framework's prefix logic, the doc-allowed variant; report ⚠).
A missing `PostToolUse` entry for `sandbox-error-hint.sh` reports ⚠ (not ✗).
The hook is a discoverability aid for the failure modes in [`docs/setup/sandbox-troubleshooting.md`](../../../../docs/setup/sandbox-troubleshooting.md); without it nothing breaks, but those failures show the raw error without the `[sandbox-hint]` annotation.

## Check 3 — hook scripts present and executable

All three of `~/.claude/scripts/sandbox-bypass-warn.sh`, `~/.claude/scripts/sandbox-error-hint.sh`, and `~/.claude/scripts/sandbox-status-line.sh`.
Symlinks into a `~/.claude-config` sync repo are equivalent to direct files; resolve the link target and check that.
A missing `sandbox-error-hint.sh` is ⚠ (not ✗), for the same reason as check 2.

## Check 4 — claude-iso sourced

`claude-iso` shell function defined and sourced.
The grep pattern is the source line in `~/.bashrc` / `~/.zshrc`; its presence alone decides this check (✓ when present).
A sourced script that is missing from `~/.claude/scripts/` is check 3's finding, not this one's.
Check whether `alias claude='claude-iso'` is set; report it as a note (the doc makes it optional).

## Check 5 — tool versions

Two rules: an exact-pin match for the sandbox primitives, and a hard floor for the agent runtime.

- **Pinned sandbox primitives (`bubblewrap`, `socat`).** The installed version must match the exact `version` pin in the framework checkout's `tools/agent-isolation/pinned-versions.toml`.
  Report drift either way (newer or older than the pin) as ⚠.
  On macOS, skip both (Seatbelt is built-in); nothing is left to check here.
- **Agent harness (`claude-code`) — `min_version` floor, NOT a pin.** The runtime tracks `@latest`, so there is no exact version to match; the manifest's `[tools.claude-code]` table declares a `min_version` floor instead.
  Get the running version (`command claude --version`) and compare it to `min_version`.
  `command` skips the doc-suggested `alias claude=claude-iso`, which would otherwise launch the isolation wrapper just to print a version:
  - **At or above the floor** → ✓.
  - **Below the floor, under Claude Code** → **HARD FAIL (✗)**; do not downgrade it to ⚠.
    The permission-rule, sandbox and prompt-injection guarantees depend on runtime behaviour present from `min_version` onward and may silently not hold on an older build, so the run cannot certify the setup at all.
  - **Below the floor, under another harness** that cannot introspect a claude-code version → ⚠, noting the floor could not be enforced as a hard gate here.

## Check 6 — status-line prefix

Status-line prefix in this session is `[sandbox]`, not `[NO SANDBOX]`.
Resolve the precedence `<cwd>/.claude/settings.local.json` → `<cwd>/.claude/settings.json` → `~/.claude/settings.json`, and report the `sandbox.enabled` value from each.
`~/.claude/settings.local.json` is not in the walk: Claude Code does not load it, so an `enabled: true` there sandboxes nothing.
Read it only to diagnose: `enabled: true` there is ✗ when no file Claude Code loads sets `sandbox.enabled`, the session then having no sandbox.
Those files are the walk, check 1's managed settings and, in a linked worktree, the main checkout's `.claude/settings*.json`.

## Check 8 — project-root grants

The static half of check 8; the live probe and the scope detection stay in `SKILL.md`.
Confirm the current working tree's absolute path appears in both `sandbox.filesystem.allowRead` and `sandbox.filesystem.allowWrite` of `<worktree>/.claude/settings.local.json`.
For every other linked worktree in `git worktree list --porcelain`, check *that* worktree's own `.claude/settings.local.json`; each worktree carries its own entry.
✗ on any missing entry; remediation: `~/.claude/scripts/sandbox-add-project-root.sh --all-worktrees` (or re-run `setup-isolated-setup-install` if the helper is not installed).
The same file should also carry the absolute dev-tool paths the helper adds (`$HOME/.local/bin`, `$HOME/.local/share/uv`, `$HOME/.cache`, `$HOME/.gitconfig`, `$HOME/.config/git`), because the harness drops the committed `~/…` entries too.
Their absence is ⚠, not ✗: nothing is exposed, but `prek` and `uv` are not found inside the sandbox — [troubleshooting entry](../../../../docs/setup/sandbox-troubleshooting.md#prek-or-uv-not-found-or-cannot-write-its-cache-inside-the-sandbox); same remediation.

## Check 11 — gh runs outside the sandbox

`sandbox.excludedCommands` must contain `"gh *"` in any layer Claude Code merges: the project `.claude/settings.json`, the project-local `.claude/settings.local.json` (where the framework checkout's template puts it), or the user-scope `~/.claude/settings.json`.
On macOS a sandboxed `gh` cannot verify TLS or read the keychain (`x509: OSStatus -26276` / `HTTP 401`), so without the exclusion every skill that talks to GitHub fails; the "`gh` is sandbox-bypassed" note under `credentials` relies on it.
Missing on macOS is ✗; missing on Linux is ⚠ (a sandboxed `gh` may work there, but the reference config expects the exclusion).

**11b — no catch-all `gh` ask rule.** `permissions.ask` (project, local and user scope alike; ask rules merge from every source) must not contain `Bash(gh *)`.
Claude Code evaluates deny, then ask, then allow, and "a matching ask rule prompts even when a more specific allow rule also matches", so the catch-all forces a prompt on every read-only `gh` call the `allow` rules meant to exempt.
The reference config lists the write subcommands one by one instead.
A catch-all in any scope is ✗, and the report should say which file carries it.
