<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #70300
Changed files: 2
Additions: 6
Deletions: 2
Total churn: 8

Files:
  airflow-core/tests/unit/auth/test_manager.py           +5/-2
  airflow-core/src/airflow/auth/managers/simple.py       +1/-0

Note: airflow-core/tests/unit/auth/test_manager.py matches the Tier B
allow glob (**/tests/**) but also matches **/auth*/** in the deny list.
Deny-list evaluation takes priority over allow-list (Golden rule 3).
