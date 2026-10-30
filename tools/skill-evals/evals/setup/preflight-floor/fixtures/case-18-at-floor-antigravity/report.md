<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.3.0`, and a `plugins` list of magpie-setup and
magpie-agent-guard.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Google Antigravity CLI (`ANTIGRAVITY_CONVERSATION_ID` is set). There
is no `claude` executable on PATH and no Codex session markers in the
environment. The installed Magpie plugin reports version 0.3.0:
`agy plugin list --json` prints
`[{"name": "magpie", "version": "0.3.0"}]`.

The invoking skill is already reconciled to `sha256:2edc90a1b7f3440d`.

The pre-flight command printed:

```json
{
  "verdict": "ok"
}
```
