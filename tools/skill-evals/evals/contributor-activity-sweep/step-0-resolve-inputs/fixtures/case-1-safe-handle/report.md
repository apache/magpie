<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Inputs

- login argument: `justinmclean`
- window: 6 months
- today: 2026-05-19
- computed since: 2025-11-19

## API responses

**gh api repos/apache/magpie --jq '.created_at'**
```json
"2024-09-03T14:22:11Z"
```

Repo created 2024-09-03 — older than the window start of 2025-11-19. No trim needed.
