<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Running: `/magpie-pr-management:pr-triage` (not a setup run), in a repo that has installed Magpie but not adopted it.

The first sweep read, `uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller pr-management-triage viewer`, exited 3 with:

`vetted-op: config error: no vetted-ops config at /work/acme/.apache-magpie-overrides/tools/vetted-ops/config.toml`
