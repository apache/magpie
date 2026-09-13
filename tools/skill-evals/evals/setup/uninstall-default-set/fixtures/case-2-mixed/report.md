<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` at the repo root contains `method: marketplace`,
`url: apache/magpie`, `min_version: 0.3.0`, and a `plugins` list of
magpie-setup, magpie-utilities and magpie-agent-guard, in that order.

Top-level keys, in order: `permissions`, `enabledPlugins`. `enabledPlugins`
contains the three floor members plus `magpie-security@apache-magpie: true` and
`some-other-plugin@vendor-marketplace: true`.
