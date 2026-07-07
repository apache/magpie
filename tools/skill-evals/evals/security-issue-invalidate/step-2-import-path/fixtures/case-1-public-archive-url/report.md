<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: gh issue view 312 --repo airflow-s/airflow-s

```json
{
  "number": 312,
  "title": "Arbitrary file read via log endpoint without auth check",
  "state": "OPEN",
  "labels": [{"name": "security issue"}, {"name": "needs triage"}, {"name": "airflow"}],
  "body": "**Security mailing list thread:** https://lists.apache.org/thread/abc123xyz\n\n**Affected versions:** 2.8.0, 2.8.1\n\n**Reporter credited as:** Alice Nguyen <alice@example.com>\n\n**CVE tool link:** _No response_\n\n**PR with the fix:** _No response_",
  "comments": [
    {
      "author": {"login": "triager-a"},
      "body": "After review: the log endpoint requires session auth; the request must already carry a valid session cookie. This is not an unauthenticated read.",
      "url": "https://github.com/airflow-s/airflow-s/issues/312#issuecomment-1001"
    }
  ]
}
```
