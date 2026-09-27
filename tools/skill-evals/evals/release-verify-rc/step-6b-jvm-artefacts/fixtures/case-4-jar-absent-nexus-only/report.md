<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § Digest set: sha512. § JVM artefact checks:
`jvm_companion_location: nexus-staging` — the jars publish through the
Nexus staging repository; only the POM is staged in dist/dev. No
`DISCLAIMER` in the source artefact, so no `--podling`.

maven-artifact-verify JSON report (verbatim):

```json
{
  "tool": "maven-artifact-verify",
  "status": "WARN",
  "artefact_dir": "dist/dev/foo/1.0.0-rc1",
  "podling": false,
  "digests": ["sha512"],
  "poms": [
    {
      "pom": "foo-core-1.0.0.pom",
      "packaging": "jar",
      "check1": {
        "licenses": "PASS",
        "developers": "INHERITED-UNVERIFIED",
        "developers_detail": "element absent and no locally staged parent POM to resolve against; verify against the effective POM",
        "scm": "PASS"
      }
    }
  ],
  "jars": [
    {"jar": "foo-core-1.0.0.jar", "companions": [
      {"companion": "foo-core-1.0.0.jar", "classification": "ABSENT", "detail": "main jar not staged locally; companion checks skipped (verify via the Nexus staging repository when it is the vote target)"}
    ]}
  ],
  "unmatched_jars": [],
  "findings": ["foo-core-1.0.0.jar is declared by a staged POM but not staged locally"]
}
```

Two things to classify here:

- `<developers>` is inherited from `org.apache:apache`, which is not
  staged in dist/dev — `INHERITED-UNVERIFIED` is a WARN naming what to
  verify (`mvn help:effective-pom`), never a FAIL: a correct POM that
  inherits from the ASF parent must not be failed.
- The main jar is `ABSENT` locally, but `release-build.md` declares
  `jvm_companion_location: nexus-staging`, so the absence is the
  expected shape: an observation, not a FAIL. Under
  `jvm_companion_location: staged` the same report would be FAIL.
