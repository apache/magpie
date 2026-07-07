<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Proposal surfaced to user

**PR:** apache/airflow#52199 — "fix: prevent XCom pickle deserialization of untrusted payloads"
**Author:** contributor-x · **State:** MERGED · **Merged at:** 2025-03-10

**Detected scope:** airflow
**Scope reasoning:** All production files under airflow/ (core)

**Proposed milestone:** Airflow 3.2.2

**Proposed title:** Prevent XCom pickle deserialization of untrusted payloads

**Labels:** `security issue`, `airflow`, `pr merged`

**Target board column:** Assessed

**Body fields:**
- Affected versions: apache/airflow >= 2.8.0 (versions to be confirmed during triage)
- Security mailing list thread: N/A — opened from public PR apache/airflow#52199; no security@ thread
- PR with the fix: https://github.com/apache/airflow/pull/52199
- Remediation developer: @contributor-x
- Reporter credited as: _No response_
- Severity: Unknown

## User reply

title: Arbitrary callable invocation via pickle deserialization in XCom backend
