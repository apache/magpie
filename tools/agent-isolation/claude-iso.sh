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
# claude-iso.sh — launch Claude Code with a clean environment.
#
# This is layer 0 of the secure-agent setup (see
# `docs/setup/secure-agent-setup.md`): strip every credential-shaped
# environment variable from the parent shell before exec'ing
# Claude Code, so the agent never sees `$AWS_*`, `$GH_TOKEN`,
# `$ANTHROPIC_API_KEY`, etc. that an unrelated terminal session
# may have exported into your interactive shell.
#
# Filesystem-level isolation (the bigger lift) is enforced by
# Claude Code's `sandbox` feature — see the `.claude/settings.json`
# block in `docs/setup/secure-agent-setup.md`. This wrapper is the
# environment-variable counterpart.
#
# Usage:
#   - Source it from your shell rc:
#       source /path/to/claude-iso.sh
#     and then invoke `claude-iso` instead of `claude`.
#   - Or invoke directly: `bash claude-iso.sh [claude args ...]`.
#
# To inject a single credential explicitly for one session:
#   GH_TOKEN="$(gh auth token)" claude-iso
#   AWS_PROFILE=read-only claude-iso
#
# Current-repo auto-allow:
#   Whenever the wrapper is invoked from inside a git working
#   tree, claude-iso automatically grants the session's sandbox
#   read access to that working tree's root (resolved via
#   `git rev-parse --show-toplevel`). Without this, the agent
#   can't read the source the user just `cd`'d into unless the
#   repo path was hand-listed in `.claude/settings.json` ahead of
#   time. Outside a git repo it's a silent no-op. The path is
#   injected via a one-shot `--settings` merge — nothing on disk
#   changes — and a stderr banner reports what was added.
#
# Worktree mode (`claude-iso -w` / `claude-iso --worktree`):
#   Additive on top of the current-repo auto-allow above. When
#   `-w` / `--worktree` is present in the args AND the wrapper is
#   invoked from inside a git repo, claude-iso also grants read
#   access to the *main* repo (resolved via
#   `git rev-parse --git-common-dir`, so it works whether you
#   launch from the main checkout or from a nested worktree).
#   When run in the main repo, the toplevel and the main repo
#   resolve to the same path and are deduped. Both paths ride
#   into the session via a single `--settings` injection that
#   Claude merges into the loaded settings stack at startup,
#   before the sandbox is initialised.

claude_iso_main() {
  # Resolve the claude binary on PATH before clobbering the env so
  # the lookup uses the user's normal $PATH. Use a path-only lookup
  # (bash `type -P`, zsh `whence -p`) instead of `command -v`: with
  # `command -v`, an `alias claude=claude-iso` in the user's rc file
  # (a documented setup option — see `docs/setup/secure-agent-setup.md`) would
  # resolve back to the alias and recurse.
  local claude_bin
  if [[ -n "${ZSH_VERSION-}" ]]; then
    claude_bin="$(whence -p claude 2>/dev/null || true)"
  else
    claude_bin="$(type -P claude 2>/dev/null || true)"
  fi
  if [[ -z "$claude_bin" ]]; then
    echo "claude-iso: 'claude' not found on PATH. Install per docs/setup/secure-agent-setup.md." >&2
    return 127
  fi

  # The minimal env every interactive shell needs. We deliberately
  # drop everything else — the goal is no implicit credential
  # propagation.
  local -a passthrough=(
    HOME
    PATH
    SHELL
    TERM
    LANG
    LC_ALL
    LC_CTYPE
    USER
    LOGNAME
    PWD
    XDG_RUNTIME_DIR
    XDG_CONFIG_HOME
    XDG_CACHE_HOME
    XDG_DATA_HOME
    DISPLAY              # for OAuth flows that pop a browser
    WAYLAND_DISPLAY
    SSH_AUTH_SOCK        # for git push (the agent gates push behind ASK; the socket alone is harmless)
  )

  # Build an `env -i ... NAME=value ...` argv from the passthrough list.
  # Use `eval` for the indirect lookup so this works under both bash and
  # zsh — bash's `${!var}` indirect expansion is a "bad substitution" in
  # zsh.
  local -a env_args=()
  local var val
  for var in "${passthrough[@]}"; do
    eval "val=\${$var-}"
    if [[ -n "$val" ]]; then
      env_args+=("${var}=${val}")
    fi
  done

  # Explicit single-credential injection: any env var that the user
  # set on the *invocation* line of `claude-iso` is preserved. We
  # detect this by comparing the inherited env to the parent shell's
  # via the documented contract: the user puts `KEY=value` on the
  # same line as `claude-iso`, so the variable is present in our env
  # exactly when it was passed explicitly.
  #
  # NB: this preserves *any* variable named in CLAUDE_ISO_ALLOW
  # (space-separated), so the user can route additional credentials
  # in for one session via:
  #     CLAUDE_ISO_ALLOW="GH_TOKEN AWS_PROFILE" GH_TOKEN=... claude-iso
  if [[ -n "${CLAUDE_ISO_ALLOW-}" ]]; then
    # Word-split portably: zsh doesn't split unquoted parameters by default
    # (it needs ${=var}), whereas bash does. Build an array either way.
    local -a allow_list
    if [[ -n "${ZSH_VERSION-}" ]]; then
      allow_list=(${=CLAUDE_ISO_ALLOW})
    else
      # shellcheck disable=SC2206
      allow_list=($CLAUDE_ISO_ALLOW)
    fi
    for var in "${allow_list[@]}"; do
      eval "val=\${$var-}"
      if [[ -n "$val" ]]; then
        env_args+=("${var}=${val}")
      fi
    done
  fi

  # Common one-off injections that don't need CLAUDE_ISO_ALLOW: if
  # the user explicitly set GH_TOKEN/ANTHROPIC_API_KEY on the
  # invocation line we honour it. (We can tell because the parent
  # shell didn't have it — well, actually we can't reliably tell
  # without a shadow. The conservative read: include these only when
  # the user named them in CLAUDE_ISO_ALLOW.)

  # Sandbox auto-allow injection. See the "Current-repo auto-allow"
  # and "Worktree mode" sections in the file header for the full
  # rationale. The injection uses `claude --settings <json>`, which
  # merges with the loaded settings stack at startup (i.e. before
  # sandbox init), so the added paths are in scope for the session
  # immediately — no on-disk settings.json edit is performed.
  #
  # We collect up to two candidate paths:
  #   - cwd_toplevel: the working tree root of $PWD (always when
  #     inside a git repo). Lets Claude read the source the user
  #     just `cd`'d into.
  #   - main_repo:    the parent of the main repo's .git dir; added
  #     only when `-w`/`--worktree` is on the argv, so worktree
  #     sessions can see the original checkout.
  # When both resolve to the same path (no worktree, or `-w` from
  # the main repo) they collapse to a single entry.
  local cwd_toplevel
  cwd_toplevel="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true)"

  local has_worktree=0
  local arg
  for arg in "$@"; do
    case "$arg" in
      -w|--worktree|-w=*|--worktree=*) has_worktree=1; break ;;
    esac
  done

  local main_repo=""
  if [[ "$has_worktree" -eq 1 ]]; then
    local common_dir
    common_dir="$(git -C "$PWD" rev-parse --git-common-dir 2>/dev/null || true)"
    if [[ -n "$common_dir" ]]; then
      case "$common_dir" in
        /*) ;;
        *) common_dir="$PWD/$common_dir" ;;
      esac
      main_repo="$(cd "$(dirname "$common_dir")" 2>/dev/null && pwd)"
    fi
  fi

  local -a allow_read_paths=()
  local candidate existing seen
  for candidate in "$cwd_toplevel" "$main_repo"; do
    [[ -z "$candidate" ]] && continue
    seen=0
    for existing in "${allow_read_paths[@]}"; do
      if [[ "$existing" == "$candidate" ]]; then
        seen=1
        break
      fi
    done
    [[ "$seen" -eq 0 ]] && allow_read_paths+=("$candidate")
  done

  if (( ${#allow_read_paths[@]} > 0 )); then
    # Hand-roll the JSON array literal (escape backslashes and
    # double quotes) so a pathological repo path can't break out
    # of the string literal. Keeping it dependency-free — no jq.
    local json_array="" banner_paths="" sep=""
    local p escaped
    for p in "${allow_read_paths[@]}"; do
      escaped="${p//\\/\\\\}"
      escaped="${escaped//\"/\\\"}"
      json_array+="${sep}\"${escaped}\""
      banner_paths+="${sep}\"${p}\""
      sep=","
    done
    set -- --settings "{\"sandbox\":{\"filesystem\":{\"allowRead\":[${json_array}]}}}" "$@"
    if [[ -t 2 ]]; then
      printf '\033[2m[claude-iso] added to sandbox allowRead: %s\033[0m\n' "$banner_paths" >&2
    else
      printf '[claude-iso] added to sandbox allowRead: %s\n' "$banner_paths" >&2
    fi
  fi

  # When the user has aliased `claude=claude-iso`, an interactive
  # session looks indistinguishable from a normal `claude` launch.
  # Print a one-line banner on stderr (dim if a TTY) so it's obvious
  # which mode the agent is starting in.
  if [[ -t 2 ]]; then
    printf '\033[2m[claude-iso] running in isolated env (%s)\033[0m\n' "$claude_bin" >&2
  else
    printf '[claude-iso] running in isolated env (%s)\n' "$claude_bin" >&2
  fi

  exec env -i "${env_args[@]}" "$claude_bin" "$@"
}

# When sourced, expose `claude-iso` as a function. When executed
# directly, just dispatch.
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  claude-iso() { claude_iso_main "$@"; }
else
  claude_iso_main "$@"
fi
