<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo:
orgapachefoo-1025`, `jvm_companion_location: nexus-staging`. The RC is
1.0.0-rc2, staged under dist/dev/foo/1.0.0-rc2/. ASF Nexus
credentials are available.

Staging repository details (authenticated, verbatim):

```json
{
  "data": {
    "repositoryId": "orgapachefoo-1025",
    "profileName": "org.apache.foo",
    "description": "Managed Release: foo 1.0.0",
    "state": "open",
    "transitioning": false
  }
}
```

Artefact inventory (authenticated content crawl, trimmed): the tree
is complete for `1.0.0` — every jar, POM and companion carries its
`.asc` and checksum siblings, coordinates match the RC's declared
release version.

Things to classify here:

- `state` is `open` — the repository is still mutable and is not a
  valid vote target. This is a distinct finding from a
  not-reachable repository: something editable is there. The
  inventory itself is complete and matching; the state alone decides
  this case.
