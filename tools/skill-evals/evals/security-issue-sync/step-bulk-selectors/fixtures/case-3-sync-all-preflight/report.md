<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Current time: 2026-10-03T12:00:00Z

Operator selector:

```text
sync all
```

Mocked `gh issue list --repo <tracker> --state open --limit 100 --json number,title,labels`:

```json
[
  {"number": 99,  "title": "Rejected reports ledger", "labels": [{"name": "rejections-ledger"}]},
  {"number": 210, "title": "Trigger DAG API bypass", "labels": [{"name": "airflow"}, {"name": "cve allocated"}, {"name": "pr merged"}]},
  {"number": 211, "title": "Log file path traversal", "labels": [{"name": "airflow"}, {"name": "cve allocated"}, {"name": "fix released"}]},
  {"number": 212, "title": "Connection test SSRF", "labels": [{"name": "airflow"}, {"name": "cve allocated"}, {"name": "pr merged"}]},
  {"number": 214, "title": "Variable export leaks masked values", "labels": [{"name": "airflow"}, {"name": "cve allocated"}, {"name": "pr merged"}, {"name": "announced"}]},
  {"number": 215, "title": "Webserver header injection", "labels": [{"name": "airflow"}, {"name": "needs triage"}]}
]
```

Mocked `gh issue list --repo <tracker> --state closed --label "announced" --limit 50 --json number,title,labels,closedAt`
(raw output, before the 90-day `--jq` filter):

```json
[
  {"number": 150, "title": "Old DAG code view XSS", "labels": [{"name": "announced"}], "closedAt": "2026-06-05T10:00:00Z"},
  {"number": 180, "title": "Pool API authorization bypass", "labels": [{"name": "announced"}], "closedAt": "2026-08-19T10:00:00Z"},
  {"number": 195, "title": "Asset event spoofing", "labels": [{"name": "announced"}], "closedAt": "2026-09-23T10:00:00Z"}
]
```

Mocked pre-flight GraphQL state (one row per issue the orchestrator queried).
"Marker" means the last comment's body starts with `<!-- apache-magpie: status-rollup v1 -->`
— a skill-authored rollup proposal posted under the operator's own account (`potiuk`) that nobody has answered yet.

| Issue | state | closedAt | updatedAt | labels | last comment author | last comment createdAt | last comment body |
|---|---|---|---|---|---|---|---|
| 180 | CLOSED | 2026-08-19T10:00:00Z | 2026-08-19T10:00:00Z | airflow, cve allocated, pr merged, fix released, announced | potiuk | 2026-08-19T10:00:00Z | Marker |
| 195 | CLOSED | 2026-09-23T10:00:00Z | 2026-09-23T10:00:00Z | airflow, cve allocated, pr merged, fix released, announced | potiuk | 2026-09-23T10:00:00Z | Marker |
| 210 | OPEN | — | 2026-10-01T08:00:00Z | airflow, cve allocated, pr merged | potiuk | 2026-10-01T08:00:00Z | Marker |
| 211 | OPEN | — | 2026-09-20T08:00:00Z | airflow, cve allocated, fix released | potiuk | 2026-09-20T08:00:00Z | Marker |
| 212 | OPEN | — | 2026-09-30T11:00:00Z | airflow, cve allocated, pr merged | dave-reporter | 2026-09-30T11:00:00Z | `Could you share the release date?` |
| 214 | OPEN | — | 2026-09-10T08:00:00Z | airflow, cve allocated, pr merged, announced | github-actions[bot] | 2026-09-10T08:00:00Z | `Milestone 3.2.2 closed.` |
| 215 | OPEN | — | 2026-09-28T08:00:00Z | airflow, needs triage | potiuk | 2026-09-28T08:00:00Z | Marker |
