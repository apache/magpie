<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# License headers

Read the source section the adopter's `Section anchors` table links for this category (`section_anchors` in the `context` output) and quote the rule **verbatim** in the finding — never paraphrase. If the category has no anchor row, use a plain reference and surface the missing anchor once at the top of the review.

`code-review context` already applied the mechanical rules (`candidate_findings` with `finding_category: License headers`): deference to header tooling present in the rollup, the missing-header fallback when none is, the exclusion-masking case, overly broad exclusion patterns, and a mis-applied SPDX identifier on a contributor-authored file. What is left to judge: whether an exclusion is legitimately exempt (generated code, fixtures, an attributed third-party file) and the borderline exemptions — when unsure, defer.

ASF policy requires every source file in a release to carry the
standard Apache license header
(`https://www.apache.org/legal/src-headers.html`). This is a
**framework-level default** that applies regardless of
adopter-specific rules.

**Defer to the project's header tooling when it exists.** Many ASF
projects enforce headers in CI — `apache-rat`, the pre-commit
`insert-license` hook, `license-eye` / `skywalking-eyes`, or an
equivalent. If such a check appears in the PR's status-check
rollup (the [CI precheck](../prerequisites.md) already reads it):

- That tool is **authoritative for the mechanical question** —
  "does this file carry the header" — including which paths are
  in scope. Do **not** raise a duplicate "missing header"
  finding: a real miss already turns the check red, and Golden
  rule 8 already takes `APPROVE` off the table and quotes the
  failing check. Restating it as a review finding is noise and
  risks contradicting the tool's own exclusion list.
- The source of truth for **scope and exemptions** is the
  project's tool config (the `apache-rat` `<excludes>` block,
  `.rat-excludes`, the pre-commit `exclude:` regex, the
  `licenserc.yaml` ignore globs — whatever the project uses),
  **not** the policy page. When reasoning about whether a file
  is in scope, read that config, not a summarised list here.

**Fallback — projects with no header tooling.** If no
license-header check appears in the rollup, the skill **is** the
safety net. Scan every source file the diff **adds** (and any it
materially rewrites) for the Apache header; raise a `major`
finding for each contributor-authored file missing it, quoting
`https://www.apache.org/legal/src-headers.html`. Apply the
exemptions listed in the *Exemptions* paragraph at the end of
this section using judgement, and the *When in doubt — defer*
rule at the end of this file for anything borderline.

**The exclusion-masking case — check even when CI is green.**
Deference above assumes the tool's exclusion list is fixed. It is
not when the **PR itself changes it**. If the same diff both
(a) adds or modifies a header-tool exclusion entry — an
`<exclude>` in `pom.xml` / `build.gradle`, a line in
`.rat-excludes`, an `exclude:` pattern in
`.pre-commit-config.yaml`, an ignore glob in `licenserc.yaml`,
etc. — and (b) adds a file that lacks an Apache header or carries
a third-party header, then the check passes **green by
construction** and CI deference gives no coverage. This is
precisely where the skill earns its place. Raise a `major`
finding asking the maintainer to confirm the exclusion is
appropriate:

- **Legitimately exempt** — generated code, data/test fixtures,
  binary assets, or a genuinely third-party file correctly
  attributed in `LICENSE` (route the third-party part to
  [§ Third-party license compliance](third-party-license-compliance.md)).
  If so, the exclusion is fine; note it and move on.
- **Masking a missing header** — a contributor-authored source
  file that simply has no header and was excluded to make CI
  pass. Not acceptable; the fix is to add the header, not to
  exclude the file.
- **Overly broad exclusion pattern** — even if the files added
  in this PR carry correct headers, a glob wider than necessary
  (e.g. `src/**`, `*.java`, a whole subtree containing
  contributor-authored source) silently degrades the tool for
  all future PRs. Raise a `minor` finding asking the maintainer
  to scope the pattern to the specific file or directory it is
  meant to cover.

Quote the added exclusion line and the offending file path in the
finding so the maintainer can adjudicate without digging.

**Judgement cases the tool cannot decide.** Even on a
fully-tooled project, raise a finding for:

- a contributor-authored file with a **mis-applied SPDX
  identifier** or the **wrong license** in an otherwise
  Apache-intended header (the tool sees *a* header and passes;
  the header is still wrong);
- a header that is **clearly third-party / upstream** — do not
  treat as a missing-header miss; route to
  [§ Third-party license compliance](third-party-license-compliance.md)
  (the fix there is preserve-and-attribute, not replace).

**Exemptions (no finding).** Generated files; vendored or
third-party files (handled by the third-party category); data and
test-resource fixtures; binary files; trivially short config/data
files where the project conventionally omits headers; files in
formats that do not support comments and therefore cannot carry a
header (e.g. JSON, CSV, most binary data formats); documentation
and plain-text files (`.md`, `.rst`, `.txt`) where ASF projects
are conventionally lenient; `README` files (in any format);
`LICENSE`, `NOTICE`, `DISCLAIMER`, and similar legal declaration
files that are themselves the licence artefact. On a tooled
project the project config is the authority for these; on an
untooled project use judgement and defer when unsure.

| Situation | Severity |
|---|---|
| Missing header, no header tooling in CI | `major` |
| Missing / 3rd-party header + new tool exclusion in same PR | `major` (confirm exclusion is justified) |
| New exclusion pattern is overly broad | `minor` |
| Wrong / mis-applied SPDX on contributor-authored file | `major` |
| Missing header but header tooling is red on the PR | no separate finding — defer to CI (Golden rule 8) |
| Header tooling present, CI green, no exclusion change in this PR | no finding — defer to tooling |
| Header added in this PR alongside the file | no finding |

Source: `https://www.apache.org/legal/src-headers.html` (policy)
and the project's own header-tool configuration (scope and
exemptions).

---
