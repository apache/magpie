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
# The skills read two such places on every run: the fixed vetted-ops path
# and the session scratch root. additionalDirectories takes literal paths;
# a glob is listed as a working directory but never matched.
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

if ! printf '%s' "$settings" | grep -q '"blockReadsOutsideWorkingDirectories"[[:space:]]*:[[:space:]]*true'; then
  if [ "$user_readable" -eq 0 ]; then
    echo "PROBE: working-dirs → ⊘ (user-scope settings unreadable from the sandbox; setup-isolated-setup-verify check 15 covers it)"
  else
    echo "PROBE: working-dirs → ⊘ (permissions.blockReadsOutsideWorkingDirectories is off)"
  fi
else
  missing=""
  for dir in "$magpie_dir" "$scratch_dir"; do
    printf '%s' "$settings" | grep -qF "\"$dir\"" || missing="$missing $dir"
  done
  globs=$(printf '%s' "$settings" | grep -o '"/tmp/claude-\*[^"]*"' | head -1)
  if [ -z "$missing" ]; then
    echo "PROBE: working-dirs → ✓ ($magpie_dir and $scratch_dir are working directories)"
  elif [ -n "$globs" ]; then
    echo "PROBE: working-dirs → ⚠ (not a working directory:$missing; the glob entry $globs is never matched)"
  else
    echo "PROBE: working-dirs → ⚠ (not a working directory:$missing)"
  fi
fi
