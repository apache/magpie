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

if ! command -v gh > /dev/null 2>&1; then
  echo "PROBE: gh-sandbox → ⊘ (gh not on PATH)"
else
  out=$(sh -c 'gh api user --jq .login' 2>&1); rc=$?
  if [ $rc -eq 0 ]; then
    echo "PROBE: gh-sandbox → ✓ (gh works inside the sandbox; exclusion not needed on this platform)"
  else
    excl=$(cat .claude/settings.json .claude/settings.local.json ~/.claude/settings.json 2>/dev/null \
      | grep -c '"gh \*"')
    case "$out" in
      *"OSStatus -26276"*|*"HTTP 401"*)
        if [ "$excl" -gt 0 ]; then
          echo "PROBE: gh-sandbox → ✓ (sandboxed gh fails as expected; \"gh *\" is in excludedCommands — keep gh calls to cd/gh-only segments)"
        else
          echo "PROBE: gh-sandbox → ✗ (sandboxed gh fails: $(echo "$out" | head -1); \"gh *\" NOT found in excludedCommands)"
        fi ;;
      *) echo "PROBE: gh-sandbox → ⚠ (gh failed for another reason, rc=$rc: $(echo "$out" | head -1))" ;;
    esac
  fi
  # A catch-all ask rule prompts on every gh call, reads included:
  # Claude Code evaluates deny, then ask, then allow, regardless of
  # how specific the allow rules are.
  if cat .claude/settings.json .claude/settings.local.json ~/.claude/settings.json 2>/dev/null \
      | grep -q '"Bash(gh \*)"'; then
    echo "PROBE: gh-sandbox → ⚠ (catch-all \"Bash(gh *)\" in permissions.ask — every gh call prompts, read-only allow rules never fire)"
  fi
fi
