#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#   https://www.apache.org/licenses/LICENSE-2.0
#
# Deterministic helpers for tools/spec-loop/loop.sh. Keep this file free of
# live agent execution so fixture tests can pin runner behaviour without
# launching a headless harness.

spec_loop_append_tooling_source_context() {
    local mode=$1 base=$2 tooling_ref=$3

    cat <<EOF

## Tooling source — read the plan and specs from here

This iteration builds on the integration base \`$base\`, which does
NOT carry the spec-loop tooling. The plan and specs live on the
control branch \`$tooling_ref\`. Read them from there with \`git show\`,
never from the working tree:

\`\`\`
git show $tooling_ref:tools/spec-loop/IMPLEMENTATION_PLAN.md
git ls-tree -r --name-only $tooling_ref tools/spec-loop/specs/
git show $tooling_ref:tools/spec-loop/specs/<file>
\`\`\`

EOF
    if [ "$mode" = "update" ]; then
        cat <<EOF
Read the current specs from \`$tooling_ref\` (commands above) as the
baseline, then author the updated spec files on this work branch —
the sync PR adds them to \`$base\`. Update is the one beat that
writes specs; do that here, not on the control branch.
EOF
    else
        cat <<EOF
Implement the product change on the work branch; do NOT edit specs
there — they are not on \`$base\`. The control branch owns the specs.
EOF
    fi
}

spec_loop_assemble_prompt_file() {
    local prompt_file=$1 dest=$2 mode=$3 build_iteration=$4 base=$5 tooling_ref=$6
    local compact_file=$7 pr_file=$8 branch_file=$9 update_scope_file=${10:-}

    cat "$prompt_file" > "$dest"
    cat "$compact_file" >> "$dest"
    if [ "$mode" != "update" ]; then
        cat "$pr_file" >> "$dest"
    fi
    cat "$branch_file" >> "$dest"

    if [ "$build_iteration" = "true" ] && [ "$tooling_ref" != "$base" ]; then
        spec_loop_append_tooling_source_context "$mode" "$base" "$tooling_ref" >> "$dest"
    fi
    if [ "$mode" = "update" ] && [ -n "$update_scope_file" ]; then
        cat "$update_scope_file" >> "$dest"
    fi
}

# ---- single-flight lock --------------------------------------------------
#
# Two loops in one checkout fight over the working tree: each iteration
# checks out BASE and the agent carves a branch, so the second run yanks
# files out from under the first and both can end up committing half of
# each other's work. When the loop is started by cron or CI an overlap is
# routine (a slow iteration outlives the schedule interval), so the runner
# takes a lock before its first iteration and the second starter exits.
#
# The lock is a directory: `mkdir` is atomic on every POSIX filesystem and
# needs neither flock(1) (absent on macOS) nor a .git write. Inside it,
# `owner` records `<pid> <host> <ISO-8601 start>` so a contender can tell
# a live holder from a crashed one. A holder whose pid is gone on this
# host is stale and is taken over; a holder on another host, or a live
# pid, is respected.
#
# spec_loop_lock_acquire LOCKDIR
#   0  acquired (prints nothing)
#   1  another loop holds it; prints one `already_running …` line on stdout
#   2  could not create or inspect the lock (prints the reason on stderr)
# spec_loop_lock_release LOCKDIR
#   Removes the lock only if this process owns it.
spec_loop_lock_owner_line() {
    printf '%s %s %s\n' "$$" "$(hostname 2>/dev/null || echo unknown-host)" \
        "$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date)"
}

spec_loop_lock_acquire() {
    local lockdir=$1 attempt
    for attempt in 1 2; do
        if mkdir "$lockdir" 2>/dev/null; then
            spec_loop_lock_owner_line > "$lockdir/owner" || {
                rmdir "$lockdir" 2>/dev/null
                echo "spec-loop: could not write $lockdir/owner" >&2
                return 2
            }
            return 0
        fi
        [ -d "$lockdir" ] || {
            echo "spec-loop: could not create lock $lockdir" >&2
            return 2
        }
        local owner pid host started
        owner="$(cat "$lockdir/owner" 2>/dev/null)"
        read -r pid host started <<< "$owner"
        # Stale: same host, the recorded pid is gone. Take it over once.
        if [ "$attempt" = 1 ] && [ -n "$pid" ] && [ "$host" = "$(hostname 2>/dev/null || echo unknown-host)" ] \
            && ! kill -0 "$pid" 2>/dev/null; then
            echo "spec-loop: removing stale lock $lockdir (pid $pid is gone)" >&2
            rm -rf "$lockdir"
            continue
        fi
        if [ -z "$pid" ]; then
            # Lock dir exists but the owner file is not there yet (a racing
            # starter between its mkdir and its write) or unreadable. Treat
            # as held: the other side is live or will be cleaned up next run.
            echo "already_running: another spec-loop holds $lockdir (owner unknown); exiting 0"
        else
            echo "already_running: spec-loop pid $pid on $host (since ${started:-?}) holds $lockdir; exiting 0"
        fi
        return 1
    done
    echo "spec-loop: could not acquire lock $lockdir after removing a stale one" >&2
    return 2
}

spec_loop_lock_release() {
    local lockdir=$1 pid _rest
    [ -d "$lockdir" ] || return 0
    read -r pid _rest < "$lockdir/owner" 2>/dev/null || pid=""
    if [ "$pid" = "$$" ]; then
        rm -rf "$lockdir"
    fi
}

spec_loop_write_last_sync_marker() {
    local marker=$1 base_head=$2
    mkdir -p "$(dirname "$marker")"
    printf '%s\n' "$base_head" > "$marker"
}

spec_loop_marker_branch_name() {
    local base_head=$1
    printf 'advance-last-sync-%s\n' "${base_head:0:7}"
}

spec_loop_launch_agent() {
    local harness=$1 agent=$2 root=$3 prompt_file=$4 model=$5 output_format=$6
    local effort=${7:-}
    local model_args=()
    [ -n "$model" ] && model_args=(--model "$model")

    if [ "$harness" = "opencode" ]; then
        local oc_format_args=()
        local oc_effort_args=()
        [ "$output_format" = "stream-json" ] && oc_format_args=(--format json)
        case "$effort" in
            low)    oc_effort_args=(--variant minimal) ;;
            medium) oc_effort_args=(--variant medium) ;;
            high)   oc_effort_args=(--variant max) ;;
        esac
        "$agent" run \
            --auto \
            ${model_args[@]+"${model_args[@]}"} \
            ${oc_format_args[@]+"${oc_format_args[@]}"} \
            ${oc_effort_args[@]+"${oc_effort_args[@]}"} \
            "$(cat "$prompt_file")" &
    elif [ "$harness" = "codex" ]; then
        local codex_format_args=()
        local codex_effort_args=()
        [ "$output_format" = "stream-json" ] && codex_format_args=(--json)
        case "$effort" in
            low)    codex_effort_args=(-c model_reasoning_effort=low) ;;
            medium) codex_effort_args=(-c model_reasoning_effort=medium) ;;
            high)   codex_effort_args=(-c model_reasoning_effort=xhigh) ;;
        esac
        "$agent" exec \
            --dangerously-bypass-approvals-and-sandbox \
            --cd "$root" \
            ${model_args[@]+"${model_args[@]}"} \
            ${codex_format_args[@]+"${codex_format_args[@]}"} \
            ${codex_effort_args[@]+"${codex_effort_args[@]}"} \
            - < "$prompt_file" &
    elif [ "$harness" = "cursor" ]; then
        # Cursor has no per-invocation effort/thinking-level flag.
        local cursor_format_args=(--output-format "$output_format")
        local cursor_subcommand=()
        [ "$(basename "$agent")" = "cursor" ] && cursor_subcommand=(agent)
        "$agent" \
            ${cursor_subcommand[@]+"${cursor_subcommand[@]}"} \
            --print \
            --force \
            --trust \
            --workspace "$root" \
            ${model_args[@]+"${model_args[@]}"} \
            ${cursor_format_args[@]+"${cursor_format_args[@]}"} \
            "$(cat "$prompt_file")" &
    elif [ "$harness" = "antigravity" ]; then
        # Antigravity CLI (`agy`) headless: `-p <prompt>`. Never pass
        # --dangerously-skip-permissions: headless runs keep the request-review
        # permission mode, so tool calls needing approval are soft-denied (the
        # run still exits 0; the JSON envelope lists them in `denied_actions`).
        # Effort is a first-class `--effort` flag (low|medium|high|xhigh|max).
        local agy_effort_args=()
        case "$effort" in
            low)    agy_effort_args=(--effort low) ;;
            medium) agy_effort_args=(--effort medium) ;;
            high)   agy_effort_args=(--effort max) ;;
        esac
        "$agent" \
            --output-format "$output_format" \
            ${model_args[@]+"${model_args[@]}"} \
            ${agy_effort_args[@]+"${agy_effort_args[@]}"} \
            -p "$(cat "$prompt_file")" &
    elif [ "$harness" = "pi" ]; then
        # Pi headless: `-p <prompt>`, text output by default, JSONL events with
        # `--mode json`. Pi itself never prompts; Magpie's user-scope Pi
        # extension refuses every command that would need approval when there
        # is no UI, so a push or a mutating gh call cannot run unattended.
        # Effort is `--thinking` (off|minimal|low|medium|high|xhigh|max).
        local pi_mode_args=()
        case "$output_format" in
            json|stream-json) pi_mode_args=(--mode json) ;;
        esac
        local pi_effort_args=()
        case "$effort" in
            low)    pi_effort_args=(--thinking low) ;;
            medium) pi_effort_args=(--thinking medium) ;;
            high)   pi_effort_args=(--thinking max) ;;
        esac
        "$agent" \
            ${pi_mode_args[@]+"${pi_mode_args[@]}"} \
            ${model_args[@]+"${model_args[@]}"} \
            ${pi_effort_args[@]+"${pi_effort_args[@]}"} \
            -p "$(cat "$prompt_file")" &
    elif [ "$harness" = "goose" ]; then
        # Goose headless: `goose run --no-session -i <file>` reads the prompt
        # from the instructions file. No approval-skipping flag: Goose's mode
        # comes from its settings, and Magpie's Goose hook refuses everything
        # that would need confirmation outside approve mode, so a push or a
        # mutating gh call cannot run unattended. Goose has no per-invocation
        # effort flag, so the runner omits it.
        "$agent" run --no-session \
            ${model_args[@]+"${model_args[@]}"} \
            -i "$prompt_file" &
    elif [ "$harness" = "kiro" ]; then
        # Kiro CLI headless: positional prompt to `kiro-cli chat --no-interactive`.
        # The model is selected by the chosen agent config (.kiro/agents), not a
        # per-invocation flag, and Kiro has no stream-json output mode here.
        # Effort is a first-class `--effort` flag (low|medium|high|xhigh|max).
        local kiro_effort_args=()
        case "$effort" in
            low)    kiro_effort_args=(--effort low) ;;
            medium) kiro_effort_args=(--effort medium) ;;
            high)   kiro_effort_args=(--effort max) ;;
        esac
        "$agent" chat --no-interactive \
            ${kiro_effort_args[@]+"${kiro_effort_args[@]}"} \
            "$(cat "$prompt_file")" &
    elif [ "$harness" = "grok" ]; then
        # Grok Build headless mode accepts the assembled prompt directly from
        # a file. `--always-approve` permits unattended local work while the
        # explicit deny rules keep remote mutation blocked in depth alongside
        # the external sandbox and agent guard.
        local grok_output_format=plain
        local grok_effort_args=()
        [ "$output_format" = "stream-json" ] && grok_output_format=streaming-json
        case "$effort" in
            low)    grok_effort_args=(--reasoning-effort low) ;;
            medium) grok_effort_args=(--reasoning-effort medium) ;;
            high)   grok_effort_args=(--reasoning-effort high) ;;
        esac
        "$agent" \
            --always-approve \
            --cwd "$root" \
            --deny "Bash(git push:*)" \
            --deny "Bash(gh:*)" \
            --output-format "$grok_output_format" \
            ${model_args[@]+"${model_args[@]}"} \
            ${grok_effort_args[@]+"${grok_effort_args[@]}"} \
            --prompt-file "$prompt_file" &
    else
        local verbose_args=()
        local claude_effort_args=()
        [ "$output_format" = "stream-json" ] && verbose_args=(--verbose)
        case "$effort" in
            low)    claude_effort_args=(--effort low) ;;
            medium) claude_effort_args=(--effort medium) ;;
            high)   claude_effort_args=(--effort max) ;;
        esac
        "$agent" -p \
            --dangerously-skip-permissions \
            --disallowedTools "Bash(git push:*)" "Bash(gh:*)" \
            --output-format="$output_format" \
            ${verbose_args[@]+"${verbose_args[@]}"} \
            ${model_args[@]+"${model_args[@]}"} \
            ${claude_effort_args[@]+"${claude_effort_args[@]}"} < "$prompt_file" &
    fi
    SPEC_LOOP_AGENT_PID=$!
}
