<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Current issue: #234
Title: "Authenticated user can trigger scheduler DoS via large conf payload"
Code pointer: airflow/models/dagrun.py — DagRun.verify_integrity()
Vulnerability class: denial-of-service by authenticated user

### gh search issues — rejection precedents

```json
[
  {
    "number": 187,
    "title": "Scheduler OOM via crafted dagrun conf",
    "labels": ["not CVE worthy"],
    "closedAt": "2025-08-14T00:00:00Z",
    "body_excerpt": "Code pointer: airflow/models/dagrun.py — conf size validation. Closed: authenticated DoS is outside the Security Model boundary."
  }
]
```

Match assessment: STRONG — same file (airflow/models/dagrun.py), same
vulnerability class (authenticated DoS), same attacker model.

### gh search issues — positive precedents

No results.

Budget: 2 of 3 additional calls used.
