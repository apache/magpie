<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

threadId: AAMkAGQ8xZ3mPqRs

### dedup-index result from complete saved tracker index

```json
{
  "ok": true,
  "tracked": {},
  "untracked": [
    "AAMkAGQ8xZ3mPqRs"
  ],
  "complete": true,
  "truncated": false,
  "undecided": [],
  "rejected_ids": []
}
```

### Gmail on-thread check (2-bis) — get_thread AAMkAGQ8xZ3mPqRs (MINIMAL)

```json
[
  {
    "from": "researcher@example.com",
    "date": "2026-05-14T08:30:00Z",
    "snippet": "I discovered that a DAG-scoped API user can read XCom entries from DAGs they have no permission to access via GET /api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/xcomEntries..."
  }
]
```

Only one message in the thread — the reporter's inbound report.
No security-team reply present.
