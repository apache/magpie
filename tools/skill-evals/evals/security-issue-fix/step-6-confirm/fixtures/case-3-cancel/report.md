<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Implementation plan for airflow-s/airflow-s#301 fix:

1. Branch: tighten-assets-graph-dag-permission-check off main
2. Files: airflow/api/common/assets.py, airflow/auth/managers/base.py
3. Commit: "Enforce permission check on asset graph DAG view"
4. Test plan: update tests/api/common/test_assets.py
5. Backport: backport-to-v3-0-test
6. Newsfragment: none
7. PR body: [draft]

User confirmation: cancel
