#!/bin/bash -p
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
# container-gateway-dispatch.sh — the one command the managed-settings drop-in runs.
#
# Installed root-owned as <managed-settings dir>/magpie/container-gateway-dispatch
# (macOS /Library/Application Support/ClaudeCode/, Linux /etc/claude-code/) and
# registered for SessionStart / SessionEnd / PreToolUse in
# managed-settings.d/50-magpie-container-gateway.json. Managed settings apply to
# every account on the machine, so the drop-in must never name one user's
# script: that user could rewrite it and run code as whoever starts Claude Code
# next. Instead every account runs this dispatcher, which hands over to the
# INVOKING account's own ~/.claude/scripts/container-gateway-hook.sh, and only
# when that account alone can write it.
#
#   - The home directory comes from the account database (`~user`), never from
#     $HOME, which the session environment can redirect.
#   - The hook script, ~/.claude/scripts and ~/.claude must each be owned by the
#     invoking uid, must not be symlinks, and must not be group- or
#     world-writable. Anything else is a silent no-op: another account can never
#     plant what this one runs.
#   - Like the hook it calls, it never fails a session: every exit is 0, and an
#     account without the hook installed simply gets nothing.
#
# The payload on stdin and the action argument pass through unchanged; the hook
# does all the project checks. The shebang's -p keeps BASH_ENV and exported
# functions out, so it must be executed directly, never as `bash <path>`.
#
# MAGPIE_CONTAINER_GATEWAY_DRY_RUN=1 prints the hook it would run instead of
# running it; only then may MAGPIE_GATEWAY_DISPATCH_HOME replace the account
# home, so the test suite can use a home of its own.

set -uo pipefail
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

action="${1:-}"
case "$action" in
    start|stop|ensure) ;;
    *) printf '%s: expected start|stop|ensure, got "%s"\n' "${0##*/}" "$action" >&2; exit 0 ;;
esac

log() { printf '%s: %s\n' "${0##*/}" "$*" >&2; }

uid="$(id -u 2>/dev/null)" || exit 0
user="$(id -un 2>/dev/null)" || exit 0
[[ $user =~ ^[A-Za-z0-9._][A-Za-z0-9._-]*$ ]] || exit 0
home=""
eval "home=~$user"
if [[ -n ${MAGPIE_CONTAINER_GATEWAY_DRY_RUN:-} && -n ${MAGPIE_GATEWAY_DISPATCH_HOME:-} ]]; then
    home="$MAGPIE_GATEWAY_DISPATCH_HOME"
fi
[[ $home == /* && -d $home ]] || exit 0

# BSD stat (macOS) and GNU stat (Linux) spell the formats differently; GNU's -f means
# "file system", so the flavour is chosen by OS rather than by trying one after the other.
case "$(uname -s 2>/dev/null)" in
    Darwin|*BSD) stat_owner=(-f %u) stat_mode=(-f %p) ;;
    *) stat_owner=(-c %u) stat_mode=(-c %a) ;;
esac

owner_of() { stat "${stat_owner[@]}" -- "$1" 2>/dev/null; }

# The permission and sticky bits as up to four octal digits. BSD %p carries the file
# type in front (41777); its %Lp would drop the sticky bit.
mode_of() {
    local mode
    mode="$(stat "${stat_mode[@]}" -- "$1" 2>/dev/null)" || return 1
    mode="0000$mode"
    printf '%s\n' "${mode: -4}"
}

# True when an access-control list on <path> lets an account other than the
# invoking one (or root) modify or replace it; mode bits alone do not show that.
# macOS: any `allow` entry granting a write-class right to a principal other than
# this user. A `deny` entry, such as the `group:everyone deny delete` every macOS
# home carries, grants nothing. Linux: any extended POSIX ACL (the `+` after the
# mode string), since parsing getfacl portably is not worth the rarity.
foreign_acl_grant() {
    local path="$1" listing line entry saved_ifs
    local -a lines
    # A listing that cannot be read counts as a grant: this check fails closed.
    listing="$(ls -lde -- "$path" 2>/dev/null)" || listing="$(ls -ld -- "$path" 2>/dev/null)" || return 0
    [[ -n $listing ]] || return 0
    case "$(uname -s 2>/dev/null)" in
        Darwin)
            # Split without a here-string: bash 3.2 backs `<<<` with a temporary file,
            # and when it cannot create one the loop would read nothing and pass.
            saved_ifs="$IFS"
            IFS=$'\n'
            set -f
            # shellcheck disable=SC2206  # splitting on newlines is the point; globbing is off
            lines=($listing)
            set +f
            IFS="$saved_ifs"
            # Principals may contain spaces (`group:Domain Users`), so entries are not
            # parsed into fields: an entry is trusted only when it names this user
            # (whose name was validated to have none), and any other `allow` entry
            # with a write-class right is a grant, whatever its principal looks like.
            for line in "${lines[@]}"; do
                [[ $line =~ ^\ *[0-9]+:\ (.*)$ ]] || continue
                entry="${BASH_REMATCH[1]}"
                [[ $entry == "user:$user "* ]] && continue
                [[ $entry == *" allow "* && $entry =~ (write|append|delete|add_file|add_subdirectory|chown) ]] && return 0
            done
            return 1
            ;;
        *)
            [[ ${listing%%$'\n'*} =~ ^[^\ ]{10}\+ ]] && return 0
            return 1
            ;;
    esac
}

# True when only the invoking account can change <path>: owned by it, not a
# symlink, no group or other write bit, no ACL letting anyone else write it.
only_mine() {
    local path="$1" mode
    [[ -e $path && ! -L $path ]] || return 1
    [[ "$(owner_of "$path")" == "$uid" ]] || return 1
    mode="$(mode_of "$path")" || return 1
    [[ $mode =~ ^[0-7]+$ ]] || return 1
    (( (8#$mode & 8#022) == 0 )) || return 1
    ! foreign_acl_grant "$path"
}

# True when no account but root and the invoking one can replace an entry in the
# directory <path>: owned by one of them, and either no group or other write bit or
# the sticky bit (as on /tmp), under which only an entry's owner may rename it.
only_root_or_mine() {
    local path="$1" owner mode
    owner="$(owner_of "$path")" || return 1
    [[ $owner == 0 || $owner == "$uid" ]] || return 1
    mode="$(mode_of "$path")" || return 1
    [[ $mode =~ ^[0-7]+$ ]] || return 1
    (( (8#$mode & 8#022) == 0 || (8#$mode & 8#1000) != 0 )) || return 1
    ! foreign_acl_grant "$path"
}

hook="$home/.claude/scripts/container-gateway-hook.sh"
if [[ -L $hook ]]; then
    # A link's target can be swapped after these checks; the hook must be a plain copy.
    log "$hook is a symlink; replace it with a plain copy (rm it, then cp the framework's) to run the container-gateway hook"
    exit 0
fi
[[ -e $hook ]] || exit 0
# Every directory above the home, up to /: a writable one would let another account
# rename the home's entries away between these checks and the exec below.
ancestor="$home"
while [[ $ancestor != / ]]; do
    ancestor="$(dirname -- "$ancestor")"
    if ! only_root_or_mine "$ancestor"; then
        log "$ancestor is writable by another account; not running the container-gateway hook"
        exit 0
    fi
done
for path in "$home" "$home/.claude" "$home/.claude/scripts" "$hook"; do
    if ! only_mine "$path"; then
        log "$path is not owned and writable by $user alone; not running the container-gateway hook"
        exit 0
    fi
done
[[ -f $hook && -x $hook ]] || exit 0

if [[ -n ${MAGPIE_CONTAINER_GATEWAY_DRY_RUN:-} ]]; then
    printf '%s %s\n' "$hook" "$action"
    exit 0
fi
"$hook" "$action"
exit 0
