<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Tracker state

**Tracker:** apache/security-tracker#998
**Title:** Timing side-channel in PBKDF2 password comparison in webserver auth
**Current step:** Step 11 — PR merged, awaiting release
**Labels (current):** `security`, `step-11`, `pr-merged`, `HIGH`, `cve-allocated`
**CVE:** CVE-2026-38812
**Milestone:** Airflow 3.0.3
**Days since last activity:** 4

## Step diagnosis

The private fix PR was merged into the main branch 4 days ago. The fix is
included in the Airflow 3.0.3 milestone but that release has not yet been cut.
PyPI shows no 3.0.3 release yet.

The tracker is correctly parked at Step 11. No action is required from the
security team — the next sync run will detect the PyPI release and
automatically propose the `fix released` label swap (Step 12).

## Proposed changes (2b output)

Items proposed:
1. Remove label `step-10` (already absent — skip)
2. Label `step-11` already present — skip
3. Post status comment: "Private PR merged. Tracker parked at Step 11 pending
   Airflow 3.0.3 release. Sync will auto-detect PyPI publication."

Label state is already clean.
