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
