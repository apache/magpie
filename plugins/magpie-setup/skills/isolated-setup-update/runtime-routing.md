<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Runtime routing for a harness other than Claude Code

Read from `SKILL.md` § *Runtime routing* when the selected harness is not Claude Code.

When the active harness is Codex, compare the installed `.codex` policy with the framework sources described in [docs/adapters/codex.md](../../../../docs/adapters/codex.md#setup-isolated-lifecycle).
Surface policy, rules, and tested-version drift; never auto-weaken or silently overwrite a hand-edited policy.
Then stop.
The remainder of this skill is the Claude Code update branch.

When the selected runtime is Antigravity, follow [docs/adapters/antigravity.md](../../../../docs/adapters/antigravity.md#update): compare the user-scope profile, guard path, wrapper, and runtime version with the framework's shipped profile.
Report drift and proposed changes only; do not apply changes or require Claude configuration.
Then stop before the Claude-specific drift report below.

When the selected runtime is Pi, follow [docs/adapters/pi.md](../../../../docs/adapters/pi.md#update): compare the installed framework package's ref, the Pi version and the wrapper with the framework's current ones.
Report drift and the `pi update --extensions` refresh only; do not apply changes or require Claude configuration.
Then stop before the Claude-specific drift report below.

When the selected runtime is Goose, follow [docs/adapters/goose.md](../../../../docs/adapters/goose.md#update): compare the installed plugin's ref, the sandbox runtime under it, the Goose version and the wrapper with the framework's current ones.
Report drift and the `goose plugin update magpie` plus `npm ci` refresh only; do not apply changes or require Claude configuration.
Then stop before the Claude-specific drift report below.

When the selected runtime is Copilot CLI, follow [docs/adapters/copilot.md](../../../../docs/adapters/copilot.md#update): report hook drift against the framework copy; never loosen policy automatically.
