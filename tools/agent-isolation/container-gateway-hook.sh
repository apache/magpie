#!/bin/bash
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
#   this project grants, because setups grant them to every project. The one
#   exception is uv's managed interpreters, $HOME/.local/share/uv/python: the
#   reference setup keeps ~/.local/share/uv read-only to the sandbox and
#   sandbox-lint rejects a grant over it, so they are refused only when a
#   settings scope here grants it anyway. A machine where another project still
#   carries the old grant must drop it (sandbox-add-project-root.sh does).
#
#   The interpreter is never looked up on PATH, which a repository can set
#   through project settings. Candidates, in order: the absolute path in
#   $HOME/.claude/scripts/container-gateway/python (an operator pin, one line),
#   then fixed Homebrew and system locations, then uv-managed CPython under
#   $HOME/.local/share/uv/python (newest minor first). The first one outside every
#   writable root that is Python 3.11 or newer wins; none means the hook logs one
#   line and does nothing.
#
#   The gateway source is looked up in $MAGPIE_CONTAINER_GATEWAY_SRC (development
#   override), then $HOME/.claude/scripts/container-gateway/src (operator
#   install), and refused under a writable root like the interpreter. A copy
#   inside the repository -- including an .apache-magpie/ snapshot -- is never
#   used: the project root is always sandbox-writable.
#
#   The interpreter runs by its canonical path with -I -S, so PYTHONPATH,
#   PYTHONHOME, every other PYTHON* variable, site-packages (and any .pth file
#   or sitecustomize in it) and the working directory (the project being
#   opened) never reach sys.path; the source directory is put there explicitly
#   by a one-line bootstrap. Its prefix and standard library must not overlap a
#   writable root either, and neither may the source tree, file by file.
#
#   $MAGPIE_CONTAINER_GATEWAY_ARGS is allow-listed, token by token, against the
#   flags below (e.g. "--egress require"). Anything else -- notably
#   --extra-bind-root, which widens the bind-mount roots -- makes the hook ignore
#   the whole variable and log one line to stderr rather than start a gateway
#   with a policy the repository chose.
#
# MAGPIE_CONTAINER_GATEWAY_DRY_RUN=1 prints the command instead of running it.

set -uo pipefail

# Every helper this hook runs (jq, git, readlink, dirname, find) comes from the
# root-owned system directories, never from an inherited PATH that project
# settings can set, nor from a package-manager prefix a sandbox grant could
# cover. The shebang names /bin/bash for the same reason; the script keeps to
# bash 3.2.
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

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

# System and package-manager locations. The hook refuses to run at all when a
# write grant overlaps one (below), so nothing inside them is writable or
# re-pointable from the sandbox.
system_dirs=(/usr /opt /Library /System /Applications /nix /etc /private/etc /bin /sbin /lib /lib64)

in_system_dir() {
    local path="$1" dir
    for dir in "${system_dirs[@]}"; do
        [[ $path == "$dir" || $path == "$dir"/* ]] && return 0
    done
    return 1
}

# True when following <link>'s target one component at a time never leaves
# <inside> except to pass through its ancestors (which no writable root can
# hold, or <inside> would already be refused) or a system location (which no
# writable root may overlap): Debian's /usr/lib/python3.X links into /etc.
link_stays_inside() {
    local link="$1" inside="$2" target cur part
    local -a parts
    target="$(readlink -- "$link")" || return 1
    if [[ $target == /* ]]; then cur=""; else cur="$(dirname -- "$link")"; fi
    IFS=/ read -r -a parts <<< "$target"
    for part in ${parts[@]+"${parts[@]}"}; do
        case "$part" in
            ""|.) continue ;;
            ..) cur="${cur%/*}" ;;
            *) cur="$cur/$part" ;;
        esac
        # A component that is itself a symlink is followed physically, hop by
        # hop: inside the prefix by name, it could still route through ~/.cache.
        [[ -L $cur ]] && under_writable_root "$cur" && return 1
        [[ -z $cur || $cur == "$inside" || $cur == "$inside"/* || $inside == "$cur"/* ]] && continue
        in_system_dir "$cur" || return 1
    done
    return 0
}

# Physical path, symlinks resolved; the literal path when it does not exist.
resolve() {
    local p
    p="$(readlink -f -- "$1" 2>/dev/null)" && [[ -n $p ]] && { printf '%s' "$p"; return; }
    printf '%s' "$1"
}

# A settings path entry as absolute directories, one per line: `//x` and `~`
# expanded, relative entries taken from the settings file's root (<base>), and
# any glob cut back to the directory that holds it. A single-slash `/x` is
# absolute for sandbox paths but relative to <base> for permission rules, so it
# yields both: a root counted twice only refuses more.
normalize_entry() {
    local entry="$1" base="$2" p b
    local -a forms bases
    # Sandbox paths and permission rules resolve relative entries differently
    # (settings directory, project root, session cwd), so a relative entry
    # counts against every one of them; a root counted twice only refuses more.
    bases=("$base" "$root")
    [[ -n ${main_root:-} ]] && bases+=("$main_root")
    case "$entry" in
        */../*|*/..|../*|..) forms=("/") ;;  # not folded: refuse everything
        //*) forms=("/${entry#//}") ;;
        "~") forms=("$HOME") ;;
        "~/"*) forms=("$HOME/${entry#\~/}") ;;
        /*) forms=("$entry"); for b in "${bases[@]}"; do forms+=("$b$entry"); done ;;
        *) forms=(); for b in "${bases[@]}"; do forms+=("$b/${entry#./}"); done ;;
    esac
    for p in "${forms[@]}"; do
        if [[ $p == *[\*\?\[]* ]]; then
            p="${p%%[\*\?\[]*}"
            [[ $p == */ ]] || p="$(dirname -- "$p")"
        fi
        p="${p%/}"
        printf '%s\n' "${p:-/}"
    done
}

writable_roots=("$root" "$HOME/.cache")
# $HOME/.local is refused too, all but uv's managed interpreters (see the header);
# kept out of writable_roots so a settings grant over them still counts in full.
home_local="$HOME/.local"
uv_python_dir="$HOME/.local/share/uv/python"
# The exemption holds only for a real directory reached without a symlink:
# a linked ~/.local/share/uv/python (or a linked parent) could point anywhere.
uv_exempt=0
[[ -d $uv_python_dir && "$(resolve "$uv_python_dir")" == "$uv_python_dir" ]] && uv_exempt=1
[[ -n ${CLAUDE_CODE_TMPDIR:-} ]] && writable_roots+=("$CLAUDE_CODE_TMPDIR")
# Each settings file with the root its relative entries resolve against.
# In a linked worktree Claude Code also reads the main checkout's settings,
# and the main checkout is as writable as the worktree.
# The worktree's own `.git` file names the main checkout and is as writable as
# the worktree, so the main checkout counts only when its
# `worktrees/<name>/gitdir` points back here; otherwise the hook refuses.
main_root=""
if [[ -f $root/.git ]]; then
    git_dir="$(git -C "$root" rev-parse --absolute-git-dir 2>/dev/null || true)"
    common_dir="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
    # The git dir must be exactly <common>/worktrees/<name>, and the back-pointer
    # is read from the common dir, not from wherever the .git file says.
    back=""
    if [[ -n $git_dir && -n $common_dir ]]; then
        expected="$(resolve "$common_dir")/worktrees/$(basename -- "$git_dir")"
        [[ "$(resolve "$git_dir")" == "$expected" && -r $expected/gitdir ]] && IFS= read -r back < "$expected/gitdir"
    fi
    if [[ $common_dir != */.git || -z $back \
          || "$(resolve "$back")" != "$(resolve "$root/.git")" ]]; then
        log "cannot confirm the main checkout of linked worktree $root; not starting the container gateway"
        exit 0
    fi
    main_root="$(cd "${common_dir%/.git}" 2>/dev/null && pwd -P)" || main_root=""
    [[ $main_root == "$root" ]] && main_root=""
fi
settings_specs=("$HOME/.claude/settings.json|$HOME/.claude"
                "$HOME/.claude/settings.local.json|$HOME/.claude"
                "$root/.claude/settings.json|$root"
                "$root/.claude/settings.local.json|$root")
if [[ -n $main_root ]]; then
    writable_roots+=("$main_root")
    settings_specs+=("$main_root/.claude/settings.json|$main_root"
                     "$main_root/.claude/settings.local.json|$main_root")
fi
settings_specs+=("/Library/Application Support/ClaudeCode/managed-settings.json|/Library/Application Support/ClaudeCode"
                 "/etc/claude-code/managed-settings.json|/etc/claude-code")
for spec in "${settings_specs[@]}"; do
    settings="${spec%|*}" base="${spec##*|}"
    [[ -r $settings ]] || continue
    if ! command -v jq >/dev/null 2>&1; then
        log "no jq in /usr/bin or /bin to read $settings; not starting the container gateway"
        exit 0
    fi
    while IFS= read -r entry; do
        [[ -n $entry ]] || continue
        while IFS= read -r form; do
            writable_roots+=("$form")
        done < <(normalize_entry "$entry" "$base")
    # Edit/Write allow rules merge into the sandbox's write access too; a bare
    # `Edit` (every file) comes out as `//`, i.e. the filesystem root.
    done < <(jq -r '(.sandbox.filesystem.allowWrite // [])[], (.permissions.additionalDirectories // [])[],
                    ((.permissions.allow // [])[] | strings
                     | if test("^(Edit|Write|MultiEdit|NotebookEdit)$") then "//"
                       else (capture("^(Edit|Write|MultiEdit|NotebookEdit)\\((?<p>.*)\\)$").p // empty) end)
                    | strings' "$settings" 2>/dev/null)
done

writable_forms=()
for r in "${writable_roots[@]}"; do
    writable_forms+=("$r" "$(resolve "$r")")
done

# The hook trusts only system and package-manager locations for what it runs,
# native libraries included (Homebrew's OpenSSL for _ssl, say), so a sandbox
# grant over any of them leaves nothing it can vouch for.
for form in "${writable_forms[@]}"; do
    if [[ $form == / ]] || in_system_dir "$form"; then
        log "a sandbox write grant covers $form, a system location; not starting the container gateway"
        exit 0
    fi
done

is_writable_path() {
    local path="$1" form local_form
    # The sandbox's own scratch space, by prefix: /tmp/claude, /tmp/claude-<uid>, ...
    [[ $path == /tmp/claude* || $path == /private/tmp/claude* ]] && return 0
    for local_form in "$home_local" "$(resolve "$home_local")"; do
        [[ $path == "$local_form" || $path == "$local_form"/* ]] || continue
        (( uv_exempt )) && [[ $path == "$uv_python_dir"/* ]] && continue
        return 0
    done
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

# True when a directory is under a writable root, or a writable root is inside
# it: a grant on one file in an interpreter's prefix or the gateway source makes
# that file writable just the same.
overlaps_writable() {
    local dir form
    dir="$(resolve "$1")"
    is_writable_path "$dir" && return 0
    [[ $dir == / || /tmp/claude == "$dir"/* || /private/tmp/claude == "$dir"/* ]] && return 0
    for form in "${writable_forms[@]}"; do
        [[ -n $form && $form == "$dir"/* ]] && return 0
    done
    return 1
}

# A source tree the hook may put on sys.path: not overlapping a writable root,
# and holding no symlink (the operator install is a plain copy), so every file
# in it is judged where it really is.
tree_is_trusted() {
    local dir="$1" entry
    overlaps_writable "$dir" && return 1
    while IFS= read -r -d '' entry; do
        [[ -L $entry ]] && return 1
        under_writable_root "$entry" && return 1
    done < <(find "$dir" -mindepth 1 -print0 2>/dev/null)
    return 0
}

src=""
for candidate in "${MAGPIE_CONTAINER_GATEWAY_SRC:-}" \
                 "$HOME/.claude/scripts/container-gateway/src"; do
    [[ -n $candidate ]] || continue
    if [[ $candidate != /* ]]; then
        log "refusing gateway source $candidate: not an absolute path"
        continue
    fi
    # Resolved once: the path judged below is the path that runs, so no
    # symlink on the way can be re-pointed in between.
    canonical="$(readlink -f -- "$candidate" 2>/dev/null)" || continue
    [[ -n $canonical && -d $canonical/container_gateway ]] || continue
    # The whole directory goes on sys.path, so a stray json.py beside the
    # package would shadow the stdlib: judge all of it, by its real location.
    if under_writable_root "$candidate" || ! tree_is_trusted "$canonical"; then
        log "refusing gateway source $candidate: it is, contains or links into a sandbox-writable directory"
        continue
    fi
    src="$canonical"
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
# uv-managed CPython, newest minor first; the free-threaded builds are left out.
for minor in 14 13 12 11; do
    found=()
    for uv_python in "$uv_python_dir"/cpython-3."$minor".*/bin/python3."$minor"; do
        [[ -x $uv_python && $uv_python != *freethreaded* ]] && found+=("$uv_python")
    done
    # The glob sorts patch releases oldest first; take the newest first.
    for (( i = ${#found[@]} - 1; i >= 0; i-- )); do
        python_candidates+=("${found[i]}")
    done
done
for minor in 14 13 12 11; do
    python_candidates+=("/opt/homebrew/bin/python3.$minor" "/usr/local/bin/python3.$minor" "/usr/bin/python3.$minor")
done

# Run by its canonical path, so no symlink on the way can be re-pointed between
# this check and the exec, and with -I -S: the gateway needs only the standard
# library, so no site-packages, .pth file or sitecustomize is ever loaded.
python=""
for candidate in "${python_candidates[@]}"; do
    [[ -x $candidate ]] || continue
    # Checked before it is ever run: the probes below execute it.
    under_writable_root "$candidate" && continue
    canonical="$(readlink -f -- "$candidate" 2>/dev/null)" || continue
    [[ -n $canonical && -x $canonical ]] || continue
    # Judged before the first exec, from the layout alone: a real installation
    # keeps its standard library in <prefix>/lib/python3.*, which rules out
    # virtualenvs (their base runtime could be anywhere) and launcher stubs
    # such as macOS's /usr/bin/python3, which execs another interpreter.
    prefix="$(dirname -- "$(dirname -- "$canonical")")"
    [[ -e $prefix/pyvenv.cfg || -e $(dirname -- "$canonical")/pyvenv.cfg ]] && continue
    stdlib_found=0
    for stdlib in "$prefix"/lib/python3.*/os.py; do
        [[ -f $stdlib ]] && { stdlib_found=1; break; }
    done
    (( stdlib_found )) || continue
    overlaps_writable "$prefix" && continue
    # What -I -S loads: the standard library (a real directory) and the shared
    # libpython beside it. Every symlink there stays inside the prefix or a
    # system location at each step of its target and once resolved, so no hop
    # can lead out to something re-pointable. site-packages / dist-packages are
    # exempt: -S never loads them.
    stdlib_dir="${stdlib%/os.py}"
    [[ -L $prefix/lib || -L $stdlib_dir ]] && continue
    runtime_ok=1
    while IFS= read -r -d '' link; do
        case "$link" in
            "$stdlib_dir/site-packages"|"$stdlib_dir/dist-packages") continue ;;
        esac
        real="$(resolve "$link")"
        if ! link_stays_inside "$link" "$prefix" || { [[ $real != "$prefix"/* ]] && ! in_system_dir "$real"; }; then
            runtime_ok=0
            break
        fi
    done < <(find "$stdlib_dir" -type l -print0 2>/dev/null; find "$prefix/lib" -maxdepth 1 -type l -print0 2>/dev/null)
    (( runtime_ok )) || continue
    "$canonical" -I -S -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1 || continue
    # Where the interpreter really loads its standard library from.
    runtime_ok=1
    while IFS= read -r dir; do
        [[ -n $dir ]] && overlaps_writable "$dir" && { runtime_ok=0; break; }
    done < <("$canonical" -I -S -c 'import sys, sysconfig; print(sys.prefix); print(sys.base_prefix); print(sysconfig.get_path("stdlib")); print(sysconfig.get_path("platstdlib"))' 2>/dev/null)
    (( runtime_ok )) || continue
    python="$canonical"
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
    if (( ${#extra[@]} )) && ! vet_extra_args ${extra[@]+"${extra[@]}"} >/dev/null; then
        printf '%s: ignoring MAGPIE_CONTAINER_GATEWAY_ARGS: %s is not an accepted serve flag\n' \
            "${0##*/}" "${MAGPIE_CONTAINER_GATEWAY_ARGS}" >&2
        extra=()
    fi
    # ${extra[@]+...}: bash 3.2 treats an empty array as unset under set -u.
    args=(serve --project="$root" --daemon ${extra[@]+"${extra[@]}"})
else
    args=(stop --project="$root")
fi

if [[ -n ${MAGPIE_CONTAINER_GATEWAY_DRY_RUN:-} ]]; then
    printf '%s -I -S %s container_gateway %s\n' "$python" "$src" "${args[*]}"
    exit 0
fi
# -I keeps every PYTHON* variable, the user site and the working directory off
# sys.path, -S every site-packages directory; the bootstrap puts the vetted
# source directory there and nothing else.
bootstrap='import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module("container_gateway", run_name="__main__", alter_sys=True)'
"$python" -I -S -c "$bootstrap" "$src" "${args[@]}" >/dev/null 2>&1 || true
exit 0
