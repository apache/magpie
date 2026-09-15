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
# sandbox-status-line.sh — Claude Code statusLine helper.
#
# Renders one line for the terminal footer that always shows whether
# Claude Code's filesystem/network sandbox is active in the current
# session, so a session that is *not* sandboxed cannot drift
# unnoticed for hours. Alongside the sandbox tag (green `[sandbox]` /
# yellow `[sandbox-auto]` / bold-red `[NO SANDBOX]`) it carries what
# tells several sessions apart across worktrees and repos — which
# project, which branch, which PR:
#
#   [sandbox]  <folder>   | <branch><dirty><ahead/behind>
#                         | #<PR> <title>
#                         | <model>
#
# Claude-Code-only, unlike the harness-agnostic helpers alongside it:
# it is wired through Claude Code's `statusLine` setting, is fed Claude
# Code's statusLine payload on stdin, and reads Claude Code's
# `sandbox.enabled` settings schema. No other harness the framework
# supports has a status-line hook of that shape — Codex, Gemini,
# OpenCode and Kiro carry their sandbox posture in their own config and
# surface it, where they surface it at all, through their own UI. A
# harness that grows one gets its own helper; see
# `docs/adapters/add-a-harness.md`.
#
# - Folder name is colour-coded by a stable hash of its basename, so
#   each repo / worktree keeps the same colour across sessions.
# - Inside a linked git worktree renders `<source>/<worktree>` with
#   each segment hash-coloured independently — the source colour stays
#   stable across worktrees. Covers every layout: worktrunk's sibling
#   `<repo>.<branch>/` directories (the repeated `<repo>.` prefix is
#   stripped from the second segment), Claude Code's own
#   `<source>/.claude/worktrees/<name>`, and plain `git worktree add`.
# - Git segment is local-only (no network): branch, dirty marker
#   (`-uno` skips untracked-file scan), ahead/behind vs upstream from
#   cached refs.
# - PR segment runs `gh pr view` once per branch with a 5-min success
#   / 60-s miss cache under `${XDG_CACHE_HOME:-~/.cache}/claude-statusline/`.
#   Silent when `gh` is missing, unauthenticated, or the branch has no
#   PR. Wrapped in a portable `timeout` (with a `perl -e 'alarm'`
#   fallback for systems where neither `timeout` nor `gtimeout` is
#   installed) so a hung gh call cannot stall every status-line render.
# - Yellow `[sandbox-auto]` lights up when the active settings set
#   `.sandbox.autoAllowBashIfSandboxed: true` — that flag widens blast
#   radius (bash inside the sandbox skips the per-call allow prompt)
#   and is worth surfacing distinctly from plain `[sandbox]`.
#
# Sandbox tag reads `.sandbox.enabled` from the active settings,
# walked in Claude Code's standard precedence order (most-specific
# first):
#   1. <cwd>/.claude/settings.local.json
#   2. <cwd>/.claude/settings.json
#   3. <worktree-root>/.claude/settings.local.json
#   4. <worktree-root>/.claude/settings.json
#   5. <main-checkout>/.claude/settings.local.json
#   6. <main-checkout>/.claude/settings.json
#   7. ~/.claude/settings.local.json
#   8. ~/.claude/settings.json
# First file with `.sandbox.enabled` set (true *or* false) wins. The
# `/sandbox` slash-command toggle persists to project-scope
# `settings.local.json`, so reading that file is what makes the prefix
# update after an in-session toggle. CLI flags like
# `--bypass-permissions` are still not visible here — pair with
# `sandbox-bypass-warn.sh` for per-call signal.
#
# Steps 3-6 are what make the tag correct inside a linked git
# worktree. Claude Code scopes the project of a linked worktree to
# the *main* checkout — that is where `/sandbox` writes the toggle and
# where `.claude/.cc-writes` lands — while `<cwd>` is the worktree's
# own directory, whose `.claude/settings.local.json` typically carries
# only the per-worktree filesystem allowlist and no `enabled` key.
# Walking `<cwd>` alone there falls straight through to user scope, so
# a session the operator switched *out* of the sandbox still renders
# green `[sandbox]` — precisely the silent drift this line exists to
# prevent. Layout-agnostic: worktrunk's `<repo>.<branch>/` siblings,
# `.claude/worktrees/<name>`, and plain `git worktree add` all resolve
# through the same `--git-dir` / `--git-common-dir` comparison.
#
# Wiring (user-scope):
#
#   {
#     "statusLine": {
#       "type": "command",
#       "command": "~/.claude/scripts/sandbox-status-line.sh"
#     }
#   }
#
# See `docs/setup/secure-agent-setup.md` → "Sandbox-state status line" for
# the install steps. This is the only status line Magpie ships and the
# one the setup skill installs. A minimal sandbox-tag-only variant
# existed alongside it until 0.2.0 and was dropped: every segment here
# degrades to silence on its own when its input is missing, so the
# small version was this script with less to say and a second file to
# keep correct.

set -u

input=$(cat)

# ---------------------------------------------------------------------------
# 0. Parse stdin once — pull out cwd and model display name.
# ---------------------------------------------------------------------------
parsed=$(printf '%s' "$input" | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(); sys.exit(0)
cwd = d.get("cwd") or (d.get("workspace") or {}).get("current_dir") or ""
m = d.get("model") or {}
model = m.get("display_name") or m.get("id") or ""
print(f"{cwd}\t{model}")' 2>/dev/null)
cwd=${parsed%%$'\t'*}
model=${parsed#*$'\t'}
[ -z "$cwd" ] && cwd="$PWD"

# ---------------------------------------------------------------------------
# 1. Worktree roots
#    `wt_root` is the working tree containing <cwd>; `main_root` is the main
#    checkout, set only when <cwd> sits in a *linked* worktree. Both feed the
#    folder segment below and the settings walk in section 5.
#
#    `--git-dir` != `--git-common-dir` is the exact test for "linked
#    worktree" and is layout-agnostic — it holds for worktrunk's sibling
#    `<repo>.<branch>/` directories, for Claude Code's own
#    `<source>/.claude/worktrees/<name>`, and for a plain `git worktree add`
#    anywhere else. Matching on the directory name instead would only ever
#    know the layouts someone thought to enumerate.
# ---------------------------------------------------------------------------
wt_root=""
main_root=""
if wt_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null); then
    gdir=$(git -C "$cwd" rev-parse --git-dir 2>/dev/null || true)
    gcommon=$(git -C "$cwd" rev-parse --git-common-dir 2>/dev/null || true)
    # Both come back relative to <cwd> when <cwd> *is* the working-tree
    # root and absolute from a subdirectory below it, so resolve each to
    # a real path before comparing — a raw string compare reports every
    # subdirectory of a plain checkout as a linked worktree.
    [ -n "$gdir" ] && [[ "$gdir" != /* ]] && gdir="$cwd/$gdir"
    [ -n "$gcommon" ] && [[ "$gcommon" != /* ]] && gcommon="$cwd/$gcommon"
    gdir=$(cd "$gdir" 2>/dev/null && pwd -P) || gdir=""
    gcommon=$(cd "$gcommon" 2>/dev/null && pwd -P) || gcommon=""
    if [ -n "$gcommon" ] && [ "$gdir" != "$gcommon" ]; then
        # <main>/.git -> <main>.
        main_root=$(cd "$gcommon/.." 2>/dev/null && pwd -P) || main_root=""
        [ "$main_root" = "$wt_root" ] && main_root=""
    fi
else
    wt_root=""
fi

# ---------------------------------------------------------------------------
# 2. Folder (colour-coded by hash)
#    In a linked worktree we render "<source>/<worktree>" with each segment
#    hash-coloured independently — the source colour stays stable across all
#    worktrees of the same repo.
# ---------------------------------------------------------------------------
folder=$(basename "$cwd")
worktree_name=""
if [ -n "$main_root" ]; then
    worktree_name=$(basename "$wt_root")
    folder=$(basename "$main_root")
    # worktrunk names worktrees "<repo>.<branch>" as siblings of the main
    # checkout, so the repo name would otherwise appear twice. Strip the
    # repeated prefix and its separator; layouts that do not repeat it
    # (".claude/worktrees/<name>") fall through untouched.
    case "$worktree_name" in
        "$folder"[._-]*) worktree_name=${worktree_name#"$folder"?} ;;
    esac
fi

palette=(33 39 45 51 75 81 87 105 111 117 123 141 147 153 159 165 171 177 183 189 195 201 207 213 219 220 226 214 208 202 196 199 203 209 215 221 227 154 118 82 46 47 48 49 50 84 120 156 190 228)
n=${#palette[@]}
idx=$(printf '%s' "$folder" | cksum | awk '{print $1}')
color=${palette[$((idx % n))]}
folder_out=$(printf '\033[38;5;%dm%s\033[0m' "$color" "$folder")

if [ -n "$worktree_name" ]; then
    wt_idx=$(printf '%s' "$worktree_name" | cksum | awk '{print $1}')
    wt_color=${palette[$((wt_idx % n))]}
    wt_out=$(printf '\033[38;5;%dm%s\033[0m' "$wt_color" "$worktree_name")
    folder_out="$folder_out/$wt_out"
fi

# ---------------------------------------------------------------------------
# 3. Git status
# ---------------------------------------------------------------------------
git_info=""
branch=""

if git_dir=$(git -C "$cwd" rev-parse --git-dir 2>/dev/null); then
    if [[ "$git_dir" != /* ]]; then
        git_dir="$cwd/$git_dir"
    fi
    head_file="$git_dir/HEAD"
    if [ -f "$head_file" ]; then
        head_content=$(cat "$head_file")
        if [[ "$head_content" == ref:* ]]; then
            branch="${head_content#ref: refs/heads/}"
        else
            branch="${head_content:0:7} (detached)"
        fi
    fi

    dirty=""
    if [ -n "$(git -C "$cwd" status --porcelain --no-renames -uno 2>/dev/null)" ]; then
        dirty="*"
    fi

    ahead_behind=""
    if upstream=$(git -C "$cwd" rev-parse --abbrev-ref "@{u}" 2>/dev/null); then
        if counts=$(git -C "$cwd" rev-list --left-right --count "HEAD...@{u}" 2>/dev/null); then
            ahead=$(printf '%s' "$counts" | awk '{print $1}')
            behind=$(printf '%s' "$counts" | awk '{print $2}')
            [ "${ahead:-0}" -gt 0 ] 2>/dev/null && ahead_behind="+$ahead"
            [ "${behind:-0}" -gt 0 ] 2>/dev/null && ahead_behind="${ahead_behind}-$behind"
            [ -n "$ahead_behind" ] && ahead_behind=" $ahead_behind"
        fi
    fi

    [ -n "$branch" ] && git_info=" | $branch$dirty$ahead_behind"
fi

# ---------------------------------------------------------------------------
# 4. PR title (cached per repo+branch)
# ---------------------------------------------------------------------------
pr_info=""
if [ -n "$branch" ] && [[ "$branch" != *"(detached)" ]] && command -v gh >/dev/null 2>&1; then
    cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/claude-statusline"
    mkdir -p "$cache_dir" 2>/dev/null
    if repo_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null); then
        safe_key=$(printf '%s/%s' "$repo_root" "$branch" | tr '/ ' '__')
        cache_file="$cache_dir/pr_${safe_key}"

        # TTL: 5 min on success, 60 s on miss so we re-probe quickly after
        # `gh auth login`, a PR open, or gh being installed.
        now=$(date +%s)
        cache_mtime=0
        # GNU stat (Linux) first, BSD stat (macOS) fallback. Order
        # matters: on Linux, BSD's `-f %m` is misread as "filesystem
        # mode" and stat exits 0 with multi-line garbage on stdout
        # that breaks the arithmetic on the next line under `set -u`.
        [ -f "$cache_file" ] && cache_mtime=$(stat -c %Y "$cache_file" 2>/dev/null || stat -f %m "$cache_file" 2>/dev/null || echo 0)
        age=$(( now - cache_mtime ))
        ttl=300
        [ -s "$cache_file" ] || ttl=60

        if [ "$age" -ge "$ttl" ]; then
            # Portable timeout wrapper: prefer `timeout` / `gtimeout`; fall
            # back to perl (present on macOS by default; plain `timeout` is
            # not, which silently broke this segment previously).
            if command -v timeout >/dev/null 2>&1; then
                tmo=(timeout 3)
            elif command -v gtimeout >/dev/null 2>&1; then
                tmo=(gtimeout 3)
            else
                tmo=(perl -e 'alarm shift; exec @ARGV' 3)
            fi
            pr_raw=$(cd "$cwd" && "${tmo[@]}" gh pr view --json number,title --jq '"#\(.number) \(.title)"' 2>/dev/null || true)
            printf '%s' "$pr_raw" > "$cache_file"
        else
            pr_raw=$(cat "$cache_file")
        fi

        if [ -n "$pr_raw" ]; then
            if [ "${#pr_raw}" -gt 55 ]; then
                pr_raw="${pr_raw:0:55}..."
            fi
            pr_info=" | $pr_raw"
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 5. Sandbox state — green [sandbox] / yellow [sandbox-auto] / bold-red
#    [NO SANDBOX] suffix. Walks settings.local.json + settings.json in
#    project then user scope. First file with `.sandbox.enabled` set
#    (true *or* false) wins — `/sandbox` writes to project
#    `settings.local.json`, so that is the file that flips when the user
#    toggles in-session. In a linked worktree that project scope is the
#    *main* checkout, not the worktree directory, so `main_root` has to be
#    in the walk: without it a worktree session whose sandbox is off reads
#    user scope instead and renders a green `[sandbox]` it has not earned.
#    `wt_root` covers the other half — a <cwd> below the working-tree root,
#    where `<cwd>/.claude/` does not exist at all.
#
#    The yellow `[sandbox-auto]` variant lights up when
#    `.sandbox.autoAllowBashIfSandboxed` is true in the same file —
#    it signals that bash commands inside the sandbox skip the per-call
#    allow prompt, which is a wider blast radius than vanilla sandbox.
# ---------------------------------------------------------------------------
sandbox=""
sandbox_auto=""
for f in \
    "${cwd:+$cwd/.claude/settings.local.json}" \
    "${cwd:+$cwd/.claude/settings.json}" \
    "${wt_root:+$wt_root/.claude/settings.local.json}" \
    "${wt_root:+$wt_root/.claude/settings.json}" \
    "${main_root:+$main_root/.claude/settings.local.json}" \
    "${main_root:+$main_root/.claude/settings.json}" \
    "$HOME/.claude/settings.local.json" \
    "$HOME/.claude/settings.json"; do
    [ -n "$f" ] && [ -f "$f" ] || continue
    v=$(python3 -c 'import json,sys
try:
    s = json.load(open(sys.argv[1])).get("sandbox",{})
    e = s.get("enabled")
    a = s.get("autoAllowBashIfSandboxed")
    en = "true" if e is True else ("false" if e is False else "")
    au = "true" if a is True else ("false" if a is False else "")
    print(f"{en}\t{au}")
except Exception:
    pass' "$f" 2>/dev/null)
    en=${v%%$'\t'*}
    au=${v#*$'\t'}
    if [ -n "$en" ]; then
        sandbox="$en"
        sandbox_auto="$au"
        break
    fi
done

esc=$(printf '\033')
green="${esc}[1;32m"
yellow="${esc}[1;33m"
red="${esc}[1;31m"
reset="${esc}[0m"

if [ "$sandbox" = "true" ]; then
    if [ "$sandbox_auto" = "true" ]; then
        sandbox_tag="${yellow}[sandbox-auto]${reset}"
    else
        sandbox_tag="${green}[sandbox]${reset}"
    fi
else
    sandbox_tag="${red}[NO SANDBOX]${reset}"
fi

model_info=""
[ -n "$model" ] && model_info=" | $model"

# ---------------------------------------------------------------------------
# 6. Emit — sandbox tag leads, then folder / git / PR / model.
# ---------------------------------------------------------------------------
printf '%s %s%s%s%s' "$sandbox_tag" "$folder_out" "$git_info" "$pr_info" "$model_info"
