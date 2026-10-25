#!/bin/bash -p
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
#
# Session-start hook for the Apache Magpie plugin. Wired by the Claude Code
# plugin (SessionStart) and by the Codex CLI plugin, which uses the same event
# schema. Agent Plugins 1.0 defines no hook component, so an AP1-only client
# does not run this at all — see docs/setup/marketplaces.md.
#
# Also warns, once per session, when the isolated setup is not configured on
# this machine (see `setup_preflight.isolated.session_start`).
#
# Detects when the installed plugin version has changed since the last
# session (i.e. the marketplace updated it) and prompts the user to run
# `/magpie-setup:complete-upgrade`. That skill covers what `setup upgrade`
# used to be suggested for (the snapshot, the agentic overrides, and drift)
# plus the isolated setup.
#
# Deliberately DETECT-AND-PROMPT, not auto-run: a plugin hook cannot invoke
# a slash command, and Magpie never mutates an adopter repo without the
# guided skill's confirmation. The hook makes no network calls and writes
# only its own version marker and, through `setup_preflight`, one cleanup: it
# drops the old `~/.local/share/uv` sandbox write grant from the checkout's
# `.claude/settings.local.json`, the per-machine file the project-root helper
# already maintains, and tells the user (apache/magpie#1785). It runs no git
# command and follows no symlink to do it.
#
# Agents without a session hook (e.g. Gemini CLI) surface the same prompt via
# their extension context file (GEMINI.md) instead.
#
# The session environment comes from settings a project can set, and this hook
# runs outside the sandbox, so none of it may choose what runs: bash is the
# fixed /bin/bash in privileged mode (-p: no BASH_ENV, no imported functions,
# no SHELLOPTS) — the plugin wires the command as `/bin/bash -p <path>` and the
# shebang says the same for a direct exec — and the helpers come from the fixed
# system PATH below.
set -euo pipefail
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH

# The event JSON on stdin: its `cwd` is the project as Claude Code reports it.
payload="$(cat 2>/dev/null || true)"

# Claude Code exports `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA` to hook
# processes; Codex exports `PLUGIN_ROOT` / `PLUGIN_DATA` (the Agent Plugins 1.0
# names) *and* the `CLAUDE_*` pair for compatibility. There is no
# `CODEX_PLUGIN_ROOT`.
root="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-.}}"

# The final fallback is the XDG state dir — never a path inside `$root`, which
# for a `marketplace add` install (or this repo's own local marketplace) is a
# git working tree, and which a plugin update may replace wholesale.
data="${CLAUDE_PLUGIN_DATA:-${PLUGIN_DATA:-${XDG_STATE_HOME:-$HOME/.local/state}/magpie}}"

# Read the plugin version from whichever manifest is present. The root
# `plugin.json` is the Agent Plugins 1.0 manifest; the two client-specific
# manifests carry the same version string (enforced by
# `tools/dev/check-family-plugins.py`), so the order only matters for which
# file is read, not for the value.
manifest=""
for m in "$root/.claude-plugin/plugin.json" "$root/.codex-plugin/plugin.json" "$root/plugin.json"; do
  [ -f "$m" ] && { manifest="$m"; break; }
done
[ -n "$manifest" ] || exit 0

current="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$manifest" | head -n1)"
[ -n "$current" ] || exit 0

marker="$data/magpie-plugin-version"
stored=""
[ -f "$marker" ] && stored="$(cat "$marker" 2>/dev/null || true)"

notice=""
if [ "$current" != "$stored" ]; then
  mkdir -p "$data" 2>/dev/null || true
  printf '%s' "$current" >"$marker" 2>/dev/null || true

  if [ -n "$stored" ]; then
    notice="Apache Magpie updated ($stored -> $current). Run \`/magpie-setup:complete-upgrade\` to check and fix this machine and this project for the new version."
  else
    notice="Apache Magpie plugin $current is active. Run \`/magpie-setup:complete-upgrade\` to check and fix this machine and this project."
  fi
fi

# Once per session, the isolated-setup warning: `setup_preflight` decides
# whether it applies and prints the notice with it, as hook JSON whose
# `systemMessage` the user sees. Without a usable Python the notice goes out
# alone.
#
# The hook runs outside the sandbox, so the interpreter is never `python3`
# from PATH, which project settings can set: only fixed system and Homebrew
# locations. And it runs only an interpreter the sandbox cannot
# rewrite by file permissions, whatever any settings grant: the sandbox runs as
# this user, so a file owned by root and writable by neither group nor others
# is out of its reach. A candidate counts only when
#   - every component of its path, and of each symlink hop on the way to its
#     real binary, is such a root-owned entry;
#   - it is a real installation, judged from its layout before it ever runs:
#     the real binary's prefix holds the standard library of its own version
#     (lib/ or lib64/python3.X for python3.X; every lib*/python3.* when the
#     name carries no version) and no pyvenv.cfg. That rules out launcher stubs such as
#     macOS's /usr/bin/python3, which execs whatever DEVELOPER_DIR names, and
#     virtualenvs, whose base runtime could be anywhere;
#   - that standard library, the shared libraries beside it in <prefix>/lib,
#     and every symlink hop out of them are root-owned the same way
#     (site-packages / dist-packages are exempt: -S never loads them).
# Homebrew is owned by the user who installed it, and a macOS framework build
# (python.org) re-execs a bundle this hook does not vet, so neither qualifies.
# On a machine with no root-owned Python 3.11+ the hook prints its own notice
# and says so when that leaves the ~/.local/share/uv cleanup below undone; the
# isolated-setup warning, which only the pre-flight can decide, is not shown.
# It runs by its real path under `env -i`, so no inherited variable
# (DEVELOPER_DIR, LD_PRELOAD, DYLD_*, PYTHON*) reaches it, and with `-I -S`, so
# no site-packages or working directory (the project being opened, which could
# carry its own `setup_preflight/`) reaches `sys.path`; a one-line bootstrap
# puts the plugin's own source there. `setup_preflight` needs only the stdlib.

# True when <path> itself (not what it links to) is owned by root and, unless
# it is a symlink, writable by neither group nor others. A symlink's own mode
# is meaningless (0777 on Linux): only its directory, checked as the component
# before it, decides whether it can be re-pointed.
root_owned() {
  if [ -L "$1" ]; then
    [ -n "$(find "$1" -maxdepth 0 -user 0 -print 2>/dev/null)" ]
  else
    [ -n "$(find "$1" -maxdepth 0 -user 0 ! -perm -020 ! -perm -002 -print 2>/dev/null)" ]
  fi
}

# True when every component of <path>, and of every symlink hop met while
# resolving it, is root-owned: nothing on the way can be re-pointed.
trusted_path() {
  local rest="$1" cur="" part hops=0 link
  case "$rest" in /*) ;; *) return 1 ;; esac
  root_owned / || return 1
  rest="${rest#/}"
  while [ -n "$rest" ]; do
    part="${rest%%/*}"
    if [ "$part" = "$rest" ]; then rest=""; else rest="${rest#*/}"; fi
    case "$part" in
      ""|.) continue ;;
      ..) cur="${cur%/*}"; continue ;;
    esac
    root_owned "$cur/$part" || return 1
    if [ -L "$cur/$part" ]; then
      hops=$((hops + 1))
      [ "$hops" -le 40 ] || return 1
      link="$(readlink -- "$cur/$part")" || return 1
      case "$link" in /*) cur="" ;; esac
      rest="${link#/}${rest:+/$rest}"
    else
      cur="$cur/$part"
    fi
  done
  return 0
}

# True when everything under <dir> (site-/dist-packages aside) is root-owned,
# and every symlink in it leads only through root-owned entries.
trusted_tree() {
  local dir link
  # From the real directory: find does not descend into a symlinked start.
  dir="$(readlink -f -- "$1" 2>/dev/null)" || return 1
  [ -n "$(find "$dir" \( -name site-packages -o -name dist-packages \) -prune -o \
          \( ! -user 0 -o \( ! -type l \( -perm -020 -o -perm -002 \) \) \) -print 2>/dev/null | head -n1)" ] && return 1
  # A symlink to a directory would bring in contents this scan never saw.
  while IFS= read -r -d '' link; do
    [ -d "$link" ] && return 1
    trusted_path "$link" || return 1
  done < <(find "$dir" \( -name site-packages -o -name dist-packages \) -prune -o -type l -print0 2>/dev/null)
  return 0
}

python=""
for candidate in /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
  [ -x "$candidate" ] || continue
  trusted_path "$candidate" || continue
  canonical="$(readlink -f -- "$candidate" 2>/dev/null)" || continue
  [ -n "$canonical" ] && [ -x "$canonical" ] || continue
  # A macOS framework build re-execs Resources/Python.app and loads the
  # framework's own library, outside what is checked below: not trusted.
  case "$canonical" in */*.framework/*) continue ;; esac
  prefix="$(dirname -- "$(dirname -- "$canonical")")"
  [ -e "$prefix/pyvenv.cfg" ] || [ -e "$(dirname -- "$canonical")/pyvenv.cfg" ] && continue
  name="${canonical##*/}"
  # lib64 too: Fedora / RHEL keep the standard library in <prefix>/lib64.
  case "$name" in
    python3.[0-9]*) stdlibs=("$prefix/lib/$name" "$prefix/lib64/$name") ;;
    *) stdlibs=("$prefix"/lib/python3.* "$prefix"/lib64/python3.*) ;;
  esac
  ok=1 found=0
  for stdlib in "${stdlibs[@]}"; do
    [ -f "$stdlib/os.py" ] && found=1
    [ -d "$stdlib" ] || continue
    trusted_path "$stdlib" && trusted_tree "$stdlib" || { ok=0; break; }
  done
  [ "$ok" = 1 ] && [ "$found" = 1 ] || continue
  # The shared libraries beside the standard library (libpython and friends).
  while IFS= read -r -d '' lib; do
    trusted_path "$lib" || { ok=0; break; }
  done < <(find "$prefix/lib" "$prefix/lib64" -maxdepth 1 ! -type d -print0 2>/dev/null)
  [ "$ok" = 1 ] || continue
  env -i PATH=/usr/bin:/bin "$canonical" -I -S -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1 || continue
  python="$canonical"
  break
done

# Where the session's settings live, for the ~/.local/share/uv check below:
# CLAUDE_PROJECT_DIR and $HOME come from the environment, so the payload's cwd,
# the working directory, the checkout each sits in (and, for a linked
# worktree, its main checkout, whose settings Claude Code also reads) and the
# account database's home (`~user`) count as well.
project="${CLAUDE_PROJECT_DIR:-$PWD}"
projects=("$project" "$PWD")
if command -v jq >/dev/null 2>&1; then
  payload_cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
  [ -n "$payload_cwd" ] && projects+=("$payload_cwd")
fi
# Absolute, physical paths only (a relative CLAUDE_PROJECT_DIR would never
# reach / below); one that does not resolve is dropped.
resolved=()
for p in ${projects[@]+"${projects[@]}"}; do
  p="$(cd "$p" 2>/dev/null && pwd -P)" && resolved+=("$p")
done
projects=(${resolved[@]+"${resolved[@]}"})
for p in ${projects[@]+"${projects[@]}"}; do
  d="$p"
  while [ -n "$d" ] && [ "$d" != / ]; do
    if [ -e "$d/.git" ]; then projects+=("$d"); break; fi
    next="$(dirname -- "$d")"
    [ "$next" = "$d" ] && break
    d="$next"
  done
done
for p in ${projects[@]+"${projects[@]}"}; do
  [ -f "$p/.git" ] || continue
  gitdir="$(sed -n 's/^gitdir:[[:space:]]*//p' "$p/.git" 2>/dev/null | head -n1)"
  [ -n "$gitdir" ] || continue
  case "$gitdir" in /*) ;; *) gitdir="$p/$gitdir" ;; esac
  common="$gitdir"
  if [ -r "$gitdir/commondir" ]; then
    c="$(head -n1 "$gitdir/commondir")"
    case "$c" in /*) common="$c" ;; *) common="$gitdir/$c" ;; esac
  fi
  main="$(cd "$common/.." 2>/dev/null && pwd -P)" || continue
  projects+=("$main")
done
homes=("$HOME")
user="$(id -un 2>/dev/null || true)"
if [[ $user =~ ^[A-Za-z0-9._][A-Za-z0-9._-]*$ ]]; then
  eval "account_home=~$user"
  [[ $account_home == /* && $account_home != "$HOME" ]] && homes+=("$account_home")
fi

# Sandbox write grants as `<settings file><TAB><absolute directory>` lines; "/"
# for a grant that cannot be pinned down (a bare Edit rule, a `..`, a file jq
# cannot read). Used only to report, never to decide what runs.
write_grants() {
  local files=() bases=() i settings base entry h p form slash=/ dslash=// dotdir=/./
  for h in "${homes[@]}"; do
    files+=("$h/.claude/settings.json" "$h/.claude/settings.local.json"); bases+=("$h/.claude" "$h/.claude")
  done
  for p in ${projects[@]+"${projects[@]}"}; do
    files+=("$p/.claude/settings.json" "$p/.claude/settings.local.json"); bases+=("$p" "$p")
  done
  files+=("/Library/Application Support/ClaudeCode/managed-settings.json" "/etc/claude-code/managed-settings.json")
  bases+=("/Library/Application Support/ClaudeCode" "/etc/claude-code")
  for (( i = 0; i < ${#files[@]}; i++ )); do
    settings="${files[i]}" base="${bases[i]}"
    [ -r "$settings" ] || continue
    command -v jq >/dev/null 2>&1 || { printf '%s\t/\t//\n' "$settings"; continue; }
    jq -r --arg file "$settings" --arg base "$base" '((.sandbox.filesystem.allowWrite // [])[], (.permissions.additionalDirectories // [])[],
           ((.permissions.allow // [])[] | strings
            | if test("^(Edit|Write|MultiEdit|NotebookEdit)$") then "//"
              else (capture("^(Edit|Write|MultiEdit|NotebookEdit)\\((?<p>.*)\\)$").p // empty) end))
           | strings | (if test("[\t\n]") then "//" else . end) | "\($file)\t\($base)\t\(.)"' "$settings" 2>/dev/null \
      || printf '%s\t/\t//\n' "$settings"
  done | while IFS=$'\t' read -r settings base entry; do
    [ -n "$entry" ] || continue
    # A relative or single-slash entry counts against the settings file's own
    # directory and every place the project could be.
    forms=()
    case "$entry" in
      */../*|*/..|../*|..) forms=("/") ;;
      //*) forms=("/${entry#//}") ;;
      "~") forms=("${homes[@]}") ;;
      "~/"*) for h in "${homes[@]}"; do forms+=("$h/${entry#\~/}"); done ;;
      /*) forms=("$entry" "$base$entry"); for p in ${projects[@]+"${projects[@]}"}; do forms+=("$p$entry"); done ;;
      *) forms=("$base/${entry#./}"); for p in ${projects[@]+"${projects[@]}"}; do forms+=("$p/${entry#./}"); done ;;
    esac
    for form in "${forms[@]}"; do
      case "$form" in *[\*\?\[]*) form="${form%%[\*\?\[]*}"; form="${form%/*}" ;; esac
      # `a//b`, `a/./b` and a trailing `/.` name the same directory as `a/b`.
      # (Patterns in variables: bash 3.2 keeps a backslash in the replacement.)
      while [[ $form == *//* ]]; do form="${form//$dslash/$slash}"; done
      while [[ $form == */./* ]]; do form="${form//$dotdir/$slash}"; done
      form="${form%/.}"
      form="${form%/}"
      printf '%s\t%s\n' "$settings" "${form:-/}"
    done
  done
}

output="$notice"
preflight_ran=0
if [ -n "$python" ]; then
  bootstrap='import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module("setup_preflight.isolated", run_name="__main__", alter_sys=True)'
  if ran="$(env -i PATH=/usr/bin:/bin HOME="$HOME" LANG=C.UTF-8 "$python" -I -S -c "$bootstrap" "$root/skills/setup" session-start \
      --project-root "$project" --notice "$notice" 2>/dev/null)"; then
    output="$ran"
    preflight_ran=1
  fi
fi

# The pre-flight also drops the old ~/.local/share/uv sandbox write grant
# (apache/magpie#1785). With no trusted Python that cleanup cannot run, and
# the grant lets a sandboxed command replace interpreters that run outside the
# sandbox, so say so rather than stay silent. A read-only text match over the
# files the cleanup covers: it errs towards warning, and edits nothing.
json_str() {
  local s="$1"
  s="${s//\\/\\\\}" s="${s//\"/\\\"}" s="${s//$'\n'/\\n}" s="${s//$'\t'/\\t}" s="${s//$'\r'/\\r}"
  # Any other control character has no business in a path or this message.
  s="$(printf '%s' "$s" | tr -d '\000-\010\013\014\016-\037')"
  printf '"%s"' "$s"
}
if [ "$preflight_ran" = 0 ]; then
  # Which settings files grant writes over ~/.local/share/uv (it, an ancestor,
  # or something inside it), from the normalised write grants alone; a file
  # that could not be read leaves the answer unknown rather than guessed.
  stale_files=() unknown_files=()
  while IFS=$'\t' read -r file grant; do
    [ -n "$grant" ] || continue
    hit=0
    if [ "$grant" = / ]; then
      case " ${unknown_files[*]-} " in *" $file "*) ;; *) unknown_files+=("$file") ;; esac
      continue
    fi
    for h in "${homes[@]}"; do
      uv="$h/.local/share/uv"
      case "$uv/" in "$grant"/*) hit=1 ;; esac
      case "$grant/" in "$uv"/*) hit=1 ;; esac
    done
    [ "$hit" = 1 ] || continue
    case " ${stale_files[*]-} " in *" $file "*) ;; *) stale_files+=("$file") ;; esac
  done < <(write_grants)
  stale=""
  if [ "${#stale_files[@]}" -gt 0 ]; then
    stale="Apache Magpie: ~/.local/share/uv holds the interpreters and tools uv runs outside the sandbox, so the sandbox must not write there (apache/magpie#1785). This session had no trusted Python to remove that grant, and these settings still make it: ${stale_files[*]}. Remove it by hand, or run /magpie-setup verify."
  elif [ "${#unknown_files[@]}" -gt 0 ]; then
    stale="Apache Magpie: this session had no trusted Python and could not read ${unknown_files[*]}, so it could not check for the ~/.local/share/uv sandbox write grant (apache/magpie#1785). Run /magpie-setup verify."
  fi
  if [ -n "$stale" ]; then
    context="$stale"
    [ -n "$notice" ] && context="$notice"$'\n\n'"$stale"
    output="{\"systemMessage\": $(json_str "$stale"), \"hookSpecificOutput\": {\"hookEventName\": \"SessionStart\", \"additionalContext\": $(json_str "$context")}}"
  fi
fi

# stdout, not stderr: for a `SessionStart` hook exiting 0, Claude Code adds
# stdout to the session context (stderr on a zero exit only reaches the debug
# log). Writing the prompt to stderr would deliver it to nobody — and because
# the marker is written first, the next session would see no change and stay
# silent too.
if [ -n "$output" ]; then
  printf '%s\n' "$output"
fi

exit 0
