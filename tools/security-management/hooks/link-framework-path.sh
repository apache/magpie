#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
#
# Session-start hook for the magpie-security-tools plugin.
#
# On a marketplace install there is no framework checkout, so `<framework>` is
# ~/.cache/apache-magpie/framework/current. This hook materialises a copy of the
# plugin's tools/ there, once per plugin version, and points `current` at it.
# The plugin cache itself is read-only to a sandboxed command, and `uv run
# --project` writes a .venv and uv.lock into the project; a copy under ~/.cache
# (readable and writable under the framework's sandbox floor) lets the skills'
# `uv run --project <framework>/tools/<tool> …` work unchanged, as well as
# `uvx --from`. The tools run sandboxed, so a writable copy grants nothing.
#
# Runs every session, so a marketplace upgrade materialises the new version and
# moves the link without anyone re-pointing it. It only ever replaces a symlink;
# a real file or directory at `current` is left alone and reported.
set -euo pipefail

# Drain any event JSON delivered on stdin (unused).
cat >/dev/null 2>&1 || true

root="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-}}"
[ -n "$root" ] || exit 0
[ -d "$root/tools" ] || exit 0

version="$(sed -n 's/^ *"version": *"\([^"]*\)".*/\1/p' "$root/.claude-plugin/plugin.json" 2>/dev/null | head -n 1)"
[ -n "$version" ] || version="unversioned"
base="$HOME/.cache/apache-magpie/framework"
target="$base/$version"
link="$base/current"

if [ ! -f "$target/.complete" ]; then
  mkdir -p "$base"
  # One installer per version: two sessions starting together must not both
  # replace the tree, or the second deletes one the first is already using.
  lock="$base/.lock.$version"
  tries=0
  until mkdir "$lock" 2>/dev/null; do
    # An installer killed mid-copy leaves its lock behind: reclaim it once its
    # owner is gone, so no later session is locked out of this version.
    owner="$(cat "$lock/pid" 2>/dev/null || true)"
    if [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; then
      rm -rf "$lock"
      continue
    fi
    tries=$((tries + 1))
    [ "$tries" -lt 50 ] || { echo "magpie-security-tools: $lock is held; not materialising" >&2; exit 0; }
    sleep 0.2
  done
  echo $$ >"$lock/pid"
  trap 'rm -rf "$lock" 2>/dev/null || true' EXIT
  if [ ! -f "$target/.complete" ]; then
    staging="$(mktemp -d "$base/.staging.XXXXXX")"
    cp -R "$root/tools" "$staging/tools"
    # The plugin cache may be read-only; uv writes a .venv and uv.lock beside each project.
    chmod -R u+w "$staging"
    touch "$staging/.complete"
    # Only an incomplete leftover can be here, and nothing is using it.
    rm -rf "$target"
    mv "$staging" "$target"
  fi
fi

if [ -e "$link" ] && [ ! -L "$link" ]; then
  echo "magpie-security-tools: $link exists and is not a symlink; not replacing it" >&2
  exit 0
fi
if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
  exit 0
fi
ln -sfn "$target" "$link"
