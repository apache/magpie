<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker state for airflow-s/airflow-s#287 (SSRF via connection test endpoint):

Labels: airflow, cve allocated
CVE: CVE-2025-31902
Milestone: 3.0.3

Discussion thread summary:
  jsmith: "The fix is to add an allowlist of permitted host patterns to the
  connection test endpoint. We need to decide: (a) who controls the allowlist
  — admin config or per-connection, and (b) whether the endpoint should be
  restricted to authenticated admin users only."

  mwilson: "We still need to check if disabling the endpoint entirely for
  non-admin roles would break any existing integration tests — I haven't
  confirmed that yet."

  jsmith: "Also waiting for the reporter to confirm whether the PoC works
  against v2.9 as well, since we flagged it as affecting 2.9.x but haven't
  verified."

Fix PR: none yet
Security classification: valid
Open questions: admin-vs-per-connection allowlist decision pending; reporter
confirmation of 2.9.x scope pending; integration-test impact unknown
