<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

CI: SUCCESS
Unresolved threads: 0
Findings:
  - severity: major, file: airflow/hooks/http.py:55, description: missing Apache header, no CI tooling
  - severity: major, file: airflow/utils/cron.py:12, description: MIT-licensed vendored code, LICENSE not updated
  - severity: minor, file: tests/test_http.py:8, description: missing autospec on mock
