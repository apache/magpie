<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: gh issue view 287 --repo airflow-s/airflow-s

```json
{
  "number": 287,
  "title": "DAG serialization leaks connection passwords to unprivileged readers",
  "state": "OPEN",
  "labels": [{"name": "security issue"}, {"name": "needs triage"}, {"name": "airflow"}],
  "body": "**Security mailing list thread:** No public archive URL — tracked privately on Gmail thread 18f3a2b9c1d4e507\n\n**Affected versions:** 2.7.3\n\n**Reporter credited as:** Bob Svensson <bob@corp.io>\n\n**CVE tool link:** _No response_\n\n**PR with the fix:** _No response_",
  "comments": [
    {
      "author": {"login": "triager-b"},
      "body": "Connection passwords in serialized DAGs are only readable by users with View access to the DAG definition, which already implies trusted access. Working as intended.",
      "url": "https://github.com/airflow-s/airflow-s/issues/287#issuecomment-2001"
    }
  ]
}
```
