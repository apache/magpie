#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
#
# Session-start hook for the magpie-vetted-ops plugin.
#
# Points the fixed path ~/.claude/magpie/vetted-ops at the dispatcher inside the
# installed plugin version, and ~/.claude/magpie/skill-lock at the write lock the
# batch skills take before posting (it ships here because this plugin is on every
# install, and the plugin cache is read-only, so skills run it with `uvx --from`). The permission `allow` rule and the sandbox exclusion
# for `vetted-op-read` name that fixed path, so neither needs a wildcard where the
# plugin version sits. A `*` there also matches spaces: a command with extra `uv`
# options spliced in at that position would be approved without a prompt, and
# would run outside the sandbox.
#
# Runs every session, so a marketplace upgrade moves the link without anyone
# re-pointing it. It only ever replaces a symlink; a real file or directory at
# the path is left alone and reported.
set -euo pipefail

# Drain any event JSON delivered on stdin (unused).
cat >/dev/null 2>&1 || true

root="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-}}"
[ -n "$root" ] || exit 0
link_dir="$HOME/.claude/magpie"

# link_one <name>: point $link_dir/<name> at $root/tools/<name>. Skips a tool this
# plugin version does not carry, and never replaces anything but a symlink.
link_one() {
  local name=$1
  local target="$root/tools/$name"
  local link="$link_dir/$name"
  [ -d "$target" ] || return 0
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    echo "magpie-vetted-ops: $link exists and is not a symlink; not replacing it" >&2
    return 0
  fi
  if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
    return 0
  fi
  mkdir -p "$link_dir"
  ln -sfn "$target" "$link"
}

link_one vetted-ops
link_one skill-lock

# A copy for `vetted-op-checks`, the one vetted-ops command that runs *inside*
# the sandbox. The plugin cache behind ~/.claude/magpie is read-denied there, so
# that command cannot start from it; ~/.cache is readable. The copy is
# sandbox-writable, which grants nothing: the command it serves runs sandboxed,
# and its record is already documented as keeping an agent honest, not as
# proof. Every command that runs *outside* the sandbox keeps using
# ~/.claude/magpie, which the agent cannot edit. One copy per plugin version.
#
# This hook itself runs outside the sandbox, in a tree the sandbox can write,
# so it never follows what may have been planted there: every directory on the
# way must be a real directory the user owns, the copy is staged in a private
# temporary directory and renamed into place, nothing existing is deleted, and
# the lock's pid file is created exclusively.
[ -d "$root/tools/vetted-ops" ] || exit 0
version="$(sed -n 's/^ *"version": *"\([^"]*\)".*/\1/p' "$root/.claude-plugin/plugin.json" 2>/dev/null | head -n 1)"
case "$version" in
  "" ) version="unversioned" ;;
  */* | .* ) echo "magpie-vetted-ops: unexpected plugin version '$version'; not copying" >&2; exit 0 ;;
esac
base="$HOME/.cache/apache-magpie/vetted-ops"
target="$base/$version"
current="$base/current"

# real_dir <path>: create it if missing; fail unless it is a real directory the user owns.
real_dir() {
  local dir=$1 owner
  [ -L "$dir" ] && return 1
  [ -d "$dir" ] || mkdir -m 700 "$dir" 2>/dev/null || return 1
  [ ! -L "$dir" ] && [ -d "$dir" ] || return 1
  # Not `stat`: GNU `stat -f` reports the file system, BSD `stat -c` does not exist.
  owner="$(python3 -I -c 'import os, sys; print(os.lstat(sys.argv[1]).st_uid)' "$dir" 2>/dev/null)"
  [ "$owner" = "$(id -u)" ]
}
# The copy is staged under ~/.local/state, which no sandbox write rule covers and
# which sits on the same file system as ~/.cache, so publishing is one rename.
stage_root="$HOME/.local/state/apache-magpie"
for dir in "$HOME/.cache" "$HOME/.cache/apache-magpie" "$base" \
  "$HOME/.local" "$HOME/.local/state" "$stage_root"; do
  real_dir "$dir" || { echo "magpie-vetted-ops: $dir is not a plain directory you own; not copying" >&2; exit 0; }
done
# Expected from the home directory, which the sandbox cannot replace, never from $base itself.
base_real="$(cd "$HOME" && pwd -P)/.cache/apache-magpie/vetted-ops"
cd "$base" || exit 0
# Every name below is relative to this directory, held as the working directory.
[ "$(pwd -P)" = "$base_real" ] || { echo "magpie-vetted-ops: $base moved while it was checked; not copying" >&2; exit 0; }
target="$version"
current="current"

if [ -L "$target" ] || { [ -e "$target" ] && [ ! -f "$target/.complete" ]; }; then
  echo "magpie-vetted-ops: $target is not a copy this hook made; leaving it alone" >&2
  exit 0
fi

if [ ! -e "$target" ]; then
  # One installer per version: two sessions starting together must not both publish.
  lock=".lock.$version"
  tries=0
  until mkdir "$lock" 2>/dev/null; do
    owner="$(cat "$lock/pid" 2>/dev/null || true)"
    # A lock whose owner is gone, or one left without a pid for over a minute
    # (an installer killed between the two steps), is reclaimed.
    if { [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; } ||
      { [ -z "$owner" ] && [ -n "$(find "$lock" -maxdepth 0 -mmin +1 2>/dev/null)" ]; }; then
      rm -rf "$lock" # a symlink planted here is removed, never followed
      continue
    fi
    tries=$((tries + 1))
    # Well inside the SessionStart hook's timeout.
    [ "$tries" -lt 20 ] || { echo "magpie-vetted-ops: $lock is held; not copying" >&2; exit 0; }
    sleep 0.2
  done
  (set -C; echo $$ >"$lock/pid") 2>/dev/null || { rm -rf "$lock"; exit 0; }
  staging=""
  trap 'rm -rf "$lock" 2>/dev/null || true; [ -z "$staging" ] || rm -rf "$staging" 2>/dev/null || true' EXIT
  if [ ! -e "$target" ] && [ ! -L "$target" ]; then
    # Staged where the sandbox cannot write, so nothing can be planted in it mid-copy.
    staging="$(mktemp -d "$stage_root/vetted-ops.XXXXXX")"
    cp -R "$root/tools/vetted-ops/." "$staging/"
    # The plugin cache may be read-only; uvx builds from the copy.
    chmod -R u+w "$staging"
    touch "$staging/.complete"
    # rename(2), never `mv`: it does not follow a symlink planted at the name, and it
    # refuses anything already there instead of moving the copy into it.
    if python3 -I -c 'import os, sys; os.rename(sys.argv[1], sys.argv[2])' "$staging" "$target" 2>/dev/null; then
      staging=""
    else
      echo "magpie-vetted-ops: could not publish $base_real/$target; not linking it" >&2
      exit 0
    fi
    if [ -L "$target" ] || [ ! -f "$target/.complete" ]; then
      echo "magpie-vetted-ops: $target changed while it was being published; not linking it" >&2
      exit 0
    fi
  fi
fi

if [ -e "$current" ] && [ ! -L "$current" ]; then
  echo "magpie-vetted-ops: $current exists and is not a symlink; not replacing it" >&2
  exit 0
fi
if [ -L "$current" ] && [ "$(readlink "$current")" = "$base/$version" ]; then
  exit 0
fi
ln -sfn "$base/$version" "$current"
