<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Quality signals to check

Read the source section the adopter's `Section anchors` table links for this category (`section_anchors` in the `context` output) and quote the rule **verbatim** in the finding — never paraphrase. If the category has no anchor row, use a plain reference and surface the missing anchor once at the top of the review.

`code-review context` lists every added compiled artifact as a `major` candidate. Escalate one to `blocking` only when the file would ship in a release archive: re-run `context` with `--in-release <path>` for each you confirmed, so the finding text matches.

## Compiled artifacts

ASF releases must be source-only. Compiled or binary build artifacts added to
the repository risk ending up in a release, violating the ASF Release Policy
(`https://www.apache.org/legal/release-policy.html`).

When the diff adds any of the following file types, raise a `major` finding:

- **JVM**: `.class`, `.jar` (non-empty), `.war`, `.ear`
- **Python**: `.pyc`, `.pyo`, `.pyd`
- **Native**: `.so`, `.dll`, `.dylib`, `.exe`, `.o`, `.a`
- **Packages**: `.whl`, `.egg`

The finding is `major` with the text: *"Compiled artifacts must not be
committed to the source tree — ASF releases are source-only. Remove this
file and ensure it is generated at build time."* If the file would be
included in a release archive, escalate to `blocking`.

---
