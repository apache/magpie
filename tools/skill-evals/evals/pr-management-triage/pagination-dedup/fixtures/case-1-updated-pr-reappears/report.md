<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The search is sorted by `updated-asc`. These pages were fetched serially:

Page 1:

```json
[
  {"number": 11, "updatedAt": "2026-08-05T10:00:00Z", "headRefOid": "old-11"},
  {"number": 12, "updatedAt": "2026-08-05T10:05:00Z", "headRefOid": "head-12"}
]
```

Page 2, after PR 11 was updated and moved to the end of the search:

```json
[
  {"number": 13, "updatedAt": "2026-08-05T10:10:00Z", "headRefOid": "head-13"},
  {"number": 11, "updatedAt": "2026-08-05T10:15:00Z", "headRefOid": "fresh-11"}
]
```

Page 2 reports `hasNextPage: false`.
