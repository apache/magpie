<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Implementation plan for airflow-s/airflow-s#254 fix:

1. Branch: fix-dag-name-validation-backtracking off main
2. Files: airflow/dag_processing/processor.py (replace regex with linear impl)
3. Commit: "Fix DAG name validation to avoid pathological backtracking"
4. Test plan: update tests/dag_processing/test_processor.py, run pytest
5. Backport: backport-to-v3-0-test label
6. Newsfragment: none
7. PR body: [draft]

User response: "The branch name is fine but can you also add
tests/utils/test_helpers.py to the file list? The helper function there
calls the same validator."
