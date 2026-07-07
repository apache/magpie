<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Detected scope: airflow

## Mock: gh pr view 52199 --repo apache/airflow --json milestone

```json
{
  "number": 52199,
  "title": "fix: prevent XCom pickle deserialization of untrusted payloads",
  "milestone": {"title": "Airflow 3.2.2"}
}
```

## Mock: gh api repos/airflow-s/airflow-s/milestones --jq '.[].title'

```text
Airflow 3.2.1
Airflow 3.2.2
Airflow 3.3.0
Providers 2025-06-15
```
