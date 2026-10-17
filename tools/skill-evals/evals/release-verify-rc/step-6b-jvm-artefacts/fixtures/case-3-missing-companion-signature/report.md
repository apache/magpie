<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § Digest set: sha512. § JVM artefact checks:
`jvm_companion_location: staged`. No `DISCLAIMER` in the source
artefact — a top-level project, so no `--podling`.

maven-artifact-verify JSON report (verbatim):

```json
{
  "tool": "maven-artifact-verify",
  "status": "FAIL",
  "artefact_dir": "dist/dev/foo/1.0.0-rc1",
  "podling": false,
  "digests": ["sha512"],
  "poms": [
    {
      "pom": "foo-core-1.0.0.pom",
      "packaging": "jar",
      "check1": {"licenses": "PASS", "developers": "PASS", "scm": "PASS"}
    }
  ],
  "jars": [
    {"jar": "foo-core-1.0.0.jar", "companions": [
      {"companion": "foo-core-1.0.0-sources.jar", "classification": "FAIL", "detail": "missing .asc signature file (foo-core-1.0.0-sources.jar.asc)"},
      {"companion": "foo-core-1.0.0-javadoc.jar", "classification": "PASS", "detail": null}
    ]}
  ],
  "unmatched_jars": [],
  "findings": []
}
```

Maven Central requires each companion jar to carry its own `.asc`
signature; a staged companion without one is a hard FAIL. The RM
re-signs and re-stages.

`release-management verify-rc jvm --inventory <inventory.json> --staged-dir dist/dev/foo/1.0.0-rc1 --tree <unpacked-dir> --report <report.json>`
printed:

```json
{
  "step": "jvm-artefacts",
  "status": "FAIL",
  "tool_report": "{\n  \"tool\": \"maven-artifact-verify\",\n  \"status\": \"FAIL\",\n  \"artefact_dir\": \"dist/dev/foo/1.0.0-rc1\",\n  \"podling\": false,\n  \"digests\": [\"sha512\"],\n  \"poms\": [\n    {\n      \"pom\": \"foo-core-1.0.0.pom\",\n      \"packaging\": \"jar\",\n      \"check1\": {\"licenses\": \"PASS\", \"developers\": \"PASS\", \"scm\": \"PASS\"}\n    }\n  ],\n  \"jars\": [\n    {\"jar\": \"foo-core-1.0.0.jar\", \"companions\": [\n      {\"companion\": \"foo-core-1.0.0-sources.jar\", \"classification\": \"FAIL\", \"detail\": \"missing .asc signature file (foo-core-1.0.0-sources.jar.asc)\"},\n      {\"companion\": \"foo-core-1.0.0-javadoc.jar\", \"classification\": \"PASS\", \"detail\": null}\n    ]}\n  ],\n  \"unmatched_jars\": [],\n  \"findings\": []\n}",
  "pom_findings": [],
  "companion_findings": [
    "foo-core-1.0.0-sources.jar: missing .asc signature file (foo-core-1.0.0-sources.jar.asc)"
  ],
  "observations": [],
  "paste_recipe": "uv run --project <framework>/tools/maven-artifact-verify \\\n  maven-artifact-verify \"dist/dev/foo/1.0.0-rc1\" --digests sha512\n# without uv:\n# python3 <framework>/tools/maven-artifact-verify/src/maven_artifact_verify/__init__.py ...\n\n# Companion signatures (same KEYS flow as Step 2):\ngpg --verify \"foo-core-1.0.0-javadoc.jar.asc\" \"foo-core-1.0.0-javadoc.jar\""
}
```
