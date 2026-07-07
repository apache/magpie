<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Inputs

- login argument: `contributor-x`
- window: 6 months
- today: 2026-05-19
- computed since (before trim): 2025-11-19

## API responses

**gh api repos/apache/magpie --jq '.created_at'**
```json
"2026-03-01T09:00:00Z"
```

Repo created 2026-03-01 — newer than the computed window start of 2025-11-19.
The window must be trimmed to the repo creation date.
