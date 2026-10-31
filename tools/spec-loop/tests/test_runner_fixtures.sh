#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#   https://www.apache.org/licenses/LICENSE-2.0

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=tools/spec-loop/lib.sh
. "$ROOT/tools/spec-loop/lib.sh"

TMPDIR_TEST="$(mktemp -d "${TMPDIR:-/tmp}/spec-loop-fixtures.XXXXXX")"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

assert_contains() {
    local file=$1 expected=$2
    grep -Fq -- "$expected" "$file" || fail "expected '$file' to contain: $expected"
}

assert_not_contains() {
    local file=$1 unexpected=$2
    ! grep -Fq -- "$unexpected" "$file" || fail "expected '$file' not to contain: $unexpected"
}

write_fixture() {
    local file=$1 text=$2
    printf '%s\n' "$text" > "$file"
}

test_prompt_assembly_build() {
    write_fixture "$TMPDIR_TEST/prompt.md" "PROMPT BODY"
    write_fixture "$TMPDIR_TEST/compact.md" "COMPACT INVENTORY"
    write_fixture "$TMPDIR_TEST/prs.md" "OPEN PR CONTEXT"
    write_fixture "$TMPDIR_TEST/branches.md" "LOCAL BRANCH CONTEXT"
    write_fixture "$TMPDIR_TEST/update.md" "UPDATE SCOPE"

    spec_loop_assemble_prompt_file \
        "$TMPDIR_TEST/prompt.md" "$TMPDIR_TEST/build.out" build true main control-branch \
        "$TMPDIR_TEST/compact.md" "$TMPDIR_TEST/prs.md" "$TMPDIR_TEST/branches.md" "$TMPDIR_TEST/update.md"

    assert_contains "$TMPDIR_TEST/build.out" "PROMPT BODY"
    assert_contains "$TMPDIR_TEST/build.out" "COMPACT INVENTORY"
    assert_contains "$TMPDIR_TEST/build.out" "OPEN PR CONTEXT"
    assert_contains "$TMPDIR_TEST/build.out" "LOCAL BRANCH CONTEXT"
    assert_contains "$TMPDIR_TEST/build.out" "git show control-branch:tools/spec-loop/IMPLEMENTATION_PLAN.md"
    assert_contains "$TMPDIR_TEST/build.out" "Implement the product change on the work branch"
    assert_not_contains "$TMPDIR_TEST/build.out" "UPDATE SCOPE"
}

test_prompt_assembly_update() {
    write_fixture "$TMPDIR_TEST/prompt.md" "PROMPT BODY"
    write_fixture "$TMPDIR_TEST/compact.md" "COMPACT INVENTORY"
    write_fixture "$TMPDIR_TEST/prs.md" "OPEN PR CONTEXT"
    write_fixture "$TMPDIR_TEST/branches.md" "LOCAL BRANCH CONTEXT"
    write_fixture "$TMPDIR_TEST/update.md" "UPDATE SCOPE"

    spec_loop_assemble_prompt_file \
        "$TMPDIR_TEST/prompt.md" "$TMPDIR_TEST/update.out" update true main control-branch \
        "$TMPDIR_TEST/compact.md" "$TMPDIR_TEST/prs.md" "$TMPDIR_TEST/branches.md" "$TMPDIR_TEST/update.md"

    assert_contains "$TMPDIR_TEST/update.out" "PROMPT BODY"
    assert_contains "$TMPDIR_TEST/update.out" "COMPACT INVENTORY"
    assert_contains "$TMPDIR_TEST/update.out" "LOCAL BRANCH CONTEXT"
    assert_contains "$TMPDIR_TEST/update.out" "Read the current specs from"
    assert_contains "$TMPDIR_TEST/update.out" "UPDATE SCOPE"
    assert_not_contains "$TMPDIR_TEST/update.out" "OPEN PR CONTEXT"
}

make_fake_agent() {
    local path=$1 log=$2
    cat > "$path" <<EOF
#!/usr/bin/env bash
{
  printf 'argv:'
  printf ' <%s>' "\$@"
  printf '\\nstdin:'
  cat
  printf '\\n'
} > "$log"
EOF
    chmod +x "$path"
}

test_harness_command_construction() {
    write_fixture "$TMPDIR_TEST/prompt.md" "PROMPT BODY"
    make_fake_agent "$TMPDIR_TEST/claude" "$TMPDIR_TEST/claude.log"
    make_fake_agent "$TMPDIR_TEST/codex" "$TMPDIR_TEST/codex.log"

    # Unset effort: argv must not gain effort-related flags.
    spec_loop_launch_agent claude "$TMPDIR_TEST/claude" /repo "$TMPDIR_TEST/prompt.md" sonnet stream-json
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/claude.log" "<-p>"
    assert_contains "$TMPDIR_TEST/claude.log" "<--dangerously-skip-permissions>"
    assert_contains "$TMPDIR_TEST/claude.log" "<--disallowedTools>"
    assert_contains "$TMPDIR_TEST/claude.log" "<Bash(git push:*)>"
    assert_contains "$TMPDIR_TEST/claude.log" "<Bash(gh:*)>"
    assert_contains "$TMPDIR_TEST/claude.log" "<--output-format=stream-json>"
    assert_contains "$TMPDIR_TEST/claude.log" "<--verbose>"
    assert_contains "$TMPDIR_TEST/claude.log" "<--model>"
    assert_contains "$TMPDIR_TEST/claude.log" "<sonnet>"
    assert_contains "$TMPDIR_TEST/claude.log" "stdin:PROMPT BODY"
    assert_not_contains "$TMPDIR_TEST/claude.log" "<--effort>"

    spec_loop_launch_agent codex "$TMPDIR_TEST/codex" /repo "$TMPDIR_TEST/prompt.md" gpt-5 stream-json
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/codex.log" "<exec>"
    assert_contains "$TMPDIR_TEST/codex.log" "<--dangerously-bypass-approvals-and-sandbox>"
    assert_contains "$TMPDIR_TEST/codex.log" "<--cd>"
    assert_contains "$TMPDIR_TEST/codex.log" "</repo>"
    assert_contains "$TMPDIR_TEST/codex.log" "<--model>"
    assert_contains "$TMPDIR_TEST/codex.log" "<gpt-5>"
    assert_contains "$TMPDIR_TEST/codex.log" "<--json>"
    assert_contains "$TMPDIR_TEST/codex.log" "<->"
    assert_contains "$TMPDIR_TEST/codex.log" "stdin:PROMPT BODY"
    assert_not_contains "$TMPDIR_TEST/codex.log" "<model_reasoning_effort="

    make_fake_agent "$TMPDIR_TEST/kiro-cli" "$TMPDIR_TEST/kiro.log"
    spec_loop_launch_agent kiro "$TMPDIR_TEST/kiro-cli" /repo "$TMPDIR_TEST/prompt.md" "" text
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/kiro.log" "<chat>"
    assert_contains "$TMPDIR_TEST/kiro.log" "<--no-interactive>"
    assert_contains "$TMPDIR_TEST/kiro.log" "<PROMPT BODY>"
    assert_not_contains "$TMPDIR_TEST/kiro.log" "<--model>"
    assert_not_contains "$TMPDIR_TEST/kiro.log" "<--effort>"

    # Set-and-mapped: framework high → each CLI's top effort value.
    make_fake_agent "$TMPDIR_TEST/claude-effort" "$TMPDIR_TEST/claude-effort.log"
    spec_loop_launch_agent claude "$TMPDIR_TEST/claude-effort" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/claude-effort.log" "<--effort>"
    assert_contains "$TMPDIR_TEST/claude-effort.log" "<max>"

    make_fake_agent "$TMPDIR_TEST/codex-effort" "$TMPDIR_TEST/codex-effort.log"
    spec_loop_launch_agent codex "$TMPDIR_TEST/codex-effort" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/codex-effort.log" "<-c>"
    assert_contains "$TMPDIR_TEST/codex-effort.log" "<model_reasoning_effort=xhigh>"

    make_fake_agent "$TMPDIR_TEST/opencode" "$TMPDIR_TEST/opencode.log"
    spec_loop_launch_agent opencode "$TMPDIR_TEST/opencode" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/opencode.log" "<run>"
    assert_contains "$TMPDIR_TEST/opencode.log" "<--auto>"
    assert_contains "$TMPDIR_TEST/opencode.log" "<--variant>"
    assert_contains "$TMPDIR_TEST/opencode.log" "<max>"

    # OpenCode low is the one non-identity low mapping (low → minimal).
    make_fake_agent "$TMPDIR_TEST/opencode-low" "$TMPDIR_TEST/opencode-low.log"
    spec_loop_launch_agent opencode "$TMPDIR_TEST/opencode-low" /repo "$TMPDIR_TEST/prompt.md" "" text low
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/opencode-low.log" "<--variant>"
    assert_contains "$TMPDIR_TEST/opencode-low.log" "<minimal>"
    assert_not_contains "$TMPDIR_TEST/opencode-low.log" "<low>"

    # One medium case (identity mapping still worth pinning).
    make_fake_agent "$TMPDIR_TEST/claude-medium" "$TMPDIR_TEST/claude-medium.log"
    spec_loop_launch_agent claude "$TMPDIR_TEST/claude-medium" /repo "$TMPDIR_TEST/prompt.md" "" text medium
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/claude-medium.log" "<--effort>"
    assert_contains "$TMPDIR_TEST/claude-medium.log" "<medium>"

    make_fake_agent "$TMPDIR_TEST/kiro-effort" "$TMPDIR_TEST/kiro-effort.log"
    spec_loop_launch_agent kiro "$TMPDIR_TEST/kiro-effort" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/kiro-effort.log" "<--effort>"
    assert_contains "$TMPDIR_TEST/kiro-effort.log" "<max>"
    assert_not_contains "$TMPDIR_TEST/kiro-effort.log" "<--model>"

    # Set-but-unsupported: Cursor has no effort knob — omit silently.
    make_fake_agent "$TMPDIR_TEST/cursor-agent" "$TMPDIR_TEST/cursor.log"
    spec_loop_launch_agent cursor "$TMPDIR_TEST/cursor-agent" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/cursor.log" "<--print>"
    assert_contains "$TMPDIR_TEST/cursor.log" "<--force>"
    assert_contains "$TMPDIR_TEST/cursor.log" "<--trust>"
    assert_not_contains "$TMPDIR_TEST/cursor.log" "<--effort>"
    assert_not_contains "$TMPDIR_TEST/cursor.log" "<--variant>"
    assert_not_contains "$TMPDIR_TEST/cursor.log" "model_reasoning_effort"

    # Antigravity CLI: headless -p, effort forwarded, never auto-approved.
    make_fake_agent "$TMPDIR_TEST/agy" "$TMPDIR_TEST/agy.log"
    spec_loop_launch_agent antigravity "$TMPDIR_TEST/agy" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/agy.log" "<-p> <PROMPT BODY>"
    assert_contains "$TMPDIR_TEST/agy.log" "<--output-format> <text>"
    assert_contains "$TMPDIR_TEST/agy.log" "<--effort> <max>"
    assert_not_contains "$TMPDIR_TEST/agy.log" "<--dangerously-skip-permissions>"
    assert_not_contains "$TMPDIR_TEST/agy.log" "<--mode>"
    assert_not_contains "$TMPDIR_TEST/agy.log" "<--model>"

    make_fake_agent "$TMPDIR_TEST/agy-model" "$TMPDIR_TEST/agy-model.log"
    spec_loop_launch_agent antigravity "$TMPDIR_TEST/agy-model" /repo "$TMPDIR_TEST/prompt.md" agy-test stream-json low
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/agy-model.log" "<--output-format> <stream-json>"
    assert_contains "$TMPDIR_TEST/agy-model.log" "<--model> <agy-test>"
    assert_contains "$TMPDIR_TEST/agy-model.log" "<--effort> <low>"

    # Pi: headless -p, text by default, --thinking for effort, no approval flag.
    make_fake_agent "$TMPDIR_TEST/pi" "$TMPDIR_TEST/pi.log"
    spec_loop_launch_agent pi "$TMPDIR_TEST/pi" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/pi.log" "<-p> <PROMPT BODY>"
    assert_contains "$TMPDIR_TEST/pi.log" "<--thinking> <max>"
    assert_not_contains "$TMPDIR_TEST/pi.log" "<--mode>"
    assert_not_contains "$TMPDIR_TEST/pi.log" "<--model>"
    assert_not_contains "$TMPDIR_TEST/pi.log" "<--magpie-no-sandbox>"
    assert_not_contains "$TMPDIR_TEST/pi.log" "<--no-extensions>"

    make_fake_agent "$TMPDIR_TEST/pi-model" "$TMPDIR_TEST/pi-model.log"
    spec_loop_launch_agent pi "$TMPDIR_TEST/pi-model" /repo "$TMPDIR_TEST/prompt.md" anthropic/claude-test stream-json low
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/pi-model.log" "<--mode> <json>"
    assert_contains "$TMPDIR_TEST/pi-model.log" "<--model> <anthropic/claude-test>"
    assert_contains "$TMPDIR_TEST/pi-model.log" "<--thinking> <low>"

    # Goose: `run --no-session -i <prompt file>`, no effort flag, no approval bypass.
    make_fake_agent "$TMPDIR_TEST/goose" "$TMPDIR_TEST/goose.log"
    spec_loop_launch_agent goose "$TMPDIR_TEST/goose" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/goose.log" "<run> <--no-session>"
    assert_contains "$TMPDIR_TEST/goose.log" "<-i> <$TMPDIR_TEST/prompt.md>"
    assert_not_contains "$TMPDIR_TEST/goose.log" "<--model>"
    assert_not_contains "$TMPDIR_TEST/goose.log" "<--thinking>"
    assert_not_contains "$TMPDIR_TEST/goose.log" "GOOSE_MODE"

    make_fake_agent "$TMPDIR_TEST/goose-model" "$TMPDIR_TEST/goose-model.log"
    spec_loop_launch_agent goose "$TMPDIR_TEST/goose-model" /repo "$TMPDIR_TEST/prompt.md" claude-test text low
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/goose-model.log" "<--model> <claude-test>"

    # Grok Build 1.0.50: prompt-file headless mode, explicit cwd,
    # unattended approval, remote-write denies, output mapping, model,
    # and framework effort mapping.
    make_fake_agent "$TMPDIR_TEST/grok" "$TMPDIR_TEST/grok.log"
    spec_loop_launch_agent grok "$TMPDIR_TEST/grok" /repo "$TMPDIR_TEST/prompt.md" grok-test stream-json high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/grok.log" "<--always-approve>"
    assert_contains "$TMPDIR_TEST/grok.log" "<--cwd> </repo>"
    assert_contains "$TMPDIR_TEST/grok.log" "<--deny> <Bash(git push:*)>"
    assert_contains "$TMPDIR_TEST/grok.log" "<--deny> <Bash(gh:*)>"
    assert_contains "$TMPDIR_TEST/grok.log" "<--output-format> <streaming-json>"
    assert_contains "$TMPDIR_TEST/grok.log" "<--model> <grok-test>"
    assert_contains "$TMPDIR_TEST/grok.log" "<--reasoning-effort> <high>"
    assert_contains "$TMPDIR_TEST/grok.log" "<--prompt-file> <$TMPDIR_TEST/prompt.md>"
    assert_not_contains "$TMPDIR_TEST/grok.log" "stdin:PROMPT BODY"

    # Default text output maps to Grok's plain headless format and unset
    # effort must not add a reasoning-effort flag.
    spec_loop_launch_agent grok "$TMPDIR_TEST/grok" /repo "$TMPDIR_TEST/prompt.md" "" text
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/grok.log" "<--output-format> <plain>"
    assert_not_contains "$TMPDIR_TEST/grok.log" "<--reasoning-effort>"
    assert_not_contains "$TMPDIR_TEST/grok.log" "<--model>"
}

# loop.sh validates SPEC_LOOP_EFFORT at startup (reject anything other than
# low|medium|high|empty). That gate is not exercised here — these fixtures
# only call lib.sh helpers — so keep a manual check in the PR test plan.

test_last_sync_marker_helpers() {
    local marker="$TMPDIR_TEST/.last-sync"
    spec_loop_write_last_sync_marker "$marker" "abcdef1234567890"
    assert_contains "$marker" "abcdef1234567890"

    local branch
    branch="$(spec_loop_marker_branch_name "abcdef1234567890")"
    [ "$branch" = "advance-last-sync-abcdef1" ] || fail "unexpected marker branch: $branch"
}

test_single_flight_lock_helpers() {
    local lock="$TMPDIR_TEST/lock"

    # First acquire wins and records this process as owner.
    spec_loop_lock_acquire "$lock" || fail "first acquire should succeed"
    assert_contains "$lock/owner" "$$ "

    # Second acquire against the live owner is refused with exit 1 and the
    # already_running line, and the lock is left in place.
    local out rc
    rc=0; out="$(spec_loop_lock_acquire "$lock")" || rc=$?
    [ "$rc" = 1 ] || fail "second acquire should return 1, got $rc"
    case "$out" in already_running:*) ;; *) fail "expected already_running line, got: $out" ;; esac
    case "$out" in *"pid $$ "*) ;; *) fail "already_running line should name the holder pid: $out" ;; esac
    [ -d "$lock" ] || fail "contended acquire must not remove the live lock"

    # Release removes it; a fresh acquire then succeeds.
    spec_loop_lock_release "$lock"
    [ ! -d "$lock" ] || fail "release should remove the lock"
    spec_loop_lock_acquire "$lock" || fail "acquire after release should succeed"
    spec_loop_lock_release "$lock"

    # Release by a non-owner is a no-op.
    mkdir "$lock"
    printf '%s %s now\n' "999999" "$(hostname)" > "$lock/owner"
    spec_loop_lock_release "$lock"
    [ -d "$lock" ] || fail "release must not remove a lock owned by another pid"
    rm -rf "$lock"

    # Stale lock: owner pid on this host is gone. Taken over, exit 0.
    local dead_pid
    ( : ) & dead_pid=$!; wait "$dead_pid"
    mkdir "$lock"
    printf '%s %s 2026-01-01T00:00:00Z\n' "$dead_pid" "$(hostname)" > "$lock/owner"
    spec_loop_lock_acquire "$lock" 2>"$TMPDIR_TEST/stale.err" || fail "stale lock should be taken over"
    assert_contains "$TMPDIR_TEST/stale.err" "removing stale lock"
    assert_contains "$lock/owner" "$$ "
    spec_loop_lock_release "$lock"

    # A lock held on another host is respected even when the pid is dead here.
    mkdir "$lock"
    printf '%s %s 2026-01-01T00:00:00Z\n' "$dead_pid" "some-other-host" > "$lock/owner"
    rc=0; out="$(spec_loop_lock_acquire "$lock")" || rc=$?
    [ "$rc" = 1 ] || fail "foreign-host lock should be respected, got rc=$rc"
    case "$out" in *some-other-host*) ;; *) fail "expected the foreign host in: $out" ;; esac
    rm -rf "$lock"
}

# End to end: a second loop.sh against a held lock exits 0 with the
# already_running line and never launches the agent; SPEC_LOOP_LOCK=off
# skips the lock. Needs a throwaway git repository because loop.sh refuses
# to run outside one.
test_loop_single_flight_end_to_end() {
    command -v git >/dev/null 2>&1 || { echo "skip: git not on PATH"; return 0; }
    local repo="$TMPDIR_TEST/repo"
    mkdir -p "$repo/tools/spec-loop" "$TMPDIR_TEST/bin"
    cp "$ROOT/tools/spec-loop/loop.sh" "$ROOT/tools/spec-loop/lib.sh" "$repo/tools/spec-loop/"
    cp "$ROOT"/tools/spec-loop/PROMPT_*.md "$repo/tools/spec-loop/"
    : > "$repo/tools/spec-loop/IMPLEMENTATION_PLAN.md"
    git -C "$repo" init -q -b main
    git -C "$repo" -c user.name=t -c user.email=t@example.invalid add -A
    git -C "$repo" -c user.name=t -c user.email=t@example.invalid commit -q -m init

    # A fake agent that records whether it was ever launched.
    local agent_log="$TMPDIR_TEST/agent-launched"
    printf '#!/usr/bin/env bash\necho launched >> "%s"\n' "$agent_log" > "$TMPDIR_TEST/bin/claude"
    chmod +x "$TMPDIR_TEST/bin/claude"

    # Hold the lock as a live process (this shell), then start a loop.
    local lock="$repo/tools/spec-loop/.lock"
    mkdir "$lock"
    printf '%s %s 2026-01-01T00:00:00Z\n' "$$" "$(hostname)" > "$lock/owner"

    local out rc
    rc=0; out="$(cd "$repo" && PATH="$TMPDIR_TEST/bin:$PATH" bash tools/spec-loop/loop.sh build 1 2>&1)" || rc=$?
    [ "$rc" = 0 ] || fail "loop.sh should exit 0 when already running, got $rc: $out"
    case "$out" in *already_running:*) ;; *) fail "expected already_running in loop output: $out" ;; esac
    [ ! -e "$agent_log" ] || fail "agent must not launch while another loop holds the lock"
    [ -d "$lock" ] || fail "the second loop must not remove the first loop's lock"

    # A bad argument exits 1 before touching the lock, so the holder keeps it.
    rc=0; out="$(cd "$repo" && PATH="$TMPDIR_TEST/bin:$PATH" bash tools/spec-loop/loop.sh bogus 2>&1)" || rc=$?
    [ "$rc" = 1 ] || fail "unknown argument should still exit 1, got $rc"
    [ -d "$lock" ] || fail "an early exit must not release someone else's lock"

    # SPEC_LOOP_LOCK=off: the held lock is ignored and the agent runs.
    rc=0; out="$(cd "$repo" && SPEC_LOOP_LOCK=off PATH="$TMPDIR_TEST/bin:$PATH" bash tools/spec-loop/loop.sh plan 1 2>&1)" || rc=$?
    [ "$rc" = 0 ] || fail "SPEC_LOOP_LOCK=off run should exit 0, got $rc: $out"
    case "$out" in *"Lock:   off"*) ;; *) fail "expected the lock-off banner line in: $out" ;; esac
    [ -e "$agent_log" ] || fail "agent should launch when the lock is off"
    [ -d "$lock" ] || fail "a lock-off run must leave the other loop's lock alone"
    rm -rf "$lock"

    # Normal run: the loop takes the lock and releases it on exit.
    rc=0; out="$(cd "$repo" && PATH="$TMPDIR_TEST/bin:$PATH" bash tools/spec-loop/loop.sh plan 1 2>&1)" || rc=$?
    [ "$rc" = 0 ] || fail "plan run should exit 0, got $rc: $out"
    case "$out" in *"Lock:   $lock"*) ;; *) fail "expected the lock banner line in: $out" ;; esac
    [ ! -d "$lock" ] || fail "lock should be released when the loop exits"
}

test_prompt_assembly_build
test_prompt_assembly_update
test_harness_command_construction
test_last_sync_marker_helpers
test_single_flight_lock_helpers
test_loop_single_flight_end_to_end

printf 'spec-loop runner fixtures: OK\n'
