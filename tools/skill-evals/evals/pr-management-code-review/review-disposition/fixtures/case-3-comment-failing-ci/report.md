<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #6503 — Fix typo in scheduler docstring
Author: carol-contributor (CONTRIBUTOR)
CI: FAILURE — "integration-tests-postgres" is failing
Mergeable: MERGEABLE
Unresolved threads: 0
Existing maintainer reviews: (none)

Diff findings:
  - The change is a one-line docstring typo fix: "occurred" → "occurred".
  - No code logic changed.
  - The failing CI check ("integration-tests-postgres") is unrelated to this PR's diff —
    it has been failing on main for the past 3 days due to a flaky test in the Postgres
    integration suite (tracked in AIRFLOW-99999).
