<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo:
orgapachefoo-1027`. The RC is 1.0.0-rc3 of release version 1.0.0. ASF
Nexus credentials are available.

Staging repository details (authenticated):

```json
{"data": {"repositoryId": "orgapachefoo-1027", "profileName": "org.apache.foo",
 "description": "Managed Release: foo 1.0.1", "state": "closed", "transitioning": false}}
```

Artefact inventory (authenticated crawl, trimmed to one module —
every entry carries its `.asc` and checksum siblings):

```text
/org/apache/foo/foo-core/1.0.1/
  foo-core-1.0.1.jar              foo-core-1.0.1.jar.asc
  foo-core-1.0.1.pom              foo-core-1.0.1.pom.asc
  foo-core-1.0.1-sources.jar      foo-core-1.0.1-sources.jar.asc
  foo-core-1.0.1-javadoc.jar      foo-core-1.0.1-javadoc.jar.asc
```

Things to classify here:

- The staging repository is `closed` and its companion coverage is
  complete — but the inventory holds `1.0.1`, not the `1.0.0` this
  RC declares. A hard `FAIL`: the vote would cover jars for some
  other version. The `-rcN` suffix lives in the dist path, not in
  the Maven version, so the expected inventory version is the plain
  `1.0.0`.
