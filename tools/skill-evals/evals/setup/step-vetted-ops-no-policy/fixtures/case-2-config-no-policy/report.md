<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Running: `/magpie-setup:setup config` in a repo with no `.apache-magpie-overrides/` directory.

Checking which tracker labels to offer, the agent ran `uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller security-issue-sync policy`, which exited 3 with:

`vetted-op: config error: no vetted-ops config at /work/acme/.apache-magpie-overrides/tools/vetted-ops/config.toml`

The user has not asked for a policy.
