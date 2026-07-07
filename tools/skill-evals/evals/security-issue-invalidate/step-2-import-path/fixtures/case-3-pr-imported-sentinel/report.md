<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Mock: gh issue view 341 --repo airflow-s/airflow-s

```json
{
  "number": 341,
  "title": "SSRF via HTTP operator allow_redirects flag missing validation",
  "state": "OPEN",
  "labels": [{"name": "security issue"}, {"name": "needs triage"}, {"name": "providers"}],
  "body": "**Security mailing list thread:** N/A — opened from public PR apache/airflow#45210; no security@ thread\n\n**Affected versions:** providers-http 4.6.0\n\n**Reporter credited as:** _No response_\n\n**CVE tool link:** _No response_\n\n**PR with the fix:** apache/airflow#45210",
  "comments": [
    {
      "author": {"login": "triager-a"},
      "body": "The HTTP operator's allow_redirects is a feature, not a bug. The DAG author controls this flag deliberately. No SSRF path exists that isn't already gated by DAG-level trust.",
      "url": "https://github.com/airflow-s/airflow-s/issues/341#issuecomment-3001"
    }
  ]
}
```
