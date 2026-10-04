<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo:
orgapachefoo-1024`, `jvm_companion_location: nexus-staging`. The RC is
1.0.0-rc1, staged under dist/dev/foo/1.0.0-rc1/. ASF Nexus
credentials are available at
`~/.config/apache-magpie/asf-nexus/nexus-credentials`.

Staging repository details (authenticated, verbatim):

```json
{
  "data": {
    "repositoryId": "orgapachefoo-1024",
    "profileName": "org.apache.foo",
    "description": "Managed Release: foo 1.0.0",
    "state": "closed",
    "transitioning": false
  }
}
```

Artefact inventory (authenticated content crawl, trimmed to one
module — every entry below carries its own `.asc`, `.sha1` and
`.md5` sibling in the listing):

```text
/org/apache/foo/foo-core/1.0.0/
  foo-core-1.0.0.jar
  foo-core-1.0.0.pom
  foo-core-1.0.0-sources.jar
  foo-core-1.0.0-javadoc.jar
  foo-core-1.0.0.jar.asc        foo-core-1.0.0.jar.sha1
  foo-core-1.0.0.pom.asc        foo-core-1.0.0.pom.sha1
  foo-core-1.0.0-sources.jar.asc  foo-core-1.0.0-sources.jar.sha1
  foo-core-1.0.0-javadoc.jar.asc  foo-core-1.0.0-javadoc.jar.sha1
```

Things to classify here:

- The inventory version is `1.0.0` — the plain release version, no
  `-rcN` suffix; the suffix lives in the dist path and tag. The
  coordinates correspond to the staged POMs Step 6b verified
  locally.
- `state` is `closed`, read authoritatively under the RM's
  credentials; the profile listing shows no other staging repository
  for `org.apache.foo`.
