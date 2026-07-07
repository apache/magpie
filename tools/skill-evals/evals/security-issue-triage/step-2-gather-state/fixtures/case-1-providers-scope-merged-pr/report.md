<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### gh issue view 212

```json
{
  "number": 212,
  "title": "HTTP provider leaks Basic-Auth credentials into task logs",
  "body": "When the SimpleHttpOperator is used with Basic-Auth, the Authorization\nheader value is written verbatim into the task log at DEBUG level.\n\n**PR with the fix:** https://github.com/apache/airflow/pull/39812\n\n**Security mailing list thread:** (markdown import — no thread ID)",
  "labels": [
    {"name": "needs triage"},
    {"name": "providers"}
  ],
  "closedByPullRequestsReferences": [],
  "comments": []
}
```

### gh search prs cross-repo

```json
[
  {
    "number": 39812,
    "title": "Fix: redact Basic-Auth header from SimpleHttpOperator task logs",
    "state": "MERGED",
    "mergedAt": "2026-04-30T11:22:00Z",
    "author": {"login": "alice"},
    "url": "https://github.com/apache/airflow/pull/39812"
  }
]
```

### Gmail thread

null (markdown-imported tracker — no thread ID)

### Canned-response scan

No match found.

### Cross-reference search

No STRONG or MODERATE match found in closed trackers.
