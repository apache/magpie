<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step 6c — Nexus staging repository

From `release-management verify-rc nexus`. GETs only: the remediation is always the RM's, in the Nexus UI or a re-deploy — the skill never closes, drops or promotes.

| Symptom | Likely cause | Remediation |
|---|---|---|
| Step 6c FAIL — staging repository not reachable | The id given for this RC serves nothing (wrong id, already promoted/dropped, or never deployed) | RM re-checks the id on the planning issue and the Nexus UI, re-deploys if never staged |
| Step 6c FAIL — staging repository `open` | The close operation did not happen (or failed) before the vote | RM closes the staging repo in the Nexus UI, then re-runs verify-rc |
| Step 6c FAIL — snapshots repository targeted | The RC's jars were deployed to the snapshots repository instead of a staging repository | RM re-deploys through the staging workflow; snapshots are never a vote target |
| Step 6c FAIL — coordinates/version mismatch | The staging repository holds artefacts for a different version than the RC declares | RM re-deploys the correct version and re-checks for stale sibling repositories |
| Step 6c FAIL — `.asc` or companion missing in staging | A `.jar`/`.pom` in the staging repository has no signature, or a main jar's `-sources.jar`/`-javadoc.jar` set is incomplete | RM re-deploys the complete signed set — Nexus close-time validation would reject the promotion anyway |
| Step 6c WARN — `STATE-UNVERIFIED` | The runner has no Nexus credentials (or the sandbox refused the probe), so the authoritative `closed` state could not be read | RM verifies by hand in the Nexus UI (`stagingRepositories`); no action needed when it reads `closed` |
| Step 6c WARN — stale sibling repositories | The profile holds several staging repositories for the project (retried deploys, earlier RCs) | RM drops the stale ones after confirming which id belongs to this RC |
