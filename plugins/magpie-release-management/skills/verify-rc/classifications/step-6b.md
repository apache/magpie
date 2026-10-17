<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 6b — JVM artefacts

From `release-management verify-rc jvm`. Informational observations never change the status.

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 6b FAIL — POM licence/developers/scm wrong | The POM does not satisfy ASF Incubator distribution policy § Maven distribution | RM fixes the POM, re-deploys, re-cuts RC |
| Step 6b FAIL — companion jar or its `.asc`/checksum missing | Maven Central requires `-sources.jar` / `-javadoc.jar` companions, each signed and checksummed; Nexus close-time validation fails without them | RM re-deploys with signed companions, re-cuts RC |
| Step 6b FAIL — companion checksum mismatch | The recorded digest does not match the companion jar's bytes (stale or corrupted checksum file) | RM re-deploys the companion set with regenerated checksums, re-cuts RC |
| Step 6b WARN — `INHERITED-UNVERIFIED` | POM element inherited from a parent POM that is not staged locally | Verify against the effective POM (`mvn help:effective-pom`); if correct, no action |
| Step 6b FAIL — jar absent but `jvm_companion_location: staged` | The RC was expected to stage its jars locally and did not | RM re-stages the jar set or corrects `release-build.md` |
