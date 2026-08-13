#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
#
# Session-start hook for the Apache Magpie plugin. Wired by the Claude Code
# plugin (SessionStart) and by the Codex CLI plugin, which uses the same event
# schema. Agent Plugins 1.0 defines no hook component, so an AP1-only client
# does not run this at all — see docs/setup/marketplaces.md.
#
# Detects when the installed plugin version has changed since the last
# session (i.e. the marketplace updated it) and prompts the user to run
# `/magpie-setup upgrade`, which reconciles the gitignored snapshot, the
# agentic overrides, and drift.
#
# Deliberately DETECT-AND-PROMPT, not auto-run: a plugin hook cannot invoke
# a slash command, and Magpie never mutates an adopter repo without the
# guided skill's confirmation. The hook is read-only apart from writing its
# own version marker; it makes no network calls and touches nothing in the
# adopter repo.
#
# Agents without a session hook (e.g. Gemini CLI) surface the same prompt via
# their extension context file (GEMINI.md) instead.
set -euo pipefail

# Drain any event JSON delivered on stdin (unused).
cat >/dev/null 2>&1 || true

# Claude Code exports `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA` to hook
# processes; Codex exports `PLUGIN_ROOT` / `PLUGIN_DATA` (the Agent Plugins 1.0
# names) *and* the `CLAUDE_*` pair for compatibility. There is no
# `CODEX_PLUGIN_ROOT`.
root="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-.}}"

# The final fallback is the XDG state dir — never a path inside `$root`, which
# for a `marketplace add` install (or this repo's own local marketplace) is a
# git working tree, and which a plugin update may replace wholesale.
data="${CLAUDE_PLUGIN_DATA:-${PLUGIN_DATA:-${XDG_STATE_HOME:-$HOME/.local/state}/magpie}}"

# Read the plugin version from whichever manifest is present. The root
# `plugin.json` is the Agent Plugins 1.0 manifest; the two client-specific
# manifests carry the same version string (enforced by
# `tools/dev/check-family-plugins.py`), so the order only matters for which
# file is read, not for the value.
manifest=""
for m in "$root/.claude-plugin/plugin.json" "$root/.codex-plugin/plugin.json" "$root/plugin.json"; do
  [ -f "$m" ] && { manifest="$m"; break; }
done
[ -n "$manifest" ] || exit 0

current="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$manifest" | head -n1)"
[ -n "$current" ] || exit 0

marker="$data/magpie-plugin-version"
stored=""
[ -f "$marker" ] && stored="$(cat "$marker" 2>/dev/null || true)"

if [ "$current" != "$stored" ]; then
  mkdir -p "$data" 2>/dev/null || true
  printf '%s' "$current" >"$marker" 2>/dev/null || true

  # stdout, not stderr: for a `SessionStart` hook exiting 0, Claude Code adds
  # stdout to the session context (stderr on a zero exit only reaches the debug
  # log). Writing the prompt to stderr would deliver it to nobody — and because
  # the marker is written first, the next session would see no change and stay
  # silent too.
  if [ -n "$stored" ]; then
    echo "Apache Magpie plugin updated ($stored -> $current). If this repo adopts Magpie, run \`/magpie-setup upgrade\` to reconcile the snapshot, agentic overrides, and drift."
  else
    echo "Apache Magpie plugin $current is active. If this repo already adopts Magpie, run \`/magpie-setup upgrade\` to reconcile; otherwise run \`/magpie-setup\` to adopt."
  fi
fi

exit 0
