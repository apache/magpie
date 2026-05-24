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
# Stop gracefully: press Ctrl+C, or `touch STOP` (exits after the current
# iteration finishes).
#
# Env overrides:
#   SPEC_LOOP_BASE   branch to fork work items from
#                    (default: the branch you start the loop on, e.g. main)
#   SPEC_LOOP_MODEL  model passed to the agent CLI (default: sonnet)

set -uo pipefail

trap 'echo -e "\nStopping loop..."; exit 0' INT TERM

# Operate from the repo root so the agent sees the whole tree.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "Error: not inside a git repository." >&2; exit 1; }
cd "$ROOT" || exit 1

LOOP_DIR="tools/spec-loop"
PLAN="$LOOP_DIR/IMPLEMENTATION_PLAN.md"
# Default the integration base to the branch the loop is started on
# (typically the repo default, e.g. main). Fall back to main if detached.
BASE="${SPEC_LOOP_BASE:-$(git branch --show-current)}"
BASE="${BASE:-main}"
MODEL="${SPEC_LOOP_MODEL:-sonnet}"
PLAN_CONSOLIDATE_THRESHOLD=500

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

if ! command -v claude >/dev/null 2>&1; then
    echo "Error: 'claude' agent CLI not found on PATH." >&2; exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Mode:   $MODE"
echo "Prompt: $PROMPT_FILE"
echo "Base:   $BASE  (work items fork from here)"
echo "Model:  $MODEL"
[ "$MAX_ITERATIONS" -gt 0 ] && echo "Max:    $MAX_ITERATIONS iterations"
echo "Stop:   Ctrl+C  or  touch STOP"
echo "Note:   this loop never pushes and never opens a PR."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

rm -f STOP
ITERATION=0

# spinner during silent agent calls
spinner() {
    local pid=$1 frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  %s  working... (Ctrl+C to stop)" "${frames:$i:1}"
        i=$(( (i+1) % ${#frames} )); sleep 0.15
    done
    printf "\r                                              \r"
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
        # If the plan has grown too long, consolidate it this round instead.
        PLAN_LINES=$(wc -l < "$PLAN" 2>/dev/null || echo 0)
        if [ "$PLAN_LINES" -gt "$PLAN_CONSOLIDATE_THRESHOLD" ]; then
            echo "  [plan] $PLAN is ${PLAN_LINES} lines — running a consolidation round"
            ACTIVE_PROMPT="$LOOP_DIR/PROMPT_consolidate.md"
        fi
    fi

    # Run one iteration with a fresh context.
    #   -p                              headless / non-interactive
    #   --dangerously-skip-permissions  autonomous edits; the loop's safety
    #                                   is branch-per-item + no-push (above)
    #                                   and the OS sandbox underneath.
    cat "$ACTIVE_PROMPT" | claude -p \
        --dangerously-skip-permissions \
        --output-format=text \
        --model "$MODEL" &
    CLAUDE_PID=$!
    spinner "$CLAUDE_PID" & SPINNER_PID=$!
    wait "$CLAUDE_PID"; kill "$SPINNER_PID" 2>/dev/null; wait "$SPINNER_PID" 2>/dev/null

    CUR_BRANCH="$(git branch --show-current)"
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
