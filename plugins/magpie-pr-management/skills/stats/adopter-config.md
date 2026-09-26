<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Adopter overrides

Before running the default behaviour documented
below, this skill consults
[`.apache-magpie-local/pr-management-stats.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/pr-management-stats.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
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

## Snapshot drift

Also at the top of every run, this skill compares the
gitignored `.apache-magpie.local.lock` (per-machine
fetch) against the committed `.apache-magpie.lock`
(the project pin). On mismatch the skill surfaces the
gap and proposes
[`setup upgrade`](../../../magpie-setup/skills/setup/upgrade.md).
The proposal is non-blocking — the user may defer if
they want to run with the local snapshot for now. See
[`docs/setup/install-recipes.md` § Subsequent runs and drift detection](../../../../docs/quick-start/other-install-methods.md#subsequent-runs-and-drift-detection)
for the full flow.

Drift severity:

- **method or URL differ** → ✗ full re-install needed.
- **ref differs** (project bumped tag, or `git-branch`
  local is behind upstream tip) → ⚠ sync needed.
- **`svn-zip` SHA-512 mismatches the committed
  anchor** → ✗ security-flagged; investigate before
  upgrading.

---
## Adopter configuration

This skill reads the same area-label prefix and triage-marker
string declared in [`pr-management-triage`'s adopter config](../pr-triage/SKILL.md#adopter-configuration):

- [`<project-config>/pr-management-config.md → area_label_prefix`](../../../../projects/_template/pr-management-config.md) — drives the area grouping in both stats tables.
- [`<project-config>/pr-management-triage-comment-templates.md → Triage-marker visible link text`](../../../../projects/_template/pr-management-triage-comment-templates.md) — the literal string that classifies a PR as triaged. **Both `pr-management-triage` and `pr-management-stats` must agree** on this string; the framework defaults to `Pull Request quality criteria`.

No `pr-management-stats`-specific config file is needed — the skill is
read-only and inherits everything from `pr-management-triage`'s contract.

---
