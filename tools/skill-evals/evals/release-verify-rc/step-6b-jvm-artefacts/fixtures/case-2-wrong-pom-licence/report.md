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

`release-management verify-rc jvm --inventory <inventory.json> --staged-dir dist/dev/foo/1.0.0-rc1 --tree <unpacked-dir> --report <report.json>`
printed:

```json
{
  "step": "jvm-artefacts",
  "status": "FAIL",
  "tool_report": "{\n  \"tool\": \"maven-artifact-verify\",\n  \"status\": \"FAIL\",\n  \"artefact_dir\": \"dist/dev/foo/1.0.0-rc1\",\n  \"podling\": true,\n  \"digests\": [\"sha512\"],\n  \"poms\": [\n    {\n      \"pom\": \"foo-core-1.0.0.pom\",\n      \"packaging\": \"jar\",\n      \"check1\": {\n        \"licenses\": \"FAIL\",\n        \"licenses_detail\": \"licences declared but none is ALv2 (expected name matching 'Apache License, Version 2.0' or url containing apache.org/licenses/LICENSE-2.0)\",\n        \"developers\": \"PASS\",\n        \"scm\": \"PASS\"\n      },\n      \"check2\": {\"disclaimer\": \"PASS\", \"disclaimer_detail\": null}\n    }\n  ],\n  \"jars\": [\n    {\"jar\": \"foo-core-1.0.0.jar\", \"companions\": [\n      {\"companion\": \"foo-core-1.0.0-sources.jar\", \"classification\": \"PASS\", \"detail\": null},\n      {\"companion\": \"foo-core-1.0.0-javadoc.jar\", \"classification\": \"PASS\", \"detail\": null}\n    ]}\n  ],\n  \"unmatched_jars\": [],\n  \"findings\": []\n}",
  "pom_findings": [
    "foo-core-1.0.0.pom: licences declared but none is ALv2 (expected name matching 'Apache License, Version 2.0' or url containing apache.org/licenses/LICENSE-2.0)"
  ],
  "companion_findings": [],
  "observations": [],
  "paste_recipe": "uv run --project <framework>/tools/maven-artifact-verify \\\n  maven-artifact-verify \"dist/dev/foo/1.0.0-rc1\" --digests sha512 --podling\n# without uv:\n# python3 <framework>/tools/maven-artifact-verify/src/maven_artifact_verify/__init__.py ...\n\n# Companion signatures (same KEYS flow as Step 2):\ngpg --verify \"foo-core-1.0.0-sources.jar.asc\" \"foo-core-1.0.0-sources.jar\"\ngpg --verify \"foo-core-1.0.0-javadoc.jar.asc\" \"foo-core-1.0.0-javadoc.jar\""
}
```
