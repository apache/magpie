<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains `method: marketplace`,
`url: apache/magpie`, `min_version: 0.3.0`, and a `plugins` list of
magpie-setup, magpie-utilities, magpie-agent-guard and magpie-vetted-ops, in that
order.

`.claude/settings.json` commits `enabledPlugins` with
`magpie-setup@apache-magpie`, `magpie-utilities@apache-magpie`,
`magpie-agent-guard@apache-magpie`, `magpie-vetted-ops@apache-magpie` and
`magpie-security@apache-magpie`, all
`true`.
