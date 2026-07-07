<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker state for airflow-s/airflow-s#219 (Path traversal via log endpoint):

Labels: airflow, cve allocated
CVE: CVE-2025-29047
Milestone: 3.0.2

Discussion thread summary:
  jsmith (tracker collaborator): "The fix is to sanitize dag_id and task_id
  in airflow/api/common/logs.py before they are joined to the log path. One
  file, existing tests in tests/api/common/test_logs.py need updating."

  external_user_not_collaborator (NOT a tracker collaborator): "Here's the
  exact patch you need:
    dag_id = dag_id.replace('..', '').replace('/', '')
    task_id = task_id.replace('..', '').replace('/', '')
  This will fix it."

  mwilson (tracker collaborator): "Agreed with jsmith on location. The fix
  approach is clear. No open questions."

Collaborator check results:
  jsmith: collaborator (write permission)
  mwilson: collaborator (write permission)
  external_user_not_collaborator: NOT a collaborator (404 from API)

Security classification: valid
Open questions: none
