#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
#
# Session-start hook for the magpie-adversarial-review plugin.
#
# Points the fixed path ~/.claude/magpie/adversarial-review at the tool inside the
# installed plugin version. The sandbox exclusion for `adversarial-review` names
# that fixed path, so it needs no wildcard where the plugin version sits. A `*`
# there also matches spaces: a command with extra `uv` options spliced in at that
# position (`--with <any package>`, a second `--from`) would run outside the
# sandbox once approved.
#
# Runs every session, so a marketplace upgrade moves the link without anyone
# re-pointing it. It only ever replaces a symlink; a real file or directory at
# the path is left alone and reported.
set -euo pipefail

# Drain any event JSON delivered on stdin (unused).
cat >/dev/null 2>&1 || true

root="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-}}"
[ -n "$root" ] || exit 0
target="$root/tools/adversarial-review"
[ -d "$target" ] || exit 0

link_dir="$HOME/.claude/magpie"
link="$link_dir/adversarial-review"

if [ -e "$link" ] && [ ! -L "$link" ]; then
  echo "magpie-adversarial-review: $link exists and is not a symlink; not replacing it" >&2
  exit 0
fi
if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
  exit 0
fi

mkdir -p "$link_dir"
ln -sfn "$target" "$link"
