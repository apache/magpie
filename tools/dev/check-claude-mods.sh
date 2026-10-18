#!/usr/bin/env bash
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# check-claude-mods.sh
#
# Validates and tests every Claude Code mod in the repository.
#
# A mod is a plugin whose `hooks/hooks.json` declares a non-empty
# `modules` list (docs/when-to-use-mods.md). For each one this runs:
#
#   claude plugin validate --strict <plugin>   static analysis of the
#       manifest and hooks module, the same analysis Claude Code runs when
#       it loads the mod. A module Claude Code would refuse to load fails
#       here instead of silently doing nothing on an adopter's machine.
#   claude plugin test <plugin>                the mod's `*.test.ts` /
#       `*.test.tsx` files, run with `claude-code/testing`. A mod with no
#       tests fails: `claude plugin test` exits 1 when it finds none.
#
# A `hooks/hooks.json` with settings hooks only (no `modules`) is not a mod
# and is skipped, as is the whole run when the tree has no mods at all.
#
# Two hooks run this script:
#
#   check-claude-mods        `claude` from the prek hook environment
#       (`language: node`, pinned in `.pre-commit-config.yaml`). Manual stage;
#       CI runs it, and it is the authoritative result.
#   check-claude-mods-local  `--local`: the contributor's own `claude`, on
#       ordinary commits. Skipped when Claude Code is not installed or cannot
#       run, and when it is older than the pin, since an older CLI may not
#       know events a mod uses and would fail it for nothing. A newer one
#       runs: it is what adopters have, and a mod it rejects is worth knowing
#       about before the pin catches up.
#
# Neither command needs a login or the network; the configuration directory
# is a throwaway one so the run never reads or writes the user's `~/.claude`.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if [ "${1:-}" = "--local" ]; then
  pinned="$(sed -n 's/.*"@anthropic-ai\/claude-code@\([0-9.]*\)".*/\1/p' .pre-commit-config.yaml | head -n1)"
  if ! command -v claude >/dev/null 2>&1; then
    echo "check-claude-mods-local: Claude Code is not installed; skipped (CI runs the pinned $pinned)."
    exit 0
  fi
  # Some installs wrap the binary and print a banner first; take the line
  # that starts with a version.
  local_version="$(claude --version 2>/dev/null | grep -Eo '^[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || true)"
  if [ -z "$local_version" ]; then
    echo "check-claude-mods-local: \`claude --version\` did not run; skipped (CI runs the pinned $pinned)."
    exit 0
  fi
  if [ "$(printf '%s\n%s\n' "$pinned" "$local_version" | sort -V | head -n1)" != "$pinned" ]; then
    echo "check-claude-mods-local: local Claude Code $local_version is older than the pinned $pinned; skipped."
    echo "  Update Claude Code, or run the pinned one: prek run check-claude-mods --hook-stage manual --all-files"
    exit 0
  fi
  echo "check-claude-mods-local: using local Claude Code $local_version (CI pins $pinned)."
fi

mods=()
while IFS= read -r hooks_json; do
  if node -e '
    const m = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")).modules;
    process.exit(Array.isArray(m) && m.length > 0 ? 0 : 1);
  ' "$hooks_json"; then
    mods+=("$(dirname "$(dirname "$hooks_json")")")
  fi
done < <(git ls-files -- '*/hooks/hooks.json')

[ "${#mods[@]}" -gt 0 ] || exit 0

# The git directory is the fallback for an agent sandbox that denies writes
# to the system temp directory but allows them inside the repository.
config_dir="$(mktemp -d 2>/dev/null || mktemp -d "$(git rev-parse --absolute-git-dir)/claude-mods.XXXXXX")"
trap 'rm -rf "$config_dir"' EXIT
export CLAUDE_CONFIG_DIR="$config_dir"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export DISABLE_AUTOUPDATER=1

status=0
for mod in "${mods[@]}"; do
  echo "== $mod"
  claude plugin validate --strict "$mod" || status=1
  claude plugin test "$mod" || status=1
done
exit "$status"
