<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Current candidate keywords: "authenticated user", "scheduler", "dos", "large payload"

### Gmail search 1 — prior outbound rejections

Query: list:security.airflow.apache.org "authenticated user" "dos" newer_than:180d

```json
[
  {
    "threadId": "AAMkADEF456",
    "from": "security@airflow.apache.org",
    "date": "2026-01-20T11:00:00Z",
    "subject": "Re: DoS via large dagrun conf",
    "snippet": "Thank you for the report. We do not consider DoS by authenticated users a security vulnerability per our Security Model. Authenticated users are trusted within the scope of their permissions.",
    "url": "https://lists.apache.org/thread/AAMkADEF456"
  }
]
```

Team member match: security@airflow.apache.org is on the roster.
Canned-response shape: "We do not consider DoS by authenticated users" — matches
"When someone reports a DoS that requires authenticated access".

### Gmail search 2 — inbound without tracker

```json
[
  {
    "threadId": "AAMkADEF456",
    "from": "prior-reporter@example.com",
    "date": "2026-01-19T08:00:00Z",
    "snippet": "An authenticated user can crash the scheduler by sending a 50MB conf payload..."
  }
]
```

Cross-reference: no tracker for AAMkADEF456. Rejected without tracker.

Reporter follow-up after team reply:
```json
[
  {
    "from": "prior-reporter@example.com",
    "date": "2026-01-22T09:30:00Z",
    "snippet": "But what if the user is only DAG-viewer and still manages to trigger a run via the API? Surely that changes things?"
  },
  {
    "from": "security@airflow.apache.org",
    "date": "2026-01-23T10:00:00Z",
    "snippet": "The trigger permission is separate from the viewer role; a user with only DAG-view cannot trigger runs. The attack requires trigger permissions, which is an authoritative role. Our position stands."
  }
]
```

Reporter did not reply after the team's follow-up. Thread closed.
The prior reporter pushed back on the viewer-vs-trigger permission distinction;
the team added a clarification paragraph covering that ambiguity.
