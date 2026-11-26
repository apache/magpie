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
#   AGENT_ISO_ALLOW=GH_TOKEN claude-iso       # token already set in the shell
#   AGENT_ISO_ALLOW=AWS_PROFILE AWS_PROFILE=read-only claude-iso
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

# ASF hosts for one Antigravity session (#2003).
#
# Antigravity keeps its permission rules in one user-scope file, so an ASF
# project's hosts cannot go there without reaching every repository. Instead
# `agent-iso agy` passes them for one session with `agy --settings`, which is
# never saved, when all of these hold:
#   - the launch starts a session (not `agy plugin …`, `--help`, …) and
#     carries no --settings of the user's own;
#   - the launch directory is inside a git checkout (git run with a clean
#     environment, its reported root checked to contain the launch directory)
#     whose resolved project.md holds one explicit `organization: ASF`, as
#     decided by setup_preflight.organization_network from agy's own installed
#     Magpie plugin, ~/.gemini/config/plugins/magpie/, which the shipped
#     profile denies agents writing (write_file(~/.gemini/config)) and no
#     other harness's sandbox can reach: the check runs outside the sandbox,
#     so it is only ever taken from there, with a stripped environment and no
#     site-packages, its answer counting only when it is exactly the reviewed
#     host list below;
#   - the user approved this checkout (agent_iso_agy_asf_approved).
# AGENT_ISO_ASF=0 turns it off. Anything unexpected means no grant.
# The reviewed host list, as a function rather than a variable: a shell that
# replays this file's functions from a snapshot (`typeset -f`) drops its
# plain variables.
_agent_iso_asf_hosts() {
  printf '%s' "lists.apache.org dist.apache.org repository.apache.org downloads.apache.org archive.apache.org cveprocess.apache.org"
}

# The real path of the `$1` on PATH, unless it lies somewhere a sandboxed
# agent can write (the checkout `$2`, the launch directory, temporary
# directories, ~/.cache): an interpreter or git swapped in there, such as an
# active virtualenv's python3, would otherwise run outside the sandbox.
# The resolved path of an existing directory `$1`, or `$1` itself when it does
# not exist; zsh resolves with :A, since it runs chpwd hooks even on
# `builtin cd`.
_agent_iso_realdir() {
  if [[ -n "${ZSH_VERSION-}" ]]; then
    # shellcheck disable=SC2296
    printf '%s' "${1:A}"
  else
    (builtin cd -P -- "$1" 2>/dev/null && builtin pwd -P) || printf '%s' "$1"
  fi
}

_agent_iso_trusted_bin() {
  local found real dir here
  if [[ -n "${ZSH_VERSION-}" ]]; then
    found="$(whence -p "$1" 2>/dev/null)" || return 1
    # shellcheck disable=SC2296
    real="${found:A}"
    here="${PWD:A}"
  else
    found="$(type -P "$1" 2>/dev/null)" || return 1
    real="$(command -p realpath -- "$found" 2>/dev/null)" || return 1
    here="$(builtin pwd -P)"
  fi
  [[ -n "$real" ]] || return 1
  # Any directory above the launch directory may be a checkout, up to the
  # root, apart from home itself, its parents, and system install locations.
  local home up
  home="$(_agent_iso_realdir "${HOME%/}")"
  up="$here"
  while [[ -n "$up" && "$up" != "/" ]]; do
    case "$up" in
      "$home"|/usr|/usr/local|/opt|/opt/homebrew|/opt/local|/nix|/nix/store|/bin|/sbin|/Library|/System|/Applications) ;;
      *)
        if [[ "$home" != "$up"/* ]]; then
          [[ "$real" == "$up"/* ]] && return 1
        fi
        ;;
    esac
    up="${up%/*}"
  done
  for dir in "$2" "$here" "$PWD" "${TMPDIR:-/tmp}" /tmp /private/tmp /var/tmp /private/var/tmp /var/folders /private/var/folders "${HOME%/}/.cache" "${XDG_CACHE_HOME-}"; do
    [[ -n "$dir" ]] || continue
    dir="$(_agent_iso_realdir "${dir%/}")"
    dir="${dir%/}"
    [[ -n "$dir" ]] || continue
    [[ "$real" == "$dir" || "$real" == "$dir"/* ]] && return 1
  done
  printf '%s' "$real"
}

# Approval is once per checkout, as Claude Code's setup proposes the same grant
# once per project. The first launch asks on the terminal, Enter meaning yes,
# and keeps the answer in ~/.gemini/config/magpie-agy-asf, outside every
# checkout and under the directory the shipped profile already denies agents
# writing (write_file(~/.gemini/config)), keyed on the path and the identity
# of the checkout and its
# .git, so a later repository at the same path is asked again. With no
# terminal and no recorded answer there is no grant; an interrupted prompt
# declines for this launch only. AGENT_ISO_ASF=1 grants without asking.
agent_iso_agy_asf_approved() {
  local key="$1" root="$2"
  [[ "${AGENT_ISO_ASF-}" == "1" ]] && return 0
  local record="${HOME%/}/.gemini/config/magpie-agy-asf"
  local line
  if [[ -f "$record" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ "$line" == "approve $key" ]] && return 0
      [[ "$line" == "decline $key" ]] && return 1
    done < "$record"
  fi
  if [[ ! -t 0 || ! -t 2 ]] || ! { : </dev/tty; } 2>/dev/null; then
    echo "agy-iso: ASF project; run agent-iso agy once in a terminal to approve the ASF hosts, or set AGENT_ISO_ASF=1." >&2
    return 1
  fi
  local answer=""
  printf 'agy-iso: %s is an ASF project. Grant its sessions read_url for %s? [Y/n] ' "$root" "$(_agent_iso_asf_hosts)" >&2
  if ! read -r answer </dev/tty; then
    printf '\nagy-iso: no answer; starting without ASF hosts this time.\n' >&2
    return 1
  fi
  local verdict="approve"
  case "$answer" in
    ""|[Yy]|[Yy][Ee][Ss]) ;;
    *) verdict="decline" ;;
  esac
  # `>|` creates the file even under zsh's noclobber, where `>>` would not.
  command -p mkdir -p "${record%/*}" || return 1
  [[ -e "$record" ]] || : >| "$record"
  printf '%s %s\n' "$verdict" "$key" >> "$record"
  [[ "$verdict" == "approve" ]]
}

# Prints the JSON for `agy --settings`, or nothing. Called with the agy argv.
# The JSON repeats the user-scope allow / ask / deny lists of
# ~/.gemini/antigravity-cli/settings.json and adds one read_url(<host>) per
# ASF host, so every user rule still applies whether agy merges or replaces the
# lists; a file that exists but cannot be read as those lists means no grant.
# agy refuses a relative file path in --settings, so a relative read_file /
# write_file path is anchored at the launch directory and its resolved path
# and, for ask and deny, at the checkout root as well; `~` at the home
# directory.
agent_iso_agy_asf_settings() {
  [[ "${AGENT_ISO_ASF-}" == "0" ]] && return 0
  case "${1-}" in
    acp|agent|agents|changelog|help|install|mcp|mic-serve|models|plugin|plugins|remote-control|update) return 0 ;;
  esac
  local arg
  for arg in "$@"; do
    case "$arg" in
      --settings|--settings=*|--help|-h|--version|-v) return 0 ;;
    esac
  done
  local home="${HOME%/}"
  local plugins="$home/.gemini/config/plugins"
  local checker="$plugins/magpie/plugins/magpie-setup/skills/setup"
  # The selector must sit at exactly this path with no symlink anywhere in
  # it (a link could lead out of the protected tree, or to another plugin),
  # and nothing under setup_preflight/ may be a symlink either.
  [[ -d "$checker/setup_preflight" && -f "$checker/setup_preflight/organization_network.py" ]] || return 0
  local real_home
  real_home="$(_agent_iso_realdir "$home")"
  [[ "$(_agent_iso_realdir "$checker")" == "$real_home/.gemini/config/plugins/magpie/plugins/magpie-setup/skills/setup" ]] || return 0
  [[ -z "$(command -p find "$checker/setup_preflight" -type l 2>/dev/null)" ]] || return 0
  checker="$real_home/.gemini/config/plugins/magpie/plugins/magpie-setup/skills/setup"
  # The checkout root is the nearest directory holding a .git (a directory,
  # or a file for a linked worktree), found without running git, so neither
  # a git on PATH nor its configuration or environment is involved.
  local py root="" up
  if [[ -n "${ZSH_VERSION-}" ]]; then
    # shellcheck disable=SC2296
    up="${PWD:A}"
  else
    up="$(builtin pwd -P)"
  fi
  while [[ -n "$up" ]]; do
    if [[ -e "$up/.git" ]]; then
      root="$up"
      break
    fi
    [[ "$up" == "/" ]] && break
    up="${up%/*}"
    [[ -z "$up" ]] && up="/"
  done
  [[ -n "$root" && "$root" != *$'\n'* && "$PWD" != *$'\n'* ]] || return 0
  if ! py="$(_agent_iso_trusted_bin python3 "$root")"; then
    echo "agy-iso: the python3 on PATH is inside the checkout or a temporary directory; starting without ASF hosts." >&2
    return 0
  fi
  local selected
  if ! selected="$(command -p env -i PATH="$PATH" HOME="$HOME" PYTHONPATH="$checker" "$py" -P -S -m setup_preflight.organization_network --project-root "$root" 2>/dev/null)"; then
    echo "agy-iso: the ASF network check failed; starting without ASF hosts." >&2
    return 0
  fi
  # Three lines back: the approval key, the hosts, then the settings JSON.
  local out
  out="$(command -p env -i PATH="$PATH" "$py" -I -S -c '
import json, os, sys
selected, path, root, cwd, home, reviewed = sys.argv[1:7]
home = home.rstrip("/") or "/"
real_root, real_cwd = os.path.realpath(root), os.path.realpath(cwd)
if real_cwd != real_root and not real_cwd.startswith(real_root.rstrip("/") + "/"):
    sys.exit(0)  # git reported a root that does not contain the launch directory
try:
    domains = json.loads(selected or "{}").get("sandbox", {}).get("network", {}).get("allowedDomains", [])
except (ValueError, AttributeError):
    sys.exit(0)
if not domains:
    sys.exit(0)
if domains != reviewed.split():
    print("agy-iso: the ASF network check returned unexpected hosts; starting without them.", file=sys.stderr)
    sys.exit(0)
try:
    with open(path, encoding="utf-8-sig") as f:
        profile = json.load(f)
    user = profile.get("permissions", {})
except FileNotFoundError:
    profile, user = {}, {}
except (OSError, ValueError, AttributeError):
    print("agy-iso: %s could not be read; starting without ASF hosts." % path, file=sys.stderr)
    sys.exit(0)
if not isinstance(user, dict) or not all(isinstance(user.get(k, []), list) for k in ("allow", "ask", "deny")):
    print("agy-iso: %s has malformed permissions; starting without ASF hosts." % path, file=sys.stderr)
    sys.exit(0)

def anchors(rule, bases):
    for tool in ("read_file(", "write_file("):
        if rule.startswith(tool) and rule.endswith(")"):
            p = rule[len(tool):-1]
            if p == "~" or p.startswith("~/"):
                return [tool + os.path.normpath(home + p[1:]) + ")"]
            if p and not p.startswith(("/", "regex:")) and p != "*":
                if p.startswith("~") or any(c in p for c in "*?[]{}"):
                    return None  # cannot be anchored without changing what it matches
                return [tool + os.path.normpath(os.path.join(b, p)) + ")" for b in bases]
    return [rule]

lists = {}
for key in ("allow", "ask", "deny"):
    bases = [cwd, real_cwd] if key == "allow" else [cwd, real_cwd, root, real_root]
    bases = list(dict.fromkeys(bases))
    out = []
    for rule in user.get(key, []):
        if not isinstance(rule, str):
            print("agy-iso: %s has a non-text %s rule; starting without ASF hosts." % (path, key), file=sys.stderr)
            sys.exit(0)
        anchored = anchors(rule, bases)
        if anchored is None:
            print("agy-iso: %s has a %s rule that cannot be made absolute (%s); starting without ASF hosts." % (path, key, rule), file=sys.stderr)
            sys.exit(0)
        for r in anchored:
            if r not in out:
                out.append(r)
    lists[key] = out
for domain in domains:
    rule = "read_url(%s)" % domain
    if rule not in lists["allow"]:
        lists["allow"].append(rule)

def ident(p):
    st = os.stat(p)
    born = getattr(st, "st_birthtime", None)
    return "%d:%d%s" % (st.st_dev, st.st_ino, "" if born is None else ":%r" % born)

git_dir = os.path.join(real_root, ".git")
print("%s %s %s" % (real_root, ident(real_root), ident(git_dir) if os.path.exists(git_dir) else "-"))
print(" ".join(domains))
# The sandbox switches ride along too, in case a session setting replaces
# rather than overlays the user-scope value.
session = {k: profile[k] for k in ("enableTerminalSandbox", "toolPermission", "allowNonWorkspaceAccess", "agentMode") if k in profile}
session["permissions"] = lists
print(json.dumps(session, separators=(",", ":")))
' "$selected" "$home/.gemini/antigravity-cli/settings.json" "$root" "$PWD" "$home" "$(_agent_iso_asf_hosts)")" || return 0
  [[ "$out" == *$'\n'*$'\n'* ]] || return 0
  local key="${out%%$'\n'*}"
  local rest="${out#*$'\n'}"
  local hosts="${rest%%$'\n'*}"
  agent_iso_agy_asf_approved "$key" "$root" || return 0
  if [[ -t 2 ]]; then
    printf '\033[2m[agy-iso] ASF project: read_url for this session only: %s\033[0m\n' "$hosts" >&2
  else
    printf '[agy-iso] ASF project: read_url for this session only: %s\n' "$hosts" >&2
  fi
  printf '%s' "${rest#*$'\n'}"
}

# Core: launch agent CLI "$1" (claude / opencode / …) in a clean environment.
# The env-stripping below is identical for every agent — only the injected
# settings differ (the `--settings` sandbox grant is Claude-specific). The
# `claude-iso` / `opencode-iso` entry points are thin wrappers over this.
agent_iso_run() {
  local agent="$1"
  # The Kiro harness is invoked as `kiro` but ships the `kiro-cli` binary;
  # normalise so both `AGENT_ISO_AGENT=kiro` and the `kiro-iso` entry point
  # resolve the real executable. (Claude/OpenCode names match their binaries.)
  [[ "$agent" == "kiro" ]] && agent="kiro-cli"
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

  # Explicit opt-in for runtime authentication and other required variables.
  # Only named variables pass through; setting KEY=value alone is insufficient.
  # The neutral name takes precedence, including an explicitly empty value.
  # CLAUDE_ISO_ALLOW remains the backwards-compatible fallback for every CLI.
  # Example (Linux keyring): AGENT_ISO_ALLOW=DBUS_SESSION_BUS_ADDRESS agent-iso agy
  local allowed_env_vars="${AGENT_ISO_ALLOW-${CLAUDE_ISO_ALLOW-}}"
  if [[ -n "$allowed_env_vars" ]]; then
    # Word-split portably: zsh doesn't split unquoted parameters by default
    # (it needs ${=var}), whereas bash does. Build an array either way.
    local -a allow_list
    if [[ -n "${ZSH_VERSION-}" ]]; then
      allow_list=(${=allowed_env_vars})
    else
      # shellcheck disable=SC2206
      allow_list=($allowed_env_vars)
    fi
    for var in "${allow_list[@]}"; do
      if [[ ! "$var" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
        echo "${agent}-iso: invalid variable name in environment allow list" >&2
        return 2
      fi
      eval "val=\${$var-}"
      if [[ -n "$val" ]]; then
        env_args+=("${var}=${val}")
      fi
    done
  fi

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

  # Antigravity keeps its permission rules in one user-scope file, so an ASF
  # project's hosts cannot go there without reaching every repository
  # (#2003). For a checkout whose resolved project.md declares
  # `organization: ASF`, pass them for this session only with
  # `agy --settings`, which never writes them to disk.
  if [[ "$agent" == "agy" ]]; then
    local agy_settings
    agy_settings="$(agent_iso_agy_asf_settings "$@")"
    if [[ -n "$agy_settings" ]]; then
      set -- --settings "$agy_settings" "$@"
    fi
  fi

  # Goose has no sandbox of its own, so the whole process runs inside the
  # sandbox runtime, in approve mode, through the launcher of the installed
  # Magpie plugin (docs/adapters/harnesses/goose.md). Refuse rather than fall back to an
  # unsandboxed Goose when the launcher or Node is missing.
  if [[ "$agent" == "goose" ]]; then
    local goose_plugin="${MAGPIE_GOOSE_PLUGIN:-$HOME/.agents/plugins/magpie}"
    local goose_launch="$goose_plugin/tools/agent-isolation/goose/launch.ts"
    local node_bin
    if [[ -n "${ZSH_VERSION-}" ]]; then
      node_bin="$(whence -p node 2>/dev/null || true)"
    else
      node_bin="$(type -P node 2>/dev/null || true)"
    fi
    if [[ ! -f "$goose_launch" || -z "$node_bin" ]]; then
      echo "goose-iso: needs node and the Magpie Goose plugin at $goose_plugin (goose plugin install https://github.com/apache/magpie). Not starting Goose unsandboxed." >&2
      return 127
    fi
    set -- "$goose_launch" "$agent_bin" "$@"
    agent_bin="$node_bin"
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

  # `exec` replaces the current process with the agent. That is right when
  # this script was *executed* (one less process, and the agent inherits the
  # caller's exit-status slot) but wrong when it was *sourced*: there the
  # current process is the user's own interactive shell, so `exec` would
  # replace it — quitting the agent would close the terminal — and a failed
  # exec (lost permission bit, bad interpreter, binary replaced mid-upgrade)
  # would take the shell down with it. In sourced mode run the agent as a
  # child and hand its exit status back to the shell instead.
  if [[ -n "${_AGENT_ISO_SOURCED-}" ]]; then
    env -i "${env_args[@]}" "$agent_bin" "$@"
    return $?
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
#   agentic harness — Codex, Cursor, Antigravity (`agy`), Aider, or any future CLI.
#   The credential-strip and clean-env launch are harness-agnostic; only the
#   `--settings` sandbox allowRead injection is skipped (it is Claude-specific
#   and already guarded by `if [[ "$agent" == "claude" ]]`).
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  # Sourced: every entry point below runs inside the user's interactive
  # shell, so nothing on this path may `exec` or `exit` — both would take
  # the shell with them. The flag tells `agent_iso_run` to launch the agent
  # as a child and `return`; the guards below use `return`, never `exit`.
  #
  # Each entry point sets the flag itself, as a `local`, rather than relying
  # on a global set here: a shell that replays these functions from a
  # snapshot (Claude Code's Bash tool does, via `typeset -f`) gets the
  # function bodies and the `alias claude=claude-iso`, but not this file's
  # plain variables. With a global flag, `claude --version` in such a shell
  # took the `exec` path and replaced the shell, dropping the rest of the
  # command.
  claude-iso()   { local _AGENT_ISO_SOURCED=1; agent_iso_run claude "$@"; }
  opencode-iso() { local _AGENT_ISO_SOURCED=1; agent_iso_run opencode "$@"; }
  kiro-iso()     { local _AGENT_ISO_SOURCED=1; agent_iso_run kiro "$@"; }
  # Harness-agnostic entry point: agent-iso <cli> [cli-args]
  # Guard the no-CLI case so it matches the direct-exec path (usage + exit 1)
  # instead of falling through to agent_iso_run with an empty agent name.
  agent-iso() {
    if [[ $# -lt 1 ]]; then
      printf 'Usage: agent-iso <cli> [cli-args]\n  e.g.: agent-iso codex "my prompt"\n' >&2
      return 1
    fi
    local _AGENT_ISO_SOURCED=1
    agent_iso_run "$@"
  }
else
  # Executed directly: this process exists only to become the agent, so the
  # `exec` in `agent_iso_run` and the `exit`s below are the correct exits.
  _AGENT_ISO_SOURCED=
  _aig_basename="$(basename "${0}")"
  case "$_aig_basename" in
    opencode-iso*) agent_iso_run opencode "$@" ;;
    kiro-iso*)     agent_iso_run kiro "$@" ;;
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
