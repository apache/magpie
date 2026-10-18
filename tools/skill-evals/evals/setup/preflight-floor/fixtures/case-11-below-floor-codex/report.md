<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.3.0`, and a `plugins` list of magpie-setup and
magpie-agent-guard.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is OpenAI Codex CLI (`CODEX_SANDBOX=1`). There is no
`claude` executable on PATH and no Gemini session markers in the
environment. `codex plugin list --json` reports magpie-setup 0.2.0 and
magpie-agent-guard 0.2.0, both from the `apache-magpie` marketplace.
