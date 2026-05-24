#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#   https://www.apache.org/licenses/LICENSE-2.0
#
# Spec-driven build loop for this repository.
#
# A small loop in the general "Ralph" style (run a fresh agent context
# against a prompt, repeat), adapted to this framework's posture:
#
#   * THREE modes, ONE mechanism:
#       ./loop.sh                 build, unlimited iterations
#       ./loop.sh 20              build, max 20 iterations
#       ./loop.sh plan [N]        gap-analysis only (updates the plan)
#       ./loop.sh update [N]      back-fill specs from code others contributed
#       ./loop.sh consolidate [N] shrink the plan
#   * BRANCH PER WORK ITEM: before each build iteration the loop returns
#     to the integration base; the build prompt then carves out
#     spec/<slug> for the one work item it implements. One work item =
#     one branch = one PR.
#   * NEVER pushes, NEVER opens a PR. `git push` / `gh pr create` are in
#     .claude/settings.json `ask` — they are the human's step. The loop
#     ends at a local commit and the build prompt prints the human-run
#     push + `gh pr create --web` commands.
#
# SECURITY — read before running:
#   This loop runs the agent with `--dangerously-skip-permissions`, which
#   bypasses the AGENT permission layer (.claude/settings.json deny/ask)
#   but NOT the OS sandbox (clean-env + filesystem/network). Per the
#   project's security model it MUST be launched inside the sandbox
#   harness, with no push/write credentials in the environment. Full
#   rationale: docs/spec-driven-development.md § Security and the
#   dangerously-skip-permissions flag.
#
# Stop gracefully: press Ctrl+C, or `touch STOP` (exits after the current
# iteration finishes).
#
# Env overrides:
#   SPEC_LOOP_BASE   branch to fork work items from
#                    (default: the branch you start the loop on, e.g. main)
#   SPEC_LOOP_AGENT  Claude-compatible agent CLI to run (default: claude)
#   SPEC_LOOP_MODEL  model passed to the agent CLI (default: sonnet)
#   SPEC_LOOP_PR_LIMIT  open PRs to list for duplicate-work checks (default: 100)
#   SPEC_LOOP_PLAN_MAX  plan line count that triggers ONE consolidation
#                    round before building (default: 500)

set -uo pipefail

trap 'echo -e "\nStopping loop..."; exit 0' INT TERM

# Operate from the repo root so the agent sees the whole tree.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "Error: not inside a git repository." >&2; exit 1; }
cd "$ROOT" || exit 1

LOOP_DIR="tools/spec-loop"
PLAN="$LOOP_DIR/IMPLEMENTATION_PLAN.md"

current_branch() {
    local branch
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" || return 1
    if [ "$branch" = "HEAD" ]; then
        return 0
    fi
    printf '%s\n' "$branch"
}

# Default the integration base to the branch the loop is started on
# (typically the repo default, e.g. main). Fall back to main if detached.
BASE="${SPEC_LOOP_BASE:-$(current_branch)}"
BASE="${BASE:-main}"
AGENT="${SPEC_LOOP_AGENT:-claude}"
MODEL="${SPEC_LOOP_MODEL:-sonnet}"
PR_LIMIT="${SPEC_LOOP_PR_LIMIT:-100}"
# Plan length that triggers ONE consolidation round before building. The
# consolidate beat preserves every planned work item, so a plan that is long
# because of *pending work* (not stale history) cannot shrink below this —
# hence the one-shot latch below, which avoids re-consolidating forever.
PLAN_CONSOLIDATE_THRESHOLD="${SPEC_LOOP_PLAN_MAX:-500}"

# ---- parse arguments -------------------------------------------------
if [ "${1:-}" = "plan" ]; then
    MODE="plan";        PROMPT_FILE="$LOOP_DIR/PROMPT_plan.md";        MAX_ITERATIONS="${2:-0}"
elif [ "${1:-}" = "update" ]; then
    MODE="update";      PROMPT_FILE="$LOOP_DIR/PROMPT_update.md";      MAX_ITERATIONS="${2:-0}"
elif [ "${1:-}" = "consolidate" ]; then
    MODE="consolidate"; PROMPT_FILE="$LOOP_DIR/PROMPT_consolidate.md"; MAX_ITERATIONS="${2:-0}"
elif [[ "${1:-}" =~ ^[0-9]+$ ]]; then
    MODE="build";       PROMPT_FILE="$LOOP_DIR/PROMPT_build.md";       MAX_ITERATIONS="$1"
else
    MODE="build";       PROMPT_FILE="$LOOP_DIR/PROMPT_build.md";       MAX_ITERATIONS=0
fi

[ -f "$PROMPT_FILE" ] || { echo "Error: $PROMPT_FILE not found" >&2; exit 1; }

if ! command -v "$AGENT" >/dev/null 2>&1; then
    echo "Error: agent CLI '$AGENT' not found on PATH." >&2
    echo "Set SPEC_LOOP_AGENT to a Claude-compatible CLI or wrapper." >&2
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Mode:   $MODE"
echo "Prompt: $PROMPT_FILE"
echo "Base:   $BASE  (work items fork from here)"
echo "Agent:  $AGENT"
echo "Model:  $MODEL"
[ "$MAX_ITERATIONS" -gt 0 ] && echo "Max:    $MAX_ITERATIONS iterations"
echo "Stop:   Ctrl+C  or  touch STOP"
echo "Note:   this loop never pushes and never opens a PR."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

rm -f STOP
ITERATION=0
CONSOLIDATE_TRIED=false   # one-shot latch; resets when the plan drops back under the limit

# spinner during silent agent calls
spinner() {
    local pid=$1 frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  %s  working... (Ctrl+C to stop)" "${frames:$i:1}"
        i=$(( (i+1) % ${#frames} )); sleep 0.15
    done
    printf "\r                                              \r"
}

open_pr_context() {
    echo ""
    echo "## Open pull-request context"
    echo ""
    echo "The runner collected this immediately before the iteration. Treat open"
    echo "pull requests as in-flight work: do not add plan items that are already"
    echo "substantially covered by an open PR, and do not pick a build item that"
    echo "duplicates one."
    echo ""

    if ! command -v gh >/dev/null 2>&1; then
        echo "- unavailable: gh CLI not found on PATH."
        return 0
    fi

    local prs
    prs="$(gh pr list \
        --state open \
        --limit "$PR_LIMIT" \
        --json number,title,headRefName,baseRefName,url,isDraft \
        --template '{{range .}}- #{{.number}} {{.title}} ({{.headRefName}} -> {{.baseRefName}}){{if .isDraft}} [draft]{{end}} {{.url}}{{"\n"}}{{end}}' \
        2>/dev/null)"
    if [ $? -ne 0 ]; then
        echo "- unavailable: gh pr list failed. Check GitHub authentication or network access."
    elif [ -z "$prs" ]; then
        echo "- No open pull requests found."
    else
        printf '%s\n' "$prs"
    fi
}

while true; do
    if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
        echo "Reached max iterations: $MAX_ITERATIONS"; break
    fi
    if [ -f STOP ]; then echo "STOP file detected — exiting."; rm -f STOP; break; fi

    ITERATION=$((ITERATION + 1))
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━ LOOP $ITERATION  [ $(date '+%H:%M:%S') ] ━━━━━━━━━━━━━━━━━━━━"

    ACTIVE_PROMPT="$PROMPT_FILE"

    if [ "$MODE" = "build" ] || [ "$MODE" = "update" ]; then
        # Return to the integration base so the next branch forks cleanly.
        if ! git switch "$BASE" >/dev/null 2>&1; then
            echo "Error: could not switch to base '$BASE' (uncommitted changes?)." >&2
            echo "Resolve the working tree, then re-run." >&2; break
        fi
        BASE_HEAD="$(git rev-parse HEAD)"
    fi

    if [ "$MODE" = "build" ]; then
        # Consolidate at most ONCE when the plan grows too long, then build
        # even if it is still over: the remaining length is planned work
        # items, which the consolidate beat preserves by design. The latch
        # resets once the plan drops back under the limit (e.g. after items
        # merge and a plan pass prunes them), so we never re-consolidate in a
        # loop without making progress.
        PLAN_LINES=$(wc -l < "$PLAN" 2>/dev/null || echo 0)
        if [ "$PLAN_LINES" -le "$PLAN_CONSOLIDATE_THRESHOLD" ]; then
            CONSOLIDATE_TRIED=false
        elif [ "$CONSOLIDATE_TRIED" = false ]; then
            echo "  [plan] $PLAN is ${PLAN_LINES} lines (> ${PLAN_CONSOLIDATE_THRESHOLD}) — one consolidation round"
            ACTIVE_PROMPT="$LOOP_DIR/PROMPT_consolidate.md"
            CONSOLIDATE_TRIED=true
        else
            echo "  [plan] $PLAN still ${PLAN_LINES} lines after consolidation — length is planned work; building"
        fi
    fi

    PROMPT_WITH_CONTEXT="$(mktemp "${TMPDIR:-/tmp}/spec-loop-prompt.XXXXXX")" || exit 1
    cat "$ACTIVE_PROMPT" > "$PROMPT_WITH_CONTEXT"
    open_pr_context >> "$PROMPT_WITH_CONTEXT"

    # Run one iteration with a fresh context.
    #   -p                              headless / non-interactive
    #   --dangerously-skip-permissions  let the agent edit + validate
    #                                   unattended. Bypasses the AGENT
    #                                   permission layer, NOT the OS sandbox
    #                                   (see the SECURITY header above).
    #   --disallowedTools …             defense-in-depth: hard-deny push and
    #                                   gh so a stray call cannot reach the
    #                                   remote even with permissions skipped.
    "$AGENT" -p \
        --dangerously-skip-permissions \
        --disallowedTools "Bash(git push *)" "Bash(gh *)" \
        --output-format=text \
        --model "$MODEL" < "$PROMPT_WITH_CONTEXT" &
    AGENT_PID=$!
    spinner "$AGENT_PID" & SPINNER_PID=$!
    wait "$AGENT_PID"
    wait "$SPINNER_PID" 2>/dev/null
    rm -f "$PROMPT_WITH_CONTEXT"

    CUR_BRANCH="$(current_branch)"
    LAST_COMMIT="$(git log --oneline -1 2>/dev/null)"
    echo "[ branch ] $CUR_BRANCH"
    [ -n "$LAST_COMMIT" ] && echo "[ commit ] $LAST_COMMIT"

    # Safety guard: a build/update iteration must never commit to the base.
    if { [ "$MODE" = "build" ] || [ "$MODE" = "update" ]; } && [ "$ACTIVE_PROMPT" = "$PROMPT_FILE" ]; then
        if [ "$CUR_BRANCH" = "$BASE" ] && [ "$(git rev-parse HEAD)" != "$BASE_HEAD" ]; then
            echo "✗ This iteration committed to '$BASE' instead of a work-item branch." >&2
            echo "  Stopping so you can review (expected a new spec/<slug> branch)." >&2
            break
        fi
    fi
    echo ""
done
