<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Tracker state

**Tracker:** apache/security-tracker#1003
**Title:** Path traversal in LocalFilesystemBackend allows reading arbitrary files
**Current step:** Step 13 — Fix released, RM must publish advisory
**Labels (current):** `security`, `step-13`, `fix-released`, `MEDIUM`, `cve-allocated`
**CVE:** CVE-2026-41205
**Milestone:** Airflow 2.10.5
**Days since last activity:** 1

## Step diagnosis

Airflow 2.10.5 published to PyPI 1 day ago — the LocalFilesystemBackend
path-traversal fix is now shipped. The label swap from `pr-merged` to
`fix-released` was applied by the previous sync run (Step 12).

The tracker is at Step 13. The release manager for Airflow 2.10.5 must now:
- Fill in the CVE tool fields (CWE, affected versions, severity, patch link,
  reporter credits) in the ASF CVE tool record for CVE-2026-41205.
- Move the CVE status from REVIEW → READY.
- Send the advisory to `announce@apache.org` and `users@airflow.apache.org`.

The CVE tool link is recorded in the tracker body field
(`https://cveprocess.apache.org/cve5/CVE-2026-41205`).

Known release manager for Airflow 2.10.5: Ephraim Kiptoo Birech (per AGENTS.md cache).

## Proposed changes (2b output)

Items proposed:
1. Label `step-13` already present — skip
2. Post status comment: "Fix shipped in Airflow 2.10.5 (PyPI). Ownership
   transferred to release manager Ephraim Kiptoo Birech for advisory
   publication."
