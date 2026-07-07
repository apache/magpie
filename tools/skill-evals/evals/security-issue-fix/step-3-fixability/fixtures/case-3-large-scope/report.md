<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker state for airflow-s/airflow-s#301 (API permission bypass):

Labels: airflow, cve allocated
CVE: CVE-2025-51208
Milestone: 3.1.0

Discussion thread summary:
  jsmith: "The root cause is that the DAG permission model doesn't propagate
  through the asset graph view. A full fix requires refactoring the
  permission-check layer across the REST API, the UI, and the scheduler's
  task-isolation boundary — probably 15-20 files, new test fixtures for the
  asset graph API, and changes to the public permissions schema."

  mwilson: "We need to coordinate with the core-api team because their
  upcoming refactor in PR #46000 is rewriting the same code. We shouldn't
  land a security patch on code that's about to be torn out."

  jsmith: "Agreed. This needs the private-PR path — too large to do quietly
  on main without drawing questions in review."

Fix PR: none yet
Security classification: valid
Open questions: coordination with core-api refactor
