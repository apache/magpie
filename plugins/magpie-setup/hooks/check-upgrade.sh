#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
#
# Session-start hook for the Apache Magpie plugin. Wired by the Claude Code
# plugin (SessionStart) and by the Codex CLI plugin, which uses the same event
# schema. Agent Plugins 1.0 defines no hook component, so an AP1-only client
# does not run this at all — see docs/setup/marketplaces.md.
#
# Also warns, once per session, when the isolated setup is not configured on
# this machine (see `setup_preflight.isolated.session_start`).
#
# Detects when the installed plugin version has changed since the last
# session (i.e. the marketplace updated it) and prompts the user to run
# `/magpie-setup upgrade`, which reconciles the gitignored snapshot, the
# agentic overrides, and drift.
#
# Deliberately DETECT-AND-PROMPT, not auto-run: a plugin hook cannot invoke
# a slash command, and Magpie never mutates an adopter repo without the
# guided skill's confirmation. The hook makes no network calls and writes
# only its own version marker and, through `setup_preflight`, one cleanup: it
# drops the old `~/.local/share/uv` sandbox write grant from the checkout's
# `.claude/settings.local.json`, the per-machine file the project-root helper
# already maintains, and tells the user (apache/magpie#1785). It runs no git
# command and follows no symlink to do it.
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

notice=""
if [ "$current" != "$stored" ]; then
  mkdir -p "$data" 2>/dev/null || true
  printf '%s' "$current" >"$marker" 2>/dev/null || true

  if [ -n "$stored" ]; then
    notice="Apache Magpie plugin updated ($stored -> $current). If this repo adopts Magpie, run \`/magpie-setup upgrade\` to reconcile the snapshot, agentic overrides, and drift."
  else
    notice="Apache Magpie plugin $current is active. If this repo already adopts Magpie, run \`/magpie-setup upgrade\` to reconcile; otherwise run \`/magpie-setup\` to adopt."
  fi
fi

# Once per session, the isolated-setup warning: `setup_preflight` decides
# whether it applies and prints the notice with it, as hook JSON whose
# `systemMessage` the user sees. Without a usable Python the notice goes out
# alone.
#
# The hook runs outside the sandbox, so the interpreter is never `python3`
# from PATH, which project settings can set: only fixed system and Homebrew
# locations, which no sandbox grant may cover (the container-gateway hook
# refuses to run at all when one does). uv-managed interpreters are left out:
# trusting them needs the gateway hook's full writable-root checks, and this
# hook only prints a notice, so without a system Python it prints its own.
# It runs with `-I -S`, so no PYTHON* variable, site-packages or working
# directory (the project being opened, which could carry its own
# `setup_preflight/`) reaches `sys.path`; a one-line bootstrap puts the
# plugin's own source there. `setup_preflight` needs only the stdlib.
python=""
for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  [ -x "$candidate" ] || continue
  "$candidate" -I -S -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1 || continue
  python="$candidate"
  break
done
output="$notice"
if [ -n "$python" ]; then
  bootstrap='import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module("setup_preflight.isolated", run_name="__main__", alter_sys=True)'
  output="$("$python" -I -S -c "$bootstrap" "$root/skills/setup" session-start \
    --project-root "${CLAUDE_PROJECT_DIR:-$PWD}" --notice "$notice" 2>/dev/null)" || output="$notice"
fi

# stdout, not stderr: for a `SessionStart` hook exiting 0, Claude Code adds
# stdout to the session context (stderr on a zero exit only reaches the debug
# log). Writing the prompt to stderr would deliver it to nobody — and because
# the marker is written first, the next session would see no change and stay
# silent too.
if [ -n "$output" ]; then
  printf '%s\n' "$output"
fi

exit 0
