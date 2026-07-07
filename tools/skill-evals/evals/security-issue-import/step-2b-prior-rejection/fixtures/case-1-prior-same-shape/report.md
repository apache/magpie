<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Current candidate keywords: "dag author", "variable", "sql injection", "PostgresOperator"

### Gmail search 1 — prior outbound rejections

Query: list:security.airflow.apache.org "dag author" "sql injection" newer_than:180d

```json
[
  {
    "threadId": "AAMkABC123",
    "from": "security@airflow.apache.org",
    "date": "2026-02-10T14:00:00Z",
    "subject": "Re: SQL injection via DAG variable in PostgresOperator",
    "snippet": "Per the project's security model, DAG authors are trusted to execute arbitrary code on the worker, including arbitrary SQL via operators. This is documented at https://airflow.apache.org/docs/apache-airflow/stable/security/security_model.html#dag-authors. We do not consider this a security issue.",
    "url": "https://lists.apache.org/thread/AAMkABC123"
  }
]
```

Team member match: security@airflow.apache.org is on the roster.
Canned-response shape: "Per the project's security model" opening — matches
"When someone claims Dag author-provided 'user input' is dangerous".

### Gmail search 2 — inbound without tracker

Query: list:security.airflow.apache.org "dag author" "sql injection" newer_than:180d -from:me -from:security@airflow.apache.org

```json
[
  {
    "threadId": "AAMkABC123",
    "from": "prev-reporter@example.com",
    "date": "2026-02-09T09:00:00Z",
    "snippet": "I found a SQL injection via a DAG variable passed to PostgresOperator..."
  }
]
```

Cross-reference check: gh search issues "AAMkABC123" --repo example-s/example-s → no results.
Confirmed: prior report was rejected without creating a tracker.

Reporter follow-up after team reply: no messages from prev-reporter@example.com
after 2026-02-10. Thread closed.
