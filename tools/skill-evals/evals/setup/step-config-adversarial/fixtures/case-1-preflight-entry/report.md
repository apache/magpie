<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Entry: `magpie-pr-management-code-review`'s pre-flight found `reviewer-routing.md`
missing and started `setup config` for that one skill.

The `magpie-adversarial-review` plugin is installed. No `adversarial-review.md`
resolves.

`adversarial-review detect` printed:

```json
{"self": "claude", "backends": [
  {"name": "codex", "path": "/opt/homebrew/bin/codex", "version": "codex-cli 0.154.0", "available": true, "is_self": false, "reason": ""},
  {"name": "copilot", "path": "/opt/homebrew/bin/copilot", "version": "0.0.361", "available": true, "is_self": false, "reason": ""},
  {"name": "gemini", "path": null, "version": null, "available": false, "is_self": false, "reason": "not on PATH"},
  {"name": "claude", "path": "/usr/local/bin/claude", "version": "2.1.0 (Claude Code)", "available": true, "is_self": true, "reason": ""}
]}
```
