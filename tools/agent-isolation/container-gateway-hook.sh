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
# container-gateway-hook.sh — Claude Code SessionStart / SessionEnd hook.
#
# Starts the per-project container gateway when a session begins and stops
# it when the session ends, so sandboxed podman / docker commands have a
# socket to talk to. Runs outside the sandbox, like every hook. Never fails
# the session: every exit is 0, and a missing gateway is silently a no-op.
#
#   start   SessionStart — <python> -I container_gateway serve --project=<root> --daemon
#   stop    SessionEnd   — <python> -I container_gateway stop  --project=<root>
#
# Trust model: the hook runs outside the sandbox, so everything it executes --
# the interpreter, the standard library under it, and the gateway source -- must
# live where neither the repository being opened nor a sandboxed command can
# write. Otherwise any sandboxed command, which runs without a prompt, could
# plant code that runs unsandboxed at the next session start.
#
#   Writable roots. A path is refused when it resolves (symlinks followed) under
#   the project root, $HOME/.cache, $HOME/.local, /tmp/claude*,
#   /private/tmp/claude*, $CLAUDE_CODE_TMPDIR, or any sandbox.filesystem.allowWrite
#   or permissions.additionalDirectories entry in the user, project, local or
#   managed settings. $HOME/.cache and $HOME/.local are always refused, whatever
#   this project grants, because the reference setup grants them to every
#   project: a uv-managed python3 under ~/.local/share/uv is writable from any
#   other project's sandbox.
#
#   The interpreter is never looked up on PATH, which a repository can set
#   through project settings. Candidates, in order: the absolute path in
#   $HOME/.claude/scripts/container-gateway/python (an operator pin, one line),
#   then fixed Homebrew and system locations. The first one outside every
#   writable root that is Python 3.11 or newer wins; none means the hook logs one
#   line and does nothing.
#
#   The gateway source is looked up in $MAGPIE_CONTAINER_GATEWAY_SRC (development
#   override), then $HOME/.claude/scripts/container-gateway/src (operator
#   install), and refused under a writable root like the interpreter. A copy
#   inside the repository -- including an .apache-magpie/ snapshot -- is never
#   used: the project root is always sandbox-writable.
#
#   The interpreter runs with -I, so PYTHONPATH, PYTHONHOME, every other PYTHON*
#   variable, the user site-packages and the working directory (the project
#   being opened) never reach sys.path; the source directory is put there
#   explicitly by a one-line bootstrap.
#
#   $MAGPIE_CONTAINER_GATEWAY_ARGS is allow-listed, token by token, against the
#   flags below (e.g. "--egress require"). Anything else -- notably
#   --extra-bind-root, which widens the bind-mount roots -- makes the hook ignore
#   the whole variable and log one line to stderr rather than start a gateway
#   with a policy the repository chose.
#
# MAGPIE_CONTAINER_GATEWAY_DRY_RUN=1 prints the command instead of running it.

set -uo pipefail

action="${1:-}"
case "$action" in
    start|stop) ;;
    *) printf '%s: expected start|stop, got "%s"\n' "${0##*/}" "$action" >&2; exit 0 ;;
esac

payload="$(cat 2>/dev/null || true)"
cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
[[ -n $cwd ]] || cwd="$PWD"
root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$cwd")"
root="$(cd "$root" 2>/dev/null && pwd -P)" || exit 0

log() { printf '%s: %s\n' "${0##*/}" "$*" >&2; }

# Physical path, symlinks resolved; the literal path when it does not exist.
resolve() {
    local p
    p="$(readlink -f -- "$1" 2>/dev/null)" && [[ -n $p ]] && { printf '%s' "$p"; return; }
    printf '%s' "$1"
}

# A settings path entry as an absolute directory: `//x` and `~` expanded,
# relative entries taken from the project root, and any glob cut back to the
# directory that holds it.
normalize_entry() {
    local p="$1"
    case "$p" in
        //*) p="/${p#//}" ;;
        "~") p="$HOME" ;;
        "~/"*) p="$HOME/${p#\~/}" ;;
        /*) ;;
        *) p="$root/$p" ;;
    esac
    if [[ $p == *[\*\?\[]* ]]; then
        p="${p%%[\*\?\[]*}"
        [[ $p == */ ]] || p="$(dirname -- "$p")"
    fi
    p="${p%/}"
    printf '%s' "${p:-/}"
}

writable_roots=("$root" "$HOME/.cache" "$HOME/.local")
[[ -n ${CLAUDE_CODE_TMPDIR:-} ]] && writable_roots+=("$CLAUDE_CODE_TMPDIR")
for settings in "$HOME/.claude/settings.json" "$HOME/.claude/settings.local.json" \
                "$root/.claude/settings.json" "$root/.claude/settings.local.json" \
                "/Library/Application Support/ClaudeCode/managed-settings.json" \
                "/etc/claude-code/managed-settings.json"; do
    [[ -r $settings ]] || continue
    while IFS= read -r entry; do
        [[ -n $entry ]] && writable_roots+=("$(normalize_entry "$entry")")
    done < <(jq -r '(.sandbox.filesystem.allowWrite // [])[], (.permissions.additionalDirectories // [])[]
                    | strings' "$settings" 2>/dev/null)
done

writable_forms=()
for r in "${writable_roots[@]}"; do
    writable_forms+=("$r" "$(resolve "$r")")
done

is_writable_path() {
    local path="$1" form
    # The sandbox's own scratch space, by prefix: /tmp/claude, /tmp/claude-<uid>, ...
    [[ $path == /tmp/claude* || $path == /private/tmp/claude* ]] && return 0
    for form in "${writable_forms[@]}"; do
        [[ -n $form && ( $path == "$form" || $path == "$form"/* || $form == / ) ]] && return 0
    done
    return 1
}

# True when the path, any symlink on the way to its target, or the target itself
# sits under a writable root: a symlink in a writable directory can be re-pointed.
under_writable_root() {
    local path="$1" hops=0 link
    while :; do
        is_writable_path "$path" && return 0
        is_writable_path "$(resolve "$path")" && return 0
        [[ -L $path ]] || return 1
        link="$(readlink -- "$path")" || return 1
        [[ $link == /* ]] || link="$(dirname -- "$path")/$link"
        path="$link"
        (( ++hops > 40 )) && return 0
    done
}

src=""
for candidate in "${MAGPIE_CONTAINER_GATEWAY_SRC:-}" \
                 "$HOME/.claude/scripts/container-gateway/src"; do
    [[ -n $candidate && -d $candidate/container_gateway ]] || continue
    if under_writable_root "$candidate" || under_writable_root "$candidate/container_gateway"; then
        log "refusing gateway source $candidate: it is under a sandbox-writable directory"
        continue
    fi
    src="$(resolve "$candidate")"
    break
done
[[ -n $src ]] || exit 0

python_candidates=()
pin="$HOME/.claude/scripts/container-gateway/python"
if [[ -r $pin ]] && ! under_writable_root "$pin"; then
    IFS= read -r pinned < "$pin" || true
    [[ ${pinned:-} == /* ]] && python_candidates+=("$pinned")
fi
python_candidates+=(/opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3)
for minor in 14 13 12 11; do
    python_candidates+=("/opt/homebrew/bin/python3.$minor" "/usr/local/bin/python3.$minor" "/usr/bin/python3.$minor")
done

python=""
for candidate in "${python_candidates[@]}"; do
    [[ -x $candidate ]] || continue
    # Checked before it is ever run: the version probe below executes it.
    under_writable_root "$candidate" && continue
    "$candidate" -I -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1 || continue
    python="$candidate"
    break
done
if [[ -z $python ]]; then
    log "no trusted Python 3.11+ found outside sandbox-writable directories; not starting the container gateway (pin one in $pin)"
    exit 0
fi

# The only serve flags the hook will pass on from the environment. A value
# may be attached (--egress=require) or follow as the next token
# (--egress require); nothing else is accepted, and one bad token drops the
# whole variable.
allowed_flag='^--(egress|egress-port|egress-host|backend|backend-timeout|idle-timeout|log-level)(=.*)?$'

vet_extra_args() {
    # Echoes the vetted tokens; returns 1 when the variable must be ignored.
    local expecting=0 token
    for token in "$@"; do
        if (( expecting )); then
            expecting=0
            continue
        fi
        [[ $token =~ $allowed_flag ]] || return 1
        [[ $token == *=* ]] || expecting=1
    done
    (( expecting == 0 )) || return 1
    printf '%s\n' "$@"
}

if [[ $action == start ]]; then
    # shellcheck disable=SC2206  # word-splitting the extra args is the point
    extra=(${MAGPIE_CONTAINER_GATEWAY_ARGS:-})
    if (( ${#extra[@]} )) && ! vet_extra_args "${extra[@]}" >/dev/null; then
        printf '%s: ignoring MAGPIE_CONTAINER_GATEWAY_ARGS: %s is not an accepted serve flag\n' \
            "${0##*/}" "${MAGPIE_CONTAINER_GATEWAY_ARGS}" >&2
        extra=()
    fi
    args=(serve --project="$root" --daemon "${extra[@]}")
else
    args=(stop --project="$root")
fi

if [[ -n ${MAGPIE_CONTAINER_GATEWAY_DRY_RUN:-} ]]; then
    printf '%s -I %s container_gateway %s\n' "$python" "$src" "${args[*]}"
    exit 0
fi
# -I keeps every PYTHON* variable, the user site and the working directory off
# sys.path; the bootstrap puts the vetted source directory there and nothing else.
bootstrap='import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module("container_gateway", run_name="__main__", alter_sys=True)'
"$python" -I -c "$bootstrap" "$src" "${args[@]}" >/dev/null 2>&1 || true
exit 0
