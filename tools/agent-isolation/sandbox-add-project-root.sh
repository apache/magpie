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
# sandbox-add-project-root.sh — add the project root to the
# project-local Claude Code sandbox allowlists.
#
# Defensive fix for the harness behaviour described in
# https://github.com/apache/magpie/issues/197 :
# `sandbox.filesystem.allowRead: ["."]` is *not* equivalent to
# `allowWrite: ["."]` in the harness — the read side pre-resolves
# `.` at session start to absolute paths and then drops the literal,
# so reads under CWD fall through to `denyRead: ["~/"]` and fail.
# The defensive measure is to add the project root as an explicit
# absolute path to BOTH `allowRead` and `allowWrite` in the
# project's gitignored `.claude/settings.local.json`. The `.` entry
# stays in the project's committed `.claude/settings.json` —
# the explicit absolute path is belt-and-braces.
#
# Scope: writes ONLY to project-local `<repo>/.claude/settings.local.json`,
# never to user-scope (`~/.claude/settings.json`) and never to the
# committed project-scope (`<repo>/.claude/settings.json`).
# - User-scope is shared across every project on the host; per-adopter
#   paths there would pollute every session.
# - Committed project-scope is shared across contributors; machine-
#   specific absolute paths there would leak into the repo.
# - Project-local (`settings.local.json`) is gitignored by convention,
#   per-machine, per-project, and merged on top of the other two by
#   the harness. The right home for this fix.
#
# Sandbox interaction: the target file
# `<repo>/.claude/settings.local.json` is in Claude Code's built-in
# sandbox `denyWithinAllow` set — Bash writes to it from inside a
# sandboxed session fail with `operation not permitted` (verified
# empirically via `echo >> .claude/settings.local.json`). This is
# a SECURITY FEATURE, not a bug: a compromised agent cannot mutate
# the file to broaden its own sandbox. Practical consequence: this
# script writes successfully only from one of:
#   1. A user-terminal context (no Claude Code sandbox active) — e.g.
#      the post-checkout git hook fired by `git checkout` /
#      `git worktree add` run in the operator's shell.
#   2. A `setup-isolated-setup-install` first-run flow that the
#      operator drives outside an agent session.
#   3. An agent's `Bash` tool call with `dangerouslyDisableSandbox: true`
#      — `/magpie-setup adopt`, `upgrade`, `worktree-init` invoke this
#      script that way, proposing the bypass to the operator first so
#      `sandbox-bypass-warn.sh`'s bold-red banner fires as a backstop.
# If invoked from inside a sandboxed session *without* the bypass, jq's
# `mv` fails and this script logs the failure to stderr but exits 0
# — never derails the calling flow.
#
# Usage:
#   sandbox-add-project-root.sh                # current worktree only
#   sandbox-add-project-root.sh --all-worktrees  # main + every linked worktree
#   sandbox-add-project-root.sh --dry-run        # print what would change, do not write
#   sandbox-add-project-root.sh --help
#
# Behaviour:
# - Single mode (no `--all-worktrees`): resolves the current worktree
#   via `git rev-parse --show-toplevel`, then writes/updates
#   `<that-path>/.claude/settings.local.json` so its
#   `sandbox.filesystem.allowRead` and `allowWrite` arrays contain
#   the worktree's absolute path. Used by the `post-checkout` git
#   hook installed by `/magpie-setup adopt` — when a new worktree
#   is created, the hook fires in the new working tree and the
#   helper writes that worktree's own settings.local.json.
# - All-worktrees mode (`--all-worktrees`): enumerates
#   `git worktree list --porcelain` from the current repo and
#   invokes the same write pass once per worktree, each against
#   the worktree's own `.claude/settings.local.json`. Used by
#   `setup-isolated-setup-install`, `/magpie-setup adopt`,
#   `/magpie-setup upgrade`.
# - The target file is created from scratch if it does not exist
#   (only the `sandbox.filesystem` block is written; nothing else
#   is touched). Existing files: idempotent, atomic (`jq` → tmp →
#   `mv`), no-op when the path is already present.
# - Tolerant of missing prerequisites:
#   - Not inside a git repo  → warn on stderr, exit 0.
#   - `jq` not on PATH        → warn on stderr, exit 0.
#   - Invalid existing JSON   → warn on stderr, exit 0.
#   All exit 0 so callers (post-checkout hook, /magpie-setup
#   sub-actions) are not derailed by a half-installed setup.
#
# Invoked from:
# - setup-isolated-setup-install (at install, with --all-worktrees).
# - /magpie-setup adopt + upgrade (with --all-worktrees from the main).
# - /magpie-setup worktree-init (without the flag — current worktree only).
# - The post-checkout git hook installed by /magpie-setup adopt
#   (without the flag — only the new worktree's path).

set -euo pipefail

# --- option parsing ---------------------------------------------------------

all_worktrees=0
dry_run=0
while [ $# -gt 0 ]; do
  case "$1" in
    --all-worktrees) all_worktrees=1 ;;
    --dry-run)       dry_run=1 ;;
    -h|--help)
      sed -n '19,103p' "$0"  # print the usage + behaviour block above
      exit 0
      ;;
    *)
      printf 'sandbox-add-project-root.sh: unknown option: %s\n' "$1" >&2
      exit 2
      ;;
  esac
  shift
done

# --- non-fatal preflight ----------------------------------------------------

warn() { printf 'sandbox-add-project-root.sh: %s\n' "$*" >&2; }

if ! command -v git >/dev/null 2>&1; then
  warn "git not on PATH — skipping (no project root to add)."
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  warn "jq not on PATH — skipping. Install jq to enable project-local sandbox-allowlist updates."
  exit 0
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  warn "not inside a git working tree — skipping (no project root to add)."
  exit 0
fi

# --- collect (worktree-path, settings-file) pairs ---------------------------

# Pairs are stored as two parallel arrays — bash 3 (macOS default) has no
# associative arrays we can rely on portably.
worktree_paths=()
target_files=()

add_pair() {
  local wt="$1"
  # Skip if we've already queued this worktree (de-dup in --all-worktrees mode).
  local existing
  for existing in "${worktree_paths[@]:-}"; do
    [ "$existing" = "$wt" ] && return 0
  done
  worktree_paths+=("$wt")
  target_files+=("$wt/.claude/settings.local.json")
}

if [ "$all_worktrees" -eq 1 ]; then
  while IFS= read -r line; do
    case "$line" in
      "worktree "*)
        add_pair "${line#worktree }"
        ;;
    esac
  done < <(git worktree list --porcelain)
else
  add_pair "$(git rev-parse --show-toplevel)"
fi

# --- update a single project-local settings file ----------------------------

# update_settings <file> <project-root-abs-path>
#
# Ensure <project-root-abs-path> appears in `.sandbox.filesystem.allowRead`
# and `.sandbox.filesystem.allowWrite` of <file>. Atomic write.
# Creates <file> + parent dir if missing.
update_settings() {
  local file="$1"
  local path="$2"

  # Safety: refuse to touch <file> if it is NOT gitignored in the
  # repo it lives in. settings.local.json is per-machine; writing
  # to a tracked path would create a git diff with absolute paths
  # that should never be committed. The framework's adopt flow
  # adds `/.claude/settings.local.json` to the adopter's
  # .gitignore — if we land here without that entry in place, the
  # adopter setup is incomplete and the user should fix the
  # .gitignore first.
  #
  # Both git calls below run the repo discovery themselves, from the
  # repo root, with the hook environment stripped. That matters: git
  # hooks export GIT_DIR, and with GIT_DIR set but no GIT_WORK_TREE
  # git treats the *current directory* as the work-tree root. Any
  # check run from a subdirectory would then evaluate a root-anchored
  # pattern like `/.claude/settings.local.json` against `.claude/` as
  # the root, where it cannot match — so the check reported "not
  # ignored" for a correctly-ignored file on every invocation from a
  # hook (post-checkout, post-merge, …), and the helper refused to
  # write. See the regression tests in
  # tests/test_sandbox_add_project_root.py.
  local git_env root probe
  git_env="env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE"

  # `.claude/` may not exist yet, so discover from the nearest
  # existing ancestor rather than from the file's own parent.
  probe=$(dirname "$file")
  while [ ! -d "$probe" ] && [ "$probe" != "/" ] && [ "$probe" != "." ]; do
    probe=$(dirname "$probe")
  done

  root=$($git_env git -C "$probe" rev-parse --show-toplevel 2>/dev/null) || root=""

  if [ -n "$root" ]; then
    if $git_env git -C "$root" check-ignore -q "$file" 2>/dev/null; then
      : # ignored — safe to write
    else
      # Inside a git repo and the path is genuinely not ignored.
      warn "$file is not gitignored — refusing to write. Add /.claude/settings.local.json to the adopter's .gitignore and re-run."
      return 0
    fi
  fi
  # If the parent dir is not in any git repo, we are running under a
  # caller that already verified that. Allow the write to proceed.

  local dir
  dir=$(dirname "$file")
  if [ ! -d "$dir" ]; then
    if [ "$dry_run" -eq 1 ]; then
      printf 'sandbox-add-project-root.sh [dry-run]: would mkdir -p %s\n' "$dir" >&2
    else
      mkdir -p "$dir"
    fi
  fi

  local input
  if [ -f "$file" ]; then
    if ! jq empty "$file" >/dev/null 2>&1; then
      warn "$file is not valid JSON — skipping. Fix the file by hand or re-run /setup-isolated-setup-install."
      return 0
    fi
    input="$file"
  else
    # Synthesise an empty JSON object as input. jq will then
    # build the sandbox.filesystem.{allowRead,allowWrite} keys from
    # scratch. The output file lands with ONLY the sandbox stanza
    # — nothing else is touched.
    input=/dev/null
  fi

  local jq_prog='
    .
    | .sandbox.filesystem.allowRead  = (
        (.sandbox.filesystem.allowRead  // [])
        | if index($p) then . else . + [$p] end
      )
    | .sandbox.filesystem.allowWrite = (
        (.sandbox.filesystem.allowWrite // [])
        | if index($p) then . else . + [$p] end
      )
  '

  local tmp
  tmp=$(mktemp "${file}.XXXXXX")

  if [ "$input" = "/dev/null" ]; then
    if ! printf '{}\n' | jq --arg p "$path" "$jq_prog" > "$tmp"; then
      rm -f "$tmp"
      warn "jq update of $file failed — leaving file untouched."
      return 0
    fi
  else
    if ! jq --arg p "$path" "$jq_prog" "$file" > "$tmp"; then
      rm -f "$tmp"
      warn "jq update of $file failed — leaving file untouched."
      return 0
    fi
  fi

  if [ -f "$file" ] && cmp -s "$file" "$tmp"; then
    rm -f "$tmp"
    return 0  # no change
  fi

  if [ "$dry_run" -eq 1 ]; then
    if [ -f "$file" ]; then
      printf 'sandbox-add-project-root.sh [dry-run]: would update %s with:\n' "$file" >&2
      diff -u "$file" "$tmp" >&2 || true
    else
      printf 'sandbox-add-project-root.sh [dry-run]: would create %s with:\n' "$file" >&2
      cat "$tmp" >&2
    fi
    rm -f "$tmp"
    return 0
  fi

  mv "$tmp" "$file"
  printf 'sandbox-add-project-root.sh: updated %s (project root: %s)\n' "$file" "$path" >&2
}

# --- apply ------------------------------------------------------------------

i=0
while [ "$i" -lt "${#worktree_paths[@]}" ]; do
  update_settings "${target_files[$i]}" "${worktree_paths[$i]}"
  i=$((i + 1))
done

exit 0
