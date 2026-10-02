<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Adopter overrides

Before running the default behaviour documented
below, this skill consults
[`.apache-magpie-local/pr-management-code-review.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/pr-management-code-review.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo if it exists, and applies any
agent-readable overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)
for the contract — what overrides may contain, hard
rules, the reconciliation flow on framework upgrade,
upstreaming guidance.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-magpie/`. Local modifications
go in the override file. Framework changes go via PR
to `apache/magpie`.

---

## Adopter configuration

This skill resolves project-specific content from the adopter's
`<project-config>/` directory:

- [`<project-config>/pr-management-code-review-criteria.md`](../../../magpie-setup/templates/pr-management-code-review-criteria.md) — list of the project's review-criteria source files (repo-wide AGENTS.md, code-review docs, per-area AGENTS.md), security-model calibration doc, backport-branch pattern, and section-anchor URLs the framework links per finding.

The skill reads all project-specific content (source-file paths,
security-model doc, backport-branch pattern, section anchors)
from the file listed above.  No defaults are baked into the
framework.
