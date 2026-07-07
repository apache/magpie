<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### gh issue view 218

```json
{
  "number": 218,
  "title": "SQL injection via DAG-author-controlled variable in PostgresOperator",
  "body": "A DAG author can store a malicious SQL fragment in an Airflow Variable\nand pass it into the sql= parameter of PostgresOperator without sanitisation.\nThis allows arbitrary SQL execution against the target database.\n\n**PR with the fix:** (none)\n\n**Security mailing list thread:** threadId=AAMkAGQ1NjY",
  "labels": [
    {"name": "needs triage"}
  ],
  "closedByPullRequestsReferences": [],
  "comments": []
}
```

### gh search prs cross-repo

No results.

### Gmail thread (threadId=AAMkAGQ1NjY, last 3 messages)

```json
[
  {
    "from": "reporter@example.com",
    "date": "2026-05-01T09:00:00Z",
    "snippet": "I found that the sql= parameter is not sanitised..."
  },
  {
    "from": "security@airflow.apache.org",
    "date": "2026-05-02T14:30:00Z",
    "snippet": "Thank you for the report. We are reviewing this."
  }
]
```

Last message is from the security team — no new activity from reporter since.

### Canned-response scan

EXACT MATCH: "When someone claims Dag author-provided 'user input' is dangerous"
Section heading matches the report shape: DAG author routes untrusted input
to an operator parameter, claims this is a security vulnerability.

### Cross-reference search

No STRONG or MODERATE match found in closed trackers.
