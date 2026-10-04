<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo:
orgapachefoo-1024`, `jvm_companion_location: nexus-staging`. The RC is
1.0.0-rc1. ASF Nexus credentials are available.

Profile-wide staging repository listing (authenticated, verbatim):

```json
{
  "data": [
    {
      "repositoryId": "orgapachefoo-1023",
      "profileName": "org.apache.foo",
      "description": "Managed Release: foo 0.9.0 (abandoned attempt)",
      "state": "open",
      "transitioning": false
    },
    {
      "repositoryId": "orgapachefoo-1024",
      "profileName": "org.apache.foo",
      "description": "Managed Release: foo 1.0.0",
      "state": "closed",
      "transitioning": false
    }
  ]
}
```

Staging repository details for `orgapachefoo-1024`: `state: closed`,
inventory complete and matching — every jar, POM and companion for
`1.0.0` carries its `.asc` and checksum siblings.

Things to classify here:

- The profile holds **two** staging repositories: `orgapachefoo-1023`
  is an open leftover from an abandoned 0.9.0 attempt (a retried
  deploy is the common real-world footgun), `orgapachefoo-1024` is
  this RC's. Surface both — never silently pick one — and proceed
  only with the one matching the RC's version, noting the other as
  stale.
- `orgapachefoo-1024` itself passes cleanly: closed, matching,
  complete. The stale sibling is a warning about housekeeping, not a
  defect in this RC.
