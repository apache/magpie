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
# agent-iso.sh — launch an agent CLI with a clean environment.
#
# This is layer 0 of the secure-agent setup (see
# `docs/setup/secure-agent-setup.md`): strip every credential-shaped
# environment variable from the parent shell before exec'ing the
# agent, so it never sees `$AWS_*`, `$GH_TOKEN`, `$ANTHROPIC_API_KEY`,
# etc. that an unrelated terminal session may have exported into your
# interactive shell.
#
# The clean-env strip is agent-agnostic. Two entry points share the core:
# `claude-iso` (the default) launches Claude Code, and `opencode-iso`
# launches OpenCode. Only the Claude Code path additionally injects the
# in-process `--settings` sandbox grant below; OpenCode gets its
# filesystem isolation from the OS-level sandbox of the secure setup.
#
# Filesystem-level isolation (the bigger lift) is enforced by
# Claude Code's `sandbox` feature — see the `.claude/settings.json`
# block in `docs/setup/secure-agent-setup.md`. This wrapper is the
# environment-variable counterpart.
#
# Usage:
#   - Source it from your shell rc:
#       source /path/to/agent-iso.sh
#     and then invoke `claude-iso` (or `opencode-iso`) instead of the
#     agent CLI.
#   - Or invoke directly: `bash agent-iso.sh [claude args ...]`. To
#     isolate OpenCode when executing directly, either set
#     `AGENT_ISO_AGENT=opencode` or invoke via a symlink named
#     `opencode-iso`.
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

# Core: launch agent CLI "$1" (claude / opencode / …) in a clean environment.
# The env-stripping below is identical for every agent — only the injected
# settings differ (the `--settings` sandbox grant is Claude-specific). The
# `claude-iso` / `opencode-iso` entry points are thin wrappers over this.
agent_iso_run() {
  local agent="$1"
  shift

  # Resolve the agent binary on PATH before clobbering the env so
  # the lookup uses the user's normal $PATH. Use a path-only lookup
  # (bash `type -P`, zsh `whence -p`) instead of `command -v`: with
  # `command -v`, an `alias claude=claude-iso` in the user's rc file
  # (a documented setup option — see `docs/setup/secure-agent-setup.md`) would
  # resolve back to the alias and recurse.
  local agent_bin
  if [[ -n "${ZSH_VERSION-}" ]]; then
    agent_bin="$(whence -p "$agent" 2>/dev/null || true)"
  else
    agent_bin="$(type -P "$agent" 2>/dev/null || true)"
  fi
  if [[ -z "$agent_bin" ]]; then
    echo "${agent}-iso: '${agent}' not found on PATH. Install per docs/setup/secure-agent-setup.md." >&2
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
    # SSH_AUTH_SOCK is a fixed member of the Layer 0 passthrough (RFC-AI-0002
    # § "Layer 0 — Clean-env wrapper"): git push/pull needs the ssh-agent socket.
    # Layer 0 stays harness-agnostic. Gating the push itself is a *separate* layer
    # (Layer 3 — permissions.ask / agent-guard), wired per-harness; a runtime with
    # no Layer 3 adapter is responsible for providing its own push gate.
    SSH_AUTH_SOCK
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

  # `-w` / `--worktree` is an agent-iso control flag understood only by the
  # Claude sandbox-grant path below (it widens the allowRead set to the main
  # repo). For any other harness it is meaningless, and forwarding it into the
  # launched CLI's argv risks it being misparsed as a native flag. Strip it for
  # non-Claude agents so the generic entry point stays transparent.
  if [[ "$agent" != "claude" && "$has_worktree" -eq 1 ]]; then
    local -a _passargs=()
    for arg in "$@"; do
      case "$arg" in
        -w|--worktree|-w=*|--worktree=*) ;;   # drop the control flag
        *) _passargs+=("$arg") ;;
      esac
    done
    set -- "${_passargs[@]}"
    # The main-repo git resolution below is Claude-only (settings injection is
    # gated on `$agent == claude`), so once `-w` is stripped for a non-Claude
    # agent there is nothing left to resolve — skip the git calls.
    has_worktree=0
  fi

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

  # The `--settings` sandbox-allowRead injection is Claude Code's in-process
  # sandbox feature and is applied only for that agent. Other harnesses (e.g.
  # OpenCode) get their filesystem isolation from the OS-level sandbox of the
  # secure-agent setup, which is configured out of band — so the clean-env
  # launch below still applies, we just skip the Claude-only settings grant.
  if [[ "$agent" == "claude" ]] && (( ${#allow_read_paths[@]} > 0 )); then
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
    printf '\033[2m[%s-iso] running in isolated env (%s)\033[0m\n' "$agent" "$agent_bin" >&2
  else
    printf '[%s-iso] running in isolated env (%s)\n' "$agent" "$agent_bin" >&2
  fi

  exec env -i "${env_args[@]}" "$agent_bin" "$@"
}

# Back-compat wrapper: the historical entry point defaults to `claude`, and
# still honours AGENT_ISO_AGENT for callers that set it.
claude_iso_main() { agent_iso_run "${AGENT_ISO_AGENT:-claude}" "$@"; }

# When sourced, expose one launcher per agent as a shell function (so a user
# can `alias claude=claude-iso` and/or `alias opencode=opencode-iso`). When
# executed directly, pick the agent from the invoked name (a symlink such as
# `opencode-iso` selects OpenCode) or from AGENT_ISO_AGENT, defaulting to
# `claude` so existing `bash agent-iso.sh …` invocations are unchanged.
#
# Generic entry point:
#   agent-iso() / `bash agent-iso.sh agent-iso <cli> [args]` takes the
#   harness CLI name as its first positional argument and works for ANY
#   agentic runtime — Codex, Cursor, Gemini CLI, Aider, or any future CLI.
#   The credential-strip and clean-env launch are harness-agnostic; only the
#   `--settings` sandbox allowRead injection is skipped (it is Claude-specific
#   and already guarded by `if [[ "$agent" == "claude" ]]`).
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  claude-iso()   { agent_iso_run claude "$@"; }
  opencode-iso() { agent_iso_run opencode "$@"; }
  # Harness-agnostic entry point: agent-iso <cli> [cli-args]
  # Guard the no-CLI case so it matches the direct-exec path (usage + exit 1)
  # instead of falling through to agent_iso_run with an empty agent name.
  agent-iso() {
    if [[ $# -lt 1 ]]; then
      printf 'Usage: agent-iso <cli> [cli-args]\n  e.g.: agent-iso codex "my prompt"\n' >&2
      return 1
    fi
    agent_iso_run "$@"
  }
else
  _aig_basename="$(basename "${0}")"
  case "$_aig_basename" in
    opencode-iso*) agent_iso_run opencode "$@" ;;
    # Symlink named exactly `agent-iso` (no .sh extension) → first positional
    # arg is the harness CLI name.
    agent-iso)
      if [[ $# -ge 1 ]]; then
        _aig_cli="$1"; shift; agent_iso_run "$_aig_cli" "$@"
      else
        printf 'Usage: %s <cli> [cli-args]\n  e.g.: agent-iso codex "my prompt"\n' \
          "$_aig_basename" >&2
        exit 1
      fi
      ;;
    *)
      # Default direct-exec path (e.g. `bash agent-iso.sh`).
      # If the first positional arg is the literal word "agent-iso", treat
      # the next arg as the harness CLI name — generic sub-command:
      #   bash agent-iso.sh agent-iso codex [codex-args]
      if [[ "${1-}" == "agent-iso" ]]; then
        shift
        if [[ $# -ge 1 ]]; then
          _aig_cli="$1"; shift; agent_iso_run "$_aig_cli" "$@"
        else
          printf 'Usage: %s agent-iso <cli> [cli-args]\n  e.g.: bash %s agent-iso codex "my prompt"\n' \
            "$_aig_basename" "$_aig_basename" >&2
          exit 1
        fi
      else
        agent_iso_run "${AGENT_ISO_AGENT:-claude}" "$@"
      fi
      ;;
  esac
fi
