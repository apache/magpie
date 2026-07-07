<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Implementation plan for airflow-s/airflow-s#272 fix:

1. Branch: fix-xcom-deserialization-owner-check off main
2. Files: airflow/models/xcom.py (add owner check before pickle.loads)
3. Commit: "Improve XCom value isolation in extra links API"
4. Test plan: update tests/models/test_xcom.py, run pytest + prek
5. Backport: backport-to-v3-0-test label needed (milestone is 3.0.3)
6. Newsfragment: none (security-adjacent change, skip per convention)
7. PR body: [draft with gen-AI disclosure block]

User confirmation: all
