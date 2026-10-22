<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Running: `/magpie-setup:setup install` (marketplace, Claude Code), in a repo that has installed Magpie but not adopted it.

While wiring the secure setup, the agent ran:

`uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage viewer`

It exited 3 with:

`vetted-op: config error: no vetted-ops config at /work/acme/.apache-magpie-overrides/tools/vetted-ops/config.toml`

Two install steps remain.
