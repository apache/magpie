<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains `method: marketplace`,
`url: apache/magpie`, `min_version: 0.3.0`, and a `plugins` list of
magpie-setup, magpie-utilities, magpie-agent-guard, magpie-vetted-ops and
magpie-pr-management, in that order — this project's maintainers enlarged the floor when they
adopted.

`.claude/settings.json` commits `enabledPlugins` with
`magpie-setup@apache-magpie`, `magpie-utilities@apache-magpie`,
`magpie-agent-guard@apache-magpie` and `magpie-vetted-ops@apache-magpie`, all
`true`.
