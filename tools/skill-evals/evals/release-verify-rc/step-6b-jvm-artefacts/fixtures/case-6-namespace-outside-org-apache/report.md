<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § Digest set: sha512. § JVM artefact checks:
`jvm_companion_location: nexus-staging`. No `DISCLAIMER` in the source
artefact — the project graduated from the Incubator years ago.

maven-artifact-verify JSON report (verbatim):

```json
{
  "tool": "maven-artifact-verify",
  "status": "PASS",
  "artefact_dir": "dist/dev/foo/2.1.0-rc1",
  "podling": false,
  "digests": ["sha512"],
  "poms": [
    {
      "pom": "foo-core-2.1.0.pom",
      "packaging": "jar",
      "check1": {"licenses": "PASS", "developers": "PASS", "scm": "PASS"}
    }
  ],
  "jars": [
    {"jar": "foo-core-2.1.0.jar", "companions": [
      {"companion": "foo-core-2.1.0-sources.jar", "classification": "PASS", "detail": null},
      {"companion": "foo-core-2.1.0-javadoc.jar", "classification": "PASS", "detail": null}
    ]}
  ],
  "unmatched_jars": [],
  "findings": [],
  "observations": {
    "timestamp_signal": [
      {"jar": "foo-core-2.1.0.jar", "signal": "consistent", "entries": 204, "distinct_timestamps": 1,
       "detail": "every file entry shares one timestamp - consistent with a reproducible configuration (project.build.outputTimestamp set); this observation does not claim the jar is reproducible"}
    ],
    "namespace_signal": [
      {"jar": "foo-core-2.1.0.jar", "group_id": "com.github.foo", "under_org_apache": false,
       "class_entries": 24, "matching_entries": 24,
       "package_roots": ["com/github/foo"],
       "detail": "24/24 class entries under the package path 'com/github/foo' derived from groupId 'com.github.foo'; package roots (first three segments): com/github/foo"}
    ],
    "companion_content": [
      {"jar": "foo-core-2.1.0-sources.jar", "kind": "sources", "signal": "sources-present",
       "detail": "31 .java/.scala/.kt source entries; no .class entries"},
      {"jar": "foo-core-2.1.0-javadoc.jar", "kind": "javadoc", "signal": "content-present",
       "detail": "58 non-META-INF entries; documentation layout is not judged"}
    ]
  }
}
```

Two things to classify here:

- The groupId `com.github.foo` is not under `org.apache.*`: the
  project entered the ASF with existing Maven coordinates and kept
  them for downstream compatibility. That is real policy quoted in
  the issue, but deliberately informational **even for ASF
  projects** — a published artefact's coordinates cannot be changed
  retroactively, so failing the RC would leave the RM no available
  remedy. The status stays the tool's status.
- The consistent timestamp signal reads "consistent with a
  reproducible configuration" — it must never be reworded into a
  claim that the jar is reproducible; only Step 9's rebuild can
  assert that.

`release-management verify-rc jvm --inventory <inventory.json> --staged-dir dist/dev/foo/2.1.0-rc1 --tree <unpacked-dir> --report <report.json>`
printed:

```json
{
  "step": "jvm-artefacts",
  "status": "PASS",
  "tool_report": "{\n  \"tool\": \"maven-artifact-verify\",\n  \"status\": \"PASS\",\n  \"artefact_dir\": \"dist/dev/foo/2.1.0-rc1\",\n  \"podling\": false,\n  \"digests\": [\"sha512\"],\n  \"poms\": [\n    {\n      \"pom\": \"foo-core-2.1.0.pom\",\n      \"packaging\": \"jar\",\n      \"check1\": {\"licenses\": \"PASS\", \"developers\": \"PASS\", \"scm\": \"PASS\"}\n    }\n  ],\n  \"jars\": [\n    {\"jar\": \"foo-core-2.1.0.jar\", \"companions\": [\n      {\"companion\": \"foo-core-2.1.0-sources.jar\", \"classification\": \"PASS\", \"detail\": null},\n      {\"companion\": \"foo-core-2.1.0-javadoc.jar\", \"classification\": \"PASS\", \"detail\": null}\n    ]}\n  ],\n  \"unmatched_jars\": [],\n  \"findings\": [],\n  \"observations\": {\n    \"timestamp_signal\": [\n      {\"jar\": \"foo-core-2.1.0.jar\", \"signal\": \"consistent\", \"entries\": 204, \"distinct_timestamps\": 1,\n       \"detail\": \"every file entry shares one timestamp - consistent with a reproducible configuration (project.build.outputTimestamp set); this observation does not claim the jar is reproducible\"}\n    ],\n    \"namespace_signal\": [\n      {\"jar\": \"foo-core-2.1.0.jar\", \"group_id\": \"com.github.foo\", \"under_org_apache\": false,\n       \"class_entries\": 24, \"matching_entries\": 24,\n       \"package_roots\": [\"com/github/foo\"],\n       \"detail\": \"24/24 class entries under the package path 'com/github/foo' derived from groupId 'com.github.foo'; package roots (first three segments): com/github/foo\"}\n    ],\n    \"companion_content\": [\n      {\"jar\": \"foo-core-2.1.0-sources.jar\", \"kind\": \"sources\", \"signal\": \"sources-present\",\n       \"detail\": \"31 .java/.scala/.kt source entries; no .class entries\"},\n      {\"jar\": \"foo-core-2.1.0-javadoc.jar\", \"kind\": \"javadoc\", \"signal\": \"content-present\",\n       \"detail\": \"58 non-META-INF entries; documentation layout is not judged\"}\n    ]\n  }\n}",
  "pom_findings": [],
  "companion_findings": [],
  "observations": [
    "foo-core-2.1.0.jar: consistent (1 distinct across 204 entries) - every file entry shares one timestamp - consistent with a reproducible configuration (project.build.outputTimestamp set); this observation does not claim the jar is reproducible",
    "foo-core-2.1.0.jar: groupId com.github.foo is NOT under org.apache.* (informational even for ASF projects - published coordinates cannot be renamed retroactively); 24/24 class entries under the package path 'com/github/foo' derived from groupId 'com.github.foo'; package roots (first three segments): com/github/foo",
    "foo-core-2.1.0-sources.jar: sources-present - 31 .java/.scala/.kt source entries; no .class entries",
    "foo-core-2.1.0-javadoc.jar: content-present - 58 non-META-INF entries; documentation layout is not judged"
  ],
  "paste_recipe": "uv run --project <framework>/tools/maven-artifact-verify \\\n  maven-artifact-verify \"dist/dev/foo/2.1.0-rc1\" --digests sha512\n# without uv:\n# python3 <framework>/tools/maven-artifact-verify/src/maven_artifact_verify/__init__.py ...\n\n# Companion signatures (same KEYS flow as Step 2):\ngpg --verify \"foo-core-2.1.0-sources.jar.asc\" \"foo-core-2.1.0-sources.jar\"\ngpg --verify \"foo-core-2.1.0-javadoc.jar.asc\" \"foo-core-2.1.0-javadoc.jar\""
}
```
