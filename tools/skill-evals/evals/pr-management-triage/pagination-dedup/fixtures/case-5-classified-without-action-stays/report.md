<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The search is sorted by `updated-asc`. These pages were fetched serially:

Page 1:

```json
[
  {"number": 61, "updatedAt": "2026-08-05T12:20:00Z", "headRefOid": "head-61"},
  {"number": 62, "updatedAt": "2026-08-05T12:25:00Z", "headRefOid": "head-62"}
]
```

Page 1 reports `hasNextPage: false`. PR 61 was classified earlier in this
session but no action was taken on it — the cache entry has no terminal
`action_taken`.

The session cache for this repository holds:

```json
{
  "prs": {
    "61": {
      "head_sha": "head-61",
      "classification": "deterministic_flag",
      "suggested_action": "draft"
    }
  }
}
```
