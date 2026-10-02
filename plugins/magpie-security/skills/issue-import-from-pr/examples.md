<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr — examples

## Examples

### Example 1 — `<scope-b>` scope, already merged

```text
import from pr 65703
```

PR `<upstream>#65703` (*Prevent unauthorized access to
team-scoped secrets in SM and SSM*), state `MERGED`, author
`justinpakzad`. Files: 6 paths under
`<scope-b>/<name>/.../secrets/`. Scope detection: `<scope-b>`
(sub-package `<name>`). Milestone: next release-train wave (the PR
itself has no milestone). Labels: `<scope-b>`, `pr merged`,
`security issue`. Board column: `Assessed`. *Affected versions*:
`<product>-<component> < NEXT VERSION`. *Remediation
developer*: `Justin Pakzad` (PR commit attributes the change
publicly). *Reporter credited as*: blank — public-PR imports do
not credit the PR author as the CVE reporter (no responsible
disclosure; see *[Reporter credit policy](SKILL.md#reporter-credit-policy-for-public-pr-imports)*).

### Example 2 — `<scope-a>` scope, in-flight

```text
import from pr https://github.com/<upstream>/pull/65999
```

PR state `OPEN`, milestone `X.Y.Z` (the project's core release
train). Files all under
`<scope-a>/src/.../api_fastapi/`. Scope: `<scope-a>`.
Milestone: `X.Y.Z`. Labels: `<scope-a>`, `pr created`,
`security issue`. *Affected versions*: `< X.Y.Z`. The skill
proposes everything; on user confirmation, the tracker lands
`Assessed`, ready for `security-cve-allocate`.

### Example 3 — Mixed-scope PR (blocker)

```text
import from pr 66042
```

PR touches `<scope-a>/src/.../serialization.py` **and**
`<scope-b>/<name>/src/.../python_operator.py`. The skill
**stops** and surfaces:

> PR 66042 changes files across `<scope-a>` and `<scope-b>`
> scopes. Split the report into two trackers (one per scope)
> manually, or re-confirm which scope the CVE should be
> allocated against.
