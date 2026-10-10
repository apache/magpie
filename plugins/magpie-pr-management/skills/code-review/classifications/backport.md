<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Backport base branch

[`code-review`](../../../../../tools/pr-management/README.md#code-review--pr-management-code-review) `context` matched the PR's base against the backport pattern in `<project-config>/pr-management-code-review-criteria.md`. Note the base in the headline.

If the adopter's
`<project-config>/pr-management-code-review-criteria.md` declares
a backport branch pattern (see its `Backports / version-specific
PRs` table), PRs whose base branch matches the pattern are
treated as backports of already-merged `main` work and get a
lighter-touch calibration:

- **Diff parity**: does this match what was merged on `main`?
- **Cherry-pick conflicts**: did the resolution introduce new
  changes that need scrutiny?
- **API/migration version markers**: backports should not
  introduce new version bumps in any
  versioning-sensitive subsystem the adopter calls out; if they
  do, cite the relevant `API correctness` anchor from the
  adopter's `Section anchors` table.

For these PRs, prefer `COMMENT` over `REQUEST_CHANGES` unless
the cherry-pick has clearly drifted from the `main` change.

If the adopter config has no backport pattern declared, this
section is a no-op and every PR is reviewed under the same
calibration.

---
