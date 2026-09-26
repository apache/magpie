<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Adopter overrides

Before running the default behaviour, this skill consults
[`.apache-magpie-local/pr-management-quick-merge.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/pr-management-quick-merge.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo if it exists, and applies any agent-readable overrides it
finds. **Hard rule**: agents never modify the snapshot under
`<adopter-repo>/.apache-magpie/`. Local modifications go in the override file;
framework changes go via PR to `apache/magpie`.

---

## Snapshot drift

At the top of every run, compare the gitignored `.apache-magpie.local.lock`
against the committed `.apache-magpie.lock`. On mismatch, surface the gap and
propose [`setup upgrade`](../../../magpie-setup/skills/setup/upgrade.md). Non-blocking —
the maintainer may defer.
