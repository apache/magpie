<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The search is sorted by `updated-asc`. These pages were fetched serially:

Page 1:

```json
[
  {"number": 41, "updatedAt": "2026-08-05T12:00:00Z", "headRefOid": "head-41"},
  {"number": 42, "updatedAt": "2026-08-05T12:05:00Z", "headRefOid": "head-42"}
]
```

Page 1 reports `hasNextPage: false`.

The session cache for this repository holds:

```json
{
  "prs": {
    "41": {
      "head_sha": "head-41",
      "classification": "deterministic_flag",
      "suggested_action": "comment",
      "action_taken": "comment",
      "action_at": "2026-08-05T09:30:00Z"
    }
  }
}
```
