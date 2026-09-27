<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

All rows voted in the last year, so every row has the same recency weight. Metrics measured: prs_merged, issues_filed.

| Row | Target | Outcome | prs_merged | issues_filed |
|---|---|---|---|---|
| r1 | committer | elected | 40 | 3 |
| r2 | committer | elected | 48 | 2 |
| r3 | committer | elected | 55 | 4 |
| r4 | committer | elected | 60 | 3 |
| r5 | committer | elected | 72 | 5 |
| r6 | committer | deferred | 10 | 0 |
| r7 | pmc | elected | 45 | 2 |
| r8 | pmc | elected | 52 | 1 |
| r9 | pmc | deferred | 30 | 1 |

`contributor-metrics floors` output for these rows:

```json
{
  "floors": {
    "committer": {
      "issues_filed": 3,
      "prs_merged": 48
    },
    "pmc": {}
  },
  "evidence_only": {
    "committer": [],
    "pmc": []
  },
  "no_floors_for": [
    "pmc"
  ],
  "notes": [
    "pmc: 2 elected rows, fewer than 5; no floors proposed"
  ]
}
```
