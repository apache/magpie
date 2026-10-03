<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Current time: 2026-10-03T12:00:00Z

Operator selector:

```text
sync all open
```

Mocked `gh issue list --repo <tracker> --state open --limit 100 --json number,title,labels`:

```json
[
  {"number": 270, "title": "REST API pagination leaks hidden DAGs", "labels": [{"name": "airflow"}, {"name": "cve allocated"}]},
  {"number": 271, "title": "Trigger form stored XSS", "labels": [{"name": "airflow"}, {"name": "needs triage"}]}
]
```

Mocked pre-flight GraphQL state:

| Issue | state | updatedAt | labels | last comment author | last comment createdAt | last comment body |
|---|---|---|---|---|---|---|
| 270 | OPEN | 2026-10-03T09:00:00Z | airflow, cve allocated, security issue | dana-reporter | 2026-10-03T09:00:00Z | `Any news on the fix? I can retest today…` |
| 271 | OPEN | 2026-09-30T14:00:00Z | airflow, needs triage, security issue | erik-maintainer | 2026-09-30T14:00:00Z | `I can reproduce this on main…` |
