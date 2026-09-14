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
# This is the other half of the hardware-key rule in AGENTS.md
# ("Commit and PR conventions"). That rule has the agent probe the PIN
# cache and warn *before* committing; gpg-agent's `keyinfo` reports the
# PIN cache only, so a key with a warm PIN and a cold touch still blocks
# with no prompt at all. This covers that case from the other side, at
# the moment gpg is actually waiting.
#
#   arm     PreToolUse  — a git command that might sign is about to run;
#                         start a watcher that shows the window if and
#                         when signing actually blocks.
#   disarm  PostToolUse — the command is done; tear the watcher down.
#
# The watcher, not the hook, decides whether anything is shown:
#
#   * `pgrep -x gpg` — a signing gpg is in flight. Matching on the exact
#     process name matters: `pgrep -f` would match the hook's own command
#     line and report a signature that is not happening.
#   * `pgrep -x 'pinentry.*'` — pinentry is up, so the PIN is being asked
#     for. The window stays hidden then; two dialogs competing for focus
#     would make the PIN impossible to type.
#   * SHOW_DELAY — a signature with a still-cached touch finishes in well
#     under a second. Nothing is shown until gpg has blocked for longer
#     than that, so ordinary commits stay silent.
#
# So arming is cheap and deliberately over-broad: it costs one background
# process that exits on its own when no signature materialises.
#
# Dismissing the window with its button is honoured — it is a prompt, not
# a trap, and gpg keeps waiting either way. It is not re-shown for the
# same signature.

set -uo pipefail

SELF="$(readlink -f "${BASH_SOURCE[0]}")"
readonly SELF
readonly OVERLAY_WINDOW="${SELF%/*}/gpg-touch-overlay-window.py"

readonly TITLE="Touch your security key"
readonly BODY="<b>gpg is waiting for a touch to sign.</b>

Touch the key's contact now — the commit is blocked until you do.
This window closes by itself once the touch registers."

readonly SHOW_DELAY=8     # polls a signature must block before showing (0.2s each)
readonly APPEAR_GRACE=45  # seconds to wait for gpg to appear at all
readonly MAX_WAIT=600     # seconds the watcher may live, whatever happens
readonly POLL=0.2

RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp}/magpie-gpg-touch"
readonly WATCHER_PID_FILE="$RUNTIME_DIR/watcher.pid"

# A signing gpg is running. Exact-name match only — see the header.
signing_in_flight() { pgrep -x 'gpg|gpg2' >/dev/null 2>&1; }

# pinentry is asking for the PIN and owns the screen.
pinentry_up() { pgrep -x 'pinentry.*' >/dev/null 2>&1; }

# ---------------------------------------------------------------- arm ---

# Subcommands that can produce a signature under this config. Broad on
# purpose: a false positive costs one short-lived watcher, a false
# negative costs a silent block with no window.
readonly SIGNING_SUBCOMMANDS='commit|tag|merge|rebase|revert|cherry-pick|am|push'

arm() {
    if [[ -z ${MAGPIE_GPG_TOUCH_DRY_RUN:-} ]]; then
        [[ -n ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]] || return 0
        command -v zenity >/dev/null 2>&1 || python3 -c 'import gi' >/dev/null 2>&1 || return 0
    fi

    local payload command_text
    payload="$(cat)"
    command_text="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null)"
    [[ -n $command_text ]] || return 0

    printf '%s' "$command_text" |
        grep -Eq "(^|[;&|(]|[[:space:]])git([[:space:]]+-[A-Za-z-]+([[:space:]]+[^[:space:]]+)?)*[[:space:]]+($SIGNING_SUBCOMMANDS)([[:space:]]|$)" ||
        return 0

    # Test seam: report the decision instead of spawning a watcher, so
    # the command matcher can be exercised without an X display.
    if [[ -n ${MAGPIE_GPG_TOUCH_DRY_RUN:-} ]]; then
        printf 'arm\n'
        return 0
    fi

    mkdir -p "$RUNTIME_DIR" 2>/dev/null || return 0

    # One watcher covers whatever is in flight; a live one needs no second.
    local old
    old="$(cat "$WATCHER_PID_FILE" 2>/dev/null || true)"
    if [[ -n ${old:-} ]] && kill -0 "$old" 2>/dev/null; then
        return 0
    fi

    # setsid: the watcher leads its own process group, so disarm can take
    # down the window it spawned with a single group kill.
    local log=/dev/null
    [[ -n ${MAGPIE_GPG_TOUCH_DEBUG:-} ]] && log="$RUNTIME_DIR/watcher.log"
    setsid "$SELF" _watch >"$log" 2>&1 &
    printf '%s\n' "$!" >"$WATCHER_PID_FILE"
}

# ------------------------------------------------------------- disarm ---

disarm() {
    local pid
    pid="$(cat "$WATCHER_PID_FILE" 2>/dev/null || true)"
    [[ -n ${pid:-} ]] || return 0
    kill -- -"$pid" 2>/dev/null || true
    rm -f "$WATCHER_PID_FILE"
}

# ------------------------------------------------------------ watcher ---

overlay_pid=""
overlay_dismissed=0

# Raise the window and keep it above the others. Backgrounded: it polls
# for the window to map, which must not hold up the watcher's own loop.
raise_overlay() {
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
    if [[ -n $overlay_pid ]]; then
        # Still up: nothing to do. Gone without us killing it: the button
        # was pressed, so respect that and stop re-showing.
        if kill -0 "$overlay_pid" 2>/dev/null; then
            return 0
        fi
        overlay_pid=""
        overlay_dismissed=1
        return 0
    fi
    "$SELF" _overlay &
    overlay_pid=$!
    raise_overlay &
}

hide_overlay() {
    [[ -n $overlay_pid ]] || return 0
    kill "$overlay_pid" 2>/dev/null || true
    overlay_pid=""
}

_watch() {
    trap 'hide_overlay' EXIT INT TERM

    local i blocked=0

    # Nothing signs instantly; git may run hooks first. Wait for gpg to
    # show up, and stop caring if it never does.
    for (( i = 0; i < APPEAR_GRACE * 5; i++ )); do
        signing_in_flight && break
        sleep "$POLL"
    done
    signing_in_flight || return 0

    for (( i = 0; i < MAX_WAIT * 5; i++ )); do
        signing_in_flight || break
        if pinentry_up; then
            blocked=0
            hide_overlay
        else
            blocked=$(( blocked + 1 ))
            (( blocked >= SHOW_DELAY )) && show_overlay
        fi
        sleep "$POLL"
    done
}

# The window is exec'd so this pid *is* the window: one kill closes it,
# with no orphaned child left drawing on the screen.
#
# The GTK overlay dims the whole desktop the way the pinentry PIN prompt
# does. zenity is the fallback for a machine without PyGObject — a small
# dialog, but better than a silent block.
_overlay() {
    if python3 -c 'import gi' >/dev/null 2>&1; then
        exec python3 "$OVERLAY_WINDOW" >/dev/null 2>&1
    fi
    exec zenity --warning --title="$TITLE" --width=560 --text="$BODY" >/dev/null 2>&1
}

case "${1:-}" in
    arm)      arm ;;
    disarm)   disarm ;;
    _watch)   _watch ;;
    _overlay) _overlay ;;
    *)
        printf '%s: expected arm|disarm, got "%s"\n' "${0##*/}" "${1:-}" >&2
        exit 2
        ;;
esac
exit 0
