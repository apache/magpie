<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

~~~json
{
  "runtime": "codex" | "claude" | "unknown",
  "action": "follow-codex-install" | "continue-claude-branch" | "ask-for-runtime",
  "claude_files_required": true | false,
  "stop_before_claude_branch": true | false
}
~~~

For a Codex session, route to the Codex adapter, do not require .claude
files, and stop before the Claude-specific branch. For Claude Code, continue
the existing branch. If the runtime is genuinely unknown, ask once.
