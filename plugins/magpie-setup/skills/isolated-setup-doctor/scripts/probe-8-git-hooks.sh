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

# Git treats a hook it cannot see as a hook that does not exist, so an
# unreadable core.hooksPath costs every hook without an error. The only
# way to notice is to look from inside the sandbox, which is where this
# probe runs.

hooks_path=$(git config --global --get core.hooksPath 2>/dev/null)
if [ -z "$hooks_path" ]; then
  echo "PROBE: git-hooks → ⊘ (no global core.hooksPath; hooks live in each repo's .git/hooks)"
  exit 0
fi
case "$hooks_path" in
  "~/"*) hooks_path="$HOME/${hooks_path#\~/}" ;;
esac

if ! ls "$hooks_path" >/dev/null 2>&1; then
  echo "PROBE: git-hooks → ✗ (core.hooksPath $hooks_path not readable inside sandbox; sandboxed git skips every hook)"
  exit 0
fi

visible=""
unreadable=""
for hook in pre-commit commit-msg pre-push post-checkout; do
  [ -e "$hooks_path/$hook" ] || [ -L "$hooks_path/$hook" ] || continue
  if [ -r "$hooks_path/$hook" ] && [ -r "$(readlink -f "$hooks_path/$hook" 2>/dev/null)" ]; then
    visible="$visible $hook"
  else
    unreadable="$unreadable $hook"
  fi
done
visible="${visible# }"
unreadable="${unreadable# }"

if [ -n "$unreadable" ]; then
  echo "PROBE: git-hooks → ✗ ($hooks_path readable, but not the target of: $unreadable)"
elif [ -z "$visible" ]; then
  echo "PROBE: git-hooks → ⚠ ($hooks_path readable but holds none of pre-commit, commit-msg, pre-push, post-checkout)"
else
  echo "PROBE: git-hooks → ✓ ($hooks_path readable; hooks visible: $visible)"
fi
