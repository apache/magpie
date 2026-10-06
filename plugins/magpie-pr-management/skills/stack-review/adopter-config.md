<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Adopter overrides

Before running the default behaviour documented in `SKILL.md`, this skill consults
`pr-management-stack-review.md` in the personal layer
(`.apache-magpie-local/` when the project adopted Magpie, falling back to the main checkout's in a linked worktree,
or `<git-common-dir>/apache-magpie/` when Magpie is only installed; applied first, wins on conflict) and
[`.apache-magpie-overrides/pr-management-stack-review.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo, if present, and applies any agent-readable overrides it finds.
See [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md) for the contract.

Knobs an override may set, each with the framework default:

| Knob | Default | Used by |
|---|---|---|
| generated-file globs | `stack_ledger.py` built-ins plus `.gitattributes` `linguist-generated` | `--generated-globs` |
| release-note globs | `**/newsfragments/*`, `CHANGELOG*`, `changelog.rst`, `RELEASE_NOTES*` | duplicate detector |
| lock ↔ manifest pairs | `uv.lock`, `poetry.lock`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock` with their manifests | co-location detector |
| read budget | 4000 changed lines | Step 4 |
| residue tokens | taken from the PR bodies | Step 3 residue check |

**Hard rule**: agents NEVER modify the snapshot under `<adopter-repo>/.apache-magpie/`.
Local modifications go in the override file; framework changes go via PR to `apache/magpie`.

---

## Adopter configuration

This skill resolves project-specific content from the adopter's `<project-config>/` directory:

- [`<project-config>/project.md`](../../../magpie-setup/templates/project.md) — `upstream_repo`, `upstream_default_branch`, and `upstream_contributing_docs_url` for the footer.
- [`<project-config>/pr-management-code-review-criteria.md`](../../../magpie-setup/templates/pr-management-code-review-criteria.md) — the review-criteria source files quoted when a Step 4 note is a rule violation; the same file `pr-management-code-review` reads.

No project value is baked into the skill.
