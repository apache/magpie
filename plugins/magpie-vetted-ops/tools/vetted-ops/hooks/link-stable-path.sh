#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
#
# Session-start hook for the magpie-vetted-ops plugin.
#
# Points the fixed path ~/.claude/magpie/vetted-ops at the dispatcher inside the
# installed plugin version. The permission `allow` rule and the sandbox exclusion
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
target="$root/tools/vetted-ops"
[ -d "$target" ] || exit 0

link_dir="$HOME/.claude/magpie"
link="$link_dir/vetted-ops"

if [ -e "$link" ] && [ ! -L "$link" ]; then
  echo "magpie-vetted-ops: $link exists and is not a symlink; not replacing it" >&2
  exit 0
fi
if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
  exit 0
fi

mkdir -p "$link_dir"
ln -sfn "$target" "$link"
