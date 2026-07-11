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
# claude-term-bg.sh — tint the terminal background while Claude Code is
# waiting on YOU, and keep it calm the rest of the time.
#
# This is a quality-of-life helper, NOT a security control: it makes the
# "Claude is BLOCKED ON A DECISION I have to make" state impossible to miss in
# a window you've tabbed away from — while deliberately NOT tinting when Claude
# merely finished a task and is idle until you start the next thing. Those two
# look identical at the `Stop` event, so the script distinguishes them with
# three genuine "Claude is asking you for something" signals (two exact, one
# heuristic) and stays calm for everything else. Wire it into six hooks
# (user-scope):
#
#   "Stop"              -> claude-term-bg.sh stop    (turn ended: TINT only if the final
#                                                     assistant message is genuinely a
#                                                     question/request; stay calm if it reads
#                                                     as a completion — heuristic, see below)
#   "PreToolUse"        -> claude-term-bg.sh wait    (matcher: AskUserQuestion — a structured
#                                                     question was posed; EXACT signal)
#   "PostToolUse"       -> claude-term-bg.sh reset   (matcher: * — a tool finished: calm while
#                                                     working, and clears the tint the instant
#                                                     you approve a permission prompt or answer
#                                                     an AskUserQuestion)
#   "Notification"      -> claude-term-bg.sh notify  (TINT for permission prompts only — EXACT;
#                                                     the plain 60s idle ping is a NO-OP so it
#                                                     can't wipe a pending question's tint)
#   "UserPromptSubmit"  -> claude-term-bg.sh reset   (you replied — back to calm)
#   "SessionStart"      -> claude-term-bg.sh reset   (fresh session — clear any stale tint)
#
# Two design notes that make the distinction hold:
#
#   * Why PostToolUse (not PreToolUse) clears the "you just acted" tint:
#     PreToolUse fires BEFORE the permission prompt is shown, so it cannot clear
#     a tint the prompt itself sets. PostToolUse fires AFTER the tool completes
#     — the moment your approval/selection lets work resume — so it is the hook
#     that returns the screen to calm once you have acted. (This is also why the
#     general PreToolUse reset is gone: PreToolUse is now reserved for the
#     AskUserQuestion->wait tint, and PostToolUse alone keeps work calm.)
#   * Why the idle ping is a no-op (not a reset): the `Notification` hook also
#     fires the plain "waiting for your input" ping ~60s after a turn ends. If
#     that reset the background, a turn that ended on a genuine question (tinted
#     by `stop`) would silently go calm after a minute. Leaving it untouched
#     preserves whatever state `stop`/`notify` decided.
#
# The `stop` heuristic (the only non-exact signal): it reads the LAST assistant
# text message from the session transcript (path arrives on stdin in the Stop
# hook payload) and tints when that message ends as a question ("...?") or with
# a strong trailing request ("want me to", "would you like", "should I", "OK
# to", "your call", ...). A statement-shaped completion ("Done.", "All set.")
# stays calm. Needs python3/python on PATH; if absent, `stop` defaults to calm
# (only the two EXACT signals tint).
#
# Colours are overridable via the environment (e.g. inline in the hook command):
#   CLAUDE_WAIT_BG    background while waiting   (default: #2a1a3a, a muted indigo)
#   CLAUDE_RESET_BG   calm/idle background       (default: unset -> reset to profile default;
#                                                 set e.g. to #000000 for a deterministic black)
#
# Mechanism notes (the two things that make this actually work):
#
#   1. No controlling terminal. Claude Code spawns hook commands detached
#      from the tty, so /dev/tty does not resolve to your terminal window.
#      find_tty_dev() walks up the process tree to the Claude process's pty
#      (e.g. /dev/ttys003) and writes the escape straight to that device.
#
#   2. Set vs. reset asymmetry. iTerm2 honours OSC 11 (set background) but
#      does NOT reliably honour OSC 111 (reset-to-default) through Claude's
#      fullscreen TUI, so a naive reset leaves the tint stuck. The only
#      deterministic reset is an explicit colour via CLAUDE_RESET_BG (OSC 11,
#      the path we know works); without it we emit BOTH OSC 111 and iTerm2's
#      proprietary SetColors=bg=default and let whichever the terminal
#      understands win. VTE terminals (terminator, gnome-terminal) DO honour
#      OSC 111, so on Linux the default reset works without CLAUDE_RESET_BG; the
#      iTerm2-proprietary escape they don't recognise is harmlessly ignored.
#
# Tested on iTerm2 + macOS and terminator (VTE) + Linux. The only OS-specific
# part is locating the pty device: find_tty_dev() matches both macOS "ttysNNN"
# and Linux "pts/N" names. Terminals that ignore OSC 11 entirely simply see no
# change (fail-soft). For a guaranteed reset anywhere, set CLAUDE_RESET_BG.
set -u
WAIT_BG="${CLAUDE_WAIT_BG:-#2a1a3a}"
RESET_BG="${CLAUDE_RESET_BG:-}"
action="${1:-reset}"

find_tty_dev() {
  local pid=${PPID:-$$} t i
  for i in 1 2 3 4 5 6 7 8; do
    [ -z "$pid" ] || [ "$pid" = "0" ] || [ "$pid" = "1" ] && break
    t=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    # macOS reports ptys as "ttys003"; Linux (terminator/VTE, xterm, …) reports
    # them as "pts/0". Both prepend /dev to give a writable device path.
    case "$t" in
      ttys*|tty[0-9]*|pts/[0-9]*) echo "/dev/$t"; return 0 ;;
    esac
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
  done
  return 1
}

tty_dev=$(find_tty_dev || true)
[ -n "${tty_dev:-}" ] && [ -w "$tty_dev" ] || exit 0

set_wait() { printf '\033]11;%s\007' "$WAIT_BG" > "$tty_dev"; }
set_reset() {
  if [ -n "$RESET_BG" ]; then
    printf '\033]11;%s\007' "$RESET_BG" > "$tty_dev"
  else
    printf '\033]111\007' > "$tty_dev"                       # xterm: reset bg
    printf '\033]1337;SetColors=bg=default\007' > "$tty_dev" # iTerm2 proprietary
  fi
}

# Classify the final assistant message of a transcript as a genuine
# question/request ("wait") vs a completion ("calm"). Prints one word.
# Heuristic, anchored on the trailing sentence so a long completion that
# merely *mentions* a question earlier still reads as calm.
classify_last_message() {
  local transcript="$1" py
  py=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)
  [ -n "$py" ] && [ -f "$transcript" ] || { echo calm; return; }
  "$py" - "$transcript" <<'PY' 2>/dev/null || echo calm
import json, re, sys
last = ""
try:
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            role = msg.get("role") or (obj.get("type") if obj.get("type") == "assistant" else None)
            if role != "assistant":
                continue
            content = msg.get("content", obj.get("content"))
            txt = ""
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        txt += b.get("text", "")
            elif isinstance(content, str):
                txt = content
            if txt.strip():
                last = txt
except Exception:
    print("calm"); sys.exit(0)

t = re.sub(r'[`*_>#\s]+$', '', last.strip())   # drop trailing markdown/space
if not t:
    print("calm"); sys.exit(0)
tail = t.splitlines()[-1].strip()
blob = t.lower()[-240:]
ask = tail.endswith("?") or any(p in blob for p in (
    "want me to", "would you like", "should i ", "shall i ", "do you want",
    "ok to ", "okay to ", "your call", "which would you", "let me know which",
    "let me know if you'd like", "want that too", "proceed with",
))
print("wait" if ask else "calm")
PY
}

case "$action" in
  wait|set)  set_wait ;;
  reset|off) set_reset ;;
  stop)
    # Turn ended. Tint ONLY if the final assistant message is genuinely a
    # question/request; a completion-shaped message stays calm. This is what
    # separates "Claude is asking me something" from "Claude finished — I'll
    # start the next thing whenever." Payload (with transcript_path) on stdin.
    payload=$(cat 2>/dev/null)
    transcript=$(printf '%s' "$payload" \
      | sed -n 's/.*"transcript_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
      | head -n1)
    case "$transcript" in "~/"*) transcript="$HOME/${transcript#\~/}" ;; esac
    case "$(classify_last_message "$transcript")" in
      wait) set_wait ;;
      *)    set_reset ;;
    esac
    ;;
  notify)
    # Notification fires for permission prompts AND the plain 60s idle ping.
    # Tint for a genuine permission request; leave the background UNTOUCHED on
    # the idle ping so it can't wipe a question-tint set by `stop`.
    msg=$(cat 2>/dev/null)
    case "$msg" in
      *permission*|*approve*|*"needs your"*) set_wait ;;
      *)                                     : ;;   # idle ping / other — no-op
    esac
    ;;
esac
exit 0
