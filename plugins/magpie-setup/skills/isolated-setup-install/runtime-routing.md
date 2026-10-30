<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Runtime routing for a harness other than Claude Code

Read from `SKILL.md` § *Runtime routing* when the selected harness is not Claude Code.

Determine the active harness from the session metadata and executable. When it
is Codex, follow the install lifecycle in
[docs/adapters/codex.md](../../../../docs/adapters/codex.md#install), including the
project profile merge, static lint, project trust, and `agent-iso codex`
steps. Do not write Claude settings or report a missing `.claude` file as a
Codex failure. After completing the Codex branch, stop; the remainder of this
skill is the Claude Code branch.

When the selected runtime is Antigravity, follow
[docs/adapters/antigravity.md](../../../../docs/adapters/antigravity.md#install): resolve the installed plugin, snapshot, or framework checkout; propose the merge of the user-scope profile into `~/.gemini/antigravity-cli/settings.json` and of the guard into `~/.gemini/config/hooks.json`; then guide the wrapper launch and verification.
The setup is per user: write nothing into the repository.
Do not require or write Claude configuration.
After completing the Antigravity branch, stop before the Claude-specific procedure below.

When the selected runtime is Pi, follow
[docs/adapters/pi.md](../../../../docs/adapters/pi.md#install): propose the one per-user package install, which brings the skills, the guard, the permission rules and the bash sandbox together; then guide the wrapper launch and verification.
The setup is per user: never install the package with `-l` and write nothing into the repository.
Do not require or write Claude configuration.
After completing the Pi branch, stop before the Claude-specific procedure below.

When the selected runtime is Goose, follow
[docs/adapters/goose.md](../../../../docs/adapters/goose.md#install): propose the per-user plugin install, which brings the skills and the guard hook, and the `npm ci` of the locked sandbox runtime into the plugin; then guide the `agent-iso goose` launch, which runs Goose in the sandbox in approve mode, and verification.
The setup is per user: install nothing into a project's `.agents/plugins/` and write nothing into the repository.
Do not require or write Claude configuration.
After completing the Goose branch, stop before the Claude-specific procedure below.

When the selected runtime is Copilot CLI, follow [docs/adapters/copilot.md](../../../../docs/adapters/copilot.md#install): register the guard hook, detect and declare mail sources from the MCP servers already present, and ask nothing beyond the single apply confirmation (PRINCIPLES.md §1, *Avoiding prompt fatigue*). Do not require or write Claude configuration.
After completing the Copilot branch, stop before the Claude-specific procedure below.
