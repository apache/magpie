<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Runtime routing for a harness other than Claude Code

Read from `SKILL.md` § *Runtime routing* when the selected harness is not Claude Code.

When the active harness is Codex, follow the full verification contract in [docs/adapters/codex.md](../../../../docs/adapters/codex.md#verify), including its hook-trust, vetted-operation and isolation-gap checks.
Report every Codex check and then stop.
Do not interpret the Claude settings checks below as Codex requirements.

When the selected runtime is Antigravity, follow
[docs/adapters/antigravity.md](../../../../docs/adapters/antigravity.md#verify): check the user-scope profile, guard registration, skill discovery, and actual runtime behavior.
Report static and live checks separately, including any checks not run and the documented isolation limits.
Do not require Claude configuration; then stop before the Claude-specific checks below.

When the selected runtime is Goose, follow
[docs/adapters/goose.md](../../../../docs/adapters/goose.md#verify): check that the plugin is installed for the user with its hook and sandbox runtime, that `agent-iso goose` launches it sandboxed in approve mode, and the actual runtime behavior of the guard, the deny rules and the sandbox.
Report static and live checks separately, including any checks not run and the documented limits.
Do not require Claude configuration; then stop before the Claude-specific checks below.

When the selected runtime is Pi, follow
[docs/adapters/pi.md](../../../../docs/adapters/pi.md#verify): check that the framework package is installed for the user (not per project), that the Magpie extension loads, and the actual runtime behavior of the guard, the rules and the bash sandbox.
Report static and live checks separately, including any checks not run and the documented limits.
Do not require Claude configuration; then stop before the Claude-specific checks below.

When the selected runtime is Copilot CLI, follow [docs/adapters/copilot.md](../../../../docs/adapters/copilot.md#verify): check the hook registration and probe an allow, a deny and a silent write.
