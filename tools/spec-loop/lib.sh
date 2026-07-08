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
    local model_args=()
    [ -n "$model" ] && model_args=(--model "$model")

    if [ "$harness" = "opencode" ]; then
        local oc_format_args=()
        [ "$output_format" = "stream-json" ] && oc_format_args=(--format json)
        "$agent" run \
            --auto \
            ${model_args[@]+"${model_args[@]}"} \
            ${oc_format_args[@]+"${oc_format_args[@]}"} \
            "$(cat "$prompt_file")" &
    elif [ "$harness" = "codex" ]; then
        local codex_format_args=()
        [ "$output_format" = "stream-json" ] && codex_format_args=(--json)
        "$agent" exec \
            --dangerously-bypass-approvals-and-sandbox \
            --cd "$root" \
            ${model_args[@]+"${model_args[@]}"} \
            ${codex_format_args[@]+"${codex_format_args[@]}"} \
            - < "$prompt_file" &
    elif [ "$harness" = "cursor" ]; then
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
    elif [ "$harness" = "gemini" ]; then
        "$agent" \
            --yolo \
            ${model_args[@]+"${model_args[@]}"} \
            --prompt "$(cat "$prompt_file")" &
    elif [ "$harness" = "kiro" ]; then
        # Kiro CLI headless: positional prompt to `kiro-cli chat --no-interactive`.
        # The model is selected by the chosen agent config (.kiro/agents), not a
        # per-invocation flag, and Kiro has no stream-json output mode here.
        "$agent" chat --no-interactive \
            "$(cat "$prompt_file")" &
    else
        local verbose_args=()
        [ "$output_format" = "stream-json" ] && verbose_args=(--verbose)
        "$agent" -p \
            --dangerously-skip-permissions \
            --disallowedTools "Bash(git push:*)" "Bash(gh:*)" \
            --output-format="$output_format" \
            ${verbose_args[@]+"${verbose_args[@]}"} \
            ${model_args[@]+"${model_args[@]}"} < "$prompt_file" &
    fi
    SPEC_LOOP_AGENT_PID=$!
}
