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

    # Set-but-unsupported: Cursor/Gemini have no effort knob — omit silently.
    make_fake_agent "$TMPDIR_TEST/cursor-agent" "$TMPDIR_TEST/cursor.log"
    spec_loop_launch_agent cursor "$TMPDIR_TEST/cursor-agent" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/cursor.log" "<--print>"
    assert_contains "$TMPDIR_TEST/cursor.log" "<--force>"
    assert_contains "$TMPDIR_TEST/cursor.log" "<--trust>"
    assert_not_contains "$TMPDIR_TEST/cursor.log" "<--effort>"
    assert_not_contains "$TMPDIR_TEST/cursor.log" "<--variant>"
    assert_not_contains "$TMPDIR_TEST/cursor.log" "model_reasoning_effort"

    make_fake_agent "$TMPDIR_TEST/gemini" "$TMPDIR_TEST/gemini.log"
    spec_loop_launch_agent gemini "$TMPDIR_TEST/gemini" /repo "$TMPDIR_TEST/prompt.md" "" text high
    wait "$SPEC_LOOP_AGENT_PID"
    assert_contains "$TMPDIR_TEST/gemini.log" "<--yolo>"
    assert_contains "$TMPDIR_TEST/gemini.log" "<--prompt>"
    assert_not_contains "$TMPDIR_TEST/gemini.log" "<--effort>"
    assert_not_contains "$TMPDIR_TEST/gemini.log" "<--variant>"
    assert_not_contains "$TMPDIR_TEST/gemini.log" "model_reasoning_effort"
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

test_prompt_assembly_build
test_prompt_assembly_update
test_harness_command_construction
test_last_sync_marker_helpers

printf 'spec-loop runner fixtures: OK\n'
