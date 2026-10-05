<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo:
snapshots`. No ASF Nexus credentials available (the runner is a
voter).

Existence check (anonymous):

```text
curl -fsS -o /dev/null -w '%{http_code}
'   "https://repository.apache.org/content/repositories/snapshots/"
→ HTTP 200 OK
```

Artefact inventory (anonymous crawl, trimmed):

```text
/org/apache/foo/foo-core/1.0.0-SNAPSHOT/
  foo-core-1.0.0-SNAPSHOT.jar
  foo-core-1.0.0-SNAPSHOT.pom
```

Things to classify here:

- The id resolves to the snapshots repository — the issue's boundary
  condition is explicit: it is never a valid vote target, whatever
  the version string claims. A hard `FAIL` naming the snapshots
  repository, not a lookup miss.
- The version strings carry `-SNAPSHOT`: unmarked snapshots staged
  as an RC is exactly the mistake this exclusion exists to catch.
