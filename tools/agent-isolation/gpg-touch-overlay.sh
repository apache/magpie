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
# gpg-touch-overlay.sh — Claude Code PreToolUse/PostToolUse hook (Bash matcher).
#
# Shows a window while gpg blocks waiting for a touch on a hardware
# signing key (YubiKey, Nitrokey, any OpenPGP card).
#
# A key whose signature slot has a touch policy of `on` or `cached`
# (`ykman openpgp info`) needs a physical touch for every signature. gpg
# puts a pinentry window on screen for the *PIN* and nothing at all for
# the *touch* — it simply blocks, and `git commit` sits there until the
# key is touched or gpg gives up with "signing failed: Timeout". There is
# nothing to distinguish it from a hung command.
#
# Two commands reach that key and both are watched: gpg itself, and the
# `ssh-keygen -Y sign` git runs when it is configured with
# `gpg.format=ssh` — that one signs over gpg-agent's ssh socket and
# starts no gpg at all.
#
# The key's *authentication* slot can carry a touch policy of its own,
# and then every ssh transport — `git pull`, `fetch`, `push`, `clone`
# over an ssh remote — waits for a touch before a byte moves. That wait
# has no process name to match: the ssh git spawns looks the same
# blocked on the key as it does busy transferring for a minute. What it
# does have is an open connection to the agent's socket. ssh opens one,
# sends the sign request, and closes it as soon as the answer is back;
# while a transfer runs there is none. The kernel lists the agent's end
# of every such connection under the socket's path, so the watcher
# counts those rows against the number it saw when the watch began.
#
# This is the other half of the hardware-key rule in AGENTS.md
# ("Commit and PR conventions"). That rule has the agent probe the PIN
# cache and warn *before* committing; gpg-agent's `keyinfo` reports the
# PIN cache only, so a key with a warm PIN and a cold touch still blocks
# with no prompt at all. This covers that case from the other side, at
# the moment gpg is actually waiting.
#
# The window itself is GTK on Linux (zenity where PyGObject is missing)
# and Tk on macOS, which has neither — see the two window scripts next to
# this one.
#
#   arm     PreToolUse  — a git command that might sign is about to run;
#                         start a watcher that shows the window if and
#                         when signing actually blocks.
#   disarm  PostToolUse — the command is done; tear the watcher down.
#   wrap    git config  — not a hook at all: git runs this *as* its
#                         signing program (`gpg.ssh.program`,
#                         `gpg.program`) or its ssh command
#                         (`core.sshCommand`), and it runs the real one
#                         with a watcher alive for exactly that long.
#                         What covers a commit or push made from a
#                         terminal, where no hook of the agent's runs.
#
# Each of those is a *signing context*, and a context owns its watcher:
# an agent session, keyed by the session id both of its hooks carry, and
# a wrapped git, keyed by the wrapper's own pid. A context may take down
# the watcher it started and no other. That ownership is the whole point
# of the registry under `owners/`: two sessions signing at once, or a
# terminal git signing beside one, used to share a single pid file, and
# sharing it meant either could kill a watcher it did not start (a touch
# that blocks with no window) or overwrite the only record of one (a
# window that nothing is left to close). A context whose owner process
# is gone is swept by the next one to arm, so a session that crashed
# without disarming costs nothing rather than a window that stays up
# until MAX_WAIT.
#
# What stays shared is the window, because one touch should draw one
# window however many watchers can see it. It is leased, not owned:
# whichever watcher creates the lock directory first shows it, and the
# lease is reclaimed if that watcher dies holding it.
#
# The watcher, not the hook, decides whether anything is shown:
#
#   * `pgrep -x gpg` — a signing gpg is in flight. Matching on the exact
#     process name matters: `pgrep -f` would match the hook's own command
#     line and report a signature that is not happening.
#   * the agent socket has more connections than it had at arm time —
#     ssh, or `ssh-keygen -Y sign`, has a request out to the agent and
#     is waiting on the key's answer. See above.
#   * `pgrep -x 'pinentry.*'` — pinentry is up, so the PIN is being asked
#     for. The window stays hidden then; two dialogs competing for focus
#     would make the PIN impossible to type.
#   * SHOW_DELAY — a signature with a still-cached touch finishes in well
#     under a second. Nothing is shown until gpg has blocked for longer
#     than that, so ordinary commits stay silent.
#
# So arming is cheap and deliberately over-broad: it costs one background
# process that disarm tears down when the command ends. The watcher lives
# for the whole command, not for one signature: a rebase signs every
# commit it replays, and a hook may run a look-alike before git signs at
# all — a test suite that starts a process named ssh-keygen, say. A
# watcher that left with the first one would be gone when the real
# signature blocked.
#
# Dismissing the window with its button is honoured — it is a prompt, not
# a trap, and gpg keeps waiting either way. It is not re-shown for the
# same signature, by the watcher that drew it or by any other: the
# dismissal is recorded where every watcher can see it, and cleared once
# the last context has disarmed.

set -uo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SELF
readonly OVERLAY_WINDOW="${SELF%/*}/gpg-touch-overlay-window.py"
readonly OVERLAY_WINDOW_MACOS="${SELF%/*}/gpg-touch-overlay-window-macos.py"

PLATFORM="$(uname -s)"
readonly PLATFORM

readonly TITLE="Touch your security key"
readonly BODY="<b>Your security key is waiting for a touch.</b>

Touch the key's contact now — the git command is blocked until you do.
This window closes by itself once the touch registers."

readonly SHOW_DELAY=8     # polls a signature must block before showing (0.2s each)
readonly MAX_WAIT=600     # seconds the watcher may live, whatever happens
readonly POLL=0.2

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/magpie-gpg-touch"

# One registration per signing context, never one pid file for all of
# them. Two agent sessions sign at the same time often enough, and a
# terminal git signs beside them, and a single shared file gave every
# one of them the power to kill a watcher it did not start: whoever
# disarmed first took down whatever was in the file, and two arms that
# raced both wrote to it, so the loser's watcher became unreachable and
# ran on with its window up. A file per owner removes the sharing, so
# the question "is this mine to kill?" always has an answer.
readonly OWNERS_DIR="$RUNTIME_DIR/owners"

# The window is the one thing that must stay single across owners, so it
# is leased rather than owned: an atomic directory create, which is the
# one primitive both macOS and Linux have without flock(1).
readonly WINDOW_LOCK="$RUNTIME_DIR/window.lock"
readonly DISMISSED_MARKER="$RUNTIME_DIR/dismissed"

# Logging is switched on by the environment or by a marker file. The
# file is for the case that matters most: a hook runs with the
# harness's environment, which nobody can set a variable in from a
# terminal, but anyone can `touch` the marker there.
_debugging() { [[ -n ${MAGPIE_GPG_TOUCH_DEBUG:-} || -e $RUNTIME_DIR/debug ]]; }

# A signature is in flight: gpg itself, or the `ssh-keygen -Y sign` git
# runs under `gpg.format=ssh`. That one signs through gpg-agent's ssh
# socket without ever starting gpg, so watching for gpg alone is blind to
# an ssh-signed commit — the same key, the same touch, no window.
# Exact-name match only — see the header.
signing_in_flight() {
    # Under `wrap` around a signing program the watcher lives exactly as
    # long as that program does, so its being alive *is* the signature
    # in flight -- no process-name probe needed (and none possible from
    # a sandbox that denies pgrep).
    [[ -n ${MAGPIE_GPG_TOUCH_WRAPPED_SIGNER:-} ]] && return 0
    pgrep -x 'gpg|gpg2|ssh-keygen' >/dev/null 2>&1
}

# pinentry is asking for the PIN and owns the screen.
pinentry_up() { pgrep -x 'pinentry.*' >/dev/null 2>&1; }

# The ssh agent sockets a request to the key can arrive through: gpg-agent's
# (ssh transport and `ssh-keygen -Y sign` under `enable-ssh-support`) and
# whatever SSH_AUTH_SOCK names, which is usually the same file and
# otherwise the system ssh-agent. One path per line, deduplicated.
agent_sockets() {
    {
        gpgconf --list-dirs agent-ssh-socket 2>/dev/null
        [[ -n ${SSH_AUTH_SOCK:-} ]] && printf '%s\n' "$SSH_AUTH_SOCK"
    } | sed '/^$/d' | sort -u
}

# Rows the kernel's unix-socket table holds for the sockets in $1 (one
# path per line): the listener, plus one for each connection the agent
# has accepted and not yet closed. Linux keeps the table in /proc and
# lists an accepted socket under the path it was accepted on; macOS has
# no /proc, and lsof's unix-socket listing shows the same rows there.
# The absolute number means little — what the watcher reads is the
# change against its baseline.
agent_socket_rows() {
    local sockets=$1 rows
    [[ -n $sockets ]] || { printf '0\n'; return 0; }
    if [[ -r /proc/net/unix ]]; then
        rows="$(grep -cF -f <(printf '%s\n' "$sockets") /proc/net/unix 2>/dev/null)"
    else
        rows="$(lsof -U -n 2>/dev/null | grep -cF -f <(printf '%s\n' "$sockets"))"
    fi
    printf '%s\n' "${rows:-0}"
}

# ---------------------------------------------------------------- arm ---

# Subcommands that can reach the key: the ones that sign under this
# config, and the ones that talk to a remote and so authenticate over
# ssh. Broad on purpose: a false positive costs one short-lived watcher,
# a false negative costs a silent block with no window. The subcommand
# may be followed by whitespace, the end of the command, or whatever
# ends a shell word — `git commit;`, `git commit)` and `git commit | tee`
# sign just as much as `git commit -m`.
readonly KEY_SUBCOMMANDS='commit|tag|merge|rebase|revert|cherry-pick|am|push|pull|fetch|clone|ls-remote|remote|submodule'

# A screen to draw on, and something to draw the window with.
#
# On macOS both questions collapse into one: a logged-in user always has
# the window server — there is no DISPLAY to test — and the fallbacks the
# Linux side leans on do not exist there, so the only thing left to ask is
# whether a python that can import tkinter is around.
_gui_available() {
    # Test seam: the ownership tests need arm to really spawn a watcher,
    # which the dry-run seam cannot do -- it reports and returns.
    [[ -n ${MAGPIE_GPG_TOUCH_ASSUME_GUI:-} ]] && return 0
    if [[ $PLATFORM == Darwin ]]; then
        _tk_python >/dev/null
    else
        [[ -n ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]] || return 1
        command -v zenity >/dev/null 2>&1 || _gi_python >/dev/null
    fi
}

# The prefix that makes a command the leader of its own session, so the
# single group kill in disarm takes down the watcher and any window it
# spawned. macOS ships no setsid(1); perl's POSIX::setsid does the same
# job.
#
# A prefix rather than a wrapper function on purpose: the caller records
# `$!` as the group to kill, so whatever it backgrounds has to *become*
# the watcher. A function would put a subshell in between, and the pid
# written to the file would lead no group at all — disarm would then kill
# nothing and leave the window up.
SESSION_LAUNCHER=()
_set_session_launcher() {
    if command -v setsid >/dev/null 2>&1; then
        SESSION_LAUNCHER=(setsid)
    else
        SESSION_LAUNCHER=(perl -e 'use POSIX qw(setsid); setsid() or die "setsid: $!"; exec @ARGV or die "exec: $!"' --)
    fi
}

# ---------------------------------------------------------- ownership ---

# The key a signing context is known by, stable from its arm to its
# disarm and distinct from every other context's. An agent session is
# identified by the session id the harness puts in both hook payloads;
# a wrapped git by the wrapper's own pid. The fallback covers a harness
# that sends no session id: the hook's parent is the harness process,
# which is the same for that session's arm and its disarm.
_owner_id() {
    local session=${1:-}
    [[ -z $session ]] && session=${CLAUDE_SESSION_ID:-}
    if [[ -n $session ]]; then
        printf 's-%s\n' "${session//[^A-Za-z0-9_-]/_}"
        return 0
    fi
    printf 'h-%s\n' "$PPID"
}

# A registration records two pids: the owner, whose death means the
# context is gone however it went, and the watcher, which is the only
# process this owner may kill. Written through a temporary file so a
# reader never sees half a line.
_register() {
    local id=$1 owner=$2 watcher=$3 tmp="$OWNERS_DIR/.$1.$$"
    printf '%s %s\n' "$owner" "$watcher" >"$tmp" 2>/dev/null &&
        mv -f "$tmp" "$OWNERS_DIR/$id" 2>/dev/null
}

# Sets _owner_pid / _watcher_pid from a registration, or fails.
_owner_pid=""
_watcher_pid=""
_read_registration() {
    local id=$1 reg="$OWNERS_DIR/$id"
    _owner_pid=""
    _watcher_pid=""
    # Tested before the redirection, not around it: a `<` on a file that
    # is not there fails before any `2>` on the same command applies, and
    # the shell's complaint would land on the hook's stderr.
    [[ -r $reg ]] || return 1
    read -r _owner_pid _watcher_pid <"$reg" || return 1
    [[ -n $_owner_pid && -n $_watcher_pid ]]
}

# Take down one owner's watcher: the group, for the window it may have
# spawned, and the pid itself for a watcher too young to have called
# setsid and leading no group of its own.
_kill_watcher() {
    kill -- -"$1" "$1" 2>/dev/null || true
}

# A context whose owner is gone left its watcher behind, and a watcher
# nobody will disarm holds its window until MAX_WAIT. This is what turns
# a crashed session from a ten-minute stuck overlay into nothing at all.
_sweep_owners() {
    local reg id
    for reg in "$OWNERS_DIR"/*; do
        [[ -e $reg ]] || continue
        id=${reg##*/}
        if ! _read_registration "$id"; then
            rm -f "$reg" 2>/dev/null
            continue
        fi
        if ! kill -0 "$_owner_pid" 2>/dev/null; then
            _kill_watcher "$_watcher_pid"
            rm -f "$reg" 2>/dev/null
        fi
    done
}

# Nothing is signing anywhere: drop the shared state, so the next touch
# starts from a clean slate rather than inheriting a dismissal or a lock
# left by a holder that is no longer around.
_cleanup_if_idle() {
    local reg
    for reg in "$OWNERS_DIR"/*; do
        [[ -e $reg ]] && return 0
    done
    rm -f "$DISMISSED_MARKER" 2>/dev/null
    [[ -n ${WINDOW_LOCK:-} ]] && rm -rf "$WINDOW_LOCK" 2>/dev/null
    return 0
}

# ------------------------------------------------------- window lease ---

# mkdir either creates the directory or it does not, and only one caller
# can be the one that did -- no lock file, no flock(1), nothing to leave
# half-written. The holder writes its pid inside so a lease left by a
# watcher that died can be told from one in use, and reclaimed.
_lease_acquire() {
    if mkdir "$WINDOW_LOCK" 2>/dev/null; then
        printf '%s\n' "$$" >"$WINDOW_LOCK/holder" 2>/dev/null
        return 0
    fi
    local holder
    holder="$(cat "$WINDOW_LOCK/holder" 2>/dev/null || true)"
    if [[ -z $holder ]] || ! kill -0 "$holder" 2>/dev/null; then
        rm -rf "$WINDOW_LOCK" 2>/dev/null
        if mkdir "$WINDOW_LOCK" 2>/dev/null; then
            printf '%s\n' "$$" >"$WINDOW_LOCK/holder" 2>/dev/null
            return 0
        fi
    fi
    return 1
}

_lease_held() {
    [[ "$(cat "$WINDOW_LOCK/holder" 2>/dev/null || true)" == "$$" ]]
}

_lease_release() {
    _lease_held || return 0
    rm -rf "$WINDOW_LOCK" 2>/dev/null
}

arm() {
    if [[ -z ${MAGPIE_GPG_TOUCH_DRY_RUN:-} ]]; then
        _gui_available || return 0
    fi

    local payload command_text session
    payload="$(cat)"
    command_text="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null)"
    [[ -n $command_text ]] || return 0
    session="$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)"

    printf '%s' "$command_text" |
        grep -Eq "(^|[;&|(]|[[:space:]])git([[:space:]]+-[A-Za-z-]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+($KEY_SUBCOMMANDS)([[:space:];&|)]|$)" ||
        return 0

    # Test seam: report the decision instead of spawning a watcher, so
    # the command matcher can be exercised without an X display.
    if [[ -n ${MAGPIE_GPG_TOUCH_DRY_RUN:-} ]]; then
        printf 'arm\n'
        return 0
    fi

    mkdir -p "$OWNERS_DIR" 2>/dev/null || return 0
    _sweep_owners

    # One watcher per session, not one per command: a session that is
    # already armed is signing under a watcher it owns, and a second
    # command in the same session rides along with it.
    local id
    id="$(_owner_id "$session")"
    if _read_registration "$id" && kill -0 "$_watcher_pid" 2>/dev/null; then
        return 0
    fi

    # The watcher leads its own process group, so disarm can take down the
    # window it spawned with a single group kill.
    # Every writer to the log appends — the watcher's trace, the window's
    # output, the environment line — because a single non-append writer
    # would overwrite the others' lines at its own offset. The truncation
    # is separate, once, here.
    local log=/dev/null
    if _debugging; then
        log="$RUNTIME_DIR/watcher.log"
        : >"$log"
    fi
    _set_session_launcher
    # The watcher is told whose it is. A hook exits the moment it has
    # spawned, so the process worth watching for is the harness itself:
    # if that goes, the disarm is never coming, and the watcher should
    # not wait out MAX_WAIT to find that out.
    MAGPIE_GPG_TOUCH_PARENT=$PPID \
        "${SESSION_LAUNCHER[@]}" "$SELF" _watch >>"$log" 2>&1 &
    _register "$id" "$PPID" "$!"
}

# ------------------------------------------------------------- disarm ---

disarm() {
    # The same payload the arm hook was given, read for the same session
    # id. Only when something is actually piped in: run by hand from a
    # terminal there is nobody to send EOF, and a disarm that hangs would
    # hang the tool call it belongs to.
    local payload="" session=""
    if [[ ! -t 0 ]]; then
        payload="$(cat)"
        session="$(printf '%s' "$payload" | jq -r '.session_id // empty' 2>/dev/null)"
    fi

    local id
    id="$(_owner_id "$session")"
    if _read_registration "$id"; then
        _kill_watcher "$_watcher_pid"
        rm -f "$OWNERS_DIR/$id" 2>/dev/null
    fi
    # Somebody else's crashed session is nobody's to wait for.
    _sweep_owners
    _cleanup_if_idle
}

# --------------------------------------------------------------- wrap ---

# `wrap PROGRAM [ARGS...]` runs PROGRAM with a watcher alive for exactly as
# long as it runs, and exits with PROGRAM's status. This is the entry point
# for git itself rather than for a Claude Code hook: git names the program
# it signs with (`gpg.program`, `gpg.ssh.program`) and the one it reaches
# an ssh remote with (`core.sshCommand`), so pointing those at this
# wrapper covers every commit, tag, rebase, pull and push from any
# terminal -- no git hook type sits at the right moment for either
# (commit-msg/post-commit bracket only `git commit`; pre-push runs after
# ssh has already authenticated).
#
#   git config --global gpg.ssh.program  ~/.claude/scripts/gpg-touch-wrap-ssh-keygen
#   git config --global core.sshCommand "~/.claude/scripts/gpg-touch-overlay.sh wrap ssh"
#
# `gpg.ssh.program` is exec'd as one path, not shell-split, so it needs an
# argument-free entry: a symlink named `gpg-touch-wrap-<program>` to this
# script wraps <program> (see the basename dispatch at the bottom).
#
# Never two windows for one signature. Inside an agent session (Claude
# Code sets CLAUDECODE=1) the hook has armed a watcher already and the
# wrapper only runs the program; outside one, a watcher somebody else
# armed -- the pid file says so -- is left alone and not torn down here.
wrap() {
    local program=$1; shift
    local real="" candidate
    # The real program: first match on PATH that is not this script under
    # another name.
    while IFS= read -r candidate; do
        [[ "$(readlink -f "$candidate" 2>/dev/null)" == "$SELF" ]] && continue
        real=$candidate; break
    done < <(command -v -a "$program" 2>/dev/null || true)
    [[ -n $real ]] || real=$program

    # Which invocations reach the key. A signing program is also git's
    # verifier (`git log --show-signature` runs `ssh-keygen -Y verify`
    # per commit, `gpg --verify` likewise), and those never touch the
    # key: straight through, no watcher, no display probe.
    local signer=""
    case "${program##*/}" in
        ssh-keygen) [[ ${1:-} == -Y && ${2:-} == sign ]] && signer=1 || exec "$real" "$@" ;;
        gpg|gpg2)   [[ " $* " == *" -bsau "* ]] && signer=1 || exec "$real" "$@" ;;
    esac

    # Inside an agent session the hook is in charge: it armed a watcher
    # outside the sandbox before this command started, and it will tear
    # that one down. The wrapper stands aside there whatever it could
    # see -- one watcher, one window, decided by the environment rather
    # than by a race on the pid file. Claude Code marks its Bash with
    # CLAUDECODE=1.
    [[ -n ${CLAUDECODE:-} ]] && exec "$real" "$@"

    # Test seam, as in arm: no display, but the watcher's trace is
    # still worth having.
    if [[ -z ${MAGPIE_GPG_TOUCH_DRY_RUN:-} ]]; then
        _gui_available || exec "$real" "$@"
    fi
    mkdir -p "$OWNERS_DIR" 2>/dev/null || exec "$real" "$@"
    _sweep_owners

    # This wrapper is its own signing context and gets its own watcher,
    # whatever else is running. Reusing a watcher somebody else started
    # was the old behaviour, and it made a terminal signature's window
    # depend on an unrelated session's disarm: when that session's
    # command ended, the window this signature needed went with it.
    # Keyed by this wrapper's own pid: it is the owner, and it is alive
    # for exactly as long as the signature it is wrapping.
    local own log=/dev/null id="p-$$"
    if _debugging; then
        log="$RUNTIME_DIR/watcher.log"
        : >"$log"
    fi
    _set_session_launcher
    # The watcher is told whose it is, and leaves on its own once this
    # wrapper is gone -- however that happened. The kill in the trap
    # below is the fast path; the parent check is the one that cannot be
    # raced or skipped.
    MAGPIE_GPG_TOUCH_WRAPPED_SIGNER=$signer MAGPIE_GPG_TOUCH_PARENT=$$ \
        "${SESSION_LAUNCHER[@]}" "$SELF" _watch >>"$log" 2>&1 &
    own=$!
    _register "$id" "$$" "$own"
    # The wrapped program is handed its own registration, so a signing
    # program that wants to know what is watching it -- and the tests --
    # can read it without guessing at pids.
    export MAGPIE_GPG_TOUCH_REGISTRATION="$OWNERS_DIR/$id"
    # Whatever ends this wrapper -- the program returning, or a signal
    # from git or the terminal -- takes down this wrapper's own watcher
    # and its own registration, and nobody else's: the group for any
    # window it spawned, the pid itself for a watcher too young to have
    # called setsid (a signature that returns in milliseconds ends
    # before it has).
    trap 'kill -- -'"$own"' '"$own"' 2>/dev/null; rm -f "'"$OWNERS_DIR/$id"'" 2>/dev/null; _cleanup_if_idle' EXIT

    "$real" "$@"
    return $?
}

# ------------------------------------------------------------ watcher ---

overlay_pid=""
overlay_dismissed=0

# Raise the window and keep it above the others. Backgrounded: it polls
# for the window to map, which must not hold up the watcher's own loop.
raise_overlay() {
    # EWMH hints and wmctrl are an X11 affair; the Tk window raises itself.
    [[ $PLATFORM == Darwin ]] && return 0

    local i
    for (( i = 0; i < 15; i++ )); do
        if wmctrl -l 2>/dev/null | grep -Fq -- "$TITLE"; then
            wmctrl -F -r "$TITLE" -b add,above 2>/dev/null || true
            wmctrl -F -a "$TITLE" 2>/dev/null || true
            return 0
        fi
        sleep 0.2
    done
}

show_overlay() {
    (( overlay_dismissed )) && return 0
    # Dismissed under another watcher: one touch, one decision. The
    # marker goes when the last owner disarms, so the next signature
    # asks again.
    if [[ -e $DISMISSED_MARKER ]]; then
        overlay_dismissed=1
        return 0
    fi
    if [[ -n $overlay_pid ]]; then
        # Still up: nothing to do. Gone without us killing it: the button
        # was pressed, so respect that and stop re-showing.
        if kill -0 "$overlay_pid" 2>/dev/null; then
            return 0
        fi
        overlay_pid=""
        overlay_dismissed=1
        : >"$DISMISSED_MARKER" 2>/dev/null
        _lease_release
        return 0
    fi
    # Watchers are per owner, so without the lease two of them would
    # draw two windows for the same touch. Losing it is the normal case
    # and means somebody else's window is already up.
    _lease_acquire || return 0
    "$SELF" _overlay &
    overlay_pid=$!
    raise_overlay &
}

hide_overlay() {
    if [[ -z $overlay_pid ]]; then
        _lease_release
        return 0
    fi
    kill "$overlay_pid" 2>/dev/null || true
    overlay_pid=""
    _lease_release
}

_watch() {
    # A trapped signal alone does not end a bash loop — the handler runs
    # and the loop goes on — so disarm's kill has to be turned into an
    # exit here, or the watcher would live out MAX_WAIT after the command
    # it was armed for is long done.
    trap 'hide_overlay' EXIT
    trap 'hide_overlay; exit 0' INT TERM

    # The loop itself is silent, so a log is only worth having as a trace.
    _debugging && set -x

    local i blocked=0 sockets baseline rows

    # Connections to the agent that already exist are somebody else's —
    # a stuck client, a session in another terminal — and are not what
    # this command is waiting for. Only ones that appear from here on
    # count.
    sockets="$(agent_sockets)"
    baseline="$(agent_socket_rows "$sockets")"

    # Live until disarm, or MAX_WAIT if that never comes. A signature
    # ending is not the end of the watch — see the header. Between
    # signatures the window comes down and the block count starts over.
    for (( i = 0; i < MAX_WAIT * 5; i++ )); do
        # Spawned by `wrap`: the wrapper's exit is the end of the watch,
        # whether or not its trap got to send a signal.
        if [[ -n ${MAGPIE_GPG_TOUCH_PARENT:-} ]] && ! kill -0 "$MAGPIE_GPG_TOUCH_PARENT" 2>/dev/null; then
            break
        fi
        # `signing_in_flight` is O(1) under `wrap` -- the watcher's own
        # existence is the answer -- while `agent_socket_rows` shells out to
        # `lsof -U -n`, which enumerates every unix socket on the machine and
        # on a loaded host can take longer than the signature it is meant to
        # observe. Asking the cheap question first keeps the expensive one out
        # of the hot loop entirely on the wrapped path; polling it first cost
        # the overlay the whole window on a busy machine, so it never appeared.
        if { signing_in_flight || { rows="$(agent_socket_rows "$sockets")"; (( rows > baseline )); }; } && ! pinentry_up; then
            blocked=$(( blocked + 1 ))
            (( blocked >= SHOW_DELAY )) && show_overlay
        else
            blocked=0
            hide_overlay
        fi
        sleep "$POLL"
    done
}

# Resolve an interpreter that can actually import gi, printing it on
# stdout. `python3` alone is not a reliable probe: a Homebrew, pyenv or
# asdf python ahead of the system one on PATH has no PyGObject, while a
# distro's python3-gi is bound to /usr/bin/python3. Probing only the
# PATH python on such a machine reports "no PyGObject" while a perfectly
# good gi sits one path away, and the full-screen overlay silently
# degrades to the zenity box.
_gi_python() {
    local py
    for py in python3 /usr/bin/python3; do
        command -v "$py" >/dev/null 2>&1 || continue
        if "$py" -c 'import gi' >/dev/null 2>&1; then
            printf '%s\n' "$py"
            return 0
        fi
    done
    return 1
}

# The same probe for the macOS window's toolkit, and it has to go two
# steps further than importing. A uv, pyenv or Homebrew python commonly
# ships the tkinter module while the Tcl/Tk behind it is missing or
# unfindable, so the import succeeds and the first Tk() call dies with
# "Tcl wasn't installed properly"; only starting a Tk instance tells the
# two apart — withdrawn and destroyed at once, so the probe never puts
# anything on screen. And Tk 8.5, which is what the python in Apple's
# Command Line Tools carries, starts fine and then does not reliably
# show a borderless translucent window at all — or hangs setting it
# up — so the probe also insists on 8.6.
#
# Each candidate is probed and reported by its resolved path. Tcl looks
# for init.tcl relative to the executable it was started as and does not
# follow symlinks, so the `python3` symlink uv or pyenv puts on PATH fails
# the probe while the interpreter it points at passes it.
#
# The usual homes are listed by absolute path as well as `python3` on
# PATH: this runs from a Claude Code hook, whose environment is the
# harness's own and need not carry the shell's PATH — a uv python only
# reachable through `~/.local/bin` on PATH would otherwise be invisible
# here, and the probe would settle on the system python that cannot draw.
_tk_python() {
    local py real
    for py in python3 "$HOME/.local/bin/python3" "$HOME/.pyenv/shims/python3" \
              /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
        real="$(readlink -f "$(command -v "$py" 2>/dev/null)" 2>/dev/null)" || continue
        [[ -n $real ]] || continue
        if "$real" -c 'import sys, tkinter
t = tkinter.Tk(); t.withdraw()
ok = tuple(int(p) for p in t.tk.call("info", "patchlevel").split(".")[:2]) >= (8, 6)
t.destroy(); sys.exit(0 if ok else 1)' >/dev/null 2>&1; then
            printf '%s\n' "$real"
            return 0
        fi
    done
    return 1
}

# The window is exec'd so this pid *is* the window: one kill closes it,
# with no orphaned child left drawing on the screen.
#
# The GTK overlay dims the whole desktop the way the pinentry PIN prompt
# does. zenity is the fallback for a machine without PyGObject — a small
# dialog, but better than a silent block.
_overlay() {
    local py out=/dev/null
    # The window's own complaints — a toolkit that cannot reach the
    # display, say — are the one thing a log is for.
    if _debugging; then
        out="$RUNTIME_DIR/watcher.log"
        # The environment the window is drawn from — a hook's, not the
        # terminal's — is usually the whole question. A safe subset only:
        # no tokens or keys land in a world-readable log.
        {
            printf 'overlay env: '
            env | grep -E '^(PATH|HOME|USER|SHELL|TERM|LANG|TMPDIR|DISPLAY|WAYLAND_DISPLAY|SSH_AUTH_SOCK|XPC_SERVICE_NAME|__CFBundleIdentifier|CLAUDE[A-Z_]*)=' | sort | tr '\n' ' '
            printf '\n'
        } >>"$out" 2>&1
    fi
    if [[ $PLATFORM == Darwin ]]; then
        py="$(_tk_python)" || return 0
        exec "$py" "$OVERLAY_WINDOW_MACOS" >>"$out" 2>&1
    fi
    if py="$(_gi_python)"; then
        exec "$py" "$OVERLAY_WINDOW" >>"$out" 2>&1
    fi
    exec zenity --warning --title="$TITLE" --width=560 --text="$BODY" >>"$out" 2>&1
}

# A PreToolUse hook's exit status is a verdict on the command about to
# run, so arm and disarm end 0 whatever their own plumbing did — a missing
# python or an unwritable runtime dir must never block a commit. The
# probes below are internal and report their real status, which is what
# the callers above and the tests read them for.
# A symlink named `gpg-touch-wrap-<program>` is the argument-free form of
# `wrap <program>` that `gpg.ssh.program` / `gpg.program` need.
_name="${0##*/}"
if [[ $_name == gpg-touch-wrap-?* ]]; then
    wrap "${_name#gpg-touch-wrap-}" "$@"
    exit $?
fi

case "${1:-}" in
    arm)      arm; exit 0 ;;
    wrap)     shift; wrap "$@"; exit $? ;;
    disarm)   disarm; exit 0 ;;
    _watch)   _watch; exit 0 ;;
    _overlay) _overlay ;;
    _gi_python) _gi_python ;;
    _tk_python) _tk_python ;;
    _gui_available) _gui_available ;;
    _signing_in_flight) signing_in_flight ;;
    _agent_sockets) agent_sockets ;;
    _agent_socket_rows) agent_socket_rows "$(printf '%s\n' "${@:2}")" ;;
    _spawn_session) shift; _set_session_launcher; exec "${SESSION_LAUNCHER[@]}" "$@" ;;
    # Test seam: race two of these and exactly one may print "held".
    _lease-probe)
        if _lease_acquire; then
            printf 'held\n'
            sleep "${2:-0}"
            _lease_release
        else
            printf 'taken\n'
        fi
        exit 0
        ;;
    *)
        printf '%s: expected arm|disarm|wrap, got "%s"\n' "${0##*/}" "${1:-}" >&2
        exit 2
        ;;
esac
