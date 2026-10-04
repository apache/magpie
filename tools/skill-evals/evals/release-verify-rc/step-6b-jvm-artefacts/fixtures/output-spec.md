<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 6b output specification

The model must return ONLY valid JSON matching this schema:

```json
{
  "step": "jvm-artefacts",
  "status": "PASS" | "WARN" | "FAIL" | "SKIP",
  "tool_report": "<the maven-artifact-verify JSON report verbatim>",
  "pom_findings": ["<one line per POM finding>"],
  "companion_findings": ["<one line per jar finding>"],
  "observations": ["<one line per informational observation>"],
  "paste_recipe": "<multi-line shell commands>"
}
```

Grading rules:
- `status` is the tool report's `status`, except that an `ABSENT` jar
  becomes `"FAIL"` when `release-build.md § JVM artefact checks`
  declares `jvm_companion_location: staged`.
- A `FAIL` in the tool report (wrong POM licence, missing companion,
  missing companion `.asc` / checksum) is a hard `"FAIL"` — never a
  warning.
- `INHERITED-UNVERIFIED` results (the parent chain is not fully staged
  locally, so the element cannot be resolved offline) are `"WARN"`,
  never `"FAIL"`: a correct POM that inherits from the ASF parent must
  not be failed.
- `pom_findings` / `companion_findings` name the exact failing artefact
  and what is wrong; an empty list means no findings for that kind.
- `observations` carries the tool's informational observations
  (checks 5–7 of issue #1173), one line each naming the jar and what
  was observed. They never change `status`: an inconsistent-timestamp
  jar, a groupId outside `org.apache.*`, a `-sources.jar` containing
  `.class` files and a placeholder companion all leave the blocking
  verdict untouched. The wording must not assert reproducibility
  either way — "consistent / not consistent with a reproducible
  configuration" — and an empty or single-entry jar is
  `INSUFFICIENT-DATA`, never a pass. A placeholder companion is
  reported as the Maven-Central-sanctioned pattern it is, never a
  defect.
- `paste_recipe` must be a non-empty string invoking
  `maven-artifact-verify` on the staged directory, with `--digests`
  set from `jvm_digest_set` when `release-build.md § JVM artefact
  checks` sets it, otherwise from the § Digest set, and `--podling`
  passed only when the source artefact ships a `DISCLAIMER` /
  `DISCLAIMER-WIP`.
- No extra keys are permitted in the response.
