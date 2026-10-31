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
# git-hook-dispatcher.sh — the universal, hook-type-agnostic
# dispatcher installed under ~/.claude/git-hooks/<hook-name> when
# the operator picks **whole-user (global) scope with the
# per-repo dispatcher** in `setup-isolated-setup-install`.
#
# Installed by symlinking (or copying) this one script to each git
# hook name the operator wants covered, e.g.:
#
#   ln -s git-hook-dispatcher.sh ~/.claude/git-hooks/pre-commit
#   ln -s git-hook-dispatcher.sh ~/.claude/git-hooks/commit-msg
#   ln -s git-hook-dispatcher.sh ~/.claude/git-hooks/pre-push
#   ln -s git-hook-dispatcher.sh ~/.claude/git-hooks/post-checkout
#   ... (one symlink per hook type)
#
# and activated by:
#
#   git config --global core.hooksPath ~/.claude/git-hooks/
#
# WHY A DISPATCHER
# ----------------
# Setting `core.hooksPath` globally makes git resolve hooks from
# ONE shared directory for every repo, so each repo's own
# `.git/hooks/*` becomes inert. A plain global hook would therefore
# shadow every repo's per-commit linter, pre-push gate, etc.
#
# This dispatcher restores per-repo behaviour: for every git
# operation it (1) runs the framework's own logic for that hook
# type, then (2) **chains through to the repo-local
# `.git/hooks/<hook-name>`** if the current repo has one. So a repo
# can keep using prek, husky, lefthook, or a hand-written hook in
# its own `.git/hooks/` — installed there via, e.g.,
# `prek install --git-dir "$(git rev-parse --git-common-dir)"`
# (the bundled `hook-manager-shim.sh` injects that flag automatically) —
# and the dispatcher will invoke it, while the framework's global
# post-checkout sandbox-allowlist sync still runs everywhere.
#
# CONTRACT
# --------
#   * The hook name is taken from the invocation basename, so this
#     one file serves every hook type.
#   * Framework logic is best-effort and `|| true`-guarded so it
#     never breaks the surrounding git operation.
#   * The repo-local hook is resolved via `--git-common-dir` so
#     linked worktrees chain to the main checkout's `.git/hooks/`.
#   * For every hook type EXCEPT post-checkout (which has framework
#     logic to run first and whose exit code git ignores), the
#     local hook is `exec`-ed with the original argv and inherited
#     stdin — a perfect passthrough that preserves the local hook's
#     exit code (so a failing pre-commit / pre-push still aborts
#     the git operation) and any stdin it consumes (pre-push,
#     post-rewrite, ...).
#   * A repo with NO local hook is a clean no-op — the git
#     operation proceeds normally (unlike a global prek shim, which
#     would abort on repos that have no prek config).

set -u

hook="$(basename "$0")"

# --- framework logic, keyed by hook type -----------------------------------
run_framework() {
  case "$hook" in
    post-checkout)
      # Sandbox-allowlist for the current worktree (issue #197).
      local wt
      wt="$(git rev-parse --show-toplevel 2>/dev/null || true)"
      if [ -n "$wt" ] \
          && [ -x "$HOME/.claude/scripts/sandbox-add-project-root.sh" ] \
          && [ -d "$wt/.claude" ]; then
        "$HOME/.claude/scripts/sandbox-add-project-root.sh" 2>/dev/null || true
      fi
      ;;
    *)
      : # no framework logic for other hook types today
      ;;
  esac
}

# --- resolve the repo-local hook (worktree-safe) ---------------------------
common="$(git rev-parse --git-common-dir 2>/dev/null || echo .git)"
case "$common" in
  /*) : ;;
  *)  common="$(cd "$common" 2>/dev/null && pwd -P || echo "$common")" ;;
esac
local_hook="$common/hooks/$hook"

# Guard against chaining into ourselves (defensive; core.hooksPath is a
# different dir from .git/hooks, but symlink layouts can surprise).
self_canon="$(readlink -f "$0" 2>/dev/null || echo "$0")"
lh_canon="$(readlink -f "$local_hook" 2>/dev/null || echo "$local_hook")"

has_local=0
if [ -x "$local_hook" ] && [ "$lh_canon" != "$self_canon" ]; then
  has_local=1
fi

# --- hook managers' homes outside the sandbox -----------------------------
# A hook manager (prek, overcommit, ...: tools/hook-manager/registry.json) runs a hook from
# environments under its home, ~/.cache/<tool> by default, which the sandbox's
# ~/.cache grant makes writable. A hook run outside the sandbox (a commit from
# a terminal, or one Claude Code ran with the sandbox bypassed) must not run
# what a sandboxed command wrote there, so outside the sandbox (no
# SANDBOX_RUNTIME) every registered manager gets a home of its own under
# ~/.local/share, which no sandbox grant covers, and so does XDG_CACHE_HOME.
# Every manager, not only those the repository is detected to use: a hook can
# reach a manager the detection does not see (through a script), and the
# settings' sandbox home would then reach it; an unused variable is harmless.
# Sandboxed hooks keep the defaults. An operator's own value is kept unless it
# sits under ~/.cache.
# The selection need not be trusted: sandboxed code that unsets
# SANDBOX_RUNTIME only makes its own hook manager fail to write the host home.
# Entries: <home var>=<host dir under ~/.local/share>
# BEGIN generated by tools/dev/sync-hook-managers.py; do not edit
hook_manager_homes="PREK_HOME=prek-host"
hook_manager_runtime_envs="overcommit:overcommit"
# END generated by tools/dev/sync-hook-managers.py
if [ -z "${SANDBOX_RUNTIME:-}" ]; then
  for _entry in $hook_manager_homes; do
    _var="${_entry%%=*}"
    case "${!_var:-}" in
      ""|"~/.cache"|"~/.cache/"*|"$HOME/.cache"|"$HOME/.cache/"*)
        export "$_var=$HOME/.local/share/${_entry#*=}"
        ;;
    esac
  done
  # The tools any hook calls keep caches of their own (pip, go, npm and uv
  # without a configured cache-dir follow XDG_CACHE_HOME, ~/.cache by default
  # on Linux), and installing from a cache the sandbox wrote is the same
  # escape. Same rule: a host-only cache root
  # unless the operator chose one outside ~/.cache.
  case "${XDG_CACHE_HOME:-}" in
    ""|"~/.cache"|"~/.cache/"*|"$HOME/.cache"|"$HOME/.cache/"*)
      export XDG_CACHE_HOME="$HOME/.local/share/prek-host/cache"
      ;;
  esac
fi

# --- managers that re-read core.hooksPath at run time -----------------------
# overcommit re-checks its install on every hook run and compares the result
# with `git config --get core.hooksPath`. While the dispatcher chains into its
# hook, that value must name the repository's own hooks dir, not the shared
# one, or overcommit's self-update check fails. Entries: <name>:<hook marker>.
apply_hook_manager_runtime_env() {
  for _entry in $hook_manager_runtime_envs; do
    _marker="${_entry#*:}"
    if grep -q -- "$_marker" "$local_hook" 2>/dev/null; then
      export GIT_CONFIG_COUNT=1
      export GIT_CONFIG_KEY_0=core.hooksPath
      export GIT_CONFIG_VALUE_0="$common/hooks"
    fi
  done
}

if [ "$has_local" = 1 ]; then
  apply_hook_manager_runtime_env
fi

# --- non-post-checkout: exec local for a perfect passthrough ---------------
if [ "$hook" != "post-checkout" ]; then
  if [ "$has_local" = 1 ]; then
    exec "$local_hook" "$@"
  fi
  exit 0
fi

# --- post-checkout: framework first, then local; never break the checkout --
run_framework
if [ "$has_local" = 1 ]; then
  "$local_hook" "$@" || true
fi
exit 0
