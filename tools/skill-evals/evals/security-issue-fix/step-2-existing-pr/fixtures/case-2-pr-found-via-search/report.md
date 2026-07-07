<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker state for airflow-s/airflow-s#45 (DAG permission leak in asset graph view):

Labels: airflow, cve allocated
CVE: CVE-2026-51234
Milestone: 3.2.2

Discussion thread summary:
  mwilson: "The asset graph endpoint does not check DAG-level permissions.
  Any authenticated user can see assets belonging to DAGs they don't have
  access to."

  jsmith: "The fix belongs in `airflow/www/views.py` — the graph endpoint
  needs to call `can_read_dag()` before including each node."

Fix PR: none

GitHub search results for open PRs matching "asset graph dag permission":
  - #66801 "Add DAG-level permission check to asset graph API"
    Author: contributor-x, Branch: fix/asset-graph-perms, State: OPEN
    (last updated 3 days ago, 2 review comments, CI passing)
