<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tool: ruff
Confirmed findings (user selected all):

ruff:F401:airflow/models/xcom.py:5   — `os` imported but unused
ruff:E501:airflow/models/xcom.py:89  — line too long (103 > 88 characters)
ruff:E501:airflow/models/xcom.py:142 — line too long (95 > 88 characters)
ruff:F841:airflow/utils/helpers.py:34 — local variable `result` is assigned but never used

No security labels present.
