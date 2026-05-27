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
#       ./loop.sh plan [N]        gap-analysis only, updates the plan (default 1 pass; N=0 unlimited)
#       ./loop.sh update [N]      back-fill specs from code others contributed (default 1 pass; N=0 unlimited)
#       ./loop.sh consolidate [N] shrink the plan (default 1 pass; N=0 unlimited)
#   * BRANCH PER WORK ITEM: before each build iteration the loop returns
#     to the integration base; the build prompt then carves out
#     <slug> for the one work item it implements. One work item =
#     one branch = one PR.
#   * NEVER pushes, NEVER opens a PR. `git push` / `gh pr create` are in
#     .claude/settings.json `ask` — they are the human's step. The loop
#     ends at a local commit and the build prompt prints the human-run
#     push + `gh pr create --web` commands.
#   * NO REDOING BUILT WORK: because the loop never pushes, a work item it
#     already built exists only as a LOCAL BRANCH and has no open PR. Each
#     iteration therefore feeds the agent BOTH the open PRs and the local
#     work-item branches as in-flight work. Without the local-branch signal
#     the agent would re-pick the same top-priority plan item every
#     iteration and rebuild it forever (an endless loop).
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
#   SPEC_LOOP_BASE   branch to fork work items from (default: main)
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

# Default the integration base to main — the repo's integration target —
# regardless of which branch the loop is launched from. Work items fork
# from here. Override with SPEC_LOOP_BASE to build on top of a different
# branch.
BASE="${SPEC_LOOP_BASE:-main}"
# The control branch: where loop.sh, the prompts, the plan and the specs
# live. Captured now, before the loop checks anything out, because a
# build/update iteration checks out BASE (e.g. main) — which need not carry
# the spec-loop tooling. Every tooling read below goes through this ref via
# `git show`, so the loop works when launched from a feature branch while
# building on main.
TOOLING_REF="$(current_branch)"
TOOLING_REF="${TOOLING_REF:-HEAD}"
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
    MODE="plan";        PROMPT_FILE="$LOOP_DIR/PROMPT_plan.md";        MAX_ITERATIONS="${2:-1}"
elif [ "${1:-}" = "update" ]; then
    MODE="update";      PROMPT_FILE="$LOOP_DIR/PROMPT_update.md";      MAX_ITERATIONS="${2:-1}"
elif [ "${1:-}" = "consolidate" ]; then
    MODE="consolidate"; PROMPT_FILE="$LOOP_DIR/PROMPT_consolidate.md"; MAX_ITERATIONS="${2:-1}"
elif [[ "${1:-}" =~ ^[0-9]+$ ]]; then
    MODE="build";       PROMPT_FILE="$LOOP_DIR/PROMPT_build.md";       MAX_ITERATIONS="$1"
else
    MODE="build";       PROMPT_FILE="$LOOP_DIR/PROMPT_build.md";       MAX_ITERATIONS=0
fi

# Reject a non-numeric iteration count. The plan/update/consolidate second
# argument flows straight into the integer comparisons below, where a typo'd
# value would otherwise error to stderr and be silently treated as 0 — i.e.
# run unbounded instead of failing.
if ! [[ "$MAX_ITERATIONS" =~ ^[0-9]+$ ]]; then
    echo "Error: iteration count must be a non-negative integer, got '${MAX_ITERATIONS}'." >&2
    exit 1
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
    local pid=$1 i=0
    # Index frames as array elements, not string offsets: ${frames:$i:1} is
    # byte-based under a C/POSIX locale (common in the clean-env sandbox) and
    # would slice a multibyte braille glyph into garbage.
    local frames=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  %s  working... (Ctrl+C to stop)" "${frames[i]}"
        i=$(( (i+1) % ${#frames[@]} )); sleep 0.15
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

# Local work-item branches the loop has already built. This is the companion
# to open_pr_context: the loop never pushes, so a freshly built item has NO
# open PR and is invisible to the PR check above. Listing it here as in-flight
# work is what stops the agent re-picking the same top-priority plan item and
# rebuilding it on a new branch every iteration. Reads refs only, so it is
# correct regardless of which branch is currently checked out.
local_branch_context() {
    echo ""
    echo "## Local work-item branches"
    echo ""
    echo "The runner collected this immediately before the iteration. This loop"
    echo "never pushes and never opens a PR, so a work item it has already built"
    echo "exists ONLY as a local branch and will NOT appear in the open-PR"
    echo "context above. Treat every branch listed here as work that is already"
    echo "built or in flight: do not add a plan item, and do not pick a build"
    echo "item, whose slug matches one of these branches or whose change one of"
    echo "them already carries. Checking these branches (not just open PRs) is"
    echo "what keeps the loop from rebuilding the same item every iteration."
    echo ""

    local have_base=false
    if git rev-parse --verify --quiet "refs/heads/$BASE" >/dev/null 2>&1; then
        have_base=true
    fi

    # Every local branch except the integration base and the control branch
    # (where the tooling lives); those two are never work-item branches.
    local branches
    branches="$(git for-each-ref --format='%(refname:short)' refs/heads/ \
        | grep -vxF "$BASE" \
        | grep -vxF "$TOOLING_REF")"

    if [ -z "$branches" ]; then
        echo "- No local work-item branches found."
        return 0
    fi

    local b subject ahead
    while IFS= read -r b; do
        [ -n "$b" ] || continue
        subject="$(git log -1 --format='%s' "$b" 2>/dev/null)"
        if [ "$have_base" = true ]; then
            ahead="$(git rev-list --count "$BASE..$b" 2>/dev/null)"
            echo "- ${b} (${ahead:-?} commit(s) ahead of ${BASE}): ${subject}"
        else
            echo "- ${b}: ${subject}"
        fi
    done <<< "$branches"
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

    if [ "$MODE" = "build" ]; then
        # Consolidate at most ONCE when the plan grows too long, then build
        # even if it is still over: the remaining length is planned work
        # items, which the consolidate beat preserves by design. The latch
        # resets once the plan drops back under the limit (e.g. after items
        # merge and a plan pass prunes them), so we never re-consolidate in a
        # loop without making progress. Prefer the working-tree plan (so
        # local edits count); fall back to the control branch ($TOOLING_REF)
        # if the tree is on a base (e.g. main) that lacks the spec-loop tooling.
        PLAN_LINES=$( { [ -f "$PLAN" ] && cat "$PLAN" || git show "$TOOLING_REF:$PLAN" 2>/dev/null; } | wc -l )
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

    # A genuine build/update iteration (not a consolidate swap-in) carves a
    # work-item branch off BASE. Plan/consolidate beats — and the consolidate
    # swap-in — instead stay on the control branch, where the tooling lives.
    BUILD_ITERATION=false
    if { [ "$MODE" = "build" ] || [ "$MODE" = "update" ]; } && [ "$ACTIVE_PROMPT" = "$PROMPT_FILE" ]; then
        BUILD_ITERATION=true
    fi

    # Assemble the prompt BEFORE any checkout, while the working tree is still
    # on the control branch. Prefer the working-tree copy (local edits count);
    # fall back to the control branch ($TOOLING_REF) if the tree is on a base
    # that lacks the tooling. Either way the read never breaks after checkout.
    PROMPT_WITH_CONTEXT="$(mktemp "${TMPDIR:-/tmp}/spec-loop-prompt.XXXXXX")" || exit 1
    if [ -f "$ACTIVE_PROMPT" ]; then
        cat "$ACTIVE_PROMPT" > "$PROMPT_WITH_CONTEXT"
    elif ! git show "$TOOLING_REF:$ACTIVE_PROMPT" > "$PROMPT_WITH_CONTEXT" 2>/dev/null; then
        echo "Error: could not read '$ACTIVE_PROMPT' from the working tree or control branch '$TOOLING_REF'." >&2
        rm -f "$PROMPT_WITH_CONTEXT"; break
    fi
    open_pr_context >> "$PROMPT_WITH_CONTEXT"
    local_branch_context >> "$PROMPT_WITH_CONTEXT"

    if [ "$BUILD_ITERATION" = true ]; then
        # The work-item branch forks off BASE (e.g. main), which need not
        # carry the spec-loop tooling. Tell the agent to read the plan and
        # specs from the control branch, not the working tree.
        if [ "$TOOLING_REF" != "$BASE" ]; then
            {
                echo ""
                echo "## Tooling source — read the plan and specs from here"
                echo ""
                echo "This iteration builds on the integration base \`$BASE\`, which does"
                echo "NOT carry the spec-loop tooling. The plan and specs live on the"
                echo "control branch \`$TOOLING_REF\`. Read them from there with \`git show\`,"
                echo "never from the working tree:"
                echo ""
                echo '```'
                echo "git show $TOOLING_REF:tools/spec-loop/IMPLEMENTATION_PLAN.md"
                echo "git ls-tree -r --name-only $TOOLING_REF tools/spec-loop/specs/"
                echo "git show $TOOLING_REF:tools/spec-loop/specs/<file>"
                echo '```'
                echo ""
                if [ "$MODE" = "update" ]; then
                    echo "Read the current specs from \`$TOOLING_REF\` (commands above) as the"
                    echo "baseline, then author the updated spec files on this work branch —"
                    echo "the sync PR adds them to \`$BASE\`. Update is the one beat that"
                    echo "writes specs; do that here, not on the control branch."
                else
                    echo "Implement the product change on the work branch; do NOT edit specs"
                    echo "there — they are not on \`$BASE\`. The control branch owns the specs."
                fi
            } >> "$PROMPT_WITH_CONTEXT"
        fi

        # Check out the base now — right before the agent runs, not earlier —
        # so the reads above came from the control branch. The agent then
        # forks its own <slug> branch off this base.
        if [ "$(current_branch)" != "$BASE" ]; then
            if ! checkout_out="$(git checkout "$BASE" 2>&1)"; then
                echo "Error: could not check out base '$BASE'. git reported:" >&2
                printf '  %s\n' "$checkout_out" >&2
                echo "Resolve the working tree (commit or stash changes), then re-run." >&2
                rm -f "$PROMPT_WITH_CONTEXT"; break
            fi
        fi
        BASE_HEAD="$(git rev-parse HEAD)"
    fi

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
        --disallowedTools "Bash(git push:*)" "Bash(gh:*)" \
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

    if [ "$BUILD_ITERATION" = true ]; then
        # Report the work-item branch the agent produced, by name, so you know
        # exactly what to push.
        if [ "$CUR_BRANCH" != "$BASE" ] && [ "$CUR_BRANCH" != "$TOOLING_REF" ]; then
            echo "[ new branch ] $CUR_BRANCH  (forked off $BASE)"
            echo "               push it with:  git push -u origin $CUR_BRANCH"
        else
            echo "⚠ No work-item branch was created (still on '$CUR_BRANCH'). Check the agent output above." >&2
        fi

        # Safety guard: a build/update iteration must never commit to the base.
        if [ "$CUR_BRANCH" = "$BASE" ] && [ "$(git rev-parse HEAD)" != "$BASE_HEAD" ]; then
            echo "✗ This iteration committed to '$BASE' instead of a work-item branch." >&2
            echo "  Stopping so you can review (expected a new <slug> branch)." >&2
            break
        fi

        # Return to the control branch so the tooling (plan, prompts, specs) is
        # present again and you are never stranded on the base. The work-item
        # branch the agent created persists; this only moves HEAD.
        if [ "$(current_branch)" != "$TOOLING_REF" ]; then
            git checkout "$TOOLING_REF" >/dev/null 2>&1 || \
                echo "⚠ Could not return to control branch '$TOOLING_REF' (now on '$(current_branch)')." >&2
        fi
    fi
    echo ""
done
