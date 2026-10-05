<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Before running its default behaviour, this skill consults
[`.apache-magpie-local/{override_name}.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored; applied first, wins on conflict) and
[`.apache-magpie-overrides/{override_name}.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo, if present, and applies any agent-readable overrides it finds.
See [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md) for the contract.

**Hard rule**: agents NEVER modify the snapshot under `<adopter-repo>/.apache-magpie/`.
Local modifications go in the override file; framework changes go via PR to `apache/magpie`.
