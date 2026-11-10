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

# Paths the update beat diffs since the last sync. Skill content lives under
# plugins/magpie-<family>/skills/ (skills/<name> and .claude/skills/magpie-<name>
# are symlinks into it), so an edit to a skill changes nothing under .claude/skills
# and the old `.claude/skills tools docs/modes.md` scope dropped it. Every place a
# spec's "Where it lives" can point is listed; paths no spec names are simply not
# mapped by spec-scope.
SPEC_LOOP_UPDATE_PATHSPEC=(
    plugins
    skills
    .claude/skills
    tools
    docs
    projects
    organizations
    .github
    AGENTS.md
    README.md
)

spec_loop_update_pathspec() {
    printf '%s\n' "${SPEC_LOOP_UPDATE_PATHSPEC[@]}"
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
# The lock is a symbolic link whose target is the owner line
# `<pid> <host> <ISO-8601 start>`. `ln -s` creates the link and its content
# in one atomic step on every POSIX filesystem, so there is never a lock
# without an owner, and it needs neither flock(1) (absent on macOS) nor a
# .git write. The target is never a real path; it is only read back with
# readlink.
#
# A live holder keeps the link's own mtime fresh (spec_loop_lock_heartbeat,
# every SPEC_LOOP_LOCK_BEAT_SEC seconds, default 60). A lock is stale when
# its pid is gone on this host, or when its heartbeat is older than
# SPEC_LOOP_LOCK_STALE_MIN minutes (default 10) on any host: that covers a
# crashed run on another host or container and a pid reused by an unrelated
# process. A pid that exists but belongs to another user (kill -0 fails
# with EPERM) counts as alive.
#
# Takeovers are serialised by a second link, LOCK.takeover: the starter
# that creates it re-reads the lock and unlinks it only if it still holds
# the owner line judged stale, then acquires normally. A takeover lasts
# milliseconds, so a takeover link older than a minute is left by a
# crashed starter and is removed.
#
# spec_loop_lock_acquire LOCK
#   0  acquired (prints nothing)
#   1  another loop holds it; prints one `already_running …` line on stdout
#   2  could not create or inspect the lock (prints the reason on stderr)
# spec_loop_lock_release LOCK [PID]
#   Removes the lock only if it names PID (default: this process).
# spec_loop_lock_handoff LOCK PID
#   Re-points a lock this process holds at PID (the agent it could not stop).
spec_loop_lock_host() {
    hostname 2>/dev/null || echo unknown-host
}

spec_loop_lock_owner_line() {
    printf '%s %s %s' "${1:-$$}" "$(spec_loop_lock_host)" \
        "$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo unknown-time)"
}

spec_loop_lock_read() {
    readlink "$1" 2>/dev/null
}

# spec_loop_pid_alive PID: 0 when the pid exists (another user's included).
spec_loop_pid_alive() {
    local err
    [ -n "$1" ] || return 1
    err="$(kill -0 "$1" 2>&1)" && return 0
    case "$err" in *"not permitted"*|*EPERM*) return 0 ;; esac
    return 1
}

# spec_loop_lock_stale_reason LOCK PID HOST: prints why the lock is stale,
# nothing when its holder looks alive.
spec_loop_lock_stale_reason() {
    local lock=$1 pid=$2 host=$3 stale_min=${SPEC_LOOP_LOCK_STALE_MIN:-10}
    if [ "$host" = "$(spec_loop_lock_host)" ] && ! spec_loop_pid_alive "$pid"; then
        echo "pid $pid is gone"
    elif [ -n "$(find "$lock" -maxdepth 0 -mmin "+$stale_min" 2>/dev/null)" ]; then
        echo "no heartbeat for over $stale_min min"
    fi
}

# spec_loop_lock_takeover LOCK SEEN_OWNER
#   0 when this caller removed the stale lock it saw; 1 otherwise.
spec_loop_lock_takeover() {
    local lock=$1 seen=$2 mutex="$1.takeover"
    if ! ln -s "$$" "$mutex" 2>/dev/null; then
        if [ -n "$(find "$mutex" -maxdepth 0 -mmin +1 2>/dev/null)" ]; then
            rm -f "$mutex"
        fi
        return 1
    fi
    if [ -n "$seen" ] && [ "$(spec_loop_lock_read "$lock")" = "$seen" ]; then
        rm -f "$lock"
        rm -f "$mutex"
        return 0
    fi
    rm -f "$mutex"
    return 1
}

spec_loop_lock_acquire() {
    local lock=$1 attempt owner pid host started stale
    for attempt in 1 2; do
        # `ln -s` onto an existing directory would create the link inside it
        # and succeed (BSD ln has no -T), so refuse a real directory first.
        if [ -d "$lock" ] && [ ! -L "$lock" ]; then
            echo "spec-loop: $lock exists but is not a spec-loop lock; remove it if no loop is running" >&2
            return 2
        fi
        if ln -s "$(spec_loop_lock_owner_line)" "$lock" 2>/dev/null; then
            return 0
        fi
        if [ ! -L "$lock" ]; then
            if [ -e "$lock" ]; then
                echo "spec-loop: $lock exists but is not a spec-loop lock; remove it if no loop is running" >&2
                return 2
            fi
            [ -d "$(dirname "$lock")" ] || {
                echo "spec-loop: could not create lock $lock (no such directory)" >&2
                return 2
            }
            continue # released between our ln and our check
        fi
        owner="$(spec_loop_lock_read "$lock")"
        read -r pid host started <<< "$owner"
        stale="$(spec_loop_lock_stale_reason "$lock" "$pid" "$host")"
        if [ "$attempt" = 1 ] && [ -n "$stale" ]; then
            if spec_loop_lock_takeover "$lock" "$owner"; then
                echo "spec-loop: removed stale lock $lock ($stale)" >&2
            fi
            continue
        fi
        echo "already_running: spec-loop pid ${pid:-?} on ${host:-?} (since ${started:-?}) holds $lock; exiting 0"
        return 1
    done
    echo "spec-loop: could not acquire lock $lock" >&2
    return 2
}

spec_loop_lock_release() {
    local lock=$1 me=${2:-$$} pid _rest
    read -r pid _rest <<< "$(spec_loop_lock_read "$lock")"
    if [ -n "$pid" ] && [ "$pid" = "$me" ]; then
        rm -f "$lock"
    fi
    return 0
}

spec_loop_lock_handoff() {
    local lock=$1 pid=$2 tmp="$1.handoff.$$"
    rm -f "$tmp"
    ln -s "$(spec_loop_lock_owner_line "$pid")" "$tmp" && mv -f "$tmp" "$lock"
}

# spec_loop_lock_heartbeat LOCK
#   Runs in the background: refreshes the lock's mtime while the pid it
#   names is alive on this host, and exits once it is not. It follows the
#   lock across a handoff, so a lock kept for a running agent stays fresh.
spec_loop_lock_heartbeat() {
    local lock=$1 beat=${SPEC_LOOP_LOCK_BEAT_SEC:-60} pid host _rest
    while :; do
        read -r pid host _rest <<< "$(spec_loop_lock_read "$lock")"
        [ "$host" = "$(spec_loop_lock_host)" ] && spec_loop_pid_alive "$pid" || return 0
        touch -h "$lock" 2>/dev/null
        sleep "$beat"
    done
}

# spec_loop_stop_agent PID [TIMEOUT_SECONDS]
#   Sends TERM to a running agent and waits up to TIMEOUT (default 10) for it
#   to exit. 0 when it is gone, 1 when it is still running. The runner hands
#   its lock to the agent in the second case so no other loop starts over a
#   live agent. Only PID itself is signalled: a SPEC_LOOP_AGENT wrapper must
#   `exec` the agent so the agent is the process that receives TERM.
spec_loop_pid_running() {
    # kill -0 also succeeds for an exited child nobody has reaped yet (a
    # zombie), so read the process state and count Z as gone. When ps is
    # missing or denied (empty output) the process is assumed to be running:
    # keeping the lock is the safe answer.
    spec_loop_pid_alive "$1" || return 1
    case "$(ps -o stat= -p "$1" 2>/dev/null)" in
        Z*) return 1 ;;
    esac
    return 0
}

spec_loop_stop_agent() {
    local pid=$1 timeout=${2:-10} i
    [ -n "$pid" ] || return 0
    spec_loop_pid_running "$pid" || return 0
    kill -TERM "$pid" 2>/dev/null
    for ((i = 0; i < timeout * 10; i++)); do
        spec_loop_pid_running "$pid" || return 0
        sleep 0.1
    done
    return 1
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
