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
