<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.3.0`, and a `plugins` list of magpie-setup and
magpie-agent-guard.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Google Gemini CLI (`GEMINI_CLI=1`). There is no
`claude` executable on PATH and no Codex session markers in the
environment. The installed Magpie extension reports version 0.2.0:
`gemini extensions list -o json` prints
`[{"name": "magpie", "version": "0.2.0"}]`.
