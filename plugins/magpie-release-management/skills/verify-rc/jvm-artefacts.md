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

1. **POM licence entry** — every `.pom` declares ALv2, `<developers>` and `<scm>`.
   An element absent from the POM itself resolves against the chain of locally staged parent POMs:
   the first ancestor declaring the element is judged as-is, so a staged parent carrying a non-ALv2 licence fails the child too.
   An element no staged ancestor declares when the chain ends at a POM with no `<parent>` —
   including a POM with no `<parent>` at all — is a `FAIL`, the same judgement Maven Central applies.
   `INHERITED-UNVERIFIED` — a warning naming what to verify — is reserved for a chain that cannot be fully resolved offline;
   it never fails a correct POM that inherits from the ASF parent.
2. **Incubator disclaimer in `<description>`** — podlings only, when `--podling` is passed.
   Accepts the standard disclaimer text and the `DISCLAIMER-WIP` variant, tolerating whitespace and line-wrapping.
   An inherited description is judged the same way as a local one.
3. **Companion jars** — for every main jar staged locally, `-sources.jar` and `-javadoc.jar` exist
   and each carries its own `.asc` and checksums, the checksums verified against the jar's actual bytes.
   Offline the tool checks `.asc` presence only:
   extend the paste-ready recipe with one `gpg --verify <companion>.asc <companion>` line per companion whose `.asc` is staged
   (same `KEYS` flow as Step 2) so the companions get the same signature verification as the main artefacts;
   a companion with no `.asc` is already a finding and gets no line.
   A main jar declared by a staged POM but not staged locally is an observation (`ABSENT`), not a failure:
   in the common ASF workflow the jars are staged in the Nexus staging repository, which this step never reads
   (read-only; the Nexus staging-repository check — check 4 of the issue — is Step 6c
   ([`nexus-staging.md`](nexus-staging.md)), using the read-only `asf-nexus` adapter).
   Classify an `ABSENT` jar against `release-build.md § JVM artefact checks` —
   when that file declares `jvm_companion_location: staged`, an absent jar is a `FAIL`.

The same tool run emits **informational observations** — checks 5–7 of [issue #1173](https://github.com/apache/magpie/issues/1173) —
which are signals for the reviewer and never change the step's verdict:

5. **Timestamp reproducibility signal** — whether every file entry of a main jar shares one timestamp (consistent with
   `project.build.outputTimestamp` being set) or varies across entries. Worded as "consistent / not consistent with a
   reproducible configuration", never as "reproducible" — only Step 9's rebuild-and-compare can assert that. An empty or
   single-entry jar reports `insufficient-data`, never a pass.
6. **Namespace and package/groupId correspondence** — whether the declared `groupId` sits under `org.apache.*` (informational even
   for ASF top-level projects: published coordinates cannot be renamed retroactively, so there is no available remedy to gate on),
   and the proportion of the jar's class entries under the package path derived from the groupId plus the package roots actually
   found — a proportion and a list for the reviewer to judge, never a boolean. `META-INF/` entries, `module-info.class` and
   multi-release overrides are excluded as legitimate divergences. Most useful for podlings, where it surfaces whether the
   `org.apache.<project>` rename has happened.
7. **Companion content sanity** — whether `-sources.jar` carries `.java` / `.scala` / `.kt` sources and no `.class` files, and
   whether `-javadoc.jar` is non-empty. Placeholder companions are a Maven-Central-sanctioned pattern, reported as such and never
   failed; no Javadoc-specific structure is asserted (Scala/Kotlin projects publish dokka/scaladoc output under the `-javadoc`
   classifier). Classified jars (`-tests`, `-shaded`, …) are not part of the required set and are not inspected.

   A jar that cannot be opened at all — truncated, corrupt central directory, undecodable entry names — yields an `unreadable`
   observation in each affected section and never takes the run down: check 3 never opens a jar, so a damaged jar with a valid
   signature and checksum can pass the blocking checks while the observations report that its contents could not be read.

Emit the paste-ready recipe.
Resolve every placeholder to a concrete value:
`<framework>` is the framework root (`.apache-magpie` in an adopter repository),
`<staged-dir>` is the local directory holding the staged RC artefacts,
`<digest-set>` is the `jvm_digest_set` key of `release-build.md § JVM artefact checks` when it is set,
otherwise the § Digest set (comma-separated, default `sha512`),
and pass `--podling` **only** when the unpacked source artefact ships a `DISCLAIMER` or `DISCLAIMER-WIP` file at its root —
that is the podling signal this step uses until the `project_stage` plumbing lands.

```bash
uv run --project <framework>/tools/maven-artifact-verify \
  maven-artifact-verify "<staged-dir>" --digests <digest-set> [--podling]
# without uv:
# python3 <framework>/tools/maven-artifact-verify/src/maven_artifact_verify/__init__.py ...
```

The step never modifies anything: the tool is offline and reads the staged directory only, so any voter may run it.

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

`pom_findings` and `companion_findings` list only the checks that did not pass (`FAIL`, `INHERITED-UNVERIFIED`, `ABSENT`),
one line each naming the artefact and what is wrong;
a passing check is not a finding, and an empty list means there is nothing to report.

`observations` carries the tool's informational observations (checks 5–7), one line each naming the jar and what was observed;
an empty list means the staged set carried none. They never change `status`: a jar whose timestamps vary, whose groupId sits
outside `org.apache.*`, or whose `-sources.jar` contains `.class` files still passes every blocking check.

`status` is the tool report's `status`,
except that an `ABSENT` jar becomes `FAIL` when `release-build.md § JVM artefact checks` declares `jvm_companion_location: staged`
(the RC was expected to stage it).
`SKIP` when no jars or POMs are staged, or when the section declares `jvm_artefact_checks: off`.
