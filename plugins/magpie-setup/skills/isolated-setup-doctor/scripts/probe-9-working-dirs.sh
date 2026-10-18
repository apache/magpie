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

# The read block makes every read outside the working directories prompt.
# The skills read the session scratch root on every run.
# additionalDirectories takes literal paths; a glob is listed as a working
# directory but never matched. The fixed vetted-ops path must NOT be one:
# the sandbox makes working directories writable, and the vetted-ops
# commands run from there outside the sandbox.
if [ -z "$HOME" ]; then
  echo "PROBE: working-dirs → ⊘ (HOME is not set; cannot resolve the directories)"
  exit 0
fi
magpie_dir="$HOME/.claude/magpie"
scratch_dir="/tmp/claude-$(id -u)"
files=".claude/settings.json .claude/settings.local.json"
if [ -r "$HOME/.claude/settings.json" ]; then
  files="$files $HOME/.claude/settings.json"
  user_readable=1
else
  user_readable=0
fi
# shellcheck disable=SC2086
settings=$(cat $files 2>/dev/null)

globs=$(printf '%s' "$settings" | grep -o '"/tmp/claude-\*[^"]*"' | head -1)

# An entry overlaps the checkout when it is the path, inside it, or a parent.
covering=""
if command -v jq >/dev/null 2>&1; then
  # One jq per file: a file that is not valid JSON must not hide the others.
  work_dirs=""
  for file in $files; do
    [ -r "$file" ] || continue
    work_dirs="$work_dirs
$(jq -r '.permissions.additionalDirectories[]? // empty' "$file" 2>/dev/null)"
  done
  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    case "$entry" in
      "~" | "~/"*) entry="$HOME${entry#\~}" ;;
    esac
    root="${entry%/}"
    case "$magpie_dir/" in
      "$root"/*) covering="$entry"; break ;;
    esac
    case "$root/" in
      "$magpie_dir"/*) covering="$entry"; break ;;
    esac
  done <<EOF_DIRS
$work_dirs
EOF_DIRS
elif printf '%s' "$settings" | grep -qF -e "\"$magpie_dir\"" -e "\"$magpie_dir/\"" -e '"~/.claude/magpie' -e "\"$magpie_dir/"; then
  covering="$magpie_dir"
fi

if [ -n "$covering" ]; then
  echo "PROBE: working-dirs → ✗ ($covering is a working directory overlapping $magpie_dir, so sandboxed commands can write the vetted-ops checkout; remove it from additionalDirectories — sandbox-add-project-root.sh --all-worktrees removes the ~/.claude/magpie entry it once added, any other needs a hand edit)"
elif printf '%s' "$settings" | grep -qF "\"$scratch_dir\""; then
  echo "PROBE: working-dirs → ✓ ($scratch_dir is a working directory)"
elif printf '%s' "$settings" | grep -q '"blockReadsOutsideWorkingDirectories"[[:space:]]*:[[:space:]]*true'; then
  if [ -n "$globs" ]; then
    echo "PROBE: working-dirs → ⚠ (not a working directory: $scratch_dir; the glob entry $globs is never matched)"
  else
    echo "PROBE: working-dirs → ⚠ (not a working directory: $scratch_dir)"
  fi
elif [ "$user_readable" -eq 0 ]; then
  echo "PROBE: working-dirs → ⊘ (not a working directory: $scratch_dir; user-scope settings unreadable from the sandbox, so whether the read block is on is unknown — setup-isolated-setup-verify check 15 covers it)"
else
  echo "PROBE: working-dirs → ⊘ (permissions.blockReadsOutsideWorkingDirectories is off)"
fi
