<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § Digest set: sha512. § JVM artefact checks:
`jvm_companion_location: staged`.

The unpacked source artefact ships a `DISCLAIMER` file at its root —
the podling signal — so `--podling` is passed.

maven-artifact-verify JSON report (verbatim):

```json
{
  "tool": "maven-artifact-verify",
  "status": "PASS",
  "artefact_dir": "dist/dev/foo/1.0.0-rc1",
  "podling": true,
  "digests": ["sha512"],
  "poms": [
    {
      "pom": "foo-core-1.0.0.pom",
      "packaging": "jar",
      "check1": {"licenses": "PASS", "developers": "PASS", "scm": "PASS"},
      "check2": {"disclaimer": "PASS", "disclaimer_detail": null}
    }
  ],
  "jars": [
    {"jar": "foo-core-1.0.0.jar", "companions": [
      {"companion": "foo-core-1.0.0-sources.jar", "classification": "PASS", "detail": null},
      {"companion": "foo-core-1.0.0-javadoc.jar", "classification": "PASS", "detail": null}
    ]}
  ],
  "unmatched_jars": ["foo-core-1.0.0-tests.jar"],
  "findings": []
}
```

The `-tests` jar is a classified jar: neither a main nor a companion,
reported as an observation only.
