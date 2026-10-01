<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The search is sorted by `updated-asc`. These pages were fetched serially:

Page 1:

```json
[
  {"number": 51, "updatedAt": "2026-08-05T12:10:00Z", "headRefOid": "fresh-51"},
  {"number": 52, "updatedAt": "2026-08-05T12:15:00Z", "headRefOid": "head-52"}
]
```

Page 1 reports `hasNextPage: false`. PR 51 was acted on earlier in this
session, but its head SHA differs from the cached one — the contributor
pushed since.

The session cache for this repository holds:

```json
{
  "prs": {
    "51": {
      "head_sha": "old-51",
      "classification": "deterministic_flag",
      "suggested_action": "rebase",
      "action_taken": "rebase",
      "action_at": "2026-08-05T09:45:00Z"
    }
  }
}
```
