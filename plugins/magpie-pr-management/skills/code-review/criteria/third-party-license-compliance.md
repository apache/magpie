<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Third-party license compliance

Read the source section the adopter's `Section anchors` table links for this category (`section_anchors` in the `context` output) and quote the rule **verbatim** in the finding — never paraphrase. If the category has no anchor row, use a plain reference and surface the missing anchor once at the top of the review.

`code-review context` already classified every added file whose header is third-party (`candidate_findings` with a `licence` and `category`): Category X and B are `blocking`, Category A is `major` unless the same PR updates `LICENSE` / `LICENSE.txt` — a `licenses/` directory entry alone is not enough. Post those findings as computed; the judgement left is whether a header the tool did not recognise is third-party.

When the diff adds or modifies a file that contains a non-Apache licence
header (`SPDX-License-Identifier:` value other than `Apache-2.0`, or a
recognised licence block — MIT, BSD, GPL, LGPL, CDDL, MPL, EPL, etc.) or a
third-party copyright line (`Copyright (c) <non-ASF entity>`), classify the
licence against the ASF `resolved_licenses` policy
(`https://www.apache.org/legal/resolved.html`) and apply the following
severity rules:

| Category | Licences (examples) | Severity |
|---|---|---|
| X | GPL, AGPL, LGPL, CDDL, BUSL, SSPL | `blocking` — cannot be included in an ASF release in any form |
| B | MPL, EPL | `blocking` — cannot be included in source form; binary-only inclusion requires explicit justification |
| A | MIT, BSD-2, BSD-3, ISC, Apache 2.0 (other orgs) | `major` if `LICENSE` / `LICENSE.txt` was **not** also updated in this PR — attribution is required before shipping |
| A + LICENSE updated | any Category A | ✅ no finding |

For Category A findings, check whether the same PR modifies `LICENSE`
or `LICENSE.txt` to add an attribution notice for the bundled component.
If it does, the inclusion is correctly attributed and no finding is raised.
Some projects also keep a `licenses/` directory containing the full licence
text of each bundled component — this is a common and good practice, but it
is not required and does not affect the finding: the determining factor is
whether `LICENSE` / `LICENSE.txt` was updated, not whether a `licenses/`
entry exists.

**Relationship to "License headers":** when a new file's header is non-Apache
but not third-party (e.g. a contributor accidentally used the wrong SPDX
identifier), the "License headers" finding applies (see
[§ License headers](license-headers.md) below). When the header is
clearly from an upstream library or external author, route to this category
instead — the fix is to preserve the original header and update `LICENSE`,
not to replace it with an Apache header.

Source: `https://www.apache.org/legal/resolved.html` and
`https://www.apache.org/legal/apply-license.html`.

---
