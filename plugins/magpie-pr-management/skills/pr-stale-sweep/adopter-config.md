<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Adopter overrides

Before running the default behaviour documented below, this skill
consults
[`.apache-magpie-local/pr-stale-sweep.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/pr-stale-sweep.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo if it exists, and applies any agent-readable
overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)
for the contract.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-magpie/`. Local modifications go in the override
file. Framework changes go via PR to `apache/magpie`.

---

## Snapshot drift

At the top of every run, this skill compares the gitignored
`.apache-magpie.local.lock` (per-machine fetch) against the committed
`.apache-magpie.lock` (the project pin). On mismatch the skill surfaces
the gap and proposes
[`setup upgrade`](../../../magpie-setup/skills/setup/upgrade.md). The proposal is non-blocking
— the user may defer if they want to run with the local snapshot for now.

---

## Prerequisites

- **GitHub read access** to `<upstream>` for the sweep phase. The `gh`
  CLI must be authenticated. See
  [`<project-config>/project.md`](../../../../projects/_template/project.md).
- **GitHub write access** for the apply phase. The skill surfaces an
  auth error and stops before any apply if write credentials are missing.
- **`<project-config>/project.md`** populated — the skill reads
  `upstream_repo` and `upstream_default_branch`.
- **`<project-config>/pr-management-config.md`** populated — the skill
  reads `ready_for_maintainer_review_label` and `committers_team`.

See
[Prerequisites for running the agent skills](../../../../docs/quick-start/prerequisites.md#prerequisites-for-running-the-agent-skills)
in `docs/prerequisites.md` for the overall setup.

---
