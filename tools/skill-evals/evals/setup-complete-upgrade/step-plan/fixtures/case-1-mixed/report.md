<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Harness: Claude Code (sandboxed Bash; `dangerouslyDisableSandbox` available).
Installed version 0.9.0.dev202610250024, previous 0.9.0.dev202610200101.
Personal layer: `.apache-magpie-local/` (main checkout, adopted project).
Isolated setup: configured (`{"configured": true}`).

Findings:
- slug: gateway-hook-stale. `~/.claude-config/hooks/container-gateway-hook.sh` lacks the hardening of the framework copy.
  Writing under `~/.claude-config` is denied inside the sandbox.
- slug: checker-copy-stale. The pre-flight checker copy in `.apache-magpie-local/` is older than the shipped one. Writable inside the sandbox.
- slug: mentoring-config-missing. `mentoring-config.md` is required by the installed `mentor` skill and absent. Scaffold in the personal layer, inside the sandbox.
- slug: allowlist-worktrees. Three worktrees lack the sandbox project-root allowlist entry. Writing each worktree's `.claude/settings.local.json` is outside the sandbox write scope.
- slug: zshrc-claude-iso-grep. Whether `claude-iso` is sourced in `~/.zshrc` is unknown; the grep needs `~/.zshrc`, which the sandbox cannot read. Read-only probe.
