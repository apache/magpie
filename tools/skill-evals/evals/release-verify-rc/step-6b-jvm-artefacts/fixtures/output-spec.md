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
- `INHERITED-UNVERIFIED` results (element inherited from a parent POM
  that is not staged locally) are `"WARN"`, never `"FAIL"`: a correct
  POM that inherits from the ASF parent must not be failed.
- `pom_findings` / `companion_findings` name the exact failing artefact
  and what is wrong; an empty list means no findings for that kind.
- `paste_recipe` must be a non-empty string invoking
  `maven-artifact-verify` on the staged directory, with `--digests`
  set from `release-build.md § Digest set` and `--podling` passed only
  when the source artefact ships a `DISCLAIMER` / `DISCLAIMER-WIP`.
- No extra keys are permitted in the response.
