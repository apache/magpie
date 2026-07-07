<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Current candidate keywords: "local file read", "Connection extra", "worker filesystem", "task SDK"

### Gmail search 1 — prior outbound rejections

Query: list:security.airflow.apache.org "local file read" "connection extra" newer_than:180d

```json
[]
```

### Gmail search 2 — inbound without tracker

Query: list:security.airflow.apache.org "local file read" "connection extra" newer_than:180d -from:me -from:security@airflow.apache.org

```json
[]
```

No prior mailing-list rejection found for this shape.

### Closed-invalid tracker cross-check (unconditional)

Query: gh issue list --repo example-s/example-s --state closed --label "invalid" --search "connection extra worker filesystem" --limit 10 --json number,title,closedAt,url

```json
[
  {
    "number": 188,
    "title": "Local file read via Connection extra on the worker filesystem",
    "closedAt": "2026-03-04T11:22:00Z",
    "url": "https://github.com/example-s/example-s/issues/188"
  },
  {
    "number": 142,
    "title": "Scheduler log verbosity exposes connection IDs",
    "closedAt": "2026-01-09T08:00:00Z",
    "url": "https://github.com/example-s/example-s/issues/142"
  }
]
```

Closing comment on #188 (fetched to confirm disposition): "Closed invalid —
workers are operator-trusted in the security model; a Connection extra is a
secret the deployment already grants the worker, so reading it from the worker
filesystem is not a privilege boundary crossing. Matches the canned response
'When someone reports that a trusted component can read its own secrets'."

Match assessment: candidate matches #188 on BOTH component (worker filesystem /
Connection extra) AND bug-class (trusted-component reads own secret). #142 shares
only the loose "connection" keyword (different component, different bug class) —
loosely-related context, not a match.
