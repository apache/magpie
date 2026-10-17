<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 6b — JVM artefact checks (when the RC stages jars)

**When it runs.** Only when the Step 1 listing contains at least one `.jar` or `.pom`,
and only when `release-build.md § JVM artefact checks` does not declare `jvm_artefact_checks: off` (absent or `on` means run).
A non-JVM project's RC, or a project that has turned the checks off, skips this step cleanly —
state the skip explicitly, do not silently pass.

Step 6 treats a `.jar` as contraband inside the **source** artefact.
The jars downstream consumers actually resolve are a separate surface:
the published `.pom` files, the main jars, and their companion `-sources.jar` / `-javadoc.jar`.
This step validates that surface with the
[`maven-artifact-verify`](../../../../tools/maven-artifact-verify/README.md) tool —
blocking checks 1–3 of [issue #1173](https://github.com/apache/magpie/issues/1173),
which implement [ASF Incubator distribution policy § Maven distribution](https://incubator.apache.org/guides/distribution.html)
and [Maven Central's publishing requirements](https://central.sonatype.org/publish/requirements/):

1. **POM licence entry** — every `.pom` declares ALv2, `<developers>` and `<scm>`, resolved through the locally staged parent chain.
   An element no staged ancestor declares is a `FAIL`;
   `INHERITED-UNVERIFIED` — a warning naming what to verify — is reserved for a chain that cannot be fully resolved offline,
   and never fails a correct POM that inherits from the ASF parent.
2. **Incubator disclaimer in `<description>`** — podlings only (`--podling`); the standard text and the `DISCLAIMER-WIP` variant both pass.
3. **Companion jars** — for every main jar staged locally, `-sources.jar` and `-javadoc.jar` exist,
   each with its own `.asc` and checksums verified against the jar's bytes.
   Offline the tool checks `.asc` presence only, so the recipe adds one `gpg --verify` per companion whose `.asc` is staged (same `KEYS` flow as Step 2).
   A main jar declared by a staged POM but not staged locally is `ABSENT`: an observation, because the ASF workflow stages jars in Nexus (Step 6c, [`nexus-staging.md`](nexus-staging.md)) —
   except under `jvm_companion_location: staged`, where it is a `FAIL`.

The same run reports **informational observations** — checks 5–7 of the issue: the timestamp signal, the namespace and package/groupId correspondence, and companion content.
They are signals for the reviewer and never change the step's verdict.
They are worded "consistent / not consistent with a reproducible configuration", never "reproducible" (only Step 9 can assert that);
a groupId outside `org.apache.*` stays informational even for ASF projects (published coordinates cannot be renamed);
a placeholder companion is the Maven-Central-sanctioned pattern, never a defect; an empty or single-entry jar is `insufficient-data`, and an unopenable one `unreadable`.

**Run.** The gate, the recipe and the classification are one command
(`<verify-rc>` as in SKILL.md; `<inventory.json>` is Step 1's saved JSON):

```bash
<verify-rc> jvm --inventory <inventory.json> --staged-dir <staged-dir> --tree <unpacked-dir>
```

It prints `SKIP` with `skip_reason` when the gate fails;
otherwise `paste_recipe`, the `maven-artifact-verify` run with `--digests` from `jvm_digest_set` (else the § Digest set, default `sha512`)
and `--podling` **only** when the unpacked source artefact ships a `DISCLAIMER` or `DISCLAIMER-WIP` at its root.
Run it (offline, read-only: any voter may), save the JSON report, and re-run the command with `--report <report.json>`:
the output is this step's JSON, the recipe now carrying the companion `gpg --verify` lines.

`status` is the tool report's `status`, except that an `ABSENT` jar becomes `FAIL` under `jvm_companion_location: staged`.
`pom_findings` and `companion_findings` list only the checks that did not pass (`FAIL`, `INHERITED-UNVERIFIED`, `ABSENT`), one line each naming the artefact and what is wrong;
an empty list means there is nothing to report.
`observations` carries checks 5–7, one line each naming the jar; an empty list means the staged set carried none.
A jar whose timestamps vary, whose groupId sits outside `org.apache.*`, or whose `-sources.jar` contains `.class` files still passes every blocking check.

Return ONLY valid JSON with this structure:

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
