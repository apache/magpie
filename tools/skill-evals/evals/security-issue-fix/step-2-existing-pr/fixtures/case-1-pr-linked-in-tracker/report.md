<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker state for airflow-s/airflow-s#23 (Bulk API team-context authz bypass):

Labels: airflow, needs triage
Milestone: 3.2.2

Discussion thread summary:
  potiuk: "The bulk pool / connection / variable endpoints skip the team
  membership check for CREATE+OVERWRITE. The fix should include
  CREATE+OVERWRITE entities in the existing-team lookup."

  vincbeck: "I have an open PR for this already — see below."

Fix PR: https://github.com/apache/airflow/pull/67293
Security classification: valid, defense-in-depth (consensus)
Open questions: none

GitHub search results for open PRs matching "bulk team permissions":
  - #67293 "Check team permissions on bulk APIs for Connections, Variables and Pools"
    Author: vincbeck, Branch: vincbeck/bulk_teams, State: OPEN
