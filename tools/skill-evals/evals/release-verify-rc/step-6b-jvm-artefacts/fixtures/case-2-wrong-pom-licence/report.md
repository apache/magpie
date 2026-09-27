<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § Digest set: sha512. § JVM artefact checks:
`jvm_companion_location: staged`. The source artefact ships a
`DISCLAIMER` file, so `--podling` is passed.

maven-artifact-verify JSON report (verbatim):

```json
{
  "tool": "maven-artifact-verify",
  "status": "FAIL",
  "artefact_dir": "dist/dev/foo/1.0.0-rc1",
  "podling": true,
  "digests": ["sha512"],
  "poms": [
    {
      "pom": "foo-core-1.0.0.pom",
      "packaging": "jar",
      "check1": {
        "licenses": "FAIL",
        "licenses_detail": "licences declared but none is ALv2 (expected name matching 'Apache License, Version 2.0' or url containing apache.org/licenses/LICENSE-2.0)",
        "developers": "PASS",
        "scm": "PASS"
      },
      "check2": {"disclaimer": "PASS", "disclaimer_detail": null}
    }
  ],
  "jars": [
    {"jar": "foo-core-1.0.0.jar", "companions": [
      {"companion": "foo-core-1.0.0-sources.jar", "classification": "PASS", "detail": null},
      {"companion": "foo-core-1.0.0-javadoc.jar", "classification": "PASS", "detail": null}
    ]}
  ],
  "unmatched_jars": [],
  "findings": []
}
```

The POM declares an MIT licence. ASF Incubator distribution policy §
Maven distribution requires the ALv2 licence in the POM — a hard FAIL;
the RM must fix the POM and re-cut.
