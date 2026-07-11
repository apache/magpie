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
#
# prek-shim.sh — a transparent front for `prek`, installed as
# `~/.claude/bin/prek` with `~/.claude/bin` prepended to PATH so it
# shadows the real `prek` binary.
#
# WHY THIS EXISTS
# ---------------
# Under **whole-user (global) scope**, the framework sets
#   git config --global core.hooksPath ~/.claude/git-hooks/
# which makes git resolve hooks from ONE shared directory for every
# repo. prek honours `core.hooksPath`, so a bare `prek install`
# would write its shim into that shared dir instead of the repo's
# own `.git/hooks/` — collapsing every repo onto a single shared
# shim and colliding with the framework's dispatchers.
#
# With the framework's per-repo **dispatcher** hooks installed in
# the shared dir (git-hook-dispatcher.sh), the correct arrangement
# is the opposite: prek's shim belongs in each repo's *local*
# `.git/hooks/`, where the dispatcher chains into it. prek supports
# that via `prek install --git-dir <gitdir>`.
#
# WHAT THIS SHIM DOES
# -------------------
#   * `prek install [...]`  -> injects
#         --git-dir "$(git rev-parse --git-common-dir)"
#     (absolute) UNLESS the caller already passed --git-dir, or
#     asked for help, or we are not inside a git work tree. This
#     forces the shim into the repo-local `.git/hooks/`, worktree-
#     safe (`--git-common-dir` resolves linked worktrees to the
#     shared hooks dir of the main checkout).
#   * every other invocation (`prek run`, `prek install-hooks`,
#     `prek autoupdate`, `--version`, bare `prek`, ...) is passed
#     through to the real prek **unchanged**.
#
# The shim is a no-op on hosts that never set a global
# core.hooksPath — installing prek into `.git/hooks/` is exactly
# where a bare `prek install` would have put it anyway, so the
# rewrite is harmless when there is no global hooks dir.

set -euo pipefail

# --- locate the REAL prek: the next `prek` on PATH that is not us -----------
self_canon="$(readlink -f "$0" 2>/dev/null || echo "$0")"
real_prek=""
IFS=':' read -ra _path_dirs <<<"${PATH:-}"
for _d in "${_path_dirs[@]}"; do
  [ -n "$_d" ] || continue
  _cand="$_d/prek"
  [ -x "$_cand" ] || continue
  _cand_canon="$(readlink -f "$_cand" 2>/dev/null || echo "$_cand")"
  [ "$_cand_canon" = "$self_canon" ] && continue   # skip ourselves
  real_prek="$_cand"
  break
done

if [ -z "$real_prek" ]; then
  echo "prek-shim: could not locate the real 'prek' binary on PATH" >&2
  echo "prek-shim: (this wrapper must sit ahead of prek, not replace it)" >&2
  exit 127
fi

# --- only rewrite the `install` subcommand; everything else is transparent --
if [ "${1:-}" != "install" ]; then
  exec "$real_prek" "$@"
fi

shift  # drop the literal `install`

# Respect an explicit --git-dir, and never interfere with help output.
inject=1
for _a in "$@"; do
  case "$_a" in
    --git-dir|--git-dir=*|-h|--help) inject=0; break ;;
  esac
done

if [ "$inject" = 1 ]; then
  if gitdir="$(git rev-parse --git-common-dir 2>/dev/null)"; then
    case "$gitdir" in
      /*) : ;;                                   # already absolute
      *)  gitdir="$(cd "$gitdir" 2>/dev/null && pwd -P || echo "$gitdir")" ;;
    esac
    exec "$real_prek" install --git-dir "$gitdir" "$@"
  fi
  # not in a git work tree: let real prek produce its own error
fi

exec "$real_prek" install "$@"
