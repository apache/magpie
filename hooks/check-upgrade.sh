#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
#
# Claude Code SessionStart hook for the Apache Magpie plugin.
#
# Detects when the installed plugin version has changed since the last
# session (i.e. the marketplace updated it) and prompts the user to run
# `/magpie-setup upgrade`, which reconciles the gitignored snapshot, the
# agentic overrides, and drift.
#
# Deliberately DETECT-AND-PROMPT, not auto-run: a Claude Code hook cannot
# invoke a slash command, and Magpie never mutates an adopter repo without
# the guided skill's confirmation. The hook is read-only apart from writing
# its own version marker; it makes no network calls and touches nothing in
# the adopter repo.
set -euo pipefail

# Drain the event JSON delivered on stdin (unused).
cat >/dev/null 2>&1 || true

root="${CLAUDE_PLUGIN_ROOT:-.}"
data="${CLAUDE_PLUGIN_DATA:-$root}"
manifest="$root/.claude-plugin/plugin.json"

[ -f "$manifest" ] || exit 0

# Extract "version" without a jq dependency.
current="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$manifest" | head -n1)"
[ -n "$current" ] || exit 0

marker="$data/magpie-plugin-version"
stored=""
[ -f "$marker" ] && stored="$(cat "$marker" 2>/dev/null || true)"

if [ "$current" != "$stored" ]; then
  mkdir -p "$data" 2>/dev/null || true
  printf '%s' "$current" >"$marker" 2>/dev/null || true

  if [ -n "$stored" ]; then
    echo "Apache Magpie plugin updated ($stored -> $current). If this repo adopts Magpie, run \`/magpie-setup upgrade\` to reconcile the snapshot, agentic overrides, and drift." >&2
  else
    echo "Apache Magpie plugin $current is active. If this repo already adopts Magpie, run \`/magpie-setup upgrade\` to reconcile; otherwise run \`/magpie-setup\` to adopt." >&2
  fi
fi

exit 0
