<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo:
orgapachefoo-1024`, `jvm_companion_location: nexus-staging`. The RC is
1.0.0-rc1. The runner is a **voter with no Nexus credentials** — no
`~/.config/apache-magpie/asf-nexus/netrc` file exists.

Staging repository details (authenticated path):

```text
curl .../service/local/staging/repository/orgapachefoo-1024
→ HTTP 401 Unauthorized
```

Artefact inventory (anonymous web-tree crawl over
`https://repository.apache.org/content/repositories/orgapachefoo-1024/`,
trimmed to one module):

```text
/org/apache/foo/foo-core/1.0.0/
  foo-core-1.0.0.jar            foo-core-1.0.0.jar.asc
  foo-core-1.0.0.pom            foo-core-1.0.0.pom.asc
  foo-core-1.0.0-sources.jar
  foo-core-1.0.0-javadoc.jar    foo-core-1.0.0-javadoc.jar.asc
```

Things to classify here:

- The `401` is the expected anonymous shape for `/service/local/...`
  — it says nothing about whether the repository exists. The
  authoritative `state` cannot be read, which is `STATE-UNVERIFIED`
  (a warning naming what to verify by hand in the Nexus UI), never a
  failure: a voter with no Nexus account is the expected runner of
  the anonymous path.
- The inventory is otherwise complete and matching — except
  `foo-core-1.0.0-sources.jar` has no sibling `.asc`, while the main
  jar, the POM and the javadoc companion do. A hard finding: the
  signature coverage is the same rule Step 2 applies to the main
  artefacts.
