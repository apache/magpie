<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Runtime routing for a harness other than Claude Code

Read from `SKILL.md` § *Runtime routing* when the selected harness is not Claude Code.

When the active harness is Codex, first require the static verification in [docs/adapters/harnesses/codex.md](../../../../docs/adapters/harnesses/codex.md#verify), then run the shared live environment probes inside the active Codex sandbox.
Attribute failures separately to native sandbox/network denial, approval policy, or the POSIX agent-iso layer.
Do not prescribe a `.claude` settings change for a Codex failure.
Then stop before the Claude-specific branch below.

When the selected runtime is Antigravity, follow
[docs/adapters/harnesses/antigravity.md](../../../../docs/adapters/harnesses/antigravity.md#doctor): verify the user-scope profile first, then diagnose the actual tool result in the active Antigravity session.
Distinguish sandbox limits, permission-rule denials, guard-hook failures, and wrapper or authentication problems.
Do not require Claude configuration or prescribe Claude settings changes; then stop before the Claude-specific probes below.

When the selected runtime is Goose, follow
[docs/adapters/harnesses/goose.md](../../../../docs/adapters/harnesses/goose.md#doctor): verify the plugin, its sandbox runtime and the launcher first, then diagnose the actual tool result in the active Goose session.
Distinguish sandbox limits or a missing sandbox runtime, hook denials (deny rules or the guard), a hook that failed closed, approve-mode declines, and wrapper or provider-key problems.
Do not require Claude configuration or prescribe Claude settings changes; then stop before the Claude-specific probes below.

When the selected runtime is Pi, follow
[docs/adapters/harnesses/pi.md](../../../../docs/adapters/harnesses/pi.md#doctor): verify the package install first, then diagnose the actual tool result in the active Pi session.
Distinguish sandbox limits or a sandbox that could not start, permission-rule denials, guard denials, and wrapper or authentication problems.
Do not require Claude configuration or prescribe Claude settings changes; then stop before the Claude-specific probes below.

When the selected runtime is Copilot CLI, follow [docs/adapters/harnesses/copilot.md](../../../../docs/adapters/harnesses/copilot.md#doctor): verify the hook first, then diagnose the actual tool result in the live session.
