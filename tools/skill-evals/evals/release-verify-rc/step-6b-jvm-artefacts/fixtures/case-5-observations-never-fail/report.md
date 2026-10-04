<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § Digest set: sha512. § JVM artefact checks:
`jvm_companion_location: nexus-staging`. The RC is a podling (a
`DISCLAIMER` file ships at the source artefact root).

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
  "unmatched_jars": [],
  "findings": [],
  "observations": {
    "timestamp_signal": [
      {"jar": "foo-core-1.0.0.jar", "signal": "inconsistent", "entries": 118, "distinct_timestamps": 4,
       "detail": "entry timestamps vary - not consistent with a reproducible configuration (project.build.outputTimestamp likely unset); this observation does not claim the jar is unreproducible"}
    ],
    "namespace_signal": [
      {"jar": "foo-core-1.0.0.jar", "group_id": "org.apache.foo", "under_org_apache": true,
       "class_entries": 47, "matching_entries": 45,
       "package_roots": ["com/example/relocated", "org/apache/foo"],
       "detail": "45/47 class entries under the package path 'org/apache/foo' derived from groupId 'org.apache.foo'; package roots (first three segments): com/example/relocated, org/apache/foo"}
    ],
    "companion_content": [
      {"jar": "foo-core-1.0.0-sources.jar", "kind": "sources", "signal": "contains-class-files",
       "detail": "3 .class entries inside a -sources.jar (compiled code in the sources companion); observation only, never a failure"},
      {"jar": "foo-core-1.0.0-javadoc.jar", "kind": "javadoc", "signal": "placeholder",
       "detail": "empty or MANIFEST-only jar - placeholder companions are a Maven-Central-sanctioned pattern; observation only (content is not structure-asserted: dokka/scaladoc output is equally valid)"}
    ]
  }
}
```

Three things to classify here:

- Every blocking check passes: the POM set is clean, both companions
  are staged with `.asc` and checksums. The status is the tool's
  status.
- The observations — varying entry timestamps, two relocated class
  roots, `.class` files inside the sources companion, a placeholder
  javadoc companion — are signals for the reviewer. None of them may
  change the verdict: the placeholder is Maven-Central-sanctioned,
  and the observations never assert reproducibility either way.
- The podling signal is present, so `--podling` stays in the recipe.
