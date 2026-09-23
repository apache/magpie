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

# Inside the sandbox a read-denied ~/.local/bin looks exactly like an
# absent one, so "not found" alone cannot tell a sandbox gap from a tool
# that was never installed. The worktree's settings.local.json is
# readable, and it records whether the path was granted.

found=""
missing=""
for tool in prek uv; do
  if command -v "$tool" >/dev/null 2>&1 && "$tool" --version >/dev/null 2>&1; then
    found="$found $tool"
  else
    missing="$missing $tool"
  fi
done
found="${found# }"
missing="${missing# }"

local_settings="$(git rev-parse --show-toplevel 2>/dev/null)/.claude/settings.local.json"
granted=0
if [ -n "${HOME:-}" ] && [ -f "$local_settings" ] && grep -qF "\"$HOME/.local/bin\"" "$local_settings" 2>/dev/null; then
  granted=1
fi

if [ -z "$found" ]; then
  if [ "$granted" -eq 1 ]; then
    echo "PROBE: dev-tools → ⊘ (prek and uv not found; $HOME/.local/bin is granted, so they are not installed there)"
  else
    echo "PROBE: dev-tools → ⚠ (prek and uv not found; $HOME/.local/bin is not in $local_settings)"
  fi
elif [ -n "${HOME:-}" ] && ! { mkdir -p "$HOME/.cache" 2>/dev/null && touch "$HOME/.cache/.doctor-probe" 2>/dev/null; }; then
  echo "PROBE: dev-tools → ✗ (found: $found; $HOME/.cache not writable inside sandbox)"
else
  rm -f "$HOME/.cache/.doctor-probe"
  if [ -n "$missing" ]; then
    echo "PROBE: dev-tools → ✓ (found: $found; not found: $missing; $HOME/.cache writable)"
  else
    echo "PROBE: dev-tools → ✓ (found: $found; $HOME/.cache writable)"
  fi
fi
